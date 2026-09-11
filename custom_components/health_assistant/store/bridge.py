from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from .bridge_models import BridgeError, canonical, normalize_batch, provider, timestamp
from .bridge_registry import BridgeRegistry
from .models import MetricType
from .recovery import RecoveryRepository
from .recovery_models import RecoveryObservation
from .repository import HealthRepository
from .sleep import SleepRepository
from .sleep_models import SleepSession


def stored_time(value):
    return datetime.fromisoformat(value).isoformat(timespec="microseconds")


class BridgeRepository:
    def __init__(self, database):
        self.database = database
        self.registry = BridgeRegistry(database)
        self.health = HealthRepository(database)

    def apply_batch(self, source_id, value, now, check_authorized):
        with self.database.transaction():
            check_authorized()
            source = self.registry.get(source_id)
            batch = normalize_batch(
                source_id, value, self.registry.modes(source_id), now
            )
            receipt = self.database.execute(
                "SELECT * FROM bridge_receipts WHERE source_id=? AND domain=?",
                (source_id, batch.domain),
            )[0]
            batch_id, request_hash = (
                UUID(batch.batch_id).bytes,
                bytes.fromhex(batch.request_hash),
            )
            if receipt["batch_id"] == batch_id:
                if receipt["request_hash"] != request_hash:
                    raise BridgeError("batch_conflict")
                check_authorized()
                return {
                    "replayed": True,
                    "changed": 0,
                    "counts": {
                        key: receipt[key] for key in ("changed", "unchanged", "stale")
                    },
                }
            if (
                batch.checkpoint is not None
                and batch.checkpoint["expected_checkpoint_id"]
                != receipt["checkpoint_id"]
            ):
                raise BridgeError("checkpoint_conflict")
            if source["capture_started_at"] is not None:
                for record in batch.records:
                    if (
                        record.payload is not None
                        and record.payload.get(
                            "observed_at", record.payload.get("started_at")
                        )
                        < source["capture_started_at"]
                    ):
                        raise BridgeError("before_capture_boundary")
            counts = {"changed": 0, "unchanged": 0, "stale": 0}
            affected = set()
            for record in batch.records:
                outcome, changed = self.apply_record(record, now)
                counts[outcome] += 1
                if changed and batch.domain == "scalar":
                    affected.add(MetricType(record.record_type))
            self.finish(affected, batch.domain, counts["changed"])
            self.database.execute(
                "UPDATE bridge_receipts SET batch_id=?,request_hash=?,checkpoint_id=?,changed=?,unchanged=?,stale=? WHERE source_id=? AND domain=?",
                (
                    batch_id,
                    request_hash,
                    batch.checkpoint["checkpoint_id"] if batch.checkpoint else None,
                    counts["changed"],
                    counts["unchanged"],
                    counts["stale"],
                    source_id,
                    batch.domain,
                ),
            )
            check_authorized()
            return {"replayed": False, "changed": counts["changed"], "counts": counts}

    def finish(self, affected, domain, changed):
        for metric in sorted(affected):
            self.health.reconcile_metric("primary", metric, streaming=True)
        if changed and domain in ("sleep", "recovery"):
            self.database.execute(
                f"UPDATE {domain}_state SET generation=generation+1 WHERE id=1"
            )

    def apply_record(self, record, now, *, excluded=False, importing=False):
        if record.domain in ("sleep", "recovery"):
            return self._sparse(record, now, excluded, importing)
        key = (record.source_id, record.domain, record.external_id)
        rows = self.database.execute(
            "SELECT * FROM bridge_records WHERE source_id=? AND domain=? AND external_id=?",
            key,
        )
        existing = rows[0] if rows else None
        if existing is not None and existing["record_type"] != record.record_type:
            raise BridgeError("identity_conflict")
        projection = self._projection(record, existing)
        excluded = bool(existing is not None and existing["locally_excluded"]) or bool(
            importing and excluded
        )
        exclusion_changed = existing is not None and excluded != bool(
            existing["locally_excluded"]
        )
        if (
            existing is not None
            and record.source_revision <= existing["source_revision"]
        ):
            if (
                record.source_revision == existing["source_revision"]
                and record.payload_hash != existing["payload_hash"]
            ):
                raise BridgeError("revision_conflict")
            if exclusion_changed:
                self.database.execute(
                    "UPDATE bridge_records SET locally_excluded=1 WHERE source_id=? AND domain=? AND external_id=?",
                    key,
                )
                if projection is not None:
                    table = "source_claims" if record.domain == "scalar" else "workouts"
                    self.database.execute(
                        f"UPDATE {table} SET status='excluded' WHERE id=?",
                        (projection["id"],),
                    )
            return (
                "stale"
                if record.source_revision < existing["source_revision"]
                else "unchanged",
                exclusion_changed,
            )
        projection_id = self._replace_projection(record, projection, now, excluded)
        self.database.execute(
            """
            INSERT INTO bridge_records(source_id,domain,external_id,record_type,source_revision,hash_version,payload_hash,source_state,locally_excluded,first_ingested_at,last_ingested_at,payload_json,projection_id)
            VALUES(?,?,?,?,?,1,?,?,?,?,?,?,?)
            ON CONFLICT(source_id,domain,external_id) DO UPDATE SET source_revision=excluded.source_revision,payload_hash=excluded.payload_hash,source_state=excluded.source_state,locally_excluded=excluded.locally_excluded,last_ingested_at=excluded.last_ingested_at,payload_json=excluded.payload_json,projection_id=excluded.projection_id
        """,
            (
                *key,
                record.record_type,
                record.source_revision,
                record.payload_hash,
                "deleted" if record.payload is None else "active",
                int(excluded),
                timestamp(now),
                timestamp(now),
                canonical(record.payload).decode()
                if record.payload is not None
                else None,
                projection_id,
            ),
        )
        if importing:
            self.registry.mark_import_changed(record.source_id)
        return "changed", True

    def _projection(self, record, existing):
        table = "source_claims" if record.domain == "scalar" else "workouts"
        rows = self.database.execute(
            f"SELECT * FROM {table} WHERE provider=? AND external_id=?",
            (provider(record.source_id), record.external_id),
        )
        expected = existing is not None and existing["source_state"] == "active"
        if len(rows) != int(expected):
            raise BridgeError("projection_conflict")
        if not expected:
            if existing is not None and existing["projection_id"] is not None:
                raise BridgeError("projection_conflict")
            return None
        row = rows[0]
        if (
            row["id"] != existing["projection_id"]
            or row["person_id"] != "primary"
            or record.domain == "scalar"
            and row["metric"] != record.record_type
            or bool(existing["locally_excluded"]) != (row["status"] == "excluded")
        ):
            raise BridgeError("projection_conflict")
        payload = json.loads(existing["payload_json"])
        actual = {
            key: json.loads(row[key])
            if key == "provenance"
            else timestamp(row[key])
            if key in ("observed_at", "started_at", "ended_at")
            else row[key]
            for key in payload
        }
        if canonical(actual) != canonical(payload):
            raise BridgeError("projection_conflict")
        return row

    def _replace_projection(self, record, existing, now, excluded):
        table = "source_claims" if record.domain == "scalar" else "workouts"
        if record.payload is None:
            if existing is not None:
                self.database.execute(
                    f"DELETE FROM {table} WHERE id=?", (existing["id"],)
                )
            return None
        values = {
            "person_id": "primary",
            "provider": provider(record.source_id),
            "external_id": record.external_id,
            "ingested_at": stored_time(timestamp(now)),
            "status": "excluded" if excluded else "active",
        }
        if record.domain == "scalar":
            values["metric"] = record.record_type
        for key, value in record.payload.items():
            values[key] = (
                canonical(value).decode()
                if key == "provenance"
                else stored_time(value)
                if key in ("observed_at", "started_at", "ended_at")
                else value
            )
        if existing is not None:
            self.database.execute(
                f"UPDATE {table} SET "
                + ",".join(f"{key}=?" for key in values)
                + " WHERE id=?",
                (*values.values(), existing["id"]),
            )
            return existing["id"]
        return self.database.execute(
            f"INSERT INTO {table}({','.join(values)}) VALUES({','.join('?' for _ in values)}) RETURNING id",
            values.values(),
        )[0][0]

    def _sparse(self, record, now, excluded, importing):
        if record.domain == "sleep":
            incoming = SleepSession(
                provider(record.source_id),
                record.source_id,
                record.external_id,
                record.source_revision,
                record.payload_hash,
                record.payload,
                "primary",
                bool(excluded),
            )
            repository = SleepRepository(self.database, clock=lambda: now)
        else:
            incoming = RecoveryObservation(
                provider(record.source_id),
                record.source_id,
                record.external_id,
                record.source_revision,
                record.payload_hash,
                record.payload,
                record.record_type,
                "primary",
                bool(excluded),
            )
            repository = RecoveryRepository(self.database, clock=lambda: now)
        table = "sleep_sessions" if record.domain == "sleep" else "recovery_records"
        before = self.database.execute(
            f"SELECT source_revision FROM {table} WHERE provider=? AND source_id=? AND external_id=?",
            (incoming.provider, record.source_id, record.external_id),
        )
        result = repository._apply(incoming, now, importing)
        if importing and (not before or record.source_revision > before[0][0]):
            self.registry.mark_import_changed(record.source_id)
        return (
            "changed"
            if result.changed
            else "stale"
            if result.action == "stale_revision"
            else "unchanged",
            result.changed,
        )
