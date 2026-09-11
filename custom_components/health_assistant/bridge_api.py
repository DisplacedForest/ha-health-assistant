from __future__ import annotations

from functools import partial

import voluptuous as vol
from aiohttp import web
from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.auth_util import async_user_not_allowed_do_auth
from homeassistant.core import callback
from homeassistant.helpers.http import KEY_HASS

from .const import DOMAIN
from .store.bridge_models import BridgeError, exact, text
from .store.errors import StoreValidationError


def runtime(hass):
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries or entries[0].runtime_data.bridge is None:
        raise BridgeError("not_loaded")
    return entries[0].runtime_data.bridge


def connection_auth(hass, connection, *, admin=False):
    token = (
        hass.auth.async_get_refresh_token(connection.refresh_token_id)
        if connection.refresh_token_id
        else None
    )
    if (
        token is None
        or token.user.id != connection.user.id
        or not token.user.is_active
        or admin
        and not token.user.is_admin
    ):
        raise BridgeError("unauthorized")


class BridgeBatchView(HomeAssistantView):
    url = f"/api/{DOMAIN}/bridge/{{registration_id}}/batches"
    name = f"api:{DOMAIN}:bridge:batches"
    requires_auth = True

    async def post(self, request, registration_id):
        hass = request.app[KEY_HASS]
        try:
            bridge = runtime(hass)
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                raise BridgeError("unauthorized")
            access_token = header[7:]

            def current():
                token = hass.auth.async_validate_access_token(access_token)
                if token is None or async_user_not_allowed_do_auth(
                    hass, token.user, request
                ):
                    raise BridgeError("unauthorized")
                return token.user.id

            owner_id = current()

            def authorized():
                if current() != owner_id:
                    raise BridgeError("unauthorized")

            if (
                request.headers.get("Content-Encoding")
                or request.content_type != "application/json"
            ):
                raise BridgeError("unsupported_encoding")
            if (
                request.content_length is not None
                and request.content_length > 8 * 1024 * 1024
            ):
                raise BridgeError("size_limit")

            async def read_body():
                body = bytearray()
                async for chunk in request.content.iter_chunked(65536):
                    body.extend(chunk)
                    if len(body) > 8 * 1024 * 1024:
                        raise BridgeError("size_limit")
                return bytes(body)

            result = await bridge.async_ingest(
                registration_id,
                read_body,
                owner_id,
                request.headers.get("X-Health-Receiver-Session"),
                request.headers.get("X-Health-Write-Lease"),
                authorized,
            )
            return self.json(result)
        except StoreValidationError as err:
            code = getattr(err, "code", "invalid_request")
            status = (
                401
                if code == "unauthorized"
                else 429
                if code == "busy"
                else 413
                if code == "size_limit"
                else 409
                if code
                in (
                    "session_required",
                    "registration_paused",
                    "revision_conflict",
                    "batch_conflict",
                    "checkpoint_conflict",
                    "sequence_conflict",
                )
                else 400
            )
            response = {"error": code, "retryable": code == "busy"}
            details = getattr(err, "details", None)
            if (
                code == "retained_resolution_required"
                and isinstance(details, dict)
                and set(details) == {"required_resolution", "required_start"}
            ):
                response["details"] = details
            return web.json_response(
                response,
                status=status,
                headers={"Retry-After": "1"} if code == "busy" else None,
            )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/bridge/status",
        vol.Required("registration_id"): str,
    }
)
@websocket_api.async_response
async def ws_bridge_status(hass, connection, msg):
    try:
        result = await runtime(hass).async_status(
            msg["registration_id"],
            connection.user.id,
            partial(connection_auth, hass, connection),
        )
        connection.send_result(msg["id"], result)
    except StoreValidationError as err:
        connection.send_error(
            msg["id"],
            getattr(err, "code", "invalid_request"),
            "Bridge status is unavailable for this account.",
        )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/bridge/admin",
        vol.Required("action"): vol.In(
            ("enroll", "rearm", "revoke", "retire", "remove", "fresh_namespace")
        ),
        vol.Required("parameters"): dict,
    }
)
@websocket_api.async_response
async def ws_bridge_admin(hass, connection, msg):
    authorized = partial(connection_auth, hass, connection, admin=True)
    try:
        authorized()
        bridge = runtime(hass)
        action, parameters = msg["action"], msg["parameters"]
        if action == "rearm":
            exact(parameters, ("owner_id", "state"))
            owner = await hass.auth.async_get_user(
                text(parameters["owner_id"], 128, 128)
            )
            if owner is None or not owner.is_active:
                raise BridgeError("unauthorized")
            result = await bridge.async_rearm(owner.id, parameters["state"], authorized)
        elif action == "enroll":
            exact(parameters, ("owner_id", "metadata", "checkpoint_modes"))
            exact(
                parameters["metadata"],
                ("adapter_kind", "upstream_store", "upstream_scope", "label"),
            )
            owner = await hass.auth.async_get_user(
                text(parameters["owner_id"], 128, 128)
            )
            if owner is None or not owner.is_active:
                raise BridgeError("unauthorized")

            def enroll():
                with bridge.database.transaction():
                    bridge._loop_check(authorized)
                    source = bridge.registry.enroll(
                        parameters["metadata"],
                        owner.id,
                        parameters["checkpoint_modes"],
                        bridge.clock(),
                    )
                    bridge._loop_check(authorized)
                    return source["source_id"]

            source_id = await hass.async_add_executor_job(enroll)
            result = {
                "registration_id": source_id,
                "receiver_session_id": bridge.receiver_session_id,
            }
        else:
            exact(
                parameters,
                ("registration_id", "capture_mode")
                if action == "fresh_namespace"
                else ("registration_id",),
            )
            source_id = parameters["registration_id"]
            await bridge.async_revoke(source_id)

            def change():
                with bridge.database.transaction():
                    bridge._loop_check(authorized)
                    source = bridge.registry.get(source_id)
                    result = {"registration_id": source_id, "paused": True}
                    if action == "retire":
                        bridge.registry.retire(source_id)
                    elif action == "remove":
                        bridge.registry.remove(source_id)
                    elif action == "fresh_namespace":
                        if (
                            parameters["capture_mode"]
                            not in ("forward_only", "backfill")
                            or source["owner_id"] is None
                            or source["origin_mode"] != "local_enrollment"
                        ):
                            raise BridgeError("registration_paused")
                        metadata = {
                            key: source[key]
                            for key in (
                                "adapter_kind",
                                "upstream_store",
                                "upstream_scope",
                                "label",
                            )
                        }
                        replacement = bridge.registry.enroll(
                            metadata,
                            source["owner_id"],
                            bridge.registry.modes(source_id),
                            bridge.clock(),
                            capture_started_at=bridge.clock()
                            if parameters["capture_mode"] == "forward_only"
                            else None,
                        )
                        bridge.registry.retire(source_id)
                        result["registration_id"] = replacement["source_id"]
                    bridge._loop_check(authorized)
                    return result

            result = await hass.async_add_executor_job(change)
        connection.send_result(msg["id"], result)
    except StoreValidationError as err:
        connection.send_error(
            msg["id"],
            getattr(err, "code", "invalid_request"),
            "Bridge activation could not be completed. Keep the producer paused and check its saved state.",
        )


@callback
def async_register_bridge_api(hass):
    if not hass.data.get(f"{DOMAIN}_bridge_registered"):
        hass.http.register_view(BridgeBatchView())
        websocket_api.async_register_command(hass, ws_bridge_status)
        websocket_api.async_register_command(hass, ws_bridge_admin)
        hass.data[f"{DOMAIN}_bridge_registered"] = True
