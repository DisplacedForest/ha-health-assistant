import hashlib
import json
import sqlite3
import tarfile
import tracemalloc
from datetime import timedelta

import pytest

from custom_components.health_assistant.store.db import HealthDatabase
from custom_components.health_assistant.store.errors import (
    StoreError,
    StoreValidationError,
)
from custom_components.health_assistant.store.interchange import (
    export_archive,
    import_archive,
)
from custom_components.health_assistant.store.wearable import WearableRepository
from custom_components.health_assistant.store.wearable_models import DAY_US, time_us
from tests.store.test_wearable_store import NOW, START, apply, row, stored, wearable
from tests.test_bridge_archive import rewrite

pytestmark = pytest.mark.freeze_time("2026-09-11T00:00:00Z")
__all__ = ["wearable"]


@pytest.fixture
def target(tmp_path):
    database = HealthDatabase(tmp_path / "target.sqlite")
    database.open()
    yield database
    database.close()


def records(path, domain):
    with tarfile.open(path) as archive:
        return [json.loads(line) for line in archive.extractfile(f"{domain}.jsonl")]


def test_full_archive_preview_apply_repeat_and_read_only_origin(
    wearable, target, tmp_path
):
    repository, source, stream_id = wearable
    apply(wearable, [row().wire(), row(START + 60000000, mean=80).wire()])
    archive = tmp_path / "history.tar.gz"
    manifest = export_archive(repository.database, archive)
    assert manifest["source_schema_version"] == 10
    assert len(manifest["files"]) == 13
    preview = import_archive(target, archive)
    assert preview["expected"]["wearable_streams"]["create"] == 1
    assert preview["expected"]["bridge_sources"]["create"] == 1
    assert preview["sources"] == [f"bridge:{source['source_id']}"]
    assert preview["date_span"] == {
        "first": "2026-09-10T00:00:00.000000+00:00",
        "last": "2026-09-10T00:02:00.000000+00:00",
    }
    assert not target.execute("SELECT * FROM wearable_streams")
    assert not target.execute("SELECT * FROM bridge_sources")
    applied = import_archive(target, archive, dry_run=False)
    assert applied["applied"] == preview["expected"]
    imported = WearableRepository(target)
    assert list(imported.buckets(imported.get(stream_id))) == stored(wearable)
    assert imported.tip(stream_id)["origin_mode"] == "imported_history"
    assert target.execute("SELECT owner_id FROM bridge_sources")[0][0] is None
    assert not target.execute("SELECT * FROM bridge_receipts")
    repeated = import_archive(target, archive, dry_run=False)
    assert repeated["applied"]["wearable_streams"] == {
        "create": 0,
        "merge": 0,
        "unchanged": 1,
    }
    assert repeated["applied"]["bridge_sources"]["unchanged"] == 1


def test_export_pins_clock_and_compacts_only_backup(wearable, tmp_path, monkeypatch):
    repository, _, stream_id = wearable
    old = time_us(NOW - timedelta(days=9))
    apply(
        wearable,
        [row(old).wire(), row(old + 60000000, mean=80).wire()],
        now=NOW - timedelta(days=8),
    )
    before = stored(wearable)
    calls = []
    original = repository.database.backup_with_clock

    def backup(path, clock):
        def counted():
            calls.append(clock())
            return calls[-1]

        return original(path, counted)

    monkeypatch.setattr(repository.database, "backup_with_clock", backup)
    archive = tmp_path / "aged.tar.gz"
    manifest = export_archive(repository.database, archive)
    assert calls == [NOW]
    assert stored(wearable) == before
    descriptor = records(archive, "wearable_streams")[0]
    assert descriptor["snapshot_at"] == manifest["created_at"]
    assert descriptor["sequence"] == "1"
    exported = records(archive, "wearable_buckets")
    assert len(exported) == 1
    assert exported[0]["stream_id"] == stream_id
    assert exported[0]["resolution_s"] == 300
    assert exported[0]["sample_count"] == "2"
    assert exported[0]["sample_sum"] == 150


def test_import_ages_snapshot_without_resurrection(wearable, target, tmp_path, freezer):
    repository, _, stream_id = wearable
    apply(wearable, [row().wire()])
    archive = tmp_path / "old.tar.gz"
    export_archive(repository.database, archive)
    freezer.move_to(NOW + timedelta(days=731))
    import_archive(target, archive, dry_run=False)
    imported = WearableRepository(target)
    assert imported.tip(stream_id)["sequence"] == "1"
    assert not list(imported.buckets(imported.get(stream_id)))
    import_archive(target, archive, dry_run=False)
    assert not list(imported.buckets(imported.get(stream_id)))


def test_newer_snapshot_replaces_deleted_keys_and_older_snapshot_cannot_refill(
    wearable, target, tmp_path
):
    repository, _, stream_id = wearable
    apply(wearable, [row().wire(), row(START + 60000000).wire()])
    original = tmp_path / "original.tar.gz"
    export_archive(repository.database, original)
    import_archive(target, original, dry_run=False)
    apply(
        wearable,
        [{"op": "delete", "start": row().wire()["start"], "resolution": 60}],
        expected=1,
    )
    corrected = tmp_path / "corrected.tar.gz"
    export_archive(repository.database, corrected)
    result = import_archive(target, corrected, dry_run=False)
    assert result["applied"]["wearable_streams"]["merge"] == 1
    imported = WearableRepository(target)
    assert list(imported.buckets(imported.get(stream_id))) == [row(START + 60000000)]
    import_archive(target, original, dry_run=False)
    assert list(imported.buckets(imported.get(stream_id))) == [row(START + 60000000)]
    assert imported.tip(stream_id)["sequence"] == "2"


