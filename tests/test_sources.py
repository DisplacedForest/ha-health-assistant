from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.health_assistant.const import (
    CONF_MAPPINGS,
    CONF_SOURCE_MAPPINGS,
    DOMAIN,
)
from custom_components.health_assistant.paths import database_path
from custom_components.health_assistant.providers.contract import (
    HealthProvider,
    ProviderCapabilities,
)
from custom_components.health_assistant.sources import discover_sources
from custom_components.health_assistant.store import (
    HealthDatabase,
    HealthRepository,
    MetricType,
)

SOURCE_IDENTITIES = {
    "withings": {
        MetricType.WEIGHT: "withings_{profile}_weight_kg",
        MetricType.BODY_FAT_PERCENTAGE: "withings_{profile}_fat_ratio_pct",
        MetricType.LEAN_MASS: "withings_{profile}_fat_free_mass_kg",
        MetricType.STEPS: "withings_{profile}_activity_steps_today",
        MetricType.DISTANCE: "withings_{profile}_activity_distance_today",
    },
    "fitbit": {
        MetricType.WEIGHT: "{profile}_body/weight",
        MetricType.BODY_FAT_PERCENTAGE: "{profile}_body/fat",
        MetricType.STEPS: "{profile}_activities/steps",
        MetricType.DISTANCE: "{profile}_activities/distance",
    },
}


def source_entry(hass, domain="withings", profile="alice", title="Alice"):
    entry = MockConfigEntry(domain=domain, unique_id=profile, title=title, data={})
    entry.add_to_hass(hass)
    return entry


def source_sensor(
    hass, entry, metric=MetricType.WEIGHT, value="80", unit="kg", disabled_by=None
):
    entity = er.async_get(hass).async_get_or_create(
        "sensor",
        entry.domain,
        SOURCE_IDENTITIES[entry.domain][metric].format(profile=entry.unique_id),
        config_entry=entry,
        suggested_object_id=f"renamed_{entry.unique_id}_{metric.value}",
        disabled_by=disabled_by,
    )
    hass.states.async_set(entity.entity_id, value, {"unit_of_measurement": unit})
    return entity


async def setup_health(hass, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def choose_source(hass, config_entry, source, **extra):
    flow = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert flow["step_id"] == "sources"
    return await hass.config_entries.options.async_configure(
        flow["flow_id"],
        user_input={
            "weight": f"{source.domain}:{source.entry_id}",
            "confirm_person": True,
            **extra,
        },
    )


@pytest.mark.parametrize("domain", ["withings", "fitbit"])
async def test_discovery_uses_registry_identity_after_rename(hass, domain):
    entry = source_entry(hass, domain)
    entity = source_sensor(hass, entry)
    offers = discover_sources(hass)
    assert len(offers) == 1
    assert offers[0].entities == {MetricType.WEIGHT: entity.id}
    assert "Alice" in offers[0].label
    assert any("missing" in warning for warning in offers[0].warnings)


@pytest.mark.parametrize(
    ("value", "unit", "disabled", "warning"),
    [
        ("unavailable", "kg", None, "unavailable"),
        ("unknown", "kg", None, "unavailable"),
        ("80", "m", None, "incompatible units"),
        ("80", None, None, "missing or incompatible units"),
        ("80", "kg", er.RegistryEntryDisabler.USER, "disabled"),
    ],
)
async def test_unusable_entities_are_visible_and_not_offered(
    hass, value, unit, disabled, warning
):
    entry = source_entry(hass)
    source_sensor(hass, entry, value=value, unit=unit, disabled_by=disabled)
    offer = discover_sources(hass)[0]
    assert MetricType.WEIGHT not in offer.metrics
    assert any(warning in item for item in offer.warnings)


async def test_unverified_bridges_are_detection_only(hass):
    source_entry(hass, "health_connect")
    offer = discover_sources(hass)[0]
    assert not offer.metrics
    assert "manual entity mapping" in offer.warnings[0]


async def test_source_selection_preserves_options_and_ingests_vendor_provenance(
    hass, hass_ws_client, config_entry
):
    source = source_entry(hass)
    entity = source_sensor(hass, source)
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={},
        options={
            CONF_MAPPINGS: {"steps": ["sensor.manual_steps"]},
            "future_option": {"enabled": True},
        },
    )
    await setup_health(hass, config_entry)
    result = await choose_source(hass, config_entry, source)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert config_entry.options[CONF_MAPPINGS] == {"steps": ["sensor.manual_steps"]}
    assert config_entry.options["future_option"] == {"enabled": True}
    assert config_entry.options[CONF_SOURCE_MAPPINGS]["withings"]["entities"] == {
        "weight": entity.id
    }
    repository = config_entry.runtime_data.repository
    priority = await hass.async_add_executor_job(
        repository.get_priority, MetricType.WEIGHT
    )
    assert priority[0] == "withings"
    hass.states.async_set(entity.entity_id, "180", {"unit_of_measurement": "lb"})
    await hass.async_block_till_done()
    rows = await hass.async_add_executor_job(
        repository.get_observations, "primary", MetricType.WEIGHT
    )
    assert len(rows) == 2
    assert rows[-1].provider == "withings"
    assert rows[-1].external_id == entity.id
    assert rows[-1].value == pytest.approx(180 * 0.45359237)
    assert rows[-1].provenance["integration"] == "withings"
    assert rows[-1].provenance["entity_id"] == entity.entity_id
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/summary"})
    summary = await client.receive_json()
    assert summary["success"]
    assert summary["result"]["current_weight"]["provider"] == "withings"
    assert (
        hass.states.get("sensor.health_assistant_current_weight").attributes["provider"]
        == "withings"
    )
    flow = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert flow["data_schema"]({})["weight"] == f"withings:{source.entry_id}"
    await hass.async_add_executor_job(
        repository.set_priority, MetricType.WEIGHT, ["manual", "withings"]
    )
    flow = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert flow["data_schema"]({})["weight"] == "manual"


