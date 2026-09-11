from __future__ import annotations

import json
from datetime import UTC, datetime

from .bridge import BridgeRepository
from .bridge_models import (
    SOURCE_FIELDS,
    BridgeError,
    BridgeRecord,
    canonical,
    exact,
    normalize_record,
    provider,
    reserved,
    source_descriptor,
    timestamp,
)
from .bridge_registry import BridgeRegistry, registry_count, registry_tables
from .interchange_formats import BRIDGE_RECORD_FIELDS
from .models import MetricType


def archive_record(row):
    return {
        key: json.loads(row["payload_json"])
        if row["payload_json"] is not None
        else None
        for key in ("payload",)
    } | {
        key: str(row[key])
        if key == "source_revision"
        else bool(row[key])
        if key == "locally_excluded"
        else row[key]
        for key in BRIDGE_RECORD_FIELDS
        if key != "payload"
    }


def parse_record(record, now):
    exact(record, BRIDGE_RECORD_FIELDS)
    if (
        record["domain"] not in ("scalar", "workout")
        or type(record["locally_excluded"]) is not bool
        or record["source_state"] not in ("active", "deleted")
    ):
        raise BridgeError()
    first, last = (
        timestamp(record["first_ingested_at"]),
        timestamp(record["last_ingested_at"]),
    )
    if not first <= last <= timestamp(now):
        raise BridgeError("invalid_timestamp")
    normalized = normalize_record(
        record["source_id"],
        record["domain"],
        {
            key: record[key]
            for key in (
                "external_id",
                "record_type",
                "source_revision",
                "hash_version",
                "payload_hash",
                "payload",
            )
        }
        | {"operation": "delete" if record["source_state"] == "deleted" else "upsert"},
        now,
    )
    return {key: value for key, value in record.items() if key != "payload"} | {
        "source_revision": normalized.source_revision,
        "locally_excluded": int(record["locally_excluded"]),
        "payload_json": canonical(normalized.payload).decode()
        if normalized.payload is not None
        else None,
        "first_ingested_at": first,
        "last_ingested_at": last,
    }


def ledger_rows(database):
    after = ("", "", "")
    while rows := database.execute(
        "SELECT * FROM bridge_records WHERE (source_id,domain,external_id)>(?,?,?) ORDER BY source_id,domain,external_id LIMIT 100",
        after,
    ):
        yield from rows
        after = tuple(rows[-1][key] for key in ("source_id", "domain", "external_id"))


def record_from_row(row):
    return BridgeRecord(
        row["source_id"],
        row["domain"],
        row["external_id"],
        row["record_type"],
        row["source_revision"],
        row["payload_hash"],
        json.loads(row["payload_json"]) if row["payload_json"] is not None else None,
    )


def descriptor(database, source_id):
    rows = database.execute(
        "SELECT * FROM bridge_sources WHERE source_id=?", (source_id,)
    )
    if not rows:
        raise BridgeError("missing_source_descriptor")
    return {key: rows[0][key] for key in SOURCE_FIELDS}


def validate_target_sources(staging, target, counts):
    for row in staging.iterate("SELECT * FROM bridge_sources ORDER BY source_id"):
        source = {key: row[key] for key in SOURCE_FIELDS}
        existing = target.execute(
            "SELECT * FROM bridge_sources WHERE source_id=?", (row["source_id"],)
        )
        for table, key in registry_tables(target):
            if table != "bridge_sources" and target.execute(
                f"SELECT 1 FROM {table} WHERE {key}=?", (row["source_id"],)
            ):
                raise BridgeError("identity_conflict")
        if existing:
            if any(
                existing[0][key] != source[key]
                for key in SOURCE_FIELDS
                if key != "label"
            ):
                raise BridgeError("identity_conflict")
            summary = counts.setdefault(
                "bridge_sources", {"create": 0, "unchanged": 0, "labels_retained": 0}
            )
            summary["unchanged"] += 1
            summary["labels_retained"] += int(existing[0]["label"] != source["label"])


def sparse_batches(staging, table, maximum):
    batch = []
    size = 0
    for row in staging.iterate(
        f"SELECT * FROM {table} WHERE provider LIKE 'bridge:%' ORDER BY id"
    ):
        if not reserved(row["provider"]):
            continue
        row_size = sum(len(value.encode()) for value in row if isinstance(value, str))
        if batch and (len(batch) == 100 or size + row_size > maximum):
            yield batch
            batch, size = [], 0
        batch.append(row)
        size += row_size
    if batch:
        yield batch


