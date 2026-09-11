# Portable history format

Format 2 is a gzip-compressed tar archive produced by `health_assistant.export_history` and read by `health_assistant.import_history`. It carries the logical history stored by database schema 9, including sleep, recovery, native bridge sources and sparse ledgers. The frozen format 1/schema 6 reader remains available for 0.2 archives. It is separate from the database backup format. No schema migration is part of importing an archive.

## Actions

Both actions require a Home Assistant administrator. `path` names a `.tar.gz` file under the Home Assistant config directory. Relative paths are recommended. Traversal, symlink parents and symlink inputs are rejected. Import accepts only a regular file. Export creates missing parent directories with private permissions, writes privately and publishes the finished archive without replacing an existing file.

`export_history` returns the relative path, format version and record counts. It uses SQLite's online backup API through the shared store lock to take a consistent snapshot. Ingestion can resume while that snapshot is serialized. The archive reflects the snapshot, not writes that arrive later.

`import_history` takes `dry_run`, which defaults to `true`. It first copies the input into private staging, validates the complete archive, then simulates the merge against a database snapshot. Validation or simulation failure leaves the live database unchanged. A dry run stops there. Set `dry_run: false` to apply the validated history. The health phase is atomic; later domains use bounded transaction batches.

The response contains archive counts, a date span, source names and expected create, merge and unchanged counts. Priorities are counted by metric group, not by individual rank row. Canonical observation counts are shown before and after the simulated merge; source claims determine the final canonical count. Sources are limited to 100 entries and display labels to 256 characters, with truncation flags. Full identities are retained for storage and matching. The date span uses observation times, workout, active sleep and recovery bounds, and environmental bucket bounds. Bucket bounds do not imply complete sensor coverage.

The applied response also contains actual write counts. Those counts can differ from the preview if ingestion changed the database between simulation and application. Imported priorities apply even when a metric has no incoming readings. An empty priority list resets that metric to the store's default ordering.

## Archive layout

Members appear exactly once, in this order. They must be regular files, with no additional members:

1. `manifest.json`
2. `observations.jsonl`
3. `source_claims.jsonl`
4. `workouts.jsonl`
5. `metric_priorities.jsonl`
6. `environment_streams.jsonl`
7. `environment_buckets.jsonl`
8. `environment_maintenance.jsonl`
9. `sleep_sessions.jsonl` (format 2/schema 7, 8 and 9)
10. `recovery_records.jsonl` (format 2/schema 8 and 9)
11. `bridge_sources.jsonl` (format 2/schema 9)
12. `bridge_records.jsonl` (format 2/schema 9)

JSON is UTF-8. Each JSONL record is one object followed by a newline. Duplicate JSON keys, non-finite numbers and unknown or missing fields are rejected. Empty domains have zero-byte files. Files have no header rows. Archive readers do not extract paths supplied by the tar headers.

The manifest has exactly these fields:

| Field | Value |
| --- | --- |
| `format` | `health-assistant` |
| `format_version` | Integer `2` |
| `source_schema_version` | Integer `9` |
| `created_at` | ISO 8601 timestamp with timezone |
| `files` | Object keyed by the eleven JSONL filenames |

Each `files` entry contains `records`, `bytes` and a lowercase SHA-256 `sha256` for the exact uncompressed file bytes. Counts, sizes and checksums must match. The gzip trailer is checked even after the tar end marker. Checksums detect damage, but they do not authenticate the archive's author. Only import files you trust with your history.

The static compatibility registry accepts format 1/schema 6 and separate format 2 layouts for schemas 7, 8 and 9. Format 1 retains its original `schema_version` manifest field, seven domains and exact record definitions. Format 2 uses `source_schema_version`. Higher or mixed versions are rejected before live writes. A future layout must have its own registry entry and implemented validation; changing a manifest version is not a conversion. Old readers reject later layouts. There is no downgrade export that drops later domains.

An earlier archive that lacks a later domain does not change that domain in the destination. Importing a format 1 archive leaves existing sleep and recovery payloads, exclusions, tombstones and settings alone. Schema 7 imports leave recovery alone.

Layouts before schema 9 cannot write the reserved `bridge:<UUID>` namespace. Such incoming records fail with `unsupported_namespace`; valid older archives leave existing bridge history alone.

