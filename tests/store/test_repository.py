from datetime import UTC, datetime, timedelta, timezone

import pytest

from custom_components.health_assistant.store import (
    HealthObservation,
    MetricType,
    StoreValidationError,
    Workout,
)

OBSERVED = datetime(2026, 8, 20, 7, 30, tzinfo=UTC)
INGESTED = datetime(2026, 8, 21, 9, 0, tzinfo=UTC)


def observation(**overrides):
    base = {
        "person_id": "primary",
        "metric": MetricType.WEIGHT,
        "value": 82.5,
        "unit": "kg",
        "observed_at": OBSERVED,
        "provider": "test_scale",
        "external_id": "reading-1",
        "ingested_at": INGESTED,
        "provenance": {"device": "scale", "raw_unit": "lb"},
    }
    base.update(overrides)
    return HealthObservation(**base)


def workout(**overrides):
    base = {
        "person_id": "primary",
        "provider": "test_tracker",
        "external_id": "workout-1",
        "workout_type": "strength",
        "title": "Push day",
        "started_at": OBSERVED,
        "ended_at": OBSERVED + timedelta(hours=1),
        "energy_kcal": 420.0,
        "distance_m": None,
        "ingested_at": INGESTED,
        "provenance": {"app": "test"},
    }
    base.update(overrides)
    return Workout(**base)


def test_observation_round_trip(repository):
    stored = repository.upsert_observation(observation())
    assert stored.id is not None
    fetched = repository.get_observations("primary", MetricType.WEIGHT)
    assert fetched == [stored]
    assert fetched[0].provenance == {"device": "scale", "raw_unit": "lb"}
    assert fetched[0].observed_at == OBSERVED


def test_observed_at_normalizes_to_utc(repository):
    local = OBSERVED.astimezone(timezone(timedelta(hours=-5)))
    stored = repository.upsert_observation(observation(observed_at=local))
    assert stored.observed_at == OBSERVED
    assert stored.observed_at.tzinfo == UTC


def test_duplicate_ingestion_converges(repository):
    first = repository.upsert_observation(observation(value=82.5))
    corrected = repository.upsert_observation(
        observation(value=81.9, provenance={"device": "scale", "corrected": True})
    )
    assert corrected.id == first.id
    rows = repository.get_observations("primary", MetricType.WEIGHT)
    assert len(rows) == 1
    assert rows[0].value == 81.9
    assert rows[0].provenance == {"device": "scale", "corrected": True}


def test_distinct_observed_at_creates_new_record(repository):
    repository.upsert_observation(observation())
    repository.upsert_observation(observation(observed_at=OBSERVED + timedelta(days=1)))
    assert len(repository.get_observations("primary", MetricType.WEIGHT)) == 2


def test_query_ordering_and_range(repository):
    later = repository.upsert_observation(
        observation(observed_at=OBSERVED + timedelta(days=2), external_id="r3")
    )
    earlier = repository.upsert_observation(
        observation(observed_at=OBSERVED, external_id="r1")
    )
    middle = repository.upsert_observation(
        observation(observed_at=OBSERVED + timedelta(days=1), external_id="r2")
    )
    assert repository.get_observations("primary", MetricType.WEIGHT) == [
        earlier,
        middle,
        later,
    ]
    ranged = repository.get_observations(
        "primary",
        MetricType.WEIGHT,
        start=OBSERVED + timedelta(days=1),
        end=OBSERVED + timedelta(days=2),
    )
    assert ranged == [middle]


def test_latest_observation(repository):
    repository.upsert_observation(observation(external_id="r1"))
    newest = repository.upsert_observation(
        observation(observed_at=OBSERVED + timedelta(days=3), external_id="r2")
    )
    assert repository.latest_observation("primary", MetricType.WEIGHT) == newest
    assert repository.latest_observation("primary", MetricType.STEPS) is None


def test_person_isolation(repository):
    repository.upsert_observation(observation())
    assert repository.get_observations("someone_else") == []


def test_body_measurements_group_by_observed_at(repository):
    repository.upsert_observation(observation(value=82.5))
    repository.upsert_observation(
        observation(
            metric=MetricType.BODY_FAT_PERCENTAGE,
            value=21.0,
            unit="%",
            external_id="reading-1-bf",
        )
    )
    measurements = repository.body_measurements("primary")
    assert len(measurements) == 1
    assert measurements[0].weight_kg == 82.5
    assert measurements[0].body_fat_percentage == 21.0
    assert measurements[0].lean_mass_kg is None


def test_daily_activity_groups_by_day(repository):
    repository.upsert_observation(
        observation(
            metric=MetricType.STEPS, value=9000, unit="count", external_id="steps-1"
        )
    )
    repository.upsert_observation(
        observation(
            metric=MetricType.DISTANCE, value=6500.0, unit="m", external_id="dist-1"
        )
    )
    repository.upsert_observation(
        observation(
            metric=MetricType.STEPS,
            value=4000,
            unit="count",
            external_id="steps-2",
            observed_at=OBSERVED + timedelta(days=1),
        )
    )
    days = repository.daily_activity("primary")
    assert len(days) == 2
    assert days[0].steps == 9000
    assert days[0].distance_m == 6500.0
    assert days[0].active_energy_kcal is None
    assert days[1].steps == 4000


@pytest.mark.parametrize(
    "bad",
    [
        {"unit": "lb"},
        {"observed_at": OBSERVED.replace(tzinfo=None)},
        {"value": float("nan")},
        {"value": True},
        {"external_id": "  "},
        {"provider": ""},
        {"metric": "blood_type"},
        {"provenance": "not-a-dict"},
    ],
)
def test_malformed_observation_rejected(repository, bad):
    with pytest.raises(StoreValidationError):
        repository.upsert_observation(observation(**bad))
    assert repository.get_observations("primary") == []


def test_workout_round_trip_and_dedup(repository):
    first = repository.upsert_workout(workout())
    updated = repository.upsert_workout(workout(title="Push day (edited)"))
    assert updated.id == first.id
    workouts = repository.get_workouts("primary")
    assert len(workouts) == 1
    assert workouts[0].title == "Push day (edited)"
    assert workouts[0].energy_kcal == 420.0


def test_workout_range_query(repository):
    repository.upsert_workout(workout())
    repository.upsert_workout(
        workout(
            external_id="workout-2",
            started_at=OBSERVED + timedelta(days=5),
            ended_at=OBSERVED + timedelta(days=5, hours=1),
        )
    )
    ranged = repository.get_workouts("primary", start=OBSERVED + timedelta(days=1))
    assert len(ranged) == 1
    assert ranged[0].external_id == "workout-2"


def test_workout_end_before_start_rejected(repository):
    with pytest.raises(StoreValidationError):
        repository.upsert_workout(workout(ended_at=OBSERVED - timedelta(minutes=1)))
