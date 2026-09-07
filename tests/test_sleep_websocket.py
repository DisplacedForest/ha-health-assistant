from datetime import UTC, datetime

from custom_components.health_assistant.store.sleep import SleepRepository
from custom_components.health_assistant.store.sleep_models import normalized_session

START = "2026-09-06T00:00:00Z"
END = "2026-09-06T08:00:00Z"


async def setup(hass, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    repository = SleepRepository(config_entry.runtime_data.database)
    value = normalized_session(
        "fixture",
        "selected-account",
        "night",
        1,
        {
            "started_at": START,
            "ended_at": END,
            "provenance": {"source_app": "private fixture app"},
        },
        datetime.now(UTC),
    )
    return (await hass.async_add_executor_job(repository.apply_sleep_changes, [value]))[
        0
    ].session


async def test_sleep_list_detail_exclusion_and_lifecycle(
    hass, hass_ws_client, config_entry
):
    session = await setup(hass, config_entry)
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "health_assistant/sleep_sessions", "start": START, "end": END}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["sessions"][0]["source_revision"] == "1"
    assert "provenance" not in response["result"]["sessions"][0]
    await client.send_json(
        {"id": 2, "type": "health_assistant/sleep_session", "session_id": session.id}
    )
    detail = (await client.receive_json())["result"]
    assert detail["provenance"]["source_app"] == "private fixture app"
    assert detail["asleep_duration_us"] is None
    await client.send_json(
        {
            "id": 3,
            "type": "health_assistant/sleep_session_exclusion",
            "session_id": session.id,
            "excluded": True,
            "expected_source_revision": "1",
            "expected_payload_hash": session.payload_hash,
        }
    )
    result = await client.receive_json()
    assert result["success"] and result["result"]["status"] == "excluded"
    await client.send_json(
        {
            "id": 4,
            "type": "health_assistant/sleep_session_exclusion",
            "session_id": session.id,
            "excluded": False,
            "expected_source_revision": "2",
            "expected_payload_hash": session.payload_hash,
        }
    )
    assert (await client.receive_json())["error"]["code"] == "revision_conflict"
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await client.send_json(
        {"id": 5, "type": "health_assistant/sleep_session", "session_id": session.id}
    )
    assert (await client.receive_json())["error"]["code"] == "not_loaded"
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await client.send_json(
        {"id": 6, "type": "health_assistant/sleep_session", "session_id": session.id}
    )
    assert (await client.receive_json())["result"]["status"] == "excluded"


async def test_sleep_read_only_user_cannot_mutate(
    hass, hass_ws_client, hass_read_only_access_token, config_entry
):
    session = await setup(hass, config_entry)
    client = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    await client.send_json(
        {
            "id": 1,
            "type": "health_assistant/sleep_session_exclusion",
            "session_id": session.id,
            "excluded": True,
            "expected_source_revision": "1",
            "expected_payload_hash": session.payload_hash,
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"
    await client.send_json(
        {"id": 2, "type": "health_assistant/sleep_sessions", "start": START, "end": END}
    )
    assert (await client.receive_json())["result"]["sessions"][0]["status"] == "active"


async def test_sleep_bad_ranges_and_source_fields_are_rejected(
    hass, hass_ws_client, config_entry
):
    await setup(hass, config_entry)
    client = await hass_ws_client(hass)
    for index, extra in enumerate(
        (
            {"start": "naive"},
            {"end": START},
            {"limit": True},
            {"source": {"provider": "fixture"}},
            {
                "source": {
                    "provider": "fixture",
                    "source_id": "selected-account",
                    "person_id": "other",
                }
            },
        ),
        1,
    ):
        await client.send_json(
            {
                "id": index,
                "type": "health_assistant/sleep_sessions",
                "start": START,
                "end": END,
                **extra,
            }
        )
        response = await client.receive_json()
        assert not response["success"]
        assert "private fixture app" not in str(response)
