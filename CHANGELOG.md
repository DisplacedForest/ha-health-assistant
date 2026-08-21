# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Integration skeleton with domain `health_assistant`: config flow with a single-instance guard, minimal options flow, setup/unload/reload lifecycle, diagnostics that report integration metadata only, and English translations.
- A dedicated Health sidebar panel with an overview of latest body metrics, today's activity, and the most recent workout, plus 7/30/90 day trend charts for every metric, per-value source indicators, empty-state guidance, and full offline operation. Data flows through a bounded WebSocket API with server-side downsampling.
- Summary sensors under one Health Assistant device: current weight, current body fat, steps today, active energy today, latest workout, and workouts in the last 7 days. All read from the canonical store, update immediately after ingestion, survive restarts without replay, show unknown when no data exists, and follow the configured unit system for display.
- Entity ingestion: map existing sensors to canonical metrics through the options flow; state changes are validated, unit-converted, and stored with entity provenance, and mapping changes apply without a restart.
- Manual actions `health_assistant.add_observation`, `health_assistant.add_body_measurement`, and `health_assistant.add_workout` for direct and backfill writes, idempotent when an external ID is supplied.
- Canonical local health store: a SQLite database at `.storage/health_assistant/health.sqlite` with typed observations (weight, body fat, lean mass, steps, distance, active energy) and workouts, provenance on every record, canonical units, idempotent re-ingestion, append-only schema migrations, and safe refusal to open databases from a newer version. The database survives unload, reload, and integration removal.
