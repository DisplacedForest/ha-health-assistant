from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime

from .sleep_models import (
    PAYLOAD_FIELDS,
    SleepChangeResult,
    SleepError,
    SleepSession,
    canonical,
    hash256,
    normalized_session,
    revision64,
    stamp,
)

JSON_FIELDS = frozenset(("reported_totals", "stages", "in_bed_intervals", "provenance"))
from .interchange_formats import SLEEP_FIELDS as ARCHIVE_FIELDS


def session_from_row(row):
    payload = None
    if row["source_state"] == "active":
        payload = {
            key: json.loads(row[key]) if key in JSON_FIELDS else row[key]
            for key in PAYLOAD_FIELDS
        }
    return SleepSession(
        row["provider"],
        row["source_id"],
        row["external_id"],
        row["source_revision"],
        row["payload_hash"],
        payload,
        row["person_id"],
        bool(row["locally_excluded"]),
        row["id"],
    )


def session_columns(session, now):
    result = {
        "person_id": session.person_id,
        "provider": session.provider,
        "source_id": session.source_id,
        "external_id": session.external_id,
        "source_revision": session.source_revision,
        "payload_hash": session.payload_hash,
        "hash_version": 1,
        "source_state": session.source_state,
        "locally_excluded": int(session.locally_excluded),
        "first_ingested_at": stamp(now),
        "last_ingested_at": stamp(now),
    }
    for key in PAYLOAD_FIELDS:
        value = (
            session.payload[key]
            if session.payload is not None
            else []
            if key in ("stages", "in_bed_intervals")
            else {}
            if key == "provenance"
            else None
        )
        result[key] = (
            canonical(value).decode()
            if key in JSON_FIELDS and value is not None
            else value
        )
    return result


def archive_session(session):
    return {
        "person_id": session.person_id,
        "provider": session.provider,
        "source_id": session.source_id,
        "external_id": session.external_id,
        "source_revision": str(session.source_revision),
        "payload_hash": session.payload_hash,
        "hash_version": 1,
        "record_type": "sleep_session",
        "operation": "delete" if session.payload is None else "upsert",
        "payload": session.payload,
        "locally_excluded": session.locally_excluded,
    }


def parse_archive_session(record, now):
    if (
        set(record) != ARCHIVE_FIELDS
        or type(record["hash_version"]) is not int
        or record["hash_version"] != 1
        or record["record_type"] != "sleep_session"
    ):
        raise SleepError()
    if record["operation"] not in ("upsert", "delete") or (
        record["operation"] == "delete"
    ) != (record["payload"] is None):
        raise SleepError()
    return normalized_session(
        record["provider"],
        record["source_id"],
        record["external_id"],
        revision64(record["source_revision"]),
        record["payload"],
        now,
        person_id=record["person_id"],
        expected_hash=hash256(record["payload_hash"]),
        excluded=record["locally_excluded"],
    )


