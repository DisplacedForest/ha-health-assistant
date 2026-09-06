from dataclasses import replace

import pytest

from custom_components.health_assistant.store import StoreValidationError
from custom_components.health_assistant.store.environment import (
    DAY_MS,
    HOUR_MS,
    WINDOW_MS,
    EnvironmentAccumulator,
    EnvironmentBucket,
    EnvironmentRepository,
    normalize_environment,
)


def mapping(**changes):
    return {
        "mapping_id": "mapped-sensor",
        "source_id": "sensor-source",
        "entity_id": "sensor.bedroom",
        "metric": "temperature",
        "area_id": "bedroom",
        "area_name": "Bedroom",
        **changes,
    }


@pytest.mark.parametrize(
    ("metric", "value", "unit", "expected"),
    [
        ("temperature", 68, "°F", 20),
        ("temperature", 293.15, "K", 20),
        ("humidity", 100, "%", 100),
        ("co2", 0, "ppm", 0),
    ],
)
def test_normalization(metric, value, unit, expected):
    assert normalize_environment(metric, value, unit) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("metric", "value", "unit"),
    [
        ("temperature", float("nan"), "°C"),
        ("humidity", 101, "%"),
        ("humidity", 30, "fraction"),
        ("co2", -1, "ppm"),
        ("noise", 30, "dB"),
        ("temperature", True, "°C"),
        ("temperature", -1, "K"),
    ],
)
def test_invalid_readings(metric, value, unit):
    with pytest.raises(StoreValidationError):
        normalize_environment(metric, value, unit)


def test_time_weighting_and_unavailable_gap():
    a = EnvironmentAccumulator(1, 0)
    assert a.report(0, 10) == []
    a.report(60_000, 30)
    a.report(120_000, None)
    a.report(240_000, 20)
    (bucket,) = a.advance(WINDOW_MS)
    assert bucket.covered_ms == 180_000
    assert bucket.mean == 20
    assert bucket.sample_count == 3
    assert bucket.minimum == 10
    assert bucket.maximum == 30


def test_identical_report_extends_hold_but_clock_does_not():
    a = EnvironmentAccumulator(1, 0)
    a.report(0, 20)
    first = a.advance(600_000)
    a.report(600_000, 20)
    rest = a.advance(1_800_000)
    assert sum(b.covered_ms for b in first + rest) == 1_500_000
    assert sum(b.sample_count for b in first + rest) == 2
    assert a.advance(10_000 * DAY_MS) == []


def test_stale_and_duplicate_reports_never_rewind():
    a = EnvironmentAccumulator(1, 10_000)
    a.report(10_000, 20)
    a.report(10_000, 500)
    a.report(9_000, 600)
    (bucket,) = a.stop(20_000)
    assert bucket.sample_count == 1
    assert bucket.mean == 20
    assert bucket.covered_ms == 10_000


def test_partial_flush_restart_preserves_data_and_gap(database):
    r = EnvironmentRepository(database)
    stream = r.register(mapping())
    a = EnvironmentAccumulator(stream["id"], 0)
    a.report(0, 10)
    first = a.stop(60_000)
    r.save(first, 60_000)
    r.save(first, 60_000)
    b = EnvironmentAccumulator(stream["id"], 120_000, r.bucket(stream["id"], 0))
    b.report(120_000, 30)
    rows = b.advance(WINDOW_MS)
    r.save(rows, WINDOW_MS)
    (result,) = r.query("bedroom", "temperature", 0, WINDOW_MS)
    assert result["covered_ms"] == 240_000
    assert result["mean"] == 25
    assert result["sample_count"] == 2
    assert result["sample_sum"] == 40
    assert result["partial_overlap"] is False
    assert r.query("bedroom", "temperature", 1, WINDOW_MS)[0]["partial_overlap"] is True


def test_register_revisions_caps_and_atomicity(database):
    r = EnvironmentRepository(database)
    first = r.register(mapping())
    assert r.register(mapping()) == first
    second = r.register(mapping(area_id="office", area_name="Office"))
    third = r.register(mapping())
    assert len({first["id"], second["id"], third["id"]}) == 3
    for n in range(253):
        r.register(mapping(mapping_id=str(n)))
    with pytest.raises(StoreValidationError):
        r.register(mapping(mapping_id="overflow"))
    assert len(r.export_streams()) == 256
    with pytest.raises(StoreValidationError):
        r.register_all([mapping(mapping_id=str(n)) for n in range(13)])


