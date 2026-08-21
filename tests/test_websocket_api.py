from datetime import UTC, datetime, timedelta

from custom_components.health_assistant.const import DOMAIN
from custom_components.health_assistant.store import HealthObservation, MetricType

OBSERVED = datetime(2026, 8, 20, 7, 30, tzinfo=UTC)


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
