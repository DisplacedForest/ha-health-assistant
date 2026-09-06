from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.health_assistant.store import (
    HealthObservation,
    HealthRepository,
    MetricType,
    RecordStatus,
    StoreValidationError,
)

AT = datetime(2026, 9, 1, 8, tzinfo=UTC)


def reading(provider="scale", offset=0, value=80.0, metric=MetricType.WEIGHT):
    return HealthObservation(
        person_id="primary",
        metric=metric,
        value=value,
        unit="count" if metric is MetricType.STEPS else "kg",
        observed_at=AT + timedelta(seconds=offset),
        provider=provider,
        external_id=f"record-{offset}",
        ingested_at=AT,
    )


def test_exclusion_survives_replay_new_source_priority_and_restart(
    repository, database
):
    original = repository.upsert_observation(reading())
    repository.upsert_observation(reading("bridge", 10))
    repository.set_observation_excluded("primary", original.id, True)
    assert repository.get_observations("primary") == []
    assert repository.latest_observation("primary", MetricType.WEIGHT) is None
    assert repository.body_measurements("primary") == []
    repository.upsert_observation(reading())
    repository.upsert_observation(reading("new_bridge", 20))
    repository.set_priority(MetricType.WEIGHT, ["new_bridge", "bridge", "scale"])
    database.close()
    database.open()
    repository = HealthRepository(database)
    repository.reconcile_metric("primary", MetricType.WEIGHT)
    assert repository.get_observations("primary") == []
    excluded = repository.list_observations("primary", excluded=True)
    assert len(excluded) == 1
    assert len(repository.get_claims(excluded[0].id)) == 3
    assert all(
        c.status is RecordStatus.EXCLUDED for c in repository.get_claims(excluded[0].id)
    )
    repository.set_observation_excluded("primary", excluded[0].id, False)
    repository.set_observation_excluded("primary", excluded[0].id, False)
    assert len(repository.get_observations("primary")) == 1
    assert repository.list_observations("primary", excluded=True) == []


def test_corrected_identity_stays_excluded_but_distinct_reading_does_not(repository):
    original = repository.upsert_observation(reading())
    repository.set_observation_excluded("primary", original.id, True)
    repository.upsert_observation(replace(reading(), value=81.0))
    repository.upsert_observation(reading("scale", 86400, 81.0))
    repository.upsert_observation(reading("independent", 30, 95.0))
    values = [r.value for r in repository.get_observations("primary")]
    assert values == [95.0, 81.0]
    assert repository.latest_observation(
        "primary", MetricType.WEIGHT
    ).observed_at == AT + timedelta(days=1)


def test_excluded_daily_activity_falls_back_to_prior_reading(repository):
    repository.upsert_observation(reading(offset=0, value=100, metric=MetricType.STEPS))
    newer = repository.upsert_observation(
        reading(offset=300, value=900, metric=MetricType.STEPS)
    )
    repository.set_observation_excluded("primary", newer.id, True)
    assert repository.daily_activity("primary")[0].steps == 100
    assert repository.latest_observation("primary", MetricType.STEPS).value == 100


@pytest.mark.parametrize("identifier", [None, 0, -1, True, "1", 1.5, 999])
def test_invalid_exclusion_never_changes_history(repository, identifier):
    repository.upsert_observation(reading())
    with pytest.raises(StoreValidationError):
        repository.set_observation_excluded("primary", identifier, True)
    assert len(repository.get_observations("primary")) == 1


def test_exclusion_is_scoped_to_person(repository):
    original = repository.upsert_observation(reading())
    with pytest.raises(StoreValidationError):
        repository.set_observation_excluded("someone_else", original.id, True)
    assert repository.get_observation("someone_else", original.id) is None
    assert len(repository.get_observations("primary")) == 1


def test_exclusion_rolls_back_claims_if_reconciliation_fails(repository, monkeypatch):
    original = repository.upsert_observation(reading())

    def fail(*args):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(repository, "_apply_reconciliation", fail)
    with pytest.raises(RuntimeError, match="injected failure"):
        repository.set_observation_excluded("primary", original.id, True)
    assert repository.get_claims(original.id)[0].status is RecordStatus.ACTIVE
    assert len(repository.get_observations("primary")) == 1


def test_replay_from_separate_repositories_cannot_clear_exclusion(repository, database):
    original = repository.upsert_observation(reading())
    repository.set_observation_excluded("primary", original.id, True)

    def replay(index):
        repo = HealthRepository(database)
        repo.upsert_observation(reading(f"bridge_{index}", index % 30))
        repo.reconcile_metric("primary", MetricType.WEIGHT)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(replay, range(40)))
    assert repository.get_observations("primary") == []
    assert len(repository.list_observations("primary", excluded=True)) == 1


def test_observation_list_is_bounded_and_pages_by_id(repository):
    for index in range(5):
        repository.upsert_observation(reading(offset=index * 86400))
    first = repository.list_observations("primary", limit=2)
    second = repository.list_observations("primary", before_id=first[-1].id, limit=2)
    assert [r.id for r in first + second] == [5, 4, 3, 2]
    with pytest.raises(StoreValidationError):
        repository.list_observations("primary", limit=101)


def test_outer_transaction_rolls_back_nested_ingestion(repository):
    with pytest.raises(RuntimeError), repository._db.transaction():
        repository.upsert_observation(reading())
        raise RuntimeError("abort whole batch")
    assert repository.get_observations("primary") == []
    assert repository._db.execute("SELECT COUNT(*) FROM source_claims")[0][0] == 0
    assert repository.upsert_observation(reading()).value == 80.0


def test_inner_transaction_rollback_does_not_abort_outer_work(repository):
    with repository._db.transaction():
        original = repository.upsert_observation(reading())
        with pytest.raises(RuntimeError), repository._db.transaction():
            repository.set_observation_excluded("primary", original.id, True)
            raise RuntimeError("abort inner batch")
        repository.upsert_observation(reading(offset=86400))
    assert len(repository.get_observations("primary")) == 2
    assert repository.list_observations("primary", excluded=True) == []


def test_upgrade_from_prior_schema_preserves_history(tmp_path):
    import sqlite3

    from custom_components.health_assistant.store import HealthDatabase
    from custom_components.health_assistant.store.schema import (
        MIGRATIONS,
        apply_migrations,
    )

    path = tmp_path / "prior.sqlite"
    connection = sqlite3.connect(path)
    apply_migrations(connection, MIGRATIONS[:4], latest=4)
    connection.execute(
        "INSERT INTO observations (id, person_id, metric, value, unit, observed_at, provider, external_id, ingested_at) VALUES (1, 'primary', 'weight', 80, 'kg', ?, 'scale', 'legacy', ?)",
        (AT.isoformat(), AT.isoformat()),
    )
    connection.execute(
        "INSERT INTO source_claims (id, observation_id, person_id, metric, value, unit, observed_at, provider, external_id, ingested_at) VALUES (1, 1, 'primary', 'weight', 80, 'kg', ?, 'scale', 'legacy', ?)",
        (AT.isoformat(), AT.isoformat()),
    )
    connection.commit()
    connection.close()
    database = HealthDatabase(path)
    database.open()
    try:
        repository = HealthRepository(database)
        assert repository.latest_observation("primary", MetricType.WEIGHT).value == 80
        repository.set_observation_excluded("primary", 1, True)
        assert repository.latest_observation("primary", MetricType.WEIGHT) is None
        assert repository.get_claims(1)[0].external_id == "legacy"
    finally:
        database.close()
