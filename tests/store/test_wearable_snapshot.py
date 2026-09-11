import copy
import json
from pathlib import Path

import pytest

from custom_components.health_assistant.store.wearable_models import (
    WearableError,
    normalize_batch,
    time_us,
)
from custom_components.health_assistant.store.wearable_snapshot import (
    SnapshotValidator,
    normalize_archive_bucket,
    snapshot_hash,
)

VECTORS = json.loads(
    (
        Path(__file__).parents[1] / "fixtures" / "wearable-snapshot-vectors.json"
    ).read_text()
)
NOW = time_us("2026-09-11T00:00:00Z")


@pytest.mark.parametrize("vector", VECTORS["vectors"], ids=lambda v: v["input"]["name"])
def test_frozen_cross_language_snapshot_vectors(vector):
    value = vector["input"]
    descriptor = {**value["descriptor"], "snapshot_hash": vector["verified"]["sha256"]}
    buckets = [normalize_archive_bucket(row, descriptor) for row in value["buckets"]]
    assert snapshot_hash(descriptor, buckets) == vector["verified"]["sha256"]
    validator = SnapshotValidator(descriptor, NOW)
    for row in value["buckets"]:
        validator.add(row)
    if value["valid_snapshot_shape"]:
        validator.finish()
    else:
        with pytest.raises(WearableError, match=value["expected_validation_error"]):
            validator.finish()


def sample():
    value = copy.deepcopy(VECTORS["vectors"][1])
    descriptor = {
        **value["input"]["descriptor"],
        "snapshot_hash": value["verified"]["sha256"],
    }
    return descriptor, value["input"]["buckets"]


def test_frozen_native_tip_uses_current_typed_validation():
    value = dict(VECTORS["native_tip_projection"])
    del value["hash_scope"]
    value["content_hash"] = VECTORS["native_tip_hash"]
    parsed = normalize_batch(value, "sample")
    assert parsed.sequence == 1
    assert len(parsed.operations) == 2


@pytest.mark.parametrize(
    "patch",
    [
        {"retired": 1},
        {"hash_version": True},
        {"sequence": "0"},
        {"snapshot_bucket_count": True},
        {"snapshot_bucket_count": 50001},
        {"weighting": "mixed"},
        {"unit": "count/s"},
        {"metric": "hrv"},
        {"source_id": "unscoped"},
        {"algorithm_id": "x" * 129},
        {"snapshot_at": "2026-09-06T23:59:00Z"},
        {"snapshot_at": "2027-09-06T23:59:00.000000Z"},
        {"owner_id": "not-portable"},
    ],
)
def test_invalid_descriptor_rejected(patch):
    descriptor, _ = sample()
    with pytest.raises(WearableError):
        SnapshotValidator({**descriptor, **patch}, NOW)


@pytest.mark.parametrize(
    "patch",
    [
        {"sample_count": "0"},
        {"sample_count": 2},
        {"covered_us": "1"},
        {"sample_sum": 0},
        {"stream_id": "d265d8fa-31bb-4a28-92be-35fa20a8a26d"},
        {"start": "2026-09-12T00:00:00.000000Z"},
        {"minimum": 100},
        {"extra": "ignored"},
    ],
)
def test_invalid_archive_bucket_rejected(patch):
    descriptor, rows = sample()
    validator = SnapshotValidator(descriptor, NOW)
    with pytest.raises(WearableError):
        validator.add({**rows[0], **patch})


def test_missing_rows_and_corrupt_hash_are_distinct_failures():
    descriptor, rows = sample()
    validator = SnapshotValidator(descriptor, NOW)
    validator.add(rows[0])
    with pytest.raises(WearableError, match="snapshot_count_mismatch"):
        validator.finish()
    descriptor["snapshot_hash"] = "0" * 64
    validator = SnapshotValidator(descriptor, NOW)
    for row in rows:
        validator.add(row)
    with pytest.raises(WearableError, match="snapshot_hash_mismatch"):
        validator.finish()


def test_duplicate_rows_rejected_without_overwriting():
    descriptor, rows = sample()
    validator = SnapshotValidator(descriptor, NOW)
    validator.add(rows[0])
    with pytest.raises(WearableError, match="overlapping_buckets"):
        validator.add(rows[0])
