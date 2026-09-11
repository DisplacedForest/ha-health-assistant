import math
from datetime import UTC, date, datetime, timedelta

import pytest

from custom_components.health_assistant.store.derived_metrics import baseline, rolling
from custom_components.health_assistant.store.derived_queries import (
    DerivedError,
    DerivedQueries,
    encoded,
    range_query,
)
from custom_components.health_assistant.store.models import (
    CANONICAL_UNITS,
    HealthObservation,
    MetricType,
)
from custom_components.health_assistant.store.recovery import RecoveryRepository
from custom_components.health_assistant.store.recovery_models import (
    normalized_observation,
)
from custom_components.health_assistant.store.sleep import SleepRepository
from custom_components.health_assistant.store.sleep_models import normalized_session

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)
KEY = {
    "provider": "fixture",
    "source_id": "account",
    "metric": "hrv_sdnn",
    "context": "unknown",
    "algorithm_id": None,
    "algorithm_version": None,
}


def scalar(
    repository,
    day,
    value,
    metric="weight",
    provider="fixture",
    external_id=None,
    hour=8,
):
    instant = datetime.combine(day, datetime.min.time(), UTC) + timedelta(hours=hour)
    return repository.upsert_observation(
        HealthObservation(
            "primary",
            MetricType(metric),
            value,
            CANONICAL_UNITS[MetricType(metric)],
            instant,
            provider,
            external_id or instant.isoformat(),
            NOW,
        )
    )


def recovery(
    database,
    day,
    value=50,
    *,
    revision=1,
    external_id="night",
    source="account",
    payload=None,
):
    instant = datetime.combine(day, datetime.min.time(), UTC) + timedelta(hours=8)
    item = normalized_observation(
        "fixture",
        source,
        external_id,
        revision,
        {
            "value": value,
            "unit": "ms",
            "started_at": instant.isoformat(),
            "ended_at": instant.isoformat(),
            **(payload or {}),
        },
        NOW,
        metric="hrv_sdnn",
    )
    return RecoveryRepository(database).apply_recovery_changes([item])[0].observation


def read(database, domain="scalar", key=None, end="2026-09-06", days=7, zone="UTC"):
    return DerivedQueries(database, clock=lambda: NOW).series(
        domain, key or {"provider": "fixture", "metric": "weight"}, end, days, zone
    )


def test_hand_calculated_baseline_and_boundary():
    target = date(2026, 9, 6)
    points = {target - timedelta(days=15 - n): {"value": n} for n in range(1, 15)}
    points[target] = {"value": 15}
    points[target - timedelta(days=29)] = {"value": 999}
    result = baseline(points, target)
    assert result["n"] == 14 and result["coverage"] == 0.5
    assert result["mean"] == 7.5
    assert result["stddev"] ** 2 == pytest.approx(17.5)
    assert result["deviation"] == 7.5
    assert result["z"] == pytest.approx(7.5 / math.sqrt(17.5))
    del points[target - timedelta(days=14)]
    assert baseline(points, target)["baseline_reason"] == "insufficient_history"
    points[target - timedelta(days=28)] = {"value": 1}
    assert baseline(points, target)["n"] == 14


def test_constant_missing_overflow_and_actual_day_slope():
    target = date(2026, 9, 6)
    points = {target - timedelta(days=n): {"value": 5} for n in range(15)}
    result = baseline(points, target)
    assert result["mean"] == 5 and result["deviation"] == 0
    assert result["z"] is None and result["z_reason"] == "constant_baseline"
    del points[target]
    assert baseline(points, target)["z_reason"] == "no_current_value"
    values = {
        target + timedelta(days=offset): {"value": value}
        for offset, value in ((0, 1), (2, 5), (5, 11))
    }
    assert rolling(values, target + timedelta(days=7), 7)["trend_slope"] == 2
    assert rolling({}, target, 7)["mean"] is None
    huge = {target - timedelta(days=n): {"value": 1e308} for n in range(15)}
    assert baseline(huge, target)["baseline_reason"] == "calculation_unavailable"
    assert rolling(huge, target, 28)["mean_reason"] == "calculation_unavailable"


