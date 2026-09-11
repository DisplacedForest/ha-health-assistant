import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from custom_components.health_assistant.store import HealthDatabase
from custom_components.health_assistant.store.recovery import RecoveryRepository
from custom_components.health_assistant.store.recovery_models import (
    CandidateRecoveryObservation,
    RecoveryError,
    candidate_observation,
    canonical,
    normalized_observation,
)
from custom_components.health_assistant.store.recovery_queries import RecoveryQueries
from custom_components.health_assistant.store.schema import MIGRATIONS, apply_migrations

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)
START = "2026-09-07T00:00:00.000000Z"
END = "2026-09-07T01:00:00.000000Z"
AFTER = "2026-09-07T01:00:00.000001Z"
SERIES = {
    "provider": "fixture",
    "source_id": "account",
    "metric": "hrv_sdnn",
    "context": "unknown",
    "algorithm_id": None,
    "algorithm_version": None,
}


def observation(
    revision=1,
    external_id="reading",
    provider="fixture",
    source="account",
    payload=None,
    metric="hrv_sdnn",
    deleted=False,
    excluded=False,
):
    return normalized_observation(
        provider,
        source,
        external_id,
        revision,
        None
        if deleted
        else {
            "value": 50,
            "unit": "ms",
            "started_at": START,
            "ended_at": END,
            **(payload or {}),
        },
        NOW,
        metric=metric,
        excluded=excluded,
    )


def test_frozen_recovery_hash_projection():
    fixture = json.loads(
        (Path(__file__).parents[1] / "fixtures/recovery-hash-vectors.json").read_text()
    )
    vectors = [
        item
        for item in fixture["vectors"]
        if json.loads(item["verified"]["canonical_utf8"]).get("domain") == "recovery"
    ]
    assert vectors
    for vector in vectors:
        projection = json.loads(vector["verified"]["canonical_utf8"])
        value = normalized_observation(
            **{
                key: projection["identity"][key]
                for key in ("provider", "source_id", "external_id")
            },
            revision=1,
            payload=projection["payload"],
            now=NOW,
            metric=projection["record_type"],
        )
        assert value.payload_hash == vector["verified"]["sha256"]
        assert (
            hashlib.sha256(canonical(projection, 40960)).hexdigest()
            == value.payload_hash
        )


@pytest.mark.parametrize(
    ("metric", "value", "unit", "expected", "canonical_unit"),
    [
        ("resting_heart_rate", 1, "count/s", 60, "bpm"),
        ("resting_heart_rate", 60, "count/min", 60, "bpm"),
        ("respiratory_rate", 0.25, "count/s", 15, "breaths/min"),
        ("respiratory_rate", 15, "count/min", 15, "breaths/min"),
        ("hrv_sdnn", 0.05, "s", 50, "ms"),
        ("hrv_rmssd", 50, "ms", 50, "ms"),
    ],
)
def test_explicit_unit_equivalence(metric, value, unit, expected, canonical_unit):
    item = observation(metric=metric, payload={"value": value, "unit": unit})
    assert item.payload["value"] == expected and item.payload["unit"] == canonical_unit
    assert (
        item.payload_hash
        == observation(
            metric=metric, payload={"value": expected, "unit": canonical_unit}
        ).payload_hash
    )
    raw = observation(
        metric=metric,
        payload={
            "value": value,
            "unit": unit,
            "provenance": {"raw_value": value, "raw_unit": unit},
        },
    )
    assert raw.payload["provenance"]["raw_value"] == value
    assert raw.payload_hash != item.payload_hash


@pytest.mark.parametrize(
    "payload",
    [
        {"value": True},
        {"value": float("nan")},
        {"value": float("inf")},
        {"value": 0},
        {"value": -0.0},
        {"value": -1},
        {"value": "50"},
        {"unit": "milliseconds"},
        {"context": None},
        {"context": "resting"},
        {"provenance": None},
        {"provenance": {"raw_value": 50}},
        {"provenance": {"raw_value": 1, "raw_unit": "ms"}},
        {"provenance": {"raw_value": True, "raw_unit": "ms"}},
        {"provenance": {"algorithm": "not allowed"}},
        {"algorithm_id": "x" * 129},
        {"provenance": {"source_app": "x" * 257}},
        {"provenance": {"source_app": "\ud800"}},
        {"started_at": "2026-09-07T00:00:00"},
        {"started_at": "2026-09-07T00:00:00.0000001Z"},
        {"ended_at": "2026-09-08T00:00:00Z"},
        {"started_at": "2026-09-04T00:00:00Z"},
        {"start_zone": "America/Chicago", "start_offset_seconds": 0},
        {"start_offset_seconds": True},
        {"unknown": 1},
        {"metric": "hrv_sdnn"},
    ],
)
def test_invalid_payload_is_rejected(payload):
    with pytest.raises(RecoveryError):
        observation(payload=payload)


