from datetime import UTC, datetime

from custom_components.health_assistant.store.recovery import RecoveryRepository
from custom_components.health_assistant.store.recovery_models import (
    normalized_observation,
)

START = "2026-09-06T00:00:00Z"
END = "2026-09-06T08:00:00Z"
AFTER = "2026-09-07T00:00:00Z"
SERIES = {
    "provider": "fixture",
    "source_id": "selected-account",
    "metric": "hrv_sdnn",
    "context": "unknown",
    "algorithm_id": None,
    "algorithm_version": None,
}


async def setup(hass, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    repository = RecoveryRepository(config_entry.runtime_data.database)
    value = normalized_observation(
        "fixture",
        "selected-account",
        "night",
        1,
        {
            "value": 50,
            "unit": "ms",
            "started_at": START,
            "ended_at": END,
            "provenance": {"source_app": "private fixture app"},
        },
        datetime.now(UTC),
        metric="hrv_sdnn",
    )
    return (
        await hass.async_add_executor_job(repository.apply_recovery_changes, [value])
    )[0].observation


async def test_recovery_list_detail_exclusion_and_lifecycle(
    hass, hass_ws_client, config_entry
):
    observation = await setup(hass, config_entry)
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "health_assistant/recovery_observations",
            "start": START,
            "end": AFTER,
            "series": SERIES,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["observations"][0]["source_revision"] == "1"
    assert "provenance" not in response["result"]["observations"][0]
    await client.send_json(
        {
            "id": 2,
            "type": "health_assistant/recovery_observation",
            "record_id": observation.id,
        }
    )
    detail = (await client.receive_json())["result"]
    assert detail["provenance"]["source_app"] == "private fixture app"
    assert detail["value"] == 50
    await client.send_json(
        {
            "id": 3,
            "type": "health_assistant/recovery_observation_exclusion",
            "record_id": observation.id,
            "excluded": True,
            "expected_source_revision": "1",
            "expected_payload_hash": observation.payload_hash,
        }
    )
    result = await client.receive_json()
    assert result["success"] and result["result"]["status"] == "excluded"
    await client.send_json(
        {
            "id": 4,
            "type": "health_assistant/recovery_observation_exclusion",
            "record_id": observation.id,
            "excluded": False,
            "expected_source_revision": "2",
            "expected_payload_hash": observation.payload_hash,
        }
    )
    assert (await client.receive_json())["error"]["code"] == "revision_conflict"
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await client.send_json(
        {
            "id": 5,
            "type": "health_assistant/recovery_observation",
            "record_id": observation.id,
        }
    )
    assert (await client.receive_json())["error"]["code"] == "not_loaded"
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await client.send_json(
        {
            "id": 6,
            "type": "health_assistant/recovery_observation",
            "record_id": observation.id,
        }
    )
    assert (await client.receive_json())["result"]["status"] == "excluded"


async def test_recovery_read_only_user_cannot_mutate(
    hass, hass_ws_client, hass_read_only_access_token, config_entry
):
    observation = await setup(hass, config_entry)
    client = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    await client.send_json(
        {
            "id": 1,
            "type": "health_assistant/recovery_observation_exclusion",
            "record_id": observation.id,
            "excluded": True,
            "expected_source_revision": "1",
            "expected_payload_hash": observation.payload_hash,
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"
    await client.send_json(
        {
            "id": 2,
            "type": "health_assistant/recovery_observations",
            "start": START,
            "end": AFTER,
            "series": SERIES,
        }
    )
    assert (await client.receive_json())["result"]["observations"][0][
        "status"
    ] == "active"


async def test_recovery_bad_ranges_and_source_fields_are_rejected(
    hass, hass_ws_client, config_entry
):
    await setup(hass, config_entry)
    client = await hass_ws_client(hass)
    for index, extra in enumerate(
        (
            {"start": "naive"},
            {"end": START},
            {"limit": True},
            {"series": {"provider": "fixture"}},
            {
                "series": {
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
                "type": "health_assistant/recovery_observations",
                "start": START,
                "end": AFTER,
                "series": SERIES,
                **extra,
            }
        )
        response = await client.receive_json()
        assert not response["success"]
        assert "private fixture app" not in str(response)


async def test_recovery_diagnostics_omit_measurements_and_account(hass, config_entry):
    from custom_components.health_assistant.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    await setup(hass, config_entry)
    result = await async_get_config_entry_diagnostics(hass, config_entry)
    assert result["database"]["recovery_count"] == 1
    text = str(result)
    for private in ("private fixture app", "selected-account", "night", START, END):
        assert private not in text
