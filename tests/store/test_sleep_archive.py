import gzip
import hashlib
import io
import json
import tarfile
from dataclasses import replace
from pathlib import Path

import pytest
from test_sleep import END, NOW, START, session, stage

from custom_components.health_assistant.store import (
    HealthDatabase,
    StoreValidationError,
)
from custom_components.health_assistant.store.interchange import (
    export_archive,
    import_archive,
)
from custom_components.health_assistant.store.interchange_archive import (
    read_archive,
    validate_manifest,
)
from custom_components.health_assistant.store.sleep import (
    SleepRepository,
    archive_session,
    parse_archive_session,
)


@pytest.fixture
def target(tmp_path):
    database = HealthDatabase(tmp_path / "target.sqlite")
    database.open()
    yield database
    database.close()


def test_released_archive_preserves_new_sleep_and_tombstones(database):
    repository = SleepRepository(database, clock=lambda: NOW)
    active, _tombstone = repository.apply_sleep_changes(
        [session(), session(external_id="deleted", deleted=True)]
    )
    repository.set_excluded(active.session.id, True, "1", active.session.payload_hash)
    before = [
        tuple(row)
        for row in database.execute("SELECT * FROM sleep_sessions ORDER BY id")
    ]
    fixture = Path(__file__).parents[1] / "fixtures/released-0.2-history.tar.gz"
    manifest = read_archive(fixture, lambda *_: None)
    assert manifest["format_version"] == 1 and manifest["schema_version"] == 6
    result = import_archive(database, fixture, dry_run=False)
    assert result["records"]["observations"] == 1
    assert database.execute("SELECT value FROM observations")[0][0] == 70
    assert [
        tuple(row)
        for row in database.execute("SELECT * FROM sleep_sessions ORDER BY id")
    ] == before
    assert not database.execute("SELECT * FROM provider_state")


def test_full_roundtrip_uses_source_revision_and_exclusion_or(
    database, target, tmp_path
):
    repository = SleepRepository(database, clock=lambda: NOW)
    value = session(
        revision=9223372036854775807,
        payload={
            "started_at": START,
            "ended_at": END,
            "start_offset_seconds": 0,
            "end_offset_seconds": 0,
            "start_zone": "UTC",
            "end_zone": "UTC",
            "reported_totals": {"asleep": 3_600_000_000},
            "stages": [stage()],
            "in_bed_intervals": [{"start": START, "end": END, "source_label": "inBed"}],
            "provenance": {
                "source_app": "Fixture",
                "source_device": "Watch",
                "algorithm": "fixture",
                "source_version": "1",
                "bridge_version": "1",
                "source_modified_at": END,
                "native_record_ids": ["b", "a"],
                "provider_confidence": {"value": "high", "scale": "vendor"},
            },
        },
    )
    stored = repository.apply_sleep_changes(
        [value, session(external_id="deleted", deleted=True)]
    )[0].session
    repository.set_excluded(
        stored.id, True, str(stored.source_revision), stored.payload_hash
    )
    path = tmp_path / "sleep.tar.gz"
    manifest = export_archive(database, path)
    assert set(manifest) == {
        "format",
        "format_version",
        "source_schema_version",
        "created_at",
        "files",
    }
    assert manifest["format_version"] == 2 and manifest["source_schema_version"] == 7
    preview = import_archive(target, path)
    assert preview["expected"]["sleep_sessions"]["create"] == 1
    assert preview["expected"]["sleep_sessions"]["deleted"] == 1
    assert target.execute("SELECT count(*) FROM sleep_sessions")[0][0] == 0
    result = import_archive(target, path, dry_run=False)
    assert result["applied"] == preview["expected"]
    target_record = target.execute(
        "SELECT * FROM sleep_sessions WHERE external_id='night'"
    )[0]
    assert target_record["source_revision"] == 9223372036854775807
    assert target_record["payload_hash"] == stored.payload_hash
    assert target_record["locally_excluded"] == 1
    assert json.loads(target_record["provenance"]) == stored.payload["provenance"]
    assert (
        import_archive(target, path, dry_run=False)["applied"]["sleep_sessions"][
            "unchanged"
        ]
        == 2
    )
    contents = gzip.decompress(path.read_bytes())
    assert b"first_ingested_at" not in contents and b"last_ingested_at" not in contents
    assert b'"source_revision":"9223372036854775807"' in contents


def test_stale_archive_merges_exclusion_without_resurrection(
    database, target, tmp_path
):
    source_repo = SleepRepository(database, clock=lambda: NOW)
    original = source_repo.apply_sleep_changes([session()])[0].session
    source_repo.set_excluded(original.id, True, "1", original.payload_hash)
    target_repo = SleepRepository(target, clock=lambda: NOW)
    target_repo.apply_sleep_changes([session(revision=3, deleted=True)])
    path = tmp_path / "old.tar.gz"
    export_archive(database, path)
    result = import_archive(target, path, dry_run=False)
    assert result["applied"]["sleep_sessions"]["stale"] == 1
    assert result["applied"]["sleep_sessions"]["exclusion_change"] == 1
    row = target.execute("SELECT * FROM sleep_sessions")[0]
    assert row["source_state"] == "deleted" and row["locally_excluded"] == 1
    assert row["source_revision"] == 3 and row["started_at"] is None


