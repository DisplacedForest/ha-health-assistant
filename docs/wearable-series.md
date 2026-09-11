# Wearable heart-rate history

Wearable history stores compact heart-rate intervals from an explicitly enrolled bridge source. It keeps each source, account, weighting method and algorithm separate. It doesn't store raw samples or infer HRV from average heart rate.

The native receiver contract is available for adapter development. A matching JSON fixture doesn't establish compatibility with a phone application. Apple Health and Health Connect exporters still need verification of their stable identities, corrections, deletions and complete interval replacements before they're listed as supported clients.

## What an interval contains

An interval covers an aligned minute, five minutes or hour. Each replacement contains the complete source contribution for that interval.

- Sample weighting preserves the sample count, sum, minimum and maximum. Duration coverage is unknown and stays null.
- Time weighting preserves covered microseconds, the duration-weighted sum, minimum and maximum. Missing time doesn't count as zero heart rate.

Combining intervals adds their weights and sums. It doesn't average their averages or invent samples for gaps. A correction replaces an entire interval; a deletion removes that interval's contribution. Sources must rebuild a complete retained interval after correcting or deleting any of its original samples.

Input extrema must fall between 0.000000001 and 1,000,000,000 bpm. Counts and covered microseconds must be positive integers, no greater than the interval's seconds multiplied by 1,000,000. These are software limits that keep aggregation safe, not physiological reference ranges. Invalid values are rejected rather than clipped. Sums must be positive and finite, and agree with their extrema within the documented rounding tolerance.

The mean tolerance is `1e-12 * (resolution_seconds / 60) * max(1, abs(minimum), abs(maximum), abs(mean))`. The aggregate cannot exceed `weight * 1,000,000,001`. Both native input and archive input use these checks, as do computed rollups.

## Retention

History becomes less detailed as it ages:

| Age at interval end | Retained detail |
| --- | --- |
| Through 7 days | One minute or coarser |
| Over 7 through 90 days | Five minutes or coarser |
| Over 90 through 730 days | One hour |
| Over 730 days | Removed |

Coarse source data stays coarse. Compaction never reconstructs finer samples. At an exact age boundary, the current finer tier remains eligible.

Automatic compaction waits until the complete aligned parent interval has crossed its cutoff. This leaves at most one five-minute boundary group and one hourly boundary group temporarily at finer resolution. It prevents a partly eligible group from overlapping its replacement. Missing children remain missing contributions when the group is combined.

If a stored interval cannot be combined safely, maintenance leaves that stream's original rows intact and marks it degraded. Other streams can still be maintained. This state needs investigation; it isn't an alternative retention setting.

## Ordered batches

The bridge sends one stream per request, with at most 1,000 operations and a 1 MiB complete request body. Every new batch names the currently acknowledged sequence and the next sequence. Sequence values and counts are decimal strings, preserving all signed 64-bit integer bits across clients.

The receiver verifies the complete normalized batch hash before writing. Data and the new sequence commit together. A failed operation leaves the whole batch uncommitted. Operations within a batch cannot overlap, including a coarse deletion paired with a finer replacement.

Only the latest accepted batch can be retried. Its verified sequence and hash return an acknowledgment without applying its records again, even after retention has combined or removed them. Older, skipped and conflicting sequences are rejected. Sequence values never reset when records expire or are deleted.

New fine-grained corrections cannot overwrite retained coarse history. `retained_resolution_required` identifies the complete interval the source must rebuild. `outside_retention` means the interval has expired. A source must reconcile its pending changes before submitting a different batch; it mustn't treat a rejected request as accepted.

## Native wire format and hashing

Send a POST to `/api/health_assistant/bridge/{registration_id}/batches` with ordinary Home Assistant Bearer authentication and the current `X-Health-Receiver-Session` and `X-Health-Write-Lease` headers. See [bridge enrollment and rearm](mobile-bridge.md) for obtaining these grants. The request body has exactly three fields: `version` (integer 1), `domain` (the string `wearable`) and `stream_batch` (an object).

The stream batch has exactly these fields:

| Field | Wire value |
| --- | --- |
| `stream_id` | Enrolled lowercase UUID |
| `expected_sequence` | Current acknowledged nonnegative decimal string |
| `sequence` | Next positive decimal string |
| `hash_version` | Integer 1 |
| `content_hash` | Lowercase SHA-256 hex digest |
| `operations` | Array of 1 through 1,000 complete operations |

Sequences and counts are canonical base-10 strings, without signs, whitespace or leading zeroes. The maximum is `9223372036854775807`. No operation has a nullable or omitted required field. Its exact fields depend on its kind and the enrolled stream weighting:

