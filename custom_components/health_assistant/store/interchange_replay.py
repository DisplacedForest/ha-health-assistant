from __future__ import annotations

import json
from datetime import datetime

from .errors import StoreValidationError
from .interchange_archive import PAGE_SIZE
from .interchange_staging import rows_by_id
from .models import HealthObservation, MetricType, RecordStatus, Workout
from .repository import HealthRepository


def _same(left, right, ignored):
    return all(left[key] == right[key] for key in right if key not in ignored)


def _claim_model(record):
    value = {
        key: item for key, item in record.items() if key not in ("id", "observation_id")
    }
    value["metric"] = MetricType(value["metric"])
    value["status"] = RecordStatus(value["status"])
    value["observed_at"] = datetime.fromisoformat(value["observed_at"])
    value["ingested_at"] = datetime.fromisoformat(value["ingested_at"])
    value["provenance"] = json.loads(value["provenance"])
    return HealthObservation(**value)


def _workout_model(record):
    value = {key: item for key, item in record.items() if key != "id"}
    for key in ("started_at", "ended_at", "ingested_at"):
        value[key] = datetime.fromisoformat(value[key])
    value["status"] = RecordStatus(value["status"])
    value["provenance"] = json.loads(value["provenance"])
    return Workout(**value)


def _merge_record(existing, incoming):
    if existing["person_id"] != incoming["person_id"]:
        raise StoreValidationError("A source identity belongs to a different person")
    result = dict(
        existing if existing["ingested_at"] > incoming["ingested_at"] else incoming
    )
    if existing["status"] == "excluded" or incoming["status"] == "excluded":
        result["status"] = "excluded"
    return result


def _batches(records):
    batch = []
    for record in records:
        batch.append(record)
        if len(batch) == PAGE_SIZE:
            yield batch
            batch = []
    if batch:
        yield batch


def _count(counts, domain, action):
    counts.setdefault(domain, {"create": 0, "merge": 0, "unchanged": 0})[action] += 1


def replay_archive(staging, target, after_batch=None):
    repository = HealthRepository(target)
    counts = {}
    for metric in MetricType:
        desired = [
            row["provider"]
            for row in staging.execute(
                "SELECT provider FROM metric_priorities WHERE metric=? ORDER BY rank",
                (metric.value,),
            )
        ]
        if desired != repository.get_priority(metric):
            repository.set_priority(metric, desired, streaming=True)
            _count(counts, "metric_priorities", "merge")
        else:
            _count(counts, "metric_priorities", "unchanged")
    if after_batch:
        after_batch("metric_priorities")
    for domain in ("source_claims", "workouts"):
        for batch in _batches(rows_by_id(staging, domain)):
            with target.transaction():
                for incoming in batch:
                    if domain == "source_claims":
                        rows = target.execute(
                            "SELECT * FROM source_claims WHERE provider=? AND external_id=? AND metric=? AND observed_at=?",
                            (
                                incoming["provider"],
                                incoming["external_id"],
                                incoming["metric"],
                                incoming["observed_at"],
                            ),
                        )
                    else:
                        rows = target.execute(
                            "SELECT * FROM workouts WHERE provider=? AND external_id=?",
                            (incoming["provider"], incoming["external_id"]),
                        )
                    existing = dict(rows[0]) if rows else None
                    record = _merge_record(existing, incoming) if existing else incoming
                    if existing and _same(existing, record, {"id", "observation_id"}):
                        _count(counts, domain, "unchanged")
                        continue
                    if domain == "source_claims":
                        repository.upsert_observation(_claim_model(record))
                    else:
                        repository.upsert_workout(_workout_model(record))
                    _count(counts, domain, "merge" if existing else "create")
            if after_batch:
                after_batch(domain)
    stream_ids = _replay_streams(staging, target, counts)
    if after_batch:
        after_batch("environment_streams")
    for batch in _batches(_buckets(staging)):
        with target.transaction():
            for record in batch:
                record["stream_id"] = stream_ids[record["stream_id"]]
                action = _replay_bucket(target, record)
                _count(counts, "environment_buckets", action)
        if after_batch:
            after_batch("environment_buckets")
    if _environment_matches(staging, target, stream_ids):
        state = dict(
            staging.execute("SELECT * FROM environment_maintenance WHERE id=1")[0]
        )
        target.execute(
            "UPDATE environment_maintenance SET last_success_ms=?, duration_ms=?, rolled_up=?, deleted=?, failed=? WHERE id=1",
            (
                state["last_success_ms"],
                state["duration_ms"],
                state["rolled_up"],
                state["deleted"],
                state["failed"],
            ),
        )
    return counts


