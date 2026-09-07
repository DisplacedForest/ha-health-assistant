from __future__ import annotations

import gzip
import hashlib
import json
import os
import sqlite3
import tarfile
import zlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from .db import HealthDatabase
from .errors import StoreValidationError
from .interchange_formats import COMPATIBILITY, DOMAINS
from .schema import SCHEMA_VERSION

FORMAT_VERSION = 2
MAX_RECORD_BYTES = 1_048_576
MAX_EXPANDED_BYTES = 8_589_934_592
MAX_COMPRESSED_BYTES = 2_147_483_648
PAGE_SIZE = 256


def archive_domains(manifest):
    return tuple(
        COMPATIBILITY[
            (
                manifest["format_version"],
                manifest.get("source_schema_version", manifest.get("schema_version")),
            )
        ]
    )


ORDER = {
    "sleep_sessions": "id",
    "observations": "id",
    "source_claims": "id",
    "workouts": "id",
    "metric_priorities": "metric, context, rank",
    "environment_streams": "id",
    "environment_buckets": "stream_id, resolution_s, start_ms",
    "environment_maintenance": "id",
}


def encode_record(record: dict) -> bytes:
    try:
        data = (
            json.dumps(
                record, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            )
            + "\n"
        ).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as err:
        raise StoreValidationError("Archive record cannot be encoded") from err
    if len(data) > MAX_RECORD_BYTES:
        raise StoreValidationError("Archive record exceeds the 1 MiB limit")
    return data


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise StoreValidationError("Archive JSON contains a duplicate field")
        result[key] = value
    return result


def _constant(_value):
    raise StoreValidationError("Archive JSON contains a non-finite number")


def decode_record(data: bytes) -> dict:
    if len(data) > MAX_RECORD_BYTES:
        raise StoreValidationError("Archive record exceeds the 1 MiB limit")
    try:
        result = json.loads(data, object_pairs_hook=_object, parse_constant=_constant)
    except (ValueError, UnicodeError, RecursionError) as err:
        raise StoreValidationError("Archive record is not valid JSON") from err
    if not isinstance(result, dict):
        raise StoreValidationError("Archive records must be JSON objects")
    return result


def snapshot_records(connection, domain: str) -> Iterator[dict]:
    cursor = connection.execute(f"SELECT * FROM {domain} ORDER BY {ORDER[domain]}")
    try:
        while rows := cursor.fetchmany(PAGE_SIZE):
            for row in rows:
                if domain == "sleep_sessions":
                    from .sleep import archive_session, session_from_row

                    yield archive_session(session_from_row(row))
                    continue
                record = dict(row)
                if "provenance" in record:
                    record["provenance"] = json.loads(record["provenance"])
                yield record
    finally:
        cursor.close()


def export_archive(
    database: HealthDatabase, destination: Path, *, directory_fd: int | None = None
) -> dict:
    if directory_fd is None and destination.exists():
        raise StoreValidationError("Export destination already exists")
    with TemporaryDirectory(
        prefix="health-export-",
        dir=database.path.parent if directory_fd is not None else destination.parent,
    ) as directory:
        temporary = Path(directory)
        snapshot = temporary / "snapshot.sqlite"
        database.backup(snapshot)
        connection = sqlite3.connect(snapshot)
        connection.row_factory = sqlite3.Row
        manifest = {
            "format": "health-assistant",
            "format_version": FORMAT_VERSION,
            "source_schema_version": SCHEMA_VERSION,
            "created_at": datetime.now(UTC).isoformat(timespec="microseconds"),
            "files": {},
        }
        total = 0
        try:
            for domain in DOMAINS:
                filename = f"{domain}.jsonl"
                digest = hashlib.sha256()
                count = size = 0
                with (temporary / filename).open("wb") as output:
                    for record in snapshot_records(connection, domain):
                        data = encode_record(record)
                        count += 1
                        size += len(data)
                        total += len(data)
                        if total > MAX_EXPANDED_BYTES:
                            raise StoreValidationError(
                                "Archive exceeds the 8 GiB expanded limit"
                            )
                        digest.update(data)
                        output.write(data)
                manifest["files"][filename] = {
                    "records": count,
                    "bytes": size,
                    "sha256": digest.hexdigest(),
                }
        finally:
            connection.close()
        (temporary / "manifest.json").write_bytes(encode_record(manifest))
        archive_path = temporary / "history.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            for filename in (
                "manifest.json",
                *(f"{domain}.jsonl" for domain in DOMAINS),
            ):
                path = temporary / filename
                header = tarfile.TarInfo(filename)
                header.size = path.stat().st_size
                header.mode = 0o600
                with path.open("rb") as source:
                    archive.addfile(header, source)
        if archive_path.stat().st_size > MAX_COMPRESSED_BYTES:
            raise StoreValidationError("Archive exceeds the 2 GiB compressed limit")
        os.chmod(archive_path, 0o600)
        try:
            os.link(
                archive_path,
                destination.name if directory_fd is not None else destination,
                dst_dir_fd=directory_fd,
            )
        except FileExistsError as err:
            raise StoreValidationError("Export destination already exists") from err
        return manifest


