from __future__ import annotations

import hashlib

from .wearable_models import (
    WEIGHTINGS,
    WearableBucket,
    WearableError,
    canonical,
    counter,
    exact_fields,
    finite,
    hash_value,
    time_us,
    timestamp,
    uuid_value,
)

STREAM_FIELDS = frozenset(
    (
        "stream_id",
        "source_id",
        "metric",
        "unit",
        "weighting",
        "algorithm_id",
        "algorithm_version",
        "retired",
        "sequence",
        "hash_version",
        "content_hash",
        "snapshot_at",
        "snapshot_bucket_count",
        "snapshot_hash",
    )
)
BUCKET_FIELDS = frozenset(
    (
        "stream_id",
        "start",
        "resolution_s",
        "sample_count",
        "sample_sum",
        "minimum",
        "maximum",
        "covered_us",
        "weighted_sum",
    )
)
IDENTITY_FIELDS = (
    "stream_id",
    "source_id",
    "metric",
    "unit",
    "weighting",
    "algorithm_id",
    "algorithm_version",
)


def algorithm(value):
    if value is None:
        return value
    try:
        if not isinstance(value, str) or not 0 < len(value.encode("utf-8")) <= 128:
            raise ValueError
    except (ValueError, UnicodeError) as err:
        raise WearableError("invalid_algorithm") from err
    return value


def normalize_descriptor(value):
    exact_fields(value, STREAM_FIELDS)
    result = dict(value)
    uuid_value(value["stream_id"])
    uuid_value(value["source_id"])
    if value["metric"] != "heart_rate" or value["unit"] != "bpm":
        raise WearableError("unsupported_metric")
    if value["weighting"] not in WEIGHTINGS:
        raise WearableError("unsupported_weighting")
    algorithm(value["algorithm_id"])
    algorithm(value["algorithm_version"])
    if type(value["retired"]) is not bool:
        raise WearableError()
    if type(value["hash_version"]) is not int or value["hash_version"] != 1:
        raise WearableError("unsupported_hash_version")
    sequence = counter(value["sequence"])
    count = value["snapshot_bucket_count"]
    if type(count) is not int or not 0 <= count <= 50000:
        raise WearableError("snapshot_count_mismatch")
    if sequence == 0:
        if value["content_hash"] is not None or count != 0:
            raise WearableError("invalid_initial_tip")
    else:
        hash_value(value["content_hash"])
    hash_value(value["snapshot_hash"])
    if not isinstance(value["snapshot_at"], str):
        raise WearableError()
    result["snapshot_at"] = timestamp(time_us(value["snapshot_at"]))
    if result["snapshot_at"] != value["snapshot_at"]:
        raise WearableError("noncanonical_timestamp")
    canonical(result, 2048)
    return result


def normalize_archive_bucket(value, descriptor):
    exact_fields(value, BUCKET_FIELDS)
    if value["stream_id"] != descriptor["stream_id"]:
        raise WearableError("stream_identity_conflict")
    if not isinstance(value["start"], str):
        raise WearableError()
    start_us = time_us(value["start"])
    if timestamp(start_us) != value["start"]:
        raise WearableError("noncanonical_timestamp")
    sample = descriptor["weighting"] == "sample"
    inactive = (
        ("covered_us", "weighted_sum") if sample else ("sample_count", "sample_sum")
    )
    if any(value[key] is not None for key in inactive):
        raise WearableError("invalid_weighting_fields")
    return WearableBucket(
        start_us,
        value["resolution_s"],
        descriptor["weighting"],
        counter(value["sample_count" if sample else "covered_us"], positive=True),
        finite(value["sample_sum" if sample else "weighted_sum"]),
        finite(value["minimum"]),
        finite(value["maximum"]),
    ).validate()


class SnapshotValidator:
    def __init__(self, descriptor, now_us):
        self.descriptor = normalize_descriptor(descriptor)
        self.snapshot_us = time_us(self.descriptor["snapshot_at"])
        if self.snapshot_us > now_us:
            raise WearableError("future_snapshot")
        self.count = 0
        self.previous_end = None
        self.digest = snapshot_digest(self.descriptor)

    def add(self, value):
        bucket = normalize_archive_bucket(value, self.descriptor)
        if self.previous_end is not None and bucket.start_us < self.previous_end:
            raise WearableError("overlapping_buckets")
        if bucket.end_us > self.snapshot_us:
            raise WearableError("future_bucket")
        self.count += 1
        if self.count > self.descriptor["snapshot_bucket_count"]:
            raise WearableError("snapshot_count_mismatch")
        self.previous_end = bucket.end_us
        self.digest.update(
            canonical(bucket.archive(self.descriptor["stream_id"])) + b"\n"
        )
        return bucket

    def finish(self):
        if self.count != self.descriptor["snapshot_bucket_count"]:
            raise WearableError("snapshot_count_mismatch")
        if self.digest.hexdigest() != self.descriptor["snapshot_hash"]:
            raise WearableError("snapshot_hash_mismatch")


def snapshot_digest(descriptor):
    digest = hashlib.sha256(b"health_assistant.wearable_snapshot.v1\n")
    value = {key: val for key, val in descriptor.items() if key != "snapshot_hash"}
    digest.update(canonical(value, 2048) + b"\n")
    return digest


def snapshot_hash(descriptor, buckets):
    digest = snapshot_digest(descriptor)
    for bucket in buckets:
        digest.update(canonical(bucket.archive(descriptor["stream_id"])) + b"\n")
    return digest.hexdigest()
