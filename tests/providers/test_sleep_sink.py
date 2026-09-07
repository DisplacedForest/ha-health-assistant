from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from common import SyntheticProvider
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from custom_components.health_assistant.providers import (
    CandidateSleepDeletion,
    CandidateSleepSession,
    ProviderCapabilities,
    ProviderCapabilityError,
)
from custom_components.health_assistant.signals import SIGNAL_HEALTH_DATA_UPDATED
from custom_components.health_assistant.store.sleep_models import SleepError


class SleepProvider(SyntheticProvider):
    @property
    def sleep_source_ids(self):
        return frozenset(("selected-account",))


def candidate(revision=1):
    return CandidateSleepSession(
        "selected-account",
        "night",
        revision,
        datetime(2026, 9, 6, tzinfo=UTC),
        datetime(2026, 9, 6, 8, tzinfo=UTC),
    )


async def test_sleep_capability_source_person_and_signal(
    hass, registry, database, repository
):
    provider = SleepProvider(capabilities=ProviderCapabilities(sleep_sessions=True))
    registry.register(provider)
    other = SyntheticProvider(key="other")
    registry.register(other)
    with pytest.raises(ProviderCapabilityError):
        await registry.sink("other").async_apply_sleep_changes([candidate()])
    sink = registry.sink(provider.key)
    changed = Mock()
    unsubscribe = async_dispatcher_connect(hass, SIGNAL_HEALTH_DATA_UPDATED, changed)
    result = await sink.async_apply_sleep_changes(
        [candidate()], checkpoint={"cursor": "first"}
    )
    await hass.async_block_till_done()
    assert result[0].session.provider == "synthetic"
    assert changed.call_count == 1
    assert repository.get_provider_state(provider.key) == {"cursor": "first"}
    await sink.async_apply_sleep_changes([candidate()])
    await hass.async_block_till_done()
    assert changed.call_count == 1
    for value in (
        replace(candidate(), source_id="unselected"),
        replace(candidate(), person_id="other"),
    ):
        with pytest.raises(SleepError):
            await sink.async_apply_sleep_changes([value])
    assert registry.status("synthetic").degraded
    assert not registry.status("other").degraded
    assert changed.call_count == 1
    assert database.execute("SELECT count(*) FROM sleep_sessions")[0][0] == 1
    deleted = CandidateSleepDeletion("selected-account", "night", 2)
    await sink.async_apply_sleep_changes([deleted])
    stale = await sink.async_apply_sleep_changes([candidate()])
    await hass.async_block_till_done()
    assert stale[0].action == "stale_revision"
    assert changed.call_count == 2
    assert (
        database.execute("SELECT source_state FROM sleep_sessions")[0][0] == "deleted"
    )
    unsubscribe()


async def test_sleep_batch_conflict_has_no_dispatch_or_cursor(
    hass, registry, repository
):
    provider = SleepProvider(capabilities=ProviderCapabilities(sleep_sessions=True))
    registry.register(provider)
    sink = registry.sink(provider.key)
    await sink.async_apply_sleep_changes([candidate()], checkpoint={"cursor": "before"})
    await hass.async_block_till_done()
    changed = Mock()
    unsubscribe = async_dispatcher_connect(hass, SIGNAL_HEALTH_DATA_UPDATED, changed)
    with pytest.raises(SleepError, match="revision_conflict"):
        await sink.async_apply_sleep_changes(
            [
                replace(candidate(), external_id="new"),
                replace(candidate(), reported_totals={"asleep": 0}),
            ],
            checkpoint={"cursor": "after"},
        )
    await hass.async_block_till_done()
    assert not changed.called
    assert repository.get_provider_state(provider.key) == {"cursor": "before"}
    unsubscribe()


class MultiAccountSleepProvider(SleepProvider):
    @property
    def sleep_source_ids(self):
        return frozenset(("selected-account", "second-account"))


async def test_sleep_account_failure_survives_other_account_and_scalar_success(
    hass, registry
):
    from common import weight_candidate

    from custom_components.health_assistant.store import MetricType

    provider = MultiAccountSleepProvider(
        capabilities=ProviderCapabilities(
            sleep_sessions=True, metrics=frozenset((MetricType.WEIGHT,))
        )
    )
    registry.register(provider)
    sink = registry.sink(provider.key)
    await sink.async_apply_sleep_changes([candidate()])
    with pytest.raises(SleepError, match="revision_conflict"):
        await sink.async_apply_sleep_changes(
            [replace(candidate(), reported_totals={"asleep": 0})]
        )
    assert registry.status(provider.key, "selected-account").degraded
    assert not registry.status(provider.key, "second-account").degraded
    await sink.async_apply_sleep_changes(
        [replace(candidate(), source_id="second-account")]
    )
    await sink.async_add_observation(weight_candidate())
    await registry.async_sync(provider.key)
    assert registry.status(provider.key, "selected-account").degraded
    assert not registry.status(provider.key, "second-account").degraded
    assert registry.status(provider.key).degraded
    assert registry.statuses[provider.key].degraded
    await sink.async_apply_sleep_changes([candidate(revision=2)])
    assert not registry.status(provider.key, "selected-account").degraded
    assert not registry.status(provider.key).degraded
    assert (
        registry.status(provider.key, "selected-account").last_error
        == "revision_conflict"
    )


async def test_sleep_poll_conflict_keeps_source_status_without_adapter_error(
    hass, registry
):
    async def sync(sink, _state):
        await sink.async_apply_sleep_changes(
            [replace(candidate(), reported_totals={"asleep": 0})]
        )

    provider = MultiAccountSleepProvider(
        capabilities=ProviderCapabilities(sleep_sessions=True), sync=sync
    )
    registry.register(provider)
    await registry.sink(provider.key).async_apply_sleep_changes([candidate()])
    await registry.async_sync(provider.key)
    assert registry.status(provider.key, "selected-account").degraded
    assert not registry.status(provider.key, "second-account").degraded
    await registry.sink(provider.key).async_apply_sleep_changes([candidate(revision=2)])
    assert not registry.status(provider.key).degraded
