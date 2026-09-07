# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Recovery providers can store resting heart rate, HRV SDNN, HRV RMSSD and respiratory rate with their original method and measurement window. Sources and contexts stay separate, and corrections preserve local exclusions.
- Dev installs preserve the sleep and recovery protocol namespace so their portable archives remain compatible with regular installs.
- Portable history includes recovery observations and deletion tombstones. Older archives leave existing recovery history alone.
- Sleep providers can store completed sessions, stages and reported totals without filling gaps or combining overlapping sources. Corrections preserve local exclusions, and ordered deletions prevent older records from returning. This adds the storage and read API foundation; phone connections and the Sleep panel are separate work.
- Portable history now includes sleep sessions and deletion tombstones. Archives from 0.2 still import without changing existing sleep history.

### Changed

- The database moves to schema 8. Back up before upgrading; rolling back requires matching old integration files and a schema 6 backup.

## [0.2.0] - 2026-09-06

### Added

- The Health panel now opens with changes in your record, recent workouts and source health. Open a metric to see its readings, compare sources, or exclude an incorrect reading. Missing history, older readings and disagreements get an explanation instead of a misleading comparison.
- Setup can find Withings and Fitbit accounts and map their supported metrics. Manual sensor mapping is still available. You choose which sources belong to the person in this history.
- Hevy Tracker can supply completed workouts and their available exercise sets without another sign-in. Capture starts with its latest exposed workout and builds history from there; it doesn't fetch your full Hevy history.
- Body is an experimental second view. Flip the figure front to back and open a muscle region to see its recorded sets. Color fades over seven days. Unknown exercises and missing detail stay visible, and the figure never changes shape from your measurements.
- Optional room history captures temperature, humidity and CO2 from existing sensors. Missing reports leave gaps. Five-minute records are kept for 90 days, followed by hourly records up to two years old. Environmental charts and personal exposure estimates aren't included.
- Export and import portable history archives, including source claims, exclusions, workout detail and environmental records. Imports preview changes by default, preserve existing exclusions and can be retried after an interruption. Database backups remain the way to restore an exact earlier state.
- Diagnostics show source capabilities, degraded status and the last successful operation. Health values, workout titles and raw provider errors stay out of the download.

### Changed

- Reports of the same measurement can share one canonical reading while retaining each source's evidence. Per-metric priorities decide which source supplies a contested value. Changing priorities keeps the underlying claims.
- Incorrect readings can be excluded from current values and charts, then restored. Replaying the same source records doesn't bring an excluded reading back. Exclusion keeps history; it isn't permanent erasure.
- Home Assistant 2026.8.0 or later is required. Tests cover 2026.8.0 and 2026.9.1 with their matching frontends.
- The database upgrades from schema 1 to schema 6, preserving existing history and adding source claims, priorities, exclusion state and environmental storage. Back up before upgrading. Older integration builds can't open schema 6; rolling back requires a matching older database backup. Multi-source installations may see a different current value when priorities first apply.

### Fixed

- A sensor mapped to several metrics now updates all of them.
- Manual measurement and workout forms preserve the local time you entered when Home Assistant uses a different timezone.
- Malformed text in old workout detail no longer breaks the Body view. The affected detail is marked incomplete and the stored record is kept.

## [0.1.0] - 2026-08-21

### Added

- Integration skeleton with domain `health_assistant`: config flow with a single-instance guard, minimal options flow, setup/unload/reload lifecycle, and English translations.
- On-demand database backups via the `health_assistant.create_backup` action, producing a consistent timestamped copy under `.storage/health_assistant/backups/` through SQLite's online backup API, plus hooks that checkpoint the database when a native Home Assistant backup runs.
- Redacted diagnostics built on an explicit allowlist: record counts, schema version, provider names, mapping counts, and database health are included; measurements, workout titles, and provenance payloads never are.
- Corrupt or newer-version databases fail setup with a repair issue and are left untouched; the integration never resets health data to recover itself.
- A dedicated Health sidebar panel with an overview of latest body metrics, today's activity, and the most recent workout, plus 7/30/90 day trend charts for every metric, per-value source indicators, empty-state guidance, and full offline operation. Data flows through a bounded WebSocket API with server-side downsampling.
- Summary sensors under one Health Assistant device: current weight, current body fat, steps today, active energy today, latest workout, and workouts in the last 7 days. All read from the canonical store, update immediately after ingestion, survive restarts without replay, show unknown when no data exists, and follow the configured unit system for display.
- Entity ingestion: map existing sensors to canonical metrics through the options flow; state changes are validated, unit-converted, and stored with entity provenance, and mapping changes apply without a restart.
- Manual actions `health_assistant.add_observation`, `health_assistant.add_body_measurement`, and `health_assistant.add_workout` for direct and backfill writes, idempotent when an external ID is supplied.
- Canonical local health store: a SQLite database at `.storage/health_assistant/health.sqlite` with typed observations (weight, body fat, lean mass, steps, distance, active energy) and workouts, provenance on every record, canonical units, idempotent re-ingestion, append-only schema migrations, and safe refusal to open databases from a newer version. The database survives unload, reload, and integration removal.
