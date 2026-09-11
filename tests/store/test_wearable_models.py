import hashlib
import math
from dataclasses import replace

import pytest

from custom_components.health_assistant.store.wearable_models import (
    MAX_COUNTER,
    WearableBucket,
    WearableError,
    canonical,
    counter,
    normalize_batch,
    normalize_operation,
    rollup,
    time_us,
    timestamp,
)
from custom_components.health_assistant.store.wearable_retention import (
    DAY_US,
    display_buckets,
    retained_buckets,
)

STREAM = "d265d8fa-31bb-4a28-92be-35fa20a8a26d"
START = time_us("2026-01-01T10:00:00Z")


def bucket(start=START, resolution=60, weighting="sample", weight=1, mean=70):
    return WearableBucket(
        start, resolution, weighting, weight, weight * mean, mean, mean
    )


def batch(operations, expected="0", sequence="1"):
    projection = {
        "hash_scope": "health_assistant.wearable_batch",
        "hash_version": 1,
        "stream_id": STREAM,
        "expected_sequence": expected,
        "sequence": sequence,
        "operations": operations,
    }
    digest = hashlib.sha256(canonical(projection)).hexdigest()
    projection.pop("hash_scope")
    return {**projection, "content_hash": digest}


@pytest.mark.parametrize("weighting", ("sample", "time"))
def test_numeric_envelope_stays_valid_through_both_rollups(weighting):
    minutes = [
        bucket(START + i * 60000000, weighting=weighting, weight=60000000, mean=1e9)
        for i in range(60)
    ]
    fives = [rollup(minutes[i : i + 5], 300) for i in range(0, 60, 5)]
    hour = rollup(fives, 3600)
    assert hour.weight == 3600000000
    assert hour.total == 3.6e18
    assert hour.mean == 1e9
    assert hour.minimum == hour.maximum == 1e9
    assert hour.validate() == hour


@pytest.mark.parametrize("weighting", ("sample", "time"))
def test_rollup_preserves_weights_and_gaps(weighting):
    result = rollup(
        [
            bucket(weighting=weighting, weight=1, mean=40),
            bucket(START + 180000000, weighting=weighting, weight=3, mean=80),
        ],
        300,
    )
    assert result.weight == 4
    assert result.total == 280
    assert result.mean == 70
    assert result.minimum == 40
    assert result.maximum == 80
    archive = result.archive(STREAM)
    assert archive["covered_us"] == (None if weighting == "sample" else "4")
    assert archive["sample_count"] == ("4" if weighting == "sample" else None)


@pytest.mark.parametrize(
    "changes",
    [
        {"weight": 0},
        {"weight": -1},
        {"weight": 60000001},
        {"weight": True},
        {"total": 0},
        {"total": -1},
        {"total": math.inf},
        {"total": math.nan},
        {"minimum": 0},
        {"minimum": 1e-10},
        {"maximum": 1e9 + 1},
        {"minimum": 80, "maximum": 70},
        {"total": 1e9 + 2},
        {"resolution_s": True},
        {"resolution_s": 120},
        {"start_us": START + 1},
        {"weighting": "unknown"},
    ],
)
def test_invalid_numeric_and_interval_inputs_fail(changes):
    with pytest.raises(WearableError):
        replace(bucket(), **changes).validate()


@pytest.mark.parametrize("resolution", (60, 300, 3600))
def test_rounding_tolerance_is_bounded_without_clamping(resolution):
    tolerance = 1e-12 * (resolution / 60) * 70
    admitted = replace(bucket(resolution=resolution), total=70 + tolerance * 0.9)
    assert admitted.validate().total > 70
    with pytest.raises(WearableError, match="inconsistent_mean"):
        replace(admitted, total=70 + tolerance * 1.1).validate()


@pytest.mark.parametrize(
    "value", [True, 1, -1, "-1", "+1", "01", "1.0", "1e1", "", str(MAX_COUNTER + 1)]
)
def test_counter_is_exact_decimal(value):
    with pytest.raises(WearableError):
        counter(value)


def test_counter_preserves_all_signed64_bits():
    assert counter(str(MAX_COUNTER)) == MAX_COUNTER
    assert counter("0") == 0
    with pytest.raises(WearableError):
        counter("0", positive=True)


def test_normalization_orders_operations_and_normalizes_offsets_before_hashing():
    one = bucket().wire()
    two = bucket(START + 60000000).wire()
    value = batch([one, two])
    value["operations"] = [two, {**one, "start": "2026-01-01T05:00:00-05:00"}]
    parsed = normalize_batch(value, "sample")
    assert [op.start_us for op in parsed.operations] == [START, START + 60000000]
    assert parsed.content_hash == value["content_hash"]


def test_hash_detects_mutation_and_does_not_include_authorization():
    value = batch([bucket().wire()])
    value["operations"][0]["sum"] = 70.000000000001
    with pytest.raises(WearableError, match="content_hash_mismatch"):
        normalize_batch(value, "sample")
    value = batch([bucket().wire()])
    value["write_lease"] = "outside-the-hash"
    with pytest.raises(WearableError):
        normalize_batch(value, "sample")