@pytest.mark.parametrize("metric", list(MetricType))
def test_all_scalar_metrics_choose_latest_or_peak(database, repository, metric):
    day = date(2026, 9, 6)
    scalar(repository, day, 20, metric, external_id="earlier", hour=8)
    latest = scalar(repository, day, 10, metric, external_id="later", hour=9)
    result = read(database, key={"metric": metric.value, "provider": "fixture"})
    point = result["points"][-1]
    activity = metric.value in ("steps", "distance", "active_energy")
    assert point["value"] == (20 if activity else 10)
    assert point["selection_rule"] == (
        "daily_peak" if activity else "latest_observation"
    )
    assert point["alternative_count"] == 1
    assert point["source_revision"] is None
    assert point["scalar_ingested_at"] == latest.ingested_at.isoformat(
        timespec="microseconds"
    )
    assert len(result["points"]) == 7
    assert result["points"][0]["null_reason"] == "no_observation"


def test_scalar_winner_exclusion_priority_and_future(database, repository):
    day = NOW.date()
    a = scalar(repository, day, 50, provider="a")
    scalar(repository, day, 50, provider="b")
    repository.set_priority(MetricType.WEIGHT, ["b", "a"])
    assert (
        read(database, key={"metric": "weight", "provider": "a"}, end=day.isoformat())[
            "points"
        ][-1]["value"]
        is None
    )
    before = read(
        database, key={"metric": "weight", "provider": "b"}, end=day.isoformat()
    )
    assert before["points"][-1]["value"] == 50
    assert before["rolling"]["7"]["n"] == 0
    scalar(repository, day, 99, provider="b", hour=13)
    assert (
        read(database, key={"metric": "weight", "provider": "b"}, end=day.isoformat())[
            "points"
        ][-1]["value"]
        == 50
    )
    current = repository.get_observations("primary", MetricType.WEIGHT)[0]
    repository.set_observation_excluded("primary", current.id, True)
    after = read(
        database, key={"metric": "weight", "provider": "b"}, end=day.isoformat()
    )
    assert after["points"][-1]["value"] is None
    assert after["snapshot_token"] != before["snapshot_token"]
    assert a.id is not None


def test_recovery_ties_source_separation_and_revision_updates(database):
    day = date(2026, 9, 6)
    recovery(database, day, 55, external_id="z")
    selected = recovery(database, day, 50, external_id="a")
    recovery(database, day, 999, external_id="different", source="other")
    recovery(database, day, 888, external_id="spot", payload={"context": "spot"})
    recovery(
        database, day, 777, external_id="method", payload={"algorithm_version": "2"}
    )
    first = read(database, "recovery", KEY)
    assert first["points"][-1]["value"] == 50
    assert first["points"][-1]["selected_record_id"] == selected.id
    assert first["points"][-1]["alternative_count"] == 1
    assert first == read(database, "recovery", KEY)
    changed = recovery(database, day, 60, revision=2, external_id="a")
    second = read(database, "recovery", KEY)
    assert second["snapshot_token"] != first["snapshot_token"]
    assert second["points"][-1]["value"] == 60
    assert second["points"][-1]["source_revision"] == "2"
    repo = RecoveryRepository(database)
    repo.set_excluded(changed.id, True, "2", changed.payload_hash)
    assert read(database, "recovery", KEY)["points"][-1]["value"] == 55
    repo.set_excluded(changed.id, False, "2", changed.payload_hash)
    assert read(database, "recovery", KEY)["points"][-1]["value"] == 60
    deleted = normalized_observation(
        "fixture", "account", "a", 3, None, NOW, metric="hrv_sdnn"
    )
    repo.apply_recovery_changes([deleted])
    assert read(database, "recovery", KEY)["points"][-1]["value"] == 55


def test_longest_sleep_stays_unknown_despite_shorter_reported(database):
    repo = SleepRepository(database)
    for external, hours, reported in (
        ("long", 8, None),
        ("short", 4, 3 * 3600 * 1_000_000),
    ):
        payload = {
            "started_at": f"2026-09-06T0{8 - hours}:00:00Z",
            "ended_at": "2026-09-06T08:00:00Z",
            "reported_totals": {"asleep": reported},
        }
        item = normalized_session("fixture", "account", external, 1, payload, NOW)
        repo.apply_sleep_changes([item])
    result = read(database, "sleep", {"provider": "fixture", "source_id": "account"})
    point = result["points"][-1]
    assert point["value"] is None and point["null_reason"] == "incomplete_sleep"
    assert point["alternative_count"] == 1
    assert point["selection_rule"] == "longest_session"
    assert point["value_basis"] == "missing"
    assert result["rolling"]["7"]["n"] == 0


