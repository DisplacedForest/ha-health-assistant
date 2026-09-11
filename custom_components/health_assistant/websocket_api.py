from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .body import build_body, workout_detail
from .const import DOMAIN
from .coordinator import HealthSummary
from .derived_websocket import async_register_derived_websocket
from .overview import build_overview, reading_payload
from .recovery_websocket import async_register_recovery_websocket
from .signals import SIGNAL_HEALTH_DATA_UPDATED
from .sleep_websocket import async_register_sleep_websocket
from .store import (
    DEFAULT_PERSON_ID,
    HealthObservation,
    MetricType,
    StoreValidationError,
    Workout,
)
from .store.panel_queries import PanelQueries
from .store.reconciliation import rule_for
from .store.units import canonical_unit

MAX_POINTS = 500
ALLOWED_DAYS = (7, 30, 90)


def _observation_payload(
    observation: HealthObservation | None,
) -> dict[str, Any] | None:
    if observation is None:
        return None
    return {
        "id": observation.id,
        "metric": observation.metric.value,
        "excluded": observation.status.value == "excluded",
        "value": observation.value,
        "unit": observation.unit,
        "observed_at": observation.observed_at.isoformat(),
        "provider": observation.provider,
        "source": observation.external_id,
        "sources": list(observation.sources) or [observation.provider],
        "possible_duplicate": observation.possible_duplicate,
    }


def _workout_payload(workout: Workout | None) -> dict[str, Any] | None:
    if workout is None:
        return None
    return {
        "workout_type": workout.workout_type,
        "title": workout.title,
        "started_at": workout.started_at.isoformat(),
        "ended_at": workout.ended_at.isoformat(),
        "duration_seconds": (workout.ended_at - workout.started_at).total_seconds(),
        "energy_kcal": workout.energy_kcal,
        "distance_m": workout.distance_m,
        "provider": workout.provider,
        "source": workout.external_id,
    }


def _summary_payload(summary: HealthSummary) -> dict[str, Any]:
    return {
        "current_weight": _observation_payload(summary.current_weight),
        "current_body_fat": _observation_payload(summary.current_body_fat),
        "steps_today": _observation_payload(summary.steps_today),
        "active_energy_today": _observation_payload(summary.active_energy_today),
        "latest_workout": _workout_payload(summary.latest_workout),
        "workouts_last_7_days": summary.workouts_last_7_days,
    }


def _loaded_entry(hass: HomeAssistant) -> Any | None:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0] if entries else None


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/summary"})
@websocket_api.async_response
async def ws_summary(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    entry = _loaded_entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "Health Assistant is not loaded")
        return
    coordinator = entry.runtime_data.coordinator
    summary = coordinator.data
    if summary is None:
        summary = await hass.async_add_executor_job(coordinator.build_summary)
    connection.send_result(msg["id"], _summary_payload(summary))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/time_series",
        vol.Required("metric"): vol.In([metric.value for metric in MetricType]),
        vol.Optional("days", default=30): vol.In(ALLOWED_DAYS),
    }
)
@websocket_api.async_response
async def ws_time_series(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    entry = _loaded_entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "Health Assistant is not loaded")
        return
    repository = entry.runtime_data.repository
    metric = MetricType(msg["metric"])
    days = msg["days"]
    start = dt_util.utcnow() - timedelta(days=days)
    rows = await hass.async_add_executor_job(
        repository.get_observations, DEFAULT_PERSON_ID, metric, start
    )
    downsampled = len(rows) > MAX_POINTS
    if downsampled:
        stride_indices = sorted(
            {
                round(index * (len(rows) - 1) / (MAX_POINTS - 1))
                for index in range(MAX_POINTS)
            }
        )
        rows = [rows[index] for index in stride_indices]
    connection.send_result(
        msg["id"],
        {
            "metric": metric.value,
            "unit": canonical_unit(metric),
            "days": days,
            "downsampled": downsampled,
            "points": [
                {
                    "id": row.id,
                    "t": row.observed_at.isoformat(),
                    "v": row.value,
                    "provider": row.provider,
                    "source": row.external_id,
                    "possible_duplicate": row.possible_duplicate,
                }
                for row in rows
            ],
        },
    )