def test_point_window_dst_and_unknown_method():
    point = observation(payload={"ended_at": START})
    assert point.payload["context"] == "unknown"
    assert point.payload["started_at"] == point.payload["ended_at"]
    travel = observation(
        payload={
            "started_at": "2025-11-02T01:30:00-05:00",
            "ended_at": "2025-11-02T01:30:00-06:00",
            "start_zone": "America/Chicago",
            "end_zone": "America/Chicago",
            "start_offset_seconds": -18000,
            "end_offset_seconds": -21600,
        }
    )
    assert travel.payload["started_at"] == "2025-11-02T06:30:00.000000Z"
    assert travel.payload["ended_at"] == "2025-11-02T07:30:00.000000Z"
    with pytest.raises(RecoveryError, match="unsupported_method"):
        observation(metric="hrv")
    with pytest.raises(RecoveryError):
        observation(revision=True)
    with pytest.raises(RecoveryError):
        observation(external_id="x" * 257)
    with pytest.raises(RecoveryError):
        candidate_observation(
            "fixture",
            CandidateRecoveryObservation(
                "account", "x", 1, "hrv_sdnn", 50, "ms", START, END, person_id="other"
            ),
            NOW,
        )


def test_revisions_tombstones_metric_identity_and_exclusions(database):
    repository = RecoveryRepository(database, clock=lambda: NOW)
    first = repository.apply_recovery_changes([observation()])[0].observation
    assert repository.generation() == 1
    assert not repository.apply_recovery_changes([observation()])[0].changed
    repository.set_excluded(first.id, True, "1", first.payload_hash)
    corrected = repository.apply_recovery_changes(
        [observation(2, payload={"value": 60, "context": "spot", "ended_at": START})]
    )[0].observation
    assert corrected.locally_excluded and corrected.payload["value"] == 60
    with pytest.raises(RecoveryError, match="recovery_identity_conflict"):
        repository.apply_recovery_changes([observation(3, metric="hrv_rmssd")])
    with pytest.raises(RecoveryError, match="revision_conflict"):
        repository.set_excluded(first.id, False, "1", first.payload_hash)
    deleted = repository.apply_recovery_changes([observation(3, deleted=True)])[
        0
    ].observation
    row = database.execute("SELECT * FROM recovery_records")[0]
    assert (
        row["metric"] == "hrv_sdnn" and row["value"] is None and row["context"] is None
    )
    assert row["provenance"] == "{}"
    assert (
        repository.apply_recovery_changes([observation(2)])[0].action
        == "stale_revision"
    )
    assert (
        repository.set_excluded(
            deleted.id, False, "3", deleted.payload_hash
        ).observation.effective_status
        == "deleted"
    )
    assert "value" not in RecoveryQueries(database).observation(deleted.id)
    assert (
        repository.apply_recovery_changes([observation(4)])[
            0
        ].observation.effective_status
        == "active"
    )
    repository.apply_recovery_changes(
        [observation(4, external_id="unseen", deleted=True)]
    )
    with pytest.raises(RecoveryError, match="recovery_identity_conflict"):
        repository.apply_recovery_changes(
            [observation(1, external_id="unseen", metric="hrv_rmssd")]
        )


def test_batch_atomicity_and_checkpoint_failure(database, monkeypatch):
    repository = RecoveryRepository(database, clock=lambda: NOW)
    repository.apply_recovery_changes([observation()])
    with pytest.raises(RecoveryError, match="revision_conflict"):
        repository.apply_recovery_changes(
            [observation(external_id="new"), observation(payload={"value": 51})],
            ("fixture", {"cursor": "next"}),
        )
    assert database.execute("SELECT count(*) FROM recovery_records")[0][0] == 1
    assert not database.execute("SELECT * FROM provider_state")
    execute = database.execute

    def fail(sql, params=()):
        if sql.startswith("INSERT INTO provider_state"):
            raise RuntimeError("synthetic checkpoint failure")
        return execute(sql, params)

    monkeypatch.setattr(database, "execute", fail)
    with pytest.raises(RuntimeError):
        repository.apply_recovery_changes(
            [observation(external_id="new")], ("fixture", {})
        )
    assert repository.generation() == 1
    assert database.execute("SELECT count(*) FROM recovery_records")[0][0] == 1
    for batch in (
        [observation(), observation(2)],
        [observation(external_id=str(i)) for i in range(101)],
        [replace(observation(), locally_excluded=True)],
        [replace(observation(), payload_hash="0" * 64)],
    ):
        with pytest.raises(RecoveryError):
            repository.apply_recovery_changes(batch)


