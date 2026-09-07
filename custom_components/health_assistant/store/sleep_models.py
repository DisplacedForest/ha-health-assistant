from __future__ import annotations

import hashlib
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from itertools import pairwise
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import rfc8785

from .errors import StoreValidationError

MAX_SESSION_US = 172_800_000_000
STAGES = frozenset(
    (
        "awake",
        "awake_in_bed",
        "out_of_bed",
        "asleep_unspecified",
        "light",
        "deep",
        "rem",
        "unknown",
    )
)
ASLEEP = frozenset(("light", "deep", "rem", "asleep_unspecified"))
TOTALS = ("asleep", "awake", "light", "deep", "rem", "asleep_unspecified", "in_bed")
PROVENANCE = (
    "source_app",
    "source_device",
    "algorithm",
    "source_version",
    "bridge_version",
    "source_modified_at",
    "native_record_ids",
    "provider_confidence",
)
PAYLOAD_FIELDS = (
    "started_at",
    "ended_at",
    "start_offset_seconds",
    "end_offset_seconds",
    "start_zone",
    "end_zone",
    "reported_totals",
    "stages",
    "in_bed_intervals",
    "provenance",
)


class SleepError(StoreValidationError):
    def __init__(self, code="invalid_sleep", *, source_id=None):
        self.code = code
        self.source_id = source_id
        super().__init__(code)


def text_value(value, maximum=256, *, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise SleepError()
    try:
        value.encode("utf-8")
    except UnicodeError as err:
        raise SleepError() from err
    return value


def hash256(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise SleepError()
    return value


def integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise SleepError()
    return value


def revision64(value):
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", value):
        raise SleepError()
    return integer(int(value), 1, 9223372036854775807)


def instant(value):
    try:
        if isinstance(value, str):
            if not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)",
                value,
            ):
                raise ValueError
            value = datetime.fromisoformat(value)
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError
        return value.astimezone(UTC)
    except (ValueError, TypeError, OverflowError) as err:
        raise SleepError() from err


