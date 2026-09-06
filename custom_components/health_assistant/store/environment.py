from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import Any
from uuid import uuid4

from .db import HealthDatabase
from .errors import StoreValidationError

WINDOW_MS = 300_000
HOUR_MS = 3_600_000
DAY_MS = 86_400_000
HOLD_MS = 900_000
MAX_MAPPINGS = 12
MAX_STREAMS = 256
ENVIRONMENT_UNITS = {"temperature": "°C", "humidity": "%", "co2": "ppm"}


def normalize_environment(metric: str, value: Any, unit: str) -> float:
    if metric not in ENVIRONMENT_UNITS or isinstance(value, bool):
        raise StoreValidationError("Unsupported environmental reading")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as err:
        raise StoreValidationError("Invalid environmental reading") from err
    if not math.isfinite(number):
        raise StoreValidationError("Invalid environmental reading")
    if metric == "temperature":
        if unit == "°F":
            number = (number - 32) * 5 / 9
        elif unit == "K":
            number -= 273.15
        elif unit != "°C":
            raise StoreValidationError("Unsupported environmental unit")
        if number < -273.15:
            raise StoreValidationError("Invalid environmental reading")
    elif unit != ENVIRONMENT_UNITS[metric]:
        raise StoreValidationError("Unsupported environmental unit")
    elif (metric == "humidity" and not 0 <= number <= 100) or number < 0:
        raise StoreValidationError("Invalid environmental reading")
    if not math.isfinite(number * HOLD_MS):
        raise StoreValidationError("Environmental reading is too large")
    return number


@dataclass(slots=True)
class EnvironmentBucket:
    stream_id: int
    start_ms: int
    resolution_s: int = 300
    sample_count: int = 0
    sample_sum: float = 0.0
    minimum: float | None = None
    maximum: float | None = None
    weighted_sum: float = 0.0
    covered_ms: int = 0
    first_report_ms: int | None = None
    last_report_ms: int | None = None
    updated_ms: int = 0

    @property
    def mean(self) -> float | None:
        return self.weighted_sum / self.covered_ms if self.covered_ms else None

    def include(self, value: float) -> None:
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)


class EnvironmentAccumulator:
    def __init__(self, stream_id: int, now_ms: int, initial=None) -> None:
        self.stream_id = stream_id
        self.bucket = initial or EnvironmentBucket(
            stream_id, now_ms // WINDOW_MS * WINDOW_MS
        )
        self.position_ms = max(now_ms, self.bucket.updated_ms)
        self.last_report_ms = self.position_ms - 1
        self.value: float | None = None
        self.expires_ms = self.position_ms

    def advance(self, now_ms: int) -> list[EnvironmentBucket]:
        if now_ms < self.position_ms:
            return []
        closed = []
        while self.position_ms < now_ms:
            end = min(now_ms, self.bucket.start_ms + WINDOW_MS)
            covered_end = min(end, self.expires_ms)
            if self.value is not None and covered_end > self.position_ms:
                duration = covered_end - self.position_ms
                self.bucket.covered_ms += duration
                self.bucket.weighted_sum += self.value * duration
                self.bucket.include(self.value)
                self.bucket.updated_ms = covered_end
            self.position_ms = end
            if end == self.bucket.start_ms + WINDOW_MS:
                if self.bucket.covered_ms or self.bucket.sample_count:
                    closed.append(replace(self.bucket))
                start = end
                if self.value is None or self.expires_ms <= end:
                    start = now_ms // WINDOW_MS * WINDOW_MS
                    self.position_ms = max(self.position_ms, start)
                self.bucket = EnvironmentBucket(self.stream_id, start)
        return closed

    def report(self, now_ms: int, value: float | None) -> list[EnvironmentBucket]:
        if now_ms <= self.last_report_ms or now_ms < self.position_ms:
            return []
        closed = self.advance(now_ms)
        self.last_report_ms = now_ms
        self.value = value
        self.expires_ms = now_ms + HOLD_MS if value is not None else now_ms
        if value is not None:
            self.bucket.sample_count += 1
            self.bucket.sample_sum += value
            self.bucket.include(value)
            if self.bucket.first_report_ms is None:
                self.bucket.first_report_ms = now_ms
            self.bucket.last_report_ms = now_ms
        self.bucket.updated_ms = now_ms
        return closed

    def stop(self, now_ms: int) -> list[EnvironmentBucket]:
        closed = self.advance(now_ms)
        self.value = None
        if self.bucket.covered_ms or self.bucket.sample_count:
            closed.append(replace(self.bucket))
        return closed


