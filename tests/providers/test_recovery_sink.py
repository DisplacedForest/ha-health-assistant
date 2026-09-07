from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from common import SyntheticProvider
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from custom_components.health_assistant.providers import (
    CandidateRecoveryDeletion,
    CandidateRecoveryObservation,
    ProviderCapabilities,
    ProviderCapabilityError,
)
from custom_components.health_assistant.signals import SIGNAL_HEALTH_DATA_UPDATED
from custom_components.health_assistant.store.recovery_models import RecoveryError


class RecoveryProvider(SyntheticProvider):
    @property
    def recovery_source_ids(self):
        return frozenset(("selected-account",))


def candidate(revision=1):
    return CandidateRecoveryObservation(
        "selected-account",
        "night",
        revision,
        "hrv_sdnn",
        50,
        "ms",
        datetime(2026, 9, 6, tzinfo=UTC),
        datetime(2026, 9, 6, 8, tzinfo=UTC),
    )


async def test_recovery_capability_source_person_and_signal(
    hass, registry, database, repository
):
    provider = RecoveryProvider(
        capabilities=ProviderCapabilities(recovery_metrics=frozenset(("hrv_sdnn",)))
    )
    registry.register(provider)
    other = SyntheticProvider(key="other")
    registry.register(other)
    with pytest.raises(ProviderCapabilityError):
        await registry.sink("other").async_apply_recovery_changes([candidate()])
    sink = registry.sink(provider.key)
    changed = Mock()
    unsubscribe = async_dispatcher_connect(hass, SIGNAL_HEALTH_DATA_UPDATED, changed)
    result = await sink.async_apply_recovery_changes(
        [candidate()], checkpoint={"cursor": "first"}
    )
    await hass.async_block_till_done()
    assert result[0].observation.provider == "synthetic"
    assert changed.call_count == 1
    assert repository.get_provider_state(provider.key) == {"cursor": "first"}
    await sink.async_apply_recovery_changes([candidate()])
    await hass.async_block_till_done()
    assert changed.call_count == 1
    for value in (
        replace(candidate(), source_id="unselected"),
        replace(candidate(), person_id="other"),
    ):
        with pytest.raises(RecoveryError):
            await sink.async_apply_recovery_changes([value])
    assert registry.status("synthetic").degraded
    assert not registry.status("other").degraded
    assert changed.call_count == 1
    assert database.execute("SELECT count(*) FROM recovery_records")[0][0] == 1
    deleted = CandidateRecoveryDeletion("selected-account", "night", 2, "hrv_sdnn")
    await sink.async_apply_recovery_changes([deleted])
    stale = await sink.async_apply_recovery_changes([candidate()])
    await hass.async_block_till_done()
    assert stale[0].action == "stale_revision"
    assert changed.call_count == 2
    assert (
        database.execute("SELECT source_state FROM recovery_records")[0][0] == "deleted"
    )
    unsubscribe()


async def test_recovery_batch_conflict_has_no_dispatch_or_cursor(
    hass, registry, repository
):
    provider = RecoveryProvider(
        capabilities=ProviderCapabilities(recovery_metrics=frozenset(("hrv_sdnn",)))
    )
    registry.register(provider)
    sink = registry.sink(provider.key)
    await sink.async_apply_recovery_changes(
        [candidate()], checkpoint={"cursor": "before"}
    )
    await hass.async_block_till_done()
    changed = Mock()
    unsubscribe = async_dispatcher_connect(hass, SIGNAL_HEALTH_DATA_UPDATED, changed)
    with pytest.raises(RecoveryError, match="revision_conflict"):
        await sink.async_apply_recovery_changes(
            [
                replace(candidate(), external_id="new"),
                replace(candidate(), value=51),
            ],
            checkpoint={"cursor": "after"},
        )
    await hass.async_block_till_done()
    assert not changed.called
    assert repository.get_provider_state(provider.key) == {"cursor": "before"}
    unsubscribe()


class MultiAccountRecoveryProvider(RecoveryProvider):
    @property
    def recovery_source_ids(self):
        return frozenset(("selected-account", "second-account"))


async def test_recovery_account_failure_survives_other_account_and_scalar_success(
    hass, registry
):
    from common import weight_candidate

    from custom_components.health_assistant.store import MetricType

    provider = MultiAccountRecoveryProvider(
        capabilities=ProviderCapabilities(
            recovery_metrics=frozenset(("hrv_sdnn",)),
            metrics=frozenset((MetricType.WEIGHT,)),
        )
    )
    registry.register(provider)
    sink = registry.sink(provider.key)
    await sink.async_apply_recovery_changes([candidate()])
    with pytest.raises(RecoveryError, match="revision_conflict"):
        await sink.async_apply_recovery_changes([replace(candidate(), value=51)])
    assert registry.status(provider.key, "selected-account").degraded
    assert not registry.status(provider.key, "second-account").degraded
    await sink.async_apply_recovery_changes(
        [replace(candidate(), source_id="second-account")]
    )
    await sink.async_add_observation(weight_candidate())
    await registry.async_sync(provider.key)
    assert registry.status(provider.key, "selected-account").degraded
    assert not registry.status(provider.key, "second-account").degraded
    assert registry.status(provider.key).degraded
    assert registry.statuses[provider.key].degraded
    await sink.async_apply_recovery_changes([candidate(revision=2)])
    assert not registry.status(provider.key, "selected-account").degraded
    assert not registry.status(provider.key).degraded
    assert (
        registry.status(provider.key, "selected-account").last_error
        == "revision_conflict"
    )


async def test_recovery_poll_conflict_keeps_source_status_without_adapter_error(
    hass, registry
):
    async def sync(sink, _state):
        await sink.async_apply_recovery_changes([replace(candidate(), value=51)])

    provider = MultiAccountRecoveryProvider(
        capabilities=ProviderCapabilities(recovery_metrics=frozenset(("hrv_sdnn",))),
        sync=sync,
    )
    registry.register(provider)
    await registry.sink(provider.key).async_apply_recovery_changes([candidate()])
    await registry.async_sync(provider.key)
    assert registry.status(provider.key, "selected-account").degraded
    assert not registry.status(provider.key, "second-account").degraded
    await registry.sink(provider.key).async_apply_recovery_changes(
        [candidate(revision=2)]
    )
    assert not registry.status(provider.key).degraded


async def test_recovery_metric_permission_is_independent(registry):
    provider = RecoveryProvider(
        capabilities=ProviderCapabilities(recovery_metrics=frozenset(("hrv_sdnn",)))
    )
    registry.register(provider)
    for metric, code in (
        ("hrv_rmssd", "recovery_metric_not_allowed"),
        ("hrv", "unsupported_method"),
    ):
        with pytest.raises(RecoveryError, match=code):
            await registry.sink(provider.key).async_apply_recovery_changes(
                [replace(candidate(), metric=metric)]
            )
