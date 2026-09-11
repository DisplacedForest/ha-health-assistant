import gzip
import json
from pathlib import Path

import pytest

from custom_components.health_assistant.store import StoreValidationError
from custom_components.health_assistant.store.interchange_archive import (
    DOMAINS,
    MAX_RECORD_BYTES,
    decode_record,
    encode_record,
    export_archive,
    read_archive,
    validate_manifest,
)


def test_archive_empty_roundtrip_and_no_clobber(database, tmp_path):
    archive = tmp_path / "history.tar.gz"
    manifest = export_archive(database, archive)
    records = []
    loaded = read_archive(
        archive, lambda domain, record: records.append((domain, record))
    )
    assert loaded == manifest
    assert set(manifest["files"]) == {f"{domain}.jsonl" for domain in DOMAINS}
    assert records == [
        (
            "environment_maintenance",
            {
                "id": 1,
                "last_success_ms": None,
                "duration_ms": None,
                "rolled_up": 0,
                "deleted": 0,
                "failed": 0,
            },
        )
    ]
    original = archive.read_bytes()
    with pytest.raises(StoreValidationError, match="already exists"):
        export_archive(database, archive)
    assert archive.read_bytes() == original
    assert archive.stat().st_mode & 0o777 == 0o600


def test_archive_checks_gzip_integrity_after_tar_end(database, tmp_path):
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)
    archive.write_bytes(archive.read_bytes()[:-4])
    with pytest.raises(StoreValidationError, match="truncated|malformed"):
        read_archive(archive, lambda *_: None)


@pytest.mark.parametrize("data", [b'{"x":1,"x":2}', b'{"x":NaN}', b"[]", b"{", b"\xff"])
def test_strict_archive_json(data):
    with pytest.raises(StoreValidationError):
        decode_record(data)


def test_archive_record_memory_bound():
    with pytest.raises(StoreValidationError, match="1 MiB"):
        encode_record({"value": "a" * MAX_RECORD_BYTES})
    with pytest.raises(StoreValidationError, match="1 MiB"):
        decode_record(b" " * (MAX_RECORD_BYTES + 1))


def test_manifest_rejects_future_and_boolean_versions(database, tmp_path):
    manifest = export_archive(database, tmp_path / "history.tar.gz")
    for version in (True, 3, "1"):
        manifest["format_version"] = version
        with pytest.raises(StoreValidationError, match="format version"):
            validate_manifest(manifest)


def test_archive_checks_content_digest(database, tmp_path):
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)
    data = gzip.decompress(archive.read_bytes()).replace(b'"failed":0', b'"failed":1')
    archive.write_bytes(gzip.compress(data))
    with pytest.raises(StoreValidationError, match="checksum"):
        read_archive(archive, lambda *_: None)


def test_export_excludes_provider_runtime_state(database, tmp_path):
    database.execute(
        "INSERT INTO provider_state VALUES (?, ?, ?)",
        ("private", json.dumps({"token": "not-exported"}), "2026-09-06T00:00:00+00:00"),
    )
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)
    assert b"not-exported" not in gzip.decompress(archive.read_bytes())
    assert not any(
        path.name.startswith("health-export-") for path in Path(tmp_path).iterdir()
    )


def test_stage_reconstructs_canonical_claims_without_touching_source(
    database, repository, tmp_path
):
    from datetime import UTC, datetime, timedelta

    from custom_components.health_assistant.store import HealthObservation, MetricType
    from custom_components.health_assistant.store.interchange_staging import (
        validate_archive,
    )

    now = datetime(2026, 9, 6, 12, tzinfo=UTC)
    for provider, value, seconds in (
        ("scale", 80, 0),
        ("watch", 80.1, 30),
        ("other", 99, 60),
    ):
        repository.upsert_observation(
            HealthObservation(
                person_id="primary",
                metric=MetricType.WEIGHT,
                value=value,
                unit="kg",
                observed_at=now + timedelta(seconds=seconds),
                provider=provider,
                external_id="record",
                ingested_at=now,
                provenance={"nested": {"original": True}},
            )
        )
    repository.set_priority(MetricType.WEIGHT, ["scale", "watch", "other"])
    first = repository.latest_observation("primary", MetricType.WEIGHT)
    repository.set_observation_excluded("primary", first.id, True)
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)
    staged, manifest = validate_archive(archive, tmp_path / "staging.sqlite")
    try:
        assert manifest["files"]["source_claims.jsonl"]["records"] == 3
        for table in ("observations", "source_claims", "metric_priorities"):
            expected = [dict(row) for row in database.execute(f"SELECT * FROM {table}")]
            actual = [dict(row) for row in staged.execute(f"SELECT * FROM {table}")]
            for rows in (expected, actual):
                for row in rows:
                    if "provenance" in row:
                        row["provenance"] = json.loads(row["provenance"])
            assert actual == expected
    finally:
        staged.close()


