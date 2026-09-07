# Recovery providers and queries

Recovery records preserve what a source measured: resting heart rate, HRV SDNN, HRV RMSSD or respiratory rate. SDNN and RMSSD stay separate. We don't convert one method into another, infer resting heart rate or calculate HRV from average heart rate. This is an internal storage and API contract. It doesn't add a phone connection, Recovery panel, readiness score or new sensors.

## Provider writes

Import `CandidateRecoveryObservation` and `CandidateRecoveryDeletion` from `providers`. Declare the supported metric strings in `ProviderCapabilities(recovery_metrics=frozenset(...))` and explicitly selected stable accounts in `recovery_source_ids`. Both are empty by default. The provider must also allow imports. Existing scalar permissions grant no recovery access.

An observation candidate requires `source_id`, `external_id`, positive integer `source_revision`, `metric`, `value`, `unit`, `started_at` and `ended_at`. Optional fields are `person_id` (only `primary`), `context`, `algorithm_id`, `algorithm_version`, endpoint offsets/zones and `provenance`. Deletion candidates retain source identity, revision, metric and person, with no measurement payload.

Call `await sink.async_apply_recovery_changes(candidates, checkpoint=state)`. The sink supplies provider ownership and checks account and metric permissions. A batch has at most 100 records and 1 MiB of normalized content. Duplicate identities are invalid. Prevalidation, revision checks, records and optional checkpoint commit atomically. An update signal follows a material committed change only. Errors remain scoped to the selected account; success in a different account or domain doesn't clear them.

Identity is `(provider, source_id, external_id)`. Dates, measurement values, context and algorithm metadata can change at a higher revision. The metric and person cannot. A metric change requires deletion and a new identity. A deletion before the first observation still names the metric, so a later record cannot reuse that identity for another method.

Higher revisions replace the complete payload. Equal revision and hash is a no-op. Equal revision with different contents raises `revision_conflict` and rolls back the entire batch. Older revisions return `stale_revision` without replacing newer data. Missing results or revoked permission never imply deletion. Source deletion removes measurements and retains a minimal tombstone. Only a newer source upsert can replace it. Local exclusion survives corrections and deletions; clearing exclusion cannot restore a source deletion.

## Units, windows and context

| Metric | Canonical unit | Accepted equivalent inputs |
| --- | --- | --- |
| `resting_heart_rate` | `bpm` | `count/min`; `count/s` multiplied by 60 |
| `hrv_sdnn` | `ms` | `s` multiplied by 1000 |
| `hrv_rmssd` | `ms` | `s` multiplied by 1000 |
| `respiratory_rate` | `breaths/min` | `count/min`; `count/s` multiplied by 60 |

Values must be finite, positive numbers. Numeric strings, booleans and unrecognized units are rejected. This is shape validation, not a clinical reference range. Values aren't clamped. Conversion parses binary64 once and performs the declared multiplication; arbitrary decimal spellings aren't guaranteed to produce identical binary values.

A point measurement has equal endpoints. A summary reports its actual measurement window, up to 48 hours. Completed records only are accepted. Timestamps need explicit offsets and at most six fractional digits, then normalize to UTC microseconds. Optional endpoint offsets range from -64,800 to 64,800 seconds and must agree with an accompanying IANA zone. Different endpoint zones are allowed. Missing zones stay unknown.

Context is `spot`, `sleep_summary`, `daily_summary` or `unknown`. Missing context becomes `unknown`; null is invalid. Time of day doesn't establish sleeping or resting context. Comparable series have the same provider, source, metric, context, algorithm ID and algorithm version. Null algorithm fields mean unknown. Different methods, sources, contexts and algorithm versions aren't combined. Daily selection and baseline math belong to the shared derived-metrics layer.

## Normalization and provenance

Identity components contain at most 256 Unicode scalars and 1,024 UTF-8 bytes. Algorithm IDs and versions contain at most 128 scalars. Preserve exact Unicode; don't trim or case-fold identities. Invalid Unicode and unknown fields are rejected. Payloads are bounded to 32 KiB, provenance to 16 KiB and nesting to eight levels.

Normalized payloads contain `value`, `unit`, `started_at`, `ended_at`, `context`, `algorithm_id`, `algorithm_version`, `start_offset_seconds`, `end_offset_seconds`, `start_zone`, `end_zone` and `provenance`. Optional algorithm and endpoint metadata becomes null. Metric is the immutable envelope `record_type`, not a second payload field.

Provenance permits `source_app`, `source_device`, `source_version` and `bridge_version` (nullable strings of at most 256 scalars), `source_modified_at` (nullable aware timestamp), and `raw_value`/`raw_unit`. Raw value and unit must both be null or both present. Their allowed conversion must match the normalized measurement. Raw unit has at most 64 scalars. Missing provenance becomes the complete object with null fields; explicit null provenance is invalid. Credentials, cursors and arbitrary source payloads aren't accepted.

Hash the RFC8785 canonical UTF-8 bytes with SHA-256, using `hash_scope=health_assistant.sparse_record`, `hash_version=1`, `domain=recovery`, `identity={person_id,provider,source_id,external_id}`, immutable metric as `record_type`, `operation=upsert|delete`, and the complete normalized `payload` (null for deletion). Source revision and all local bookkeeping are excluded. Retained raw provenance is included, so equivalent measurements with different raw metadata can have different hashes. Producers must preserve the complete normalized contents on retry or issue a higher revision.

## WebSocket reads and exclusion

All commands require an authenticated Home Assistant user and enforce the primary person. The top-level `id` is request correlation. Detail and exclusion use `record_id` to select a local row; responses keep its local `id`. Source revisions are canonical positive decimal strings, preserving all signed-64-bit values in JavaScript.

`health_assistant/recovery_observations` requires aware `start` and `end`, and a `series` object with exactly `provider`, `source_id`, `metric`, `context`, `algorithm_id` and `algorithm_version`. Include null for unknown algorithm fields. The range must be positive and at most 366 days. Both points and summaries use end-time membership `[start,end)`. Active records are returned by default; `excluded=true` selects excluded records only. The default page size is 50, maximum 100. Rows sort by descending end time and local ID. `next_cursor` pins the filter and recovery generation. A committed change makes it fail with `stale_cursor`; restart the list.

Lists expose typed values, measurement windows, context and algorithm information, with provider key as the stable source label. Provenance appears only in `health_assistant/recovery_observation` detail. Deleted detail contains identity, metric, revision and status without old measurements.

`health_assistant/recovery_observation_exclusion` requires an administrator and takes `record_id`, boolean `excluded`, `expected_source_revision` and lowercase SHA-256 `expected_payload_hash`. Stale details return `revision_conflict`. Read-only users cannot mutate. No public recovery ingestion service is enabled. Diagnostics contain counts and capability/state information, without measurement values, times, account identities or raw source errors.

## Upgrade and portable history

Migration 8 adds recovery storage after sleep migration 7, with no scalar backfill. Back up before upgrading. Rollback needs matching older integration files and a database backup at the corresponding schema.

Format 2/schema 8 appends `recovery_records.jsonl`. It preserves metric identity, complete normalized payloads, revisions, tombstones and local exclusions. Source revisions govern replay, while exclusions merge with OR even when the source payload is stale. Format 1/schema 6 and format 2/schema 7 imports leave existing recovery history alone. Import does not enroll or reconnect a source. See [portable history](interchange-format.md) for validation, batch interruption and retry behavior.
