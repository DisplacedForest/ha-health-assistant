from __future__ import annotations

from functools import partial

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN
from .signals import SIGNAL_HEALTH_DATA_UPDATED
from .store.sleep import SleepRepository
from .store.sleep_models import SleepError, integer
from .store.sleep_queries import SleepQueries, summary


def _id(value):
    try:
        return integer(value, 1, 9223372036854775807)
    except SleepError as err:
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
    except SleepError as err:
        connection.send_error(
            msg["id"],
            err.code,
            "Sleep request could not be completed. Refresh the record and try again.",
        )
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/sleep_sessions",
        vol.Required("start"): str,
        vol.Required("end"): str,
        vol.Optional("source"): {"provider": str, "source_id": str},
        vol.Optional("date_basis", default="overlap"): vol.In(("overlap", "ended_at")),
        vol.Optional("excluded", default=False): bool,
        vol.Optional("limit", default=50): vol.All(_id, vol.Range(max=100)),
        vol.Optional("cursor"): str,
    }
)
@websocket_api.async_response
async def ws_sleep_sessions(hass, connection, msg):
    entry = _entry(hass, connection, msg)
    if entry is None:
        return
    source = msg.get("source")
    if source is not None and set(source) != {"provider", "source_id"}:
        connection.send_error(
            msg["id"], "invalid_sleep", "Select a provider and source together"
        )
        return
    await _execute(
        hass,
        connection,
        msg,
        partial(
            SleepQueries(entry.runtime_data.database).sessions,
            msg["start"],
            msg["end"],
            source=(source["provider"], source["source_id"])
            if source is not None
            else None,
            date_basis=msg["date_basis"],
            excluded=msg["excluded"],
            limit=msg["limit"],
            cursor=msg.get("cursor"),
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/sleep_session",
        vol.Required("session_id"): _id,
        vol.Optional("kind", default="stages"): vol.In(("stages", "in_bed_intervals")),
        vol.Optional("limit", default=128): vol.All(_id, vol.Range(max=256)),
        vol.Optional("cursor"): str,
    }
)
@websocket_api.async_response
async def ws_sleep_session(hass, connection, msg):
    entry = _entry(hass, connection, msg)
    if entry is None:
        return
    await _execute(
        hass,
        connection,
        msg,
        partial(
            SleepQueries(entry.runtime_data.database).session,
            msg["session_id"],
            kind=msg["kind"],
            limit=msg["limit"],
            cursor=msg.get("cursor"),
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/sleep_session_exclusion",
        vol.Required("session_id"): _id,
        vol.Required("excluded"): bool,
        vol.Required("expected_source_revision"): str,
        vol.Required("expected_payload_hash"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_sleep_session_exclusion(hass, connection, msg):
    entry = _entry(hass, connection, msg)
    if entry is None:
        return
    try:
        result = await hass.async_add_executor_job(
            SleepRepository(entry.runtime_data.database).set_excluded,
            msg["session_id"],
            msg["excluded"],
            msg["expected_source_revision"],
            msg["expected_payload_hash"],
        )
    except SleepError as err:
        connection.send_error(
            msg["id"],
            err.code,
            "Sleep record changed or is unavailable. Refresh it and try again.",
        )
        return
    if result.changed:
        async_dispatcher_send(hass, SIGNAL_HEALTH_DATA_UPDATED)
    connection.send_result(msg["id"], summary(result.session))


@callback
def async_register_sleep_websocket(hass):
    for command in (ws_sleep_sessions, ws_sleep_session, ws_sleep_session_exclusion):
        websocket_api.async_register_command(hass, command)
