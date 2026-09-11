from __future__ import annotations

from uuid import uuid4

from .wearable_models import (
    DAY_US,
    WearableBucket,
    WearableError,
    normalize_batch,
    time_us,
    timestamp,
    uuid_value,
)
from .wearable_retention import retained_buckets
from .wearable_snapshot import IDENTITY_FIELDS, SnapshotValidator, algorithm

BUCKET_COLUMNS = "start_us,resolution_s,weight,total,minimum,maximum"


def bucket_from_row(row, weighting):
    return WearableBucket(
        row["start_us"],
        row["resolution_s"],
        weighting,
        row["weight"],
        row["total"],
        row["minimum"],
        row["maximum"],
    )


def bucket_values(bucket):
    return (
        bucket.start_us,
        bucket.resolution_s,
        bucket.weight,
        bucket.total,
        bucket.minimum,
        bucket.maximum,
    )


class WearableRepository:
    def __init__(self, database):
        self.database = database

    def get(self, stream_id):
        rows = self.database.execute(
            "SELECT * FROM wearable_streams WHERE stream_id=?", (uuid_value(stream_id),)
        )
        if not rows:
            raise WearableError("unknown_stream")
        return dict(rows[0])

    def tip(self, stream_id):
        stream = self.get(stream_id)
        return {
            "stream_id": stream["stream_id"],
            "source_id": stream["source_id"],
            "sequence": str(stream["sequence"]),
            "hash_version": 1,
            "content_hash": stream["content_hash"].hex()
            if stream["content_hash"] is not None
            else None,
            "retired": bool(stream["retired"]),
            "origin_mode": stream["origin_mode"],
        }

    def changed(self):
        self.database.execute(
            "UPDATE wearable_state SET generation=? WHERE id=1", (uuid4().hex,)
        )

    def validate_pending(self, source_id, stream_batch, now):
        with self.database.transaction():
            if not isinstance(stream_batch, dict):
                raise WearableError()
            stream = self.get(stream_batch.get("stream_id"))
            if stream["source_id"] != source_id:
                raise WearableError("stream_identity_conflict")
            batch = normalize_batch(stream_batch, stream["weighting"])
            if batch.sequence != batch.expected_sequence + 1:
                raise WearableError("sequence_conflict")
            return {
                "stream_id": batch.stream_id,
                "expected_sequence": str(batch.expected_sequence),
                "sequence": str(batch.sequence),
                "content_hash": batch.content_hash,
            }

    def enroll(
        self,
        source_id,
        owner_id,
        *,
        weighting,
        algorithm_id=None,
        algorithm_version=None,
    ):
        from .bridge_registry import BridgeRegistry, require_registry_slot

        if weighting not in ("sample", "time"):
            raise WearableError("unsupported_weighting")
        metadata = (algorithm(algorithm_id), algorithm(algorithm_version))
        with self.database.transaction():
            BridgeRegistry(self.database).require_live(source_id, owner_id)
            stream_id = str(uuid4())
            require_registry_slot(self.database, stream_id)
            self.database.execute(
                "INSERT INTO wearable_streams(stream_id,source_id,metric,unit,weighting,algorithm_id,algorithm_version,origin_mode) VALUES(?,?,'heart_rate','bpm',?,?,?,'local_enrollment')",
                (stream_id, source_id, weighting, *metadata),
            )
            self.changed()
        return self.tip(stream_id)

    def retire(self, stream_id):
        with self.database.transaction():
            stream = self.get(stream_id)
            if not stream["retired"]:
                self.database.execute(
                    "UPDATE wearable_streams SET retired=1 WHERE id=?", (stream["id"],)
                )
                self.changed()

    def remove(self, stream_id):
        with self.database.transaction():
            stream = self.get(stream_id)
            if not stream["retired"] or self.database.execute(
                "SELECT 1 FROM wearable_buckets WHERE stream_id=? LIMIT 1",
                (stream["id"],),
            ):
                raise WearableError("stream_in_use")
            self.database.execute(
                "DELETE FROM wearable_streams WHERE id=?", (stream["id"],)
            )
            self.changed()

    def buckets(self, stream):
        for row in self.database.iterate(
            f"SELECT {BUCKET_COLUMNS} FROM wearable_buckets WHERE stream_id=? ORDER BY start_us",
            (stream["id"],),
        ):
            yield bucket_from_row(row, stream["weighting"])

    def _stage(self, stream, buckets):
        self.database.execute(
            "CREATE TEMP TABLE IF NOT EXISTS wearable_pending(start_us INTEGER PRIMARY KEY,resolution_s INTEGER,weight INTEGER,total REAL,minimum REAL,maximum REAL) WITHOUT ROWID"
        )
        self.database.execute("DELETE FROM wearable_pending")
        for bucket in buckets:
            bucket.validate()
            if bucket.weighting != stream["weighting"]:
                raise WearableError("unsupported_weighting")
            self.database.execute(
                "INSERT INTO wearable_pending VALUES(?,?,?,?,?,?)",
                bucket_values(bucket),
            )

    def _replace_staged(self, stream):
        self.database.execute(
            "DELETE FROM wearable_buckets WHERE stream_id=?", (stream["id"],)
        )
        self.database.execute(
            f"INSERT INTO wearable_buckets(stream_id,{BUCKET_COLUMNS}) SELECT ?,{BUCKET_COLUMNS} FROM wearable_pending",
            (stream["id"],),
        )

    def _compact(self, stream, now_us):
        self._stage(stream, retained_buckets(self.buckets(stream), now_us))
        different = self.database.execute(
            f"SELECT 1 FROM (SELECT {BUCKET_COLUMNS} FROM wearable_buckets WHERE stream_id=? EXCEPT SELECT {BUCKET_COLUMNS} FROM wearable_pending) LIMIT 1",
            (stream["id"],),
        ) or self.database.execute(
            f"SELECT 1 FROM (SELECT {BUCKET_COLUMNS} FROM wearable_pending EXCEPT SELECT {BUCKET_COLUMNS} FROM wearable_buckets WHERE stream_id=?) LIMIT 1",
            (stream["id"],),
        )
        if different:
            self._replace_staged(stream)
        self.database.execute("DELETE FROM wearable_pending")
        return bool(different)

    def maintain(self, now):
        now_us = time_us(now)
        result = {"changed_streams": 0, "degraded_streams": 0}
        for item in self.database.execute(
            "SELECT stream_id FROM wearable_streams ORDER BY id"
        ):
            try:
                with self.database.transaction():
                    stream = self.get(item[0])
                    changed = self._compact(stream, now_us)
                    if changed or stream["degraded"]:
                        self.database.execute(
                            "UPDATE wearable_streams SET degraded=0 WHERE id=?",
                            (stream["id"],),
                        )
                        self.changed()
                    result["changed_streams"] += int(changed)
            except WearableError:
                with self.database.transaction():
                    stream = self.get(item[0])
                    if not stream["degraded"]:
                        self.database.execute(
                            "UPDATE wearable_streams SET degraded=1 WHERE id=?",
                            (stream["id"],),
                        )
                        self.changed()
                result["degraded_streams"] += 1
        return result

    def _eligible(self, stream, operation, now_us, boundary):
        if operation.end_us > now_us:
            raise WearableError("future_bucket")
        if operation.end_us < now_us - 730 * DAY_US:
            raise WearableError("outside_retention")
        if boundary is not None and operation.start_us < time_us(boundary):
            raise WearableError("before_capture_start")
        required = (
            3600
            if operation.end_us < now_us - 90 * DAY_US
            else (300 if operation.end_us < now_us - 7 * DAY_US else 60)
        )
        overlapping = self.database.execute(
            "SELECT start_us,resolution_s FROM wearable_buckets WHERE stream_id=? AND start_us>=? AND start_us<? AND start_us+resolution_s*1000000>? ORDER BY start_us",
            (
                stream["id"],
                operation.start_us - 3600000000,
                operation.end_us,
                operation.start_us,
            ),
        )
        required = max([required, *(row["resolution_s"] for row in overlapping)])
        if operation.resolution_s < required:
            width = required * 1000000
            raise WearableError(
                "retained_resolution_required",
                required_resolution=required,
                required_start=timestamp(operation.start_us // width * width),
            )

    def apply_batch(self, source_id, stream_batch, now, check_authorized):
        from .bridge_registry import BridgeRegistry

        with self.database.transaction():
            check_authorized()
            if not isinstance(stream_batch, dict):
                raise WearableError()
            stream = self.get(stream_batch.get("stream_id"))
            source = BridgeRegistry(self.database).get(source_id)
            if (
                stream["source_id"] != source_id
                or stream["retired"]
                or stream["origin_mode"] != "local_enrollment"
                or source["origin_mode"] != "local_enrollment"
                or source["retired"]
                or source["needs_fresh_namespace"]
                or source["owner_id"] is None
            ):
                raise WearableError("stream_paused")
            batch = normalize_batch(stream_batch, stream["weighting"])
            response = {
                "changed": False,
                "replayed": False,
                "sequence": str(batch.sequence),
                "content_hash": batch.content_hash,
            }
            if (
                batch.sequence == stream["sequence"]
                and bytes.fromhex(batch.content_hash) == stream["content_hash"]
            ):
                check_authorized()
                return {**response, "replayed": True}
            if (
                batch.expected_sequence != stream["sequence"]
                or batch.sequence != stream["sequence"] + 1
            ):
                raise WearableError("sequence_conflict")
            now_us = time_us(now)
            self._compact(stream, now_us)
            for operation in batch.operations:
                self._eligible(stream, operation, now_us, source["capture_started_at"])
            for operation in batch.operations:
                self.database.execute(
                    "DELETE FROM wearable_buckets WHERE stream_id=? AND start_us>=? AND start_us<?",
                    (stream["id"], operation.start_us, operation.end_us),
                )
                if operation.bucket is not None:
                    self.database.execute(
                        f"INSERT INTO wearable_buckets(stream_id,{BUCKET_COLUMNS}) VALUES(?,?,?,?,?,?,?)",
                        (stream["id"], *bucket_values(operation.bucket)),
                    )
            self.database.execute(
                "UPDATE wearable_streams SET sequence=?,content_hash=?,degraded=0 WHERE id=?",
                (batch.sequence, bytes.fromhex(batch.content_hash), stream["id"]),
            )
            self.changed()
            check_authorized()
            return {**response, "changed": True}

    def import_snapshot(self, descriptor, buckets, source_descriptor, now):
        from .bridge_registry import BridgeRegistry, require_registry_slot

        with self.database.transaction():
            validator = SnapshotValidator(descriptor, time_us(now))
            descriptor = validator.descriptor

            def validated():
                for bucket in buckets:
                    yield validator.add(bucket.archive(descriptor["stream_id"]))
                validator.finish()

            self._stage(descriptor, retained_buckets(validated(), time_us(now)))
            registry = BridgeRegistry(self.database)
            registry.import_source(source_descriptor)
            if descriptor["source_id"] != source_descriptor["source_id"]:
                raise WearableError("stream_identity_conflict")
            rows = self.database.execute(
                "SELECT * FROM wearable_streams WHERE stream_id=?",
                (descriptor["stream_id"],),
            )
            if rows:
                stream = dict(rows[0])
                if any(stream[key] != descriptor[key] for key in IDENTITY_FIELDS):
                    raise WearableError("stream_identity_conflict")
                incoming = int(descriptor["sequence"])
                digest = bytes.fromhex(descriptor["content_hash"]) if incoming else None
                if incoming == stream["sequence"] and digest != stream["content_hash"]:
                    raise WearableError("sequence_conflict")
                if descriptor["retired"] and not stream["retired"]:
                    self.database.execute(
                        "UPDATE wearable_streams SET retired=1 WHERE id=?",
                        (stream["id"],),
                    )
                    self.changed()
                if incoming <= stream["sequence"]:
                    self.database.execute("DELETE FROM wearable_pending")
                    return False
            else:
                require_registry_slot(self.database, descriptor["stream_id"])
                self.database.execute(
                    "INSERT INTO wearable_streams(stream_id,source_id,metric,unit,weighting,algorithm_id,algorithm_version,origin_mode) VALUES(?,?,?,?,?,?,?,'imported_history')",
                    tuple(descriptor[key] for key in IDENTITY_FIELDS),
                )
                stream = self.get(descriptor["stream_id"])
            self._replace_staged(stream)
            self.database.execute("DELETE FROM wearable_pending")
            self.database.execute(
                "UPDATE wearable_streams SET sequence=?,content_hash=?,retired=MAX(retired,?),degraded=0 WHERE id=?",
                (
                    int(descriptor["sequence"]),
                    bytes.fromhex(descriptor["content_hash"])
                    if descriptor["content_hash"]
                    else None,
                    int(descriptor["retired"]),
                    stream["id"],
                ),
            )
            self.changed()
            return True
