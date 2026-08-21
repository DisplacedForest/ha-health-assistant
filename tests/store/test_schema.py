import sqlite3

import pytest

from custom_components.health_assistant.store import (
    HealthDatabase,
    StoreError,
    StoreVersionError,
)
from custom_components.health_assistant.store.schema import (
    MIGRATIONS,
    SCHEMA_VERSION,
)


def table_names(path):
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        return {row[0] for row in rows}
    finally:
        conn.close()


def stored_version(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT version FROM schema_info").fetchone()[0]
    finally:
        conn.close()


def test_fresh_database_migrates_to_current_version(tmp_path):
    path = tmp_path / "health.sqlite"
    db = HealthDatabase(path)
    db.open()
    db.close()
    assert stored_version(path) == SCHEMA_VERSION
    assert {"observations", "workouts", "schema_info"} <= table_names(path)


def test_reopen_is_idempotent(tmp_path):
    path = tmp_path / "health.sqlite"
    for _ in range(2):
        db = HealthDatabase(path)
        db.open()
        db.close()
        assert stored_version(path) == SCHEMA_VERSION


def test_newer_schema_fails_safely_without_writing(tmp_path):
    path = tmp_path / "health.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE schema_info (version INTEGER NOT NULL)")
    conn.execute("INSERT INTO schema_info (version) VALUES (?)", (SCHEMA_VERSION + 1,))
    conn.commit()
    conn.close()

    db = HealthDatabase(path)
    with pytest.raises(StoreVersionError):
        db.open()
    with pytest.raises(StoreError):
        db.execute("SELECT 1")
    assert table_names(path) == {"schema_info"}
    assert stored_version(path) == SCHEMA_VERSION + 1


def test_migrations_are_append_only_and_ordered():
    versions = [version for version, _ in MIGRATIONS]
    assert versions == sorted(versions)
    assert len(versions) == len(set(versions))
    assert versions[-1] == SCHEMA_VERSION
    assert versions[0] == 1
