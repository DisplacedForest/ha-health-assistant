from __future__ import annotations

from datetime import UTC, datetime, timedelta

from homeassistant.util import dt as dt_util

from .store import DEFAULT_PERSON_ID, MetricType
from .store.models import DAILY_ACTIVITY_METRICS
from .store.panel_queries import PanelQueries
from .store.units import canonical_unit

THRESHOLDS = {
    MetricType.WEIGHT: 0.5,
    MetricType.BODY_FAT_PERCENTAGE: 0.5,
    MetricType.LEAN_MASS: 0.5,
    MetricType.STEPS: 1000,
    MetricType.DISTANCE: 1000,
    MetricType.ACTIVE_ENERGY: 100,
}


def reading_payload(row):
    if row is None:
        return None
    return {
        "id": row.id,
        "value": row.value,
        "unit": row.unit,
        "observed_at": row.observed_at.isoformat(),
        "provider": row.provider[:120],
        "possible_duplicate": row.possible_duplicate,
        "excluded": row.status.value == "excluded",
    }


def build_overview(database, repository, now=None):
    now = now or dt_util.utcnow()
    queries = PanelQueries(database)
    metrics = []
    local_today = dt_util.as_local(now).date()
    midnight = dt_util.start_of_local_day(local_today)
    with database.transaction():
        for metric in MetricType:
            activity = metric in DAILY_ACTIVITY_METRICS
            current = reading_payload(
                repository.latest_observation(DEFAULT_PERSON_ID, metric, now)
            )
            if current and datetime.fromisoformat(current["observed_at"]) > now:
                current = None
            points = queries.points(metric, now - timedelta(days=14), now)
            comparison = None
            compared = current
            label = "Around a week earlier"
            if activity:
                daily = []
                for offset in range(14, -1, -1):
                    start = dt_util.start_of_local_day(
                        local_today - timedelta(days=offset)
                    )
                    end = dt_util.start_of_local_day(
                        local_today - timedelta(days=offset - 1)
                    )
                    peak = queries.peak(metric, start, min(end, now))
                    if peak:
                        daily.append(peak)
                points = daily
                today = queries.peak(metric, midnight, now)
                current = today or current
                compared = queries.peak(
                    metric,
                    dt_util.start_of_local_day(local_today - timedelta(days=1)),
                    midnight,
                )
                comparison = queries.peak(
                    metric,
                    dt_util.start_of_local_day(local_today - timedelta(days=2)),
                    dt_util.start_of_local_day(local_today - timedelta(days=1)),
                )
                label = "Yesterday vs day before, recorded totals"
            elif current:
                observed = datetime.fromisoformat(current["observed_at"])
                comparison = queries.comparison(
                    metric,
                    observed - timedelta(days=9),
                    observed - timedelta(days=5),
                    observed - timedelta(days=7),
                )
            delta = None
            state = "insufficient"
            if compared and comparison:
                if compared["provider"] != comparison["provider"]:
                    state = "source_changed"
                elif compared.get("possible_duplicate") or comparison.get(
                    "possible_duplicate"
                ):
                    state = "conflict"
                else:
                    delta = compared["value"] - comparison["value"]
                    state = "changed" if abs(delta) >= THRESHOLDS[metric] else "steady"
            if current and current.get("possible_duplicate"):
                state = "conflict"
                delta = None
            elif (
                current
                and compared
                and comparison
                and (
                    current["provider"] != compared["provider"]
                    or (
                        not activity
                        and queries.source_changed(
                            metric,
                            datetime.fromisoformat(comparison["observed_at"]),
                            datetime.fromisoformat(current["observed_at"]),
                            current["provider"],
                        )
                    )
                )
            ):
                state = "source_changed"
                delta = None
            for reading in (current, compared, comparison):
                if reading:
                    reading["provider"] = reading["provider"][:120]
            stale = bool(
                current
                and now - datetime.fromisoformat(current["observed_at"])
                > timedelta(hours=36 if activity else 336)
            )
            metrics.append(
                {
                    "metric": metric.value,
                    "unit": canonical_unit(metric),
                    "current": current,
                    "stale": stale,
                    "state": state,
                    "delta": delta,
                    "comparison_label": label,
                    "comparison": comparison,
                    "compared": compared,
                    "threshold": THRESHOLDS[metric],
                    "points": [
                        {
                            "id": row["id"],
                            "t": row["observed_at"],
                            "v": row["value"],
                            "provider": row["provider"][:120],
                        }
                        for row in points
                    ],
                }
            )
        workouts = queries.workouts(now - timedelta(days=7), now)
    metrics.sort(
        key=lambda item: (
            item["current"] is None,
            item["stale"],
            {"conflict": 0, "source_changed": 1, "changed": 2}.get(item["state"], 3),
            -abs(item["delta"] or 0) / item["threshold"]
            if item["state"] == "changed"
            else 0,
            item["metric"],
        )
    )
    for workout in workouts:
        workout["title"] = (workout["title"] or workout["workout_type"])[:240]
        workout["workout_type"] = workout["workout_type"][:120]
        workout["provider"] = workout["provider"][:120]
        workout["duration_seconds"] = (
            datetime.fromisoformat(workout["ended_at"])
            - datetime.fromisoformat(workout["started_at"])
        ).total_seconds()
    return {
        "generated_at": now.astimezone(UTC).isoformat(),
        "metrics": metrics,
        "workouts": workouts,
        "workout_count": workouts[0]["total"] if workouts else 0,
    }
