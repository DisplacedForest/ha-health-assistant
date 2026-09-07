from __future__ import annotations

import sqlite3

from .errors import StoreVersionError

SCHEMA_VERSION = 8

MIGRATIONS: tuple[tuple[int, tuple[str, ...]], ...] = (
    (
        1,
        (
            """
            CREATE TABLE observations (
                id INTEGER PRIMARY KEY,
                person_id TEXT NOT NULL,
                metric TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                provider TEXT NOT NULL,
                external_id TEXT NOT NULL,
                ingested_at TEXT NOT NULL,
                provenance TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'active',
                UNIQUE (provider, external_id, metric, observed_at)
            )
            """,
            """
            CREATE INDEX idx_observations_person_metric_time
            ON observations (person_id, metric, observed_at)
            """,
            """
            CREATE TABLE workouts (
                id INTEGER PRIMARY KEY,
                person_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                external_id TEXT NOT NULL,
                workout_type TEXT NOT NULL,
                title TEXT,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                energy_kcal REAL,
                distance_m REAL,
                ingested_at TEXT NOT NULL,
                provenance TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'active',
                UNIQUE (provider, external_id)
            )
            """,
            """
            CREATE INDEX idx_workouts_person_time
            ON workouts (person_id, started_at)
            """,
        ),
    ),
    (
        2,
        (
            """
            CREATE TABLE provider_state (
                provider TEXT PRIMARY KEY,
                state TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL
            )
            """,
        ),
    ),
    (
        3,
        (
            """
            CREATE TABLE source_claims (
                id INTEGER PRIMARY KEY,
                observation_id INTEGER,
                person_id TEXT NOT NULL,
                metric TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                provider TEXT NOT NULL,
                external_id TEXT NOT NULL,
                ingested_at TEXT NOT NULL,
                provenance TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'active',
                UNIQUE (provider, external_id, metric, observed_at)
            )
            """,
            """
            CREATE INDEX idx_source_claims_person_metric_time
            ON source_claims (person_id, metric, observed_at)
            """,
            """
            CREATE INDEX idx_source_claims_observation
            ON source_claims (observation_id)
            """,
            """
            INSERT INTO source_claims (
                id, observation_id, person_id, metric, value, unit,
                observed_at, provider, external_id, ingested_at,
                provenance, status
            )
            SELECT
                id, id, person_id, metric, value, unit,
                observed_at, provider, external_id, ingested_at,
                provenance, status
            FROM observations
            """,
            """
            CREATE TABLE observations_canonical (
                id INTEGER PRIMARY KEY,
                person_id TEXT NOT NULL,
                metric TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                provider TEXT NOT NULL,
                external_id TEXT NOT NULL,
                ingested_at TEXT NOT NULL,
                provenance TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'active',
                possible_duplicate INTEGER NOT NULL DEFAULT 0
            )
            """,
            """
            INSERT INTO observations_canonical (
                id, person_id, metric, value, unit, observed_at,
                provider, external_id, ingested_at, provenance, status,
                possible_duplicate
            )
            SELECT
                id, person_id, metric, value, unit, observed_at,
                provider, external_id, ingested_at, provenance, status, 0
            FROM observations
            """,
            "DROP TABLE observations",
            "ALTER TABLE observations_canonical RENAME TO observations",
            """
            CREATE INDEX idx_observations_person_metric_time
            ON observations (person_id, metric, observed_at)
            """,
            """
            CREATE TABLE metric_preferences (
                metric TEXT PRIMARY KEY,
                provider TEXT NOT NULL
            )
            """,
        ),
    ),
    (
        4,
        (
            """
            CREATE TABLE metric_priorities (
                metric TEXT NOT NULL,
                context TEXT NOT NULL DEFAULT '',
                rank INTEGER NOT NULL,
                provider TEXT NOT NULL,
                PRIMARY KEY (metric, context, rank),
                UNIQUE (metric, context, provider)
            )
            """,
            """
            INSERT INTO metric_priorities (metric, context, rank, provider)
            SELECT metric, '', 0, provider FROM metric_preferences
            """,
            "DROP TABLE metric_preferences",
        ),
    ),
    (
        5,
        (
            """
            CREATE INDEX idx_observations_person_status_id
            ON observations (person_id, status, id)
            """,
        ),
    ),
    (
        6,
        (
            """
            CREATE TABLE environment_streams (
                id INTEGER PRIMARY KEY,
                public_id TEXT NOT NULL UNIQUE,
                mapping_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                metric TEXT NOT NULL,
                area_id TEXT NOT NULL,
                area_name TEXT NOT NULL,
                unit TEXT NOT NULL
            )
            """,
            "CREATE INDEX idx_environment_area_metric ON environment_streams(area_id, metric)",
            "CREATE INDEX idx_environment_mapping ON environment_streams(mapping_id, id)",
            """
            CREATE TABLE environment_buckets (
                stream_id INTEGER NOT NULL REFERENCES environment_streams(id),
                start_ms INTEGER NOT NULL,
                resolution_s INTEGER NOT NULL,
                sample_count INTEGER NOT NULL,
                sample_sum REAL NOT NULL,
                minimum REAL,
                maximum REAL,
                weighted_sum REAL NOT NULL,
                covered_ms INTEGER NOT NULL,
                first_report_ms INTEGER,
                last_report_ms INTEGER,
                updated_ms INTEGER NOT NULL,
                PRIMARY KEY(stream_id, resolution_s, start_ms)
            ) WITHOUT ROWID
            """,
            "CREATE INDEX idx_environment_retention ON environment_buckets(resolution_s, start_ms)",
            """
            CREATE TABLE environment_maintenance (
                id INTEGER PRIMARY KEY CHECK(id=1),
                last_success_ms INTEGER,
                duration_ms INTEGER,
                rolled_up INTEGER NOT NULL DEFAULT 0,
                deleted INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0
            )
            """,
            "INSERT INTO environment_maintenance(id) VALUES (1)",
        ),
    ),
    (
        7,
        (
            """
            CREATE TABLE sleep_sessions (
                id INTEGER PRIMARY KEY,
                person_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                source_id TEXT NOT NULL,
                external_id TEXT NOT NULL,
                source_revision INTEGER NOT NULL,
                payload_hash TEXT NOT NULL,
                hash_version INTEGER NOT NULL DEFAULT 1,
                source_state TEXT NOT NULL,
                locally_excluded INTEGER NOT NULL DEFAULT 0,
                first_ingested_at TEXT NOT NULL,
                last_ingested_at TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                start_offset_seconds INTEGER,
                end_offset_seconds INTEGER,
                start_zone TEXT,
                end_zone TEXT,
                reported_totals TEXT,
                stages TEXT NOT NULL,
                in_bed_intervals TEXT NOT NULL,
                provenance TEXT NOT NULL,
                UNIQUE(provider, source_id, external_id)
            )
            """,
            "CREATE INDEX idx_sleep_query ON sleep_sessions(person_id,source_state,locally_excluded,ended_at,id)",
            "CREATE INDEX idx_sleep_source_query ON sleep_sessions(person_id,source_id,ended_at,id)",
            "CREATE TABLE sleep_state (id INTEGER PRIMARY KEY CHECK(id=1), generation INTEGER NOT NULL)",
            "INSERT INTO sleep_state(id,generation) VALUES(1,0)",
        ),
    ),
    (
        8,
        (
            """
            CREATE TABLE recovery_records (
                id INTEGER PRIMARY KEY,
                person_id TEXT NOT NULL,
                metric TEXT NOT NULL,
                provider TEXT NOT NULL,
                source_id TEXT NOT NULL,
                external_id TEXT NOT NULL,
                source_revision INTEGER NOT NULL,
                payload_hash TEXT NOT NULL,
                hash_version INTEGER NOT NULL DEFAULT 1,
                source_state TEXT NOT NULL,
                locally_excluded INTEGER NOT NULL DEFAULT 0,
                first_ingested_at TEXT NOT NULL,
                last_ingested_at TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                start_offset_seconds INTEGER,
                end_offset_seconds INTEGER,
                start_zone TEXT,
                end_zone TEXT,
                value REAL,
                unit TEXT,
                context TEXT,
                algorithm_id TEXT,
                algorithm_version TEXT,
                provenance TEXT NOT NULL,
                UNIQUE(provider, source_id, external_id)
            )
            """,
            "CREATE INDEX idx_recovery_query ON recovery_records(person_id,source_state,locally_excluded,ended_at,id)",
            "CREATE INDEX idx_recovery_source_query ON recovery_records(person_id,source_state,locally_excluded,provider,source_id,metric,context,algorithm_id,algorithm_version,ended_at,id)",
            "CREATE TABLE recovery_state (id INTEGER PRIMARY KEY CHECK(id=1), generation INTEGER NOT NULL)",
            "INSERT INTO recovery_state(id,generation) VALUES(1,0)",
        ),
    ),
)


def current_version(conn: sqlite3.Connection) -> int:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_info (version INTEGER NOT NULL)")
    row = conn.execute("SELECT version FROM schema_info").fetchone()
    return int(row[0]) if row else 0


def apply_migrations(
    conn: sqlite3.Connection,
    migrations: tuple[tuple[int, tuple[str, ...]], ...] = MIGRATIONS,
    latest: int = SCHEMA_VERSION,
) -> None:
    version = current_version(conn)
    if version > latest:
        raise StoreVersionError(
            f"database schema version {version} is newer than supported "
            f"version {latest}"
        )
    for target, statements in migrations:
        if target <= version:
            continue
        conn.execute("BEGIN IMMEDIATE")
        try:
            for statement in statements:
                conn.execute(statement)
            conn.execute("DELETE FROM schema_info")
            conn.execute("INSERT INTO schema_info (version) VALUES (?)", (target,))
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
