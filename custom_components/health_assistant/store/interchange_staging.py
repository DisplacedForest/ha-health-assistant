from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .db import HealthDatabase
from .errors import StoreValidationError
from .interchange_archive import PAGE_SIZE, read_archive
from .interchange_validation import validate_record
from .repository import HealthRepository


def rows_by_id(database, table, after=0):
    while rows := database.execute(
        f"SELECT * FROM {table} WHERE id > ? ORDER BY id LIMIT ?", (after, PAGE_SIZE)
    ):
        for row in rows:
            yield dict(row)
        after = rows[-1]["id"]


def validate_archive(path: Path, staging_path: Path):
    staging = HealthDatabase(staging_path)
    staging.open()
    staging.execute("DELETE FROM environment_maintenance")
    try:

        def consume(domain, record):
            if domain == "bridge_sources":
                from .bridge_models import source_descriptor

                value = {**source_descriptor(record), "origin_mode": "imported_history"}
            elif domain == "bridge_records":
                from .bridge_archive import parse_record

                value = parse_record(record, datetime.now(UTC))
            elif domain == "sleep_sessions":
                from .sleep import parse_archive_session, session_columns

                now = datetime.now(UTC)
                value = session_columns(parse_archive_session(record, now), now)
            elif domain == "recovery_records":
                from .recovery import observation_columns, parse_archive_observation

                now = datetime.now(UTC)
                value = observation_columns(parse_archive_observation(record, now), now)
            else:
                value = validate_record(domain, record)
            if "provenance" in value and domain not in (
                "sleep_sessions",
                "recovery_records",
            ):
                value["provenance"] = json.dumps(
                    value["provenance"],
                    sort_keys=True,
                    allow_nan=False,
                )
            columns = list(value)
            sql = f"INSERT INTO {domain} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})"
            try:
                staging.execute(sql, (value[column] for column in columns))
            except (sqlite3.IntegrityError, OverflowError) as err:
                raise StoreValidationError(
                    "Duplicate identity or invalid domain reference"
                ) from err

        with staging.transaction():
            manifest = read_archive(path, consume)
            from .bridge_archive import validate_graph

            validate_graph(staging, manifest)
            _validate_relations(staging)
            _validate_canonical(staging)
        return staging, manifest
    except BaseException:
        staging.close()
        raise


def _validate_relations(staging):
    checks = (
        (
            "SELECT 1 FROM environment_buckets b JOIN environment_streams s ON s.id=b.stream_id WHERE (s.metric='temperature' AND b.minimum < -273.15) OR (s.metric='humidity' AND (b.minimum < 0 OR b.maximum > 100)) OR (s.metric='co2' AND b.minimum < 0) LIMIT 1",
            "Environmental extrema exceed the supported metric range",
        ),
        (
            "SELECT 1 FROM source_claims c LEFT JOIN observations o ON o.id=c.observation_id WHERE o.id IS NULL OR o.person_id!=c.person_id OR o.metric!=c.metric OR o.status!=c.status LIMIT 1",
            "Claim references do not match canonical observations",
        ),
        (
            "SELECT 1 FROM observations o LEFT JOIN source_claims c ON c.observation_id=o.id WHERE c.id IS NULL LIMIT 1",
            "Canonical observation has no source claim",
        ),
        (
            "SELECT 1 FROM metric_priorities GROUP BY metric, context HAVING min(rank)!=0 OR max(rank)!=count(*)-1 LIMIT 1",
            "Priority ranks are not contiguous",
        ),
        (
            "SELECT 1 FROM environment_buckets b LEFT JOIN environment_streams s ON s.id=b.stream_id WHERE s.id IS NULL LIMIT 1",
            "Environmental stream reference is missing",
        ),
        (
            "SELECT 1 FROM environment_buckets fine JOIN environment_buckets coarse ON fine.stream_id=coarse.stream_id AND coarse.resolution_s=3600 AND coarse.start_ms=(fine.start_ms/3600000)*3600000 WHERE fine.resolution_s=300 LIMIT 1",
            "Environmental resolutions overlap",
        ),
        (
            "SELECT 1 WHERE (SELECT count(*) FROM environment_streams)>256",
            "Environmental stream registry limit exceeded",
        ),
        (
            "SELECT 1 WHERE (SELECT count(*) FROM environment_maintenance)!=1",
            "Environmental retention state is missing",
        ),
    )
    for sql, message in checks:
        if staging.execute(sql):
            raise StoreValidationError(message)


def _validate_canonical(staging):
    staging.execute("CREATE TABLE archive_observations AS SELECT * FROM observations")
    staging.execute("CREATE TABLE archive_claims AS SELECT * FROM source_claims")
    staging.execute("CREATE TABLE archive_bridge AS SELECT * FROM bridge_records")
    repository = HealthRepository(staging)
    from .models import MetricType

    for row in staging.execute("SELECT DISTINCT person_id,metric FROM source_claims"):
        repository.reconcile_metric(
            row["person_id"], MetricType(row["metric"]), streaming=True
        )
    for expected, actual in (
        ("archive_observations", "observations"),
        ("archive_claims", "source_claims"),
        ("archive_bridge", "bridge_records"),
    ):
        if staging.execute(
            f"SELECT 1 FROM (SELECT * FROM {expected} EXCEPT SELECT * FROM {actual}) LIMIT 1"
        ) or staging.execute(
            f"SELECT 1 FROM (SELECT * FROM {actual} EXCEPT SELECT * FROM {expected}) LIMIT 1"
        ):
            raise StoreValidationError(
                "Canonical records do not match source claims and priorities"
            )
    staging.execute("DROP TABLE archive_observations")
    staging.execute("DROP TABLE archive_claims")
    staging.execute("DROP TABLE archive_bridge")