def validate_manifest(manifest: dict) -> None:
    version = manifest.get("format_version")
    if type(version) is not int or version not in (1, 2):
        raise StoreValidationError("Unsupported archive format version")
    schema_key = "schema_version" if version == 1 else "source_schema_version"
    if set(manifest) != {"format", "format_version", schema_key, "created_at", "files"}:
        raise StoreValidationError("Archive manifest fields are invalid")
    if manifest["format"] != "health-assistant":
        raise StoreValidationError("Unsupported archive format")
    schema = manifest[schema_key]
    if type(schema) is not int or (version, schema) not in COMPATIBILITY:
        raise StoreValidationError("Unsupported archive schema version")
    try:
        created = datetime.fromisoformat(manifest["created_at"])
        if created.tzinfo is None:
            raise ValueError
    except (ValueError, TypeError) as err:
        raise StoreValidationError("Archive creation timestamp is invalid") from err
    files = manifest["files"]
    if not isinstance(files, dict) or set(files) != {
        f"{domain}.jsonl" for domain in archive_domains(manifest)
    }:
        raise StoreValidationError("Archive domain files are missing or unsupported")
    total = 0
    for metadata in files.values():
        if not isinstance(metadata, dict) or set(metadata) != {
            "records",
            "bytes",
            "sha256",
        }:
            raise StoreValidationError("Archive file metadata is invalid")
        for key in ("records", "bytes"):
            if type(metadata[key]) is not int or metadata[key] < 0:
                raise StoreValidationError("Archive file counts are invalid")
        digest = metadata["sha256"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise StoreValidationError("Archive checksum is invalid")
        total += metadata["bytes"]
    if total > MAX_EXPANDED_BYTES:
        raise StoreValidationError("Archive exceeds the 8 GiB expanded limit")


class _BoundedReader:
    def __init__(self, source):
        self.source = source
        self.read_bytes = 0

    def read(self, size):
        remaining = MAX_EXPANDED_BYTES + MAX_RECORD_BYTES + 32768 - self.read_bytes
        data = self.source.read(min(size, remaining + 1))
        self.read_bytes += len(data)
        if len(data) > remaining:
            raise StoreValidationError("Archive exceeds the expanded byte limit")
        return data


class _ArchiveMember(tarfile.TarInfo):
    def _proc_member(self, archive):
        if self.type not in (tarfile.REGTYPE, tarfile.AREGTYPE):
            raise StoreValidationError("Archive members must be plain regular files")
        return super()._proc_member(archive)


def read_archive(path: Path, consume) -> dict:
    if path.stat().st_size > MAX_COMPRESSED_BYTES:
        raise StoreValidationError("Archive exceeds the 2 GiB compressed limit")
    try:
        with (
            path.open("rb") as compressed,
            gzip.GzipFile(fileobj=compressed) as expanded,
        ):
            bounded = _BoundedReader(expanded)
            with tarfile.open(
                fileobj=bounded, mode="r|", tarinfo=_ArchiveMember
            ) as archive:
                header = archive.next()
                if (
                    header is None
                    or header.name != "manifest.json"
                    or not header.isfile()
                    or header.size > MAX_RECORD_BYTES
                ):
                    raise StoreValidationError(
                        "Archive must start with a valid manifest"
                    )
                with archive.extractfile(header) as source:
                    manifest = decode_record(source.read(MAX_RECORD_BYTES + 1))
                validate_manifest(manifest)
                for domain in archive_domains(manifest):
                    filename = f"{domain}.jsonl"
                    header = archive.next()
                    metadata = manifest["files"][filename]
                    if (
                        header is None
                        or header.name != filename
                        or not header.isfile()
                        or header.size != metadata["bytes"]
                    ):
                        raise StoreValidationError(
                            f"Archive domain {domain} is missing or invalid"
                        )
                    digest = hashlib.sha256()
                    count = size = 0
                    with archive.extractfile(header) as source:
                        while data := source.readline(MAX_RECORD_BYTES + 1):
                            count += 1
                            size += len(data)
                            digest.update(data)
                            if not data.endswith(b"\n"):
                                raise StoreValidationError(
                                    f"Archive domain {domain} has an incomplete record"
                                )
                            try:
                                record = decode_record(data)
                                layout = COMPATIBILITY[
                                    (
                                        manifest["format_version"],
                                        manifest.get(
                                            "source_schema_version",
                                            manifest.get("schema_version"),
                                        ),
                                    )
                                ]
                                if set(record) != layout[domain]:
                                    raise StoreValidationError(
                                        "Record fields do not match the source format"
                                    )
                                consume(domain, record)
                            except StoreValidationError as err:
                                raise StoreValidationError(
                                    f"Archive domain {domain}, record {count}: {err}"
                                ) from err
                    if (
                        count != metadata["records"]
                        or size != metadata["bytes"]
                        or digest.hexdigest() != metadata["sha256"]
                    ):
                        raise StoreValidationError(
                            f"Archive domain {domain} checksum or count mismatch"
                        )
                if archive.next() is not None:
                    raise StoreValidationError("Archive contains an unexpected member")
                while padding := archive.fileobj.read(65_536):
                    if padding.strip(b"\0"):
                        raise StoreValidationError(
                            "Archive contains data after its end marker"
                        )
    except (
        tarfile.TarError,
        gzip.BadGzipFile,
        EOFError,
        UnicodeError,
        zlib.error,
    ) as err:
        raise StoreValidationError("Archive is truncated or malformed") from err
    return manifest