## Native bridge records

`bridge_sources` contains exactly `source_id`, `person_id`, `adapter_kind`, `upstream_store`, `upstream_scope`, `created_at` and `label`. UUIDs are lowercase and person is `primary`. All fields except label are immutable. Owner bindings, origin flags, retirement permissions, receipts, cursor handles, receiver sessions and leases are never portable. Unknown identities become unbound `imported_history` sources. Existing labels win, with label-retention counts in the import response. Descriptor-only identities allocate no registry slot, but immutable conflicts still fail preview.

`bridge_records` contains exactly `source_id`, `domain`, `external_id`, `record_type`, `source_revision`, `hash_version`, `payload_hash`, `source_state`, `locally_excluded`, `first_ingested_at`, `last_ingested_at` and `payload`. Domain is scalar or workout. Revisions are positive decimal strings, exclusion is boolean, and ingestion times use the normalized UTC wire spelling. Deleted payloads are null. Local projection IDs are omitted. Fresh imports preserve the first and last bookkeeping times; accepted corrections merge first/last bounds without letting the last time precede the first.

Every bridge claim, workout, sleep record and recovery record, including tombstones, needs its source descriptor in the same archive. Active scalar/workout ledgers and their exported projections must match one-to-one in payload, effective exclusion, person, source, external identity and timestamps. Deleted ledgers must have no projection. The complete graph and canonical relationships are validated before preview or live writes. File order cannot create an orphan source.

Legacy replay skips bridge projections. Accepted ledger revisions reconstruct the authoritative projections, then reconcile affected scalar metrics in one full ordered pass. Local exclusion merges with OR even on stale content. New source descriptors are inserted inside the first dependent record batch, so failure rolls back both. Completed earlier batches remain committed and retry converges. Sleep batches are also bounded by encoded size.

After a successful preview, live import suspends affected runtime leases, drains the write boundary and blocks rearm until application finishes. Accepted new source content, higher revisions and tombstones set persistent `needs_fresh_namespace` on a local enrollment. Exclusion-only changes, stale revisions and equal-revision replays do not. No import restores a checkpoint or write grant. See [the native bridge contract](mobile-bridge.md) for rearm and full-backup behavior.

## Records

Database integer IDs in an archive are local references within that archive. The destination assigns its own IDs. Timestamps for health records are normalized to UTC with microsecond precision. Health metrics use canonical units: weight and lean mass in kg, body fat percentage in %, steps in count, distance in m, and active energy in kcal. `status` is `active` or `excluded`. Provenance is a JSON object and retains nested source details.

| Domain | Fields |
| --- | --- |
| Observations | `id`, `person_id`, `metric`, `value`, `unit`, `observed_at`, `provider`, `external_id`, `ingested_at`, `provenance`, `status`, `possible_duplicate` |
| Source claims | The observation fields except `possible_duplicate`, plus `observation_id` |
| Workouts | `id`, `person_id`, `provider`, `external_id`, `workout_type`, `title`, `started_at`, `ended_at`, `energy_kcal`, `distance_m`, `ingested_at`, `provenance`, `status` |
| Priorities | `metric`, `context`, `rank`, `provider` |
| Environmental streams | `id`, `public_id`, `mapping_id`, `source_id`, `entity_id`, `metric`, `area_id`, `area_name`, `unit` |
| Environmental buckets | `stream_id`, `start_ms`, `resolution_s`, `sample_count`, `sample_sum`, `minimum`, `maximum`, `weighted_sum`, `covered_ms`, `first_report_ms`, `last_report_ms`, `updated_ms` |
| Environmental maintenance | `id`, `last_success_ms`, `duration_ms`, `rolled_up`, `deleted`, `failed` |
| Sleep sessions | `person_id`, `provider`, `source_id`, `external_id`, `source_revision`, `payload_hash`, `hash_version`, `record_type`, `operation`, `payload`, `locally_excluded` |

Canonical observations must agree with the claims, priorities, exclusions and duplicate flags when the existing reconciliation rules run over them. Every observation needs a claim, and every claim references a matching observation. The importer verifies that consistency in staging. It then replays claims through the canonical repository instead of copying the archive's canonical rows into the destination.

