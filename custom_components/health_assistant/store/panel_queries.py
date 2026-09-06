from __future__ import annotations

from datetime import UTC, datetime

from .models import DEFAULT_PERSON_ID, MetricType


def stored_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds")


class PanelQueries:
    def __init__(self, database):
        self.database = database

    def points(self, metric: MetricType, start: datetime, end: datetime):
        rows = self.database.execute(
            """
            WITH ordered AS (
                SELECT id, value, observed_at, provider,
                    row_number() OVER (ORDER BY observed_at, id) - 1 AS n,
                    count(*) OVER () AS total
                FROM observations
                WHERE person_id = ? AND metric = ? AND status = 'active'
                    AND observed_at >= ? AND observed_at <= ?
            )
            SELECT id, value, observed_at, provider, total FROM ordered
            WHERE total <= 120 OR n = total - 1
                OR n % CAST((total + 118) / 119 AS INTEGER) = 0
            ORDER BY observed_at, id
            LIMIT 120
            """,
            (DEFAULT_PERSON_ID, metric.value, stored_time(start), stored_time(end)),
        )
        return [dict(row) for row in rows]

    def peak(self, metric: MetricType, start: datetime, end: datetime):
        rows = self.database.execute(
            """
            SELECT id, value, unit, observed_at, provider, possible_duplicate
            FROM observations
            WHERE person_id = ? AND metric = ? AND status = 'active'
                AND observed_at >= ? AND observed_at < ?
            ORDER BY value DESC, observed_at DESC, id DESC LIMIT 1
            """,
            (DEFAULT_PERSON_ID, metric.value, stored_time(start), stored_time(end)),
        )
        return dict(rows[0]) if rows else None

    def comparison(self, metric, start, end, target):
        rows = self.database.execute(
            """
            SELECT id, value, unit, observed_at, provider, possible_duplicate
            FROM observations
            WHERE person_id = ? AND metric = ? AND status = 'active'
                AND observed_at >= ? AND observed_at <= ?
            ORDER BY abs(julianday(observed_at) - julianday(?)), observed_at DESC, id DESC
            LIMIT 1
            """,
            (
                DEFAULT_PERSON_ID,
                metric.value,
                stored_time(start),
                stored_time(end),
                stored_time(target),
            ),
        )
        return dict(rows[0]) if rows else None

    def workouts(self, start, end):
        rows = self.database.execute(
            """
            SELECT id, workout_type, title, started_at, ended_at, provider,
                energy_kcal, distance_m, count(*) OVER () AS total
            FROM workouts WHERE person_id = ? AND status = 'active'
                AND started_at >= ? AND ended_at <= ?
            ORDER BY started_at DESC, id DESC LIMIT 8
            """,
            (DEFAULT_PERSON_ID, stored_time(start), stored_time(end)),
        )
        return [dict(row) for row in rows]

    def source_changed(self, metric, start, end, provider):
        return bool(
            self.database.execute(
                """
            SELECT 1 FROM observations WHERE person_id = ? AND metric = ?
                AND status = 'active' AND observed_at >= ? AND observed_at <= ?
                AND provider != ? LIMIT 1
            """,
                (
                    DEFAULT_PERSON_ID,
                    metric.value,
                    stored_time(start),
                    stored_time(end),
                    provider,
                ),
            )
        )

    def claims(self, observation_id):
        rows = self.database.execute(
            """
            SELECT id, value, unit, observed_at, provider, external_id, status,
                count(*) OVER () AS total
            FROM source_claims
            WHERE observation_id = ? AND person_id = ?
            ORDER BY provider, observed_at, id LIMIT 50
            """,
            (observation_id, DEFAULT_PERSON_ID),
        )
        return [dict(row) for row in rows]

    def nearby(self, observation, start, end):
        rows = self.database.execute(
            """
            SELECT id, value, unit, observed_at, provider, status
            FROM observations WHERE person_id = ? AND metric = ? AND id != ?
                AND observed_at >= ? AND observed_at <= ? AND status = 'active'
            ORDER BY observed_at, id LIMIT 25
            """,
            (
                DEFAULT_PERSON_ID,
                observation.metric.value,
                observation.id,
                stored_time(start),
                stored_time(end),
            ),
        )
        return [dict(row) for row in rows]
