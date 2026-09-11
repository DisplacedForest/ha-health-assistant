from __future__ import annotations

from functools import partial

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import callback

from .const import DOMAIN
from .store.wearable_models import WearableError
from .store.wearable_queries import WearableQueries


def _limit(value):
    if type(value) is not int or not 1 <= value <= 1000:
        raise vol.Invalid("Expected an integer from 1 to 1000")
    return value


def _resolution(value):
    if value == "auto" or type(value) is int and value in (60, 300, 3600):
        return value
    raise vol.Invalid("Expected auto, 60, 300 or 3600")


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/wearable_series",
        vol.Required("stream_id"): str,
        vol.Required("start"): str,
        vol.Required("end"): str,
        vol.Optional("resolution", default="auto"): _resolution,
        vol.Optional("limit", default=500): _limit,
        vol.Optional("cursor"): str,
    }
)
@websocket_api.async_response
async def ws_wearable_series(hass, connection, msg):
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        connection.send_error(msg["id"], "not_loaded", "Health Assistant is not loaded")
        return
    queries = WearableQueries(entries[0].runtime_data.database)
    try:
        result = await hass.async_add_executor_job(
            partial(
                queries.series,
                **{
                    key: value
                    for key, value in msg.items()
                    if key not in ("id", "type")
                },
            )
        )
    except WearableError as err:
        connection.send_error(
            msg["id"],
            err.code,
            "Wearable history could not be read. Refresh the selection and try again.",
        )
        return
    connection.send_result(msg["id"], result)


@callback
def async_register_wearable_websocket(hass):
    websocket_api.async_register_command(hass, ws_wearable_series)
