import gzip
import hashlib
import io
import json
import tarfile
from dataclasses import replace
from pathlib import Path

import pytest
from test_recovery import END, NOW, START, observation

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
from custom_components.health_assistant.store.recovery import (
    RecoveryRepository,
    archive_observation,
    parse_archive_observation,
)


@pytest.fixture
def target(tmp_path):
    database = HealthDatabase(tmp_path / "target.sqlite")
    database.open()
    yield database
    database.close()


def test_released_archive_preserves_new_recovery_and_tombstones(database):
    repository = RecoveryRepository(database, clock=lambda: NOW)
    active, _tombstone = repository.apply_recovery_changes(
        [observation(), observation(external_id="deleted", deleted=True)]
    )
    repository.set_excluded(
        active.observation.id, True, "1", active.observation.payload_hash
    )
    before = [
        tuple(row)
        for row in database.execute("SELECT * FROM recovery_records ORDER BY id")
    ]
    fixture = Path(__file__).parents[1] / "fixtures/released-0.2-history.tar.gz"
    manifest = read_archive(fixture, lambda *_: None)
    assert manifest["format_version"] == 1 and manifest["schema_version"] == 6
    result = import_archive(database, fixture, dry_run=False)
    assert result["records"]["observations"] == 1
    assert database.execute("SELECT value FROM observations")[0][0] == 70
    assert [
        tuple(row)
        for row in database.execute("SELECT * FROM recovery_records ORDER BY id")
    ] == before
    assert not database.execute("SELECT * FROM provider_state")


