# Native phone bridge

The native receiver accepts source-owned health records from a compatible producer. It doesn't read a phone by itself. Apple Health and Health Connect client routes still need qualification with named client versions and real producer evidence. The synthetic protocol fixtures in this repository prove receiver behavior, not client compatibility or complete source history.

An administrator enrolls a source and explicitly rearms capture after every integration setup, reload, update or full-backup restore. Existing sensor, manual and Hevy providers keep their current behavior. The receiver adds no cloud service or phone application.

## Enrollment and ownership

Use the Home Assistant WebSocket command `health_assistant/bridge/admin` with `action: enroll`. Its `parameters` object contains `owner_id`, `metadata` and `checkpoint_modes`. Metadata contains exactly `adapter_kind`, `upstream_store`, `upstream_scope` and `label`. The store is `apple_health` or `health_connect`; scope identifies the selected upstream account without containing credentials. The four checkpoint modes are keyed by `scalar`, `workout`, `sleep` and `recovery`, each set to `none` or `opaque_cas`.

The receiver returns a new `registration_id` and its current `receiver_session_id`. Registration and source IDs are the same lowercase UUID. The corresponding provider is `bridge:<source_id>`. Person is always `primary`. Adapter kind, upstream store, account scope, person and creation time are immutable. Labels are display metadata. Accounts never share an identity because their upstream record IDs happen to match.

Adapter kind is an ASCII identifier of at most 64 bytes. Scope is at most 256 UTF-8 bytes and label at most 128 bytes. Each source reserves room for all four maximum-size receipts within a 2 KiB logical metadata budget. Metadata with excessive JSON escaping can reach that combined limit before an individual field limit. The shared registry holds at most 256 retained environmental streams, bridge sources and wearable streams in total. Imported and retired identities consume capacity too.

## Sparse requests

Send `POST /api/health_assistant/bridge/{registration_id}/batches` with normal current Home Assistant bearer authentication, `Content-Type: application/json`, `X-Health-Receiver-Session` and `X-Health-Write-Lease`. A lease belongs to its source, bound owner, armed domains and current receiver setup. Do not put bearer tokens or leases into payloads, source scopes or logs.

The body contains exactly:

```json
{
  "version": 1,
  "domain": "scalar",
  "batch_id": "00000000-0000-4000-8000-000000000001",
  "hash_version": 1,
  "request_hash": "<SHA-256 of the normalized batch projection>",
  "records": [],
  "checkpoint": null
}
```

This illustrates the fields. An empty batch is only valid when it advances an opaque checkpoint. Each record contains exactly `external_id`, `record_type`, `source_revision`, `operation`, `hash_version`, `payload_hash` and `payload`. Operation is `upsert` with a complete payload, or `delete` with null payload. An upsert replaces the whole previous payload. Deletion before creation is valid, and a higher revision can resurrect a tombstone.

Revision is a decimal string from `"1"` to `"9223372036854775807"`, without signs or leading zeroes. It comes from the producer's durable ordered source state, never a guessed timestamp. Record identity is source, domain and external ID. Record type cannot change, including on a stale request or tombstone. External IDs allow at most 256 Unicode characters and 1,024 UTF-8 bytes.

Scalar types are `weight`, `body_fat_percentage`, `lean_mass`, `steps`, `distance` and `active_energy`. Payload fields are `value`, `unit`, `observed_at` and `provenance`. Units are kg, %, kg, count, m and kcal respectively. Values are finite binary64 numbers; native requests already use canonical units. The existing scalar numeric domain is preserved without adding clinical ranges.

Workout type is `workout`. Payload fields are `workout_type`, `title`, `started_at`, `ended_at`, `energy_kcal`, `distance_m` and `provenance`. Type is nonempty and at most 64 characters. Title is nullable and at most 256 characters; energy and distance are nullable finite numbers. Missing optional fields normalize to null. Start may equal end; end cannot be in the future.

Scalar and workout provenance permits only nullable `source_app`, `source_device`, `source_version`, `bridge_version` and `source_modified_at`. Scalar provenance also permits paired `raw_value` and `raw_unit`; converting them with the existing unit conversions must reproduce the canonical value. Each payload is at most 32 KiB and provenance at most 16 KiB. Arbitrary vendor objects aren't accepted here.

Sleep uses `record_type: sleep_session` and the complete [sleep payload](sleep.md). Recovery uses its immutable metric as record type and the complete [recovery payload](recovery.md). HRV methods remain separate. These domains keep their existing ordered repositories rather than entering scalar reconciliation.

Timestamps require an explicit UTC offset and at most six fractional digits. They normalize to UTC with exactly six digits and `Z`. Naive dates, leap seconds, future measurements, numeric strings, booleans used as numbers, non-finite quantities, invalid Unicode, duplicate keys and unknown fields fail validation. Negative zero normalizes to zero. No Unicode normalization is applied.

## Hashes and retries

Normalize the typed payload first, then encode with RFC 8785 JCS and hash its UTF-8 bytes with SHA-256. All digests are lowercase hexadecimal. Record hash version 1 has exactly `hash_scope: health_assistant.sparse_record`, `hash_version: 1`, `domain`, `identity`, `record_type`, `operation` and `payload`. Identity contains `person_id`, canonical `provider`, `source_id` and `external_id`. Revision, ingestion bookkeeping, local exclusion and transport fields are outside the record hash.

