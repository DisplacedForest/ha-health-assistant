from datetime import UTC, datetime, timedelta

from homeassistant.util import dt as dt_util

from custom_components.health_assistant.overview import build_overview
from custom_components.health_assistant.store import HealthObservation, MetricType
from custom_components.health_assistant.store.units import canonical_unit

NOW = datetime(2026, 9, 6, 12, tzinfo=UTC)


def seed(repository, value, when, metric=MetricType.WEIGHT, provider="scale"):
    return repository.upsert_observation(
        HealthObservation(
            person_id="primary",
            metric=metric,
            value=value,
            unit=canonical_unit(metric),
            observed_at=when,
            provider=provider,
            external_id=f"reading-{when.isoformat()}",
            ingested_at=NOW,
        )
    )


def metric_result(database, repository, metric=MetricType.WEIGHT):
    return next(
        item
        for item in build_overview(database, repository, NOW)["metrics"]
        if item["metric"] == metric
    )


def test_weight_comparison_exclusion_and_future_readings(database, repository):
    seed(repository, 82, NOW - timedelta(days=7))
    current = seed(repository, 80, NOW - timedelta(hours=1))
    seed(repository, 500, NOW + timedelta(days=1))
    result = metric_result(database, repository)
    assert result["current"]["value"] == 80
    assert result["delta"] == -2
    assert result["state"] == "changed"
    repository.set_observation_excluded("primary", current.id, True)
    result = metric_result(database, repository)
    assert result["current"]["value"] == 82
    assert result["delta"] is None
    assert all(point["v"] not in (80, 500) for point in result["points"])


def test_source_change_and_conflict_do_not_become_change(database, repository):
    seed(repository, 90, NOW - timedelta(days=7), provider="old")
    seed(repository, 80, NOW, provider="new")
    result = metric_result(database, repository)
    assert result["state"] == "source_changed"
    assert result["delta"] is None
    seed(repository, 110, NOW - timedelta(seconds=30), provider="other")
    repository.set_priority(MetricType.WEIGHT, ["new", "other", "old"])
    result = metric_result(database, repository)
    assert result["current"]["provider"] == "new"
    assert result["state"] == "conflict"
    assert result["delta"] is None
    assert build_overview(database, repository, NOW)["metrics"][0]["metric"] == "weight"


def test_activity_compares_completed_local_days(database, repository):
    dt_util.set_default_time_zone(dt_util.get_time_zone("America/Chicago"))
    seed(repository, 4000, datetime(2026, 9, 5, 3, tzinfo=UTC), MetricType.STEPS)
    seed(repository, 7000, datetime(2026, 9, 6, 3, tzinfo=UTC), MetricType.STEPS)
    seed(repository, 30, NOW, MetricType.STEPS)
    result = metric_result(database, repository, MetricType.STEPS)
    assert result["current"]["value"] == 30
    assert result["delta"] == 3000
    assert result["compared"]["value"] == 7000
    assert result["comparison"]["value"] == 4000
    assert result["comparison_label"].startswith("Yesterday")


def test_sparse_and_stale_ordering(database, repository):
    seed(repository, 1, NOW - timedelta(days=30))
    seed(repository, 50, NOW, MetricType.LEAN_MASS)
    result = build_overview(database, repository, NOW)
    assert len(result["metrics"]) == 6
    assert result["metrics"][0]["metric"] == "lean_mass"
    assert result["metrics"][0]["delta"] is None
    assert result["metrics"][1]["metric"] == "weight"
    assert result["metrics"][1]["stale"]


def test_dense_points_are_bounded_and_keep_endpoints(database, repository):
    for index in range(400):
        seed(repository, 80 + index / 100, NOW - timedelta(minutes=400 - index))
    points = metric_result(database, repository)["points"]
    assert len(points) <= 120
    assert points[0]["v"] == 80
    assert points[-1]["v"] == 83.99


def test_long_provider_identity_is_preserved_until_presentation(database, repository):
    provider = "source-" + "a" * 122
    seed(repository, 82, NOW - timedelta(days=7), provider=provider)
    seed(repository, 80, NOW, provider=provider)
    result = metric_result(database, repository)
    assert result["state"] == "changed"
    assert result["delta"] == -2
    assert len(result["current"]["provider"]) == 120
    assert not any(point["source_changed"] for point in result["points"])

    seed(repository, 81, NOW - timedelta(days=3), provider=provider + "other")
    result = metric_result(database, repository)
    assert result["state"] == "source_changed"
    assert result["delta"] is None
    assert [point["source_changed"] for point in result["points"]] == [
        False,
        True,
        True,
    ]
    assert len({point["provider"] for point in result["points"]}) == 1
