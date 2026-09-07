from __future__ import annotations

import math
from datetime import UTC, datetime

from .errors import StoreValidationError
from .interchange_archive import encode_record
from .interchange_formats import LEGACY_FIELDS as FIELDS
from .models import CANONICAL_UNITS, MetricType


def integer(value, minimum=0, maximum=2**63 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise StoreValidationError("Invalid integer field")
    return value


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StoreValidationError("Invalid numeric field")
    try:
        if not math.isfinite(value):
            raise StoreValidationError("Non-finite numeric field")
    except OverflowError as err:
        raise StoreValidationError("Numeric field is too large") from err
    return value


def text(value, allow_empty=False, maximum=None):
    if (
        not isinstance(value, str)
        or (not allow_empty and not value.strip())
        or (maximum is not None and len(value) > maximum)
    ):
        raise StoreValidationError("Invalid text field")
    return value


def timestamp(value):
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError
        return result.astimezone(UTC).isoformat(timespec="microseconds")
    except (ValueError, TypeError, OverflowError) as err:
        raise StoreValidationError("Timestamp must include a valid timezone") from err


def validate_record(domain: str, record: dict) -> dict:
    if set(record) != FIELDS[domain]:
        raise StoreValidationError("Record fields do not match the format")
    encode_record(record)
    result = dict(record)
    if "id" in result:
        integer(result["id"], 1)
    if domain in ("observations", "source_claims", "workouts"):
        for key in ("person_id", "provider", "external_id"):
            text(result[key])
        if result["status"] not in ("active", "excluded"):
            raise StoreValidationError("Invalid record status")
        if not isinstance(result["provenance"], dict):
            raise StoreValidationError("Provenance must be a JSON object")
        result["ingested_at"] = timestamp(result["ingested_at"])
    if domain in ("observations", "source_claims", "metric_priorities"):
        try:
            metric = MetricType(result["metric"])
        except (ValueError, TypeError) as err:
            raise StoreValidationError("Unsupported health metric") from err
        if domain != "metric_priorities":
            if result["unit"] != CANONICAL_UNITS[metric]:
                raise StoreValidationError("Health units must be canonical")
            number(result["value"])
            result["observed_at"] = timestamp(result["observed_at"])
    if domain == "observations":
        integer(result["possible_duplicate"], 0, 1)
    elif domain == "source_claims":
        integer(result["observation_id"], 1)
    elif domain == "workouts":
        text(result["workout_type"])
        if result["title"] is not None:
            text(result["title"], allow_empty=True)
        for key in ("started_at", "ended_at"):
            result[key] = timestamp(result[key])
        if result["ended_at"] < result["started_at"]:
            raise StoreValidationError("Workout ends before it starts")
        for key in ("energy_kcal", "distance_m"):
            if result[key] is not None:
                number(result[key])
    elif domain == "metric_priorities":
        if result["context"] != "":
            raise StoreValidationError("Unsupported priority context")
        integer(result["rank"])
        text(result["provider"])
    elif domain == "environment_streams":
        from .environment import ENVIRONMENT_UNITS

        for key in FIELDS[domain] - {"id"}:
            text(result[key], maximum=128)
        if (
            result["metric"] not in ENVIRONMENT_UNITS
            or result["unit"] != ENVIRONMENT_UNITS[result["metric"]]
        ):
            raise StoreValidationError("Unsupported environmental metric or unit")
        if not result["entity_id"].startswith("sensor."):
            raise StoreValidationError("Invalid environmental entity identity")
    elif domain == "environment_buckets":
        _validate_bucket(result)
    elif domain == "environment_maintenance":
        if result["id"] != 1:
            raise StoreValidationError("Invalid retention state identity")
        for key in ("last_success_ms", "duration_ms"):
            if result[key] is not None:
                integer(result[key])
        for key in ("rolled_up", "deleted"):
            integer(result[key])
        integer(result["failed"], 0, 1)
    return result


def _validate_bucket(record):
    integer(record["stream_id"], 1)
    integer(record["start_ms"], 0, 253402297200000)
    integer(record["sample_count"])
    integer(record["resolution_s"])
    if record["resolution_s"] not in (300, 3600):
        raise StoreValidationError("Unsupported environmental resolution")
    width = record["resolution_s"] * 1000
    start = record["start_ms"]
    end = start + width
    if start % width:
        raise StoreValidationError("Environmental bucket is not UTC aligned")
    integer(record["covered_ms"], 0, width)
    integer(record["updated_ms"], start, end)
    number(record["sample_sum"])
    number(record["weighted_sum"])
    minimum, maximum = record["minimum"], record["maximum"]
    if record["sample_count"] or record["covered_ms"]:
        number(minimum)
        number(maximum)
        if minimum > maximum:
            raise StoreValidationError("Environmental extrema are reversed")
    elif minimum is not None or maximum is not None:
        raise StoreValidationError("Empty environmental buckets cannot have extrema")
    if record["sample_count"]:
        first, last = record["first_report_ms"], record["last_report_ms"]
        integer(first, start, end - 1)
        integer(last, first, end - 1)
    elif (
        record["first_report_ms"] is not None
        or record["last_report_ms"] is not None
        or record["sample_sum"]
    ):
        raise StoreValidationError("Environmental sample bounds do not match the count")
    if not record["covered_ms"] and record["weighted_sum"]:
        raise StoreValidationError(
            "Uncovered environmental buckets cannot have a weighted sum"
        )

    if record["covered_ms"] > record["updated_ms"] - start:
        raise StoreValidationError(
            "Environmental coverage exceeds the recorded time bound"
        )
    if (
        record["last_report_ms"] is not None
        and record["last_report_ms"] > record["updated_ms"]
    ):
        raise StoreValidationError("Environmental report occurs after the update bound")
    for numerator, denominator in (
        ("sample_sum", "sample_count"),
        ("weighted_sum", "covered_ms"),
    ):
        if record[denominator]:
            mean = record[numerator] / record[denominator]
            tolerance = max(abs(minimum), abs(maximum), 1) * 1e-9
            if mean < minimum - tolerance or mean > maximum + tolerance:
                raise StoreValidationError(
                    "Environmental sums fall outside their extrema"
                )
