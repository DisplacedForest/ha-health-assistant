from copy import deepcopy
from datetime import UTC, datetime

import pytest
from homeassistant.core import State
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.health_assistant.const import (
    CONF_HEVY_SOURCE,
    CONF_MAPPINGS,
    DOMAIN,
)
from custom_components.health_assistant.hevy_source import (
    MAX_PAYLOAD_BYTES,
    discover_hevy,
    parse_workout,
)
from custom_components.health_assistant.providers.contract import (
    ProviderCapabilityError,
    ProviderError,
)

NOW = datetime(2026, 9, 6, 12, tzinfo=UTC)


def attributes():
    return {
        "date": "2026-09-05T12:00:00Z",
        "duration_minutes": 30,
        "total_volume": 1000,
        "total_volume_unit": "kg",
        "exercise_count": 1,
        "exercises": [
            {
                "name": "Squat",
                "notes": "Felt good",
                "sets": [
                    {
                        "type": "normal",
                        "weight": 100,
                        "weight_unit": "kg",
                        "reps": 10,
                        "duration_seconds": None,
                        "distance": None,
                        "distance_unit": "km",
                    }
                ],
            }
        ],
    }


def hevy_source(hass, title="Alice", profile="abcdef12", payload=None):
    entry = MockConfigEntry(domain="hevy", title=title, data={})
    entry.add_to_hass(hass)
    entity = er.async_get(hass).async_get_or_create(
        "sensor",
        "hevy",
        f"{profile}_last_workout_summary",
        config_entry=entry,
        suggested_object_id=f"summary_{profile}",
    )
    hass.states.async_set(
        entity.entity_id, "Leg day", attributes() if payload is None else payload
    )
    return entry, entity


async def setup_health(hass, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def select_hevy(hass, entry, source, **extra):
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    assert flow["step_id"] == "sources"
    return await hass.config_entries.options.async_configure(
        flow["flow_id"],
        user_input={
            "workout_source": f"hevy:{source.entry_id}",
            "confirm_person": True,
            **extra,
        },
    )


async def workout_rows(hass, entry):
    return await hass.async_add_executor_job(
        entry.runtime_data.repository.get_workouts, "primary"
    )


def test_parse_preserves_only_bounded_canonical_exercise_details():
    data = attributes()
    data["api_key"] = "must-not-be-stored"
    data["exercises"][0]["private"] = "must-not-be-stored"
    candidate = parse_workout(State("sensor.summary", "Leg day", data), "account", NOW)
    assert candidate.started_at == datetime(2026, 9, 5, 12, tzinfo=UTC)
    assert candidate.ended_at == datetime(2026, 9, 5, 12, 30, tzinfo=UTC)
    assert candidate.provenance["exercises"] == [
        {
            "name": "Squat",
            "notes": "Felt good",
            "sets": [{"type": "normal", "weight_kg": 100.0, "reps": 10}],
        }
    ]
    assert candidate.provenance["total_volume_kg_reps"] == 1000
    assert "must-not-be-stored" not in str(candidate)


def test_identity_ignores_equivalent_unit_presentation_and_timezone():
    first = attributes()
    second = deepcopy(first)
    second["date"] = "2026-09-05T07:00:00-05:00"
    second["total_volume"] = 1000 / 0.45359237
    second["total_volume_unit"] = "lbs"
    second["exercises"][0]["sets"][0].update(weight=100 / 0.45359237, weight_unit="lbs")
    a = parse_workout(State("sensor.old", "Leg day", first), "account", NOW)
    b = parse_workout(State("sensor.renamed", "Leg day", second), "account", NOW)
    assert a.external_id == b.external_id
    assert a.provenance["exercises"] == b.provenance["exercises"]
    assert a.provenance["total_volume_kg_reps"] == b.provenance["total_volume_kg_reps"]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("date", "not-a-date"),
        ("date", "2026-02-30T12:00:00Z"),
        ("date", "2026-09-05T12:00:00"),
        ("date", "2099-01-01T00:00:00Z"),
        ("duration_minutes", -1),
        ("duration_minutes", float("nan")),
        ("duration_minutes", float("inf")),
        ("duration_minutes", True),
        ("duration_minutes", 10**1000),
        ("total_volume", -1),
        ("total_volume_unit", "furlong"),
        ("exercise_count", 2),
        ("exercises", {}),
        ("exercises", [{}] * 101),
    ],
)
def test_invalid_workout_headers_are_rejected(key, value):
    data = attributes()
    data[key] = value
    with pytest.raises(ProviderError):
        parse_workout(State("sensor.summary", "Leg day", data), "account", NOW)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("weight", -1),
        ("weight", True),
        ("weight", float("nan")),
        ("weight_unit", None),
        ("weight_unit", "stones-ish"),
        ("reps", 1.5),
        ("reps", -1),
        ("duration_seconds", -1),
        ("distance", float("inf")),
        ("distance_unit", "parsecs"),
    ],
)
def test_invalid_set_values_are_rejected(key, value):
    data = attributes()
    row = data["exercises"][0]["sets"][0]
    row["distance"] = 1
    row[key] = value
    with pytest.raises(ProviderError):
        parse_workout(State("sensor.summary", "Leg day", data), "account", NOW)


