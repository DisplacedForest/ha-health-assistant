from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime
from typing import Any

from .db import HealthDatabase
from .errors import StoreValidationError
from .models import (
    BODY_MEASUREMENT_METRICS,
    CANONICAL_UNITS,
    DAILY_ACTIVITY_METRICS,
    BodyMeasurement,
    DailyActivity,
    HealthObservation,
    MetricType,
    RecordStatus,
    Workout,
)


def _to_stored_datetime(value: datetime, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise StoreValidationError(f"{name} must be a timezone-aware datetime")
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def _from_stored_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _to_stored_provenance(value: Any) -> str:
    if not isinstance(value, dict):
        raise StoreValidationError("provenance must be a dict")
    try:
        return json.dumps(value, sort_keys=True)
    except (TypeError, ValueError) as err:
        raise StoreValidationError("provenance must be JSON-serializable") from err


def _require_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StoreValidationError(f"{name} must be a non-empty string")
    return value


def _require_finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StoreValidationError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise StoreValidationError(f"{name} must be finite")
    return number


def _require_metric(value: Any) -> MetricType:
    try:
        return MetricType(value)
    except ValueError as err:
        raise StoreValidationError(f"unknown metric {value!r}") from err


class HealthRepository:
    def __init__(self, database: HealthDatabase) -> None:
        self._db = database

    def upsert_observation(self, observation: HealthObservation) -> HealthObservation:
        metric = _require_metric(observation.metric)
        canonical = CANONICAL_UNITS[metric]
        if observation.unit != canonical:
            raise StoreValidationError(
                f"unit {observation.unit!r} is not the canonical unit "
                f"{canonical!r} for {metric}; normalize before storing"
            )
        rows = self._db.execute(
            """
            INSERT INTO observations (
                person_id, metric, value, unit, observed_at,
                provider, external_id, ingested_at, provenance, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (provider, external_id, metric, observed_at)
            DO UPDATE SET
                person_id = excluded.person_id,
                value = excluded.value,
                unit = excluded.unit,
                ingested_at = excluded.ingested_at,
                provenance = excluded.provenance,
                status = excluded.status
            RETURNING *
            """,
            (
                _require_text(observation.person_id, "person_id"),
                metric.value,
                _require_finite(observation.value, "value"),
                canonical,
                _to_stored_datetime(observation.observed_at, "observed_at"),
                _require_text(observation.provider, "provider"),
                _require_text(observation.external_id, "external_id"),
                _to_stored_datetime(observation.ingested_at, "ingested_at"),
                _to_stored_provenance(observation.provenance),
                RecordStatus(observation.status).value,
            ),
        )
        return self._observation_from_row(rows[0])

    def get_observations(
        self,
        person_id: str,
        metric: MetricType | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[HealthObservation]:
        sql = "SELECT * FROM observations WHERE person_id = ?"
        params: list[Any] = [person_id]
        if metric is not None:
            sql += " AND metric = ?"
            params.append(_require_metric(metric).value)
        if start is not None:
            sql += " AND observed_at >= ?"
            params.append(_to_stored_datetime(start, "start"))
        if end is not None:
            sql += " AND observed_at < ?"
            params.append(_to_stored_datetime(end, "end"))
        sql += " ORDER BY observed_at, metric, id"
        return [self._observation_from_row(r) for r in self._db.execute(sql, params)]

    def latest_observation(
        self, person_id: str, metric: MetricType
    ) -> HealthObservation | None:
        rows = self._db.execute(
            """
            SELECT * FROM observations
            WHERE person_id = ? AND metric = ?
            ORDER BY observed_at DESC, id DESC
            LIMIT 1
            """,
            (person_id, _require_metric(metric).value),
        )
        return self._observation_from_row(rows[0]) if rows else None

    def body_measurements(
        self,
        person_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[BodyMeasurement]:
        grouped: dict[datetime, dict[MetricType, float]] = {}
        for metric in sorted(BODY_MEASUREMENT_METRICS):
            for obs in self.get_observations(person_id, metric, start, end):
                grouped.setdefault(obs.observed_at, {})[obs.metric] = obs.value
        return [
            BodyMeasurement(
                person_id=person_id,
                observed_at=observed_at,
                weight_kg=values.get(MetricType.WEIGHT),
                body_fat_percentage=values.get(MetricType.BODY_FAT_PERCENTAGE),
                lean_mass_kg=values.get(MetricType.LEAN_MASS),
            )
            for observed_at, values in sorted(grouped.items())
        ]

    def daily_activity(
        self,
        person_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[DailyActivity]:
        grouped: dict[date, dict[MetricType, float]] = {}
        for metric in sorted(DAILY_ACTIVITY_METRICS):
            for obs in self.get_observations(person_id, metric, start, end):
                day = obs.observed_at.astimezone(UTC).date()
                grouped.setdefault(day, {})[obs.metric] = obs.value
        return [
            DailyActivity(
                person_id=person_id,
                day=day,
                steps=values.get(MetricType.STEPS),
                distance_m=values.get(MetricType.DISTANCE),
                active_energy_kcal=values.get(MetricType.ACTIVE_ENERGY),
            )
            for day, values in sorted(grouped.items())
        ]

    def upsert_workout(self, workout: Workout) -> Workout:
        started_at = _to_stored_datetime(workout.started_at, "started_at")
        ended_at = _to_stored_datetime(workout.ended_at, "ended_at")
        if ended_at < started_at:
            raise StoreValidationError("ended_at must not precede started_at")
        rows = self._db.execute(
            """
            INSERT INTO workouts (
                person_id, provider, external_id, workout_type, title,
                started_at, ended_at, energy_kcal, distance_m,
                ingested_at, provenance, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (provider, external_id)
            DO UPDATE SET
                person_id = excluded.person_id,
                workout_type = excluded.workout_type,
                title = excluded.title,
                started_at = excluded.started_at,
                ended_at = excluded.ended_at,
                energy_kcal = excluded.energy_kcal,
                distance_m = excluded.distance_m,
                ingested_at = excluded.ingested_at,
                provenance = excluded.provenance,
                status = excluded.status
            RETURNING *
            """,
            (
                _require_text(workout.person_id, "person_id"),
                _require_text(workout.provider, "provider"),
                _require_text(workout.external_id, "external_id"),
                _require_text(workout.workout_type, "workout_type"),
                workout.title,
                started_at,
                ended_at,
                None
                if workout.energy_kcal is None
                else _require_finite(workout.energy_kcal, "energy_kcal"),
                None
                if workout.distance_m is None
                else _require_finite(workout.distance_m, "distance_m"),
                _to_stored_datetime(workout.ingested_at, "ingested_at"),
                _to_stored_provenance(workout.provenance),
                RecordStatus(workout.status).value,
            ),
        )
        return self._workout_from_row(rows[0])

    def get_workouts(
        self,
        person_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Workout]:
        sql = "SELECT * FROM workouts WHERE person_id = ?"
        params: list[Any] = [person_id]
        if start is not None:
            sql += " AND started_at >= ?"
            params.append(_to_stored_datetime(start, "start"))
        if end is not None:
            sql += " AND started_at < ?"
            params.append(_to_stored_datetime(end, "end"))
        sql += " ORDER BY started_at, id"
        return [self._workout_from_row(r) for r in self._db.execute(sql, params)]

    def latest_workout(self, person_id: str) -> Workout | None:
        rows = self._db.execute(
            """
            SELECT * FROM workouts
            WHERE person_id = ?
            ORDER BY started_at DESC, id DESC
            LIMIT 1
            """,
            (person_id,),
        )
        return self._workout_from_row(rows[0]) if rows else None

    def get_provider_state(self, provider: str) -> dict[str, Any]:
        rows = self._db.execute(
            "SELECT state FROM provider_state WHERE provider = ?",
            (_require_text(provider, "provider"),),
        )
        if not rows:
            return {}
        state = json.loads(rows[0]["state"])
        if not isinstance(state, dict):
            raise StoreValidationError(
                f"stored state for provider {provider!r} is not a dict"
            )
        return state

    def set_provider_state(self, provider: str, state: dict[str, Any]) -> None:
        if not isinstance(state, dict):
            raise StoreValidationError("provider state must be a dict")
        try:
            stored = json.dumps(state, sort_keys=True)
        except (TypeError, ValueError) as err:
            raise StoreValidationError(
                "provider state must be JSON-serializable"
            ) from err
        self._db.execute(
            """
            INSERT INTO provider_state (provider, state, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT (provider)
            DO UPDATE SET state = excluded.state, updated_at = excluded.updated_at
            """,
            (
                _require_text(provider, "provider"),
                stored,
                datetime.now(UTC).isoformat(timespec="microseconds"),
            ),
        )

    def _observation_from_row(self, row: Any) -> HealthObservation:
        return HealthObservation(
            person_id=row["person_id"],
            metric=MetricType(row["metric"]),
            value=row["value"],
            unit=row["unit"],
            observed_at=_from_stored_datetime(row["observed_at"]),
            provider=row["provider"],
            external_id=row["external_id"],
            ingested_at=_from_stored_datetime(row["ingested_at"]),
            provenance=json.loads(row["provenance"]),
            status=RecordStatus(row["status"]),
            id=row["id"],
        )

    def _workout_from_row(self, row: Any) -> Workout:
        return Workout(
            person_id=row["person_id"],
            provider=row["provider"],
            external_id=row["external_id"],
            workout_type=row["workout_type"],
            title=row["title"],
            started_at=_from_stored_datetime(row["started_at"]),
            ended_at=_from_stored_datetime(row["ended_at"]),
            energy_kcal=row["energy_kcal"],
            distance_m=row["distance_m"],
            ingested_at=_from_stored_datetime(row["ingested_at"]),
            provenance=json.loads(row["provenance"]),
            status=RecordStatus(row["status"]),
            id=row["id"],
        )
