from __future__ import annotations

from uuid import UUID, uuid4

from .bridge_models import (
    DOMAINS,
    SOURCE_FIELDS,
    BridgeError,
    source_descriptor,
    text,
    timestamp,
    uuid,
)


def registry_tables(database):
    present = {
        row[0]
        for row in database.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    return tuple(
        (table, key)
        for table, key in (
            ("environment_streams", "public_id"),
            ("bridge_sources", "source_id"),
            ("wearable_streams", "stream_id"),
        )
        if table in present
    )


def registry_count(database):
    return sum(
        database.execute(f"SELECT COUNT(*) FROM {table}")[0][0]
        for table, _ in registry_tables(database)
    )


def require_registry_slot(database, public_id, *, kind=None):
    for table, key in registry_tables(database):
        if table != kind and database.execute(
            f"SELECT 1 FROM {table} WHERE {key}=?", (public_id,)
        ):
            raise BridgeError("identity_conflict")
    if registry_count(database) >= 256:
        raise BridgeError("registry_capacity")


class BridgeRegistry:
    def __init__(self, database):
        self.database = database

    def get(self, source_id):
        rows = self.database.execute(
            "SELECT * FROM bridge_sources WHERE source_id=?", (uuid(source_id),)
        )
        if not rows:
            raise BridgeError("unknown_registration")
        return dict(rows[0])

    def modes(self, source_id):
        return {
            row["domain"]: row["checkpoint_mode"]
            for row in self.database.execute(
                "SELECT domain,checkpoint_mode FROM bridge_receipts WHERE source_id=?",
                (source_id,),
            )
        }

    def enroll(self, metadata, owner_id, modes, now, *, capture_started_at=None):
        if (
            not isinstance(modes, dict)
            or set(modes) != set(DOMAINS)
            or any(mode not in ("none", "opaque_cas") for mode in modes.values())
        ):
            raise BridgeError("invalid_checkpoint_mode")
        owner_id = text(owner_id, 128, 128)
        source = source_descriptor(
            {
                **metadata,
                "source_id": str(uuid4()),
                "person_id": "primary",
                "created_at": timestamp(now),
            }
        )
        boundary = (
            timestamp(capture_started_at) if capture_started_at is not None else None
        )
        if boundary is not None and boundary > timestamp(now):
            raise BridgeError("invalid_window")
        with self.database.transaction():
            require_registry_slot(self.database, source["source_id"])
            self._insert(source, "local_enrollment", owner_id, boundary)
            for domain in DOMAINS:
                self.database.execute(
                    "INSERT INTO bridge_receipts(source_id,domain,checkpoint_mode) VALUES(?,?,?)",
                    (source["source_id"], domain, modes[domain]),
                )
        return self.get(source["source_id"])

    def _insert(self, source, origin_mode, owner_id=None, boundary=None):
        self.database.execute(
            "INSERT INTO bridge_sources(source_id,person_id,adapter_kind,upstream_store,upstream_scope,created_at,label,origin_mode,owner_id,capture_started_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (*[source[key] for key in SOURCE_FIELDS], origin_mode, owner_id, boundary),
        )

    def import_source(self, descriptor):
        source = source_descriptor(descriptor)
        source_id = source["source_id"]
        with self.database.transaction():
            rows = self.database.execute(
                "SELECT * FROM bridge_sources WHERE source_id=?", (source_id,)
            )
            if rows:
                if any(
                    rows[0][key] != source[key]
                    for key in SOURCE_FIELDS
                    if key != "label"
                ):
                    raise BridgeError("identity_conflict")
                return False
            require_registry_slot(self.database, source_id)
            self._insert(source, "imported_history")
        return True

    def require_live(self, source_id, owner_id):
        source = self.get(source_id)
        if (
            source["owner_id"] != owner_id
            or source["origin_mode"] != "local_enrollment"
            or source["retired"]
            or source["needs_fresh_namespace"]
        ):
            raise BridgeError("registration_paused")
        return source

    def records_present(self, source_id, domain):
        if domain in ("scalar", "workout"):
            return bool(
                self.database.execute(
                    "SELECT 1 FROM bridge_records WHERE source_id=? AND domain=? LIMIT 1",
                    (source_id, domain),
                )
            )
        table = "sleep_sessions" if domain == "sleep" else "recovery_records"
        return bool(
            self.database.execute(
                f"SELECT 1 FROM {table} WHERE provider=? AND source_id=? LIMIT 1",
                (f"bridge:{source_id}", source_id),
            )
        )

    def status(self, source_id):
        source = self.get(source_id)
        domains = []
        for row in self.database.execute(
            "SELECT * FROM bridge_receipts WHERE source_id=? ORDER BY domain",
            (source_id,),
        ):
            domains.append(
                {
                    "domain": row["domain"],
                    "checkpoint_mode": row["checkpoint_mode"],
                    "latest_batch_id": str(UUID(bytes=row["batch_id"]))
                    if row["batch_id"] is not None
                    else None,
                    "latest_request_hash": row["request_hash"].hex()
                    if row["request_hash"] is not None
                    else None,
                    "checkpoint_id": row["checkpoint_id"],
                    "authoritative_records_present": self.records_present(
                        source_id, row["domain"]
                    ),
                }
            )
        return {
            "source_id": source_id,
            "registration_id": source_id,
            "origin_mode": source["origin_mode"],
            "retired": bool(source["retired"]),
            "needs_fresh_namespace": bool(source["needs_fresh_namespace"]),
            "domains": domains,
        }

    def retire(self, source_id):
        self.get(source_id)
        self.database.execute(
            "UPDATE bridge_sources SET retired=1,owner_id=NULL WHERE source_id=?",
            (source_id,),
        )

    def mark_import_changed(self, source_id):
        self.database.execute(
            "UPDATE bridge_sources SET needs_fresh_namespace=1 WHERE source_id=? AND origin_mode='local_enrollment'",
            (source_id,),
        )

    def remove(self, source_id):
        with self.database.transaction():
            source = self.get(source_id)
            if (
                not source["retired"]
                or source["owner_id"] is not None
                or any(self.records_present(source_id, domain) for domain in DOMAINS)
            ):
                raise BridgeError("registration_in_use")
            if any(
                table == "wearable_streams"
                for table, _ in registry_tables(self.database)
            ) and self.database.execute(
                "SELECT 1 FROM wearable_streams WHERE source_id=? LIMIT 1", (source_id,)
            ):
                raise BridgeError("registration_in_use")
            self.database.execute(
                "DELETE FROM bridge_receipts WHERE source_id=?", (source_id,)
            )
            self.database.execute(
                "DELETE FROM bridge_sources WHERE source_id=?", (source_id,)
            )
