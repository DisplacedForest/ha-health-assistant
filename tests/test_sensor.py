from datetime import timedelta

import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.health_assistant.const import CONF_MAPPINGS, DOMAIN, NAME

KG_TO_LB = 2.204622621848776

ENTITY_IDS = (
    "sensor.health_assistant_current_weight",
    "sensor.health_assistant_current_body_fat",
    "sensor.health_assistant_steps_today",
    "sensor.health_assistant_active_energy_today",
    "sensor.health_assistant_latest_workout",
    "sensor.health_assistant_workouts_last_7_days",
)


async def setup_integration(hass, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


async def add_observation(hass, **kwargs):
    data = {"metric": "weight", "value": 82.5}
    data.update(kwargs)
    await hass.services.async_call(DOMAIN, "add_observation", data, blocking=True)
    await hass.async_block_till_done()


async def add_workout(hass, **kwargs):
    now = dt_util.utcnow()
    data = {
        "workout_type": "strength",
        "title": "Push day",
        "start": (now - timedelta(hours=2)).isoformat(),
        "end": (now - timedelta(hours=1)).isoformat(),
    }
    data.update(kwargs)
    await hass.services.async_call(DOMAIN, "add_workout", data, blocking=True)
    await hass.async_block_till_done()


async def test_empty_store_shows_unknown_everywhere(hass, config_entry):
    await setup_integration(hass, config_entry)
    for entity_id in ENTITY_IDS:
        state = hass.states.get(entity_id)
        assert state is not None, entity_id
        assert state.state == "unknown", entity_id


async def test_entities_update_immediately_after_service_write(hass, config_entry):
    await setup_integration(hass, config_entry)
    await add_observation(hass, value=82.5)
    state = hass.states.get("sensor.health_assistant_current_weight")
    assert float(state.state) == 82.5
    assert state.attributes["provider"] == "manual"

    await add_observation(hass, metric="body_fat_percentage", value=21.0)
    assert (
        float(hass.states.get("sensor.health_assistant_current_body_fat").state) == 21.0
    )


async def test_steps_today_uses_max_and_ignores_other_days(hass, config_entry):
    await setup_integration(hass, config_entry)
    yesterday = dt_util.utcnow() - timedelta(days=1)
    await add_observation(
        hass,
        metric="steps",
        value=9000,
        observed_at=yesterday.isoformat(),
        external_id="y",
    )
    assert hass.states.get("sensor.health_assistant_steps_today").state == "unknown"

    await add_observation(hass, metric="steps", value=500, external_id="a")
    await add_observation(hass, metric="steps", value=300, external_id="b")
    assert float(hass.states.get("sensor.health_assistant_steps_today").state) == 500.0


async def test_workout_sensors(hass, config_entry):
    await setup_integration(hass, config_entry)
    assert (
        hass.states.get("sensor.health_assistant_workouts_last_7_days").state
        == "unknown"
    )

    old_start = dt_util.utcnow() - timedelta(days=8)
    await add_workout(
        hass,
        title="Old run",
        workout_type="running",
        start=old_start.isoformat(),
        end=(old_start + timedelta(hours=1)).isoformat(),
        external_id="old",
    )
    assert hass.states.get("sensor.health_assistant_latest_workout").state == "Old run"
    assert (
        float(hass.states.get("sensor.health_assistant_workouts_last_7_days").state)
        == 0.0
    )

    await add_workout(hass, title="Push day", external_id="new")
    latest = hass.states.get("sensor.health_assistant_latest_workout")
    assert latest.state == "Push day"
    assert latest.attributes["workout_type"] == "strength"
    assert latest.attributes["duration_seconds"] == 3600.0
    assert (
        float(hass.states.get("sensor.health_assistant_workouts_last_7_days").state)
        == 1.0
    )


async def test_restart_reconstructs_from_store(hass, config_entry):
    await setup_integration(hass, config_entry)
    await add_observation(hass, value=82.5, external_id="w1")
    await add_workout(hass, external_id="wo1")

    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        float(hass.states.get("sensor.health_assistant_current_weight").state) == 82.5
    )
    assert hass.states.get("sensor.health_assistant_latest_workout").state == "Push day"


async def test_weight_displays_in_us_units(hass, config_entry):
    hass.config.units = US_CUSTOMARY_SYSTEM
    await setup_integration(hass, config_entry)
    await add_observation(hass, value=80.0)
    state = hass.states.get("sensor.health_assistant_current_weight")
    assert state.attributes["unit_of_measurement"] == "lb"
    assert float(state.state) == pytest.approx(80.0 * KG_TO_LB, rel=1e-3)


async def test_entity_ingestion_updates_sensors(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        data={},
        unique_id=DOMAIN,
        options={CONF_MAPPINGS: {"weight": ["sensor.scale"]}},
    )
    await setup_integration(hass, entry)
    hass.states.async_set("sensor.scale", "81.2", {"unit_of_measurement": "kg"})
    await hass.async_block_till_done()
    state = hass.states.get("sensor.health_assistant_current_weight")
    assert float(state.state) == 81.2
    assert state.attributes["source"] == "sensor.scale"


async def test_single_device_owns_all_entities(hass, config_entry):
    await setup_integration(hass, config_entry)
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, config_entry.entry_id)})
    assert device is not None
    assert device.name == NAME
    entries = er.async_entries_for_device(entity_registry, device.id)
    assert len(entries) == len(ENTITY_IDS)


async def test_attributes_stay_bounded_with_large_history(hass, config_entry):
    await setup_integration(hass, config_entry)
    base = dt_util.utcnow() - timedelta(days=2)
    for index in range(60):
        await add_observation(
            hass,
            value=80.0 + index * 0.01,
            observed_at=(base + timedelta(minutes=index)).isoformat(),
            external_id=f"r{index}",
        )
    state = hass.states.get("sensor.health_assistant_current_weight")
    assert set(state.attributes) <= {
        "observed_at",
        "provider",
        "source",
        "unit_of_measurement",
        "device_class",
        "state_class",
        "friendly_name",
    }
    assert not any(isinstance(v, (list, tuple)) for v in state.attributes.values())