def rewrite_archive(path, transform):
    import hashlib
    import io
    import tarfile

    with tarfile.open(path, "r:gz") as archive:
        contents = {
            member.name: archive.extractfile(member).read() for member in archive
        }
    manifest = json.loads(contents["manifest.json"])
    for domain in DOMAINS:
        name = f"{domain}.jsonl"
        records = [json.loads(line) for line in contents[name].splitlines()]
        transform(domain, records)
        data = b"".join(encode_record(record) for record in records)
        contents[name] = data
        manifest["files"][name] = {
            "records": len(records),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    contents["manifest.json"] = encode_record(manifest)
    with tarfile.open(path, "w:gz") as archive:
        for name, data in contents.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))


@pytest.mark.parametrize(
    "domain,key,value",
    [
        ("source_claims", "observation_id", 999),
        ("observations", "value", 10),
        ("environment_buckets", "stream_id", 999),
        ("environment_buckets", "covered_ms", 300001),
        ("environment_maintenance", "failed", 3),
    ],
)
def test_invalid_late_domains_never_change_live_store(
    database, repository, tmp_path, domain, key, value
):
    from test_interchange import logical, populate

    from custom_components.health_assistant.store import HealthDatabase
    from custom_components.health_assistant.store.interchange import import_archive

    populate(database, repository)
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)

    def transform(name, records):
        if name == domain:
            records[0][key] = value

    rewrite_archive(archive, transform)
    target = HealthDatabase(tmp_path / "target.sqlite")
    target.open()
    try:
        before = logical(target)
        with pytest.raises(StoreValidationError):
            import_archive(target, archive, dry_run=False)
        assert logical(target) == before
    finally:
        target.close()


def test_non_regular_archive_member_is_rejected(database, tmp_path):
    import io
    import tarfile

    archive = tmp_path / "history.tar.gz"
    manifest = export_archive(database, archive)
    with tarfile.open(archive, "w:gz") as output:
        data = encode_record(manifest)
        member = tarfile.TarInfo("manifest.json")
        member.size = len(data)
        output.addfile(member, io.BytesIO(data))
        member = tarfile.TarInfo("observations.jsonl")
        member.type = tarfile.SYMTYPE
        member.linkname = "../../outside"
        output.addfile(member)
    with pytest.raises(StoreValidationError):
        read_archive(archive, lambda *_: None)


def test_export_snapshot_stays_consistent_while_ingestion_continues(
    database, repository, tmp_path, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor
    from datetime import UTC, datetime

    from custom_components.health_assistant.store import (
        HealthObservation,
        MetricType,
        interchange_archive,
    )

    original = interchange_archive.snapshot_records

    def write():
        repository.upsert_observation(
            HealthObservation(
                person_id="primary",
                metric=MetricType.WEIGHT,
                value=80,
                unit="kg",
                observed_at=datetime(2026, 9, 6, tzinfo=UTC),
                provider="manual",
                external_id="after-snapshot",
                ingested_at=datetime(2026, 9, 6, tzinfo=UTC),
            )
        )

    def records(connection, domain, snapshot_at=None):
        if domain == "observations":
            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(write).result(timeout=5)
        yield from original(connection, domain, snapshot_at)

    monkeypatch.setattr(interchange_archive, "snapshot_records", records)
    manifest = export_archive(database, tmp_path / "history.tar.gz")
    assert manifest["files"]["observations.jsonl"]["records"] == 0
    assert manifest["files"]["source_claims.jsonl"]["records"] == 0
    assert len(database.execute("SELECT * FROM observations")) == 1
    assert len(database.execute("SELECT * FROM source_claims")) == 1


@pytest.mark.parametrize("kind", [b"x", b"g", b"L", b"K", b"S"])
def test_extended_headers_are_rejected_before_payload_allocation(tmp_path, kind):
    import tarfile

    archive = tmp_path / "invalid.tar.gz"
    header = tarfile.TarInfo("extension")
    header.type = kind
    header.size = 1024 * 1024 * 1024
    archive.write_bytes(gzip.compress(header.tobuf()))
    with pytest.raises(StoreValidationError, match="plain regular files"):
        read_archive(archive, lambda *_: None)


def test_hidden_data_after_tar_end_is_rejected(database, tmp_path):
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)
    archive.write_bytes(
        gzip.compress(gzip.decompress(archive.read_bytes()) + b"hidden")
    )
    with pytest.raises(StoreValidationError, match="after its end"):
        read_archive(archive, lambda *_: None)