@pytest.mark.parametrize(
    "operations",
    [
        [bucket().wire(), bucket().wire()],
        [
            {"op": "delete", "start": timestamp(START), "resolution": 300},
            bucket().wire(),
        ],
    ],
)
def test_overlapping_operations_fail_before_application(operations):
    with pytest.raises(WearableError, match="overlapping_operations"):
        normalize_batch(batch(operations), "sample")


@pytest.mark.parametrize(
    "patch",
    [
        {"count": "0"},
        {"count": 1},
        {"count": True},
        {"count": "60000001"},
        {"sum": "70"},
        {"sum": True},
        {"min": None},
        {"extra": "data"},
    ],
)
def test_replacement_shape_is_strict(patch):
    with pytest.raises(WearableError):
        normalize_operation({**bucket().wire(), **patch}, "sample")


def test_delete_does_not_accept_replacement_fields():
    with pytest.raises(WearableError):
        normalize_operation({**bucket().wire(), "op": "delete"}, "sample")


def test_large_and_empty_operation_lists_fail():
    for operations in ([], [bucket().wire()] * 1001):
        with pytest.raises(WearableError, match="operation_limit"):
            normalize_batch(batch(operations), "sample")


def test_compaction_waits_for_complete_parent_interval_strict_boundary():
    minutes = [bucket(START + i * 60000000) for i in range(5)]
    for cutoff in (START + 120000000, START + 300000000):
        assert list(retained_buckets(minutes, cutoff + 7 * DAY_US)) == minutes
    result = list(retained_buckets(minutes, START + 300000001 + 7 * DAY_US))
    assert result == [bucket(resolution=300, weight=5)]


def test_sparse_parent_uses_interval_end_not_last_present_child():
    only = [bucket()]
    assert list(retained_buckets(only, START + 120000000 + 7 * DAY_US)) == only
    assert list(retained_buckets(only, START + 300000001 + 7 * DAY_US)) == [
        bucket(resolution=300)
    ]


def test_hour_boundary_and_expiry_are_strict():
    fives = [bucket(START + i * 300000000, resolution=300) for i in range(12)]
    clock = START + 3600000000 + 90 * DAY_US
    assert list(retained_buckets(fives, clock)) == fives
    assert list(retained_buckets(fives, clock + 1)) == [
        bucket(resolution=3600, weight=12)
    ]
    hour = bucket(resolution=3600)
    assert list(retained_buckets([hour], hour.end_us + 730 * DAY_US)) == [hour]
    assert list(retained_buckets([hour], hour.end_us + 730 * DAY_US + 1)) == []


def test_display_edge_returns_full_aggregate_including_children_outside_range():
    minutes = [bucket(START + i * 60000000, mean=50 + i * 10) for i in range(5)]
    result = list(display_buckets(minutes, 300, START + 270000000, START + 300000000))
    assert len(result) == 1
    assert result[0].start_us == START
    assert result[0].end_us == START + 300000000
    assert result[0].weight == 5
    assert result[0].total == 350


def test_display_never_upsamples_coarse_history():
    hour = bucket(resolution=3600)
    assert list(display_buckets([hour], 60, START + 1, START + 2)) == [hour]


def test_rollup_rejects_overlaps_and_cross_parent_inputs():
    for rows in ([bucket(), bucket()], [bucket(), bucket(START + 300000000)]):
        with pytest.raises(WearableError, match="invalid_rollup"):
            rollup(rows, 300)


def test_retention_checks_overlap_even_for_expired_history():
    with pytest.raises(WearableError, match="overlapping_buckets"):
        list(retained_buckets([bucket(), bucket()], START + 900 * DAY_US))


@pytest.mark.parametrize("weighting", ("sample", "time"))
def test_compensated_sum_preserves_low_order_contributions(weighting):
    large = bucket(weighting=weighting, weight=1000000, mean=1e9)
    small = [
        bucket(START + i * 60000000, weighting=weighting, mean=0.01)
        for i in range(1, 60)
    ]
    result = rollup([large, *small], 3600)
    assert result.total == math.fsum([large.total, *(b.total for b in small)])
    naive = large.total
    for item in small:
        naive += item.total
    assert result.total != naive


def test_mixed_tier_query_has_exact_intervals_weights_and_sums():
    rows = [
        bucket(START - 3600000000, resolution=3600, weight=10, mean=40),
        bucket(START, resolution=300, weight=2, mean=60),
        bucket(START + 300000000, weight=1, mean=80),
        bucket(START + 360000000, weight=3, mean=100),
    ]
    result = list(display_buckets(rows, 300, START - 1, START + 360000001))
    assert [(b.start_us, b.resolution_s, b.weight, b.total) for b in result] == [
        (START - 3600000000, 3600, 10, 400),
        (START, 300, 2, 120),
        (START + 300000000, 300, 4, 380),
    ]


def test_streamed_rollup_keeps_only_one_parent_group_in_memory():
    consumed = 0

    def source():
        nonlocal consumed
        for i in range(100000):
            consumed += 1
            yield bucket(START + i * 60000000)

    result = display_buckets(source(), 3600, START, START + 100000 * 60000000)
    first = next(result)
    assert first.weight == 60
    assert consumed == 61
    result.close()