async def test_curated_mapping_follows_runtime_rename_and_rejects_new_bad_units(
    hass, config_entry
):
    source = source_entry(hass)
    entity = source_sensor(hass, source)
    await setup_health(hass, config_entry)
    await choose_source(hass, config_entry, source)
    await hass.async_block_till_done()
    er.async_get(hass).async_update_entity(
        entity.entity_id, new_entity_id="sensor.changed_name"
    )
    hass.states.async_set("sensor.changed_name", "81", {"unit_of_measurement": "kg"})
    await hass.async_block_till_done()
    hass.states.async_set("sensor.changed_name", "82", {"unit_of_measurement": "m"})
    await hass.async_block_till_done()
    rows = await hass.async_add_executor_job(
        config_entry.runtime_data.repository.get_observations,
        "primary",
        MetricType.WEIGHT,
    )
    assert [row.value for row in rows] == [80, 81]
    assert {row.external_id for row in rows} == {entity.id}
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    rows = await hass.async_add_executor_job(
        config_entry.runtime_data.repository.get_observations,
        "primary",
        MetricType.WEIGHT,
    )
    assert len(rows) == 2


async def test_new_account_requires_confirmation_and_accounts_cannot_mix(
    hass, config_entry
):
    first = source_entry(hass)
    second = source_entry(hass, profile="bob", title="Bob")
    source_sensor(hass, first)
    source_sensor(hass, second, MetricType.LEAN_MASS)
    await setup_health(hass, config_entry)
    flow = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert flow["data_schema"]({})["weight"] == "manual"
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={"weight": f"withings:{first.entry_id}"}
    )
    assert flow["errors"] == {"base": "confirm_person"}
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        user_input={
            "weight": f"withings:{first.entry_id}",
            "lean_mass": f"withings:{second.entry_id}",
            "confirm_person": True,
        },
    )
    assert flow["errors"] == {"base": "different_profiles"}
    assert CONF_SOURCE_MAPPINGS not in config_entry.options


async def test_source_becoming_unavailable_before_submit_is_rejected(
    hass, config_entry
):
    source = source_entry(hass)
    entity = source_sensor(hass, source)
    await setup_health(hass, config_entry)
    flow = await hass.config_entries.options.async_init(config_entry.entry_id)
    hass.states.async_set(entity.entity_id, "unavailable")
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        user_input={"weight": f"withings:{source.entry_id}", "confirm_person": True},
    )
    assert flow["errors"]["weight"] == "source_unavailable"
    assert CONF_SOURCE_MAPPINGS not in config_entry.options