class EnvironmentRepository:
    def __init__(self, database: HealthDatabase) -> None:
        self.database = database

    def register(self, mapping: dict) -> dict:
        required = (
            "mapping_id",
            "source_id",
            "entity_id",
            "metric",
            "area_id",
            "area_name",
        )
        if any(
            not isinstance(mapping.get(k), str) or not 0 < len(mapping[k]) <= 128
            for k in required
        ):
            raise StoreValidationError("Invalid environmental mapping")
        if mapping["metric"] not in ENVIRONMENT_UNITS:
            raise StoreValidationError("Unsupported environmental metric")
        identity = tuple(mapping[k] for k in required)
        with self.database.transaction():
            found = self.database.execute(
                "SELECT * FROM environment_streams WHERE mapping_id = ? ORDER BY id DESC LIMIT 1",
                (mapping["mapping_id"],),
            )
            if found and tuple(found[0][k] for k in required) == identity:
                return dict(found[0])
            if (
                self.database.execute("SELECT COUNT(*) FROM environment_streams")[0][0]
                >= MAX_STREAMS
            ):
                raise StoreValidationError("Environmental stream limit reached")
            self.database.execute(
                "INSERT INTO environment_streams (public_id, mapping_id, source_id, entity_id, metric, area_id, area_name, unit) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (str(uuid4()), *identity, ENVIRONMENT_UNITS[mapping["metric"]]),
            )
            return dict(
                self.database.execute(
                    "SELECT * FROM environment_streams WHERE id = last_insert_rowid()"
                )[0]
            )

    def register_all(self, mappings: list[dict]) -> list[dict]:
        if len(mappings) > MAX_MAPPINGS or len(
            {m.get("mapping_id") for m in mappings}
        ) != len(mappings):
            raise StoreValidationError("Environmental mapping limit or duplicate")
        with self.database.transaction():
            return [self.register(mapping) for mapping in mappings]

    def bucket(self, stream_id: int, start_ms: int) -> EnvironmentBucket | None:
        rows = self.database.execute(
            "SELECT * FROM environment_buckets WHERE stream_id = ? AND resolution_s = 300 AND start_ms = ?",
            (stream_id, start_ms),
        )
        return EnvironmentBucket(**dict(rows[0])) if rows else None

    def save(self, buckets: list[EnvironmentBucket], now_ms: int) -> None:
        with self.database.transaction():
            for bucket in buckets:
                if (
                    bucket.resolution_s != 300
                    or bucket.start_ms % WINDOW_MS
                    or bucket.start_ms + WINDOW_MS <= now_ms - 90 * DAY_MS
                ):
                    raise StoreValidationError(
                        "Environmental bucket outside capture tier"
                    )
                if not 0 <= bucket.covered_ms <= WINDOW_MS or not all(
                    math.isfinite(v) for v in (bucket.weighted_sum, bucket.sample_sum)
                ):
                    raise StoreValidationError("Invalid environmental bucket")
                if not self.database.execute(
                    "SELECT 1 FROM environment_streams WHERE id = ?",
                    (bucket.stream_id,),
                ):
                    raise StoreValidationError("Unknown environmental stream")
                self.database.execute(
                    "INSERT INTO environment_buckets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(stream_id, resolution_s, start_ms) DO UPDATE SET sample_count=excluded.sample_count, sample_sum=excluded.sample_sum, minimum=excluded.minimum, maximum=excluded.maximum, weighted_sum=excluded.weighted_sum, covered_ms=excluded.covered_ms, first_report_ms=excluded.first_report_ms, last_report_ms=excluded.last_report_ms, updated_ms=excluded.updated_ms WHERE excluded.updated_ms >= environment_buckets.updated_ms",
                    tuple(asdict(bucket).values()),
                )

    def maintain_batch(self, now_ms: int, limit: int = 128) -> dict:
        if not 1 <= limit <= 512:
            raise StoreValidationError("Invalid maintenance batch")
        cutoff = (now_ms - 90 * DAY_MS) // HOUR_MS * HOUR_MS
        expired = now_ms - 730 * DAY_MS
        with self.database.transaction():
            old = self.database.execute(
                "SELECT stream_id, start_ms, resolution_s FROM environment_buckets WHERE (resolution_s=300 AND start_ms<=?) OR (resolution_s=3600 AND start_ms<=?) LIMIT ?",
                (expired - WINDOW_MS, expired - HOUR_MS, limit * 12),
            )
            for row in old:
                self.database.execute(
                    "DELETE FROM environment_buckets WHERE stream_id=? AND start_ms=? AND resolution_s=?",
                    tuple(row),
                )
            groups = self.database.execute(
                "SELECT stream_id, start_ms FROM environment_buckets WHERE resolution_s=300 AND start_ms < ? ORDER BY start_ms LIMIT ?",
                (cutoff, limit * 12),
            )
            groups = list(
                dict.fromkeys((r[0], r[1] // HOUR_MS * HOUR_MS) for r in groups)
            )[:limit]
            for group in groups:
                stream, hour = group
                rows = self.database.execute(
                    "SELECT * FROM environment_buckets WHERE stream_id=? AND resolution_s=300 AND start_ms>=? AND start_ms<?",
                    (stream, hour, hour + HOUR_MS),
                )
                if self.database.execute(
                    "SELECT 1 FROM environment_buckets WHERE stream_id=? AND resolution_s=3600 AND start_ms=?",
                    (stream, hour),
                ):
                    raise StoreValidationError(
                        "Overlapping environmental retention tiers"
                    )
                summaries = [EnvironmentBucket(**dict(row)) for row in rows]

                def extrema(field, operation, summaries=summaries):
                    values = [
                        getattr(row, field)
                        for row in summaries
                        if getattr(row, field) is not None
                    ]
                    return operation(values) if values else None

                merged = EnvironmentBucket(
                    stream,
                    hour,
                    3600,
                    sum(r.sample_count for r in summaries),
                    sum(r.sample_sum for r in summaries),
                    extrema("minimum", min),
                    extrema("maximum", max),
                    sum(r.weighted_sum for r in summaries),
                    sum(r.covered_ms for r in summaries),
                    extrema("first_report_ms", min),
                    extrema("last_report_ms", max),
                    now_ms,
                )
                self.database.execute(
                    "INSERT INTO environment_buckets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(asdict(merged).values()),
                )
                self.database.execute(
                    "DELETE FROM environment_buckets WHERE stream_id=? AND resolution_s=300 AND start_ms>=? AND start_ms<?",
                    (stream, hour, hour + HOUR_MS),
                )
            return {
                "rolled_up": len(groups),
                "deleted": len(old),
                "more": bool(groups or old),
            }

    def query(
        self,
        area_id: str,
        metric: str,
        start_ms: int,
        end_ms: int,
        limit: int = 1000,
        after: tuple[int, int, int] | None = None,
    ) -> list[dict]:
        if (
            metric not in ENVIRONMENT_UNITS
            or not 1 <= limit <= 5000
            or end_ms <= start_ms
        ):
            raise StoreValidationError("Invalid environmental query")
        cursor = after or (-1, -1, -1)
        rows = self.database.execute(
            "SELECT b.* FROM environment_streams s JOIN environment_buckets b ON b.stream_id=s.id WHERE s.area_id=? AND s.metric=? AND b.resolution_s IN (300, 3600) AND b.start_ms>=? AND b.start_ms<? AND b.start_ms+b.resolution_s*1000>? AND (b.stream_id, b.resolution_s, b.start_ms)>(?, ?, ?) ORDER BY b.stream_id, b.resolution_s, b.start_ms LIMIT ?",
            (area_id, metric, start_ms - HOUR_MS, end_ms, start_ms, *cursor, limit),
        )
        result = []
        for row in rows:
            bucket = EnvironmentBucket(**dict(row))
            result.append(
                {
                    **asdict(bucket),
                    "mean": bucket.mean,
                    "partial_overlap": bucket.start_ms < start_ms
                    or bucket.start_ms + bucket.resolution_s * 1000 > end_ms,
                }
            )
        return result

    def export_streams(self) -> list[dict]:
        return [
            dict(row)
            for row in self.database.execute(
                "SELECT * FROM environment_streams ORDER BY id"
            )
        ]

    def export_buckets(
        self, after: tuple[int, int, int] = (-1, -1, -1), limit: int = 1000
    ) -> list[dict]:
        if not 1 <= limit <= 5000:
            raise StoreValidationError("Invalid export limit")
        return [
            dict(row)
            for row in self.database.execute(
                "SELECT * FROM environment_buckets WHERE (stream_id, resolution_s, start_ms)>(?, ?, ?) ORDER BY stream_id, resolution_s, start_ms LIMIT ?",
                (*after, limit),
            )
        ]
