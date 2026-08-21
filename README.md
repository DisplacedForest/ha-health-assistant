# Health Assistant for Home Assistant

[![License](https://img.shields.io/github/license/DisplacedForest/ha-health-assistant?style=for-the-badge)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1+-blue?style=for-the-badge&logo=home-assistant)](https://www.home-assistant.io/)

A local-first personal health platform for Home Assistant, distributed through HACS.

Health Assistant normalizes health data from the sources you already have (HA sensors, smart scales, Apple Health and Health Connect bridges, fitness services, workout integrations) into a canonical local health store. It then exposes useful entities, events, automations, trends, and a dedicated Health panel in the sidebar.

> **Status: pre-release.** The integration is under active development and is not installable yet. Watch this repo or check the releases page for the first tagged version.

---

## Why

Home Assistant already sees a surprising amount of your health data: a smart scale here, a workout integration there, maybe a sleep sensor or a HealthKit bridge. But that data lives scattered across entities, gets truncated by Recorder retention, uses inconsistent units, and has no notion of "this weight reading and that weight reading are the same measurement from two sources."

Health Assistant treats health as a first-class domain:

- **Local-first canonical storage.** Your health history lives in a local store owned by the integration. Home Assistant Recorder is not the source of truth, so your data outlives entity renames and retention windows.
- **Provider-agnostic model.** Every observation carries provenance. Data from different sources gets normalized units, deduplication, and support for corrections.
- **A real health UX.** Longitudinal health analytics don't fit well into Lovelace cards, so Health Assistant ships a dedicated Health panel.
- **HA-native automations.** Health transitions and environmental context become events and triggers you can automate on.

## Privacy

Privacy by default. Health Assistant has no cloud component and requires no external service to run. Your health data stays on your Home Assistant instance unless you explicitly connect a provider that syncs with an outside service, and even then the canonical store remains local. Export and import are yours to control.

## Architecture

The integration is a HACS custom integration with the domain `health_assistant`:

```
custom_components/health_assistant/   backend: store, ingestion, providers, entities
custom_components/health_assistant/frontend/   the dedicated Health panel
```

Backend and frontend are kept behind a deliberate boundary so the panel can evolve without coupling persistence to UI.

Core concepts:

- **Canonical store**: a local SQLite database holding normalized health observations. It lives at `.storage/health_assistant/health.sqlite` inside your Home Assistant config directory, owned entirely by the integration: Recorder never stores it, and unloading or removing the integration never deletes it.
- **Observations**: typed records (body measurements, activity, workouts, and later sleep and recovery) with units, timestamps, and provenance.
- **Providers**: adapters that ingest from or export to a source (HA entities, manual entry services, and later Hevy, smart scales, and health platform bridges).
- **Entities and events**: summary sensors and automation triggers derived from the store, never the store itself.

## Roadmap

- **0.1.0 Foundation**: canonical store, body/activity/workout observations, HA sensor and manual ingestion, basic entities, first Health panel.
- **0.2.0 Providers & Sync**: provider framework, Hevy and smart-scale paths, deduplication and provenance management, import/export.
- **0.3.0 Sleep & Recovery**: sleep sessions, resting HR, HRV, recovery metrics, Apple Health and Health Connect bridge support.
- **0.4.0 Trends & Context**: longitudinal charts, environmental correlations, comparisons, health timeline.
- **0.5.0 Automation & Platform**: health events, richer automation primitives, provider capability contracts.
- **1.0.0**: stable local health platform with polished frontend and stable provider contracts.

## Getting data in

Two paths, no vendor lock-in either way.

**Map existing sensors.** Open the integration's options (Settings, then Devices & services, then Health Assistant, then Configure) and pick the sensors that feed each metric: weight, body fat percentage, lean mass, steps, distance, and active energy. Any sensor already in Home Assistant works, whatever integration it comes from. State changes are validated, converted from the sensor's unit (or your configured unit system when the sensor doesn't declare one), and stored with the entity ID as provenance. Unknown, unavailable, or non-numeric states are never stored. Mapping changes apply immediately.

**Manual actions.** Three actions write records directly, including backfill with explicit timestamps:

```yaml
action: health_assistant.add_observation
data:
  metric: weight
  value: 180.2
  unit: lb
  observed_at: "2024-11-02T07:30:00"
  source: old spreadsheet
```

```yaml
action: health_assistant.add_workout
data:
  workout_type: running
  title: Morning run
  start: "2026-08-20T07:00:00"
  end: "2026-08-20T07:45:00"
  distance: 5
  distance_unit: km
  energy_kcal: 400
```

`health_assistant.add_body_measurement` records weight, body fat, and lean mass sharing one timestamp. Passing an `external_id` makes repeated calls idempotent, so re-running a backfill script never duplicates records.

## Entities

All entities live under a single Health Assistant device, read from the canonical store, and show unknown until data exists. Display units follow your Home Assistant unit system; stored values stay canonical.

| Entity | Meaning | Units | Updates |
| --- | --- | --- | --- |
| `sensor.health_assistant_current_weight` | Latest weight reading | kg, shown as lb on US systems | On ingestion |
| `sensor.health_assistant_current_body_fat` | Latest body fat reading | % | On ingestion |
| `sensor.health_assistant_steps_today` | Highest step count recorded today | steps | On ingestion |
| `sensor.health_assistant_active_energy_today` | Highest active energy recorded today | kcal | On ingestion |
| `sensor.health_assistant_latest_workout` | Most recent workout title or type, with start, end, and duration attributes | text | On ingestion |
| `sensor.health_assistant_workouts_last_7_days` | Workouts in the trailing 7 days | count | On ingestion |

Each measurement sensor carries `observed_at`, `provider`, and `source` attributes identifying exactly where its current value came from. Attributes never contain history; trends belong to the panel.

## Installation

Not yet. Once the first release is tagged, Health Assistant will install as a custom HACS repository, and the instructions will live here.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, testing, and the pull request flow.

## License

[MIT](LICENSE)
