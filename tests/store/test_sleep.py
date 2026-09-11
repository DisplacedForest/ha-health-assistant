import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from custom_components.health_assistant.store import HealthDatabase
from custom_components.health_assistant.store.schema import MIGRATIONS, apply_migrations
from custom_components.health_assistant.store.sleep import (
    SleepRepository,
    session_from_row,
)
from custom_components.health_assistant.store.sleep_models import (
    CandidateSleepSession,
    SleepError,
    SleepStageInterval,
    bounded_input,
    candidate_session,
    canonical,
    normalize_payload,
    normalized_session,
    revision64,
)
from custom_components.health_assistant.store.sleep_queries import SleepQueries, quality

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)
START = "2026-09-07T00:00:00.000000Z"
END = "2026-09-07T01:00:00.000000Z"
HOUR = 3_600_000_000


def session(
    revision=1,
    external_id="night",
    provider="fixture",
    source="account",
    payload=None,
    deleted=False,
    excluded=False,
):
    payload = payload or {"started_at": START, "ended_at": END}
    return normalized_session(
        provider,
        source,
        external_id,
        revision,
        None if deleted else payload,
        NOW,
        excluded=excluded,
    )


def stage(start=START, end=END, kind="light"):
    return {"start": start, "end": end, "stage": kind, "source_stage": kind}


def test_cross_language_frozen_vectors_and_sleep_projection():
    vectors = json.loads(
        (Path(__file__).parents[1] / "fixtures/sleep-hash-vectors.json").read_text()
    )
    for vector in vectors["vectors"]:
        encoded = canonical(json.loads(vector["input"]["raw_json"]))
        assert encoded.decode() == vector["verified"]["canonical_utf8"]
        assert hashlib.sha256(encoded).hexdigest() == vector["verified"]["sha256"]
    expected = "e1e9ae9cc834f6e7fa014dfbec2bb28ed9739708444771a73e7ae6e6d4eb7109"
    value = session(
        provider="bridge", source="source-example", external_id="record-example"
    )
    assert value.payload_hash == expected
    assert replace(value, source_revision=9223372036854775807).payload_hash == expected
    assert (
        session(
            payload={"started_at": START, "ended_at": END, "reported_totals": None}
        ).payload_hash
        == session().payload_hash
    )


@pytest.mark.parametrize(
    "value", [True, 1, 1.0, "-1", "01", "0", " 1", "1e0", "9223372036854775808"]
)
def test_revision_transport_is_exact_decimal_string(value):
    with pytest.raises(SleepError):
        revision64(value)


def test_revision_transport_preserves_64_bits():
    assert revision64("9223372036854775807") == 9223372036854775807


@pytest.mark.parametrize(
    "change",
    [
        {"started_at": "2026-09-07T00:00:00"},
        {"started_at": "2026-09-07T00:00:00+00:99"},
        {"started_at": "2026-09-07T00:00:00.0000001Z"},
        {"started_at": "2026-09-07T00:00:60Z"},
        {"ended_at": "2026-09-08T00:00:00Z"},
        {"started_at": "2026-09-04T00:00:00Z"},
        {"start_offset_seconds": True},
        {"start_offset_seconds": 64801},
        {"start_zone": "unknown/zone"},
        {"start_zone": "America/Chicago", "start_offset_seconds": 0},
        {"reported_totals": {"asleep": True}},
        {"reported_totals": {"awake": -1}},
        {"reported_totals": {"asleep": HOUR, "awake": 1}},
        {"reported_totals": {"asleep": 1, "deep": 2}},
        {"reported_totals": {"deep": HOUR, "rem": 1}},
        {"reported_totals": {"other": 1}},
        {"stages": None},
        {"in_bed_intervals": None},
        {"provenance": None},
        {"provenance": {"token": "unsupported"}},
        {"provenance": {"native_record_ids": ["a", "a"]}},
        {"provenance": {"native_record_ids": None}},
        {"provenance": {"source_app": "\ud800"}},
        {"provenance": {"provider_confidence": {"value": True}}},
        {"provenance": {"provider_confidence": {"value": float("inf")}}},
        {"provenance": {"provider_confidence": {"value": 1, "extra": "field"}}},
        {"stages": [stage(), stage()]},
        {"stages": [stage(), stage(kind="deep")]},
        {"stages": [stage(start="2026-09-06T23:59:59Z")]},
        {"stages": [stage(kind="unmapped")]},
        {"stages": [stage(kind=[])]},
        {"in_bed_intervals": [{"start": START, "end": END, "source_label": "a" * 65}]},
        {"unknown": None},
    ],
)
def test_invalid_candidates_rejected_as_a_whole(change):
    with pytest.raises(SleepError):
        session(payload={"started_at": START, "ended_at": END, **change})


