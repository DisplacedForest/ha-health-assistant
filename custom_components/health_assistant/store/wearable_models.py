from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import rfc8785

from .errors import StoreValidationError
from .sleep_models import SleepError, instant

MAX_COUNTER = 9223372036854775807
MAX_BODY = 1048576
MAX_OPERATIONS = 1000
RESOLUTIONS = (60, 300, 3600)
WEIGHTINGS = ("sample", "time")
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
DAY_US = 86400000000


class WearableError(StoreValidationError):
    def __init__(self, code="invalid_wearable", **details):
        self.code = code
        self.details = details
        super().__init__(code)


def exact_fields(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise WearableError()


def counter(value, *, positive=False):
    if not isinstance(value, str) or not re.fullmatch(r"0|[1-9][0-9]{0,18}", value):
        raise WearableError()
    result = int(value)
    if not int(positive) <= result <= MAX_COUNTER:
        raise WearableError()
    return result


def uuid_value(value):
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError) as err:
        raise WearableError() from err
    return value


def hash_value(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise WearableError()
    return value


def canonical(value, maximum=MAX_BODY):
    try:
        encoded = rfc8785.dumps(value)
    except (ValueError, TypeError, UnicodeError, RecursionError) as err:
        raise WearableError() from err
    if len(encoded) > maximum:
        raise WearableError("body_too_large")
    return encoded


def time_us(value):
    try:
        delta = instant(value) - EPOCH
    except SleepError as err:
        raise WearableError() from err
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def timestamp(value):
    try:
        return (
            (EPOCH + timedelta(microseconds=value))
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
    except (OverflowError, TypeError) as err:
        raise WearableError() from err


def finite(value):
    if type(value) not in (int, float):
        raise WearableError()
    try:
        value = float(value)
    except OverflowError as err:
        raise WearableError() from err
    if not math.isfinite(value):
        raise WearableError()
    return value


def interval(start_us, resolution):
    if (
        type(resolution) is not int
        or resolution not in RESOLUTIONS
        or type(start_us) is not int
        or start_us % (resolution * 1000000)
    ):
        raise WearableError("invalid_interval")
    timestamp(start_us + resolution * 1000000)


@dataclass(frozen=True, slots=True)
class WearableBucket:
    start_us: int
    resolution_s: int
    weighting: str
    weight: int
    total: float
    minimum: float
    maximum: float

    @property
    def end_us(self):
        return self.start_us + self.resolution_s * 1000000

    @property
    def mean(self):
        return self.total / self.weight

    def validate(self):
        interval(self.start_us, self.resolution_s)
        if self.weighting not in WEIGHTINGS:
            raise WearableError("unsupported_weighting")
        if type(self.weight) is not int or not (
            0 < self.weight <= self.resolution_s * 1000000
        ):
            raise WearableError("invalid_weight")
        total, low, high = map(finite, (self.total, self.minimum, self.maximum))
        if not 1e-9 <= low <= high <= 1e9:
            raise WearableError("invalid_extrema")
        if not 0 < total <= self.weight * (1e9 + 1):
            raise WearableError("invalid_aggregate")
        mean = total / self.weight
        tolerance = (
            1e-12 * (self.resolution_s / 60) * max(1, abs(low), abs(high), abs(mean))
        )
        if low > mean + tolerance or mean > high + tolerance:
            raise WearableError("inconsistent_mean")
        return self

    def wire(self):
        result = {
            "op": "replace",
            "start": timestamp(self.start_us),
            "resolution": self.resolution_s,
            "min": float(self.minimum),
            "max": float(self.maximum),
        }
        if self.weighting == "sample":
            result.update(count=str(self.weight), sum=float(self.total))
        else:
            result.update(
                covered_microseconds=str(self.weight), weighted_sum=float(self.total)
            )
        return result

    def archive(self, stream_id):
        sample = self.weighting == "sample"
        return {
            "stream_id": stream_id,
            "start": timestamp(self.start_us),
            "resolution_s": self.resolution_s,
            "sample_count": str(self.weight) if sample else None,
            "sample_sum": float(self.total) if sample else None,
            "minimum": float(self.minimum),
            "maximum": float(self.maximum),
            "covered_us": None if sample else str(self.weight),
            "weighted_sum": None if sample else float(self.total),
        }


@dataclass(frozen=True, slots=True)
class WearableOperation:
    start_us: int
    resolution_s: int
    bucket: WearableBucket | None = None

    @property
    def end_us(self):
        return self.start_us + self.resolution_s * 1000000

    def wire(self):
        return (
            self.bucket.wire()
            if self.bucket is not None
            else {
                "op": "delete",
                "start": timestamp(self.start_us),
                "resolution": self.resolution_s,
            }
        )


@dataclass(frozen=True, slots=True)
class WearableBatch:
    stream_id: str
    expected_sequence: int
    sequence: int
    content_hash: str
    operations: tuple[WearableOperation, ...]


def normalize_operation(value, weighting):
    base = ("op", "start", "resolution")
    if not isinstance(value, dict) or value.get("op") not in ("replace", "delete"):
        raise WearableError()
    if weighting not in WEIGHTINGS:
        raise WearableError("unsupported_weighting")
    sample = weighting == "sample"
    extras = (
        ("count", "sum", "min", "max")
        if sample
        else ("covered_microseconds", "weighted_sum", "min", "max")
    )
    exact_fields(value, base if value["op"] == "delete" else (*base, *extras))
    if not isinstance(value["start"], str):
        raise WearableError()
    start = time_us(value["start"])
    resolution = value["resolution"]
    interval(start, resolution)
    bucket = None
    if value["op"] == "replace":
        bucket = WearableBucket(
            start,
            resolution,
            weighting,
            counter(
                value["count" if sample else "covered_microseconds"], positive=True
            ),
            finite(value["sum" if sample else "weighted_sum"]),
            finite(value["min"]),
            finite(value["max"]),
        ).validate()
    return WearableOperation(start, resolution, bucket)


def normalize_batch(value, weighting):
    exact_fields(
        value,
        (
            "stream_id",
            "expected_sequence",
            "sequence",
            "hash_version",
            "content_hash",
            "operations",
        ),
    )
    if type(value["hash_version"]) is not int or value["hash_version"] != 1:
        raise WearableError("unsupported_hash_version")
    operations = value["operations"]
    if not isinstance(operations, list) or not 1 <= len(operations) <= MAX_OPERATIONS:
        raise WearableError("operation_limit")
    stream_id = uuid_value(value["stream_id"])
    expected = counter(value["expected_sequence"])
    sequence = counter(value["sequence"], positive=True)
    digest = hash_value(value["content_hash"])
    normalized = tuple(
        sorted(
            (normalize_operation(op, weighting) for op in operations),
            key=lambda op: (op.start_us, op.resolution_s),
        )
    )
    previous = None
    for op in normalized:
        if previous is not None and op.start_us < previous.end_us:
            raise WearableError("overlapping_operations")
        previous = op
    projection = {
        "hash_scope": "health_assistant.wearable_batch",
        "hash_version": 1,
        "stream_id": stream_id,
        "expected_sequence": str(expected),
        "sequence": str(sequence),
        "operations": [op.wire() for op in normalized],
    }
    computed = hashlib.sha256(canonical(projection)).hexdigest()
    if computed != digest:
        raise WearableError("content_hash_mismatch")
    return WearableBatch(stream_id, expected, sequence, digest, normalized)


def rollup(buckets, resolution):
    collected = []
    for bucket in buckets:
        if len(collected) >= 60:
            raise WearableError("invalid_rollup")
        collected.append(bucket)
    buckets = tuple(collected)
    if not buckets or type(resolution) is not int or resolution not in RESOLUTIONS:
        raise WearableError("invalid_rollup")
    first = buckets[0].validate()
    start = first.start_us // (resolution * 1000000) * resolution * 1000000
    end = start + resolution * 1000000
    previous_end = start
    for bucket in buckets:
        bucket.validate()
        if (
            bucket.weighting != first.weighting
            or bucket.resolution_s > resolution
            or bucket.start_us < previous_end
            or bucket.end_us > end
        ):
            raise WearableError("invalid_rollup")
        previous_end = bucket.end_us
    return WearableBucket(
        start,
        resolution,
        first.weighting,
        sum(b.weight for b in buckets),
        math.fsum(b.total for b in buckets),
        min(b.minimum for b in buckets),
        max(b.maximum for b in buckets),
    ).validate()
