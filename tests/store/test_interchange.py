from datetime import UTC, datetime, timedelta

import pytest

from custom_components.health_assistant.store import (
    HealthDatabase,
    HealthObservation,
    HealthRepository,
    MetricType,
    StoreValidationError,
    Workout,
)
from custom_components.health_assistant.store.environment import (
    EnvironmentAccumulator,
    EnvironmentRepository,
)
from custom_components.health_assistant.store.interchange import (
    export_archive,
    import_archive,
)

NOW = datetime(2026, 9, 6, 12, tzinfo=UTC)


def populate(database, repository):
    for provider, value in (("scale", 80), ("watch", 80.1)):
        observation = repository.upsert_observation(
            HealthObservation(
                person_id="primary",
                metric=MetricType.WEIGHT,
                value=value,
                unit="kg",
                observed_at=NOW,
                provider=provider,
                external_id="reading",
                ingested_at=NOW,
                provenance={"source": provider},
            )
        )
    repository.set_priority(MetricType.WEIGHT, ["scale", "watch"])
    repository.set_observation_excluded("primary", observation.id, True)
    repository.upsert_workout(
        Workout(
            person_id="primary",
            provider="hevy",
            external_id="workout",
            workout_type="strength",
            title="Morning",
            started_at=NOW - timedelta(hours=1),
            ended_at=NOW,
            ingested_at=NOW,
            provenance={
                "exercises": [
                    {"title": "Squat", "sets": [{"reps": 5, "weight_kg": 80}]}
                ]
            },
        )
    )
    environment = EnvironmentRepository(database)
    stream = environment.register(
        {
            "mapping_id": "bedroom",
            "source_id": "sensor.temperature",
            "entity_id": "sensor.temperature",
            "metric": "temperature",
            "area_id": "bedroom",
            "area_name": "Bedroom",
        }
    )
    timestamp = int(NOW.timestamp() * 1000)
    accumulator = EnvironmentAccumulator(stream["id"], timestamp)
    accumulator.report(timestamp, 20)
    accumulator.report(timestamp + 60000, None)
    environment.save(accumulator.stop(timestamp + 120000), timestamp + 120000)
    database.execute(
        "UPDATE environment_maintenance SET last_success_ms=?, duration_ms=3, rolled_up=1 WHERE id=1",
        (timestamp,),
    )


def logical(database):
    result = {}
    for table in (
        "observations",
        "source_claims",
        "workouts",
        "metric_priorities",
        "environment_streams",
        "environment_buckets",
        "environment_maintenance",
    ):
        rows = []
        for row in database.execute(f"SELECT * FROM {table}"):
            value = dict(row)
            value.pop("id", None)
            value.pop("observation_id", None)
            if "stream_id" in value:
                value["stream_id"] = database.execute(
                    "SELECT public_id FROM environment_streams WHERE id=?",
                    (value["stream_id"],),
                )[0]["public_id"]
            rows.append(value)
        result[table] = sorted(rows, key=str)
    return result


def test_full_roundtrip_dry_run_and_exact_replay(database, repository, tmp_path):
    populate(database, repository)
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)
    target = HealthDatabase(tmp_path / "target.sqlite")
    target.open()
    try:
        empty = logical(target)
        preview = import_archive(target, archive)
        assert preview["dry_run"]
        assert preview["records"]["source_claims"] == 2
        assert preview["expected"]["source_claims"]["create"] == 2
        assert logical(target) == empty
        result = import_archive(target, archive, dry_run=False)
        assert not result["dry_run"]
        assert logical(target) == logical(database)
        before = logical(target)
        result = import_archive(target, archive, dry_run=False)
        assert logical(target) == before
        assert all(
            count["create"] == count["merge"] == 0
            for count in result["applied"].values()
        )
    finally:
        target.close()


@pytest.mark.parametrize(
    "failed_domain", ["source_claims", "environment_streams", "environment_buckets"]
)
def test_mid_import_failure_replays_consistently(
    database, repository, tmp_path, failed_domain
):
    populate(database, repository)
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)
    target = HealthDatabase(tmp_path / "target.sqlite")
    target.open()
    try:

        def fail(domain):
            if domain == failed_domain:
                raise RuntimeError("Injected stop")

        with pytest.raises(RuntimeError, match="Injected"):
            import_archive(target, archive, dry_run=False, after_batch=fail)
        assert target.execute("SELECT count(*) FROM source_claims")[0][0] == 2
        assert target.execute("SELECT status FROM observations")[0][0] == "excluded"
        import_archive(target, archive, dry_run=False)
        assert logical(target) == logical(database)
    finally:
        target.close()


def test_person_identity_conflict_is_rejected_before_live_write(
    database, repository, tmp_path
):
    populate(database, repository)
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)
    target = HealthDatabase(tmp_path / "target.sqlite")
    target.open()
    try:
        HealthRepository(target).upsert_observation(
            HealthObservation(
                person_id="other",
                metric=MetricType.WEIGHT,
                value=50,
                unit="kg",
                observed_at=NOW,
                provider="scale",
                external_id="reading",
                ingested_at=NOW,
            )
        )
        before = logical(target)
        with pytest.raises(StoreValidationError, match="different person"):
            import_archive(target, archive, dry_run=False)
        assert logical(target) == before
    finally:
        target.close()