@pytest.mark.parametrize(
    "damage", ["last_bucket", "snapshot_clock", "snapshot_hash", "missing_source"]
)
def test_malformed_last_domain_never_touches_target(wearable, target, tmp_path, damage):
    repository, _, _ = wearable
    apply(wearable, [row().wire(), row(START + 60000000).wire()])
    source = tmp_path / "original.tar.gz"
    export_archive(repository.database, source)
    before = target.execute("SELECT generation FROM wearable_state")[0][0]

    def edit(parts, manifest):
        if damage == "missing_source":
            parts["bridge_sources.jsonl"] = b""
            return
        domain = (
            "wearable_buckets.jsonl"
            if damage == "last_bucket"
            else "wearable_streams.jsonl"
        )
        rows = [json.loads(line) for line in parts[domain].splitlines()]
        if damage == "last_bucket":
            rows[-1]["sample_sum"] = -1
        elif damage == "snapshot_clock":
            rows[-1]["snapshot_at"] = "2026-09-10T23:59:00.000000Z"
        else:
            rows[-1]["snapshot_hash"] = "f" * 64
        parts[domain] = b"".join(json.dumps(value).encode() + b"\n" for value in rows)

    invalid = tmp_path / "invalid.tar.gz"
    rewrite(source, invalid, edit)
    with pytest.raises(StoreValidationError):
        import_archive(target, invalid, dry_run=False)
    assert not target.execute("SELECT * FROM bridge_sources")
    assert not target.execute("SELECT * FROM wearable_streams")
    assert not target.execute("SELECT * FROM wearable_buckets")
    assert target.execute("SELECT generation FROM wearable_state")[0][0] == before


def test_final_live_insert_failure_preserves_complete_old_tip(
    wearable, target, tmp_path, monkeypatch
):
    repository, _, stream_id = wearable
    apply(wearable, [row().wire()])
    original = tmp_path / "original.tar.gz"
    export_archive(repository.database, original)
    import_archive(target, original, dry_run=False)
    before = [
        tuple(value) for value in target.execute("SELECT * FROM wearable_streams")
    ]
    apply(wearable, [row(START + 60000000).wire()], expected=1)
    archive = tmp_path / "newer.tar.gz"
    export_archive(repository.database, archive)
    execute = target.execute

    def failing(sql, params=()):
        if sql.startswith("INSERT INTO wearable_buckets"):
            raise sqlite3.OperationalError("fixture insert failure")
        return execute(sql, params)

    monkeypatch.setattr(target, "execute", failing)
    with pytest.raises(sqlite3.OperationalError):
        import_archive(target, archive, dry_run=False)
    assert [
        tuple(value) for value in target.execute("SELECT * FROM wearable_streams")
    ] == before
    imported = WearableRepository(target)
    assert list(imported.buckets(imported.get(stream_id))) == [row()]


def test_backup_cold_open_preserves_source_and_tip(wearable, tmp_path):
    repository, source, stream_id = wearable
    apply(wearable, [row().wire()])
    backup = tmp_path / "backup.sqlite"
    repository.database.backup(backup)
    restored = HealthDatabase(backup)
    restored.open()
    try:
        assert restored.execute("PRAGMA integrity_check")[0][0] == "ok"
        assert WearableRepository(restored).tip(stream_id) == repository.tip(stream_id)
        assert (
            restored.execute(
                "SELECT owner_id FROM bridge_sources WHERE source_id=?",
                (source["source_id"],),
            )[0][0]
            == "owner"
        )
    finally:
        restored.close()


def test_backup_clock_rejects_uncommitted_transaction(database, tmp_path):
    with database.transaction(), pytest.raises(StoreError, match="committed"):
        database.backup_with_clock(tmp_path / "invalid.sqlite", lambda: NOW)


def test_full_retained_archive_uses_bounded_python_memory(wearable, target, tmp_path):
    repository, _, stream_id = wearable
    internal = repository.get(stream_id)["id"]
    count = 17000
    start = time_us(NOW) - count * 3600000000
    with repository.database.transaction():
        for index in range(count):
            bucket = row(start + index * 3600000000, 3600)
            repository.database.execute(
                "INSERT INTO wearable_buckets VALUES(?,?,?,?,?,?,?)",
                (
                    internal,
                    bucket.start_us,
                    3600,
                    bucket.weight,
                    bucket.total,
                    bucket.minimum,
                    bucket.maximum,
                ),
            )
        repository.database.execute(
            "UPDATE wearable_streams SET sequence=1,content_hash=? WHERE id=?",
            (hashlib.sha256(b"fixture").digest(), internal),
        )
    archive = tmp_path / "large.tar.gz"
    tracemalloc.start()
    try:
        manifest = export_archive(repository.database, archive)
        _, export_peak = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()
        result = import_archive(target, archive, dry_run=False)
        _, import_peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert manifest["files"]["wearable_buckets.jsonl"]["records"] == count
    assert target.execute("SELECT count(*) FROM wearable_buckets")[0][0] == count
    assert result["applied"]["wearable_streams"]["create"] == 1
    assert export_peak < 8 * 1024 * 1024
    assert import_peak < 8 * 1024 * 1024
    assert count * 3600000000 < 730 * DAY_US
    print(
        {
            "archive_rows": count,
            "export_python_peak": export_peak,
            "import_python_peak": import_peak,
            "compressed_bytes": archive.stat().st_size,
        }
    )