Workout titles, energy and distance can be null. Exercise and set records remain in workout provenance exactly as stored, including source-specific fields. The archive cannot add detail that the provider never supplied.

Priority context is currently the empty string. Ranks start at zero and are contiguous within each metric. Provider names are unique within a metric.

Environmental metrics are `temperature` in °C, `humidity` in % and `co2` in ppm. Stream metadata is immutable and has a maximum of 128 characters per field. A public stream identity refers to exactly one source, metric and area revision. The destination may have different local integer IDs; buckets are mapped through `public_id`. Neither live sensor mappings nor provider accounts are created by import.

Environmental buckets are UTC-aligned at 300 or 3600 seconds. Times and durations use integer milliseconds. `sample_sum / sample_count` is a sample mean. `weighted_sum / covered_ms` is a time-weighted mean over covered intervals. A zero denominator means unavailable, not a zero measurement. Extrema include the covered values and fresh samples. First and last report times are null when there were no samples. Carried coverage can exist without a sample inside that bucket. Fine and hourly rows cannot overlap for a stream. Bounds, coverage, extrema and sums are validated before replay.

There is exactly one maintenance row with `id: 1`. Last success and duration may be null, counters are nonnegative, and `failed` is zero or one. The maintenance row is restored when the destination's resulting complete environmental domain matches the archive. When history is combined with other or newer local streams or buckets, the destination keeps its existing maintenance state.

## Sleep records

Sleep identity is `(provider, source_id, external_id)`, scoped to `person_id=primary`. No local row ID, ingestion timestamp, query generation or provider checkpoint is exported. `source_revision` is a canonical decimal string between `"1"` and `"9223372036854775807"`. `hash_version` is integer 1, `record_type` is `sleep_session`, and `operation` is `upsert` or `delete`. Deletions have `payload=null`; they retain identity, revision/hash and the boolean local exclusion only.

An upsert carries the complete normalized sleep payload described in [sleep provider guidance](sleep.md), including nullable endpoint metadata, fixed totals and provenance fields, and sorted stage/context arrays. A lowercase SHA-256 of the RFC8785 projection verifies that content. Revisions and local exclusion are outside the source hash. Archive checksums and record hashes have different jobs and neither authenticates a source.

Newer source revisions replace the complete payload, equal revision/hash pairs are unchanged, and lower revisions are counted as stale. Equal revisions with different hashes fail. Local exclusion merges with OR even when the archived source payload is stale. An old active payload never replaces a newer tombstone. Imported history does not reconnect an account.

After the existing domains, sleep is replayed in batches of at most 100 sessions and 8 MiB. A failed batch rolls back; completed earlier phases and batches remain committed. Full validation and simulation run before any live phase, so a conflict found in preview starts no live writes. Counts distinguish `create`, `update`, `stale`, `unchanged`, `deleted` and `exclusion_change`. Stages are part of one session, not additional records.

## Recovery records

`recovery_records.jsonl` uses the same envelope fields as sleep. Its immutable `record_type` is `resting_heart_rate`, `hrv_sdnn`, `hrv_rmssd` or `respiratory_rate`. The complete normalized payload and hash projection are defined in [the recovery contract](recovery.md). Deletes have a null payload while retaining metric identity. Local IDs, ingestion times and query generations are not exported.

Recovery replay uses source revision and hash, with sticky exclusion OR even on a stale payload. Metric reuse under one source identity is invalid. A full validation and simulated replay precede any live writes. Recovery batches have at most 100 records and 1 MiB, and commit independently after sleep. A conflict found in preview starts no live writes; earlier completed phases can survive an interruption during apply. Counts distinguish create, update, stale, unchanged, deleted and exclusion_change. Import never grants provider permissions.

## Merge and recovery

Health claims match by provider, external ID, metric and observation time. Workouts match by provider and external ID. A matching identity belonging to a different person is rejected. For the same identity, the later `ingested_at` wins; an equal timestamp uses the incoming record. If either side is excluded, the merged record is excluded. Reconciliation also preserves exclusions across the resulting canonical group. Import never uses a replay to restore an excluded reading.

