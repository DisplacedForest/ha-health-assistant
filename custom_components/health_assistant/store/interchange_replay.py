from __future__ import annotations

import json
from datetime import datetime

from .bridge_archive import replay_bridge, validate_target_sources
from .bridge_models import reserved
from .bridge_registry import require_registry_slot
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
    validate_target_sources(staging, target, counts)
    with target.transaction():
        changed = False
        for batch in _batches(rows_by_id(staging, "source_claims")):
            for incoming in batch:
                if reserved(incoming["provider"]):
                    continue
                rows = target.execute(
                    "SELECT * FROM source_claims WHERE provider=? AND external_id=? AND metric=? AND observed_at=?",
                    (
                        incoming["provider"],
                        incoming["external_id"],
                        incoming["metric"],
                        incoming["observed_at"],
                    ),
                )
                existing = dict(rows[0]) if rows else None
                record = _merge_record(existing, incoming) if existing else incoming
                if existing and _same(existing, record, {"id", "observation_id"}):
                    _count(counts, "source_claims", "unchanged")
                    continue
                repository._upsert_claim(_claim_model(record))
                changed = True
                _count(counts, "source_claims", "merge" if existing else "create")
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
        if changed:
            after = ("", "")
            while pairs := target.execute(
                "SELECT DISTINCT person_id,metric FROM source_claims WHERE (person_id,metric)>(?,?) ORDER BY person_id,metric LIMIT ?",
                (*after, PAGE_SIZE),
            ):
                for pair in pairs:
                    repository.reconcile_metric(
                        pair["person_id"], MetricType(pair["metric"]), streaming=True
                    )
                after = (pairs[-1]["person_id"], pairs[-1]["metric"])
    if after_batch:
        after_batch("source_claims")
    for batch in _batches(rows_by_id(staging, "workouts")):
        with target.transaction():
            for incoming in batch:
                if reserved(incoming["provider"]):
                    continue
                rows = target.execute(
                    "SELECT * FROM workouts WHERE provider=? AND external_id=?",
                    (incoming["provider"], incoming["external_id"]),
                )
                existing = dict(rows[0]) if rows else None
                record = _merge_record(existing, incoming) if existing else incoming
                if existing and _same(existing, record, {"id"}):
                    _count(counts, "workouts", "unchanged")
                    continue
                repository.upsert_workout(_workout_model(record))
                _count(counts, "workouts", "merge" if existing else "create")
        if after_batch:
            after_batch("workouts")
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
    _replay_sleep(staging, target, counts, after_batch)
    _replay_recovery(staging, target, counts, after_batch)
    replay_bridge(staging, target, counts, after_batch)
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
            require_registry_slot(target, incoming["public_id"])
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


def _replay_sleep(staging, target, counts, after_batch):
    from .sleep import SleepRepository, session_from_row

    repository = SleepRepository(target)
    batch = []
    size = 0
    for row in rows_by_id(staging, "sleep_sessions"):
        if reserved(row["provider"]):
            continue
        record_size = sum(
            len(value.encode("utf-8"))
            for value in row.values()
            if isinstance(value, str)
        )
        if len(batch) == 100 or size + record_size > 7 * 1024 * 1024:
            _apply_sleep_batch(repository, batch, counts)
            if after_batch:
                after_batch("sleep_sessions")
            batch, size = [], 0
        batch.append(session_from_row(row))
        size += record_size
    if batch:
        _apply_sleep_batch(repository, batch, counts)
        if after_batch:
            after_batch("sleep_sessions")


def _apply_sleep_batch(repository, batch, counts):
    results = repository.apply_sleep_changes(batch, merge_exclusions=True)
    domain = counts.setdefault(
        "sleep_sessions",
        dict.fromkeys(
            ("create", "update", "stale", "unchanged", "deleted", "exclusion_change"), 0
        ),
    )
    for result in results:
        domain["stale" if result.action == "stale_revision" else result.action] += 1
        domain["exclusion_change"] += int(result.exclusion_changed)


def _replay_recovery(staging, target, counts, after_batch):
    from .recovery import RecoveryRepository, observation_from_row

    repository = RecoveryRepository(target)
    batch = []
    size = 0
    for row in rows_by_id(staging, "recovery_records"):
        if reserved(row["provider"]):
            continue
        record_size = sum(
            len(value.encode("utf-8"))
            for value in row.values()
            if isinstance(value, str)
        )
        if len(batch) == 100 or size + record_size > 900 * 1024:
            _apply_recovery_batch(repository, batch, counts)
            if after_batch:
                after_batch("recovery_records")
            batch, size = [], 0
        batch.append(observation_from_row(row))
        size += record_size
    if batch:
        _apply_recovery_batch(repository, batch, counts)
        if after_batch:
            after_batch("recovery_records")


def _apply_recovery_batch(repository, batch, counts):
    results = repository.apply_recovery_changes(batch, merge_exclusions=True)
    domain = counts.setdefault(
        "recovery_records",
        dict.fromkeys(
            ("create", "update", "stale", "unchanged", "deleted", "exclusion_change"), 0
        ),
    )
    for result in results:
        domain["stale" if result.action == "stale_revision" else result.action] += 1
        domain["exclusion_change"] += int(result.exclusion_changed)
