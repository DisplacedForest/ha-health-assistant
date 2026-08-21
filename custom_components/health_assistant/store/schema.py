from __future__ import annotations

import sqlite3

from .errors import StoreVersionError

SCHEMA_VERSION = 1

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
)


def current_version(conn: sqlite3.Connection) -> int:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_info (version INTEGER NOT NULL)")
    row = conn.execute("SELECT version FROM schema_info").fetchone()
    return int(row[0]) if row else 0


def apply_migrations(conn: sqlite3.Connection) -> None:
    version = current_version(conn)
    if version > SCHEMA_VERSION:
        raise StoreVersionError(
            f"database schema version {version} is newer than supported "
            f"version {SCHEMA_VERSION}"
        )
    for target, statements in MIGRATIONS:
        if target <= version:
            continue
        with conn:
            for statement in statements:
                conn.execute(statement)
            conn.execute("DELETE FROM schema_info")
            conn.execute("INSERT INTO schema_info (version) VALUES (?)", (target,))
