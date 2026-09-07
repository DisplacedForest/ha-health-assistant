from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime

from .recovery_models import (
    PAYLOAD_FIELDS,
    RecoveryChangeResult,
    RecoveryError,
    RecoveryObservation,
    canonical,
    hash256,
    normalized_observation,
    revision64,
    stamp,
)

JSON_FIELDS = frozenset(("provenance",))
from .interchange_formats import RECOVERY_FIELDS as ARCHIVE_FIELDS


def observation_from_row(row):
    payload = None
    if row["source_state"] == "active":
        payload = {
            key: json.loads(row[key]) if key in JSON_FIELDS else row[key]
            for key in PAYLOAD_FIELDS
        }
    return RecoveryObservation(
        row["provider"],
        row["source_id"],
        row["external_id"],
        row["source_revision"],
        row["payload_hash"],
        payload,
        row["metric"],
        row["person_id"],
        bool(row["locally_excluded"]),
        row["id"],
    )


def observation_columns(observation, now):
    result = {
        "person_id": observation.person_id,
        "metric": observation.metric,
        "provider": observation.provider,
        "source_id": observation.source_id,
        "external_id": observation.external_id,
        "source_revision": observation.source_revision,
        "payload_hash": observation.payload_hash,
        "hash_version": 1,
        "source_state": observation.source_state,
        "locally_excluded": int(observation.locally_excluded),
        "first_ingested_at": stamp(now),
        "last_ingested_at": stamp(now),
    }
    for key in PAYLOAD_FIELDS:
        value = (
            observation.payload[key]
            if observation.payload is not None
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


def archive_observation(observation):
    return {
        "person_id": observation.person_id,
        "provider": observation.provider,
        "source_id": observation.source_id,
        "external_id": observation.external_id,
        "source_revision": str(observation.source_revision),
        "payload_hash": observation.payload_hash,
        "hash_version": 1,
        "record_type": observation.metric,
        "operation": "delete" if observation.payload is None else "upsert",
        "payload": observation.payload,
        "locally_excluded": observation.locally_excluded,
    }


def parse_archive_observation(record, now):
    if (
        set(record) != ARCHIVE_FIELDS
        or type(record["hash_version"]) is not int
        or record["hash_version"] != 1
    ):
        raise RecoveryError()
    if record["operation"] not in ("upsert", "delete") or (
        record["operation"] == "delete"
    ) != (record["payload"] is None):
        raise RecoveryError()
    return normalized_observation(
        record["provider"],
        record["source_id"],
        record["external_id"],
        revision64(record["source_revision"]),
        record["payload"],
        now,
        person_id=record["person_id"],
        metric=record["record_type"],
        expected_hash=hash256(record["payload_hash"]),
        excluded=record["locally_excluded"],
    )


class RecoveryRepository:
    def __init__(self, database, *, clock=None):
        self.database = database
        self.clock = clock or (lambda: datetime.now(UTC))

    def generation(self):
        return self.database.execute(
            "SELECT generation FROM recovery_state WHERE id=1"
        )[0][0]

    def apply_recovery_changes(
        self, changes, checkpoint=None, *, merge_exclusions=False
    ):
        if not isinstance(changes, (list, tuple)) or len(changes) > 100:
            raise RecoveryError("recovery_batch_limit")
        now = self.clock()
        validated = []
        identities = set()
        total = 0
        for change in changes:
            if not isinstance(change, RecoveryObservation):
                raise RecoveryError()
            observation = normalized_observation(
                change.provider,
                change.source_id,
                change.external_id,
                change.source_revision,
                change.payload,
                now,
                person_id=change.person_id,
                metric=change.metric,
                expected_hash=hash256(change.payload_hash),
                excluded=change.locally_excluded,
            )
            if observation.locally_excluded and not merge_exclusions:
                raise RecoveryError()
            identity = (
                observation.provider,
                observation.source_id,
                observation.external_id,
            )
            if identity in identities:
                raise RecoveryError("duplicate_recovery_identity")
            identities.add(identity)
            total += len(canonical(archive_observation(observation), 40960))
            if total > 1024 * 1024:
                raise RecoveryError("recovery_batch_limit")
            validated.append(observation)
        checkpoint_value = None
        if checkpoint is not None:
            if not isinstance(checkpoint, tuple) or len(checkpoint) != 2:
                raise RecoveryError()
            provider, state = checkpoint
            if (
                not isinstance(provider, str)
                or not provider
                or not isinstance(state, dict)
                or any(observation.provider != provider for observation in validated)
            ):
                raise RecoveryError()
            checkpoint_value = (provider, canonical(state, 65536).decode(), stamp(now))
        with self.database.transaction():
            results = [
                self._apply(observation, now, merge_exclusions)
                for observation in validated
            ]
            if checkpoint_value is not None:
                self.database.execute(
                    "INSERT INTO provider_state(provider,state,updated_at) VALUES(?,?,?) ON CONFLICT(provider) DO UPDATE SET state=excluded.state,updated_at=excluded.updated_at",
                    checkpoint_value,
                )
            if any(result.changed for result in results):
                self.database.execute(
                    "UPDATE recovery_state SET generation=generation+1 WHERE id=1"
                )
        return results

    def _apply(self, incoming, now, merge_exclusions):
        rows = self.database.execute(
            "SELECT * FROM recovery_records WHERE provider=? AND source_id=? AND external_id=?",
            (incoming.provider, incoming.source_id, incoming.external_id),
        )
        existing = observation_from_row(rows[0]) if rows else None
        exclusion_changed = False
        if existing:
            if (
                existing.person_id != incoming.person_id
                or existing.metric != incoming.metric
            ):
                raise RecoveryError(
                    "recovery_identity_conflict", source_id=incoming.source_id
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
                    raise RecoveryError(
                        "revision_conflict", source_id=incoming.source_id
                    )
                if exclusion_changed:
                    self.database.execute(
                        "UPDATE recovery_records SET locally_excluded=1 WHERE id=?",
                        (existing.id,),
                    )
                    existing = replace(existing, locally_excluded=True)
                return RecoveryChangeResult(
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
        values = observation_columns(incoming, now)
        columns = list(values)
        updates = [
            key
            for key in columns
            if key not in ("provider", "source_id", "external_id", "first_ingested_at")
        ]
        row = self.database.execute(
            f"INSERT INTO recovery_records({','.join(columns)}) VALUES({','.join('?' for _ in columns)}) ON CONFLICT(provider,source_id,external_id) DO UPDATE SET "
            + ",".join(f"{key}=excluded.{key}" for key in updates)
            + " RETURNING *",
            values.values(),
        )[0]
        return RecoveryChangeResult(
            observation_from_row(row),
            "deleted"
            if incoming.payload is None
            else "update"
            if existing
            else "create",
            True,
            exclusion_changed,
        )

    def set_excluded(self, observation_id, excluded, expected_revision, expected_hash):
        if (
            type(observation_id) is not int
            or not 0 < observation_id <= 9223372036854775807
            or type(excluded) is not bool
        ):
            raise RecoveryError()
        revision = revision64(expected_revision)
        hash256(expected_hash)
        with self.database.transaction():
            rows = self.database.execute(
                "SELECT * FROM recovery_records WHERE person_id='primary' AND id=?",
                (observation_id,),
            )
            if not rows:
                raise RecoveryError("not_found")
            observation = observation_from_row(rows[0])
            if (
                observation.source_revision != revision
                or observation.payload_hash != expected_hash
            ):
                raise RecoveryError("revision_conflict")
            changed = observation.locally_excluded != excluded
            if changed:
                self.database.execute(
                    "UPDATE recovery_records SET locally_excluded=? WHERE id=?",
                    (int(excluded), observation_id),
                )
                self.database.execute(
                    "UPDATE recovery_state SET generation=generation+1 WHERE id=1"
                )
            return RecoveryChangeResult(
                replace(observation, locally_excluded=excluded),
                "exclusion" if changed else "unchanged",
                changed,
                changed,
            )
