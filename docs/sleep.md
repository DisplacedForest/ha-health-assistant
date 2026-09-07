# Sleep providers and queries

Sleep sessions are source-owned intervals, separate from scalar observations. The current implementation supports one person, `primary`. No existing provider gains sleep capability automatically. This API foundation does not claim that an Apple Health or Health Connect connection is available.

## Provider writes

Import `CandidateSleepSession` and `CandidateSleepDeletion` from `providers`. A provider declares `ProviderCapabilities(sleep_sessions=True, can_import=True)` and a `sleep_source_ids` frozenset containing only its explicitly selected stable account scopes. The sink supplies the provider key. Identity is the exact `(provider, source_id, external_id)` tuple, not session dates, titles or entity names.

A session candidate requires `source_id`, `external_id`, integer `source_revision`, `started_at` and `ended_at`. Optional fields are `person_id` (only `primary`), `start_offset_seconds`, `end_offset_seconds`, `start_zone`, `end_zone`, `reported_totals`, `stages`, `in_bed_intervals` and `provenance`. A deletion candidate carries only source identity, person and revision.

Call `await sink.async_apply_sleep_changes(candidates, checkpoint=state)`. The optional checkpoint is a bounded provider-state object. At most 100 changes and 8 MiB of normalized records fit in a batch. Duplicate identities are rejected. Candidate validation, atomic writes and checkpoint persistence run in one executor job through the shared database transaction boundary. A conflict or write failure rolls back the batch and checkpoint. Dispatch occurs only after a material committed change. An acknowledged stale replay does not count as a successful new change.

A producer must persist ordered positive signed-64-bit revisions across restart and retry. Higher revisions replace every source-owned field. Equal revision and hash is a no-op; equal revision with different contents raises `revision_conflict`. Older revisions return `stale_revision`. Neither arrival time nor a payload hash supplies a missing revision. Deleted records keep tombstones, and only a newer upstream revision can replace one. Local exclusion survives correction and deletion. It is separate from source ownership and can be changed only by a local administrator.

## Time and coverage

Use offset-aware timestamps with no more than six fractional digits. Instants normalize to UTC with six fractional digits. Session elapsed time is an exact integer number of microseconds, must be positive and cannot exceed 48 hours. The session must have ended before ingestion. Endpoint offset metadata is optional, integral and between -64,800 and 64,800 seconds. An optional IANA zone must exist and agree with an accompanying endpoint offset. Endpoints can have different zones. Missing source zone information stays unknown.

Stages are half-open intervals with exactly `start`, `end`, `stage` and `source_stage`. The source label is retained. Allowed stages are `awake`, `awake_in_bed`, `out_of_bed`, `asleep_unspecified`, `light`, `deep`, `rem` and `unknown`. Intervals must fit within the session and may be adjacent but cannot overlap or repeat. The normalizer sorts them without filling gaps, merging intervals or clipping errors.

Adapters use these vocabulary mappings while keeping original labels:

| Source value | Canonical value |
| --- | --- |
| Apple asleepCore, asleepDeep, asleepREM | light, deep, rem |
| Apple asleepUnspecified or legacy asleep | asleep_unspecified |
| Apple awake | awake |
| Apple inBed | Separate in-bed context |
| Android LIGHT, DEEP, REM, SLEEPING | light, deep, rem, asleep_unspecified |
| Android AWAKE, AWAKE_IN_BED, OUT_OF_BED | awake, awake_in_bed, out_of_bed |
| Unknown code | unknown |

A HealthKit adapter must supply durable session grouping and full replacements when constituent samples change. The repository does not group arbitrary samples by calendar night.

`in_bed_intervals` have exactly `start`, `end` and `source_label`. They cannot overlap each other but can overlap stages. They never add to asleep duration. Overlap with an `out_of_bed` stage sets `context_disagreement` while preserving both assertions.