@pytest.mark.parametrize("shape", ["sets", "all_sets", "notes", "bytes"])
def test_payload_limits_are_enforced(shape):
    data = attributes()
    exercise = data["exercises"][0]
    if shape == "sets":
        exercise["sets"] *= 101
    elif shape == "all_sets":
        exercise["sets"] *= 100
        data["exercises"] *= 11
        data["exercise_count"] = 11
    elif shape == "notes":
        exercise["notes"] = "x" * 1001
    else:
        exercise["notes"] = "界" * 1000
        data["exercises"] *= 100
        data["exercise_count"] = 100
    with pytest.raises(ProviderError):
        parse_workout(State("sensor.summary", "Leg day", data), "account", NOW)


async def test_unicode_payload_bound_matches_persisted_bytes(hass, config_entry):
    data = attributes()
    data["exercises"][0]["notes"] = "界" * 1000
    data["exercises"] *= 40
    data["exercise_count"] = 40
    source, entity = hevy_source(hass, payload=data)
    await setup_health(hass, config_entry)
    await select_hevy(hass, config_entry, source)
    await hass.async_block_till_done()
    before = await workout_rows(hass, config_entry)
    assert len(before) == 1
    assert before[0].provenance["exercises"][0]["notes"] == "界" * 1000
    database = config_entry.runtime_data.database
    stored = await hass.async_add_executor_job(
        database.execute,
        "SELECT length(CAST(provenance AS BLOB)) AS size FROM workouts",
    )
    assert 240000 < stored[0]["size"] <= MAX_PAYLOAD_BYTES
    data["exercises"] = data["exercises"][:1] * 50
    data["exercise_count"] = 50
    hass.states.async_set(entity.entity_id, "Leg day", data)
    await hass.async_block_till_done()
    assert config_entry.runtime_data.registry.status("hevy").degraded
    assert await workout_rows(hass, config_entry) == before
    unchanged = await hass.async_add_executor_job(
        database.execute,
        "SELECT length(CAST(provenance AS BLOB)) AS size FROM workouts",
    )
    assert unchanged[0]["size"] == stored[0]["size"]


async def test_absent_source_and_drafts_do_not_offer_hevy(hass, config_entry):
    await setup_health(hass, config_entry)
    assert discover_hevy(hass) == []
    assert "hevy" not in config_entry.runtime_data.registry.providers
    flow = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert flow["step_id"] == "init"
    source = MockConfigEntry(domain="hevy", title="Alice", data={})
    source.add_to_hass(hass)
    entity = er.async_get(hass).async_get_or_create(
        "sensor", "hevy", "abcdef12_workout_session", config_entry=source
    )
    hass.states.async_set(entity.entity_id, "Session", attributes())
    assert discover_hevy(hass)[0].binding is None


