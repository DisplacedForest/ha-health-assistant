from datetime import UTC, datetime, timedelta

from custom_components.health_assistant.store import (
    DEFAULT_PERSON_ID,
    RECONCILIATION_RULES,
    HealthObservation,
    MetricClass,
    MetricType,
    metric_class,
)

BASE = datetime(2026, 8, 20, 8, 0, tzinfo=UTC)
BODY_RULE = RECONCILIATION_RULES[MetricClass.BODY_MEASUREMENT]


def observation(
    provider="withings",
    external_id="w-1",
    value=80.0,
    observed_at=BASE,
    metric=MetricType.WEIGHT,
):
    return HealthObservation(
        person_id=DEFAULT_PERSON_ID,
        metric=metric,
        value=value,
        unit="kg" if metric is MetricType.WEIGHT else "count",
        observed_at=observed_at,
        provider=provider,
        external_id=external_id,
        ingested_at=observed_at,
        provenance={"origin": provider},
    )


def data_version(database):
    return database.execute("PRAGMA data_version")[0][0]


def test_every_metric_has_a_reconciliation_class():
    for metric in MetricType:
        assert metric_class(metric) is not None


def test_exact_duplicate_converges_to_one_claim(repository):
    repository.upsert_observation(observation(value=80.0))
    stored = repository.upsert_observation(observation(value=80.5))
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert len(rows) == 1
    assert rows[0].value == 80.5
    assert len(repository.get_claims(stored.id)) == 1


def test_cross_provider_duplicate_in_window_merges(repository):
    repository.upsert_observation(observation(provider="withings"))
    merged = repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-1",
            value=80.2,
            observed_at=BASE + timedelta(seconds=60),
        )
    )
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert len(rows) == 1
    assert rows[0].sources == ("apple_health", "withings")
    assert rows[0].provider == "withings"
    assert rows[0].value == 80.0
    assert not rows[0].possible_duplicate
    claims = repository.get_claims(merged.id)
    assert {claim.provider for claim in claims} == {"withings", "apple_health"}
    assert {claim.value for claim in claims} == {80.0, 80.2}


def test_merge_window_boundary_is_inclusive(repository):
    repository.upsert_observation(observation(provider="withings"))
    repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-1",
            observed_at=BASE + BODY_RULE.merge_window,
        )
    )
    assert len(repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)) == 1


def test_just_outside_merge_window_stays_separate_and_flagged(repository):
    repository.upsert_observation(observation(provider="withings"))
    repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-1",
            observed_at=BASE + BODY_RULE.merge_window + timedelta(seconds=1),
        )
    )
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert len(rows) == 2
    assert all(row.possible_duplicate for row in rows)


def test_outside_suspicious_window_is_not_flagged(repository):
    repository.upsert_observation(observation(provider="withings"))
    repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-1",
            observed_at=BASE + BODY_RULE.suspicious_window + timedelta(seconds=1),
        )
    )
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert len(rows) == 2
    assert not any(row.possible_duplicate for row in rows)


def test_same_provider_never_merges_or_flags(repository):
    repository.upsert_observation(observation(external_id="w-1"))
    repository.upsert_observation(
        observation(external_id="w-2", observed_at=BASE + timedelta(seconds=30))
    )
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert len(rows) == 2
    assert not any(row.possible_duplicate for row in rows)


def test_activity_metrics_never_cross_provider_merge(repository):
    repository.upsert_observation(
        observation(
            provider="ha_entity",
            external_id="sensor.steps",
            value=1000,
            metric=MetricType.STEPS,
        )
    )
    repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-steps",
            value=1000,
            metric=MetricType.STEPS,
        )
    )
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.STEPS)
    assert len(rows) == 2
    assert not any(row.possible_duplicate for row in rows)


def test_store_answers_which_source_supplies_the_value(repository):
    repository.upsert_observation(observation(provider="withings", value=80.0))
    stored = repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-1",
            value=80.2,
            observed_at=BASE + timedelta(seconds=30),
        )
    )
    assert stored.provider == "withings"
    assert stored.external_id == "w-1"
    assert stored.sources == ("apple_health", "withings")