async def test_source_flow_manual_escape_preserves_unrelated_options(
    hass, config_entry
):
    source = source_entry(hass)
    source_sensor(hass, source)
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN, data={}, options={"future_option": 42}
    )
    await setup_health(hass, config_entry)
    flow = await choose_source(hass, config_entry, source, manual_mapping=True)
    assert flow["step_id"] == "manual"
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={"steps": ["sensor.template_steps"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert config_entry.options["future_option"] == 42
    assert config_entry.options[CONF_MAPPINGS] == {"steps": ["sensor.template_steps"]}
    assert "withings" in config_entry.options[CONF_SOURCE_MAPPINGS]


async def test_initial_setup_offers_sources_and_writes_canonical_priority(hass):
    source = source_entry(hass)
    entity = source_sensor(hass, source)
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    flow = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={}
    )
    assert flow["step_id"] == "sources"
    flow = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        user_input={"weight": f"withings:{source.entry_id}", "confirm_person": True},
    )
    assert flow["type"] is FlowResultType.CREATE_ENTRY
    assert (
        flow["options"][CONF_SOURCE_MAPPINGS]["withings"]["entities"]["weight"]
        == entity.id
    )

    def read():
        database = HealthDatabase(database_path(hass))
        database.open()
        try:
            return HealthRepository(database).get_priority(MetricType.WEIGHT)
        finally:
            database.close()

    assert (await hass.async_add_executor_job(read))[0] == "withings"


class OtherProvider(HealthProvider):
    @property
    def key(self):
        return "other_source"

    @property
    def display_name(self):
        return "Other source"

    @property
    def capabilities(self):
        return ProviderCapabilities(metrics=frozenset({MetricType.WEIGHT}))


async def test_framework_provider_joins_source_chooser(hass, config_entry):
    await setup_health(hass, config_entry)
    config_entry.runtime_data.registry.register(OtherProvider())
    flow = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert flow["step_id"] == "sources"
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={"weight": "other_source"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    priority = await hass.async_add_executor_job(
        config_entry.runtime_data.repository.get_priority, MetricType.WEIGHT
    )
    assert priority[0] == "other_source"
    assert CONF_SOURCE_MAPPINGS not in config_entry.options


async def test_manual_step_rechecks_source_before_saving(hass, config_entry):
    source = source_entry(hass)
    entity = source_sensor(hass, source)
    await setup_health(hass, config_entry)
    flow = await choose_source(hass, config_entry, source, manual_mapping=True)
    hass.states.async_set(entity.entity_id, "unavailable")
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "source_changed"
    assert CONF_SOURCE_MAPPINGS not in config_entry.options
    priority = await hass.async_add_executor_job(
        config_entry.runtime_data.repository.get_priority, MetricType.WEIGHT
    )
    assert "withings" not in priority


async def test_generic_manual_mapping_preserves_future_options(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN, data={}, options={"future_option": 42}
    )
    await setup_health(hass, entry)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    assert flow["step_id"] == "init"
    await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={"weight": ["sensor.template"]}
    )
    await hass.async_block_till_done()
    assert entry.options["future_option"] == 42


async def test_ambiguous_registry_matches_are_not_selected(hass):
    source = source_entry(hass)
    entity = source_sensor(hass, source)
    er.async_get(hass).async_get_or_create(
        "sensor", "other_platform", entity.unique_id, config_entry=source
    )
    offer = discover_sources(hass)[0]
    assert MetricType.WEIGHT not in offer.metrics
    assert "weight: ambiguous entity." in offer.warnings


async def test_removed_source_is_visible_and_keeps_history(hass, config_entry):
    source = source_entry(hass)
    source_sensor(hass, source)
    await setup_health(hass, config_entry)
    await choose_source(hass, config_entry, source)
    await hass.async_block_till_done()
    with patch.object(type(source), "async_remove", new=AsyncMock()):
        await hass.config_entries.async_remove(source.entry_id)
    flow = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert (
        "Configured integration is missing"
        in flow["description_placeholders"]["source_details"]
    )
    rows = await hass.async_add_executor_job(
        config_entry.runtime_data.repository.get_observations,
        "primary",
        MetricType.WEIGHT,
    )
    assert len(rows) == 1