def test_series_boundaries_corrections_and_cursor_generation(database):
    repository = RecoveryRepository(database, clock=lambda: NOW)
    records = repository.apply_recovery_changes(
        [observation(external_id=str(i)) for i in range(3)]
        + [
            observation(external_id="rmssd", metric="hrv_rmssd"),
            observation(external_id="spot", payload={"context": "spot"}),
            observation(external_id="algorithm", payload={"algorithm_version": "2"}),
            observation(external_id="source", source="second"),
        ]
    )
    queries = RecoveryQueries(database)
    assert not queries.observations(START, END, series=SERIES)["observations"]
    page = queries.observations(START, AFTER, series=SERIES, limit=1)
    assert len(page["observations"]) == 1 and page["next_cursor"]
    assert "provenance" not in page["observations"][0]
    next_page = queries.observations(
        START, AFTER, series=SERIES, limit=1, cursor=page["next_cursor"]
    )
    assert next_page["observations"][0]["id"] != page["observations"][0]["id"]
    with pytest.raises(RecoveryError, match="invalid_cursor"):
        queries.observations(
            START,
            AFTER,
            series={**SERIES, "context": "spot"},
            cursor=page["next_cursor"],
        )
    repository.apply_recovery_changes(
        [observation(2, external_id="0", payload={"context": "spot"})]
    )
    assert len(queries.observations(START, AFTER, series=SERIES)["observations"]) == 2
    assert (
        len(
            queries.observations(START, AFTER, series={**SERIES, "context": "spot"})[
                "observations"
            ]
        )
        == 2
    )
    with pytest.raises(RecoveryError, match="stale_cursor"):
        queries.observations(START, AFTER, series=SERIES, cursor=page["next_cursor"])
    selected = records[1].observation
    repository.set_excluded(selected.id, True, "1", selected.payload_hash)
    assert (
        queries.observations(START, AFTER, series=SERIES, excluded=True)[
            "observations"
        ][0]["id"]
        == selected.id
    )
    database.execute(
        "UPDATE recovery_records SET person_id='other' WHERE id=?", (selected.id,)
    )
    assert not queries.observations(START, AFTER, series=SERIES, excluded=True)[
        "observations"
    ]
    with pytest.raises(RecoveryError, match="not_found"):
        queries.observation(selected.id)
    for kwargs in (
        {"series": {}},
        {"series": SERIES, "limit": True},
        {"series": SERIES, "limit": 101},
        {"series": SERIES, "cursor": "bad"},
    ):
        with pytest.raises(RecoveryError):
            queries.observations(START, AFTER, **kwargs)


def test_concurrent_correction_and_exclusion(database):
    repository = RecoveryRepository(database, clock=lambda: NOW)
    first = repository.apply_recovery_changes([observation()])[0].observation

    def exclude():
        try:
            return repository.set_excluded(
                first.id, True, "1", first.payload_hash
            ).changed
        except RecoveryError as err:
            assert err.code == "revision_conflict"
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        exclusion = pool.submit(exclude)
        correction = pool.submit(repository.apply_recovery_changes, [observation(2)])
        changed, result = exclusion.result(), correction.result()[0].observation
    assert result.source_revision == 2
    assert (
        bool(database.execute("SELECT locally_excluded FROM recovery_records")[0][0])
        == changed
    )


def test_migration_eight_preserves_seven_and_is_atomic(tmp_path):
    path = tmp_path / "old.sqlite"
    connection = sqlite3.connect(path)
    apply_migrations(connection, MIGRATIONS[:7], latest=7)
    connection.execute(
        "INSERT INTO provider_state VALUES('fixture','{}','2026-09-07T00:00:00Z')"
    )
    connection.commit()
    with pytest.raises(sqlite3.OperationalError):
        apply_migrations(
            connection,
            ((8, (*MIGRATIONS[7][1], "SELECT missing FROM recovery_records")),),
            latest=8,
        )
    assert connection.execute("SELECT version FROM schema_info").fetchone()[0] == 7
    assert not connection.execute(
        "SELECT name FROM sqlite_master WHERE name='recovery_records'"
    ).fetchall()
    connection.close()
    database = HealthDatabase(path)
    database.open()
    assert database.execute("SELECT version FROM schema_info")[0][0] == 9
    assert database.execute("SELECT count(*) FROM provider_state")[0][0] == 1
    assert database.execute("SELECT count(*) FROM sleep_sessions")[0][0] == 0
    database.close()
