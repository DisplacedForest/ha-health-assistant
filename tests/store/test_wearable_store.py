import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from custom_components.health_assistant.store.bridge_models import (
    DOMAINS,
    SOURCE_FIELDS,
    BridgeError,
)
from custom_components.health_assistant.store.bridge_registry import (
    BridgeRegistry,
    registry_count,
)
from custom_components.health_assistant.store.wearable import WearableRepository
from custom_components.health_assistant.store.wearable_models import (
    WearableBucket,
    WearableError,
    canonical,
    time_us,
    timestamp,
)
from custom_components.health_assistant.store.wearable_queries import WearableQueries
from custom_components.health_assistant.store.wearable_schema import MIGRATION
from custom_components.health_assistant.store.wearable_snapshot import (
    IDENTITY_FIELDS,
    snapshot_hash,
)

NOW = datetime(2026, 9, 11, tzinfo=UTC)
START = time_us(NOW - timedelta(days=1))


@pytest.fixture
def wearable(database):
    with database.transaction():
        for statement in MIGRATION:
            database.execute(statement)
    registry = BridgeRegistry(database)
    source = registry.enroll(
        {
            "adapter_kind": "fixture",
            "upstream_store": "apple_health",
            "upstream_scope": "sample",
            "label": "Sample",
        },
        "owner",
        dict.fromkeys(DOMAINS, "none"),
        NOW,
    )
    repository = WearableRepository(database)
    stream = repository.enroll(source["source_id"], "owner", weighting="sample")
    return repository, source, stream["stream_id"]


def row(start=START, resolution=60, *, weight=1, mean=70, weighting="sample"):
    return WearableBucket(
        start, resolution, weighting, weight, mean * weight, mean, mean
    )


def native(stream_id, operations, expected=0, sequence=None):
    value = {
        "hash_scope": "health_assistant.wearable_batch",
        "hash_version": 1,
        "stream_id": stream_id,
        "expected_sequence": str(expected),
        "sequence": str(expected + 1 if sequence is None else sequence),
        "operations": operations,
    }
    digest = hashlib.sha256(canonical(value)).hexdigest()
    del value["hash_scope"]
    return {**value, "content_hash": digest}


def apply(fixture, operations, expected=0, now=NOW):
    repository, source, stream_id = fixture
    return repository.apply_batch(
        source["source_id"], native(stream_id, operations, expected), now, lambda: None
    )


def stored(fixture):
    repository, _, stream_id = fixture
    return list(repository.buckets(repository.get(stream_id)))


def snapshot(fixture, *, sequence=None, rows=None, retired=False):
    repository, source, stream_id = fixture
    stream = repository.get(stream_id)
    rows = stored(fixture) if rows is None else rows
    number = stream["sequence"] if sequence is None else sequence
    digest = (
        stream["content_hash"].hex()
        if number == stream["sequence"] and stream["content_hash"]
        else ("b" * 64 if number else None)
    )
    descriptor = {key: stream[key] for key in IDENTITY_FIELDS}
    descriptor.update(
        sequence=str(number),
        hash_version=1,
        content_hash=digest,
        retired=retired,
        snapshot_at=timestamp(time_us(NOW)),
        snapshot_bucket_count=len(rows),
    )
    descriptor["snapshot_hash"] = snapshot_hash(descriptor, rows)
    source_descriptor = {key: source[key] for key in SOURCE_FIELDS}
    return descriptor, rows, source_descriptor


def test_complete_replacement_deletion_and_latest_retry(wearable):
    repository, _, stream_id = wearable
    apply(wearable, [row().wire()])
    apply(wearable, [row(mean=90).wire()], 1)
    assert stored(wearable) == [row(mean=90)]
    deletion = {"op": "delete", "start": timestamp(START), "resolution": 60}
    apply(wearable, [deletion], 2)
    assert stored(wearable) == []
    replay = apply(wearable, [deletion], 2)
    assert replay["replayed"] and not replay["changed"]
    assert repository.tip(stream_id)["sequence"] == "3"
    with pytest.raises(WearableError, match="sequence_conflict"):
        apply(wearable, [row().wire()])
    assert stored(wearable) == []