def test_priority_order_supplies_the_canonical_value(repository):
    repository.upsert_observation(observation(provider="withings", value=80.0))
    repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-1",
            value=80.2,
            observed_at=BASE + timedelta(seconds=30),
        )
    )
    repository.set_priority(MetricType.WEIGHT, ["apple_health", "withings"])
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert len(rows) == 1
    assert rows[0].value == 80.2
    assert rows[0].provider == "apple_health"
    assert rows[0].sources == ("apple_health", "withings")
    repository.set_priority(MetricType.WEIGHT, ["withings", "apple_health"])
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert rows[0].provider == "withings"
    assert rows[0].value == 80.0
    assert repository.get_priority(MetricType.WEIGHT) == ["withings", "apple_health"]
    repository.set_priority(MetricType.WEIGHT, [])
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert rows[0].provider == "withings"
    assert rows[0].value == 80.0


def test_correction_re_derives_without_touching_other_claims(repository):
    repository.upsert_observation(observation(provider="withings", value=80.0))
    repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-1",
            value=80.2,
            observed_at=BASE + timedelta(seconds=30),
        )
    )
    corrected = repository.upsert_observation(
        observation(provider="withings", value=79.5)
    )
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert len(rows) == 1
    assert rows[0].value == 79.5
    claims = repository.get_claims(corrected.id)
    apple = next(claim for claim in claims if claim.provider == "apple_health")
    assert apple.value == 80.2


def test_rereconciliation_over_unchanged_inputs_is_a_noop(repository, database):
    repository.upsert_observation(observation(provider="withings"))
    repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-1",
            observed_at=BASE + timedelta(seconds=30),
        )
    )
    before = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    version = data_version(database)
    repository.reconcile_metric(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    after = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert after == before
    assert data_version(database) == version


def test_replay_rebuilds_the_same_canonical_series(repository):
    for minute in (0, 1, 10, 45):
        repository.upsert_observation(
            observation(
                provider="withings" if minute != 1 else "apple_health",
                external_id=f"x-{minute}",
                value=80.0 + minute,
                observed_at=BASE + timedelta(minutes=minute),
            )
        )
    before = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    repository.reconcile_metric(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    after = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert after == before


def test_flag_clears_when_ambiguity_resolves(repository):
    repository.upsert_observation(observation(provider="withings"))
    ambiguous = observation(
        provider="apple_health",
        external_id="a-1",
        observed_at=BASE + timedelta(minutes=10),
    )
    repository.upsert_observation(ambiguous)
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert all(row.possible_duplicate for row in rows)
    repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-0",
            observed_at=BASE + timedelta(seconds=30),
        )
    )
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    merged = next(row for row in rows if len(row.sources) == 2)
    assert merged.sources == ("apple_health", "withings")
    assert not any(row.possible_duplicate for row in rows)


def test_merged_group_not_flagged_by_unrelated_same_provider_neighbor(repository):
    repository.upsert_observation(
        observation(
            provider="withings",
            external_id="w-early",
            value=79.0,
            observed_at=BASE - timedelta(minutes=10),
        )
    )
    repository.upsert_observation(observation(provider="withings", value=80.0))
    repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-1",
            value=80.2,
            observed_at=BASE + timedelta(seconds=60),
        )
    )
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert len(rows) == 2
    assert not any(row.possible_duplicate for row in rows)


def test_two_fully_merged_groups_are_not_flagged(repository):
    for minutes, suffix in ((0, "one"), (10, "two")):
        repository.upsert_observation(
            observation(
                provider="withings",
                external_id=f"w-{suffix}",
                observed_at=BASE + timedelta(minutes=minutes),
            )
        )
        repository.upsert_observation(
            observation(
                provider="apple_health",
                external_id=f"a-{suffix}",
                observed_at=BASE + timedelta(minutes=minutes, seconds=30),
            )
        )
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert len(rows) == 2
    assert all(row.sources == ("apple_health", "withings") for row in rows)
    assert not any(row.possible_duplicate for row in rows)


def test_merged_group_still_flags_against_third_provider(repository):
    repository.upsert_observation(observation(provider="withings"))
    repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-1",
            observed_at=BASE + timedelta(seconds=30),
        )
    )
    repository.upsert_observation(
        observation(
            provider="fitbit",
            external_id="f-1",
            observed_at=BASE + timedelta(minutes=10),
        )
    )
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert len(rows) == 2
    assert all(row.possible_duplicate for row in rows)


