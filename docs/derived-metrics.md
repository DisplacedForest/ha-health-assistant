# Daily values and personal baselines

Health Assistant computes derived values from your current local history when you ask for them. It doesn't retain a second derived table or cache old answers. A correction, exclusion, deletion or import takes effect on the next query.

These values describe your own history. They don't predict illness, diagnose a condition or measure readiness to train.

## Choosing a series

A scalar series selects one metric and its current winning provider. It reads canonical observations, so duplicate source claims aren't counted again. If reconciliation changes the winning provider, the observation moves between provider series. This doesn't retain a historical audit of previous winners.

Sleep selects one provider and account. Recovery also selects the metric, context, algorithm and algorithm version. SDNN and RMSSD stay separate, as do spot readings, sleep summaries and daily summaries. Select a series explicitly. The API never falls back to another account or method when the selection has no data.

Source descriptors show retained history separately from capture permission. `active` means the current provider declares that capture scope, not that the device has reported recently. An unrecognized capture state is `unknown`, including imported history without a matching active producer. Revoked or retired capture doesn't make retained history disappear. Selectors are display preferences, not reconciliation priorities.

## Daily selection

Calendar days use the IANA display timezone supplied with the request. This doesn't infer the source's timezone. A day includes its starting midnight and excludes the next midnight, including daylight saving changes.

| Domain | Daily representative |
| --- | --- |
| Weight, body fat and lean mass | Latest observation |
| Steps, distance and active energy | Greatest reported daily cumulative value, then latest observation |
| Recovery | Latest observation ending on that display date |
| Sleep | Longest session envelope ending on that display date, then latest end |

Ties use ascending UTF-8 external identity, so insertion order doesn't change the answer. `alternative_count` reports how many other eligible records were discarded on that date. Recovery points retain the selected record's window and revision. Scalar points retain their observation and ingestion timestamps, record identity and possible-duplicate flag.

Sleep is longest-session sleep duration, not total daily sleep. Naps aren't added to it. The selected session uses reported asleep duration, or complete derived asleep duration when available. If the longest session has incomplete coverage and no reported duration, its value stays null even when a shorter session has a known duration. Sleep is returned in seconds.

The current display day is incomplete. Its latest eligible record is shown, but that day isn't used in rolling summaries. Records timestamped after the server's pinned query time are excluded. Empty days remain null; missing data is never replaced with zero or carried forward.

## Baselines and trends

The end-date baseline uses the preceding 28 complete calendar days, excluding the end date. At least 14 days need values. Each available daily value gets equal weight. Coverage is the number of present days divided by 28.

The baseline returns the arithmetic mean and sample standard deviation, using n minus one. Deviation is the target value minus that mean. The z value divides deviation by sample standard deviation. A constant baseline still has a mean and deviation, but its z value is null. A missing target leaves deviation and z null.

Rolling summaries cover 7, 28 and 90 complete calendar days. They end after the requested end date when it is complete, or before it when it is the current day. A mean needs one present value. A trend needs three. Trend slope fits daily values against actual calendar-day offsets, preserving gaps, and is expressed in canonical units per day.

Math keeps raw precision. Round only when formatting display text. A finite arithmetic overflow returns `calculation_unavailable`. Other reasons include `no_observation`, `incomplete_sleep`, `insufficient_history`, `no_current_value` and `constant_baseline`. These are data or calculation states, not medical categories.

## Read-only WebSocket API

`health_assistant/derived_series` accepts these fields in addition to the usual `id` and `type`:

```json
{
  "domain": "recovery",
  "series_key": {
    "provider": "example",
    "source_id": "selected-account",
    "metric": "hrv_sdnn",
    "context": "sleep_summary",
    "algorithm_id": null,
    "algorithm_version": null
  },
  "end_date": "2026-09-06",
  "days": 28,
  "timezone": "America/Chicago"
}
```

The exact scalar key is `{metric, provider}`. The exact sleep key is `{provider, source_id}`. A recovery key contains all six fields shown above, including both nullable algorithm fields. Domains are `scalar`, `sleep` and `recovery`. Days must be 7, 28 or 90. Dates after today in the chosen timezone, invalid zones and unknown fields are rejected.

The result contains `calculation_version: 1`, `timezone`, server-pinned `as_of`, an opaque `snapshot_token`, `selected_series`, ascending daily `points`, `rolling` objects keyed by `7`, `28` and `90`, and the end-date `baseline`. Summary `end_date` boundaries are exclusive. Each point has `selection_rule` and `value_basis` separately. Source revisions are decimal strings.

One SQLite snapshot supplies the entire response. At most 118 calendar days are read through indexed ranges, rows are streamed, and at most 90 points are returned. The snapshot token hashes the selected normalized data and policy within that read. It isn't a persisted generation or a guarantee that separate requests share a database snapshot.

`health_assistant/derived_sources` accepts `domain`, optional `limit` (50 by default, maximum 100) and optional `cursor`. It returns `sources`, `catalog_token` and `next_cursor`. Descriptors include the exact `series_key`, `display_label`, `scope`, active/excluded counts, retained-history availability and capture state. Scalar scope is `canonical_winning_provider`; sparse scope is `source_account`. No measurements or raw provenance appear in the catalog.

Pagination pins a hash of the complete sorted descriptor catalog. A catalog change returns `stale_cursor`; begin again without the old cursor. The endpoints use the Health panel's existing read access and add no mutation operation. Existing Overview and Body screens keep their current behavior.
