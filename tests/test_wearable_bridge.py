import hashlib
from datetime import UTC, datetime

from custom_components.health_assistant.store.bridge_models import DOMAINS
from custom_components.health_assistant.store.wearable_models import canonical


def native_batch(stream_id, expected=0, mean=70):
    projection = {
        "hash_scope": "health_assistant.wearable_batch",
        "hash_version": 1,
        "stream_id": stream_id,
        "expected_sequence": str(expected),
        "sequence": str(expected + 1),
        "operations": [
            {
                "op": "replace",
                "start": "2026-09-10T00:00:00.000000Z",
                "resolution": 60,
                "count": "2",
                "sum": mean * 2,
                "min": mean,
                "max": mean,
            }
        ],
    }
    digest = hashlib.sha256(canonical(projection)).hexdigest()
    del projection["hash_scope"]
    return {
        "version": 1,
        "domain": "wearable",
        "stream_batch": {**projection, "content_hash": digest},
    }


async def request(socket, number, command, **fields):
    await socket.send_json(
        {"id": number, "type": f"health_assistant/{command}", **fields}
    )
    return await socket.receive_json()


async def enroll(hass, config_entry, hass_ws_client, hass_admin_user):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    config_entry.runtime_data.bridge.clock = lambda: datetime(2026, 9, 11, tzinfo=UTC)
    socket = await hass_ws_client(hass)
    source = await request(
        socket,
        1,
        "bridge/admin",
        action="enroll",
        parameters={
            "owner_id": hass_admin_user.id,
            "metadata": {
                "adapter_kind": "fixture",
                "upstream_store": "apple_health",
                "upstream_scope": "example",
                "label": "Example",
            },
            "checkpoint_modes": dict.fromkeys(DOMAINS, "none"),
        },
    )
    assert source["success"], source
    source_id = source["result"]["registration_id"]
    stream = await request(
        socket,
        2,
        "wearable/admin",
        action="enroll",
        parameters={
            "registration_id": source_id,
            "owner_id": hass_admin_user.id,
            "weighting": "sample",
            "algorithm_id": None,
            "algorithm_version": None,
        },
    )
    assert stream["success"], stream
    return socket, source_id, stream["result"]["stream_id"]


async def arm(
    socket,
    number,
    source_id,
    stream_id,
    session,
    owner,
    *,
    committed=None,
    pending=None,
):
    return await request(
        socket,
        number,
        "bridge/admin",
        action="rearm",
        parameters={
            "owner_id": owner,
            "state": {
                "registration_id": source_id,
                "receiver_session_id": session,
                "domains": {},
                "streams": {
                    stream_id: {
                        "committed": committed
                        or {"sequence": "0", "content_hash": None},
                        "pending_batch": pending,
                    }
                },
            },
        },
    )


def headers(grant):
    return {
        "X-Health-Receiver-Session": grant["receiver_session_id"],
        "X-Health-Write-Lease": grant["write_lease"],
    }


async def test_native_wearable_transport_query_retry_and_retirement(
    hass, config_entry, hass_ws_client, hass_client, hass_admin_user
):
    socket, source_id, stream_id = await enroll(
        hass, config_entry, hass_ws_client, hass_admin_user
    )
    granted = await arm(
        socket,
        3,
        source_id,
        stream_id,
        config_entry.runtime_data.bridge.receiver_session_id,
        hass_admin_user.id,
    )
    assert granted["success"], granted
    grant = granted["result"]
    client = await hass_client()
    url = f"/api/health_assistant/bridge/{source_id}/batches"
    body = native_batch(stream_id)
    response = await client.post(url, json=body, headers=headers(grant))
    assert response.status == 200, await response.text()
    assert (await response.json())["sequence"] == "1"
    retry = await client.post(url, json=body, headers=headers(grant))
    assert (await retry.json())["replayed"]
    queried = await request(
        socket,
        4,
        "wearable_series",
        stream_id=stream_id,
        start="2026-09-10T00:00:00Z",
        end="2026-09-10T00:01:00Z",
    )
    assert queried["success"] and queried["result"]["points"][0]["value"] == 70
    retired = await request(
        socket,
        5,
        "wearable/admin",
        action="retire",
        parameters={"stream_id": stream_id},
    )
    assert retired["success"]
    denied = await client.post(
        url, json=native_batch(stream_id, 1, 80), headers=headers(grant)
    )
    assert denied.status == 409
    assert (
        config_entry.runtime_data.wearable.repository.tip(stream_id)["sequence"] == "1"
    )
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_reload_reconciles_one_lost_response_and_keeps_old_lease_invalid(
    hass, config_entry, hass_ws_client, hass_client, hass_admin_user
):
    socket, source_id, stream_id = await enroll(
        hass, config_entry, hass_ws_client, hass_admin_user
    )
    grant = (
        await arm(
            socket,
            3,
            source_id,
            stream_id,
            config_entry.runtime_data.bridge.receiver_session_id,
            hass_admin_user.id,
        )
    )["result"]
    client = await hass_client()
    url = f"/api/health_assistant/bridge/{source_id}/batches"
    body = native_batch(stream_id)
    response = await client.post(url, json=body, headers=headers(grant))
    assert response.status == 200
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    config_entry.runtime_data.bridge.clock = lambda: datetime(2026, 9, 11, tzinfo=UTC)
    old = await client.post(url, json=body, headers=headers(grant))
    assert old.status == 409
    rearmed = await arm(
        socket,
        4,
        source_id,
        stream_id,
        config_entry.runtime_data.bridge.receiver_session_id,
        hass_admin_user.id,
        pending=body["stream_batch"],
    )
    assert rearmed["success"], rearmed
    assert rearmed["result"]["acknowledged"]["streams"] == [stream_id]
    retried = await client.post(url, json=body, headers=headers(rearmed["result"]))
    assert (await retried.json())["replayed"]
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_wearable_admin_rejects_read_only_sessions(
    hass, config_entry, hass_ws_client, hass_read_only_access_token
):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    socket = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    response = await request(
        socket, 1, "wearable/admin", action="enroll", parameters={}
    )
    assert response["error"]["code"] == "unauthorized"
    assert (
        config_entry.runtime_data.database.execute(
            "SELECT COUNT(*) FROM wearable_streams"
        )[0][0]
        == 0
    )
    assert await hass.config_entries.async_unload(config_entry.entry_id)
