import pytest
from common import OBSERVED_AT, SyntheticProvider, weight_candidate

from custom_components.health_assistant.providers import (
    CandidateWorkout,
    ProviderCapabilities,
    ProviderCapabilityError,
)
from custom_components.health_assistant.store import (
    DEFAULT_PERSON_ID,
    MetricType,
    StoreValidationError,
    UnitConversionError,
)


async def test_sink_stores_canonical_observation_with_provider_identity(
    hass, registry, repository
):
    provider = SyntheticProvider()
    registry.register(provider)
    stored = await registry.sink(provider.key).async_add_observation(
        weight_candidate(value=176.37, unit="lb")
    )
    assert stored.provider == "synthetic"
    assert stored.unit == "kg"
    assert stored.value == pytest.approx(80.0, abs=0.01)
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert len(rows) == 1
    assert rows[0].provider == "synthetic"


async def test_sink_rejects_undeclared_metric(hass, registry):
    provider = SyntheticProvider(
        capabilities=ProviderCapabilities(metrics=frozenset({MetricType.STEPS}))
    )
    registry.register(provider)
    with pytest.raises(ProviderCapabilityError):
        await registry.sink(provider.key).async_add_observation(weight_candidate())


async def test_sink_rejects_workout_without_capability(hass, registry):
    provider = SyntheticProvider(
        capabilities=ProviderCapabilities(metrics=frozenset({MetricType.WEIGHT}))
    )
    registry.register(provider)
    with pytest.raises(ProviderCapabilityError):
        await registry.sink(provider.key).async_add_workout(
            CandidateWorkout(
                workout_type="run",
                started_at=OBSERVED_AT,
                ended_at=OBSERVED_AT,
                external_id="w-1",
            )
        )


async def test_sink_rejects_import_on_export_only_provider(hass, registry):
    provider = SyntheticProvider(
        capabilities=ProviderCapabilities(
            metrics=frozenset({MetricType.WEIGHT}), can_import=False, can_export=True
        )
    )
    registry.register(provider)
    with pytest.raises(ProviderCapabilityError):
        await registry.sink(provider.key).async_add_observation(weight_candidate())


async def test_export_rejected_before_reaching_import_only_provider(hass, registry):
    provider = SyntheticProvider()
    registry.register(provider)
    with pytest.raises(ProviderCapabilityError):
        await registry.async_export(provider.key, [object()])
    assert provider.export_calls == []


async def test_export_reaches_declared_provider(hass, registry):
    provider = SyntheticProvider(
        capabilities=ProviderCapabilities(
            metrics=frozenset({MetricType.WEIGHT}), can_export=True
        )
    )
    registry.register(provider)
    records = [object(), object()]
    await registry.async_export(provider.key, records)
    assert provider.export_calls == [records]


async def test_sink_propagates_unit_and_validation_errors(hass, registry):
    provider = SyntheticProvider()
    registry.register(provider)
    sink = registry.sink(provider.key)
    with pytest.raises(UnitConversionError):
        await sink.async_add_observation(weight_candidate(unit="furlongs"))
    with pytest.raises(StoreValidationError):
        await sink.async_add_observation(weight_candidate(value=float("nan")))


async def test_sink_upsert_is_idempotent_on_external_id(hass, registry, repository):
    provider = SyntheticProvider()
    registry.register(provider)
    sink = registry.sink(provider.key)
    await sink.async_add_observation(weight_candidate(value=80.0))
    await sink.async_add_observation(weight_candidate(value=81.0))
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert len(rows) == 1
    assert rows[0].value == pytest.approx(81.0)