The batch projection has exactly `hash_scope: health_assistant.sparse_batch`, `hash_version: 1`, `registration_id`, `domain`, `batch_id`, `checkpoint` and `records`. Sort records by external ID in UTF-16 code-unit order. Each reduced record contains only `external_id`, `record_type`, `operation`, `source_revision` and `payload_hash`. Verify each full record hash before constructing the reduced batch hash. The [frozen wire vectors](../tests/fixtures/native_wire_vectors.json) cover cross-language canonicalization; their illustrative identities are not enrolled native sources.

For `none`, checkpoint is null. For `opaque_cas`, it contains exactly `expected_checkpoint_id` and `checkpoint_id`. The expected handle is null only for initial state. Handles are 1 to 128 ASCII letters, digits, underscores or hyphens, and the new handle must differ. The producer must keep handles durable and never reuse them for different cursor states.

The latest batch ID and matching request hash replay with `replayed: true`, `changed: 0` and the original counts. This check happens before checkpoint comparison. Reusing that ID with different content fails. Otherwise the expected checkpoint must match before any record is written. Higher record revisions replace, equal revisions with equal hashes do nothing, lower revisions are stale, and equal revisions with different hashes roll back the whole batch. Records, projections, reconciliation, checkpoint and latest receipt commit together.

The receiver retains one receipt per sparse domain, not a history of batch requests. Older retries in `none` converge through record revisions. An old opaque checkpoint fails its compare-and-swap. Transport-only checkpoint advances, replays and stale requests don't signal new health data.

## Rearm and restore

The authenticated `health_assistant/bridge/status` command takes `registration_id` and is scoped to the bound user. It returns source lifecycle, current session and four domain tips. Each tip contains `domain`, `checkpoint_mode`, nullable `latest_batch_id`, nullable `latest_request_hash`, nullable `checkpoint_id` and `authoritative_records_present`, which includes tombstones.

Pause the producer before rearm. Call the admin command with `action: rearm` and parameters containing `owner_id` and `state`. State contains exactly `registration_id`, `receiver_session_id`, `domains` and `streams`. Domains maps each requested domain to `committed` and `pending_request`. Committed contains exactly checkpoint mode, latest batch ID, latest request hash and checkpoint ID. Pending is null or the one complete native request the producer has durably saved but not acknowledged. Streams is empty unless the wearable implementation is installed.

Exact committed tips can rearm. Fresh null tips can rearm only when no authoritative records exist. If the receiver tip equals the fully validated pending request, rearm acknowledges a lost response without applying its records again. Pending must have a distinct batch ID and follow the producer's committed checkpoint. Any other mismatch leaves all requested domains paused. A successful response supplies `write_lease` and the acknowledged domains/streams. Keep producer state durable before resuming capture.

`action: revoke` takes `registration_id`, invalidates its grants and drains the current transaction boundary. `retire` also unbinds and permanently retires the source. `remove` only removes a retired, unbound source with no records, tombstones or dependent streams. These actions never erase history.

`fresh_namespace` takes `registration_id` and explicit `capture_mode: forward_only` or `backfill`. It allocates a new source and retires the old source atomically after capacity checks. Forward-only enrollment records a durable start boundary and rejects earlier measurements; backfill is an explicit producer choice. It never adopts imported history. A producer that lost durable continuity needs this new identity, not a forced reset of the old receipt.

Every setup starts with a random in-memory session and no write leases. Neither is saved in SQLite, config entries, archives or backups. Full backups must be restored with Home Assistant stopped, followed by normal setup and explicit rearm. Hot database replacement is unsupported. A receiver can't detect source history lost from both restored sides.

## Portable history and limits

Schema 9 archives include source descriptors and scalar/workout ledgers. Claims, workouts and canonical observations are checked as redundant views, then reconstructed only from accepted ledgers. Complete graph validation and preview precede any live writes. Unknown sources import as permanently read-only history without owner bindings or receipts. Descriptor-only imports allocate nothing; conflicting immutable metadata still fails preview. Existing display labels win, with `labels_retained` reported.

Live imports suspend affected leases before applying their bounded batches. An accepted new record, higher revision or tombstone sets `needs_fresh_namespace` on an existing local enrollment. That flag persists through restart. Stale/equal content, label choices and exclusion-only changes don't set it. Scalar and workout exclusions merge with OR independently of source revision. See [portable history](interchange-format.md) for interruption and retry behavior.

Sleep bodies are capped at 8 MiB; other sparse bodies at 1 MiB. A sparse request has at most 100 records. Original bytes and nesting are bounded before full JSON parsing, with normalized limits checked again. Content encodings are rejected. Each source admits one current request and one queued request, including body reading; a third receives retryable `busy` with `Retry-After: 1`. Queued work rechecks current authentication, ownership and lease after waiting and immediately before commit.

Scalar corrections run one complete indexed ordered pass per affected metric per batch. Groups and links are staged in temporary SQLite tables, so Python memory doesn't grow with lifetime history. Runtime still grows with retained claims and nearby groups. A 100,000-claim alternating-provider fixture shifted every canonical group after deleting its first claim. On the development host, its instrumented first pass took 2.26 seconds, peaked at 22,362 traced Python bytes, used 6,373,376 temporary SQLite bytes and retained a 36,210,712-byte WAL after both passes. Process peak RSS was 236,027,904 bytes including the Home Assistant test harness.

The full 256-source fixture with 1,024 maximum-size receipts allocated 565,248 bytes for source and receipt tables, including 8,192 fixed bytes. Marginal allocation was 2,176 bytes per source, below the 4 KiB slot budget. Its whole-store backup was 737,280 bytes. These are reproducible synthetic measurements, not a cap on the complete health database or its backup and temporary space.

Diagnostics report counts and lifecycle totals. They omit source scopes, account labels, source UUIDs, payloads, receipts, bearer tokens and write leases.