@pytest.mark.parametrize(("domain", "metrics"), list(SOURCE_IDENTITIES.items()))
async def test_every_curated_metric_matches_upstream_registry_identity(
    hass, domain, metrics
):
    source = source_entry(hass, domain)
    units = {
        MetricType.WEIGHT: "kg",
        MetricType.LEAN_MASS: "kg",
        MetricType.BODY_FAT_PERCENTAGE: "%",
        MetricType.STEPS: "steps",
        MetricType.DISTANCE: "km",
    }
    expected = {
        metric: source_sensor(hass, source, metric, unit=units[metric]).id
        for metric in metrics
    }
    offer = discover_sources(hass)[0]
    assert offer.entities == expected
    assert not offer.warnings


async def test_options_saved_during_flow_keep_new_unrelated_settings(
    hass, config_entry
):
    source = source_entry(hass)
    source_sensor(hass, source)
    await setup_health(hass, config_entry)
    flow = await choose_source(hass, config_entry, source, manual_mapping=True)
    hass.config_entries.async_update_entry(
        config_entry, options={"environment": {"area": "bedroom"}}
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert config_entry.options["environment"] == {"area": "bedroom"}
    assert "withings" in config_entry.options[CONF_SOURCE_MAPPINGS]


async def test_indistinguishable_account_names_require_renaming(hass):
    first = source_entry(hass, profile="first")
    second = source_entry(hass, profile="second")
    source_sensor(hass, first)
    source_sensor(hass, second)
    offers = discover_sources(hass)
    assert len(offers) == 2
    assert all(not offer.metrics for offer in offers)
    assert all("Rename the integrations" in offer.warnings[0] for offer in offers)


@pytest.mark.parametrize("change", ["disabled", "identity", "account"])
async def test_curated_provider_stops_when_registry_ownership_changes(
    hass, config_entry, change
):
    source = source_entry(hass)
    other = source_entry(hass, profile="bob", title="Bob")
    entity = source_sensor(hass, source)
    await setup_health(hass, config_entry)
    await choose_source(hass, config_entry, source)
    await hass.async_block_till_done()
    changes = {
        "disabled": {"disabled_by": er.RegistryEntryDisabler.USER},
        "identity": {"new_unique_id": "unrecognized_weight"},
        "account": {"config_entry_id": other.entry_id},
    }
    er.async_get(hass).async_update_entity(entity.entity_id, **changes[change])
    hass.states.async_set(entity.entity_id, "81", {"unit_of_measurement": "kg"})
    await hass.async_block_till_done()
    rows = await hass.async_add_executor_job(
        config_entry.runtime_data.repository.get_observations,
        "primary",
        MetricType.WEIGHT,
    )
    assert [row.value for row in rows] == [80]


@pytest.mark.parametrize("replacement", [False, True])
async def test_manual_step_validates_exact_binding_but_allows_entity_rename(
    hass, config_entry, replacement
):
    source = source_entry(hass)
    entity = source_sensor(hass, source)
    await setup_health(hass, config_entry)
    flow = await choose_source(hass, config_entry, source, manual_mapping=True)
    registry = er.async_get(hass)
    if replacement:
        registry.async_update_entity(entity.entity_id, new_unique_id="retired_weight")
        new_entity = source_sensor(hass, source, value="81")
        assert new_entity.id != entity.id
    else:
        registry.async_update_entity(entity.entity_id, new_entity_id="sensor.new_name")
        hass.states.async_set("sensor.new_name", "81", {"unit_of_measurement": "kg"})
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={}
    )
    await hass.async_block_till_done()
    repository = config_entry.runtime_data.repository
    priority = await hass.async_add_executor_job(
        repository.get_priority, MetricType.WEIGHT
    )
    rows = await hass.async_add_executor_job(
        repository.get_observations, "primary", MetricType.WEIGHT
    )
    if replacement:
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "source_changed"
        assert CONF_SOURCE_MAPPINGS not in config_entry.options
        assert "withings" not in priority
        assert rows == []
    else:
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert (
            config_entry.options[CONF_SOURCE_MAPPINGS]["withings"]["entities"]["weight"]
            == entity.id
        )
        assert priority[0] == "withings"
        assert len(rows) == 1
        assert rows[0].value == 81
        assert rows[0].provider == "withings"
        assert rows[0].external_id == entity.id
