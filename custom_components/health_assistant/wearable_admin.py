from __future__ import annotations

from functools import partial

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import callback

from .const import DOMAIN
from .store.bridge_models import BridgeError, exact, text
from .store.bridge_registry import registry_count
from .store.errors import StoreValidationError
from .store.wearable import WearableRepository


def fresh_namespace(
    bridge, repository, source_id, capture_mode, stream_ids, authorized
):
    if capture_mode not in ("forward_only", "backfill"):
        raise BridgeError("invalid_capture_mode")
    if (
        not isinstance(stream_ids, list)
        or len(stream_ids) > 255
        or any(not isinstance(item, str) for item in stream_ids)
        or len(set(stream_ids)) != len(stream_ids)
    ):
        raise BridgeError("invalid_streams")
    with bridge.database.transaction():
        bridge._loop_check(authorized)
        source = bridge.registry.get(source_id)
        if (
            source["origin_mode"] != "local_enrollment"
            or source["owner_id"] is None
            or source["retired"]
        ):
            raise BridgeError("registration_paused")
        selected = [repository.get(stream_id) for stream_id in stream_ids]
        if any(
            stream["source_id"] != source_id
            or stream["origin_mode"] != "local_enrollment"
            or stream["retired"]
            for stream in selected
        ):
            raise BridgeError("registration_paused")
        if registry_count(bridge.database) + 1 + len(selected) > 256:
            raise BridgeError("registry_capacity")
        now = bridge.clock()
        replacement = bridge.registry.enroll(
            {
                key: source[key]
                for key in ("adapter_kind", "upstream_store", "upstream_scope", "label")
            },
            source["owner_id"],
            bridge.registry.modes(source_id),
            now,
            capture_started_at=now if capture_mode == "forward_only" else None,
        )
        replacements = []
        for stream in selected:
            new = repository.enroll(
                replacement["source_id"],
                source["owner_id"],
                weighting=stream["weighting"],
                algorithm_id=stream["algorithm_id"],
                algorithm_version=stream["algorithm_version"],
            )
            replacements.append({"previous_stream_id": stream["stream_id"], **new})
        for stream in bridge.database.execute(
            "SELECT stream_id FROM wearable_streams WHERE source_id=?", (source_id,)
        ):
            repository.retire(stream[0])
        bridge.registry.retire(source_id)
        bridge._loop_check(authorized)
        return {
            "registration_id": replacement["source_id"],
            "streams": replacements,
            "paused": True,
            "capture_mode": capture_mode,
        }


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/wearable/admin",
        vol.Required("action"): vol.In(
            ("enroll", "retire", "remove", "fresh_namespace")
        ),
        vol.Required("parameters"): dict,
    }
)
@websocket_api.async_response
async def ws_wearable_admin(hass, connection, msg):
    from .bridge_api import connection_auth, runtime

    permission = partial(connection_auth, hass, connection, admin=True)
    try:
        permission()
        bridge = runtime(hass)
        owner = None

        def authorized():
            permission()
            if bridge._stopped:
                raise BridgeError("not_loaded")
            if owner is not None and not owner.is_active:
                raise BridgeError("unauthorized")

        repository = WearableRepository(bridge.database)
        parameters = msg["parameters"]
        action = msg["action"]
        if action == "enroll":
            exact(
                parameters,
                (
                    "registration_id",
                    "owner_id",
                    "weighting",
                    "algorithm_id",
                    "algorithm_version",
                ),
            )
            owner = await hass.auth.async_get_user(
                text(parameters["owner_id"], 128, 128)
            )
            if owner is None or not owner.is_active:
                raise BridgeError("unauthorized")

            def enroll():
                with bridge.database.transaction():
                    bridge._loop_check(authorized)
                    result = repository.enroll(
                        parameters["registration_id"],
                        owner.id,
                        **{
                            key: parameters[key]
                            for key in (
                                "weighting",
                                "algorithm_id",
                                "algorithm_version",
                            )
                        },
                    )
                    bridge._loop_check(authorized)
                    return result

            result = await hass.async_add_executor_job(enroll)
        elif action == "fresh_namespace":
            exact(parameters, ("registration_id", "capture_mode", "stream_ids"))
            source_id = parameters["registration_id"]
            source = await hass.async_add_executor_job(bridge.registry.get, source_id)
            if source["owner_id"] is None:
                raise BridgeError("registration_paused")
            owner = await hass.auth.async_get_user(source["owner_id"])
            if owner is None or not owner.is_active:
                raise BridgeError("unauthorized")
            async with bridge.suspend_import([source_id]):
                result = await hass.async_add_executor_job(
                    partial(
                        fresh_namespace,
                        bridge,
                        repository,
                        source_id,
                        parameters["capture_mode"],
                        parameters["stream_ids"],
                        authorized,
                    )
                )
        else:
            exact(parameters, ("stream_id",))
            stream = await hass.async_add_executor_job(
                repository.get, parameters["stream_id"]
            )
            async with bridge.suspend_import([stream["source_id"]]):

                def change():
                    with bridge.database.transaction():
                        bridge._loop_check(authorized)
                        getattr(repository, action)(stream["stream_id"])
                        bridge._loop_check(authorized)
                        return {"stream_id": stream["stream_id"], "paused": True}

                result = await hass.async_add_executor_job(change)
        connection.send_result(msg["id"], result)
    except StoreValidationError as err:
        connection.send_error(
            msg["id"],
            getattr(err, "code", "invalid_request"),
            "Wearable setup could not be completed. Keep the producer paused and check the source settings.",
        )


@callback
def async_register_wearable_admin(hass):
    websocket_api.async_register_command(hass, ws_wearable_admin)