def test_latest_retry_after_compaction_and_expiry_never_recreates_rows(wearable):
    repository, _, stream_id = wearable
    operations = [row().wire()]
    apply(wearable, operations)
    repository.maintain(NOW + timedelta(days=10))
    assert stored(wearable)[0].resolution_s == 300
    assert apply(wearable, operations, now=NOW + timedelta(days=10))["replayed"]
    assert stored(wearable)[0].resolution_s == 300
    repository.maintain(NOW + timedelta(days=800))
    assert stored(wearable) == []
    assert apply(wearable, operations, now=NOW + timedelta(days=800))["replayed"]
    assert repository.tip(stream_id)["sequence"] == "1"
    assert stored(wearable) == []


def test_new_fine_correction_requires_complete_retained_interval(wearable):
    repository, _, stream_id = wearable
    apply(wearable, [row().wire()])
    later = NOW + timedelta(days=10)
    repository.maintain(later)
    with pytest.raises(WearableError, match="retained_resolution_required") as exc:
        apply(wearable, [row(mean=80).wire()], 1, later)
    assert exc.value.details == {
        "required_resolution": 300,
        "required_start": timestamp(START),
    }
    assert repository.tip(stream_id)["sequence"] == "1"
    apply(wearable, [row(resolution=300, mean=80).wire()], 1, later)
    assert stored(wearable) == [row(resolution=300, mean=80)]


def test_complete_coarse_replacement_supersedes_all_fine_children(wearable):
    apply(wearable, [row(START + i * 60000000).wire() for i in range(5)])
    apply(wearable, [row(resolution=300, weight=2, mean=100).wire()], 1)
    assert stored(wearable) == [row(resolution=300, weight=2, mean=100)]
    with pytest.raises(WearableError, match="retained_resolution_required"):
        apply(
            wearable,
            [{"op": "delete", "start": timestamp(START + 60000000), "resolution": 60}],
            2,
        )


def test_invalid_final_operation_rolls_back_compaction_and_sequence(wearable):
    repository, _, stream_id = wearable
    apply(wearable, [row().wire()])
    later = NOW + timedelta(days=10)
    future = row(time_us(later + timedelta(hours=1))).wire()
    with pytest.raises(WearableError, match="future_bucket"):
        apply(wearable, [row(resolution=300).wire(), future], 1, later)
    assert stored(wearable) == [row()]
    assert repository.tip(stream_id)["sequence"] == "1"


def test_final_insert_failure_rolls_back_rows_and_tip(wearable):
    repository, _, stream_id = wearable
    apply(wearable, [row().wire()])
    repository.database.execute(
        f"CREATE TRIGGER fail_wearable_insert BEFORE INSERT ON wearable_buckets WHEN NEW.start_us={START + 60000000} BEGIN SELECT RAISE(ABORT,'fixture failure'); END"
    )
    with pytest.raises(sqlite3.IntegrityError, match="fixture failure"):
        apply(wearable, [row(mean=80).wire(), row(START + 60000000).wire()], 1)
    assert stored(wearable) == [row()]
    assert repository.tip(stream_id)["sequence"] == "1"


def test_authorization_loss_before_commit_rolls_back(wearable):
    repository, source, stream_id = wearable
    calls = 0

    def check():
        nonlocal calls
        calls += 1
        if calls > 1:
            raise WearableError("session_required")

    with pytest.raises(WearableError, match="session_required"):
        repository.apply_batch(
            source["source_id"], native(stream_id, [row().wire()]), NOW, check
        )
    assert stored(wearable) == []
    assert repository.tip(stream_id)["sequence"] == "0"


def test_retired_stream_reads_but_cannot_write_or_reenroll_same_identity(wearable):
    repository, _, stream_id = wearable
    apply(wearable, [row().wire()])
    repository.retire(stream_id)
    with pytest.raises(WearableError, match="stream_paused"):
        apply(wearable, [row(mean=80).wire()], 1)
    result = WearableQueries(repository.database).series(
        stream_id, timestamp(START), timestamp(START + 60000000)
    )
    assert result["retired"] and result["points"][0]["value"] == 70
    with pytest.raises(WearableError, match="stream_in_use"):
        repository.remove(stream_id)


def test_wrong_owner_and_source_cannot_write(wearable):
    repository, source, stream_id = wearable
    with pytest.raises(BridgeError, match="registration_paused"):
        repository.enroll(source["source_id"], "other-owner", weighting="time")
    with pytest.raises(BridgeError, match="unknown_registration"):
        repository.apply_batch(
            str(uuid4()), native(stream_id, [row().wire()]), NOW, lambda: None
        )