class SleepRepository:
    def __init__(self, database, *, clock=None):
        self.database = database
        self.clock = clock or (lambda: datetime.now(UTC))

    def generation(self):
        return self.database.execute("SELECT generation FROM sleep_state WHERE id=1")[
            0
        ][0]

    def apply_sleep_changes(self, changes, checkpoint=None, *, merge_exclusions=False):
        if not isinstance(changes, (list, tuple)) or len(changes) > 100:
            raise SleepError("sleep_batch_limit")
        now = self.clock()
        validated = []
        identities = set()
        total = 0
        for change in changes:
            if not isinstance(change, SleepSession):
                raise SleepError()
            session = normalized_session(
                change.provider,
                change.source_id,
                change.external_id,
                change.source_revision,
                change.payload,
                now,
                person_id=change.person_id,
                expected_hash=hash256(change.payload_hash),
                excluded=change.locally_excluded,
            )
            if session.locally_excluded and not merge_exclusions:
                raise SleepError()
            identity = (session.provider, session.source_id, session.external_id)
            if identity in identities:
                raise SleepError("duplicate_sleep_identity")
            identities.add(identity)
            total += len(canonical(archive_session(session), 532480))
            if total > 8 * 1024 * 1024:
                raise SleepError("sleep_batch_limit")
            validated.append(session)
        checkpoint_value = None
        if checkpoint is not None:
            if not isinstance(checkpoint, tuple) or len(checkpoint) != 2:
                raise SleepError()
            provider, state = checkpoint
            if (
                not isinstance(provider, str)
                or not provider
                or not isinstance(state, dict)
                or any(session.provider != provider for session in validated)
            ):
                raise SleepError()
            checkpoint_value = (provider, canonical(state, 65536).decode(), stamp(now))
        with self.database.transaction():
            results = [
                self._apply(session, now, merge_exclusions) for session in validated
            ]
            if checkpoint_value is not None:
                self.database.execute(
                    "INSERT INTO provider_state(provider,state,updated_at) VALUES(?,?,?) ON CONFLICT(provider) DO UPDATE SET state=excluded.state,updated_at=excluded.updated_at",
                    checkpoint_value,
                )
            if any(result.changed for result in results):
                self.database.execute(
                    "UPDATE sleep_state SET generation=generation+1 WHERE id=1"
                )
        return results

    def _apply(self, incoming, now, merge_exclusions):
        rows = self.database.execute(
            "SELECT * FROM sleep_sessions WHERE provider=? AND source_id=? AND external_id=?",
            (incoming.provider, incoming.source_id, incoming.external_id),
        )
        existing = session_from_row(rows[0]) if rows else None
        exclusion_changed = False
        if existing:
            if existing.person_id != incoming.person_id:
                raise SleepError(
                    "sleep_identity_conflict", source_id=incoming.source_id
                )
            exclusion_changed = (
                merge_exclusions
                and incoming.locally_excluded
                and not existing.locally_excluded
            )
            if incoming.source_revision <= existing.source_revision:
                if (
                    incoming.source_revision == existing.source_revision
                    and incoming.payload_hash != existing.payload_hash
                ):
                    raise SleepError("revision_conflict", source_id=incoming.source_id)
                if exclusion_changed:
                    self.database.execute(
                        "UPDATE sleep_sessions SET locally_excluded=1 WHERE id=?",
                        (existing.id,),
                    )
                    existing = replace(existing, locally_excluded=True)
                return SleepChangeResult(
                    existing,
                    "stale_revision"
                    if incoming.source_revision < existing.source_revision
                    else "unchanged",
                    exclusion_changed,
                    exclusion_changed,
                )
            incoming = replace(
                incoming,
                locally_excluded=existing.locally_excluded
                or (merge_exclusions and incoming.locally_excluded),
            )
        values = session_columns(incoming, now)
        columns = list(values)
        updates = [
            key
            for key in columns
            if key not in ("provider", "source_id", "external_id", "first_ingested_at")
        ]
        row = self.database.execute(
            f"INSERT INTO sleep_sessions({','.join(columns)}) VALUES({','.join('?' for _ in columns)}) ON CONFLICT(provider,source_id,external_id) DO UPDATE SET "
            + ",".join(f"{key}=excluded.{key}" for key in updates)
            + " RETURNING *",
            values.values(),
        )[0]
        return SleepChangeResult(
            session_from_row(row),
            "deleted"
            if incoming.payload is None
            else "update"
            if existing
            else "create",
            True,
            exclusion_changed,
        )

    def set_excluded(self, session_id, excluded, expected_revision, expected_hash):
        if (
            type(session_id) is not int
            or not 0 < session_id <= 9223372036854775807
            or type(excluded) is not bool
        ):
            raise SleepError()
        revision = revision64(expected_revision)
        hash256(expected_hash)
        with self.database.transaction():
            rows = self.database.execute(
                "SELECT * FROM sleep_sessions WHERE person_id='primary' AND id=?",
                (session_id,),
            )
            if not rows:
                raise SleepError("not_found")
            session = session_from_row(rows[0])
            if (
                session.source_revision != revision
                or session.payload_hash != expected_hash
            ):
                raise SleepError("revision_conflict")
            changed = session.locally_excluded != excluded
            if changed:
                self.database.execute(
                    "UPDATE sleep_sessions SET locally_excluded=? WHERE id=?",
                    (int(excluded), session_id),
                )
                self.database.execute(
                    "UPDATE sleep_state SET generation=generation+1 WHERE id=1"
                )
            return SleepChangeResult(
                replace(session, locally_excluded=excluded),
                "exclusion" if changed else "unchanged",
                changed,
                changed,
            )
