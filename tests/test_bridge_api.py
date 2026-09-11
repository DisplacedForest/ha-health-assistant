from __future__ import annotations

import pytest

from custom_components.health_assistant.store.bridge_models import DOMAINS
from tests.test_bridge import native_batch, native_record


async def setup(hass, config_entry, client):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return await client(hass)


async def enroll_and_arm(hass, config_entry, hass_ws_client, hass_admin_user):
    client = await setup(hass, config_entry, hass_ws_client)
    await client.send_json(
        {
            "id": 1,
            "type": "health_assistant/bridge/admin",
            "action": "enroll",
            "parameters": {
                "owner_id": hass_admin_user.id,
                "metadata": {
                    "adapter_kind": "fixture",
                    "upstream_store": "apple_health",
                    "upstream_scope": "fixture",
                    "label": "Fixture",
                },
                "checkpoint_modes": dict.fromkeys(DOMAINS, "none"),
            },
        }
    )
    enrolled = await client.receive_json()
    assert enrolled["success"], enrolled
    source_id = enrolled["result"]["registration_id"]
    await client.send_json(
        {
            "id": 2,
            "type": "health_assistant/bridge/status",
            "registration_id": source_id,
        }
    )
    status = (await client.receive_json())["result"]
    scalar = next(item for item in status["domains"] if item["domain"] == "scalar")
    state = {
        "registration_id": source_id,
        "receiver_session_id": status["receiver_session_id"],
        "domains": {
            "scalar": {
                "committed": {
                    key: scalar[key]
                    for key in (
                        "checkpoint_mode",
                        "latest_batch_id",
                        "latest_request_hash",
                        "checkpoint_id",
                    )
                },
                "pending_request": None,
            }
        },
        "streams": {},
    }
    await client.send_json(
        {
            "id": 3,
            "type": "health_assistant/bridge/admin",
            "action": "rearm",
            "parameters": {"owner_id": hass_admin_user.id, "state": state},
        }
    )
    response = await client.receive_json()
    assert response["success"], response
    return client, source_id, response["result"]


async def test_real_http_auth_headers_and_native_replay(
    hass, config_entry, hass_ws_client, hass_client, hass_admin_user
):
    _socket, source_id, grant = await enroll_and_arm(
        hass, config_entry, hass_ws_client, hass_admin_user
    )
    client = await hass_client()
    url = f"/api/health_assistant/bridge/{source_id}/batches"
    batch = native_batch(source_id, [native_record(source_id)])
    headers = {
        "X-Health-Receiver-Session": grant["receiver_session_id"],
        "X-Health-Write-Lease": grant["write_lease"],
    }
    response = await client.post(url, json=batch, headers=headers)
    assert response.status == 200, await response.text()
    assert (await response.json())["changed"] == 1
    assert (await (await client.post(url, json=batch, headers=headers)).json())[
        "replayed"
    ]
    rejected = await client.post(url, json=batch)
    assert rejected.status == 409
    assert (await rejected.json())["error"] == "session_required"
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert (await client.post(url, json=batch, headers=headers)).status == 400


async def test_bridge_admin_rejects_read_only_user(
    hass, config_entry, hass_ws_client, hass_read_only_access_token
):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    client = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    await client.send_json(
        {
            "id": 1,
            "type": "health_assistant/bridge/admin",
            "action": "enroll",
            "parameters": {},
        }
    )
    response = await client.receive_json()
    assert response["error"]["code"] == "unauthorized"
    assert not config_entry.runtime_data.database.execute(
        "SELECT * FROM bridge_sources"
    )


@pytest.mark.parametrize(
    "headers,data,code",
    [
        ({"Content-Encoding": "identity"}, b"{}", "unsupported_encoding"),
        (
            {"Content-Type": "application/json"},
            b'{"domain":"scalar","domain":"sleep"}',
            "duplicate_field",
        ),
        (
            {"Content-Type": "application/json"},
            b'{"domain":"scalar", "records":' + b"[" * 13 + b"]" * 13 + b"}",
            "size_limit",
        ),
    ],
)
async def test_http_rejects_ambiguous_and_unbounded_input(
    hass,
    config_entry,
    hass_ws_client,
    hass_client,
    hass_admin_user,
    headers,
    data,
    code,
):
    _socket, source_id, grant = await enroll_and_arm(
        hass, config_entry, hass_ws_client, hass_admin_user
    )
    client = await hass_client()
    auth = {
        "X-Health-Receiver-Session": grant["receiver_session_id"],
        "X-Health-Write-Lease": grant["write_lease"],
        "Content-Type": "application/json",
    }
    response = await client.post(
        f"/api/health_assistant/bridge/{source_id}/batches",
        data=data,
        headers=auth | headers,
    )
    assert (await response.json())["error"] == code
    assert not config_entry.runtime_data.database.execute(
        "SELECT * FROM bridge_records"
    )


@pytest.mark.parametrize("change", ["token", "user"])
async def test_http_rechecks_current_auth_after_middleware(
    hass,
    config_entry,
    hass_ws_client,
    hass_client,
    hass_admin_user,
    hass_access_token,
    monkeypatch,
    change,
):
    _socket, source_id, grant = await enroll_and_arm(
        hass, config_entry, hass_ws_client, hass_admin_user
    )
    await _socket.close()
    await hass.async_block_till_done()
    client = await hass_client()
    runtime = config_entry.runtime_data.bridge
    token = hass.auth.async_validate_access_token(hass_access_token)
    original = runtime.repository.apply_batch

    def revoke_then_apply(*args):
        def invalidate():
            if change == "token":
                hass.auth.async_remove_refresh_token(token)
            else:
                token.user.is_active = False

        runtime._loop_check(invalidate)
        return original(*args)

    monkeypatch.setattr(runtime.repository, "apply_batch", revoke_then_apply)
    response = await client.post(
        f"/api/health_assistant/bridge/{source_id}/batches",
        json=native_batch(source_id, [native_record(source_id)]),
        headers={
            "X-Health-Receiver-Session": grant["receiver_session_id"],
            "X-Health-Write-Lease": grant["write_lease"],
        },
    )
    assert response.status == 401
    assert (await response.json())["error"] == "unauthorized"
    assert not runtime.database.execute("SELECT * FROM bridge_records")
