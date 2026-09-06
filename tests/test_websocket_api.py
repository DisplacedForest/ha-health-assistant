from datetime import UTC, datetime, timedelta

import pytest
from homeassistant.util import dt as dt_util

from custom_components.health_assistant.const import DOMAIN
from custom_components.health_assistant.store import (
    HealthObservation,
    MetricType,
    Workout,
)

OBSERVED = datetime(2026, 8, 20, 7, 30, tzinfo=UTC)


async def test_body_and_workout_detail(hass, hass_ws_client, config_entry):
    await setup_integration(hass, config_entry)
    now = dt_util.utcnow() - timedelta(minutes=1)
    saved = await hass.async_add_executor_job(
        config_entry.runtime_data.repository.upsert_workout,
        Workout(
            person_id="primary",
            provider="fixture",
            external_id="recorded-workout",
            workout_type="strength",
            started_at=now - timedelta(hours=1),
            ended_at=now,
            ingested_at=now,
            provenance={
                "private_payload": "not exposed",
                "exercises": [{"name": "Bench Press (Barbell)", "sets": [{"reps": 8}]}],
            },
        ),
    )
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/body"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["workout_count"] == 1
    assert msg["result"]["workouts"][0]["id"] == saved.id
    assert "private_payload" not in str(msg)
    await client.send_json(
        {"id": 2, "type": f"{DOMAIN}/workout_detail", "workout_id": saved.id}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["exercises"][0]["recorded_sets"] == 1
    assert "private_payload" not in str(msg)
    await client.send_json(
        {"id": 3, "type": f"{DOMAIN}/workout_detail", "workout_id": -1}
    )
    assert not (await client.receive_json())["success"]
    await client.send_json(
        {"id": 4, "type": f"{DOMAIN}/workout_detail", "workout_id": 999999}
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"


async def setup_integration(hass, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


async def test_summary_empty_store(hass, hass_ws_client, config_entry):
    await setup_integration(hass, config_entry)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/summary"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["current_weight"] is None
    assert msg["result"]["latest_workout"] is None
    assert msg["result"]["workouts_last_7_days"] is None


async def test_overview_and_record_detail(hass, hass_ws_client, config_entry):
    await setup_integration(hass, config_entry)
    await hass.services.async_call(
        DOMAIN,
        "add_body_measurement",
        {"weight": 80, "external_id": "detail"},
        blocking=True,
    )
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/overview"})
    response = await client.receive_json()
    assert response["success"]
    result = response["result"]
    assert len(result["metrics"]) == 6
    assert result["metrics"][0]["current"]["value"] == 80
    assert result["metrics"][0]["delta"] is None
    assert all(len(item["points"]) <= 120 for item in result["metrics"])
    assert set(result["providers"][0]) == {
        "key",
        "name",
        "degraded",
        "last_success",
        "had_error",
    }
    observation_id = result["metrics"][0]["current"]["id"]
    await client.send_json(
        {
            "id": 2,
            "type": f"{DOMAIN}/observation_detail",
            "observation_id": observation_id,
        }
    )
    detail = (await client.receive_json())["result"]
    assert detail["observation"]["id"] == observation_id
    assert detail["claims"][0]["selected"]
    assert detail["claims"][0]["external_id"] == "detail-weight"
    assert "provenance" not in detail["claims"][0]
    await client.send_json(
        {"id": 3, "type": f"{DOMAIN}/observation_detail", "observation_id": 999999}
    )
    assert (await client.receive_json())["error"]["code"] == "not_found"
    await client.send_json(
        {"id": 4, "type": f"{DOMAIN}/observation_detail", "observation_id": True}
    )
    assert not (await client.receive_json())["success"]


async def test_summary_populated(hass, hass_ws_client, config_entry):
    await setup_integration(hass, config_entry)
    await hass.services.async_call(
        DOMAIN,
        "add_body_measurement",
        {"weight": 180.0, "weight_unit": "lb", "external_id": "seed"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "add_workout",
        {
            "workout_type": "running",
            "title": "Morning run",
            "start": "2026-08-21T07:00:00+00:00",
            "end": "2026-08-21T07:45:00+00:00",
            "external_id": "run",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/summary"})
    msg = await client.receive_json()
    assert msg["success"]
    weight = msg["result"]["current_weight"]
    assert weight["unit"] == "kg"
    assert weight["provider"] == "manual"
    assert weight["source"] == "seed-weight"
    workout = msg["result"]["latest_workout"]
    assert workout["title"] == "Morning run"
    assert workout["duration_seconds"] == 2700.0


async def test_time_series_payload_and_validation(hass, hass_ws_client, config_entry):
    entry = await setup_integration(hass, config_entry)
    repository = entry.runtime_data.repository

    def seed():
        now = datetime.now(UTC)
        for index in range(3):
            repository.upsert_observation(
                HealthObservation(
                    person_id="primary",
                    metric=MetricType.WEIGHT,
                    value=80.0 + index,
                    unit="kg",
                    observed_at=now - timedelta(days=index),
                    provider="test",
                    external_id=f"r{index}",
                    ingested_at=now,
                )
            )

    await hass.async_add_executor_job(seed)
    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 1, "type": f"{DOMAIN}/time_series", "metric": "weight", "days": 7}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["unit"] == "kg"
    assert msg["result"]["downsampled"] is False
    points = msg["result"]["points"]
    assert len(points) == 3
    assert points == sorted(points, key=lambda p: p["t"])
    assert points[0]["provider"] == "test"

    await client.send_json(
        {"id": 2, "type": f"{DOMAIN}/time_series", "metric": "weight", "days": 14}
    )
    msg = await client.receive_json()
    assert not msg["success"]

    await client.send_json(
        {"id": 3, "type": f"{DOMAIN}/time_series", "metric": "blood_type"}
    )
    msg = await client.receive_json()
    assert not msg["success"]


async def test_time_series_downsamples_to_cap(hass, hass_ws_client, config_entry):
    entry = await setup_integration(hass, config_entry)
    repository = entry.runtime_data.repository

    def seed():
        now = datetime.now(UTC)
        for index in range(700):
            repository.upsert_observation(
                HealthObservation(
                    person_id="primary",
                    metric=MetricType.STEPS,
                    value=float(index),
                    unit="count",
                    observed_at=now - timedelta(minutes=index),
                    provider="test",
                    external_id=f"s{index}",
                    ingested_at=now,
                )
            )

    await hass.async_add_executor_job(seed)
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": f"{DOMAIN}/time_series", "metric": "steps", "days": 7}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["downsampled"] is True
    points = msg["result"]["points"]
    assert len(points) == 500
    assert points[0]["v"] == 699.0
    assert points[-1]["v"] == 0.0


async def test_not_loaded_error_after_unload(hass, hass_ws_client, config_entry):
    entry = await setup_integration(hass, config_entry)
    client = await hass_ws_client(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    await client.send_json({"id": 1, "type": f"{DOMAIN}/summary"})
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_loaded"


async def test_panel_registered_and_removed(hass, config_entry):
    entry = await setup_integration(hass, config_entry)
    panels = hass.data["frontend_panels"]
    assert DOMAIN in panels
    panel = panels[DOMAIN]
    assert panel.sidebar_title == "Health"
    assert (
        panel.config["_panel_custom"]["module_url"] == f"/{DOMAIN}_panel_files/panel.js"
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN not in hass.data["frontend_panels"]


async def test_contested_metric_agrees_across_sensor_and_websocket(
    hass, hass_ws_client, config_entry
):
    await setup_integration(hass, config_entry)
    repository = config_entry.runtime_data.repository
    for provider, external_id, value, offset in (
        ("test_scale", "s-1", 80.0, 0),
        ("test_bridge", "b-1", 90.0, 30),
    ):
        await hass.async_add_executor_job(
            repository.upsert_observation,
            HealthObservation(
                person_id="primary",
                metric=MetricType.WEIGHT,
                value=value,
                unit="kg",
                observed_at=OBSERVED + timedelta(seconds=offset),
                provider=provider,
                external_id=external_id,
                ingested_at=OBSERVED,
            ),
        )
    await hass.async_add_executor_job(
        repository.set_priority, MetricType.WEIGHT, ["test_scale", "test_bridge"]
    )
    coordinator = config_entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.health_assistant_current_weight")
    assert float(state.state) == 80.0

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/summary"})
    msg = await client.receive_json()
    assert msg["success"]
    weight = msg["result"]["current_weight"]
    assert weight["value"] == 80.0
    assert weight["provider"] == "test_scale"
    assert weight["possible_duplicate"] is True


async def test_exclusion_and_restore_refresh_entities_and_queries(
    hass, hass_ws_client, config_entry
):
    await setup_integration(hass, config_entry)
    await hass.services.async_call(
        DOMAIN,
        "add_body_measurement",
        {"weight": 80.0, "external_id": "bad-scale-reading"},
        blocking=True,
    )
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": f"{DOMAIN}/observations", "metric": "weight"}
    )
    response = await client.receive_json()
    observation = response["result"]["observations"][0]
    assert observation["excluded"] is False
    await client.send_json(
        {
            "id": 2,
            "type": f"{DOMAIN}/observation_exclusion",
            "observation_id": observation["id"],
            "excluded": True,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["excluded"] is True
    await hass.async_block_till_done()
    assert hass.states.get("sensor.health_assistant_current_weight").state == "unknown"
    await client.send_json({"id": 3, "type": f"{DOMAIN}/summary"})
    assert (await client.receive_json())["result"]["current_weight"] is None
    await client.send_json(
        {"id": 4, "type": f"{DOMAIN}/time_series", "metric": "weight"}
    )
    assert (await client.receive_json())["result"]["points"] == []
    await client.send_json(
        {"id": 5, "type": f"{DOMAIN}/observations", "excluded": True}
    )
    assert len((await client.receive_json())["result"]["observations"]) == 1
    await client.send_json(
        {
            "id": 6,
            "type": f"{DOMAIN}/observation_exclusion",
            "observation_id": observation["id"],
            "excluded": False,
        }
    )
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done()
    assert (
        float(hass.states.get("sensor.health_assistant_current_weight").state) == 80.0
    )


async def test_exclusion_rejects_invalid_missing_and_unloaded_records(
    hass, hass_ws_client, config_entry
):
    await setup_integration(hass, config_entry)
    client = await hass_ws_client(hass)
    for request_id, identifier in enumerate([0, -1, True, "1", 1.5, 2**63, 999], 1):
        await client.send_json(
            {
                "id": request_id,
                "type": f"{DOMAIN}/observation_exclusion",
                "observation_id": identifier,
                "excluded": True,
            }
        )
        response = await client.receive_json()
        assert response["success"] is False
        assert response["error"]["code"] == (
            "not_found" if identifier == 999 else "invalid_format"
        )
    await client.send_json({"id": 8, "type": f"{DOMAIN}/observations", "limit": 101})
    assert (await client.receive_json())["success"] is False
    await hass.config_entries.async_unload(config_entry.entry_id)
    await client.send_json(
        {
            "id": 9,
            "type": f"{DOMAIN}/observation_exclusion",
            "observation_id": 1,
            "excluded": True,
        }
    )
    assert (await client.receive_json())["error"]["code"] == "not_loaded"


async def test_read_only_user_cannot_change_observation_exclusion(
    hass, hass_ws_client, hass_read_only_access_token, config_entry
):
    await setup_integration(hass, config_entry)
    client = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/observation_exclusion",
            "observation_id": 1,
            "excluded": True,
        }
    )
    response = await client.receive_json()
    assert response["success"] is False
    assert response["error"]["code"] == "unauthorized"


@pytest.mark.parametrize("field", ["name", "notes", "type", "valid"])
async def test_invalid_unicode_detail_stays_serializable(
    hass, hass_ws_client, config_entry, field
):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    now = datetime.now(UTC) - timedelta(minutes=1)
    item = {"name": "Bench Press (Barbell)", "sets": [{"reps": 8}]}
    if field == "type":
        item["sets"][0]["type"] = "\ud800"
    elif field != "valid":
        item[field] = "\ud800"
    valid = {
        "name": "スクワット 🏋️",
        "notes": "café, 今日",
        "sets": [{"type": "通常", "reps": 5}],
    }
    saved = await hass.async_add_executor_job(
        config_entry.runtime_data.repository.upsert_workout,
        Workout(
            person_id="primary",
            provider="legacy",
            external_id=field,
            workout_type="strength",
            started_at=now - timedelta(hours=1),
            ended_at=now,
            ingested_at=now,
            provenance={"exercises": [item, valid]},
        ),
    )
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/body"})
    body = await client.receive_json()
    await client.send_json(
        {"id": 2, "type": f"{DOMAIN}/workout_detail", "workout_id": saved.id}
    )
    detail = await client.receive_json()
    assert body["success"], body
    assert detail["success"], detail
    assert detail["result"]["incomplete"] is (field != "valid")
    assert detail["result"]["exercises"][-1]["name"] == valid["name"]
    assert detail["result"]["exercises"][-1]["notes"] == valid["notes"]
    assert detail["result"]["exercises"][-1]["sets"][0]["type"] == "通常"
    assert body["result"]["workout_count"] == 1
    assert body["result"]["incomplete_workouts"] == int(field != "valid")
