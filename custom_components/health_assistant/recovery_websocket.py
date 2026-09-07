from __future__ import annotations

from functools import partial

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN
from .signals import SIGNAL_HEALTH_DATA_UPDATED
from .store.recovery import RecoveryRepository
from .store.recovery_models import RecoveryError, integer
from .store.recovery_queries import SERIES_FIELDS, RecoveryQueries, summary


def _id(value):
    try:
        return integer(value, 1, 9223372036854775807)
    except RecoveryError as err:
        raise vol.Invalid("Expected a positive integer") from err


def _entry(hass, connection, msg):
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        connection.send_error(msg["id"], "not_loaded", "Health Assistant is not loaded")
        return None
    return entries[0]


async def _execute(hass, connection, msg, action):
    try:
        result = await hass.async_add_executor_job(action)
    except RecoveryError as err:
        connection.send_error(
            msg["id"],
            err.code,
            "Recovery request could not be completed. Refresh the record and try again.",
        )
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/recovery_observations",
        vol.Required("start"): str,
        vol.Required("end"): str,
        vol.Required("series"): {
            vol.Required(key): vol.Any(str, None)
            if key in ("algorithm_id", "algorithm_version")
            else str
            for key in SERIES_FIELDS
        },
        vol.Optional("excluded", default=False): bool,
        vol.Optional("limit", default=50): vol.All(_id, vol.Range(max=100)),
        vol.Optional("cursor"): str,
    }
)
@websocket_api.async_response
async def ws_recovery_observations(hass, connection, msg):
    entry = _entry(hass, connection, msg)
    if entry is None:
        return
    await _execute(
        hass,
        connection,
        msg,
        partial(
            RecoveryQueries(entry.runtime_data.database).observations,
            msg["start"],
            msg["end"],
            series=msg["series"],
            excluded=msg["excluded"],
            limit=msg["limit"],
            cursor=msg.get("cursor"),
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/recovery_observation",
        vol.Required("record_id"): _id,
    }
)
@websocket_api.async_response
async def ws_recovery_observation(hass, connection, msg):
    entry = _entry(hass, connection, msg)
    if entry is None:
        return
    await _execute(
        hass,
        connection,
        msg,
        partial(
            RecoveryQueries(entry.runtime_data.database).observation,
            msg["record_id"],
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/recovery_observation_exclusion",
        vol.Required("record_id"): _id,
        vol.Required("excluded"): bool,
        vol.Required("expected_source_revision"): str,
        vol.Required("expected_payload_hash"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_recovery_observation_exclusion(hass, connection, msg):
    entry = _entry(hass, connection, msg)
    if entry is None:
        return
    try:
        result = await hass.async_add_executor_job(
            RecoveryRepository(entry.runtime_data.database).set_excluded,
            msg["record_id"],
            msg["excluded"],
            msg["expected_source_revision"],
            msg["expected_payload_hash"],
        )
    except RecoveryError as err:
        connection.send_error(
            msg["id"],
            err.code,
            "Recovery record changed or is unavailable. Refresh it and try again.",
        )
        return
    if result.changed:
        async_dispatcher_send(hass, SIGNAL_HEALTH_DATA_UPDATED)
    connection.send_result(msg["id"], summary(result.observation))


@callback
def async_register_recovery_websocket(hass):
    for command in (
        ws_recovery_observations,
        ws_recovery_observation,
        ws_recovery_observation_exclusion,
    ):
        websocket_api.async_register_command(hass, command)
