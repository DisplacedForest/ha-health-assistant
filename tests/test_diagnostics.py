import json
from datetime import UTC, datetime

from custom_components.health_assistant.const import DOMAIN
from custom_components.health_assistant.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.health_assistant.store import (
    DEFAULT_PERSON_ID,
    HealthObservation,
    MetricType,
    Workout,
)
from custom_components.health_assistant.store.schema import SCHEMA_VERSION

OBSERVED = datetime(2026, 8, 20, 7, 30, tzinfo=UTC)


async def _seed(hass, config_entry):
    repository = config_entry.runtime_data.repository
    await hass.async_add_executor_job(
        repository.upsert_observation,
        HealthObservation(
            person_id="primary",
            metric=MetricType.WEIGHT,
            value=82.5,
            unit="kg",
            observed_at=OBSERVED,
            provider="test_scale",
            external_id="reading-1",
            ingested_at=OBSERVED,
            provenance={"source": "bathroom scale"},
        ),
    )
    await hass.async_add_executor_job(
        repository.upsert_workout,
        Workout(
            person_id="primary",
            provider="manual",
            external_id="workout-1",
            workout_type="running",
            title="Sunrise Intervals",
            started_at=OBSERVED,
            ended_at=datetime(2026, 8, 20, 8, 15, tzinfo=UTC),
            energy_kcal=512.5,
            distance_m=8046.7,
            ingested_at=OBSERVED,
        ),
    )


async def test_diagnostics_allowlist_shape(hass, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await _seed(hass, config_entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)

    assert set(diagnostics) == {
        "domain",
        "version",
        "entry_state",
        "mapped_entity_counts",
        "database",
    }
    assert diagnostics["domain"] == DOMAIN
    assert diagnostics["version"] == "0.1.0"
    assert diagnostics["database"]["schema_version"] == SCHEMA_VERSION
    assert diagnostics["database"]["supported_schema_version"] == SCHEMA_VERSION
    assert diagnostics["database"]["file_exists"] is True
    assert diagnostics["database"]["observation_counts"] == {"weight": 1}
    assert diagnostics["database"]["claim_counts"] == {"weight": 1}
    assert diagnostics["database"]["workout_count"] == 1
    assert diagnostics["database"]["observation_providers"] == {"test_scale": 1}
    assert diagnostics["database"]["workout_providers"] == {"manual": 1}
    assert diagnostics["mapped_entity_counts"]["weight"] == 0


async def test_diagnostics_provider_counts_survive_merging(hass, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    repository = config_entry.runtime_data.repository
    for provider, external_id in (("test_scale", "s-1"), ("test_bridge", "b-1")):
        await hass.async_add_executor_job(
            repository.upsert_observation,
            HealthObservation(
                person_id=DEFAULT_PERSON_ID,
                metric=MetricType.WEIGHT,
                value=82.5,
                unit="kg",
                observed_at=OBSERVED,
                provider=provider,
                external_id=external_id,
                ingested_at=OBSERVED,
            ),
        )

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)

    assert diagnostics["database"]["observation_counts"] == {"weight": 1}
    assert diagnostics["database"]["claim_counts"] == {"weight": 2}
    assert diagnostics["database"]["observation_providers"] == {
        "test_bridge": 1,
        "test_scale": 1,
    }


async def test_diagnostics_never_contain_health_values(hass, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await _seed(hass, config_entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    payload = json.dumps(diagnostics, default=str)

    assert "82.5" not in payload
    assert "512.5" not in payload
    assert "8046.7" not in payload
    assert "Sunrise Intervals" not in payload
    assert "bathroom scale" not in payload
    assert "reading-1" not in payload
    assert "workout-1" not in payload
