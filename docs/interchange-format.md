# Portable history format

Format 1 is a gzip-compressed tar archive produced by `health_assistant.export_history` and read by `health_assistant.import_history`. It carries the logical history stored by database schema 6. It is separate from the database backup format. No schema migration is part of importing an archive.

## Actions

Both actions require a Home Assistant administrator. `path` names a `.tar.gz` file under the Home Assistant config directory. Relative paths are recommended. Traversal, symlink parents and symlink inputs are rejected. Import accepts only a regular file. Export creates missing parent directories with private permissions, writes privately and publishes the finished archive without replacing an existing file.

`export_history` returns the relative path, format version and record counts. It uses SQLite's online backup API through the shared store lock to take a consistent snapshot. Ingestion can resume while that snapshot is serialized. The archive reflects the snapshot, not writes that arrive later.

`import_history` takes `dry_run`, which defaults to `true`. It first copies the input into private staging, validates the complete archive, then simulates the merge against a database snapshot. Validation or simulation failure leaves the live database unchanged. A dry run stops there. Set `dry_run: false` to apply the validated history in bounded transaction batches.

The response contains archive counts, a date span, source names and expected create, merge and unchanged counts. Priorities are counted by metric group, not by individual rank row. Canonical observation counts are shown before and after the simulated merge; source claims determine the final canonical count. Sources are limited to 100 entries and display labels to 256 characters, with truncation flags. Full identities are retained for storage and matching. The date span uses observation times, workout bounds and environmental bucket bounds. Bucket bounds do not imply complete sensor coverage.

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

JSON is UTF-8. Each JSONL record is one object followed by a newline. Duplicate JSON keys, non-finite numbers and unknown or missing fields are rejected. Empty domains have zero-byte files. Files have no header rows. Archive readers do not extract paths supplied by the tar headers.

The manifest has exactly these fields:

| Field | Value |
| --- | --- |
| `format` | `health-assistant` |
| `format_version` | Integer `1` |
| `schema_version` | Integer `6` |
| `created_at` | ISO 8601 timestamp with timezone |
| `files` | Object keyed by the seven JSONL filenames |

Each `files` entry contains `records`, `bytes` and a lowercase SHA-256 `sha256` for the exact uncompressed file bytes. Counts, sizes and checksums must match. The gzip trailer is checked even after the tar end marker. Checksums detect damage, but they do not authenticate the archive's author. Only import files you trust with your history.

Readers currently support only format 1 and schema 6. Higher versions are rejected before live writes. A future format must get its own reader or an explicit conversion path; changing the version number is not a conversion.

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

Canonical observations must agree with the claims, priorities, exclusions and duplicate flags when the existing reconciliation rules run over them. Every observation needs a claim, and every claim references a matching observation. The importer verifies that consistency in staging. It then replays claims through the canonical repository instead of copying the archive's canonical rows into the destination.

Workout titles, energy and distance can be null. Exercise and set records remain in workout provenance exactly as stored, including source-specific fields. The archive cannot add detail that the provider never supplied.

Priority context is currently the empty string. Ranks start at zero and are contiguous within each metric. Provider names are unique within a metric.

Environmental metrics are `temperature` in °C, `humidity` in % and `co2` in ppm. Stream metadata is immutable and has a maximum of 128 characters per field. A public stream identity refers to exactly one source, metric and area revision. The destination may have different local integer IDs; buckets are mapped through `public_id`. Neither live sensor mappings nor provider accounts are created by import.

Environmental buckets are UTC-aligned at 300 or 3600 seconds. Times and durations use integer milliseconds. `sample_sum / sample_count` is a sample mean. `weighted_sum / covered_ms` is a time-weighted mean over covered intervals. A zero denominator means unavailable, not a zero measurement. Extrema include the covered values and fresh samples. First and last report times are null when there were no samples. Carried coverage can exist without a sample inside that bucket. Fine and hourly rows cannot overlap for a stream. Bounds, coverage, extrema and sums are validated before replay.

There is exactly one maintenance row with `id: 1`. Last success and duration may be null, counters are nonnegative, and `failed` is zero or one. The maintenance row is restored when the destination's resulting complete environmental domain matches the archive. When history is combined with other or newer local streams or buckets, the destination keeps its existing maintenance state.

## Merge and recovery

Health claims match by provider, external ID, metric and observation time. Workouts match by provider and external ID. A matching identity belonging to a different person is rejected. For the same identity, the later `ingested_at` wins; an equal timestamp uses the incoming record. If either side is excluded, the merged record is excluded. Reconciliation also preserves exclusions across the resulting canonical group. Import never uses a replay to restore an excluded reading.

Existing records absent from the archive are retained. Repeating the same archive against an unchanged destination produces no creates or merges. Overlapping exports merge by the same identities rather than adding copies. Priorities are imported before claims and can change which retained source supplies a current value.

Environmental public IDs must have identical metadata on both sides. The registry remains capped at 256 active or historical streams. Bucket identity is the mapped stream, resolution and start time. Identical buckets are unchanged. A later `updated_ms` wins at the same resolution; equal update bounds with different contents are rejected as ambiguous. This time bound is not a general provider revision number.

An existing hourly bucket prevents an incoming five-minute row from recreating detail for that hour. An incoming hourly bucket replaces its fine rows atomically, provided none has a later update bound. It is treated as the authoritative aggregate for that hour. The importer does not add fine and coarse totals together. Normal environmental retention still applies: five-minute history lasts 90 days, then hourly history lasts to the 730-day horizon. Import itself preserves the archive snapshot, including old rows awaiting the next maintenance run.

Priority changes and each group of at most 256 claims, workouts or buckets commit independently. Stream registration is one transaction bounded by the 256-stream registry. A failure can leave earlier batches committed, so import is not an all-or-nothing database restore. Retry the same archive after fixing the failure. Natural identities, exclusion preservation, bucket ordering and mapped stream identities make completed work replayable. Entity refresh is dispatched even when a non-dry import stops after partial progress.

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