| Kind | Exact fields |
| --- | --- |
| Sample-weighted replacement | `op`, `start`, `resolution`, `count`, `sum`, `min`, `max` |
| Time-weighted replacement | `op`, `start`, `resolution`, `covered_microseconds`, `weighted_sum`, `min`, `max` |
| Deletion | `op`, `start`, `resolution` |

`op` is `replace` or `delete`. `start` is an aware timestamp and `resolution` is integer 60, 300 or 3600. Start must align to that interval in UTC. Counts and covered durations are positive decimal strings. Sums and extrema are finite JSON numbers with the numeric limits above. Use the stream's weighting fields only; do not include null placeholders for the other native weighting mode.

For the native content hash:

1. Validate and normalize each operation. Spell its start as UTC with exactly six fractional digits and `Z`, for example `2026-09-10T00:00:00.000000Z`. Normalize counts and durations to canonical decimal strings and numeric aggregates to binary64 values.
2. Sort operations by normalized start, then numeric resolution. Duplicate or overlapping intervals are invalid.
3. Build an object containing exactly `hash_scope: "health_assistant.wearable_batch"`, `hash_version: 1`, `stream_id`, `expected_sequence`, `sequence` and the normalized sorted `operations`. There is no `content_hash` field in this projection.
4. Serialize that object with RFC 8785 JSON Canonicalization Scheme (JCS), encode as UTF-8 and calculate SHA-256. Use its lowercase hexadecimal spelling as `content_hash`. Do not add a newline, byte-order mark or enclosing transport fields.

Authentication, registration, session and lease metadata are outside the hash. A successful response contains `changed`, `replayed`, `sequence` and `content_hash`; booleans identify a new commit or the latest verified retry. Error responses carry a stable code. A retained-resolution error also identifies `required_start` and `required_resolution` for the complete replacement.

The [native encoding vectors](../tests/fixtures/native_wire_vectors.json) freeze the canonical bytes and hashes. Some shared vectors use illustrative identifiers to isolate encoding behavior; they are not complete valid enrollment or HTTP requests. [Native transport tests](../tests/test_wearable_bridge.py) build valid requests against the installed integration fixture.

## Reading history

The authenticated `health_assistant/wearable_series` WebSocket command accepts `stream_id`, aware `start` and `end` timestamps, and optional `resolution`, `limit` and `cursor` fields. The range can span up to 730 days. `resolution` is `auto`, `60`, `300` or `3600`; explicit resolutions are JSON integers. Automatic display resolution is one minute through seven requested days, five minutes through ninety days, and hourly for longer ranges.

Responses return each point's full start and end, actual resolution, mean, extrema and original weighting fields. A coarse interval intersecting the range is returned in full. An edge point's mean therefore describes that complete interval, not just the portion inside the requested range.

Pages contain 500 points by default, with a maximum of 1,000. Follow `next_cursor` until it is null. The service doesn't silently sample a long range. Keep the stream, time range and resolution unchanged between pages. A write, import or retention change invalidates old cursors with `stale_cursor`; restart the query to read a consistent new view. Retired streams remain readable.

## Archives and capture permissions

A schema 10 archive adds `wearable_streams.jsonl` and `wearable_buckets.jsonl`. Each stream includes its complete retained snapshot, sequence, last accepted batch hash, row count and snapshot hash. The snapshot hash binds the descriptor and every ordered bucket. It proves archive integrity, not that a vendor signed the data.

Each stream descriptor has exactly `stream_id`, `source_id`, `metric`, `unit`, `weighting`, `algorithm_id`, `algorithm_version`, `retired`, `sequence`, `hash_version`, `content_hash`, `snapshot_at`, `snapshot_bucket_count` and `snapshot_hash`. Metric is `heart_rate`, unit is `bpm`, weighting is `sample` or `time`, and both IDs are lowercase UUIDs. Algorithm fields are null or nonempty UTF-8 strings of at most 128 bytes each. Retirement is boolean. Sequence is a nonnegative decimal string; hash version is integer 1. At sequence zero, content hash is null and bucket count is zero. Otherwise content hash is lowercase SHA-256. Bucket count is an integer from zero through 50,000. Snapshot time is canonical UTC with six fractional digits and `Z`, matching the manifest creation time.

