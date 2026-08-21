# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Source reconciliation: every incoming record is kept as a source claim, and cross-provider reports of the same physical measurement merge into one canonical observation carrying both provenances. Ambiguous near-matches are flagged as possible duplicates instead of being merged silently, a preferred source can be recorded per metric, and reconciliation is replayable with no claim ever deleted. The database migrates to schema version 3.

### Changed

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
