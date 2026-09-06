# Health Assistant for Home Assistant

[![CI](https://img.shields.io/github/actions/workflow/status/DisplacedForest/ha-health-assistant/ci.yml?branch=main&style=for-the-badge&label=CI)](https://github.com/DisplacedForest/ha-health-assistant/actions/workflows/ci.yml)
[![GitHub Release](https://img.shields.io/github/release/DisplacedForest/ha-health-assistant.svg?style=for-the-badge&color=brightgreen)](https://github.com/DisplacedForest/ha-health-assistant/releases)
[![Stars](https://img.shields.io/github/stars/DisplacedForest/ha-health-assistant?style=for-the-badge)](https://github.com/DisplacedForest/ha-health-assistant/stargazers)
[![Last Commit](https://img.shields.io/github/last-commit/DisplacedForest/ha-health-assistant?style=for-the-badge)](https://github.com/DisplacedForest/ha-health-assistant/commits/main)
[![License](https://img.shields.io/github/license/DisplacedForest/ha-health-assistant?style=for-the-badge)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1+-blue?style=for-the-badge&logo=home-assistant)](https://www.home-assistant.io/)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/o7triud67l)

A local-first personal health platform for Home Assistant.

Health Assistant normalizes health data from the sources you already have (HA sensors, smart scales, Apple Health and Health Connect bridges, fitness services, workout integrations) into a canonical local health store. It then exposes useful entities, events, automations, trends, and a dedicated Health panel in the sidebar.

> **Status: early.** 0.1.x installs manually or as a custom HACS repository. Publication to the HACS default store is planned for 0.2.0 or later.

---

## Why

Home Assistant already sees a surprising amount of your health data: a smart scale here, a workout integration there, maybe a sleep sensor or a HealthKit bridge. But that data lives scattered across entities, gets truncated by Recorder retention, uses inconsistent units, and has no notion of "this weight reading and that weight reading are the same measurement from two sources."

Health Assistant treats health as a first-class domain:

- **Local-first canonical storage.** Your health history lives in a local store owned by the integration. Home Assistant Recorder is not the source of truth, so your data outlives entity renames and retention windows.
- **Provider-agnostic model.** Every observation carries provenance. Data from different sources gets normalized units, deduplication, and support for corrections.
- **A real health UX.** Longitudinal health analytics don't fit well into Lovelace cards, so Health Assistant ships a dedicated Health panel.
- **HA-native automations.** Health transitions and environmental context become events and triggers you can automate on.

## Privacy

Privacy by default. Health Assistant has no cloud component and requires no external service to run.

What is stored, and where:

- All health data lives in a single SQLite database at `.storage/health_assistant/health.sqlite` inside your Home Assistant config directory.
- Each record holds the metric, value, unit, timestamp, person identifier, and provenance (which sensor or action produced it). Workouts additionally hold type, optional title, start, end, energy, and distance. Since schema version 3 the database also keeps a source-claims table (the per-provider evidence behind each canonical observation) and a per-metric preferred-source table; both live in the same local file.
- Backups you create land beside it under `.storage/health_assistant/backups/`.
- Your entity-to-metric mappings live in the config entry options, in HA's normal storage.

What Health Assistant never does:

- It never sends your health data anywhere. There are no outbound connections, no telemetry, no analytics. Data only leaves your instance if you explicitly connect a future provider that syncs with an outside service, and even then the canonical store stays local.
- Diagnostics downloads include record counts, schema version, provider keys and capabilities, mapping counts, and database health. Provider status includes whether it is degraded and when an operation last succeeded. That timestamp is not the time of the latest measurement. Status starts fresh when the integration reloads. A previous failure appears as `provider_error`, even after recovery; the degraded flag tells you whether the provider has recovered. Raw errors, measurements, workout titles, provider cursors, and provenance payloads are excluded.
- Uninstalling the integration never deletes your database.

## Which source wins

When more than one source reports the same metric, one documented rule decides the canonical value, and every surface (sensors, the panel, store queries) uses it.

- Each metric has a source priority order. It starts from sensible defaults (sources are added to the order as they register, in setup order) and you can reorder it; the order lives in the local database alongside your data.
- Two providers reporting the same physical measurement (inside a per-metric time window and value tolerance: for body measurements, 2 minutes and 0.5 kg or 1 percent, whichever is looser) collapse into one canonical observation that keeps both provenances. The highest-priority source supplies the value.
- Readings inside the time window but outside the value tolerance are genuinely different: both records stay, both are flagged as possible duplicates, and the current value comes from the highest-priority source among the records contesting the newest timestamp. Ties break by newest observation, then stable record id.
- Outside the contested window, normal time-series behavior applies: the newest observation is the current value regardless of priority.
- Reordering priority never deletes anything. Alternate claims are retained and the canonical values re-derive from them.

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
- **Source claims and reconciliation**: every incoming record is kept as a source claim, and canonical observations are derived from claims. When two providers report the same physical measurement close together in time (a weigh-in arriving both from the scale integration and a health platform bridge), the claims merge under one canonical observation carrying both provenances; the merge windows are conservative, per metric class, and same-provider records never merge. Near-misses that fall inside a wider suspicious window are never merged silently: both records stay separate and carry a possible-duplicate flag you can see in the panel data. No claim is ever deleted by reconciliation, so the process is replayable.
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

## The Health panel

Configuring Health Assistant adds a Health entry to the sidebar, no manual resource registration needed. The panel is a real application view over the canonical store, served entirely from your instance and fully functional offline:

- **Overview**: latest body metrics, today's activity, and the most recent workout, each with a source line showing exactly which provider and sensor produced the value.
- **Trends**: weight, body fat, lean mass, steps, distance, and active energy over 7, 30, or 90 days, drawn as lightweight SVG charts.
- Values display in your configured unit system; empty states point you at entity mapping and the manual actions.

Data reaches the panel through a dedicated WebSocket API with bounded queries and server-side downsampling. The frontend never touches the database, and the backend never renders.

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

Health Assistant is not in the HACS default store yet; that's planned for 0.2.0 or later, after the provider framework lands. For 0.1.x, install it one of two ways.

**As a custom HACS repository (recommended):**

1. In HACS, open the three-dot menu and pick Custom repositories.
2. Add `https://github.com/DisplacedForest/ha-health-assistant` with type Integration.
3. Find Health Assistant in HACS, install it, and restart Home Assistant.

**Manually:**

1. Download the latest release from the [releases page](https://github.com/DisplacedForest/ha-health-assistant/releases).
2. Copy `custom_components/health_assistant` into your config directory's `custom_components` folder.
3. Restart Home Assistant.

Either way, finish by adding the integration: Settings, then Devices & services, then Add integration, then Health Assistant.

## Backup and restore

Your health history deserves disaster recovery from day one, so 0.1 ships both paths.

**Home Assistant backups** already cover you: the database lives in `.storage`, and Health Assistant checkpoints it when a native HA backup starts, so full and partial backups contain a consistent copy.

**On-demand backups** come from the `health_assistant.create_backup` action. It uses SQLite's online backup API, so the copy is consistent even while data is being ingested, and writes a timestamped file under `.storage/health_assistant/backups/`. Call it from Developer tools, an automation, or a schedule. The action returns the path it wrote.

**To restore:**

1. Stop Home Assistant (or unload the Health Assistant config entry from Settings, then Devices & services).
2. In `.storage/health_assistant/`, delete `health.sqlite-wal` and `health.sqlite-shm` if they exist.
3. Copy the backup file over `.storage/health_assistant/health.sqlite`.
4. Start Home Assistant (or reload the entry). The restored data appears immediately.

If the database ever fails to open (corruption, or a file written by a newer version), Health Assistant refuses to start, raises a repair issue explaining what happened, and leaves the file exactly as it found it. It never resets your data to recover itself.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, testing, and the pull request flow.

## License

[MIT](LICENSE)
