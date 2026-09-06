from datetime import timedelta
from unittest.mock import patch

from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.health_assistant.environment import CONF_ENVIRONMENT
from custom_components.health_assistant.store.environment import EnvironmentRepository


async def setup_capture(hass, config_entry, freezer):
    freezer.move_to("2026-09-06T12:00:00Z")
    area = ar.async_get(hass).async_create("Bedroom")
    entity = er.async_get(hass).async_get_or_create(
        "sensor", "test", "room", suggested_object_id="bedroom"
    )
    er.async_get(hass).async_update_entity(entity.entity_id, area_id=area.id)
    hass.states.async_set(entity.entity_id, "20", {"unit_of_measurement": "°C"})
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_ENVIRONMENT: [
                {
                    "mapping_id": "room",
                    "entity_id": entity.entity_id,
                    "entity_registry_id": entity.id,
                    "metric": "temperature",
                    "area_id": area.id,
                    "area_override": False,
                }
            ]
        },
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return entity.entity_id


async def advance(hass, freezer, seconds):
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()


async def test_live_reports_startup_gap_identical_and_expiry(
    hass, config_entry, freezer
):
    entity_id = await setup_capture(hass, config_entry, freezer)
    capture = config_entry.runtime_data.environment
    r = capture.repository
    await advance(hass, freezer, 300)
    assert await hass.async_add_executor_job(r.export_buckets) == []
    hass.states.async_set(entity_id, "20", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()
    await advance(hass, freezer, 300)
    rows = await hass.async_add_executor_job(r.export_buckets)
    assert sum(r["covered_ms"] for r in rows) == 300_000
    assert sum(r["sample_count"] for r in rows) == 1
    await advance(hass, freezer, 600)
    hass.states.async_set(entity_id, "20", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()
    await advance(hass, freezer, 1200)
    rows = await hass.async_add_executor_job(r.export_buckets)
    assert sum(r["covered_ms"] for r in rows) == 1_800_000
    assert sum(r["sample_count"] for r in rows) == 2


async def test_unavailable_and_reload_keep_exact_partial_history(
    hass, config_entry, freezer
):
    entity_id = await setup_capture(hass, config_entry, freezer)
    hass.states.async_set(entity_id, "10", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=60))
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    await advance(hass, freezer, 60)
    hass.states.async_set(entity_id, "30", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=60))
    hass.states.async_set(entity_id, "unavailable")
    await hass.async_block_till_done()
    await advance(hass, freezer, 120)
    rows = await hass.async_add_executor_job(
        config_entry.runtime_data.environment.repository.export_buckets
    )
    assert len(rows) == 1
    assert rows[0]["covered_ms"] == 120_000
    assert rows[0]["weighted_sum"] / rows[0]["covered_ms"] == 20
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        await hass.async_add_executor_job(
            config_entry.runtime_data.environment.repository.export_buckets
        )
        == rows
    )
    capture = config_entry.runtime_data.environment
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert capture.unsubscribers == []
    hass.states.async_set(entity_id, "500", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()
    assert not capture.pending


async def test_old_home_assistant_rejected_before_database(hass, config_entry):
    from custom_components.health_assistant.paths import database_path

    config_entry.add_to_hass(hass)
    with patch("custom_components.health_assistant.HA_VERSION", "2026.7.4"):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert not database_path(hass).exists()


async def test_capture_options_preserve_health_and_unrelated_state(hass, config_entry):
    area = ar.async_get(hass).async_create("Office")
    entity = er.async_get(hass).async_get_or_create(
        "sensor", "test", "office", suggested_object_id="office"
    )
    er.async_get(hass).async_update_entity(entity.entity_id, area_id=area.id)
    hass.states.async_set(entity.entity_id, "450", {"unit_of_measurement": "ppm"})
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"environmental_capture": True}
    )
    assert result["step_id"] == "environment"
    hass.config_entries.async_update_entry(
        config_entry, options={"unrelated": "preserved"}
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"action": "add", "entity_id": entity.entity_id, "metric": "co2"},
    )
    assert result["type"] == "create_entry"
    assert result["data"]["unrelated"] == "preserved"
    assert result["data"][CONF_ENVIRONMENT][0]["area_id"] == area.id
    assert "environmental_capture" not in result["data"].get("entity_mappings", {})
    await hass.async_block_till_done()


async def test_area_change_starts_new_revision(hass, config_entry, freezer):
    entity_id = await setup_capture(hass, config_entry, freezer)
    hass.states.async_set(entity_id, "21", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()
    await advance(hass, freezer, 60)
    second = ar.async_get(hass).async_create("Office")
    er.async_get(hass).async_update_entity(entity_id, area_id=second.id)
    await hass.async_block_till_done()
    capture = config_entry.runtime_data.environment
    streams = await hass.async_add_executor_job(capture.repository.export_streams)
    assert len(streams) == 2
    assert streams[0]["area_name"] == "Bedroom"
    assert streams[1]["area_name"] == "Office"
    assert len(capture.accumulators) == 1


async def test_writer_failure_is_bounded_and_recovers_without_gap_fill(
    hass, config_entry, freezer
):
    import sqlite3

    entity_id = await setup_capture(hass, config_entry, freezer)
    capture = config_entry.runtime_data.environment
    hass.states.async_set(entity_id, "20", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()
    with patch.object(
        EnvironmentRepository,
        "save",
        side_effect=sqlite3.OperationalError("private temperature 99"),
    ):
        await advance(hass, freezer, 300)
        assert capture.capture_failed
        await advance(hass, freezer, 300)
        assert len(capture.pending) <= 96
    await advance(hass, freezer, 300)
    assert not capture.capture_failed
    rows = await hass.async_add_executor_job(capture.repository.export_buckets)
    assert sum(r["covered_ms"] for r in rows) == 300_000


async def test_environment_diagnostics_hide_places_and_sensor_ids(
    hass, config_entry, freezer
):
    import json

    from custom_components.health_assistant.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    entity_id = await setup_capture(hass, config_entry, freezer)
    hass.states.async_set(entity_id, "23.456789", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()
    await advance(hass, freezer, 300)
    result = await async_get_config_entry_diagnostics(hass, config_entry)
    payload = json.dumps(result)
    assert "23.456789" not in payload
    assert "Bedroom" not in payload
    assert entity_id not in payload
    assert result["database"]["environment"]["bucket_count"] == 1
    assert result["database"]["environment"]["maintenance"]["failed"] == 0


async def test_bad_mappings_do_not_prevent_health_setup(hass, config_entry):
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_ENVIRONMENT: [{"entity_id": "sensor.gone"}]}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.runtime_data.environment.mapping_failed
    assert config_entry.runtime_data.environment.accumulators == {}