async def test_explicit_source_ingests_once_and_survives_reload(hass, config_entry):
    source, entity = hevy_source(hass)
    await setup_health(hass, config_entry)
    assert await workout_rows(hass, config_entry) == []
    result = await select_hevy(hass, config_entry, source)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    rows = await workout_rows(hass, config_entry)
    assert len(rows) == 1
    assert rows[0].provider == "hevy"
    assert rows[0].title == "Leg day"
    assert rows[0].provenance["exercises"][0]["sets"][0]["weight_kg"] == 100
    assert config_entry.runtime_data.registry.providers["hevy"].capabilities.workouts
    assert not config_entry.runtime_data.registry.status("hevy").degraded
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(await workout_rows(hass, config_entry)) == 1
    er.async_get(hass).async_update_entity(
        entity.entity_id, new_entity_id="sensor.renamed_hevy"
    )
    hass.states.async_set("sensor.renamed_hevy", "Leg day", attributes())
    await hass.async_block_till_done()
    assert len(await workout_rows(hass, config_entry)) == 1


async def test_bad_hevy_state_degrades_and_recovers_without_affecting_manual(
    hass, config_entry
):
    source, entity = hevy_source(hass)
    await setup_health(hass, config_entry)
    await select_hevy(hass, config_entry, source)
    await hass.async_block_till_done()
    hass.states.async_set(entity.entity_id, "unavailable")
    await hass.async_block_till_done()
    registry = config_entry.runtime_data.registry
    assert registry.status("hevy").degraded
    assert not registry.providers["hevy"].capabilities.workouts
    await hass.services.async_call(
        DOMAIN, "add_observation", {"metric": "weight", "value": 80}, blocking=True
    )
    assert not registry.status("manual").degraded
    data = attributes()
    data["date"] = "2026-09-05T14:00:00Z"
    hass.states.async_set(entity.entity_id, "Second workout", data)
    await hass.async_block_till_done()
    assert not registry.status("hevy").degraded
    assert len(await workout_rows(hass, config_entry)) == 2


async def test_unsupported_services_never_enable_export(hass, config_entry):
    source, _ = hevy_source(hass)

    async def unsupported(call):
        raise AssertionError("Unsupported service was called")

    hass.services.async_register("hevy", "set_body_measurement", unsupported)
    assert "set_body_measurement" in discover_hevy(hass)[0].services
    await setup_health(hass, config_entry)
    await select_hevy(hass, config_entry, source)
    await hass.async_block_till_done()
    registry = config_entry.runtime_data.registry
    assert not registry.providers["hevy"].capabilities.can_export
    with pytest.raises(ProviderCapabilityError):
        await registry.async_export("hevy", [])


async def test_account_confirmation_and_options_preservation(hass):
    source, _ = hevy_source(hass)
    hevy_source(hass, title="Bob", profile="12345678")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_MAPPINGS: {"weight": ["sensor.scale"]},
            "environment": {"room": "bedroom"},
        },
    )
    await setup_health(hass, entry)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    assert flow["data_schema"]({})["workout_source"] == "keep_current"
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={"workout_source": f"hevy:{source.entry_id}"}
    )
    assert result["errors"]["workout_source"] == "confirm_person"
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        user_input={
            "workout_source": f"hevy:{source.entry_id}",
            "confirm_person": True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_HEVY_SOURCE]["config_entry_id"] == source.entry_id
    assert entry.options[CONF_MAPPINGS] == {"weight": ["sensor.scale"]}
    assert entry.options["environment"] == {"room": "bedroom"}


