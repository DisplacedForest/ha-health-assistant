from __future__ import annotations

import json

from .bridge_models import SOURCE_FIELDS
from .bridge_registry import require_registry_slot
from .wearable import BUCKET_COLUMNS, WearableRepository, bucket_from_row, bucket_values
from .wearable_models import WearableError, exact_fields, time_us, uuid_value
from .wearable_snapshot import (
    BUCKET_FIELDS,
    IDENTITY_FIELDS,
    SnapshotValidator,
    normalize_descriptor,
    snapshot_hash,
)


def prepare_staging(database):
    database.execute(
        "CREATE TABLE wearable_archive_descriptors(stream_id TEXT PRIMARY KEY,descriptor TEXT NOT NULL) WITHOUT ROWID"
    )
    database.execute(
        "CREATE TABLE wearable_archive_rows(stream_id TEXT NOT NULL,start_us INTEGER NOT NULL,record TEXT NOT NULL,PRIMARY KEY(stream_id,start_us)) WITHOUT ROWID"
    )


def stage_record(database, domain, record):
    if domain == "wearable_streams":
        normalized = normalize_descriptor(record)
        database.execute(
            "INSERT INTO wearable_archive_descriptors VALUES(?,?)",
            (normalized["stream_id"], json.dumps(normalized, allow_nan=False)),
        )
    else:
        exact_fields(record, BUCKET_FIELDS)
        database.execute(
            "INSERT INTO wearable_archive_rows VALUES(?,?,?)",
            (
                uuid_value(record["stream_id"]),
                time_us(record["start"]),
                json.dumps(record, allow_nan=False),
            ),
        )


def finalize_staging(database, now):
    if database.execute(
        "SELECT 1 FROM wearable_archive_rows r LEFT JOIN wearable_archive_descriptors d ON d.stream_id=r.stream_id WHERE d.stream_id IS NULL LIMIT 1"
    ):
        raise WearableError("missing_stream_descriptor")
    for record in database.execute(
        "SELECT descriptor FROM wearable_archive_descriptors ORDER BY stream_id"
    ):
        descriptor = json.loads(record[0])
        validator = SnapshotValidator(descriptor, time_us(now))
        source_id = descriptor["source_id"]
        if not database.execute(
            "SELECT 1 FROM bridge_sources WHERE source_id=?", (source_id,)
        ):
            raise WearableError("missing_source_descriptor")
        require_registry_slot(database, descriptor["stream_id"])
        database.execute(
            "INSERT INTO wearable_streams(stream_id,source_id,metric,unit,weighting,algorithm_id,algorithm_version,origin_mode,retired,sequence,content_hash) VALUES(?,?,?,?,?,?,?,'imported_history',?,?,?)",
            (
                *[descriptor[key] for key in IDENTITY_FIELDS],
                int(descriptor["retired"]),
                int(descriptor["sequence"]),
                bytes.fromhex(descriptor["content_hash"])
                if descriptor["content_hash"]
                else None,
            ),
        )
        internal_id = database.execute(
            "SELECT id FROM wearable_streams WHERE stream_id=?",
            (descriptor["stream_id"],),
        )[0][0]
        for row in database.iterate(
            "SELECT record FROM wearable_archive_rows WHERE stream_id=? ORDER BY start_us",
            (descriptor["stream_id"],),
        ):
            bucket = validator.add(json.loads(row[0]))
            database.execute(
                f"INSERT INTO wearable_buckets(stream_id,{BUCKET_COLUMNS}) VALUES(?,?,?,?,?,?,?)",
                (internal_id, *bucket_values(bucket)),
            )
        validator.finish()
    database.execute("DROP TABLE wearable_archive_rows")


def snapshot_descriptor(connection, stream, snapshot_at):
    descriptor = {key: stream[key] for key in IDENTITY_FIELDS}
    descriptor.update(
        retired=bool(stream["retired"]),
        sequence=str(stream["sequence"]),
        hash_version=1,
        content_hash=stream["content_hash"].hex()
        if stream["content_hash"] is not None
        else None,
        snapshot_at=snapshot_at,
        snapshot_bucket_count=connection.execute(
            "SELECT COUNT(*) FROM wearable_buckets WHERE stream_id=?", (stream["id"],)
        ).fetchone()[0],
    )
    rows = connection.execute(
        f"SELECT {BUCKET_COLUMNS} FROM wearable_buckets WHERE stream_id=? ORDER BY start_us",
        (stream["id"],),
    )
    try:
        descriptor["snapshot_hash"] = snapshot_hash(
            descriptor, (bucket_from_row(row, stream["weighting"]) for row in rows)
        )
    finally:
        rows.close()
    return descriptor


def export_records(connection, domain, snapshot_at):
    streams = connection.execute("SELECT * FROM wearable_streams ORDER BY stream_id")
    try:
        for stream in streams:
            if domain == "wearable_streams":
                yield snapshot_descriptor(connection, stream, snapshot_at)
                continue
            rows = connection.execute(
                f"SELECT {BUCKET_COLUMNS} FROM wearable_buckets WHERE stream_id=? ORDER BY start_us",
                (stream["id"],),
            )
            try:
                for row in rows:
                    yield bucket_from_row(row, stream["weighting"]).archive(
                        stream["stream_id"]
                    )
            finally:
                rows.close()
    finally:
        streams.close()


def replay_wearable(staging, target, counts, after_batch, now):
    repository = WearableRepository(target)
    incoming = WearableRepository(staging)
    for row in staging.execute(
        "SELECT descriptor FROM wearable_archive_descriptors ORDER BY stream_id"
    ):
        descriptor = json.loads(row[0])
        source = staging.execute(
            "SELECT * FROM bridge_sources WHERE source_id=?", (descriptor["source_id"],)
        )
        if not source:
            raise WearableError("missing_source_descriptor")
        source_descriptor = {key: source[0][key] for key in SOURCE_FIELDS}
        stream = incoming.get(descriptor["stream_id"])
        with target.transaction():
            before = target.execute(
                "SELECT retired FROM wearable_streams WHERE stream_id=?",
                (stream["stream_id"],),
            )
            source_before = target.execute(
                "SELECT 1 FROM bridge_sources WHERE source_id=?",
                (source_descriptor["source_id"],),
            )
            updated = repository.import_snapshot(
                descriptor, incoming.buckets(stream), source_descriptor, now
            )
            retired = bool(before and not before[0][0] and descriptor["retired"])
            action = (
                "create"
                if not before
                else "merge"
                if updated or retired
                else "unchanged"
            )
            counts.setdefault(
                "wearable_streams", {"create": 0, "merge": 0, "unchanged": 0}
            )[action] += 1
            if not source_before:
                counts.setdefault("bridge_sources", {"create": 0, "unchanged": 0})[
                    "create"
                ] += 1
        if after_batch:
            after_batch("wearable_streams")
