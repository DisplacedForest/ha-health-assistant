import asyncio

import pytest
from common import SyntheticProvider, weight_candidate

from custom_components.health_assistant.providers import (
    ProviderError,
    ProviderRegistry,
)
from custom_components.health_assistant.store import (
    DEFAULT_PERSON_ID,
    HealthRepository,
    MetricType,
)


async def test_register_rejects_duplicate_key(hass, registry):
    registry.register(SyntheticProvider())
    with pytest.raises(ProviderError):
        registry.register(SyntheticProvider())


async def test_raising_provider_is_degraded_and_isolated(hass, registry, repository):
    async def broken_sync(sink, state):
        raise RuntimeError("boom")

    async def healthy_sync(sink, state):
        await sink.async_add_observation(weight_candidate())
        return {"cursor": "1"}

    broken = SyntheticProvider(key="broken", sync=broken_sync)
    healthy = SyntheticProvider(key="healthy", sync=healthy_sync)
    registry.register(broken)
    registry.register(healthy)
    await registry.async_sync("broken")
    await registry.async_sync("healthy")

    assert registry.status("broken").degraded
    assert "boom" in registry.status("broken").last_error
    assert not registry.status("healthy").degraded
    assert registry.status("healthy").last_success is not None
    assert len(repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)) == 1


async def test_hanging_provider_times_out_to_degraded(hass, registry):
    async def hanging_sync(sink, state):
        await asyncio.sleep(30)

    provider = SyntheticProvider(key="hanging", sync=hanging_sync)
    registry.register(provider)
    await registry.async_sync("hanging")
    assert registry.status("hanging").degraded
    assert registry.status("hanging").last_error


async def test_garbage_producing_provider_is_degraded(hass, registry, repository):
    async def garbage_sync(sink, state):
        await sink.async_add_observation(weight_candidate(value=float("inf")))

    provider = SyntheticProvider(key="garbage", sync=garbage_sync)
    registry.register(provider)
    await registry.async_sync("garbage")
    assert registry.status("garbage").degraded
    assert repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT) == []


async def test_provider_recovers_after_successful_sync(hass, registry):
    attempts = []

    async def flaky_sync(sink, state):
        attempts.append(state)
        if len(attempts) == 1:
            raise RuntimeError("transient")
        return {"cursor": "2"}

    provider = SyntheticProvider(key="flaky", sync=flaky_sync)
    registry.register(provider)
    await registry.async_sync("flaky")
    assert registry.status("flaky").degraded
    await registry.async_sync("flaky")
    assert not registry.status("flaky").degraded


async def test_sync_state_persists_and_survives_failed_sync(hass, registry, repository):
    async def sync(sink, state):
        return {"cursor": state.get("cursor", 0) + 1}

    provider = SyntheticProvider(key="cursor", sync=sync)
    registry.register(provider)
    await registry.async_sync("cursor")
    await registry.async_sync("cursor")
    assert provider.sync_calls == [{}, {"cursor": 1}]
    assert repository.get_provider_state("cursor") == {"cursor": 2}

    async def broken_sync(sink, state):
        raise RuntimeError("boom")

    provider._sync = broken_sync
    await registry.async_sync("cursor")
    assert repository.get_provider_state("cursor") == {"cursor": 2}


async def test_sync_state_survives_restart(hass, database, repository):
    async def sync(sink, state):
        return {"cursor": state.get("cursor", 0) + 1}

    first = ProviderRegistry(hass, repository, sync_timeout=0.5)
    first.register(SyntheticProvider(key="restarting", sync=sync))
    await first.async_sync("restarting")

    fresh_repository = HealthRepository(database)
    second = ProviderRegistry(hass, fresh_repository, sync_timeout=0.5)
    reborn = SyntheticProvider(key="restarting", sync=sync)
    second.register(reborn)
    await second.async_sync("restarting")
    assert reborn.sync_calls == [{"cursor": 1}]
    assert fresh_repository.get_provider_state("restarting") == {"cursor": 2}


async def test_start_isolates_failing_provider(hass, registry):
    class ExplodingStart(SyntheticProvider):
        async def async_start(self, sink):
            raise RuntimeError("no start")

    exploding = ExplodingStart(key="exploding")
    healthy = SyntheticProvider(key="healthy")
    registry.register(exploding)
    registry.register(healthy)
    await registry.async_start()
    assert registry.status("exploding").degraded
    assert not registry.status("healthy").degraded
    await registry.async_stop()


async def test_stop_waits_for_inflight_sync(hass, registry):
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_sync(sink, state):
        started.set()
        await release.wait()
        return {"done": True}

    provider = SyntheticProvider(key="slow", sync=slow_sync)
    registry.register(provider)
    sync_task = hass.async_create_task(registry.async_sync("slow"))
    await started.wait()
    stop_task = hass.async_create_task(registry.async_stop())
    for _ in range(5):
        await asyncio.sleep(0)
    assert not stop_task.done()
    release.set()
    await sync_task
    await stop_task
    assert not registry.status("slow").degraded


async def test_polled_provider_syncs_on_interval(hass, registry, short_interval):
    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    async def sync(sink, state):
        return {"cursor": state.get("cursor", 0) + 1}

    provider = SyntheticProvider(key="polled", poll_interval=short_interval, sync=sync)
    registry.register(provider)
    await registry.async_start()
    async_fire_time_changed(hass, dt_util.utcnow() + short_interval * 2)
    await hass.async_block_till_done()
    assert provider.sync_calls == [{}]
    await registry.async_stop()
    async_fire_time_changed(hass, dt_util.utcnow() + short_interval * 4)
    await hass.async_block_till_done()
    assert provider.sync_calls == [{}]


async def test_start_seeds_priorities_from_capabilities(hass, registry, repository):
    from custom_components.health_assistant.providers import ProviderCapabilities

    first = SyntheticProvider(
        key="first",
        capabilities=ProviderCapabilities(metrics=frozenset({MetricType.WEIGHT})),
    )
    second = SyntheticProvider(
        key="second",
        capabilities=ProviderCapabilities(metrics=frozenset({MetricType.WEIGHT})),
    )
    registry.register(first)
    registry.register(second)
    await registry.async_start()
    assert repository.get_priority(MetricType.WEIGHT) == ["first", "second"]
    await registry.async_stop()

    await registry.async_start()
    assert repository.get_priority(MetricType.WEIGHT) == ["first", "second"]
    await registry.async_stop()