async def test_replaced_binding_during_manual_step_aborts(hass, config_entry):
    source, entity = hevy_source(hass)
    await setup_health(hass, config_entry)
    flow = await select_hevy(hass, config_entry, source, manual_mapping=True)
    registry = er.async_get(hass)
    registry.async_update_entity(entity.entity_id, new_unique_id="retired_summary")
    replacement = registry.async_get_or_create(
        "sensor", "hevy", "abcdef12_last_workout_summary", config_entry=source
    )
    hass.states.async_set(replacement.entity_id, "Leg day", attributes())
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "source_changed"
    assert CONF_HEVY_SOURCE not in config_entry.options
    assert await workout_rows(hass, config_entry) == []


async def test_bad_startup_still_recovers_on_later_state(hass, config_entry):
    source, entity = hevy_source(hass)
    await setup_health(hass, config_entry)
    await select_hevy(hass, config_entry, source)
    await hass.async_block_till_done()
    hass.states.async_set(entity.entity_id, "unavailable")
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.runtime_data.registry.status("hevy").degraded
    hass.states.async_set(entity.entity_id, "Leg day", attributes())
    await hass.async_block_till_done()
    assert not config_entry.runtime_data.registry.status("hevy").degraded
    assert len(await workout_rows(hass, config_entry)) == 1


@pytest.mark.parametrize("change", ["disabled", "identity", "account"])
async def test_registry_changes_degrade_only_the_selected_source(
    hass, config_entry, change
):
    source, entity = hevy_source(hass)
    other, _ = hevy_source(hass, title="Bob", profile="12345678")
    await setup_health(hass, config_entry)
    await select_hevy(hass, config_entry, source)
    await hass.async_block_till_done()
    changes = {
        "disabled": {"disabled_by": er.RegistryEntryDisabler.USER},
        "identity": {"new_unique_id": "12341234_last_workout_summary"},
        "account": {"config_entry_id": other.entry_id},
    }
    er.async_get(hass).async_update_entity(entity.entity_id, **changes[change])
    await hass.async_block_till_done()
    registry = config_entry.runtime_data.registry
    assert registry.status("hevy").degraded
    assert not registry.status("manual").degraded
    assert len(await workout_rows(hass, config_entry)) == 1


async def test_disabling_capture_keeps_recorded_workouts(hass, config_entry):
    source, entity = hevy_source(hass)
    await setup_health(hass, config_entry)
    await select_hevy(hass, config_entry, source)
    await hass.async_block_till_done()
    flow = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={"workout_source": "disable_capture"}
    )
    await hass.async_block_till_done()
    assert "hevy" not in config_entry.runtime_data.registry.providers
    hass.states.async_set(entity.entity_id, "Another workout", attributes())
    await hass.async_block_till_done()
    assert len(await workout_rows(hass, config_entry)) == 1


async def test_duplicate_account_names_are_not_selectable(hass):
    hevy_source(hass)
    hevy_source(hass, profile="12345678")
    offers = discover_hevy(hass)
    assert len(offers) == 2
    assert all(offer.binding is None for offer in offers)
    assert all("Rename accounts" in offer.warning for offer in offers)


def test_public_workout_id_is_preferred_and_scoped_to_account():
    data = attributes()
    data["workout_id"] = "workout-123"
    first = parse_workout(State("sensor.summary", "Leg day", data), "alice", NOW)
    renamed = parse_workout(State("sensor.summary", "New title", data), "alice", NOW)
    other = parse_workout(State("sensor.summary", "Leg day", data), "bob", NOW)
    assert first.external_id == renamed.external_id
    assert first.external_id != other.external_id


def test_distance_is_normalized_from_explicit_set_units():
    data = attributes()
    data["exercises"][0]["sets"][0].update(distance=1, distance_unit="mi")
    candidate = parse_workout(State("sensor.summary", "Training", data), "alice", NOW)
    assert candidate.distance == pytest.approx(1609.344)
    assert candidate.distance_unit == "m"
    assert candidate.provenance["exercises"][0]["sets"][0][
        "distance_m"
    ] == pytest.approx(1609.344)
