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


async def get_metric_rows(hass, entry, metric):
    return await hass.async_add_executor_job(
        entry.runtime_data.repository.get_observations, "primary", metric
    )


async def test_one_state_ingests_every_mapped_metric_and_survives_reload(hass):
    entry = await setup_entry(
        hass,
        make_entry(
            {
                CONF_MAPPINGS: {
                    "weight": ["sensor.shared_mass"],
                    "lean_mass": ["sensor.shared_mass"],
                }
            }
        ),
    )
    hass.states.async_set("sensor.shared_mass", "120", {"unit_of_measurement": "lb"})
    await hass.async_block_till_done()
    observed_at = hass.states.get("sensor.shared_mass").last_updated

    for metric in (MetricType.WEIGHT, MetricType.LEAN_MASS):
        rows = await get_metric_rows(hass, entry, metric)
        assert len(rows) == 1
        row = rows[0]
        assert row.metric == metric
        assert row.value == pytest.approx(120 * LB_TO_KG)
        assert row.unit == "kg"
        assert row.observed_at == observed_at
        assert row.provider == PROVIDER_HA_ENTITY
        assert row.external_id == "sensor.shared_mass"
        assert row.provenance == {
            "entity_id": "sensor.shared_mass",
            "source_unit": "lb",
            "raw_value": "120",
        }

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    for metric in (MetricType.WEIGHT, MetricType.LEAN_MASS):
        assert len(await get_metric_rows(hass, entry, metric)) == 1


@pytest.mark.parametrize("metrics", [("distance", "weight"), ("weight", "distance")])
async def test_invalid_unit_for_one_metric_does_not_block_another(hass, metrics):
    entry = await setup_entry(
        hass,
        make_entry(
            {CONF_MAPPINGS: {metric: ["sensor.shared_reading"] for metric in metrics}}
        ),
    )
    hass.states.async_set("sensor.shared_reading", "80", {"unit_of_measurement": "kg"})
    await hass.async_block_till_done()
    assert await get_metric_rows(hass, entry, MetricType.DISTANCE) == []
    rows = await get_weight_rows(hass, entry)
    assert len(rows) == 1
    assert rows[0].value == 80
    assert rows[0].unit == "kg"


async def test_missing_unit_uses_each_mapped_metrics_default(hass):
    hass.config.units = US_CUSTOMARY_SYSTEM
    hass.states.async_set("sensor.shared_reading", "80")
    entry = await setup_entry(
        hass,
        make_entry(
            {
                CONF_MAPPINGS: {
                    "weight": ["sensor.shared_reading"],
                    "body_fat_percentage": ["sensor.shared_reading"],
                }
            }
        ),
    )
    weight = await get_weight_rows(hass, entry)
    fat = await get_metric_rows(hass, entry, MetricType.BODY_FAT_PERCENTAGE)
    assert len(weight) == len(fat) == 1
    assert weight[0].value == pytest.approx(80 * LB_TO_KG)
    assert weight[0].unit == "kg"
    assert weight[0].provenance["source_unit"] == "lb"
    assert fat[0].value == 80
    assert fat[0].unit == "%"
    assert fat[0].provenance["source_unit"] == "%"


async def test_options_flow_keeps_multiple_metrics_for_one_entity(hass):
    entry = await setup_entry(
        hass, make_entry({CONF_MAPPINGS: {"weight": ["sensor.shared_mass"]}})
    )
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["data_schema"]({})["weight"] == ["sensor.shared_mass"]
    mappings = {
        "weight": ["sensor.shared_mass"],
        "lean_mass": ["sensor.shared_mass"],
    }
    await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=mappings
    )
    await hass.async_block_till_done()
    assert entry.options == {CONF_MAPPINGS: mappings}
    hass.states.async_set("sensor.shared_mass", "80", {"unit_of_measurement": "kg"})
    await hass.async_block_till_done()
    for metric in (MetricType.WEIGHT, MetricType.LEAN_MASS):
        rows = await get_metric_rows(hass, entry, metric)
        assert len(rows) == 1
        assert rows[0].value == 80
