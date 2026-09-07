# Contributing

Bug reports, source compatibility reports and focused pull requests are welcome. Use synthetic examples or remove personal details before sharing logs and health records.

## Setup

You need Python 3.14.2 or newer within Python 3.14, Node.js 22, and [mise](https://mise.jdx.dev/).

```bash
git clone https://github.com/DisplacedForest/ha-health-assistant.git
cd ha-health-assistant
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements-test.txt
```

## Running checks

The repo answers to mise tasks, and CI runs the same things:

```bash
mise run --tool node@22.23.2 check
mise run --tool node@22.23.2 ci
```

The explicit Node version keeps a global mise setting from silently selecting another version. Everything must be green before you push. These commands check the currently activated environment. The default requirements test Home Assistant 2026.9.1 with its matching frontend. CI also tests the minimum supported Home Assistant 2026.8.0 in a separate environment, and the required Test check passes only when both jobs pass.

For changes to Home Assistant APIs or dependencies, run both commands again in a minimum-version environment:

```bash
deactivate
python3.14 -m venv .venv/minimum
source .venv/minimum/bin/activate
pip install -r requirements-test-minimum.txt
mise run --tool node@22.23.2 check
mise run --tool node@22.23.2 ci
```

Keep each test harness paired with the frontend version required by that Home Assistant release. The shared requirements-test-common.txt file pins the tools used by both environments. Dependabot groups the default core harness and frontend updates and leaves the minimum requirements alone. Review their exact version pairing before merging. Do not replace the minimum environment with a newer core version when updating the default dependencies.

## Local Home Assistant instance

Unit tests are not enough; changes should be smoke-tested against a real Home Assistant. With Docker running:

```bash
mise run ha
```

This boots a disposable Home Assistant (`ghcr.io/home-assistant/home-assistant:stable`) on http://localhost:8123 with this repo's `custom_components/` mounted into its config. Configuration persists in a gitignored `.ha-dev/` directory, so onboarding only happens once; delete `.ha-dev/` for a truly clean instance.

To pick up code changes, restart the container (Ctrl+C, then `mise run ha` again). Add the integration from Settings, then Devices & services, then Add integration, then search for Health Assistant.

## Frontend

The Health panel's source lives in `frontend-src/` (Lit, bundled by esbuild). The built bundle at `custom_components/health_assistant/frontend/dist/panel.js` is committed, so installs never need Node; rebuild it whenever you change panel source and commit the result:

```bash
mise run --tool node@22.23.2 frontend-build
mise run --tool node@22.23.2 frontend-lint
mise run --tool node@22.23.2 frontend-test
mise run --tool node@22.23.2 frontend-verify
```

Lint, interaction tests, and bundle verification run as part of `mise run check` and in CI. A panel change pushed without a rebuilt, committed bundle fails the Frontend job. The panel gets data only through the integration's WebSocket commands; frontend code never imports storage internals, and everything it ships must work with no internet access (no CDN loads, no external fonts).

## Installing the dev variant into a real instance

If you run an actual Home Assistant and want the working tree installed next to a HACS-installed production copy:

```bash
mise run install-dev
```

This deploys the working tree to `$HA_CONFIG_DIR/custom_components/health_assistant_dev` (`HA_CONFIG_DIR` defaults to `~/ha`), rewritten to the domain `health_assistant_dev` and the name "Health Assistant (Dev)" so both variants coexist without colliding. The destination is replaced wholesale on every run, and Home Assistant needs a restart to pick up changes. Use a HACS or manual release install for the production copy.

## Providers

Data sources are provider adapters in `custom_components/health_assistant/providers/`. The contract is internal and may change between minor versions; there is no external plugin SDK yet.

A provider declares a stable key, a display name, and capabilities (which metrics it covers, whether it handles workouts, import vs export). It never touches SQLite or the repository directly: the only write path is the `ProviderSink` handed to it by the registry, which normalizes units, validates, stamps provenance, and stores through the canonical ingestion path. Push-style providers subscribe in `async_start`; polled providers implement `async_sync` and get a persisted state blob for their cursor, saved only after the sync batch lands. A provider that raises, hangs, or produces invalid records is marked degraded and isolated; it must never take down its siblings or the panel.

To add a provider, implement the contract and register it in the integration setup.

Sleep is a separate capability, disabled by default. Declare `sleep_sessions=True` and expose a `sleep_source_ids` frozenset for the explicitly selected accounts. Use `CandidateSleepSession` or `CandidateSleepDeletion` through `async_apply_sleep_changes`. The provider supplies stable identities and ordered revisions; the sink supplies authenticated provider ownership. See [the sleep contract](docs/sleep.md). Do not route sleep through scalar observations.

Sleep's normalization, queries and repository stay independent of Home Assistant. Its source hashes use pinned `rfc8785`, after typed normalization. The frozen JSON vectors were compared with Node's `canonicalize` implementation. The released archive fixture was exported by version 0.2.0 at commit `f15d5885cbf0601f5c8dd8f87a5a834fac9af813`, using synthetic data. Keep its bytes unchanged when extending archive readers.

Recovery follows the same revision boundary with `CandidateRecoveryObservation` and `CandidateRecoveryDeletion`. Declare `recovery_metrics` and explicitly selected `recovery_source_ids`; both default to empty. Use `async_apply_recovery_changes`, keeping HRV methods, contexts and algorithm versions separate. See [the recovery contract](docs/recovery.md). Baseline calculations belong to the shared derived layer.

## Branch and PR flow

- `main` is always releasable. All work happens on branches named like `feature/...` or `fix/...`.
- Every change merges through a pull request. Run the local checks before pushing, and wait for every required CI check.
- A reviewer who did not author the change must inspect the complete diff against its acceptance criteria and approve the exact head before merge. Changes after review need another review.
- Update documentation with the behavior it describes. Feature work is complete after merge, passing main checks and any required live verification. Releases also need every gate in [RELEASING.md](RELEASING.md).
- Use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`, and so on.
- Squash merge, then delete the branch.
- Add a CHANGELOG entry under `[Unreleased]` for anything user-facing.

## What gets a change rejected

- Failing or skipped CI.
- New behavior without tests.
- Anything that adds a cloud dependency to the core integration. Local-first is the point.
- Coupling the frontend panel to storage internals. The backend/frontend boundary is deliberate.
- Home Assistant imports inside `custom_components/health_assistant/store/`. The store is pure Python; the async boundary lives in the integration setup code.
- Code comments. The codebase ships uncommented; make the code say it instead.
- Unrelated changes bundled into the same PR.
- Public branch names, commits, pull requests or shipped files containing private tracker identifiers.
- AI attribution trailers or promotional release notes. Write what changed and what a user needs to do.

## Reporting bugs

Use the bug report template and include your Home Assistant version, the integration version, and debug logs with anything sensitive removed.

## Environmental capture

The environmental accumulator and repository live in `store/environment.py`. They stay independent of Home Assistant. `environment.py` handles filtered state reports, timers and lifecycle; `environment_options.py` owns its options step. Writes and maintenance use the same `HealthDatabase` transaction boundary as health observations and backups.

Environmental records use compact series tables, not scalar source claims. Tests cover report-based duration, gaps, partial flushes, immutable area revisions, retention, indexed queries, bounded registration and backup restore. A production storage fixture verifies the 160-byte retained-bucket and 4 KiB registered-stream budgets. Test report behavior on Home Assistant 2026.8.0 as well as the release host. Do not infer personal exposure from an area mapping or continuous sensor coverage from an unchanged state.

## Security checks

`mise run security` currently runs Semgrep with its automatic rules. It does not run a dependency audit. Review findings against the actual SQL construction and parameter binding; the current rules also flag fixed SQL fragments and internal savepoint names. Do not suppress a rule across the repository just to make the scan green. Record unresolved findings separately from the required test and CI results.