def test_display_timezone_dst_and_half_open_days(database, repository):
    scalar(repository, date(2026, 3, 8), 10, hour=5)
    scalar(repository, date(2026, 3, 9), 20, hour=4)
    result = read(database, end="2026-03-08", zone="America/Chicago")
    assert result["points"][-1]["value"] == 20
    assert result["points"][-2]["value"] == 10
    utc = read(database, end="2026-03-08", zone="UTC")
    assert utc["points"][-1]["value"] == 10
    assert utc["snapshot_token"] != result["snapshot_token"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"domain": "other"},
        {"series_key": {}},
        {"series_key": {"provider": "fixture", "metric": "weight", "extra": 1}},
        {"days": True},
        {"days": 91},
        {"timezone": "Not/A_Zone"},
        {"timezone": "../UTC"},
        {"end_date": "2026-09-08"},
        {"end_date": "0001-01-01"},
        {"end_date": "20260906"},
    ],
)
def test_invalid_inputs(database, kwargs):
    args = {
        "domain": "scalar",
        "series_key": {"provider": "fixture", "metric": "weight"},
        "end_date": "2026-09-06",
        "days": 7,
        "timezone": "UTC",
        **kwargs,
    }
    with pytest.raises(DerivedError):
        DerivedQueries(database, clock=lambda: NOW).series(**args)


def test_catalog_pagination_counts_and_capture_independence(database, repository):
    for provider in ("a", "b", "c"):
        scalar(
            repository, date(2026, 9, 6), 10, provider=provider, hour=ord(provider) - 90
        )
    queries = DerivedQueries(database)
    first = queries.sources("scalar", limit=1)
    second = queries.sources("scalar", limit=1, cursor=first["next_cursor"])
    assert first["sources"][0]["series_key"]["provider"] == "a"
    assert second["sources"][0]["series_key"]["provider"] == "b"
    assert "value" not in str(first)
    assert first["sources"][0]["capture_state"] == "unknown"
    scalar(repository, date(2026, 9, 5), 12, provider="b")
    with pytest.raises(DerivedError, match="stale_cursor"):
        queries.sources("scalar", cursor=first["next_cursor"])
    states = {encoded({"provider": "a", "metric": "weight"}).decode(): "revoked"}
    revoked = DerivedQueries(database, capture_states=states).sources("scalar")[
        "sources"
    ][0]
    assert (
        revoked["capture_state"] == "revoked" and revoked["retained_history_available"]
    )
    assert read(database, key=revoked["series_key"])["points"][-1]["value"] == 10


def test_queries_use_indexed_bounded_ranges(database):
    for domain, key in (
        ("scalar", {"provider": "fixture", "metric": "weight"}),
        ("sleep", {"provider": "fixture", "source_id": "account"}),
        ("recovery", KEY),
    ):
        sql, params = range_query(domain, key, NOW - timedelta(days=118), NOW, NOW)
        plans = database.execute("EXPLAIN QUERY PLAN " + sql, params)
        assert any(
            "SEARCH" in row["detail"] and "INDEX" in row["detail"] for row in plans
        )
        assert not any("SCAN " in row["detail"] for row in plans)


def test_archive_import_recomputes_without_cache(database, repository, tmp_path):
    from custom_components.health_assistant.store import HealthDatabase
    from custom_components.health_assistant.store.interchange import (
        export_archive,
        import_archive,
    )

    scalar(repository, date(2026, 9, 6), 70)
    recovery(database, date(2026, 9, 6))
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)
    other = HealthDatabase(tmp_path / "imported.sqlite")
    other.open()
    try:
        assert read(other)["points"][-1]["value"] is None
        import_archive(other, archive, dry_run=False)
        assert read(other)["points"] == read(database)["points"]
        assert (
            read(other, "recovery", KEY)["points"]
            == read(database, "recovery", KEY)["points"]
        )
    finally:
        other.close()


