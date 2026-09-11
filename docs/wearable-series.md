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

## Reading history

The authenticated `health_assistant/wearable_series` WebSocket command accepts `stream_id`, aware `start` and `end` timestamps, and optional `resolution`, `limit` and `cursor` fields. The range can span up to 730 days. `resolution` is `auto`, `60`, `300` or `3600`; explicit resolutions are JSON integers. Automatic display resolution is one minute through seven requested days, five minutes through ninety days, and hourly for longer ranges.

Responses return each point's full start and end, actual resolution, mean, extrema and original weighting fields. A coarse interval intersecting the range is returned in full. An edge point's mean therefore describes that complete interval, not just the portion inside the requested range.

Pages contain 500 points by default, with a maximum of 1,000. Follow `next_cursor` until it is null. The service doesn't silently sample a long range. Keep the stream, time range and resolution unchanged between pages. A write, import or retention change invalidates old cursors with `stale_cursor`; restart the query to read a consistent new view. Retired streams remain readable.

## Archives and capture permissions

A schema 10 archive adds `wearable_streams.jsonl` and `wearable_buckets.jsonl`. Each stream includes its complete retained snapshot, sequence, last accepted batch hash, row count and snapshot hash. The snapshot hash binds the descriptor and every ordered bucket. It proves archive integrity, not that a vendor signed the data.

Import compares complete stream tips. Older snapshots are skipped. Matching tips leave the destination's bucket representation unchanged, including missing keys. A newer snapshot replaces the complete retained stream atomically, so an old deleted interval cannot sneak back through a row-by-row merge. Retirement is permanent for that retained identity.

Imported source and stream identities are readable history. Import doesn't grant a binding or write lease, and an imported identity cannot later be adopted for live capture. Fresh capture uses fresh identifiers and an explicit source reconciliation.

Every Home Assistant restart or integration reload pauses bridge writes until administrator rearm. The producer must present its durable committed sequence and hash, plus at most one pending next batch. Matching state and an exact lost-response case can resume; divergent state stays paused. Retained history and ordinary Health Assistant, manual, Hevy and environmental capture remain available.

## Capacity

Environmental streams, bridge sources and wearable streams share one current pool of 256 metadata slots. Retired and imported rows count too. A full pool rejects a new registration without evicting history. Only eligible unused retired metadata can be removed to free a slot.

The fully populated retention ladder has 49,344 intervals per stream before the bounded edge groups. Archive descriptors accept at most 50,000 retained rows per stream. Actual database allocation also includes indexes and fixed schema pages. Backups, archive staging and replacement transactions need additional temporary disk space. Storage measurements belong to the tested implementation; the interval count alone isn't a database-size guarantee.