def test_overlap_keeps_newer_values_and_exclusions(database, repository, tmp_path):
    populate(database, repository)
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)
    target = HealthDatabase(tmp_path / "target.sqlite")
    target.open()
    try:
        local = HealthRepository(target)
        local.upsert_observation(
            HealthObservation(
                person_id="primary",
                metric=MetricType.WEIGHT,
                value=82,
                unit="kg",
                observed_at=NOW,
                provider="scale",
                external_id="reading",
                ingested_at=NOW + timedelta(hours=1),
            )
        )
        import_archive(target, archive, dry_run=False)
        claim = target.execute(
            "SELECT value,status FROM source_claims WHERE provider='scale'"
        )[0]
        assert tuple(claim) == (82, "excluded")
        assert all(
            row["status"] == "excluded"
            for row in target.execute("SELECT status FROM observations")
        )
        before = logical(target)
        import_archive(target, archive, dry_run=False)
        assert logical(target) == before
    finally:
        target.close()


def test_environment_ids_remap_without_live_mapping(database, repository, tmp_path):
    populate(database, repository)
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)
    target = HealthDatabase(tmp_path / "target.sqlite")
    target.open()
    try:
        EnvironmentRepository(target).register(
            {
                "mapping_id": "living",
                "source_id": "sensor.living",
                "entity_id": "sensor.living",
                "metric": "temperature",
                "area_id": "living",
                "area_name": "Living",
            }
        )
        result = import_archive(target, archive, dry_run=False)
        assert result["applied"]["environment_streams"]["create"] == 1
        bucket = target.execute("SELECT stream_id FROM environment_buckets")[0]
        assert bucket["stream_id"] == 2
        source = database.execute("SELECT public_id FROM environment_streams")[0][0]
        assert (
            target.execute("SELECT public_id FROM environment_streams WHERE id=2")[0][0]
            == source
        )
        assert (
            target.execute("SELECT last_success_ms FROM environment_maintenance")[0][0]
            is None
        )
        before = logical(target)
        import_archive(target, archive, dry_run=False)
        assert logical(target) == before
    finally:
        target.close()


def test_environment_metadata_collision_rejected_before_claims(
    database, repository, tmp_path
):
    populate(database, repository)
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)
    target = HealthDatabase(tmp_path / "target.sqlite")
    target.open()
    try:
        source = dict(database.execute("SELECT * FROM environment_streams")[0])
        source["area_name"] = "Wrong area"
        target.execute(
            f"INSERT INTO environment_streams ({','.join(source)}) VALUES ({','.join('?' for _ in source)})",
            source.values(),
        )
        before = logical(target)
        with pytest.raises(StoreValidationError, match="conflicting metadata"):
            import_archive(target, archive, dry_run=False)
        assert logical(target) == before
    finally:
        target.close()


def test_older_archive_cannot_resurrect_coarsened_detail(
    database, repository, tmp_path
):
    populate(database, repository)
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)
    target = HealthDatabase(tmp_path / "target.sqlite")
    target.open()
    try:
        import_archive(target, archive, dry_run=False)
        target.execute("UPDATE environment_buckets SET resolution_s=3600")
        before = logical(target)
        result = import_archive(target, archive, dry_run=False)
        assert result["applied"]["environment_buckets"]["unchanged"] == 1
        assert logical(target) == before
    finally:
        target.close()


def test_failure_commits_only_finished_batches_and_retry_is_exact(
    database, repository, tmp_path
):
    for index in range(300):
        repository.upsert_workout(
            Workout(
                person_id="primary",
                provider="history",
                external_id=f"workout-{index}",
                workout_type="walking",
                title="Walk",
                started_at=NOW + timedelta(days=index),
                ended_at=NOW + timedelta(days=index, minutes=30),
                ingested_at=NOW,
            )
        )
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)
    target = HealthDatabase(tmp_path / "target.sqlite")
    target.open()
    try:

        def stop(domain):
            if domain == "workouts":
                raise RuntimeError("Stopped after committed batch")

        with pytest.raises(RuntimeError, match="committed batch"):
            import_archive(target, archive, dry_run=False, after_batch=stop)
        assert target.execute("SELECT count(*) FROM workouts")[0][0] == 256
        result = import_archive(target, archive, dry_run=False)
        assert result["applied"]["workouts"] == {
            "create": 44,
            "merge": 0,
            "unchanged": 256,
        }
        assert logical(target) == logical(database)
    finally:
        target.close()


def test_streaming_priority_matches_full_reconciliation(database, repository, tmp_path):
    for day in range(5):
        for index, provider in enumerate(("a", "b", "c")):
            observation = repository.upsert_observation(
                HealthObservation(
                    person_id="primary",
                    metric=MetricType.WEIGHT,
                    value=80 + index * 0.1,
                    unit="kg",
                    observed_at=NOW + timedelta(days=day, seconds=index),
                    provider=provider,
                    external_id=f"day-{day}",
                    ingested_at=NOW,
                )
            )
        if day % 2:
            repository.set_observation_excluded("primary", observation.id, True)
    copied = tmp_path / "copy.sqlite"
    database.backup(copied)
    target = HealthDatabase(copied)
    target.open()
    try:
        repository.set_priority(MetricType.WEIGHT, ["c", "b", "a"])
        HealthRepository(target).set_priority(
            MetricType.WEIGHT, ["c", "b", "a"], streaming=True
        )
        assert logical(target) == logical(database)
    finally:
        target.close()
