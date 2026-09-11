from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from uuid import UUID

from . import recovery_models as recovery
from . import sleep_models as sparse
from .errors import StoreValidationError, UnitConversionError
from .models import CANONICAL_UNITS, MetricType
from .units import normalize

DOMAINS = ("scalar", "workout", "sleep", "recovery")
RECORD_FIELDS = (
    "external_id",
    "record_type",
    "source_revision",
    "operation",
    "hash_version",
    "payload_hash",
    "payload",
)
REQUEST_FIELDS = (
    "version",
    "domain",
    "batch_id",
    "hash_version",
    "request_hash",
    "records",
    "checkpoint",
)
SOURCE_FIELDS = (
    "source_id",
    "person_id",
    "adapter_kind",
    "upstream_store",
    "upstream_scope",
    "created_at",
    "label",
)
SCALAR_TYPES = tuple(metric.value for metric in MetricType)


class BridgeError(StoreValidationError):
    def __init__(self, code="invalid_request", *, details=None):
        self.code = code
        self.details = details
        super().__init__(code)


def exact(value, allowed, required=None):
    if (
        not isinstance(value, dict)
        or set(value) - set(allowed)
        or set(allowed if required is None else required) - set(value)
    ):
        raise BridgeError()


def text(value, maximum=256, byte_limit=1024, *, nullable=False, empty=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not empty and not value or len(value) > maximum:
        raise BridgeError()
    try:
        if len(value.encode("utf-8")) > byte_limit:
            raise BridgeError("size_limit")
    except UnicodeError as err:
        raise BridgeError() from err
    return value


def uuid(value):
    if not isinstance(value, str):
        raise BridgeError("invalid_identity")
    try:
        if str(UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError) as err:
        raise BridgeError("invalid_identity") from err
    return value


def provider(source_id):
    return f"bridge:{uuid(source_id)}"


def reserved(value):
    return (
        isinstance(value, str)
        and re.fullmatch(
            r"bridge:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            value,
        )
        is not None
    )


def integer(value, low=0, high=9223372036854775807):
    if type(value) is not int or not low <= value <= high:
        raise BridgeError()
    return value


def counter(value, *, positive=False):
    if not isinstance(value, str) or not re.fullmatch(r"0|[1-9][0-9]{0,18}", value):
        raise BridgeError()
    return integer(int(value), int(positive))


def digest(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise BridgeError("invalid_hash")
    return value


def canonical(value, maximum=8 * 1024 * 1024):
    try:
        return sparse.canonical(value, maximum)
    except sparse.SleepError as err:
        raise BridgeError(
            "size_limit" if "size_limit" in err.code else "invalid_request"
        ) from err


def quantity(value):
    if type(value) not in (float, int):
        raise BridgeError()
    try:
        number = float(value)
    except OverflowError as err:
        raise BridgeError() from err
    if not math.isfinite(number):
        raise BridgeError()
    return 0.0 if number == 0 else number


def timestamp(value):
    try:
        return sparse.stamp(value)
    except sparse.SleepError as err:
        raise BridgeError("invalid_timestamp") from err


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BridgeError("duplicate_field")
        text(key, 256)
        result[key] = value
    return result


def _constant(_value):
    raise BridgeError()


def parse_body(body):
    if not isinstance(body, bytes) or len(body) > 8 * 1024 * 1024:
        raise BridgeError("size_limit")
    try:
        value = body.decode("utf-8")
    except UnicodeError as err:
        raise BridgeError() from err
    depth = 0
    quoted = escaped = False
    string_start = 0
    domain = None
    for index, character in enumerate(value):
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
                if (
                    depth == 1
                    and json.loads(value[string_start - 1 : index + 1]) == "domain"
                ):
                    match = re.match(
                        r'\s*:\s*"(sleep|scalar|workout|recovery|wearable)"',
                        value[index + 1 : index + 64],
                    )
                    if match:
                        domain = match[1]
        elif character == '"':
            quoted = True
            string_start = index + 1
        elif character in "[{":
            depth += 1
            if depth > 12:
                raise BridgeError("size_limit")
        elif character in "]}":
            depth -= 1
    if len(body) > (8 * 1024 * 1024 if domain == "sleep" else 1024 * 1024):
        raise BridgeError("size_limit")
    try:
        result = json.loads(value, object_pairs_hook=_pairs, parse_constant=_constant)
    except (ValueError, RecursionError) as err:
        raise BridgeError() from err
    canonical(result)
    return result


def checkpoint(value, mode):
    if mode == "none":
        if value is not None:
            raise BridgeError("checkpoint_conflict")
        return None
    if mode != "opaque_cas":
        raise BridgeError("checkpoint_conflict")
    exact(value, ("expected_checkpoint_id", "checkpoint_id"))
    result = {}
    for key, handle in value.items():
        if handle is None and key == "expected_checkpoint_id":
            result[key] = None
        elif isinstance(handle, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", handle):
            result[key] = handle
        else:
            raise BridgeError("checkpoint_conflict")
    if result["checkpoint_id"] == result["expected_checkpoint_id"]:
        raise BridgeError("checkpoint_conflict")
    return result


def provenance(value, metric=None, measurement=None, unit=None):
    fields = recovery.PROVENANCE if metric is not None else recovery.PROVENANCE[:5]
    exact(value, fields, ())
    result = {key: text(value.get(key), nullable=True) for key in fields[:4]}
    modified = value.get("source_modified_at")
    result["source_modified_at"] = timestamp(modified) if modified is not None else None
    if metric is not None:
        raw, raw_unit = value.get("raw_value"), value.get("raw_unit")
        if (raw is None) != (raw_unit is None):
            raise BridgeError()
        if raw is not None:
            raw = quantity(raw)
            text(raw_unit, 64)
            try:
                converted = normalize(raw, raw_unit, MetricType(metric))
            except UnitConversionError as err:
                raise BridgeError("unsupported_unit") from err
            if not math.isfinite(converted) or converted != measurement:
                raise BridgeError("raw_quantity_mismatch")
        result.update(raw_value=raw, raw_unit=raw_unit)
    canonical(result, 16384)
    return result


def normalize_payload(domain, record_type, value, now):
    if domain == "sleep":
        if record_type != "sleep_session":
            raise BridgeError("identity_conflict")
        return sparse.normalize_payload(value, now)
    if domain == "recovery":
        return recovery.normalize_payload(value, record_type, now)
    if domain == "scalar":
        if record_type not in SCALAR_TYPES:
            raise BridgeError("unsupported_method")
        exact(value, ("value", "unit", "observed_at", "provenance"))
        number = quantity(value["value"])
        unit = CANONICAL_UNITS[MetricType(record_type)]
        if value["unit"] != unit:
            raise BridgeError("unsupported_unit")
        observed = timestamp(value["observed_at"])
        if observed > timestamp(now):
            raise BridgeError("future_record")
        return {
            "value": number,
            "unit": unit,
            "observed_at": observed,
            "provenance": provenance(value["provenance"], record_type, number, unit),
        }
    if domain != "workout" or record_type != "workout":
        raise BridgeError("unsupported_method")
    exact(
        value,
        (
            "workout_type",
            "title",
            "started_at",
            "ended_at",
            "energy_kcal",
            "distance_m",
            "provenance",
        ),
        ("workout_type", "started_at", "ended_at", "provenance"),
    )
    start, end = timestamp(value["started_at"]), timestamp(value["ended_at"])
    if not start <= end <= timestamp(now):
        raise BridgeError("invalid_window")
    result = {
        "workout_type": text(value["workout_type"], 64),
        "title": text(value.get("title"), nullable=True, empty=True),
        "started_at": start,
        "ended_at": end,
        "provenance": provenance(value["provenance"]),
    }
    for key in ("energy_kcal", "distance_m"):
        result[key] = quantity(value[key]) if value.get(key) is not None else None
    return result


@dataclass(frozen=True, slots=True)
class BridgeRecord:
    source_id: str
    domain: str
    external_id: str
    record_type: str
    source_revision: int
    payload_hash: str
    payload: dict | None

    @property
    def operation(self):
        return "delete" if self.payload is None else "upsert"

    def wire(self):
        return {
            "external_id": self.external_id,
            "record_type": self.record_type,
            "source_revision": str(self.source_revision),
            "operation": self.operation,
            "hash_version": 1,
            "payload_hash": self.payload_hash,
            "payload": self.payload,
        }


def normalize_record(source_id, domain, value, now):
    exact(value, RECORD_FIELDS)
    uuid(source_id)
    external_id = text(value["external_id"])
    record_type = text(value["record_type"])
    valid_type = (
        record_type in SCALAR_TYPES
        if domain == "scalar"
        else record_type == "workout"
        if domain == "workout"
        else record_type == "sleep_session"
        if domain == "sleep"
        else record_type in recovery.METRICS
        if domain == "recovery"
        else False
    )
    if (
        not valid_type
        or type(value["hash_version"]) is not int
        or value["hash_version"] != 1
        or value["operation"] not in ("upsert", "delete")
    ):
        raise BridgeError()
    revision = counter(value["source_revision"], positive=True)
    if (value["operation"] == "delete") != (value["payload"] is None):
        raise BridgeError()
    payload = (
        normalize_payload(domain, record_type, value["payload"], now)
        if value["payload"] is not None
        else None
    )
    canonical(payload, 524288 if domain == "sleep" else 32768)
    projection = {
        "hash_scope": "health_assistant.sparse_record",
        "hash_version": 1,
        "domain": domain,
        "identity": {
            "person_id": "primary",
            "provider": provider(source_id),
            "source_id": source_id,
            "external_id": external_id,
        },
        "record_type": record_type,
        "operation": value["operation"],
        "payload": payload,
    }
    actual = hashlib.sha256(canonical(projection)).hexdigest()
    if digest(value["payload_hash"]) != actual:
        raise BridgeError("hash_mismatch")
    return BridgeRecord(
        source_id, domain, external_id, record_type, revision, actual, payload
    )


@dataclass(frozen=True, slots=True)
class BridgeBatch:
    source_id: str
    domain: str
    batch_id: str
    request_hash: str
    records: tuple[BridgeRecord, ...]
    checkpoint: dict | None

    def wire(self):
        return {
            "version": 1,
            "domain": self.domain,
            "batch_id": self.batch_id,
            "hash_version": 1,
            "request_hash": self.request_hash,
            "records": [record.wire() for record in self.records],
            "checkpoint": self.checkpoint,
        }


def normalize_batch(source_id, value, modes, now):
    exact(value, REQUEST_FIELDS)
    uuid(source_id)
    domain = value["domain"]
    if domain not in DOMAINS or domain not in modes:
        raise BridgeError("domain_not_allowed")
    if (
        type(value["version"]) is not int
        or value["version"] != 1
        or type(value["hash_version"]) is not int
        or value["hash_version"] != 1
    ):
        raise BridgeError()
    batch_id = uuid(value["batch_id"])
    progress = checkpoint(value["checkpoint"], modes[domain])
    records = value["records"]
    if (
        not isinstance(records, list)
        or len(records) > 100
        or not records
        and progress is None
    ):
        raise BridgeError("batch_limit")
    normalized = tuple(
        normalize_record(source_id, domain, record, now) for record in records
    )
    if len({record.external_id for record in normalized}) != len(normalized):
        raise BridgeError("duplicate_identity")
    normalized = tuple(
        sorted(normalized, key=lambda record: record.external_id.encode("utf-16-be"))
    )
    projection = {
        "hash_scope": "health_assistant.sparse_batch",
        "hash_version": 1,
        "registration_id": source_id,
        "domain": domain,
        "batch_id": batch_id,
        "checkpoint": progress,
        "records": [
            {
                key: part
                for key, part in record.wire().items()
                if key not in ("payload", "hash_version")
            }
            for record in normalized
        ],
    }
    actual = hashlib.sha256(canonical(projection)).hexdigest()
    if actual != digest(value["request_hash"]):
        raise BridgeError("hash_mismatch")
    result = BridgeBatch(source_id, domain, batch_id, actual, normalized, progress)
    canonical(result.wire(), 8 * 1024 * 1024 if domain == "sleep" else 1024 * 1024)
    return result


def source_descriptor(value):
    exact(value, SOURCE_FIELDS)
    result = {
        "source_id": uuid(value["source_id"]),
        "person_id": value["person_id"],
        "adapter_kind": text(value["adapter_kind"], 64, 64),
        "upstream_store": value["upstream_store"],
        "upstream_scope": text(value["upstream_scope"], 256, 256),
        "created_at": timestamp(value["created_at"]),
        "label": text(value["label"], 128, 128, empty=True),
    }
    if (
        result["person_id"] != "primary"
        or result["upstream_store"] not in ("apple_health", "health_connect")
        or re.fullmatch(r"[A-Za-z0-9_-]+", result["adapter_kind"]) is None
    ):
        raise BridgeError("invalid_identity")
    return result