def test_single_source_series_matches_pre_reconciliation_behavior(repository):
    values = [(0, 80.0), (60 * 24, 79.8), (60 * 48, 79.5)]
    for minutes, value in values:
        repository.upsert_observation(
            observation(
                external_id=f"w-{minutes}",
                value=value,
                observed_at=BASE + timedelta(minutes=minutes),
            )
        )
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert [(row.value, row.provider) for row in rows] == [
        (80.0, "withings"),
        (79.8, "withings"),
        (79.5, "withings"),
    ]
    assert not any(row.possible_duplicate for row in rows)
    latest = repository.latest_observation(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert latest.value == 79.5
    assert latest.sources == ("withings",)


def test_value_divergent_pair_coexists_and_resolves_by_priority(repository):
    repository.upsert_observation(observation(provider="withings", value=80.0))
    repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-1",
            value=90.0,
            observed_at=BASE + timedelta(seconds=30),
        )
    )
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert len(rows) == 2
    assert all(row.possible_duplicate for row in rows)
    repository.set_priority(MetricType.WEIGHT, ["withings", "apple_health"])
    latest = repository.latest_observation(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert latest.provider == "withings"
    assert latest.value == 80.0
    repository.set_priority(MetricType.WEIGHT, ["apple_health", "withings"])
    latest = repository.latest_observation(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert latest.provider == "apple_health"
    assert latest.value == 90.0


def test_value_tolerance_boundaries(repository):
    repository.upsert_observation(observation(provider="withings", value=80.0))
    repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-abs",
            value=80.5,
            observed_at=BASE + timedelta(seconds=10),
        )
    )
    assert len(repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)) == 1

    repository.upsert_observation(
        observation(
            provider="withings",
            external_id="w-2",
            value=100.0,
            observed_at=BASE + timedelta(hours=2),
        )
    )
    repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-rel",
            value=101.0,
            observed_at=BASE + timedelta(hours=2, seconds=10),
        )
    )
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert len(rows) == 2
    assert rows[1].sources == ("apple_health", "withings")

    repository.upsert_observation(
        observation(
            provider="withings",
            external_id="w-3",
            value=100.0,
            observed_at=BASE + timedelta(hours=4),
        )
    )
    repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-far",
            value=101.1,
            observed_at=BASE + timedelta(hours=4, seconds=10),
        )
    )
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert len(rows) == 4


def test_reordering_priority_deletes_no_claims(repository, database):
    repository.upsert_observation(observation(provider="withings", value=80.0))
    repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-1",
            value=80.2,
            observed_at=BASE + timedelta(seconds=30),
        )
    )
    before = database.execute("SELECT COUNT(*) AS n FROM source_claims")[0]["n"]
    repository.set_priority(MetricType.WEIGHT, ["apple_health"])
    repository.set_priority(MetricType.WEIGHT, ["withings"])
    after = database.execute("SELECT COUNT(*) AS n FROM source_claims")[0]["n"]
    assert before == after == 2


def test_contested_current_value_prefers_priority_inside_window_only(repository):
    repository.set_priority(MetricType.WEIGHT, ["withings", "apple_health"])
    repository.upsert_observation(
        observation(provider="withings", value=80.0, observed_at=BASE)
    )
    repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-old",
            value=90.0,
            observed_at=BASE + timedelta(seconds=60),
        )
    )
    latest = repository.latest_observation(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert latest.provider == "withings"

    repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-new",
            value=91.0,
            observed_at=BASE + timedelta(hours=3),
        )
    )
    latest = repository.latest_observation(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert latest.provider == "apple_health"
    assert latest.value == 91.0


def test_unranked_defaults_keep_first_seen_supplier(repository):
    repository.upsert_observation(observation(provider="withings", value=80.0))
    repository.upsert_observation(
        observation(
            provider="apple_health",
            external_id="a-1",
            value=80.2,
            observed_at=BASE + timedelta(seconds=30),
        )
    )
    rows = repository.get_observations(DEFAULT_PERSON_ID, MetricType.WEIGHT)
    assert len(rows) == 1
    assert rows[0].provider == "withings"