def test_pending_validation_is_read_only_and_not_age_dependent(wearable):
    repository, source, stream_id = wearable
    value = native(stream_id, [row().wire()])
    before = repository.database.execute("SELECT generation FROM wearable_state")[0][0]
    result = repository.validate_pending(
        source["source_id"], value, NOW + timedelta(days=900)
    )
    assert result["sequence"] == "1" and result["expected_sequence"] == "0"
    assert stored(wearable) == []
    assert (
        repository.database.execute("SELECT generation FROM wearable_state")[0][0]
        == before
    )


def test_higher_snapshot_replaces_and_equal_or_older_snapshot_never_fills_gaps(
    wearable,
):
    repository, _, stream_id = wearable
    apply(wearable, [row().wire(), row(START + 60000000).wire()])
    older = snapshot(wearable)
    newer = snapshot(wearable, sequence=2, rows=[row(mean=90)])
    assert repository.import_snapshot(*newer, NOW)
    assert stored(wearable) == [row(mean=90)]
    assert not repository.import_snapshot(*older, NOW)
    equal = snapshot(wearable, rows=[row(mean=100), row(START + 60000000)])
    assert not repository.import_snapshot(*equal, NOW)
    assert stored(wearable) == [row(mean=90)]
    assert repository.tip(stream_id)["sequence"] == "2"


def test_snapshot_failure_restores_complete_old_stream(wearable):
    repository, _, stream_id = wearable
    apply(wearable, [row().wire()])
    candidate = snapshot(
        wearable, sequence=2, rows=[row(mean=80), row(START + 60000000)]
    )
    repository.database.execute(
        f"CREATE TRIGGER fail_snapshot BEFORE INSERT ON wearable_buckets WHEN NEW.start_us={START + 60000000} BEGIN SELECT RAISE(ABORT,'snapshot failure'); END"
    )
    with pytest.raises(sqlite3.IntegrityError, match="snapshot failure"):
        repository.import_snapshot(*candidate, NOW)
    assert stored(wearable) == [row()]
    assert repository.tip(stream_id)["sequence"] == "1"


def test_snapshot_validates_all_rows_even_when_incoming_tip_is_old(wearable):
    repository, _, _ = wearable
    apply(wearable, [row().wire()])
    older = snapshot(wearable)
    apply(wearable, [row(mean=90).wire()], 1)
    older[0]["snapshot_bucket_count"] += 1
    with pytest.raises(WearableError, match="snapshot_count_mismatch"):
        repository.import_snapshot(*older, NOW)
    assert stored(wearable) == [row(mean=90)]


def test_unknown_snapshot_source_and_stream_are_atomically_read_only(wearable):
    repository, _, _ = wearable
    apply(wearable, [row().wire()])
    descriptor, rows, source = snapshot(wearable)
    source["source_id"] = str(uuid4())
    descriptor.update(source_id=source["source_id"], stream_id=str(uuid4()))
    descriptor["snapshot_hash"] = snapshot_hash(descriptor, rows)
    assert repository.import_snapshot(descriptor, rows, source, NOW)
    assert repository.get(descriptor["stream_id"])["origin_mode"] == "imported_history"
    assert (
        BridgeRegistry(repository.database).get(source["source_id"])["owner_id"] is None
    )
    with pytest.raises(WearableError, match="stream_paused"):
        repository.apply_batch(
            source["source_id"],
            native(descriptor["stream_id"], [row(mean=80).wire()], 1),
            NOW,
            lambda: None,
        )


def test_failed_first_snapshot_leaves_no_source_or_stream(wearable):
    repository, _, _ = wearable
    apply(wearable, [row().wire()])
    descriptor, rows, source = snapshot(wearable)
    source["source_id"] = str(uuid4())
    descriptor.update(source_id=source["source_id"], stream_id=str(uuid4()))
    descriptor["snapshot_hash"] = snapshot_hash(descriptor, rows)
    repository.database.execute(
        "CREATE TRIGGER fail_new_snapshot BEFORE INSERT ON wearable_buckets BEGIN SELECT RAISE(ABORT,'new snapshot failure'); END"
    )
    before = registry_count(repository.database)
    with pytest.raises(sqlite3.IntegrityError):
        repository.import_snapshot(descriptor, rows, source, NOW)
    assert registry_count(repository.database) == before
    with pytest.raises(BridgeError, match="unknown_registration"):
        BridgeRegistry(repository.database).get(source["source_id"])


