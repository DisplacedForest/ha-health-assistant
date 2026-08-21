import pytest
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.health_assistant.const import (
    CONF_MAPPINGS,
    DOMAIN,
    NAME,
    PROVIDER_HA_ENTITY,
)
from custom_components.health_assistant.store import MetricType

LB_TO_KG = 0.45359237


def make_entry(options=None):
    return MockConfigEntry(
        domain=DOMAIN, title=NAME, data={}, unique_id=DOMAIN, options=options or {}
    )


async def setup_entry(hass, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def get_weight_rows(hass, entry):
    repository = entry.runtime_data.repository
    return await hass.async_add_executor_job(
        repository.get_observations, "primary", MetricType.WEIGHT
    )


async def test_state_change_ingested_with_provenance(hass):
    entry = await setup_entry(
        hass, make_entry({CONF_MAPPINGS: {"weight": ["sensor.scale_weight"]}})
    )
    hass.states.async_set("sensor.scale_weight", "180.0", {"unit_of_measurement": "lb"})
    await hass.async_block_till_done()

    rows = await get_weight_rows(hass, entry)
    assert len(rows) == 1
    assert rows[0].value == pytest.approx(180.0 * LB_TO_KG)
    assert rows[0].unit == "kg"
    assert rows[0].provider == PROVIDER_HA_ENTITY
    assert rows[0].external_id == "sensor.scale_weight"
    assert rows[0].provenance["source_unit"] == "lb"
    assert rows[0].provenance["raw_value"] == "180.0"


async def test_existing_state_ingested_at_setup(hass):
    hass.states.async_set("sensor.scale_weight", "82.5", {"unit_of_measurement": "kg"})
    entry = await setup_entry(
        hass, make_entry({CONF_MAPPINGS: {"weight": ["sensor.scale_weight"]}})
    )
    rows = await get_weight_rows(hass, entry)
    assert len(rows) == 1
    assert rows[0].value == 82.5


@pytest.mark.parametrize(
    ("state", "attributes"),
    [
        ("unknown", {}),
        ("unavailable", {}),
        ("not-a-number", {"unit_of_measurement": "kg"}),
        ("82.5", {"unit_of_measurement": "furlong"}),
    ],
)
async def test_bad_states_never_stored(hass, state, attributes):
    entry = await setup_entry(
        hass, make_entry({CONF_MAPPINGS: {"weight": ["sensor.scale_weight"]}})
    )
    hass.states.async_set("sensor.scale_weight", state, attributes)
    await hass.async_block_till_done()
    assert await get_weight_rows(hass, entry) == []


async def test_missing_unit_falls_back_to_unit_system(hass):
    entry = await setup_entry(
        hass, make_entry({CONF_MAPPINGS: {"weight": ["sensor.scale_weight"]}})
    )
    hass.states.async_set("sensor.scale_weight", "82.5")
    await hass.async_block_till_done()
    rows = await get_weight_rows(hass, entry)
    assert rows[0].value == 82.5

    hass.config.units = US_CUSTOMARY_SYSTEM
    hass.states.async_set("sensor.scale_weight", "180.0")
    await hass.async_block_till_done()
    rows = await get_weight_rows(hass, entry)
    assert len(rows) == 2
    assert rows[-1].value == pytest.approx(180.0 * LB_TO_KG)


async def test_reload_does_not_duplicate_unchanged_state(hass):
    entry = await setup_entry(
        hass, make_entry({CONF_MAPPINGS: {"weight": ["sensor.scale_weight"]}})
    )
    hass.states.async_set("sensor.scale_weight", "82.5", {"unit_of_measurement": "kg"})
    await hass.async_block_till_done()
    assert len(await get_weight_rows(hass, entry)) == 1

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert len(await get_weight_rows(hass, entry)) == 1


async def test_unmapped_entity_ignored(hass):
    entry = await setup_entry(
        hass, make_entry({CONF_MAPPINGS: {"weight": ["sensor.scale_weight"]}})
    )
    hass.states.async_set("sensor.other", "82.5", {"unit_of_measurement": "kg"})
    await hass.async_block_till_done()
    assert await get_weight_rows(hass, entry) == []


async def test_options_change_takes_effect_without_restart(hass):
    entry = await setup_entry(hass, make_entry())

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"weight": ["sensor.new_scale"]}
    )
    await hass.async_block_till_done()
    assert entry.options == {CONF_MAPPINGS: {"weight": ["sensor.new_scale"]}}

    hass.states.async_set("sensor.new_scale", "82.5", {"unit_of_measurement": "kg"})
    await hass.async_block_till_done()
    rows = await get_weight_rows(hass, entry)
    assert len(rows) == 1
    assert rows[0].external_id == "sensor.new_scale"
