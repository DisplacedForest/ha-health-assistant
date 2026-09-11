import hashlib
from datetime import UTC, datetime

from custom_components.health_assistant.store.bridge_models import DOMAINS
from custom_components.health_assistant.store.bridge_registry import BridgeRegistry
from custom_components.health_assistant.store.wearable import WearableRepository
from custom_components.health_assistant.store.wearable_models import canonical
from custom_components.health_assistant.store.wearable_schema import MIGRATION
from custom_components.health_assistant.wearable_websocket import (
    async_register_wearable_websocket,
)


async def test_wearable_read_only_route_and_strict_inputs(
    hass, hass_ws_client, hass_read_only_access_token, config_entry
):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    database = config_entry.runtime_data.database

    def prepare():
        with database.transaction():
            for statement in MIGRATION:
                database.execute(statement)
        source = BridgeRegistry(database).enroll(
            {
                "adapter_kind": "fixture",
                "upstream_store": "apple_health",
                "upstream_scope": "example",
                "label": "Example",
            },
            "owner",
            dict.fromkeys(DOMAINS, "none"),
            datetime(2026, 9, 11, tzinfo=UTC),
        )
        repository = WearableRepository(database)
        stream_id = repository.enroll(source["source_id"], "owner", weighting="sample")[
            "stream_id"
        ]
        value = {
            "hash_scope": "health_assistant.wearable_batch",
            "hash_version": 1,
            "stream_id": stream_id,
            "expected_sequence": "0",
            "sequence": "1",
            "operations": [
                {
                    "op": "replace",
                    "start": "2026-09-10T00:00:00.000000Z",
                    "resolution": 60,
                    "count": "2",
                    "sum": 140,
                    "min": 60,
                    "max": 80,
                }
            ],
        }
        digest = hashlib.sha256(canonical(value)).hexdigest()
        del value["hash_scope"]
        repository.apply_batch(
            source["source_id"],
            {**value, "content_hash": digest},
            datetime(2026, 9, 11, tzinfo=UTC),
            lambda: None,
        )
        return stream_id

    stream_id = await hass.async_add_executor_job(prepare)
    async_register_wearable_websocket(hass)
    client = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    request = {
        "type": "health_assistant/wearable_series",
        "stream_id": stream_id,
        "start": "2026-09-10T00:00:30Z",
        "end": "2026-09-10T00:01:00Z",
    }
    await client.send_json({"id": 1, **request})
    result = await client.receive_json()
    assert result["success"]
    point = result["result"]["points"][0]
    assert point["value"] == 70
    assert point["sample_count"] == "2" and point["covered_us"] is None
    assert point["start"] == "2026-09-10T00:00:00.000000Z"
    for index, patch in enumerate(
        (
            {"limit": True},
            {"limit": 1001},
            {"resolution": True},
            {"resolution": "60"},
            {"unexpected": "field"},
            {"stream_id": "unknown"},
            {"start": "2026-09-10T00:00:00"},
            {"end": "2029-01-01T00:00:00Z"},
            {"cursor": "invalid"},
        ),
        2,
    ):
        await client.send_json({"id": index, **request, **patch})
        assert not (await client.receive_json())["success"]
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await client.send_json({"id": 20, **request})
    assert (await client.receive_json())["error"]["code"] == "not_loaded"
