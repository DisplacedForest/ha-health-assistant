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
    apply_migrations,
    current_version,
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
    assert {"observations", "workouts", "provider_state", "schema_info"} <= table_names(
        path
    )


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


def test_failed_migration_rolls_back_completely(tmp_path):
    path = tmp_path / "health.sqlite"
    conn = sqlite3.connect(path)
    broken = ((1, ("CREATE TABLE partial (id INTEGER)", "THIS IS NOT SQL")),)
    with pytest.raises(sqlite3.OperationalError):
        apply_migrations(conn, migrations=broken, latest=1)
    assert current_version(conn) == 0
    names = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert "partial" not in names

    fixed = ((1, ("CREATE TABLE partial (id INTEGER)",)),)
    apply_migrations(conn, migrations=fixed, latest=1)
    assert current_version(conn) == 1
    conn.close()


def test_populated_v1_database_upgrades_to_current_version(tmp_path):
    path = tmp_path / "health.sqlite"
    conn = sqlite3.connect(path)
    apply_migrations(conn, migrations=MIGRATIONS[:1], latest=1)
    conn.execute(
        """
        INSERT INTO observations (
            person_id, metric, value, unit, observed_at,
            provider, external_id, ingested_at
        )
        VALUES (
            'primary', 'weight', 80.0, 'kg', '2026-08-20T12:00:00+00:00',
            'manual', 'obs-1', '2026-08-20T12:00:00+00:00'
        )
        """
    )
    conn.commit()
    conn.close()
    assert stored_version(path) == 1

    db = HealthDatabase(path)
    db.open()
    rows = db.execute("SELECT * FROM observations")
    claims = db.execute("SELECT * FROM source_claims")
    state_rows = db.execute("SELECT * FROM provider_state")
    preferences = db.execute("SELECT * FROM metric_preferences")
    db.close()
    assert stored_version(path) == SCHEMA_VERSION
    assert [row["value"] for row in rows] == [80.0]
    assert rows[0]["possible_duplicate"] == 0
    assert len(claims) == 1
    assert claims[0]["observation_id"] == rows[0]["id"]
    assert claims[0]["provider"] == "manual"
    assert claims[0]["value"] == 80.0
    assert state_rows == []
    assert preferences == []


def test_populated_v2_database_upgrades_with_claims_split(tmp_path):
    path = tmp_path / "health.sqlite"
    conn = sqlite3.connect(path)
    apply_migrations(conn, migrations=MIGRATIONS[:2], latest=2)
    for external_id, value in (("obs-1", 80.0), ("obs-2", 79.5)):
        conn.execute(
            """
            INSERT INTO observations (
                person_id, metric, value, unit, observed_at,
                provider, external_id, ingested_at
            )
            VALUES (
                'primary', 'weight', ?, 'kg', '2026-08-20T12:00:00+00:00',
                'ha_entity', ?, '2026-08-20T12:00:00+00:00'
            )
            """,
            (value, external_id),
        )
    conn.execute(
        """
        INSERT INTO provider_state (provider, state, updated_at)
        VALUES ('synthetic', '{"cursor": 5}', '2026-08-20T12:00:00+00:00')
        """
    )
    conn.commit()
    conn.close()

    db = HealthDatabase(path)
    db.open()
    rows = db.execute("SELECT * FROM observations ORDER BY id")
    claims = db.execute("SELECT * FROM source_claims ORDER BY id")
    state_rows = db.execute("SELECT * FROM provider_state")
    db.close()
    assert stored_version(path) == SCHEMA_VERSION
    assert [row["value"] for row in rows] == [80.0, 79.5]
    assert [claim["observation_id"] for claim in claims] == [
        rows[0]["id"],
        rows[1]["id"],
    ]
    assert len(state_rows) == 1
    assert state_rows[0]["provider"] == "synthetic"


def test_migrations_are_append_only_and_ordered():
    versions = [version for version, _ in MIGRATIONS]
    assert versions == sorted(versions)
    assert len(versions) == len(set(versions))
    assert versions[-1] == SCHEMA_VERSION
    assert versions[0] == 1
