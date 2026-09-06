import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from custom_components.health_assistant.body import (
    build_body,
    exercise_map,
    normalize_exercise,
    workout_detail,
)
from custom_components.health_assistant.store import RecordStatus, Workout

NOW = datetime(2026, 9, 6, 12, tzinfo=UTC)


def workout(repository, key, exercises=None, age=0, **kwargs):
    ended = NOW - timedelta(days=age)
    return repository.upsert_workout(
        Workout(
            person_id=kwargs.pop("person_id", "primary"),
            provider=kwargs.pop("provider", "fixture"),
            external_id=key,
            workout_type="strength",
            title="Recorded session",
            started_at=ended - timedelta(hours=1),
            ended_at=ended,
            ingested_at=NOW,
            provenance=kwargs.pop("provenance", {"exercises": exercises or []}),
            **kwargs,
        )
    )


def exercise(name, count=1):
    return {"name": name, "sets": [{"type": "normal", "reps": 8}] * count}


def region(result, name):
    return next(item for item in result["regions"] if item["key"] == name)


def test_map_has_unique_exact_aliases_and_matches_figure_regions():
    root = Path(__file__).parents[2]
    data = json.loads(
        (root / "custom_components/health_assistant/exercise_map.json").read_text()
    )
    labels, aliases = exercise_map()
    names = [
        normalize_exercise(name)
        for item in data["exercises"]
        for name in item["aliases"]
    ]
    assert len(names) == len(set(names)) == len(aliases)
    assert all(set(item["regions"]) <= labels.keys() for item in data["exercises"])
    assert all(
        item["reference"].startswith("https://www.hevyapp.com/")
        for item in data["exercises"]
    )
    figure = (root / "frontend-src/src/body-figure.js").read_text()
    assert set(re.findall(r'key: "(\w+)"', figure)) == labels.keys()
    assert aliases[normalize_exercise("  BENCH  Press (Barbell) ")] == (
        "chest",
        "triceps",
        "shoulders",
    )
    assert normalize_exercise("bench press mystery") not in aliases


def test_recent_sets_decay_and_remain_source_agnostic(database, repository):
    push = exercise("Bench Press (Barbell)", 2)
    push["sets"].append({"type": "warmup", "reps": 10})
    first = workout(repository, "push", [push], age=3.5, provider="hevy")
    second = workout(
        repository, "legs", [exercise("Squat (Barbell)")], provider="other"
    )
    result = build_body(database, NOW)
    assert region(result, "chest")["score"] == 1
    assert region(result, "chest")["recorded_sets"] == 2
    assert region(result, "chest")["workout_ids"] == [first.id]
    assert region(result, "quads")["score"] == 1
    assert region(result, "quads")["workout_ids"] == [second.id]
    assert region(result, "chest")["heat"] == 1
    assert region(result, "back")["heat"] == 0
    assert result["workouts_without_sets"] == 0
    assert result["incomplete_workouts"] == 0


def test_unknown_exercises_and_missing_sets_are_visible(database, repository):
    workout(repository, "unknown", [exercise("New custom movement")])
    workout(repository, "summary")
    result = build_body(database, NOW)
    assert result["unmapped"] == [{"name": "New custom movement", "occurrences": 1}]
    assert result["unmapped_count"] == 1
    assert result["workout_count"] == 2
    assert result["workouts_without_sets"] == 1
    assert all(item["score"] == 0 for item in result["regions"])


def test_workout_window_excludes_future_other_people_and_inactive(database, repository):
    workout(repository, "old", age=7)
    workout(repository, "future", age=-1)
    workout(repository, "excluded", status=RecordStatus.EXCLUDED)
    other = workout(repository, "other", person_id="other")
    kept = workout(repository, "current", age=6.9)
    result = build_body(database, NOW)
    assert result["workout_count"] == 1
    assert result["workouts"][0]["id"] == kept.id
    assert workout_detail(database, other.id) is None


def test_oversized_legacy_detail_and_workout_limit_are_explicit(database, repository):
    for index in range(101):
        workout(repository, f"session-{index}")
    huge = workout(
        repository, "large", provenance={"exercises": [], "legacy": "界" * 100000}
    )
    result = build_body(database, NOW)
    assert result["workout_count"] == 102
    assert len(result["workouts"]) == 100
    assert result["truncated"]
    assert result["incomplete_workouts"] == 1
    assert len(json.dumps(result).encode()) < 100000
    detail = workout_detail(database, huge.id)
    assert detail["incomplete"]
    assert detail["exercises"] == []


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "not a set",
        {},
        {"reps": True},
        {"reps": -1},
        {"reps": 1.5},
        {"reps": 10**1000},
        {"reps": 8, "weight_kg": "heavy"},
    ],
)
def test_malformed_sets_do_not_create_heat(database, repository, bad):
    workout(repository, "bad", [{"name": "Bench Press (Barbell)", "sets": [bad]}])
    result = build_body(database, NOW)
    assert result["incomplete_workouts"] == 1
    assert result["workouts_without_sets"] == 1
    assert region(result, "chest")["score"] == 0


def test_workout_detail_has_allowlisted_fields_and_bounded_sets(database, repository):
    sets = [{"type": "normal", "reps": 8, "weight_kg": 20, "secret": "private"}] * 101
    source = [{"name": "Bench Press (Barbell)", "sets": sets, "notes": "n" * 1001}] * 11
    saved = workout(
        repository, "details", provenance={"exercises": source, "token": "secret"}
    )
    result = workout_detail(database, saved.id)
    assert result["incomplete"]
    assert sum(len(item["sets"]) for item in result["exercises"]) == 1000
    assert all(len(item["notes"]) == 1000 for item in result["exercises"])
    encoded = json.dumps(result, allow_nan=False)
    assert "secret" not in encoded
    assert "private" not in encoded
    assert len(encoded.encode()) < 262144


def test_unknown_exercise_labels_are_bounded_with_total_count(database, repository):
    workout(
        repository, "unknowns", [exercise(f"Custom {index}") for index in range(30)]
    )
    result = build_body(database, NOW)
    assert len(result["unmapped"]) == 20
    assert result["unmapped_count"] == 30