Existing records absent from the archive are retained. Repeating the same archive against an unchanged destination produces no creates or merges. Overlapping exports merge by the same identities rather than adding copies. Imported priorities are used for final reconciliation and can change which retained source supplies a current value.

Environmental public IDs must have identical metadata on both sides. The registry remains capped at 256 active or historical streams. Bucket identity is the mapped stream, resolution and start time. Identical buckets are unchanged. A later `updated_ms` wins at the same resolution; equal update bounds with different contents are rejected as ambiguous. This time bound is not a general provider revision number.

An existing hourly bucket prevents an incoming five-minute row from recreating detail for that hour. An incoming hourly bucket replaces its fine rows atomically, provided none has a later update bound. It is treated as the authoritative aggregate for that hour. The importer does not add fine and coarse totals together. Normal environmental retention still applies: five-minute history lasts 90 days, then hourly history lasts to the 730-day horizon. Import itself preserves the archive snapshot, including old rows awaiting the next maintenance run.

Priorities and all source claims are written in one streamed health transaction. Canonical reconciliation runs after the complete merged claim set is present. This prevents incomplete temporary groups from spreading exclusions to records that belong to a different final group. Any failure during this phase rolls back priorities, claims and canonical observations together. It can hold the shared database lock longer and grow the write-ahead log with the size of the imported health history. Other ingestion waits for this phase to finish.

After the health phase, each group of at most 256 workouts or buckets commits independently. Stream registration is one transaction bounded by the 256-stream registry. A failure in a later phase can leave earlier work committed, so import is not an all-or-nothing database restore. Retry the same archive after fixing the failure. Natural identities, exclusion preservation, bucket ordering and mapped stream identities make completed work replayable. Entity refresh is dispatched even when a non-dry import stops after partial progress.

Use a database backup if you need to return exactly to the state before importing. A portable import merges data and is not an undo operation.

## Size, memory and privacy

Each JSON record, including its newline, is limited to 1 MiB. An archive is limited to 2 GiB compressed and 8 GiB of JSONL content. The reader also bounds expanded tar data and metadata. These limits reject an archive before live replay; they do not reserve disk space for it.

Export stages a database snapshot, the JSONL files and the compressed archive on disk. Import stages a copied archive, a validated database and a destination snapshot for simulation. Keep enough free disk space for these temporary copies in addition to the live database and its write-ahead log. Temporary folders are private and removed when the operation exits, including validation failures.

Serialization, staging and replay use bounded records and pages of 256 rows. The two-year test covers 41,280 retained environmental buckets with less than 16 MiB of peak traced Python allocations for either export or import. This measures Python allocations, not total process RSS or SQLite's own caches. Individual health reconciliation groups and a configured priority list still depend on the number of nearby claims or provider names; the whole historical dataset is never loaded into one list.

Archives include health values, timestamps, provenance, workout sets, source identities and room names. They are private files but are not encrypted. Provider runtime state, sync cursors, credentials and Home Assistant options are outside the archive. Source provenance is preserved, so any sensitive information a source recorded there is included. Room history describes environmental context; it does not establish where a person was or what they were exposed to.

## Record example

This five-minute bucket contains one 20 °C report and one minute of coverage. The other four minutes are missing. Both means are 20 °C; the coverage fraction is 0.2.

```json
{"stream_id":1,"start_ms":1788696000000,"resolution_s":300,"sample_count":1,"sample_sum":20.0,"minimum":20.0,"maximum":20.0,"weighted_sum":1200000.0,"covered_ms":60000,"first_report_ms":1788696000000,"last_report_ms":1788696000000,"updated_ms":1788696120000}
```

It belongs in `environment_buckets.jsonl` with a trailing newline and needs a matching stream record, for example:

```json
{"id":1,"public_id":"d0117465-3848-4bca-95f8-49bbcd3fb5ac","mapping_id":"bedroom","source_id":"sensor.temperature","entity_id":"sensor.temperature","metric":"temperature","area_id":"bedroom","area_name":"Bedroom","unit":"°C"}
```

Use the export action to obtain a complete example archive with the matching manifest checksums. Plain regular tar entries are required; PAX, GNU long-name and sparse extensions are rejected before their payloads are read. Nonzero trailing data after the tar end marker is also rejected.
