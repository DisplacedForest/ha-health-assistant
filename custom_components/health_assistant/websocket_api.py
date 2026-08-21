from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import HealthSummary
from .store import (
    DEFAULT_PERSON_ID,
    HealthObservation,
    MetricType,
    Workout,
)
from .store.units import canonical_unit

MAX_POINTS = 500
ALLOWED_DAYS = (7, 30, 90)


def _observation_payload(
    observation: HealthObservation | None,
) -> dict[str, Any] | None:
    if observation is None:
        return None
    return {
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


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_summary)
    websocket_api.async_register_command(hass, ws_time_series)