def _positive_id(value: Any) -> int:
    if type(value) is not int or not 0 < value <= 9223372036854775807:
        raise vol.Invalid("expected a positive integer")
    return value


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/overview"})
@websocket_api.async_response
async def ws_overview(hass, connection, msg) -> None:
    entry = _loaded_entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "Health Assistant is not loaded")
        return
    data = entry.runtime_data
    result = await hass.async_add_executor_job(
        build_overview, data.database, data.repository
    )
    result["providers"] = [
        {
            "key": key[:120],
            "name": provider.display_name[:120],
            "degraded": data.registry.status(key).degraded,
            "last_success": (
                data.registry.status(key).last_success.isoformat()
                if data.registry.status(key).last_success
                else None
            ),
            "had_error": data.registry.status(key).last_error is not None,
        }
        for key, provider in list(data.registry.providers.items())[:32]
    ]
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/observation_detail",
        vol.Required("observation_id"): _positive_id,
    }
)
@websocket_api.async_response
async def ws_observation_detail(hass, connection, msg) -> None:
    entry = _loaded_entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "Health Assistant is not loaded")
        return

    def detail():
        data = entry.runtime_data
        with data.database.transaction():
            row = data.repository.get_observation(
                DEFAULT_PERSON_ID, msg["observation_id"]
            )
            if row is None:
                return None
            queries = PanelQueries(data.database)
            claims = queries.claims(row.id)
            window = rule_for(row.metric).suspicious_window
            nearby = (
                queries.nearby(row, row.observed_at - window, row.observed_at + window)
                if window
                else []
            )
            for claim in claims:
                claim["selected"] = (
                    claim["provider"] == row.provider
                    and claim["external_id"] == row.external_id
                )
                claim["provider"] = claim["provider"][:120]
                claim["external_id"] = claim["external_id"][:240]
            for candidate in nearby:
                candidate["provider"] = candidate["provider"][:120]
            return {
                "observation": reading_payload(row),
                "metric": row.metric.value,
                "claims": claims,
                "claim_count": claims[0]["total"] if claims else 0,
                "nearby": nearby,
            }

    result = await hass.async_add_executor_job(detail)
    if result is None:
        connection.send_error(
            msg["id"], "not_found", "Observation is no longer available"
        )
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/observations",
        vol.Optional("metric"): vol.In([metric.value for metric in MetricType]),
        vol.Optional("excluded", default=False): bool,
        vol.Optional("limit", default=50): vol.All(_positive_id, vol.Range(max=100)),
        vol.Optional("before_id"): _positive_id,
    }
)
@websocket_api.async_response
async def ws_observations(hass, connection, msg) -> None:
    entry = _loaded_entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "Health Assistant is not loaded")
        return
    metric = MetricType(msg["metric"]) if "metric" in msg else None
    rows = await hass.async_add_executor_job(
        entry.runtime_data.repository.list_observations,
        DEFAULT_PERSON_ID,
        metric,
        msg["excluded"],
        msg["limit"],
        msg.get("before_id"),
    )
    connection.send_result(
        msg["id"],
        {
            "observations": [_observation_payload(row) for row in rows],
            "next_before_id": rows[-1].id if len(rows) == msg["limit"] else None,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/observation_exclusion",
        vol.Required("observation_id"): _positive_id,
        vol.Required("excluded"): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_observation_exclusion(hass, connection, msg) -> None:
    entry = _loaded_entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "Health Assistant is not loaded")
        return
    try:
        observation = await hass.async_add_executor_job(
            entry.runtime_data.repository.set_observation_excluded,
            DEFAULT_PERSON_ID,
            msg["observation_id"],
            msg["excluded"],
        )
    except StoreValidationError:
        connection.send_error(
            msg["id"], "not_found", "Observation is no longer available"
        )
        return
    await entry.runtime_data.coordinator.async_refresh()
    async_dispatcher_send(hass, SIGNAL_HEALTH_DATA_UPDATED)
    connection.send_result(msg["id"], _observation_payload(observation))


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    async_register_derived_websocket(hass)
    async_register_sleep_websocket(hass)
    async_register_recovery_websocket(hass)
    websocket_api.async_register_command(hass, ws_summary)
    websocket_api.async_register_command(hass, ws_time_series)
    websocket_api.async_register_command(hass, ws_observations)
    websocket_api.async_register_command(hass, ws_observation_exclusion)
    websocket_api.async_register_command(hass, ws_overview)
    websocket_api.async_register_command(hass, ws_observation_detail)
    websocket_api.async_register_command(hass, ws_body)
    websocket_api.async_register_command(hass, ws_workout_detail)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/body"})
@websocket_api.async_response
async def ws_body(hass, connection, msg) -> None:
    entry = _loaded_entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "Health Assistant is not loaded")
        return
    result = await hass.async_add_executor_job(build_body, entry.runtime_data.database)
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/workout_detail",
        vol.Required("workout_id"): _positive_id,
    }
)
@websocket_api.async_response
async def ws_workout_detail(hass, connection, msg) -> None:
    entry = _loaded_entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "Health Assistant is not loaded")
        return
    result = await hass.async_add_executor_job(
        workout_detail, entry.runtime_data.database, msg["workout_id"]
    )
    if result is None:
        connection.send_error(msg["id"], "not_found", "Workout is no longer available")
        return
    connection.send_result(msg["id"], result)