@pytest.mark.parametrize(
    ("start", "end", "hours"),
    [
        ("2026-03-08T00:00:00-06:00", "2026-03-09T00:00:00-05:00", 23),
        ("2025-11-02T00:00:00-05:00", "2025-11-03T00:00:00-06:00", 25),
        ("2025-11-02T01:30:00-05:00", "2025-11-02T01:30:00-06:00", 1),
    ],
)
def test_dst_uses_instants(start, end, hours):
    value = normalize_payload(
        {
            "started_at": start,
            "ended_at": end,
            "start_zone": "America/Chicago",
            "end_zone": "America/Chicago",
        },
        NOW,
    )
    assert quality(value)["elapsed_us"] == hours * HOUR
    assert value["start_offset_seconds"] is None


def test_summary_coverage_context_and_no_inferred_sleep():
    missing = quality(session().payload)
    assert missing["value_basis"] == "missing"
    assert missing["asleep_duration_us"] is None
    half = "2026-09-07T00:30:00Z"
    partial = session(
        payload={"started_at": START, "ended_at": END, "stages": [stage(end=half)]}
    )
    result = quality(partial.payload)
    assert result["interval_totals"]["asleep"] == HOUR // 2
    assert result["uncovered_us"] == HOUR // 2
    assert result["asleep_duration_us"] is None
    full = session(
        payload={
            "started_at": START,
            "ended_at": END,
            "stages": [stage(end=half), stage(start=half, kind="out_of_bed")],
            "in_bed_intervals": [{"start": START, "end": END, "source_label": "inBed"}],
            "reported_totals": {"asleep": HOUR},
        }
    )
    result = quality(full.payload)
    assert result["asleep_duration_us"] == HOUR
    assert result["value_basis"] == "reported"
    assert result["interval_totals"]["asleep"] == HOUR // 2
    assert result["summary_interval_disagreement"]
    assert result["context_disagreement"]
    assert (
        quality(
            session(
                payload={
                    "started_at": START,
                    "ended_at": END,
                    "stages": [stage(kind="unknown")],
                }
            ).payload
        )["unknown_stage_us"]
        == HOUR
    )


def test_stage_dataclass_precision_and_source_metadata():
    candidate = CandidateSleepSession(
        "account",
        "night",
        1,
        START,
        END,
        stages=[SleepStageInterval(START, END, "rem", "asleepREM")],
        provenance={
            "native_record_ids": ["\ue000", "\U00010000"],
            "provider_confidence": {"value": 1},
        },
    )
    value = candidate_session("fixture", candidate, NOW)
    assert quality(value.payload)["value_basis"] == "derived_complete"
    assert quality(value.payload)["asleep_duration_us"] == HOUR
    assert value.payload["provenance"]["native_record_ids"] == ["\U00010000", "\ue000"]
    assert value.payload["provenance"]["provider_confidence"]["scale"] is None
    assert (
        candidate_session(
            "fixture",
            replace(
                candidate,
                provenance={
                    "native_record_ids": ["\U00010000", "\ue000"],
                    "provider_confidence": {"value": 1.0},
                },
            ),
            NOW,
        ).payload_hash
        == value.payload_hash
    )
    tiny = normalize_payload(
        {"started_at": START, "ended_at": "2026-09-07T00:00:00.000001Z"}, NOW
    )
    assert quality(tiny)["elapsed_us"] == 1


def test_size_depth_count_and_identity_bounds():
    with pytest.raises(SleepError):
        session(external_id="x" * 257)
    with pytest.raises(SleepError):
        session(revision=True)
    with pytest.raises(SleepError):
        normalized_session("p", "s", "e", 1, None, NOW, person_id="someone_else")
    with pytest.raises(SleepError):
        session(
            payload={"started_at": START, "ended_at": END, "stages": [stage()] * 4097}
        )
    with pytest.raises(SleepError):
        session(
            payload={
                "started_at": START,
                "ended_at": END,
                "provenance": {
                    "native_record_ids": [str(i) + "x" * 250 for i in range(300)]
                },
            }
        )
    nested = []
    for _ in range(10):
        nested = [nested]
    with pytest.raises(SleepError):
        bounded_input(nested)
    with pytest.raises(SleepError):
        canonical({"huge": "x" * 524288})


