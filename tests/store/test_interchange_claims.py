from datetime import timedelta

import pytest
from test_interchange import NOW, logical

from custom_components.health_assistant.store import (
    HealthDatabase,
    HealthObservation,
    HealthRepository,
    MetricType,
)
from custom_components.health_assistant.store.interchange import (
    export_archive,
    import_archive,
)


def claim(provider, external_id, seconds, value=80):
    return HealthObservation(
        person_id="primary",
        metric=MetricType.WEIGHT,
        value=value,
        unit="kg",
        observed_at=NOW + timedelta(seconds=seconds),
        provider=provider,
        external_id=external_id,
        ingested_at=NOW,
    )


def temporary_groups(repository, padding):
    for index in range(padding):
        repository.upsert_observation(
            claim("history", f"padding-{index}", -86400 * (index + 1))
        )
    first = repository.upsert_observation(claim("a", "anchor", 527, 81.7))
    repository.upsert_observation(claim("c", "active", 585, 81.6))
    repository.upsert_observation(claim("c", "earlier", 573, 80.9))
    repository.set_observation_excluded("primary", first.id, True)
    repository.set_priority(MetricType.WEIGHT, ["c", "a"])


@pytest.mark.parametrize("padding", [0, 254])
@pytest.mark.parametrize("overlap", [False, True])
def test_complete_claim_set_preserves_active_group_after_split(
    database, repository, tmp_path, padding, overlap
):
    temporary_groups(repository, padding)
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)
    target = HealthDatabase(tmp_path / "target.sqlite")
    target.open()
    try:
        local = HealthRepository(target)
        if overlap:
            local.upsert_observation(claim("c", "active", 585, 81.6))
        import_archive(target, archive, dry_run=False)
        assert logical(target) == logical(database)
        assert (
            target.execute(
                "SELECT status FROM source_claims WHERE external_id='active'"
            )[0][0]
            == "active"
        )
        assert (
            target.execute(
                "SELECT status FROM observations WHERE external_id='active'"
            )[0][0]
            == "active"
        )
        before = logical(target)
        replay = import_archive(target, archive, dry_run=False)
        assert logical(target) == before
        assert (
            replay["applied"]["source_claims"]["create"]
            == replay["applied"]["source_claims"]["merge"]
            == 0
        )
    finally:
        target.close()


def test_complete_claim_set_keeps_destination_exclusion(database, repository, tmp_path):
    temporary_groups(repository, 0)
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)
    target = HealthDatabase(tmp_path / "target.sqlite")
    target.open()
    try:
        local = HealthRepository(target)
        existing = local.upsert_observation(claim("c", "active", 585, 81.6))
        local.set_observation_excluded("primary", existing.id, True)
        import_archive(target, archive, dry_run=False)
        assert all(
            row["status"] == "excluded"
            for row in target.execute("SELECT status FROM source_claims")
        )
        assert all(
            row["status"] == "excluded"
            for row in target.execute("SELECT status FROM observations")
        )
    finally:
        target.close()


@pytest.mark.parametrize("failure", ["claim", "reconciliation"])
def test_failed_health_phase_rolls_back_priorities_and_all_claim_pages(
    database, repository, tmp_path, monkeypatch, failure
):
    temporary_groups(repository, 254)
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)
    target = HealthDatabase(tmp_path / "target.sqlite")
    target.open()
    try:
        local = HealthRepository(target)
        existing = local.upsert_observation(claim("local", "preserved", -86400 * 1000))
        local.set_observation_excluded("primary", existing.id, True)
        local.set_priority(MetricType.WEIGHT, ["local"])
        before = logical(target)
        original = HealthRepository._upsert_claim

        def fail(self, observation):
            result = original(self, observation)
            if (
                failure == "claim"
                and self._db is target
                and observation.external_id == "earlier"
            ):
                assert target.execute("SELECT count(*) FROM source_claims")[0][0] == 258
                raise RuntimeError("Interrupted health phase")
            return result

        original_reconcile = HealthRepository.reconcile_metric

        def fail_reconcile(self, person, metric, **kwargs):
            original_reconcile(self, person, metric, **kwargs)
            if failure == "reconciliation" and self._db is target:
                assert self.get_priority(MetricType.WEIGHT) == ["c", "a"]
                assert target.execute("SELECT count(*) FROM source_claims")[0][0] == 258
                raise RuntimeError("Interrupted health phase")

        with monkeypatch.context() as patch:
            patch.setattr(HealthRepository, "_upsert_claim", fail)
            patch.setattr(HealthRepository, "reconcile_metric", fail_reconcile)
            with pytest.raises(RuntimeError, match="Interrupted health phase"):
                import_archive(target, archive, dry_run=False)
        assert logical(target) == before
        result = import_archive(target, archive, dry_run=False)
        assert result["applied"]["source_claims"]["create"] == 257
        assert (
            target.execute(
                "SELECT status FROM source_claims WHERE external_id='active'"
            )[0][0]
            == "active"
        )
        assert (
            target.execute(
                "SELECT status FROM source_claims WHERE external_id='preserved'"
            )[0][0]
            == "excluded"
        )
        before = logical(target)
        import_archive(target, archive, dry_run=False)
        assert logical(target) == before
    finally:
        target.close()


def test_priority_only_archive_reconciles_existing_destination(
    database, repository, tmp_path
):
    repository.set_priority(MetricType.WEIGHT, ["watch", "scale"])
    archive = tmp_path / "history.tar.gz"
    export_archive(database, archive)
    target = HealthDatabase(tmp_path / "target.sqlite")
    target.open()
    try:
        local = HealthRepository(target)
        local.upsert_observation(claim("scale", "one", 0, 80))
        local.upsert_observation(claim("watch", "two", 1, 80.1))
        local.set_priority(MetricType.WEIGHT, ["scale", "watch"])
        assert (
            local.latest_observation("primary", MetricType.WEIGHT).provider == "scale"
        )
        result = import_archive(target, archive, dry_run=False)
        assert result["records"]["source_claims"] == 0
        assert local.get_priority(MetricType.WEIGHT) == ["watch", "scale"]
        assert (
            local.latest_observation("primary", MetricType.WEIGHT).provider == "watch"
        )
        assert target.execute("SELECT count(*) FROM source_claims")[0][0] == 2
    finally:
        target.close()