def test_retention_weighting_replay_and_expiry(database):
    r = EnvironmentRepository(database)
    stream = r.register(mapping())
    rows = [
        EnvironmentBucket(
            stream["id"],
            0,
            sample_count=2,
            sample_sum=40,
            minimum=10,
            maximum=30,
            weighted_sum=10 * 60_000,
            covered_ms=60_000,
            updated_ms=WINDOW_MS,
        ),
        EnvironmentBucket(
            stream["id"],
            WINDOW_MS,
            sample_count=1,
            sample_sum=30,
            minimum=30,
            maximum=30,
            weighted_sum=30 * 300_000,
            covered_ms=300_000,
            updated_ms=2 * WINDOW_MS,
        ),
    ]
    r.save(rows, 2 * WINDOW_MS)
    now = 90 * DAY_MS + HOUR_MS
    assert r.maintain_batch(now)["rolled_up"] == 1
    assert r.maintain_batch(now) == {"rolled_up": 0, "deleted": 0, "more": False}
    (result,) = r.query("bedroom", "temperature", 0, HOUR_MS)
    assert result["resolution_s"] == 3600
    assert result["covered_ms"] == 360_000
    assert result["mean"] == pytest.approx(26.66666667)
    assert result["sample_sum"] == 70
    with pytest.raises(StoreValidationError):
        r.save(rows, now)
    assert r.maintain_batch(730 * DAY_MS + HOUR_MS)["deleted"] == 1
    assert r.export_buckets() == []


def test_save_rolls_back_and_older_flush_does_not_overwrite(database):
    r = EnvironmentRepository(database)
    stream = r.register(mapping())
    row = EnvironmentBucket(
        stream["id"], 0, sample_count=1, sample_sum=20, updated_ms=100
    )
    with pytest.raises(StoreValidationError):
        r.save([row, replace(row, stream_id=999)], 100)
    assert r.export_buckets() == []
    r.save([row], 100)
    r.save([replace(row, sample_sum=10, updated_ms=99)], 100)
    assert r.bucket(stream["id"], 0).sample_sum == 20


def test_backup_contains_environment_and_metadata(database, tmp_path):
    from custom_components.health_assistant.store import HealthDatabase

    r = EnvironmentRepository(database)
    stream = r.register(mapping())
    row = EnvironmentBucket(
        stream["id"], 0, covered_ms=100, weighted_sum=2000, updated_ms=100
    )
    r.save([row], 100)
    target = tmp_path / "backup.sqlite"
    database.backup(target)
    restored = HealthDatabase(target)
    restored.open()
    try:
        rr = EnvironmentRepository(restored)
        assert rr.export_streams() == r.export_streams()
        assert rr.export_buckets() == r.export_buckets()
    finally:
        restored.close()


def test_two_year_retention_and_twelve_stream_storage_budget(database):
    r = EnvironmentRepository(database)
    stream = r.register(mapping())
    baseline = (
        database.execute("PRAGMA page_count")[0][0]
        * database.execute("PRAGMA page_size")[0][0]
    )
    insert = "INSERT INTO environment_buckets VALUES (?, ?, 300, 1, ?, ?, ?, ?, 300000, ?, ?, ?)"
    database.execute_batch(
        (
            insert,
            (
                stream["id"],
                t,
                20.123,
                20.123,
                20.123,
                20.123 * WINDOW_MS,
                t,
                t,
                t + WINDOW_MS,
            ),
        )
        for t in range(0, 730 * DAY_MS, WINDOW_MS)
    )
    now = 730 * DAY_MS
    while r.maintain_batch(now, 512)["more"]:
        pass
    assert database.execute("SELECT COUNT(*) FROM environment_buckets")[0][0] == 41_280
    assert (
        database.execute(
            "SELECT COUNT(*) FROM environment_buckets WHERE resolution_s=300"
        )[0][0]
        == 90 * 288
    )
    for n in range(1, 12):
        target = r.register(mapping(mapping_id=f"sensor-{n}"))
        database.execute(
            "INSERT INTO environment_buckets SELECT ?, start_ms, resolution_s, sample_count, sample_sum, minimum, maximum, weighted_sum, covered_ms, first_report_ms, last_report_ms, updated_ms FROM environment_buckets WHERE stream_id=?",
            (target["id"], stream["id"]),
        )
    assert database.execute("SELECT COUNT(*) FROM environment_buckets")[0][0] == 495_360
    database.checkpoint()
    allocated = sum(
        row[0]
        for row in database.execute(
            "SELECT sum(pgsize) FROM dbstat WHERE name IN ('environment_buckets', 'idx_environment_retention')"
        )
    )
    assert allocated <= 495_360 * 160
    assert database.execute("PRAGMA integrity_check")[0][0] == "ok"
    size = database.path.stat().st_size
    assert size - baseline <= 495_360 * 160 + 12 * 4096
    plan = database.execute(
        "EXPLAIN QUERY PLAN SELECT b.* FROM environment_streams s JOIN environment_buckets b ON b.stream_id=s.id WHERE s.area_id=? AND s.metric=? AND b.resolution_s IN (300,3600) AND b.start_ms>=? AND b.start_ms<?",
        ("bedroom", "temperature", now - WINDOW_MS, now),
    )
    detail = " ".join(row[3] for row in plan)
    assert "SEARCH b" in detail
    assert "resolution_s=? AND start_ms>? AND start_ms<?" in detail
    assert "SCAN" not in detail
    assert len(r.export_buckets(limit=2)) == 2
    with pytest.raises(StoreValidationError):
        r.export_buckets(limit=5001)


