from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from .db import HealthDatabase
from .errors import StoreValidationError
from .interchange_archive import DOMAINS, MAX_COMPRESSED_BYTES, export_archive
from .interchange_replay import replay_archive
from .interchange_staging import validate_archive

__all__ = ["export_archive", "import_archive"]


def import_archive(
    database: HealthDatabase,
    archive: Path,
    *,
    dry_run=True,
    after_batch=None,
    source_file=None,
):
    with TemporaryDirectory(
        prefix="health-import-", dir=database.path.parent
    ) as directory:
        temporary = Path(directory)
        copied = temporary / "archive.tar.gz"
        source_context = (
            archive.open("rb") if source_file is None else nullcontext(source_file)
        )
        with source_context as source, copied.open("wb") as target:
            total = 0
            while data := source.read(65_536):
                total += len(data)
                if total > MAX_COMPRESSED_BYTES:
                    raise StoreValidationError(
                        "Archive exceeds the 2 GiB compressed limit"
                    )
                target.write(data)
        staging, manifest = validate_archive(copied, temporary / "archive.sqlite")
        try:
            preview_path = temporary / "preview.sqlite"
            database.backup(preview_path)
            preview = HealthDatabase(preview_path)
            preview.open()
            try:
                before = preview.execute("SELECT count(*) AS count FROM observations")[
                    0
                ]["count"]
                expected = replay_archive(staging, preview)
                after = preview.execute("SELECT count(*) AS count FROM observations")[
                    0
                ]["count"]
            finally:
                preview.close()
            summary = _summary(staging, manifest)
            summary.update(
                {
                    "dry_run": dry_run,
                    "expected": expected,
                    "canonical_observations_before": before,
                    "canonical_observations_after": after,
                }
            )
            if not dry_run:
                summary["applied"] = replay_archive(
                    staging, database, after_batch=after_batch
                )
            return summary
        finally:
            staging.close()


def _summary(staging, manifest):
    sources_sql = "SELECT provider AS source FROM source_claims UNION SELECT provider FROM workouts UNION SELECT source_id FROM environment_streams"
    sources = [
        row["source"]
        for row in staging.execute(
            f"SELECT substr(source,1,256) AS source FROM ({sources_sql}) ORDER BY source LIMIT 100"
        )
    ]
    source_count = staging.execute(f"SELECT count(*) AS count FROM ({sources_sql})")[0][
        "count"
    ]
    times_sql = "SELECT observed_at AS first, observed_at AS last FROM source_claims UNION ALL SELECT started_at, ended_at FROM workouts"
    span = staging.execute(
        f"SELECT min(first) AS first, max(last) AS last FROM ({times_sql})"
    )[0]
    first, last = span["first"], span["last"]
    environment = staging.execute(
        "SELECT min(start_ms) AS first, max(start_ms+resolution_s*1000) AS last FROM environment_buckets"
    )[0]
    if environment["first"] is not None:
        environmental_first = datetime.fromtimestamp(
            environment["first"] / 1000, UTC
        ).isoformat(timespec="microseconds")
        environmental_last = datetime.fromtimestamp(
            environment["last"] / 1000, UTC
        ).isoformat(timespec="microseconds")
        first = min(first, environmental_first) if first else environmental_first
        last = max(last, environmental_last) if last else environmental_last
    return {
        "format_version": manifest["format_version"],
        "archive_created_at": manifest["created_at"],
        "records": {
            domain: manifest["files"][f"{domain}.jsonl"]["records"]
            for domain in DOMAINS
        },
        "date_span": {"first": first, "last": last},
        "sources": sources,
        "source_count": source_count,
        "sources_truncated": source_count > len(sources),
        "source_labels_truncated": bool(
            staging.execute(
                f"SELECT 1 FROM ({sources_sql}) WHERE length(source)>256 LIMIT 1"
            )
        ),
        "imports_priorities": True,
    }
