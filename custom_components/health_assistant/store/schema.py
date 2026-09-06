from __future__ import annotations

import sqlite3

from .errors import StoreVersionError

SCHEMA_VERSION = 5

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