def test_maintenance_validation_failure_preserves_original_stream(wearable):
    repository, _, stream_id = wearable
    apply(wearable, [row().wire()])
    repository.database.execute("UPDATE wearable_buckets SET minimum=100,maximum=70")
    before = [
        tuple(r) for r in repository.database.execute("SELECT * FROM wearable_buckets")
    ]
    result = repository.maintain(NOW + timedelta(days=10))
    assert result == {"changed_streams": 0, "degraded_streams": 1}
    assert [
        tuple(r) for r in repository.database.execute("SELECT * FROM wearable_buckets")
    ] == before
    assert repository.get(stream_id)["degraded"] == 1


def test_shared_registry_capacity_includes_sources_and_retired_streams(wearable):
    repository, source, stream_id = wearable
    repository.retire(stream_id)
    for _ in range(254):
        repository.enroll(source["source_id"], "owner", weighting="sample")
    assert registry_count(repository.database) == 256
    with pytest.raises(BridgeError, match="registry_capacity"):
        repository.enroll(source["source_id"], "owner", weighting="sample")
    repository.remove(stream_id)
    fresh = repository.enroll(source["source_id"], "owner", weighting="sample")
    assert fresh["stream_id"] != stream_id


def test_complete_730_day_query_pages_without_gaps_or_duplicates(wearable):
    repository, _, stream_id = wearable
    stream = repository.get(stream_id)
    start = time_us(NOW - timedelta(days=730))
    with repository.database.transaction():
        repository._stage(
            stream, (row(start + i * 3600000000, resolution=3600) for i in range(17520))
        )
        repository._replace_staged(stream)
    queries = WearableQueries(repository.database)
    cursor = None
    points = []
    sizes = []
    while True:
        result = queries.series(
            stream_id, timestamp(start), timestamp(time_us(NOW)), cursor=cursor
        )
        sizes.append(len(result["points"]))
        points.extend(result["points"])
        cursor = result["next_cursor"]
        if cursor is None:
            break
    assert sizes == [500] * 35 + [20]
    assert [point["start"] for point in points] == [
        timestamp(start + i * 3600000000) for i in range(17520)
    ]
    assert points[-1]["end"] == timestamp(time_us(NOW))
    plan = repository.database.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM wearable_buckets WHERE stream_id=? AND start_us>=? AND start_us<? ORDER BY start_us",
        (stream["id"], start, time_us(NOW)),
    )
    assert any("SEARCH" in r[3] and "start_us>? AND start_us<?" in r[3] for r in plan)


def test_query_cursor_invalidated_by_write_and_bound_to_filter(wearable):
    repository, _, stream_id = wearable
    apply(wearable, [row(START + i * 60000000).wire() for i in range(3)])
    queries = WearableQueries(repository.database)
    args = (stream_id, timestamp(START), timestamp(START + 180000000))
    cursor = queries.series(*args, limit=1)["next_cursor"]
    with pytest.raises(WearableError, match="invalid_cursor"):
        queries.series(
            stream_id, timestamp(START), timestamp(START + 120000000), cursor=cursor
        )
    apply(wearable, [row(mean=80).wire()], 1)
    with pytest.raises(WearableError, match="stale_cursor"):
        queries.series(*args, cursor=cursor)


def test_query_edge_aggregate_collects_all_children_outside_requested_window(wearable):
    repository, _, stream_id = wearable
    apply(
        wearable, [row(START + i * 60000000, mean=50 + i * 10).wire() for i in range(5)]
    )
    points = WearableQueries(repository.database).series(
        stream_id,
        timestamp(START + 270000000),
        timestamp(START + 300000000),
        resolution=300,
    )["points"]
    assert len(points) == 1
    assert points[0]["start"] == timestamp(START)
    assert points[0]["sample_count"] == "5"
    assert points[0]["sample_sum"] == 350
    assert points[0]["value"] == 70


def test_noop_latest_retry_keeps_query_cursor_valid(wearable):
    repository, _, stream_id = wearable
    operations = [row(START + i * 60000000).wire() for i in range(2)]
    apply(wearable, operations)
    queries = WearableQueries(repository.database)
    args = (stream_id, timestamp(START), timestamp(START + 120000000))
    cursor = queries.series(*args, limit=1)["next_cursor"]
    assert apply(wearable, operations)["replayed"]
    assert len(queries.series(*args, cursor=cursor)["points"]) == 1
