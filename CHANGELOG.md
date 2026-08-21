# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Integration skeleton with domain `health_assistant`: config flow with a single-instance guard, minimal options flow, setup/unload/reload lifecycle, diagnostics that report integration metadata only, and English translations.
- Canonical local health store: a SQLite database at `.storage/health_assistant/health.sqlite` with typed observations (weight, body fat, lean mass, steps, distance, active energy) and workouts, provenance on every record, canonical units, idempotent re-ingestion, append-only schema migrations, and safe refusal to open databases from a newer version. The database survives unload, reload, and integration removal.