def test_revisions_delete_and_sticky_exclusion(database):
    repository = SleepRepository(database, clock=lambda: NOW)
    created = repository.apply_sleep_changes([session()])[0]
    snapshot = dict(database.execute("SELECT * FROM sleep_sessions")[0])
    assert repository.generation() == 1
    assert not repository.apply_sleep_changes([session()])[0].changed
    assert dict(database.execute("SELECT * FROM sleep_sessions")[0]) == snapshot
    with pytest.raises(SleepError, match="revision_conflict"):
        repository.apply_sleep_changes(
            [
                session(
                    payload={
                        "started_at": START,
                        "ended_at": END,
                        "reported_totals": {"asleep": 0},
                    }
                )
            ]
        )
    repository.set_excluded(created.session.id, True, "1", created.session.payload_hash)
    corrected = repository.apply_sleep_changes(
        [
            session(
                revision=2,
                payload={"started_at": START, "ended_at": END, "stages": [stage()]},
            )
        ]
    )[0].session
    assert corrected.locally_excluded
    assert corrected.payload["stages"]
    removed = repository.apply_sleep_changes([session(revision=3)])[0].session
    assert removed.payload["stages"] == []
    deleted = repository.apply_sleep_changes([session(revision=4, deleted=True)])[
        0
    ].session
    assert deleted.payload is None
    row = dict(database.execute("SELECT * FROM sleep_sessions")[0])
    assert row["started_at"] is None and row["reported_totals"] is None
    assert row["stages"] == "[]" and row["provenance"] == "{}"
    assert (
        repository.apply_sleep_changes([session(revision=3)])[0].action
        == "stale_revision"
    )
    restored = repository.set_excluded(
        deleted.id, False, "4", deleted.payload_hash
    ).session
    assert restored.effective_status == "deleted"
    assert (
        repository.apply_sleep_changes([session(revision=5)])[
            0
        ].session.effective_status
        == "active"
    )
    early_delete = repository.apply_sleep_changes(
        [session(external_id="unseen", revision=3, deleted=True)]
    )[0].session
    assert early_delete.payload is None
    assert (
        repository.apply_sleep_changes([session(external_id="unseen")])[0].action
        == "stale_revision"
    )


def test_batch_rolls_back_conflict_and_checkpoint_failure(database, monkeypatch):
    repository = SleepRepository(database, clock=lambda: NOW)
    repository.apply_sleep_changes([session()])
    with pytest.raises(SleepError):
        repository.apply_sleep_changes(
            [
                session(external_id="second"),
                session(
                    payload={
                        "started_at": START,
                        "ended_at": END,
                        "reported_totals": {"asleep": 0},
                    }
                ),
            ],
            ("fixture", {"cursor": "after"}),
        )
    assert database.execute("SELECT count(*) FROM sleep_sessions")[0][0] == 1
    assert database.execute("SELECT count(*) FROM provider_state")[0][0] == 0
    execute = database.execute

    def fail(sql, params=()):
        if sql.startswith("INSERT INTO provider_state"):
            raise RuntimeError("synthetic checkpoint failure")
        return execute(sql, params)

    monkeypatch.setattr(database, "execute", fail)
    with pytest.raises(RuntimeError):
        repository.apply_sleep_changes(
            [session(external_id="second")], ("fixture", {"cursor": "after"})
        )
    assert database.execute("SELECT count(*) FROM sleep_sessions")[0][0] == 1
    assert repository.generation() == 1
    with pytest.raises(SleepError):
        repository.apply_sleep_changes([session(), session(revision=2)])


def test_concurrent_corrections_never_move_backwards(database):
    repository = SleepRepository(database, clock=lambda: NOW)
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(
            executor.map(
                lambda revision: repository.apply_sleep_changes(
                    [session(revision=revision)]
                ),
                [1, 9, 4, 7, 10, 3, 8, 2],
            )
        )
    assert database.execute("SELECT source_revision FROM sleep_sessions")[0][0] == 10
    stored = session_from_row(database.execute("SELECT * FROM sleep_sessions")[0])
    with pytest.raises(SleepError, match="revision_conflict"):
        repository.set_excluded(stored.id, True, "9", stored.payload_hash)
    assert not repository.set_excluded(
        stored.id, False, "10", stored.payload_hash
    ).changed


def test_primary_scoped_list_detail_and_cursors(database):
    repository = SleepRepository(database, clock=lambda: NOW)
    values = repository.apply_sleep_changes(
        [session(external_id=str(i), source=f"source-{i}") for i in range(3)]
    )
    queries = SleepQueries(database)
    page = queries.sessions(START, END, limit=1)
    assert len(page["sessions"]) == 1 and page["next_cursor"]
    assert (
        "stages" not in page["sessions"][0] and "provenance" not in page["sessions"][0]
    )
    assert (
        len(queries.sessions(START, END, source=("fixture", "source-0"))["sessions"])
        == 1
    )
    assert not queries.sessions(START, END, date_basis="ended_at")["sessions"]
    assert queries.sessions(
        START, "2026-09-07T01:00:00.000001Z", date_basis="ended_at"
    )["sessions"]
    second = queries.sessions(START, END, limit=1, cursor=page["next_cursor"])
    assert second["sessions"][0]["id"] != page["sessions"][0]["id"]
    selected = values[0].session
    repository.set_excluded(selected.id, True, "1", selected.payload_hash)
    assert len(queries.sessions(START, END, excluded=True)["sessions"]) == 1
    with pytest.raises(SleepError, match="stale_cursor"):
        queries.sessions(START, END, cursor=page["next_cursor"])
    assert queries.session(selected.id)["status"] == "excluded"
    database.execute(
        "UPDATE sleep_sessions SET person_id=? WHERE id=?", ("other", selected.id)
    )
    with pytest.raises(SleepError, match="not_found"):
        queries.session(selected.id)
    assert not queries.sessions(START, END, excluded=True)["sessions"]


