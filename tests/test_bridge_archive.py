from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import tarfile
from datetime import timedelta

import pytest

from custom_components.health_assistant.store.bridge_models import BridgeError
from custom_components.health_assistant.store.db import HealthDatabase
from custom_components.health_assistant.store.errors import StoreValidationError
from custom_components.health_assistant.store.interchange import (
    export_archive,
    import_archive,
)
from tests.test_bridge import NOW, ingest, native_record


@pytest.fixture
def target(tmp_path):
    database = HealthDatabase(tmp_path / "target.sqlite")
    database.open()
    yield database
    database.close()


def rewrite(source, destination, edit):
    with tarfile.open(source) as archive:
        parts = {item.name: archive.extractfile(item).read() for item in archive}
    manifest = json.loads(parts["manifest.json"])
    edit(parts, manifest)
    for name, data in parts.items():
        if name == "manifest.json":
            continue
        manifest["files"][name] = {
            "records": len(data.splitlines()),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    parts["manifest.json"] = json.dumps(manifest).encode()
    with tarfile.open(destination, "w:gz") as archive:
        for name, data in parts.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))


def test_bridge_roundtrip_projections_tombstones_and_no_permissions(
    bridge, target, tmp_path
):
    repository, source_id = bridge
    ingest(
        repository,
        source_id,
        [native_record(source_id), native_record(source_id, "deleted", delete=True)],
    )
    repository.database.execute(
        "UPDATE bridge_records SET first_ingested_at='2026-09-10T23:00:00.000000Z'"
    )
    archive = tmp_path / "history.tar.gz"
    manifest = export_archive(repository.database, archive)
    assert manifest["source_schema_version"] == 9
    preview = import_archive(target, archive)
    assert preview["expected"]["bridge_records"]["changed"] == 2
    assert not target.execute("SELECT * FROM bridge_sources")
    import_archive(target, archive, dry_run=False)
    source = target.execute("SELECT * FROM bridge_sources")[0]
    assert source["origin_mode"] == "imported_history" and source["owner_id"] is None
    assert not target.execute("SELECT * FROM bridge_receipts")
    assert target.execute("SELECT count(*) FROM bridge_records")[0][0] == 2
    assert target.execute("SELECT count(*) FROM source_claims")[0][0] == 1
    assert (
        target.execute("SELECT first_ingested_at FROM bridge_records LIMIT 1")[0][0]
        == "2026-09-10T23:00:00.000000Z"
    )
    result = import_archive(target, archive, dry_run=False)
    assert result["applied"]["bridge_records"]["unchanged"] == 2
    exported = tmp_path / "again.tar.gz"
    export_archive(target, exported)
    assert (
        import_archive(target, exported)["expected"]["bridge_records"]["unchanged"] == 2
    )


@pytest.mark.parametrize(
    "change",
    ["missing_source", "projection_value", "deleted_projection", "ingested_time"],
)
def test_complete_graph_preflight_rejects_no_target_mutation(
    bridge, target, tmp_path, change
):
    repository, source_id = bridge
    ingest(repository, source_id, [native_record(source_id)])
    archive = tmp_path / "history.tar.gz"
    export_archive(repository.database, archive)

    def edit(parts, manifest):
        if change == "missing_source":
            parts["bridge_sources.jsonl"] = b""
            return
        domain = (
            "bridge_records.jsonl"
            if change == "deleted_projection"
            else "source_claims.jsonl"
        )
        value = json.loads(parts[domain])
        if change == "deleted_projection":
            deletion = native_record(source_id, delete=True)
            value.update(
                source_state="deleted",
                payload=None,
                payload_hash=deletion["payload_hash"],
            )
        elif change == "projection_value":
            value["value"] = 900
        else:
            value["ingested_at"] = "2026-09-10T00:00:00+00:00"
        parts[domain] = json.dumps(value).encode() + b"\n"

    invalid = tmp_path / "invalid.tar.gz"
    rewrite(archive, invalid, edit)
    with pytest.raises(StoreValidationError):
        import_archive(target, invalid, dry_run=False)
    assert not target.execute("SELECT * FROM bridge_sources")
    assert not target.execute("SELECT * FROM source_claims")


def test_imported_higher_revision_merges_bookkeeping_and_marks_local_source(
    bridge, tmp_path
):
    repository, source_id = bridge
    ingest(repository, source_id, [native_record(source_id)])
    destination_path = tmp_path / "restored.sqlite"
    repository.database.backup(destination_path)
    destination = HealthDatabase(destination_path)
    destination.open()
    try:
        correction = native_record(source_id, revision=2, value=82)
        from tests.test_bridge import native_batch

        repository.apply_batch(
            source_id,
            native_batch(source_id, [correction]),
            NOW + timedelta(hours=1),
            lambda: None,
        )
        destination.execute(
            "UPDATE bridge_records SET first_ingested_at='2026-09-11T02:00:00.000000Z',last_ingested_at='2026-09-11T02:00:00.000000Z'"
        )
        destination.execute(
            "UPDATE source_claims SET ingested_at='2026-09-11T02:00:00.000000+00:00'"
        )
        destination.execute(
            "UPDATE observations SET ingested_at='2026-09-11T02:00:00.000000+00:00'"
        )
        archive = tmp_path / "corrected.tar.gz"
        export_archive(repository.database, archive)
        import_archive(destination, archive, dry_run=False)
        row = destination.execute("SELECT * FROM bridge_records")[0]
        assert row["first_ingested_at"] == "2026-09-11T00:00:00.000000Z"
        assert row["last_ingested_at"] == "2026-09-11T02:00:00.000000Z"
        assert row["source_revision"] == 2
        assert (
            destination.execute("SELECT needs_fresh_namespace FROM bridge_sources")[0][
                0
            ]
            == 1
        )
        export_archive(destination, tmp_path / "merged.tar.gz")
        assert (
            import_archive(destination, tmp_path / "merged.tar.gz")["expected"][
                "bridge_records"
            ]["unchanged"]
            == 1
        )
    finally:
        destination.close()