def test_full_roundtrip_uses_source_revision_and_exclusion_or(
    database, target, tmp_path
):
    repository = RecoveryRepository(database, clock=lambda: NOW)
    value = observation(
        revision=9223372036854775807,
        payload={
            "started_at": START,
            "ended_at": END,
            "start_offset_seconds": 0,
            "end_offset_seconds": 0,
            "start_zone": "UTC",
            "end_zone": "UTC",
            "context": "sleep_summary",
            "algorithm_id": "fixture",
            "algorithm_version": "1",
            "provenance": {
                "source_app": "Fixture",
                "source_device": "Watch",
                "source_version": "1",
                "bridge_version": "1",
                "source_modified_at": END,
                "raw_value": 0.05,
                "raw_unit": "s",
            },
        },
    )
    stored = repository.apply_recovery_changes(
        [value, observation(external_id="deleted", deleted=True)]
    )[0].observation
    repository.set_excluded(
        stored.id, True, str(stored.source_revision), stored.payload_hash
    )
    path = tmp_path / "recovery.tar.gz"
    manifest = export_archive(database, path)
    assert set(manifest) == {
        "format",
        "format_version",
        "source_schema_version",
        "created_at",
        "files",
    }
    assert manifest["format_version"] == 2 and manifest["source_schema_version"] == 8
    preview = import_archive(target, path)
    assert preview["expected"]["recovery_records"]["create"] == 1
    assert preview["expected"]["recovery_records"]["deleted"] == 1
    assert target.execute("SELECT count(*) FROM recovery_records")[0][0] == 0
    result = import_archive(target, path, dry_run=False)
    assert result["applied"] == preview["expected"]
    target_record = target.execute(
        "SELECT * FROM recovery_records WHERE external_id='reading'"
    )[0]
    assert target_record["source_revision"] == 9223372036854775807
    assert target_record["payload_hash"] == stored.payload_hash
    assert target_record["locally_excluded"] == 1
    assert json.loads(target_record["provenance"]) == stored.payload["provenance"]
    assert (
        import_archive(target, path, dry_run=False)["applied"]["recovery_records"][
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
    source_repo = RecoveryRepository(database, clock=lambda: NOW)
    original = source_repo.apply_recovery_changes([observation()])[0].observation
    source_repo.set_excluded(original.id, True, "1", original.payload_hash)
    target_repo = RecoveryRepository(target, clock=lambda: NOW)
    target_repo.apply_recovery_changes([observation(revision=3, deleted=True)])
    path = tmp_path / "old.tar.gz"
    export_archive(database, path)
    result = import_archive(target, path, dry_run=False)
    assert result["applied"]["recovery_records"]["stale"] == 1
    assert result["applied"]["recovery_records"]["exclusion_change"] == 1
    row = target.execute("SELECT * FROM recovery_records")[0]
    assert row["source_state"] == "deleted" and row["locally_excluded"] == 1
    assert row["source_revision"] == 3 and row["started_at"] is None


def test_conflict_in_preview_prevents_every_live_phase(database, target, tmp_path):
    RecoveryRepository(database, clock=lambda: NOW).apply_recovery_changes(
        [observation()]
    )
    RecoveryRepository(target, clock=lambda: NOW).apply_recovery_changes(
        [
            observation(
                payload={
                    "started_at": START,
                    "ended_at": END,
                    "value": 51,
                    "unit": "ms",
                }
            )
        ]
    )
    path = tmp_path / "conflict.tar.gz"
    export_archive(database, path)
    before = [tuple(row) for row in target.execute("SELECT * FROM recovery_records")]
    calls = []
    with pytest.raises(StoreValidationError, match="revision_conflict"):
        import_archive(target, path, dry_run=False, after_batch=calls.append)
    assert calls == []
    assert [
        tuple(row) for row in target.execute("SELECT * FROM recovery_records")
    ] == before


def test_interrupted_recovery_batches_replay_to_same_result(database, target, tmp_path):
    repository = RecoveryRepository(database, clock=lambda: NOW)
    repository.apply_recovery_changes(
        [observation(external_id=str(index)) for index in range(100)]
    )
    repository.apply_recovery_changes([observation(external_id="last")])
    path = tmp_path / "large.tar.gz"
    export_archive(database, path)

    def interrupt(domain):
        if domain == "recovery_records":
            raise RuntimeError("synthetic interruption")

    with pytest.raises(RuntimeError):
        import_archive(target, path, dry_run=False, after_batch=interrupt)
    assert target.execute("SELECT count(*) FROM recovery_records")[0][0] == 100
    result = import_archive(target, path, dry_run=False)
    assert result["applied"]["recovery_records"]["unchanged"] == 100
    assert result["applied"]["recovery_records"]["create"] == 1
    assert target.execute("SELECT count(*) FROM recovery_records")[0][0] == 101


@pytest.mark.parametrize(
    "change",
    [
        {"payload_hash": None},
        {"payload_hash": "A" * 64},
        {"payload_hash": "0" * 64},
        {"source_revision": 9223372036854775807},
        {"hash_version": True},
        {"operation": "delete"},
        {"record_type": "unsupported"},
        {"id": 1},
        {"locally_excluded": 1},
        {"person_id": "other"},
    ],
)
def test_archive_record_contract_rejects_invalid_fields(change):
    value = archive_observation(observation())
    with pytest.raises(StoreValidationError):
        parse_archive_observation({**value, **change}, NOW)


def test_unknown_archive_layouts_are_rejected(database, tmp_path):
    manifest = export_archive(database, tmp_path / "history.tar.gz")
    for change in (
        {"source_schema_version": 9},
        {"source_schema_version": True},
        {"schema_version": 7},
        {"format_version": 3},
    ):
        with pytest.raises(StoreValidationError):
            validate_manifest({**manifest, **change})


def test_forged_recovery_record_fails_before_any_live_write(database, target, tmp_path):
    RecoveryRepository(database, clock=lambda: NOW).apply_recovery_changes(
        [observation()]
    )
    path = tmp_path / "history.tar.gz"
    export_archive(database, path)
    with tarfile.open(path) as source:
        members = [(item.name, source.extractfile(item).read()) for item in source]
    payload = json.loads(dict(members)["recovery_records.jsonl"])
    payload["payload"]["value"] = 51
    data = (json.dumps(payload) + "\n").encode()
    manifest = json.loads(members[0][1])
    manifest["files"]["recovery_records.jsonl"].update(
        bytes=len(data), sha256=hashlib.sha256(data).hexdigest()
    )
    members[0] = ("manifest.json", json.dumps(manifest).encode())
    members = [
        (name, data if name == "recovery_records.jsonl" else content)
        for name, content in members
    ]
    forged = tmp_path / "changed.tar.gz"
    with tarfile.open(forged, "w:gz") as output:
        for name, content in members:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            output.addfile(info, io.BytesIO(content))
    with pytest.raises(StoreValidationError, match="recovery_hash_mismatch"):
        import_archive(target, forged, dry_run=False)
    assert target.execute("SELECT count(*) FROM recovery_records")[0][0] == 0


def test_repository_revalidates_hash_and_local_exclusion(database):
    repository = RecoveryRepository(database, clock=lambda: NOW)
    for value in (
        replace(observation(), payload_hash=None),
        replace(observation(), payload_hash="0" * 64),
        replace(observation(), locally_excluded=True),
    ):
        with pytest.raises(StoreValidationError):
            repository.apply_recovery_changes([value])
    assert database.execute("SELECT count(*) FROM recovery_records")[0][0] == 0


def test_schema_seven_layout_leaves_recovery_unchanged(database, target, tmp_path):
    repository = RecoveryRepository(target, clock=lambda: NOW)
    stored = repository.apply_recovery_changes([observation()])[0].observation
    repository.set_excluded(stored.id, True, "1", stored.payload_hash)
    before = [tuple(row) for row in target.execute("SELECT * FROM recovery_records")]
    latest = tmp_path / "current.tar.gz"
    export_archive(database, latest)
    with tarfile.open(latest) as source:
        members = [
            (item.name, source.extractfile(item).read())
            for item in source
            if item.name != "recovery_records.jsonl"
        ]
    manifest = json.loads(members[0][1])
    manifest["source_schema_version"] = 7
    del manifest["files"]["recovery_records.jsonl"]
    members[0] = ("manifest.json", json.dumps(manifest).encode())
    previous = tmp_path / "schema-seven-layout.tar.gz"
    with tarfile.open(previous, "w:gz") as output:
        for name, content in members:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            output.addfile(info, io.BytesIO(content))
    result = import_archive(target, previous, dry_run=False)
    assert "recovery_records" not in result["records"]
    assert [
        tuple(row) for row in target.execute("SELECT * FROM recovery_records")
    ] == before
