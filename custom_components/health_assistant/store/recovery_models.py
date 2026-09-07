from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import sleep_models as sparse

METRICS = frozenset(("resting_heart_rate", "hrv_sdnn", "hrv_rmssd", "respiratory_rate"))
CONTEXTS = frozenset(("spot", "sleep_summary", "daily_summary", "unknown"))
PROVENANCE = (
    "source_app",
    "source_device",
    "source_version",
    "bridge_version",
    "source_modified_at",
    "raw_value",
    "raw_unit",
)
PAYLOAD_FIELDS = (
    "value",
    "unit",
    "started_at",
    "ended_at",
    "context",
    "algorithm_id",
    "algorithm_version",
    "start_offset_seconds",
    "end_offset_seconds",
    "start_zone",
    "end_zone",
    "provenance",
)


class RecoveryError(sparse.SleepError):
    def __init__(self, code="invalid_recovery", *, source_id=None):
        super().__init__(code, source_id=source_id)


def checked(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except sparse.SleepError as err:
        raise RecoveryError(
            err.code.replace("sleep", "recovery"), source_id=err.source_id
        ) from err


def text_value(value, maximum=256, *, nullable=False):
    return checked(sparse.text_value, value, maximum, nullable=nullable)


def integer(value, minimum, maximum):
    return checked(sparse.integer, value, minimum, maximum)


def revision64(value):
    return checked(sparse.revision64, value)


def hash256(value):
    return checked(sparse.hash256, value)


def stamp(value):
    return checked(sparse.stamp, value)


def canonical(value, maximum=32768):
    return checked(sparse.canonical, value, maximum)


def metric_value(value):
    if not isinstance(value, str) or value not in METRICS:
        raise RecoveryError("unsupported_method")
    return value


def quantity(metric, value, unit):
    metric_value(metric)
    if type(value) not in (int, float) or not isinstance(unit, str):
        raise RecoveryError()
    canonical_unit = (
        "bpm"
        if metric == "resting_heart_rate"
        else "breaths/min"
        if metric == "respiratory_rate"
        else "ms"
    )
    aliases = {canonical_unit: 1.0}
    aliases.update(
        {"s": 1000.0} if canonical_unit == "ms" else {"count/min": 1.0, "count/s": 60.0}
    )
    if unit not in aliases:
        raise RecoveryError("unsupported_unit")
    try:
        normalized = float(value) * aliases[unit]
    except OverflowError as err:
        raise RecoveryError() from err
    if not math.isfinite(normalized) or normalized <= 0:
        raise RecoveryError()
    return normalized, canonical_unit


def normalize_provenance(value, metric, measurement, unit):
    checked(sparse.fields, value, PROVENANCE)
    checked(sparse.bounded_input, value, 16384)
    result = {key: text_value(value.get(key), nullable=True) for key in PROVENANCE[:4]}
    modified = value.get("source_modified_at")
    result["source_modified_at"] = stamp(modified) if modified is not None else None
    raw_value, raw_unit = value.get("raw_value"), value.get("raw_unit")
    if (raw_value is None) != (raw_unit is None):
        raise RecoveryError()
    if raw_value is not None:
        text_value(raw_unit, 64)
        if quantity(metric, raw_value, raw_unit) != (measurement, unit):
            raise RecoveryError()
        raw_value = float(raw_value)
    result.update(raw_value=raw_value, raw_unit=raw_unit)
    canonical(result, 16384)
    return result


def normalize_payload(value, metric, now):
    checked(
        sparse.fields,
        value,
        PAYLOAD_FIELDS,
        ("value", "unit", "started_at", "ended_at"),
    )
    checked(sparse.bounded_input, value, 32768)
    start, end = stamp(value["started_at"]), stamp(value["ended_at"])
    elapsed = checked(sparse.elapsed_us, start, end)
    if not 0 <= elapsed <= sparse.MAX_SESSION_US or end > stamp(now):
        raise RecoveryError()
    measurement, unit = quantity(metric, value["value"], value["unit"])
    context = value.get("context", "unknown")
    if not isinstance(context, str) or context not in CONTEXTS:
        raise RecoveryError()
    result = {
        "value": measurement,
        "unit": unit,
        "started_at": start,
        "ended_at": end,
        "context": context,
    }
    for key in ("algorithm_id", "algorithm_version"):
        result[key] = text_value(value.get(key), 128, nullable=True)
    for endpoint, timestamp in (("start", start), ("end", end)):
        offset = value.get(f"{endpoint}_offset_seconds")
        if offset is not None:
            integer(offset, -64800, 64800)
        zone = text_value(value.get(f"{endpoint}_zone"), nullable=True)
        if zone is not None:
            try:
                actual = (
                    sparse.instant(timestamp)
                    .astimezone(ZoneInfo(zone))
                    .utcoffset()
                    .total_seconds()
                )
            except (ZoneInfoNotFoundError, ValueError) as err:
                raise RecoveryError() from err
            if offset is not None and actual != offset:
                raise RecoveryError()
        result[f"{endpoint}_offset_seconds"] = offset
        result[f"{endpoint}_zone"] = zone
    result["provenance"] = normalize_provenance(
        value.get("provenance", {}), metric, measurement, unit
    )
    canonical(result)
    return result


@dataclass(frozen=True, slots=True)
class CandidateRecoveryObservation:
    source_id: str
    external_id: str
    source_revision: int
    metric: str
    value: float
    unit: str
    started_at: datetime | str
    ended_at: datetime | str
    person_id: str = "primary"
    context: str = "unknown"
    algorithm_id: str | None = None
    algorithm_version: str | None = None
    start_offset_seconds: int | None = None
    end_offset_seconds: int | None = None
    start_zone: str | None = None
    end_zone: str | None = None
    provenance: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CandidateRecoveryDeletion:
    source_id: str
    external_id: str
    source_revision: int
    metric: str
    person_id: str = "primary"


@dataclass(frozen=True, slots=True)
class RecoveryObservation:
    provider: str
    source_id: str
    external_id: str
    source_revision: int
    payload_hash: str
    payload: dict[str, Any] | None
    metric: str
    person_id: str = "primary"
    locally_excluded: bool = False
    id: int | None = None

    @property
    def source_state(self):
        return "deleted" if self.payload is None else "active"

    @property
    def effective_status(self):
        return (
            "deleted"
            if self.payload is None
            else "excluded"
            if self.locally_excluded
            else "active"
        )


@dataclass(frozen=True, slots=True)
class RecoveryChangeResult:
    observation: RecoveryObservation
    action: str
    changed: bool
    exclusion_changed: bool = False


def normalized_observation(
    provider,
    source_id,
    external_id,
    revision,
    payload,
    now,
    *,
    metric,
    person_id="primary",
    expected_hash=None,
    excluded=False,
):
    identity = {
        key: text_value(value)
        for key, value in {
            "person_id": person_id,
            "provider": provider,
            "source_id": source_id,
            "external_id": external_id,
        }.items()
    }
    if person_id != "primary" or type(excluded) is not bool:
        raise RecoveryError()
    integer(revision, 1, 9223372036854775807)
    metric = metric_value(metric)
    payload = normalize_payload(payload, metric, now) if payload is not None else None
    projection = {
        "hash_scope": "health_assistant.sparse_record",
        "hash_version": 1,
        "domain": "recovery",
        "identity": identity,
        "record_type": metric,
        "operation": "delete" if payload is None else "upsert",
        "payload": payload,
    }
    digest = hashlib.sha256(canonical(projection, 40960)).hexdigest()
    if expected_hash is not None and expected_hash != digest:
        raise RecoveryError("recovery_hash_mismatch")
    return RecoveryObservation(
        provider,
        source_id,
        external_id,
        revision,
        digest,
        payload,
        metric,
        person_id,
        excluded,
    )


def candidate_observation(provider, candidate, now):
    if not isinstance(
        candidate, (CandidateRecoveryObservation, CandidateRecoveryDeletion)
    ):
        raise RecoveryError()
    data = (
        {key: getattr(candidate, key) for key in PAYLOAD_FIELDS}
        if isinstance(candidate, CandidateRecoveryObservation)
        else {}
    )
    try:
        return normalized_observation(
            provider,
            candidate.source_id,
            candidate.external_id,
            candidate.source_revision,
            data if isinstance(candidate, CandidateRecoveryObservation) else None,
            now,
            person_id=candidate.person_id,
            metric=candidate.metric,
        )
    except RecoveryError as err:
        err.source_id = candidate.source_id
        raise