Each archived bucket has exactly `stream_id`, `start`, `resolution_s`, `sample_count`, `sample_sum`, `minimum`, `maximum`, `covered_us` and `weighted_sum`. These field names differ from native operations. Start uses the same canonical timestamp spelling; resolution is integer 60, 300 or 3600. For sample weighting, sample count is a positive decimal string and sample sum is finite; covered duration and weighted sum are null. For time weighting, covered duration is a positive decimal string and weighted sum is finite; both sample fields are null. Extrema are finite numbers in either mode. Keep every field, including nulls. There are no deletion records in a complete snapshot.

The snapshot hash is SHA-256 over one concatenated byte stream:

1. UTF-8 literal `health_assistant.wearable_snapshot.v1`, followed by one LF byte.
2. UTF-8 JCS of the complete descriptor with exactly `snapshot_hash` removed, followed by one LF byte.
3. UTF-8 JCS of each complete bucket, sorted by start and numeric resolution, each followed by one LF byte.

Include the final LF. Do not insert blank lines or a byte-order mark. An empty stream still hashes the prefix and descriptor lines. Snapshot time, retirement, nullable fields and row count all participate. The [snapshot vectors](../tests/fixtures/wearable-snapshot-vectors.json) contain complete framing examples, including the deliberately mismatched-count negative case. [Snapshot validation tests](../tests/store/test_wearable_snapshot.py) distinguish valid framing from valid domain data.

Import compares complete stream tips. Older snapshots are skipped. Matching tips leave the destination's bucket representation unchanged, including missing keys. A newer snapshot replaces the complete retained stream atomically, so an old deleted interval cannot sneak back through a row-by-row merge. Retirement is permanent for that retained identity.

Imported source and stream identities are readable history. Import doesn't grant a binding or write lease, and an imported identity cannot later be adopted for live capture. Fresh capture uses fresh identifiers and an explicit source reconciliation.

Every Home Assistant restart or integration reload pauses bridge writes until administrator rearm. The producer must present its durable committed sequence and hash, plus at most one pending next batch. Matching state and an exact lost-response case can resume; divergent state stays paused. Retained history and ordinary Health Assistant, manual, Hevy and environmental capture remain available.

## Administrator controls

The `health_assistant/wearable/admin` WebSocket command requires an active administrator session. Its `action` and `parameters` fields support:

| Action | Parameters |
| --- | --- |
| `enroll` | `registration_id`, `owner_id`, `weighting`, `algorithm_id`, `algorithm_version` |
| `retire` | `stream_id` |
| `remove` | `stream_id` |
| `fresh_namespace` | `registration_id`, `capture_mode`, `stream_ids` |

Algorithm fields are present but can be null. Enrollment returns the new stream ID and its zero sequence. It doesn't activate writing; use the bridge rearm exchange with the producer's saved state. Retiring or removing a stream pauses the source's leases before changing its metadata. Removal requires a retired stream with no retained buckets.

For a fresh namespace, `capture_mode` is `forward_only` or `backfill`, and `stream_ids` selects the old streams whose definitions should be copied. The operation checks capacity, allocates a fresh source and fresh stream IDs, and retires the old source and streams in one transaction. Old history remains separate and readable. Forward-only capture rejects intervals starting before the new boundary. Backfill must still use the currently retained resolution. Neither choice copies raw samples or resets an old stream's sequence.

## Capacity

Environmental streams, bridge sources and wearable streams share one current pool of 256 metadata slots. Retired and imported rows count too. A full pool rejects a new registration without evicting history. Only eligible unused retired metadata can be removed to free a slot.

The fully populated retention ladder has 49,344 intervals per stream before the bounded edge groups. Archive descriptors accept at most 50,000 retained rows per stream. Actual database allocation also includes indexes and fixed schema pages. Backups, archive staging and replacement transactions need additional temporary disk space. Storage measurements belong to the tested implementation; the interval count alone isn't a database-size guarantee.

The synthetic SQLite fixture measured these allocations for one stream with 49,344 retained intervals and a full registry containing one source and 255 streams:

| Allocation | Measured bytes |
| --- | ---: |
| Retained bucket pages above the empty table | 2,793,472 |
| Metadata added by 254 more streams with maximum-length algorithm labels | 131,072 |
| Temporary SQLite staging pages | 2,748,416 |
| WAL file during the fixture | 4,128,272 |
| Database backup | 3,125,248 |

That fixture uses about 56.6 allocated bytes per retained bucket. A one-interval update scanned the retained stream for maintenance and used 137,705 bytes of peak traced Python allocation. The instrumented local run took about 1.3 seconds. SQLite native buffers and temporary files are separate from that Python figure. These are fixture results, not a speed or total-disk guarantee for every Home Assistant host.
