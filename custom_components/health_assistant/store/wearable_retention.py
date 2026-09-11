from __future__ import annotations

from collections.abc import Iterable, Iterator

from .wearable_models import DAY_US, RESOLUTIONS, WearableBucket, WearableError, rollup


def ordered_buckets(buckets: Iterable[WearableBucket]) -> Iterator[WearableBucket]:
    previous_end = None
    weighting = None
    for bucket in buckets:
        bucket.validate()
        if weighting is not None and bucket.weighting != weighting:
            raise WearableError("unsupported_weighting")
        weighting = bucket.weighting
        if previous_end is not None and bucket.start_us < previous_end:
            raise WearableError("overlapping_buckets")
        previous_end = bucket.end_us
        yield bucket


def promote(buckets, source_resolution, target_resolution, cutoff_us):
    pending = []
    pending_start = None
    width = target_resolution * 1000000
    for bucket in buckets:
        parent_start = bucket.start_us // width * width
        eligible = (
            bucket.resolution_s == source_resolution
            and parent_start + width < cutoff_us
        )
        if pending and (not eligible or pending_start != parent_start):
            yield rollup(pending, target_resolution)
            pending.clear()
        if eligible:
            pending_start = parent_start
            pending.append(bucket)
        else:
            yield bucket
    if pending:
        yield rollup(pending, target_resolution)


def retained_buckets(buckets, now_us):
    live = (b for b in ordered_buckets(buckets) if b.end_us >= now_us - 730 * DAY_US)
    minutes = promote(live, 60, 300, now_us - 7 * DAY_US)
    yield from promote(minutes, 300, 3600, now_us - 90 * DAY_US)


def display_buckets(buckets, target_resolution, start_us, end_us):
    if type(target_resolution) is not int or target_resolution not in RESOLUTIONS:
        raise WearableError("invalid_resolution")
    pending = []
    pending_start = None
    width = target_resolution * 1000000
    for bucket in ordered_buckets(buckets):
        parent_start = bucket.start_us // width * width
        if pending and (
            bucket.resolution_s >= target_resolution or pending_start != parent_start
        ):
            result = rollup(pending, target_resolution)
            if result.start_us < end_us and result.end_us > start_us:
                yield result
            pending.clear()
        if bucket.resolution_s < target_resolution:
            pending_start = parent_start
            pending.append(bucket)
        elif bucket.start_us < end_us and bucket.end_us > start_us:
            yield bucket
    if pending:
        result = rollup(pending, target_resolution)
        if result.start_us < end_us and result.end_us > start_us:
            yield result
