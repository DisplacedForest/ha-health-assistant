from __future__ import annotations

from functools import partial

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import callback

from .const import DOMAIN
from .store.derived_queries import DerivedError, DerivedQueries


def _limit(value):
    if type(value) is not int or not 1 <= value <= 100:
        raise vol.Invalid("Expected an integer from 1 to 100")
    return value


async def _execute(hass, connection, msg, method, **kwargs):
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        connection.send_error(msg["id"], "not_loaded", "Health Assistant is not loaded")
        return
    runtime = entries[0].runtime_data
    states = {}
    if runtime.bridge is not None:
        for lease in runtime.bridge.leases.values():
            for domain in lease.domains:
                states[("bridge", lease.source_id, domain)] = "armed"
    for key, provider in runtime.registry.providers.items():
        capabilities = provider.capabilities
        if not capabilities.can_import:
            continue
        for metric in capabilities.metrics:
            states[("scalar", key, None, metric.value)] = "active"
        if capabilities.sleep_sessions:
            for source in provider.sleep_source_ids:
                states[("sleep", key, source, None)] = "active"
        for source in provider.recovery_source_ids:
            for metric in capabilities.recovery_metrics:
                states[("recovery", key, source, metric)] = "active"
    queries = DerivedQueries(runtime.database, capture_states=states)
    try:
        result = await hass.async_add_executor_job(
            partial(getattr(queries, method), **kwargs)
        )
    except DerivedError as err:
        connection.send_error(
            msg["id"],
            err.code,
            "Derived request could not be completed. Refresh the selection and try again.",
        )
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/derived_series",
        vol.Required("domain"): vol.In(("scalar", "sleep", "recovery")),
        vol.Required("series_key"): dict,
        vol.Required("end_date"): str,
        vol.Required("days"): vol.In((7, 28, 90)),
        vol.Required("timezone"): str,
    }
)
@websocket_api.async_response
async def ws_derived_series(hass, connection, msg):
    await _execute(
        hass,
        connection,
        msg,
        "series",
        **{
            key: msg[key]
            for key in ("domain", "series_key", "end_date", "days", "timezone")
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/derived_sources",
        vol.Required("domain"): vol.In(("scalar", "sleep", "recovery")),
        vol.Optional("limit", default=50): _limit,
        vol.Optional("cursor"): str,
    }
)
@websocket_api.async_response
async def ws_derived_sources(hass, connection, msg):
    await _execute(
        hass,
        connection,
        msg,
        "sources",
        domain=msg["domain"],
        limit=msg["limit"],
        cursor=msg.get("cursor"),
    )


@callback
def async_register_derived_websocket(hass):
    for command in (ws_derived_series, ws_derived_sources):
        websocket_api.async_register_command(hass, command)