def _replay_streams(staging, target, counts):
    mapping = {}
    with target.transaction():
        for incoming in rows_by_id(staging, "environment_streams"):
            rows = target.execute(
                "SELECT * FROM environment_streams WHERE public_id=?",
                (incoming["public_id"],),
            )
            if rows:
                existing = dict(rows[0])
                if not _same(existing, incoming, {"id"}):
                    raise StoreValidationError(
                        "Environmental stream identity has conflicting metadata"
                    )
                mapping[incoming["id"]] = existing["id"]
                _count(counts, "environment_streams", "unchanged")
                continue
            if (
                target.execute("SELECT count(*) AS count FROM environment_streams")[0][
                    "count"
                ]
                >= 256
            ):
                raise StoreValidationError(
                    "Environmental stream registry limit exceeded"
                )
            columns = [key for key in incoming if key != "id"]
            rows = target.execute(
                f"INSERT INTO environment_streams ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)}) RETURNING id",
                (incoming[key] for key in columns),
            )
            mapping[incoming["id"]] = rows[0]["id"]
            _count(counts, "environment_streams", "create")
    return mapping


def _buckets(database):
    after = (0, 0, 0)
    while rows := database.execute(
        "SELECT * FROM environment_buckets WHERE (stream_id,resolution_s,start_ms)>(?,?,?) ORDER BY stream_id,resolution_s,start_ms LIMIT ?",
        (*after, PAGE_SIZE),
    ):
        for row in rows:
            yield dict(row)
        after = tuple(
            rows[-1][key] for key in ("stream_id", "resolution_s", "start_ms")
        )


def _replay_bucket(target, incoming):
    stream, resolution, start = (
        incoming[key] for key in ("stream_id", "resolution_s", "start_ms")
    )
    if resolution == 300 and target.execute(
        "SELECT 1 FROM environment_buckets WHERE stream_id=? AND resolution_s=3600 AND start_ms=?",
        (stream, start // 3600000 * 3600000),
    ):
        return "unchanged"
    rows = target.execute(
        "SELECT * FROM environment_buckets WHERE stream_id=? AND resolution_s=? AND start_ms=?",
        (stream, resolution, start),
    )
    if rows:
        existing = dict(rows[0])
        if (
            _same(existing, incoming, set())
            or existing["updated_ms"] > incoming["updated_ms"]
        ):
            return "unchanged"
        if existing["updated_ms"] == incoming["updated_ms"]:
            raise StoreValidationError(
                "Environmental bucket has conflicting data at the same revision"
            )
    if resolution == 3600:
        newest = target.execute(
            "SELECT max(updated_ms) AS newest FROM environment_buckets WHERE stream_id=? AND resolution_s=300 AND start_ms>=? AND start_ms<?",
            (stream, start, start + 3600000),
        )[0]["newest"]
        if newest is not None and newest > incoming["updated_ms"]:
            raise StoreValidationError(
                "Environmental aggregate would replace newer detailed history"
            )
        target.execute(
            "DELETE FROM environment_buckets WHERE stream_id=? AND resolution_s=300 AND start_ms>=? AND start_ms<?",
            (stream, start, start + 3600000),
        )
    columns = list(incoming)
    target.execute(
        f"INSERT INTO environment_buckets ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)}) ON CONFLICT(stream_id,resolution_s,start_ms) DO UPDATE SET "
        + ",".join(
            f"{key}=excluded.{key}"
            for key in columns
            if key not in ("stream_id", "resolution_s", "start_ms")
        ),
        (incoming[key] for key in columns),
    )
    return "merge" if rows else "create"


def _environment_matches(staging, target, stream_ids):
    if target.execute("SELECT count(*) FROM environment_streams")[0][0] != len(
        stream_ids
    ):
        return False
    if (
        target.execute("SELECT count(*) FROM environment_buckets")[0][0]
        != staging.execute("SELECT count(*) FROM environment_buckets")[0][0]
    ):
        return False
    for incoming in _buckets(staging):
        incoming["stream_id"] = stream_ids[incoming["stream_id"]]
        rows = target.execute(
            "SELECT * FROM environment_buckets WHERE stream_id=? AND resolution_s=? AND start_ms=?",
            (incoming["stream_id"], incoming["resolution_s"], incoming["start_ms"]),
        )
        if not rows or not _same(dict(rows[0]), incoming, set()):
            return False
    return True