def test_detail_pins_revision_and_kind(database):
    midpoint = "2026-09-07T00:30:00Z"
    value = session(
        payload={
            "started_at": START,
            "ended_at": END,
            "stages": [stage(end=midpoint), stage(start=midpoint, kind="deep")],
        }
    )
    repository = SleepRepository(database, clock=lambda: NOW)
    stored = repository.apply_sleep_changes([value])[0].session
    queries = SleepQueries(database)
    page = queries.session(stored.id, limit=1)
    assert len(page["intervals"]) == 1
    assert (
        queries.session(stored.id, cursor=page["next_cursor"])["intervals"][0]["stage"]
        == "deep"
    )
    with pytest.raises(SleepError, match="invalid_cursor"):
        queries.session(stored.id, kind="in_bed_intervals", cursor=page["next_cursor"])
    repository.apply_sleep_changes([session(revision=2, deleted=True)])
    with pytest.raises(SleepError, match="stale_cursor"):
        queries.session(stored.id, cursor=page["next_cursor"])
    assert "started_at" not in queries.session(stored.id)


def test_migration_seven_is_additive_and_rollback_is_atomic(tmp_path):
    path = tmp_path / "old.sqlite"
    connection = sqlite3.connect(path)
    apply_migrations(connection, MIGRATIONS[:6], latest=6)
    connection.execute(
        "INSERT INTO provider_state VALUES('fixture','{}','2026-09-07T00:00:00Z')"
    )
    connection.commit()
    broken = ((7, (*MIGRATIONS[6][1], "SELECT missing_column FROM sleep_sessions")),)
    with pytest.raises(sqlite3.OperationalError):
        apply_migrations(connection, broken, latest=7)
    assert connection.execute("SELECT version FROM schema_info").fetchone()[0] == 6
    assert not connection.execute(
        "SELECT name FROM sqlite_master WHERE name='sleep_sessions'"
    ).fetchall()
    connection.close()
    database = HealthDatabase(path)
    database.open()
    assert database.execute("SELECT version FROM schema_info")[0][0] == 10
    assert database.execute("SELECT count(*) FROM provider_state")[0][0] == 1
    assert database.execute("SELECT count(*) FROM sleep_sessions")[0][0] == 0
    database.close()


@pytest.mark.parametrize(
    "kind",
    (
        "awake",
        "awake_in_bed",
        "out_of_bed",
        "asleep_unspecified",
        "light",
        "deep",
        "rem",
        "unknown",
    ),
)
def test_all_stage_vocabulary_preserves_raw_labels(kind):
    value = session(
        payload={
            "started_at": START,
            "ended_at": END,
            "stages": [{**stage(kind=kind), "source_stage": "original vendor label"}],
        }
    )
    assert value.payload["stages"][0]["source_stage"] == "original vendor label"
    result = quality(value.payload)
    assert result["asleep_duration_us"] == (
        None
        if kind == "unknown"
        else HOUR
        if kind in ("light", "deep", "rem", "asleep_unspecified")
        else 0
    )


def test_completed_session_accepts_exact_48_hour_bound():
    value = normalize_payload(
        {"started_at": "2026-09-05T12:00:00Z", "ended_at": "2026-09-07T12:00:00Z"}, NOW
    )
    assert quality(value)["elapsed_us"] == 48 * HOUR
    with pytest.raises(SleepError):
        normalize_payload(
            {
                "started_at": "2026-09-05T11:59:59.999999Z",
                "ended_at": "2026-09-07T12:00:00Z",
            },
            NOW,
        )


def test_batch_count_bound_leaves_store_unchanged(database):
    repository = SleepRepository(database, clock=lambda: NOW)
    with pytest.raises(SleepError, match="sleep_batch_limit"):
        repository.apply_sleep_changes(
            [session(external_id=str(i)) for i in range(101)]
        )
    assert repository.generation() == 0
    assert database.execute("SELECT count(*) FROM sleep_sessions")[0][0] == 0


def test_complete_in_bed_context_can_disagree_with_reported_total():
    value = session(
        payload={
            "started_at": START,
            "ended_at": END,
            "in_bed_intervals": [{"start": START, "end": END, "source_label": "inBed"}],
            "reported_totals": {"in_bed": 0},
        }
    )
    assert quality(value.payload)["summary_interval_disagreement"]