def stamp(value):
    return instant(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def elapsed_us(start, end):
    delta = instant(end) - instant(start)
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def canonical(value, maximum=524288):
    try:
        data = rfc8785.dumps(value)
    except (ValueError, TypeError, RecursionError, UnicodeError) as err:
        raise SleepError() from err
    if len(data) > maximum:
        raise SleepError("sleep_size_limit")
    return data


def bounded_input(value, maximum=524288):
    pending = [(value, 0)]
    size = 0
    while pending:
        item, depth = pending.pop()
        if depth > 8:
            raise SleepError("sleep_size_limit")
        if isinstance(item, SleepStageInterval):
            pending.append((asdict(item), depth))
        elif isinstance(item, dict):
            if len(item) > 4096:
                raise SleepError("sleep_size_limit")
            pending.extend((part, depth + 1) for pair in item.items() for part in pair)
        elif isinstance(item, (list, tuple)):
            if len(item) > 4096:
                raise SleepError("sleep_size_limit")
            pending.extend((part, depth + 1) for part in item)
        elif isinstance(item, str):
            try:
                size += len(item.encode("utf-8")) + 2
            except UnicodeError as err:
                raise SleepError() from err
        elif (
            isinstance(item, datetime)
            or item is None
            or type(item) in (bool, int, float)
        ):
            size += 1
        else:
            raise SleepError()
        if size > maximum:
            raise SleepError("sleep_size_limit")


def fields(value, allowed, required=()):
    if (
        not isinstance(value, dict)
        or set(value) - set(allowed)
        or set(required) - set(value)
    ):
        raise SleepError()


def normalize_provenance(value):
    fields(value, PROVENANCE)
    bounded_input(value, 65536)
    result = {key: text_value(value.get(key), nullable=True) for key in PROVENANCE[:5]}
    modified = value.get("source_modified_at")
    result["source_modified_at"] = stamp(modified) if modified is not None else None
    ids = value.get("native_record_ids", [])
    if not isinstance(ids, list) or len(ids) > 4096:
        raise SleepError()
    ids = [text_value(item) for item in ids]
    if len(set(ids)) != len(ids):
        raise SleepError()
    result["native_record_ids"] = sorted(ids, key=lambda item: item.encode("utf-16be"))
    confidence = value.get("provider_confidence")
    if confidence is not None:
        fields(confidence, ("value", "scale"), ("value",))
        number = confidence["value"]
        if isinstance(number, str):
            number = text_value(number)
        elif type(number) in (int, float):
            try:
                number = float(number)
            except OverflowError as err:
                raise SleepError() from err
            if not math.isfinite(number):
                raise SleepError()
            number = number or 0.0
        else:
            raise SleepError()
        confidence = {
            "value": number,
            "scale": text_value(confidence.get("scale"), nullable=True),
        }
    result["provider_confidence"] = confidence
    canonical(result, 65536)
    return result


def normalize_intervals(values, start, end, *, context=False):
    if not isinstance(values, list) or len(values) > 4096:
        raise SleepError()
    result = []
    keys = (
        ("start", "end", "source_label")
        if context
        else ("start", "end", "stage", "source_stage")
    )
    for value in values:
        if isinstance(value, SleepStageInterval):
            value = asdict(value)
        fields(value, keys, keys)
        left, right = stamp(value["start"]), stamp(value["end"])
        if not start <= left < right <= end:
            raise SleepError()
        item = {"start": left, "end": right}
        if context:
            item["source_label"] = text_value(value["source_label"], 64)
        else:
            if not isinstance(value["stage"], str) or value["stage"] not in STAGES:
                raise SleepError()
            item["stage"] = value["stage"]
            item["source_stage"] = text_value(value["source_stage"], 64)
        result.append(item)
    result.sort(key=lambda item: tuple(item[key].encode("utf-16be") for key in keys))
    if any(right["start"] < left["end"] for left, right in pairwise(result)):
        raise SleepError()
    return result


def normalize_payload(value, now):
    fields(value, PAYLOAD_FIELDS, ("started_at", "ended_at"))
    bounded_input(value)
    start, end = stamp(value["started_at"]), stamp(value["ended_at"])
    elapsed = elapsed_us(start, end)
    if not 0 < elapsed <= MAX_SESSION_US or instant(end) > instant(now):
        raise SleepError()
    result = {"started_at": start, "ended_at": end}
    for endpoint, timestamp in (("start", start), ("end", end)):
        offset = value.get(f"{endpoint}_offset_seconds")
        if offset is not None:
            integer(offset, -64800, 64800)
        zone = text_value(value.get(f"{endpoint}_zone"), nullable=True)
        if zone is not None:
            try:
                actual = (
                    instant(timestamp)
                    .astimezone(ZoneInfo(zone))
                    .utcoffset()
                    .total_seconds()
                )
            except (ZoneInfoNotFoundError, ValueError) as err:
                raise SleepError() from err
            if offset is not None and actual != offset:
                raise SleepError()
        result[f"{endpoint}_offset_seconds"] = offset
        result[f"{endpoint}_zone"] = zone
    totals = value.get("reported_totals")
    totals = {} if totals is None else totals
    fields(totals, TOTALS)
    totals = {
        key: integer(totals[key], 0, elapsed) if totals.get(key) is not None else None
        for key in TOTALS
    }
    substages = sum(totals[key] or 0 for key in ASLEEP)
    awake = totals["awake"] or 0
    if substages + awake > elapsed or (
        totals["asleep"] is not None
        and (totals["asleep"] + awake > elapsed or substages > totals["asleep"])
    ):
        raise SleepError()
    result["reported_totals"] = totals
    result["stages"] = normalize_intervals(value.get("stages", []), start, end)
    result["in_bed_intervals"] = normalize_intervals(
        value.get("in_bed_intervals", []), start, end, context=True
    )
    result["provenance"] = normalize_provenance(value.get("provenance", {}))
    canonical(result)
    return result


@dataclass(frozen=True, slots=True)
class SleepStageInterval:
    start: datetime | str
    end: datetime | str
    stage: str
    source_stage: str


@dataclass(frozen=True, slots=True)
class CandidateSleepSession:
    source_id: str
    external_id: str
    source_revision: int
    started_at: datetime | str
    ended_at: datetime | str
    person_id: str = "primary"
    start_offset_seconds: int | None = None
    end_offset_seconds: int | None = None
    start_zone: str | None = None
    end_zone: str | None = None
    reported_totals: dict | None = None
    stages: list = field(default_factory=list)
    in_bed_intervals: list = field(default_factory=list)
    provenance: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CandidateSleepDeletion:
    source_id: str
    external_id: str
    source_revision: int
    person_id: str = "primary"


@dataclass(frozen=True, slots=True)
class SleepSession:
    provider: str
    source_id: str
    external_id: str
    source_revision: int
    payload_hash: str
    payload: dict[str, Any] | None
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
class SleepChangeResult:
    session: SleepSession
    action: str
    changed: bool
    exclusion_changed: bool = False


def normalized_session(
    provider,
    source_id,
    external_id,
    revision,
    payload,
    now,
    *,
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
        raise SleepError()
    integer(revision, 1, 9223372036854775807)
    payload = normalize_payload(payload, now) if payload is not None else None
    projection = {
        "hash_scope": "health_assistant.sparse_record",
        "hash_version": 1,
        "domain": "sleep",
        "identity": identity,
        "record_type": "sleep_session",
        "operation": "delete" if payload is None else "upsert",
        "payload": payload,
    }
    digest = hashlib.sha256(canonical(projection, 532480)).hexdigest()
    if expected_hash is not None and expected_hash != digest:
        raise SleepError("sleep_hash_mismatch")
    return SleepSession(
        provider, source_id, external_id, revision, digest, payload, person_id, excluded
    )


def candidate_session(provider, candidate, now):
    if not isinstance(candidate, (CandidateSleepSession, CandidateSleepDeletion)):
        raise SleepError()
    data = (
        {key: getattr(candidate, key) for key in PAYLOAD_FIELDS}
        if isinstance(candidate, CandidateSleepSession)
        else {}
    )
    try:
        return normalized_session(
            provider,
            candidate.source_id,
            candidate.external_id,
            candidate.source_revision,
            data if isinstance(candidate, CandidateSleepSession) else None,
            now,
            person_id=candidate.person_id,
        )
    except SleepError as err:
        err.source_id = candidate.source_id
        raise
