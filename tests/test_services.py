from datetime import UTC, datetime

import pytest
import voluptuous as vol
from homeassistant.exceptions import ServiceValidationError

from custom_components.health_assistant.const import DOMAIN, PROVIDER_MANUAL
from custom_components.health_assistant.store import MetricType

LB_TO_KG = 0.45359237
OBSERVED = datetime(2026, 8, 20, 7, 30, tzinfo=UTC)


async def setup_integration(hass, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


async def get_rows(hass, entry, metric):
    repository = entry.runtime_data.repository
    return await hass.async_add_executor_job(
        repository.get_observations, "primary", metric
    )


async def test_add_observation_backfills_with_idempotency(hass, config_entry):
    entry = await setup_integration(hass, config_entry)
    payload = {
        "metric": "weight",
        "value": 180.0,
        "unit": "lb",
        "observed_at": "2026-08-20T07:30:00+00:00",
        "external_id": "backfill-1",
        "source": "old spreadsheet",
    }
    await hass.services.async_call(DOMAIN, "add_observation", payload, blocking=True)
    await hass.services.async_call(DOMAIN, "add_observation", payload, blocking=True)

    rows = await get_rows(hass, entry, MetricType.WEIGHT)
    assert len(rows) == 1
    assert rows[0].value == pytest.approx(180.0 * LB_TO_KG)
    assert rows[0].observed_at == OBSERVED
    assert rows[0].provider == PROVIDER_MANUAL
    assert rows[0].external_id == "backfill-1"
    assert rows[0].provenance == {"source": "old spreadsheet"}


async def test_add_observation_defaults_now_and_generated_id(hass, config_entry):
    entry = await setup_integration(hass, config_entry)
    await hass.services.async_call(
        DOMAIN, "add_observation", {"metric": "steps", "value": 9000}, blocking=True
    )
    rows = await get_rows(hass, entry, MetricType.STEPS)
    assert len(rows) == 1
    assert rows[0].external_id


async def test_add_observation_rejects_unknown_metric(hass, config_entry):
    await setup_integration(hass, config_entry)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "add_observation",
            {"metric": "blood_type", "value": 1.0},
            blocking=True,
        )


async def test_add_observation_rejects_unknown_unit(hass, config_entry):
    entry = await setup_integration(hass, config_entry)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "add_observation",
            {"metric": "weight", "value": 1.0, "unit": "furlong"},
            blocking=True,
        )
    assert await get_rows(hass, entry, MetricType.WEIGHT) == []


async def test_add_body_measurement_shares_timestamp(hass, config_entry):
    entry = await setup_integration(hass, config_entry)
    await hass.services.async_call(
        DOMAIN,
        "add_body_measurement",
        {
            "weight": 180.0,
            "weight_unit": "lb",
            "body_fat_percentage": 21.0,
            "observed_at": "2026-08-20T07:30:00+00:00",
            "external_id": "scale-1",
        },
        blocking=True,
    )
    weight = await get_rows(hass, entry, MetricType.WEIGHT)
    fat = await get_rows(hass, entry, MetricType.BODY_FAT_PERCENTAGE)
    assert weight[0].value == pytest.approx(180.0 * LB_TO_KG)
    assert fat[0].value == 21.0
    assert weight[0].observed_at == fat[0].observed_at == OBSERVED
    assert weight[0].external_id == "scale-1-weight"
    assert fat[0].external_id == "scale-1-body_fat_percentage"

    repository = entry.runtime_data.repository
    measurements = await hass.async_add_executor_job(
        repository.body_measurements, "primary"
    )
    assert len(measurements) == 1


async def test_add_body_measurement_requires_a_value(hass, config_entry):
    await setup_integration(hass, config_entry)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, "add_body_measurement", {"observed_at": "2026-08-20"}, blocking=True
        )


async def test_add_workout(hass, config_entry):
    entry = await setup_integration(hass, config_entry)
    await hass.services.async_call(
        DOMAIN,
        "add_workout",
        {
            "workout_type": "running",
            "title": "Morning run",
            "start": "2026-08-20T07:00:00+00:00",
            "end": "2026-08-20T07:45:00+00:00",
            "energy_kcal": 400.0,
            "distance": 5.0,
            "distance_unit": "km",
            "external_id": "run-1",
        },
        blocking=True,
    )
    repository = entry.runtime_data.repository
    workouts = await hass.async_add_executor_job(repository.get_workouts, "primary")
    assert len(workouts) == 1
    assert workouts[0].distance_m == 5000.0
    assert workouts[0].provider == PROVIDER_MANUAL


async def test_add_workout_rejects_end_before_start(hass, config_entry):
    entry = await setup_integration(hass, config_entry)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "add_workout",
            {
                "workout_type": "running",
                "start": "2026-08-20T07:45:00+00:00",
                "end": "2026-08-20T07:00:00+00:00",
            },
            blocking=True,
        )
    repository = entry.runtime_data.repository
    assert await hass.async_add_executor_job(repository.get_workouts, "primary") == []


async def test_services_lifecycle(hass, config_entry):
    entry = await setup_integration(hass, config_entry)
    assert hass.services.has_service(DOMAIN, "add_observation")
    assert hass.services.has_service(DOMAIN, "add_body_measurement")
    assert hass.services.has_service(DOMAIN, "add_workout")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.services.has_service(DOMAIN, "add_observation")
    assert not hass.services.has_service(DOMAIN, "add_workout")