def test_rollup_failure_preserves_all_children(database):
    import sqlite3
    from unittest.mock import patch

    r = EnvironmentRepository(database)
    stream = r.register(mapping())
    row = EnvironmentBucket(
        stream["id"], 0, covered_ms=100, weighted_sum=2000, updated_ms=100
    )
    r.save([row], 100)
    execute = database.execute

    def fail(sql, params=()):
        if sql.startswith("DELETE FROM environment_buckets WHERE stream_id"):
            raise sqlite3.OperationalError("failed retention delete")
        return execute(sql, params)

    with (
        patch.object(database, "execute", side_effect=fail),
        pytest.raises(sqlite3.OperationalError),
    ):
        r.maintain_batch(90 * DAY_MS + HOUR_MS)
    assert len(r.export_buckets()) == 1
    assert r.export_buckets()[0]["resolution_s"] == 300
    assert r.maintain_batch(90 * DAY_MS + HOUR_MS)["rolled_up"] == 1


def test_health_transaction_serializes_environment_flush(database):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    r = EnvironmentRepository(database)
    stream = r.register(mapping())
    entered = threading.Event()
    finished = threading.Event()

    def flush():
        entered.set()
        r.save(
            [
                EnvironmentBucket(
                    stream["id"], 0, covered_ms=100, weighted_sum=2000, updated_ms=100
                )
            ],
            100,
        )
        finished.set()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with database.transaction():
            future = pool.submit(flush)
            assert entered.wait(timeout=2)
            assert not finished.wait(timeout=0.02)
            assert r.export_buckets() == []
        future.result(timeout=2)
    assert len(r.export_buckets()) == 1


def test_upgrade_from_schema_five_preserves_excluded_history(tmp_path):
    import sqlite3

    from custom_components.health_assistant.store import HealthDatabase
    from custom_components.health_assistant.store.schema import (
        MIGRATIONS,
        apply_migrations,
    )

    path = tmp_path / "previous.sqlite"
    with sqlite3.connect(path) as conn:
        apply_migrations(conn, MIGRATIONS[:5], latest=5)
        conn.execute(
            "INSERT INTO observations (person_id, metric, value, unit, observed_at, provider, external_id, ingested_at, status) VALUES ('primary', 'weight', 82.5, 'kg', '2026-09-01T00:00:00+00:00', 'scale', 'reading', '2026-09-01T00:00:00+00:00', 'excluded')"
        )
        before = conn.execute("SELECT * FROM observations").fetchall()
    upgraded = HealthDatabase(path)
    upgraded.open()
    try:
        assert [
            tuple(row) for row in upgraded.execute("SELECT * FROM observations")
        ] == before
        assert upgraded.execute("SELECT version FROM schema_info")[0][0] == 6
        assert upgraded.execute("SELECT count(*) FROM environment_buckets")[0][0] == 0
        assert upgraded.execute("PRAGMA integrity_check")[0][0] == "ok"
    finally:
        upgraded.close()