Reported totals contain only `asleep`, `awake`, `light`, `deep`, `rem`, `asleep_unspecified` and `in_bed`, each nullable integer microseconds. Values cannot exceed the session; exclusive subtotals must be consistent with each other. Missing values stay null. In-bed totals are independent overlapping measures.

Queries return reported and interval totals separately, plus `stage_coverage_us`, `unknown_stage_us`, `uncovered_us`, `complete_stage_coverage` and disagreement flags. `asleep_duration_us` uses reported asleep first (`value_basis=reported`), otherwise a complete interval total (`derived_complete`), otherwise null (`missing`). Partial known sleep is retained as a subtotal and never called the full total.

## Normalization and source hashes

Identity components have at most 256 Unicode scalars and 1,024 UTF-8 bytes. Preserve Unicode exactly. Raw stage/context labels have at most 64 scalars. Each interval list has at most 4,096 items. A normalized source payload has at most 512 KiB and provenance at most 64 KiB, with nesting limited to eight levels. Invalid Unicode, unknown fields, non-finite numbers and boolean numeric values are rejected without truncation.

A normalized payload has every declared key. Missing endpoint metadata becomes null. Missing or null totals expands to all seven nullable fields. Missing arrays become empty, but explicit null arrays are invalid. Missing provenance becomes its fixed default object; explicit null provenance is invalid.

Provenance permits only `source_app`, `source_device`, `algorithm`, `source_version`, `bridge_version`, `source_modified_at`, `native_record_ids` and `provider_confidence`. The first five are nullable strings of at most 256 scalars. `source_modified_at` is an aware timestamp or null. Native IDs are a duplicate-free set of at most 4,096 strings of at most 256 scalars, sorted by UTF-16 code units. Missing IDs become an empty array. Confidence is null or an object with a required finite binary64 number or bounded string `value`, and a nullable bounded string `scale`. It is a source label, not a comparable confidence score. Do not send credentials, transport cursors or raw vendor payloads.

Hash the RFC8785 canonical UTF-8 encoding of this projection with SHA-256: `hash_scope=health_assistant.sparse_record`, `hash_version=1`, `domain=sleep`, `identity={person_id,provider,source_id,external_id}`, `record_type=sleep_session`, `operation=upsert|delete`, and the complete normalized `payload` (null for deletion). Exclude source revision, local row IDs, exclusion, ingestion times and query generation. Timestamps use the normalized UTC spelling. Numbers normalize before JCS; native IDs and intervals are sorted by the domain rules first. Hash rules are versioned and must not change silently.

## Read commands

The WebSocket envelope uses `id` for request correlation. Commands select a local sleep row with `session_id`; responses expose its local `id`. Revisions are canonical decimal strings in every WebSocket and archive field so JavaScript cannot round them.

- `health_assistant/sleep_sessions` requires aware `start` and `end`, with a positive range of at most 366 days. Optional `source` has both `provider` and `source_id`. `date_basis=overlap` selects interval intersections; `ended_at` selects sessions ending within `[start,end)`. `excluded=true` selects excluded sessions only. The default limit is 50, maximum 100. Results sort by descending end time and local ID. `next_cursor` pins the filters and sleep generation. A material change makes an old cursor fail with `stale_cursor`; restart the list.
- `health_assistant/sleep_session` takes `session_id`, optional `kind=stages|in_bed_intervals`, limit (default 128, maximum 256) and cursor. Detail returns safe provenance, totals and the requested interval page. The cursor pins the revision/hash and interval kind. A correction invalidates it. Deleted detail has identity and status without the old payload.
- `health_assistant/sleep_session_exclusion` requires an administrator and takes `session_id`, boolean `excluded`, `expected_source_revision` and `expected_payload_hash`. A mismatch returns `revision_conflict`, so a stale dialog cannot act on changed content. Clearing exclusion cannot reactivate a source deletion.

Lists omit stages and provenance. All reads and local mutations enforce the primary person. There is no public sleep write service. Diagnostics expose sleep counts and capability flags, never session times, stages, source-account bindings or payloads.