def test_descriptor_only_conflict_rejected_and_unknown_not_allocated(
    bridge, target, tmp_path
):
    repository, _source_id = bridge
    archive = tmp_path / "source-only.tar.gz"
    export_archive(repository.database, archive)
    assert (
        import_archive(target, archive, dry_run=False)["applied"]["bridge_sources"][
            "unchanged"
        ]
        == 1
    )
    assert not target.execute("SELECT * FROM bridge_sources")
    invalid = tmp_path / "conflicting.tar.gz"

    def edit(parts, manifest):
        source = json.loads(parts["bridge_sources.jsonl"])
        source["upstream_scope"] = "different-account"
        parts["bridge_sources.jsonl"] = json.dumps(source).encode() + b"\n"

    rewrite(archive, invalid, edit)
    with pytest.raises(BridgeError, match="identity_conflict"):
        import_archive(repository.database, invalid, dry_run=False)


def test_source_insert_and_first_record_are_atomic_on_live_failure(
    bridge, target, tmp_path, monkeypatch
):
    repository, source_id = bridge
    ingest(repository, source_id, [native_record(source_id)])
    archive = tmp_path / "history.tar.gz"
    export_archive(repository.database, archive)
    original = target.execute

    def fail(sql, params=()):
        if "INSERT INTO bridge_records" in sql:
            raise sqlite3.IntegrityError("fixture final insert failure")
        return original(sql, params)

    monkeypatch.setattr(target, "execute", fail)
    with pytest.raises(sqlite3.IntegrityError):
        import_archive(target, archive, dry_run=False)
    assert not target.execute("SELECT * FROM bridge_sources")
    assert not target.execute("SELECT * FROM source_claims")


def test_stale_content_exclusion_merge_does_not_invalidate_namespace(bridge, tmp_path):
    repository, source_id = bridge
    ingest(repository, source_id, [native_record(source_id)])
    repository.health.set_observation_excluded("primary", 1, True)
    archive = tmp_path / "excluded.tar.gz"
    export_archive(repository.database, archive)
    repository.health.set_observation_excluded("primary", 1, False)
    ingest(repository, source_id, [native_record(source_id, revision=2, value=82)])
    import_archive(repository.database, archive, dry_run=False)
    assert repository.database.execute(
        "SELECT source_revision,locally_excluded FROM bridge_records"
    )[0][:] == (2, 1)
    assert (
        repository.database.execute("SELECT needs_fresh_namespace FROM bridge_sources")[
            0
        ][0]
        == 0
    )


def test_interrupted_bridge_batches_keep_completed_work_and_retry_converges(
    bridge, target, tmp_path
):
    repository, source_id = bridge
    for start in (0, 100):
        ingest(
            repository,
            source_id,
            [
                native_record(source_id, f"record-{index:03}")
                for index in range(start, min(start + 100, 150))
            ],
        )
    archive = tmp_path / "batches.tar.gz"
    export_archive(repository.database, archive)

    def interrupt(domain):
        if domain == "bridge_records":
            raise RuntimeError("fixture interruption")

    with pytest.raises(RuntimeError, match="fixture interruption"):
        import_archive(target, archive, dry_run=False, after_batch=interrupt)
    assert target.execute("SELECT count(*) FROM bridge_records")[0][0] == 100
    assert target.execute("SELECT count(*) FROM bridge_sources")[0][0] == 1
    result = import_archive(target, archive, dry_run=False)
    assert result["applied"]["bridge_records"] == {
        "changed": 50,
        "unchanged": 100,
        "stale": 0,
    }
    assert target.execute("SELECT count(*) FROM bridge_records")[0][0] == 150


def test_legacy_layout_cannot_bypass_bridge_ledger(bridge, target, tmp_path):
    repository, source_id = bridge
    ingest(repository, source_id, [native_record(source_id)])
    archive = tmp_path / "current.tar.gz"
    export_archive(repository.database, archive)

    def edit(parts, manifest):
        manifest["source_schema_version"] = 8
        for domain in ("bridge_sources.jsonl", "bridge_records.jsonl"):
            del parts[domain]
            del manifest["files"][domain]

    previous = tmp_path / "previous.tar.gz"
    rewrite(archive, previous, edit)
    with pytest.raises(BridgeError, match="unsupported_namespace"):
        import_archive(target, previous, dry_run=False)
    assert not target.execute("SELECT * FROM bridge_sources")
    assert not target.execute("SELECT * FROM source_claims")