def test_conflict_in_preview_prevents_every_live_phase(database, target, tmp_path):
    SleepRepository(database, clock=lambda: NOW).apply_sleep_changes([session()])
    SleepRepository(target, clock=lambda: NOW).apply_sleep_changes(
        [
            session(
                payload={
                    "started_at": START,
                    "ended_at": END,
                    "reported_totals": {"asleep": 0},
                }
            )
        ]
    )
    path = tmp_path / "conflict.tar.gz"
    export_archive(database, path)
    before = [tuple(row) for row in target.execute("SELECT * FROM sleep_sessions")]
    calls = []
    with pytest.raises(StoreValidationError, match="revision_conflict"):
        import_archive(target, path, dry_run=False, after_batch=calls.append)
    assert calls == []
    assert [
        tuple(row) for row in target.execute("SELECT * FROM sleep_sessions")
    ] == before


def test_interrupted_sleep_batches_replay_to_same_result(database, target, tmp_path):
    repository = SleepRepository(database, clock=lambda: NOW)
    repository.apply_sleep_changes(
        [session(external_id=str(index)) for index in range(100)]
    )
    repository.apply_sleep_changes([session(external_id="last")])
    path = tmp_path / "large.tar.gz"
    export_archive(database, path)

    def interrupt(domain):
        if domain == "sleep_sessions":
            raise RuntimeError("synthetic interruption")

    with pytest.raises(RuntimeError):
        import_archive(target, path, dry_run=False, after_batch=interrupt)
    assert target.execute("SELECT count(*) FROM sleep_sessions")[0][0] == 100
    result = import_archive(target, path, dry_run=False)
    assert result["applied"]["sleep_sessions"]["unchanged"] == 100
    assert result["applied"]["sleep_sessions"]["create"] == 1
    assert target.execute("SELECT count(*) FROM sleep_sessions")[0][0] == 101


@pytest.mark.parametrize(
    "change",
    [
        {"payload_hash": None},
        {"payload_hash": "A" * 64},
        {"payload_hash": "0" * 64},
        {"source_revision": 9223372036854775807},
        {"hash_version": True},
        {"operation": "delete"},
        {"record_type": "recovery"},
        {"id": 1},
        {"locally_excluded": 1},
        {"person_id": "other"},
    ],
)
def test_archive_record_contract_rejects_invalid_fields(change):
    value = archive_session(session())
    with pytest.raises(StoreValidationError):
        parse_archive_session({**value, **change}, NOW)


def test_unknown_archive_layouts_are_rejected(database, tmp_path):
    manifest = export_archive(database, tmp_path / "history.tar.gz")
    for change in (
        {"source_schema_version": 8},
        {"source_schema_version": True},
        {"schema_version": 7},
        {"format_version": 3},
    ):
        with pytest.raises(StoreValidationError):
            validate_manifest({**manifest, **change})


def test_forged_sleep_record_fails_before_any_live_write(database, target, tmp_path):
    SleepRepository(database, clock=lambda: NOW).apply_sleep_changes([session()])
    path = tmp_path / "history.tar.gz"
    export_archive(database, path)
    with tarfile.open(path) as source:
        members = [(item.name, source.extractfile(item).read()) for item in source]
    payload = json.loads(members[-1][1])
    payload["payload"]["reported_totals"]["asleep"] = 0
    data = (json.dumps(payload) + "\n").encode()
    manifest = json.loads(members[0][1])
    manifest["files"]["sleep_sessions.jsonl"].update(
        bytes=len(data), sha256=hashlib.sha256(data).hexdigest()
    )
    members[0] = ("manifest.json", json.dumps(manifest).encode())
    members[-1] = ("sleep_sessions.jsonl", data)
    forged = tmp_path / "changed.tar.gz"
    with tarfile.open(forged, "w:gz") as output:
        for name, content in members:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            output.addfile(info, io.BytesIO(content))
    with pytest.raises(StoreValidationError, match="sleep_hash_mismatch"):
        import_archive(target, forged, dry_run=False)
    assert target.execute("SELECT count(*) FROM sleep_sessions")[0][0] == 0


def test_repository_revalidates_hash_and_local_exclusion(database):
    repository = SleepRepository(database, clock=lambda: NOW)
    for value in (
        replace(session(), payload_hash=None),
        replace(session(), payload_hash="0" * 64),
        replace(session(), locally_excluded=True),
    ):
        with pytest.raises(StoreValidationError):
            repository.apply_sleep_changes([value])
    assert database.execute("SELECT count(*) FROM sleep_sessions")[0][0] == 0