def validate_graph(staging, manifest):
    current = manifest.get("source_schema_version", 0) >= 9
    for table in (
        "source_claims",
        "workouts",
        "sleep_sessions",
        "recovery_records",
        "observations",
    ):
        for row in staging.iterate(
            f"SELECT * FROM {table} WHERE provider LIKE 'bridge:%'"
        ):
            if not reserved(row["provider"]):
                continue
            if not current:
                raise BridgeError("unsupported_namespace")
            source_id = row["provider"][7:]
            source_descriptor(descriptor(staging, source_id))
            if (
                row["person_id"] != "primary"
                or row["provider"] != provider(source_id)
                or table in ("sleep_sessions", "recovery_records")
                and row["source_id"] != source_id
            ):
                raise BridgeError("identity_conflict")
            if table in ("source_claims", "workouts"):
                domain = "scalar" if table == "source_claims" else "workout"
                ledger = staging.execute(
                    "SELECT * FROM bridge_records WHERE source_id=? AND domain=? AND external_id=?",
                    (source_id, domain, row["external_id"]),
                )
                if (
                    not ledger
                    or ledger[0]["source_state"] != "active"
                    or ledger[0]["projection_id"] is not None
                ):
                    raise BridgeError("projection_conflict")
                if timestamp(row["ingested_at"]) != ledger[0]["last_ingested_at"]:
                    raise BridgeError("projection_conflict")
                staging.execute(
                    "UPDATE bridge_records SET projection_id=? WHERE source_id=? AND domain=? AND external_id=?",
                    (row["id"], source_id, domain, row["external_id"]),
                )
    repository = BridgeRepository(staging)
    for row in ledger_rows(staging):
        descriptor(staging, row["source_id"])
        repository._projection(record_from_row(row), row)
    if registry_count(staging) > 256:
        raise BridgeError("registry_capacity")
    tables = registry_tables(staging)
    for index, (left, left_key) in enumerate(tables):
        for right, right_key in tables[index + 1 :]:
            if staging.execute(
                f"SELECT 1 FROM {left} a JOIN {right} b ON a.{left_key}=b.{right_key} LIMIT 1"
            ):
                raise BridgeError("identity_conflict")


def replay_bridge(staging, target, counts, after_batch):
    repository = BridgeRepository(target)
    registry = BridgeRegistry(target)
    batch = []

    def apply_batch():
        with target.transaction():
            affected = set()
            for row in batch:
                source_id = row["source_id"]
                created = registry.import_source(descriptor(staging, source_id))
                if created:
                    counts.setdefault("bridge_sources", {"create": 0, "unchanged": 0})[
                        "create"
                    ] += 1
                record = record_from_row(row)
                previous = target.execute(
                    "SELECT first_ingested_at,last_ingested_at,source_revision FROM bridge_records WHERE source_id=? AND domain=? AND external_id=?",
                    (record.source_id, record.domain, record.external_id),
                )
                last = (
                    max(row["last_ingested_at"], previous[0]["last_ingested_at"])
                    if previous
                    else row["last_ingested_at"]
                )
                action, changed = repository.apply_record(
                    record,
                    datetime.fromisoformat(last),
                    excluded=bool(row["locally_excluded"]),
                    importing=True,
                )
                if (
                    not previous
                    or record.source_revision > previous[0]["source_revision"]
                ):
                    first = (
                        min(row["first_ingested_at"], previous[0]["first_ingested_at"])
                        if previous
                        else row["first_ingested_at"]
                    )
                    target.execute(
                        "UPDATE bridge_records SET first_ingested_at=? WHERE source_id=? AND domain=? AND external_id=?",
                        (first, record.source_id, record.domain, record.external_id),
                    )
                if changed and record.domain == "scalar":
                    affected.add(MetricType(record.record_type))
                counts.setdefault(
                    "bridge_records", {"changed": 0, "unchanged": 0, "stale": 0}
                )[action] += 1
            repository.finish(affected, "scalar", 0)
        if after_batch:
            after_batch("bridge_records")

    for row in ledger_rows(staging):
        batch.append(row)
        if len(batch) == 100:
            apply_batch()
            batch = []
    if batch:
        apply_batch()
    from .recovery import observation_from_row
    from .sleep import session_from_row

    for domain, table, decode in (
        ("sleep", "sleep_sessions", session_from_row),
        ("recovery", "recovery_records", observation_from_row),
    ):
        for rows in sparse_batches(
            staging, table, 7 * 1024 * 1024 if domain == "sleep" else 900 * 1024
        ):
            with target.transaction():
                changed = 0
                for row in rows:
                    if not reserved(row["provider"]):
                        continue
                    source_id = row["source_id"]
                    created = registry.import_source(descriptor(staging, source_id))
                    if created:
                        counts.setdefault(
                            "bridge_sources", {"create": 0, "unchanged": 0}
                        )["create"] += 1
                    sparse = decode(row)
                    record = BridgeRecord(
                        source_id,
                        domain,
                        sparse.external_id,
                        "sleep_session" if domain == "sleep" else sparse.metric,
                        sparse.source_revision,
                        sparse.payload_hash,
                        sparse.payload,
                    )
                    action, updated = repository.apply_record(
                        record,
                        datetime.now(UTC),
                        excluded=sparse.locally_excluded,
                        importing=True,
                    )
                    changed += int(updated)
                    counts.setdefault(
                        table, {"changed": 0, "unchanged": 0, "stale": 0}
                    ).setdefault(action, 0)
                    counts[table][action] += 1
                repository.finish(set(), domain, changed)
            if after_batch:
                after_batch(table)
    unused = sum(
        not target.execute("SELECT 1 FROM bridge_sources WHERE source_id=?", (row[0],))
        for row in staging.iterate(
            "SELECT source_id FROM bridge_sources WHERE source_id NOT IN (SELECT source_id FROM wearable_streams)"
        )
    )
    if unused:
        counts.setdefault("bridge_sources", {"create": 0, "unchanged": 0})[
            "unchanged"
        ] += unused
