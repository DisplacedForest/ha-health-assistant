# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Manual measurement and workout forms now preserve the local time you entered when Home Assistant uses a different timezone.

- A sensor mapped to more than one metric now updates all of them. Previously, only the last mapping was used. Existing mappings keep working without any setup changes.

### Added

- Export health history to a portable archive and import it into another installation. Preview changes first, keep exclusions and source details, and retry interrupted imports without duplicating records. Environmental history and stored workout sets are included.

- Body is a new experimental view of your recorded week. Flip between front and back, open a muscle region for its workouts, and inspect body measurements through the same source details as Overview. Color follows recent recorded sets; unknown exercise names and missing detail are shown explicitly.

- The Health overview now leads with changes, keeps quieter readings compact, and shows recent workouts and source health. Open a metric to inspect its source claims or exclude and restore an incorrect reading. Comparisons explain missing history, older readings and source disagreements instead of presenting a bare number.

- You can keep room temperature, humidity and CO2 history from existing sensors. Capture is optional, stays local, and records gaps when fresh reports are missing. Five-minute history is kept for 90 days, then hourly history for two years.
- Choose a Hevy Tracker account to start keeping completed workouts and their exercise sets locally. Capture uses the latest workout exposed by the installed integration, survives restarts without duplicates, and needs no extra sign-in. History import and body-measurement export are not included.

- Setup can find your Withings and Fitbit sensors. Choose an account for each metric without picking entity IDs, see which sensors need attention, and keep manual mappings for everything else. Source choices use the same priority order as the rest of Health Assistant.

- Incorrect readings can be excluded from current values and charts, then restored. Their source history is kept, and replaying the same records does not reactivate them. The database moves to schema 5; older builds cannot open it.

- Diagnostics now show which sources are working, what they can import or export, and when an operation last succeeded. Error details stay out of the download to avoid exposing health data.

- Cross-source conflict resolution: a configurable per-metric source priority order decides the canonical current value when sources disagree, semantic duplicate matching adds a per-metric value tolerance to the merge windows, and one resolution rule serves sensors, the panel, and store queries alike. Reordering priority re-resolves from retained claims with no data loss. The database migrates to schema version 4. Multi-source installs may see contested current values shift once when priority defaults first apply.

- Source reconciliation: every incoming record is kept as a source claim, and cross-provider reports of the same physical measurement merge into one canonical observation carrying both provenances. Ambiguous near-matches are flagged as possible duplicates instead of being merged silently, a preferred source can be recorded per metric, and reconciliation is replayable with no claim ever deleted. The database migrates to schema version 3.

### Changed

- Compatibility checks now run against Home Assistant 2026.8.0 and 2026.9.1, each with its matching frontend. The minimum supported version remains 2026.8.0.

- Home Assistant 2026.8.0 or later is now required. Environmental history adds schema 6. Back up before upgrading; returning to an older integration build requires its matching database backup.

- Data sources now run on an internal provider framework with declared capabilities, per-provider sync state, and health status. Entity and manual ingestion behave exactly as before; the database migrates to schema version 2 to add provider state storage.

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