def test_consistent_snapshot_during_external_transaction(
    database, repository, monkeypatch
):
    import sqlite3
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    scalar(repository, date(2026, 9, 5), 10)
    scalar(repository, date(2026, 9, 6), 20)
    entered, resume = Event(), Event()
    iterate = database.iterate

    def pause(sql, params=()):
        for index, row in enumerate(iterate(sql, params)):
            if index == 0:
                entered.set()
                assert resume.wait(5)
            yield row

    def writer():
        connection = sqlite3.connect(database.path)
        try:
            connection.execute("UPDATE observations SET value=value+100")
            connection.commit()
        finally:
            connection.close()

    monkeypatch.setattr(database, "iterate", pause)
    with ThreadPoolExecutor(max_workers=2) as pool:
        reading = pool.submit(read, database)
        assert entered.wait(5)
        writing = pool.submit(writer)
        resume.set()
        before = reading.result()
        writing.result()
    assert [point["value"] for point in before["points"][-2:]] == [10, 20]
    monkeypatch.setattr(database, "iterate", iterate)
    assert [point["value"] for point in read(database)["points"][-2:]] == [110, 120]


def test_large_history_streams_only_bounded_interval(database, monkeypatch):
    import tracemalloc

    with database.transaction():
        database.execute(
            "WITH RECURSIVE n(x) AS (VALUES(0) UNION ALL SELECT x+1 FROM n WHERE x<49999) INSERT INTO observations(person_id,metric,value,unit,observed_at,provider,external_id,ingested_at,status) SELECT 'primary','weight',70,'kg','2020-01-01T08:00:00.000000+00:00','fixture',CAST(x AS TEXT),'2020-01-01T08:00:00.000000+00:00','active' FROM n"
        )
        database.execute(
            "WITH RECURSIVE n(x) AS (VALUES(0) UNION ALL SELECT x+1 FROM n WHERE x<9999) INSERT INTO observations(person_id,metric,value,unit,observed_at,provider,external_id,ingested_at,status) SELECT 'primary','weight',70,'kg','2026-09-06T08:00:00.000000+00:00','fixture',CAST(x AS TEXT),'2026-09-06T08:00:00.000000+00:00','active' FROM n"
        )
    iterate, scanned = database.iterate, []

    def counted(sql, params=()):
        count = 0
        for row in iterate(sql, params):
            count += 1
            yield row
        scanned.append(count)

    monkeypatch.setattr(database, "iterate", counted)
    tracemalloc.start()
    try:
        result = read(database, days=90)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert scanned == [10000]
    assert result["points"][-1]["alternative_count"] == 9999
    assert len(result["points"]) == 90
    assert peak < 2_000_000


def test_recovery_query_does_not_traverse_old_history(database):
    with database.transaction():
        database.execute(
            "WITH RECURSIVE n(x) AS (VALUES(0) UNION ALL SELECT x+1 FROM n WHERE x<49999) INSERT INTO recovery_records(person_id,metric,provider,source_id,external_id,source_revision,payload_hash,source_state,first_ingested_at,last_ingested_at,started_at,ended_at,value,unit,context,provenance) SELECT 'primary','hrv_sdnn','fixture','account',CAST(x AS TEXT),1,'old-fixture','active','2020-01-01T00:00:00.000000Z','2020-01-01T00:00:00.000000Z','2020-01-01T00:00:00.000000Z','2020-01-01T00:00:00.000000Z',50,'ms','unknown','{}' FROM n"
        )
    sql, args = range_query("recovery", KEY, NOW - timedelta(days=118), NOW, NOW)
    plan = " ".join(
        row["detail"] for row in database.execute("EXPLAIN QUERY PLAN " + sql, args)
    )
    assert "idx_recovery_source_query" in plan
    assert "ended_at>?" in plan and "ended_at<?" in plan
    callbacks = []
    database._conn.set_progress_handler(lambda: callbacks.append(1) or 0, 100)
    try:
        result = read(database, "recovery", KEY)
    finally:
        database._conn.set_progress_handler(None, 0)
    assert all(point["value"] is None for point in result["points"])
    assert len(callbacks) < 10
