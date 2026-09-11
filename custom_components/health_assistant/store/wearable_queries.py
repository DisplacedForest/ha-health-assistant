from __future__ import annotations

import base64
import hashlib
import json

from .wearable import BUCKET_COLUMNS, WearableRepository, bucket_from_row
from .wearable_models import DAY_US, WearableError, canonical, time_us, timestamp
from .wearable_retention import display_buckets


def encode_cursor(value):
    return base64.urlsafe_b64encode(canonical(value, 1024)).decode("ascii")


def decode_cursor(value):
    if not isinstance(value, str) or not 0 < len(value) <= 2048:
        raise WearableError("invalid_cursor")
    try:
        result = json.loads(base64.b64decode(value, altchars=b"-_", validate=True))
        if not isinstance(result, dict) or set(result) != {
            "filter",
            "generation",
            "last",
        }:
            raise ValueError
        if not all(isinstance(result[key], str) for key in result):
            raise ValueError
    except (ValueError, UnicodeError, RecursionError) as err:
        raise WearableError("invalid_cursor") from err
    return result


def point(bucket):
    sample = bucket.weighting == "sample"
    return {
        "start": timestamp(bucket.start_us),
        "end": timestamp(bucket.end_us),
        "resolution_s": bucket.resolution_s,
        "value": bucket.mean,
        "unit": "bpm",
        "minimum": bucket.minimum,
        "maximum": bucket.maximum,
        "sample_count": str(bucket.weight) if sample else None,
        "sample_sum": bucket.total if sample else None,
        "covered_us": None if sample else str(bucket.weight),
        "weighted_sum": None if sample else bucket.total,
    }


class WearableQueries:
    def __init__(self, database):
        self.database = database
        self.repository = WearableRepository(database)

    def series(
        self, stream_id, start, end, *, resolution="auto", limit=500, cursor=None
    ):
        start_us, end_us = time_us(start), time_us(end)
        if not 0 < end_us - start_us <= 730 * DAY_US:
            raise WearableError("invalid_window")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise WearableError("invalid_limit")
        if resolution == "auto":
            target = (
                60
                if end_us - start_us <= 7 * DAY_US
                else (300 if end_us - start_us <= 90 * DAY_US else 3600)
            )
        elif type(resolution) is int and resolution in (60, 300, 3600):
            target = resolution
        else:
            raise WearableError("invalid_resolution")
        fingerprint = hashlib.sha256(
            canonical(
                {
                    "stream_id": stream_id,
                    "start": timestamp(start_us),
                    "end": timestamp(end_us),
                    "resolution": target,
                }
            )
        ).hexdigest()
        after = None
        with self.database.transaction():
            stream = self.repository.get(stream_id)
            generation = self.database.execute(
                "SELECT generation FROM wearable_state WHERE id=1"
            )[0][0]
            if cursor is not None:
                previous = decode_cursor(cursor)
                if previous["filter"] != fingerprint:
                    raise WearableError("invalid_cursor")
                if previous["generation"] != generation:
                    raise WearableError("stale_cursor")
                after = time_us(previous["last"])
            width = target * 1000000
            lower = start_us // 3600000000 * 3600000000
            if after is not None:
                lower = max(lower, after)
            upper = ((end_us + width - 1) // width) * width
            rows = self.database.iterate(
                f"SELECT {BUCKET_COLUMNS} FROM wearable_buckets WHERE stream_id=? AND start_us>=? AND start_us<? ORDER BY start_us",
                (stream["id"], lower, upper),
            )
            buckets = (bucket_from_row(row, stream["weighting"]) for row in rows)
            points = []
            more = False
            try:
                for bucket in display_buckets(buckets, target, start_us, end_us):
                    if after is not None and bucket.start_us <= after:
                        continue
                    if len(points) == limit:
                        more = True
                        break
                    points.append(point(bucket))
            finally:
                rows.close()
            next_cursor = (
                encode_cursor(
                    {
                        "filter": fingerprint,
                        "generation": generation,
                        "last": points[-1]["start"],
                    }
                )
                if more
                else None
            )
            return {
                "stream_id": stream_id,
                "source_id": stream["source_id"],
                "metric": "heart_rate",
                "unit": "bpm",
                "weighting": stream["weighting"],
                "algorithm_id": stream["algorithm_id"],
                "algorithm_version": stream["algorithm_version"],
                "retired": bool(stream["retired"]),
                "degraded": bool(stream["degraded"]),
                "generation": generation,
                "points": points,
                "next_cursor": next_cursor,
            }
