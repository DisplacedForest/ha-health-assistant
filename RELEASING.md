# Releasing

A release corresponds to one project milestone. Record the exact candidate commit, runtime versions and observed results in the release ticket. Use disposable Home Assistant configurations and synthetic records. Keep credentials out of logs and screenshots. Nothing gets tagged before the candidate passes its install and behavior gates and the merged main checks pass.

## Pre-flight

- [ ] All work scoped to the release is complete, with documentation updated.
- [ ] `mise run check` and `mise run ci` pass in both pinned environments from CONTRIBUTING, using Node 22.
- [ ] The full release diff has independent approval at its exact head.
- [ ] Every required pull request check passes, followed by CI and Validate on the merged main commit.
- [ ] Main requires Format, Lint, Test, Frontend, Validate with HACS Action and Validate with Hassfest, including enforcement for admins.
- [ ] The manifest version, dated changelog section and intended tag agree. Unreleased entries have moved into that dated section.
- [ ] README setup, source limits, upgrade instructions and screenshots match the installed candidate. Screenshots use synthetic data.
- [ ] Record the result and coverage of `mise run security` separately. Do not describe a failed scan or a missing dependency audit as passing.

## Install gate

Use the current stable Home Assistant for a fresh install and the declared minimum, 2026.8.0, for an upgrade rehearsal. Record the actual image versions and digests.

- [ ] Clean manual install: copy `custom_components/health_assistant` into a configuration that has never run it, restart, add the integration and confirm the database is created at the expected schema.
- [ ] Upgrade from the previous release with known readings, workouts and mappings. Back up first, install the candidate and restart. Confirm setup completes, the schema migrates and the existing data and mappings survive.
- [ ] Unload, reload and remove/re-add the config entry without errors or lost history.

## Behavior gate

- [ ] Six summary sensors share one device, show unknown on a fresh install and show expected values after ingestion.
- [ ] Overview, Trends and the opt-in Body view render live data. Check source detail, workout detail, keyboard navigation, narrow screens and light and dark themes.
- [ ] A mapped sensor's state change lands with entity provenance. Source setup shows only compatible accounts and metrics. Record which vendor contracts were exercised with fixtures and which were tested against real accounts.
- [ ] `add_observation`, `add_body_measurement` and `add_workout` write records and are idempotent with an `external_id`.
- [ ] Exclude a reading, replay its source record, confirm it stays excluded, then restore it.
- [ ] Environmental capture keeps area identity, accepts fresh identical reports, stops coverage at unavailable states and does not replay a current state on startup. Unload/reload stops and resumes listeners without duplicate samples. Check the minimum runtime as well as stable.
- [ ] Export all eight archive domains, including sleep sessions and tombstones. Import an actual format 1 archive from 0.2 and verify that existing sleep history is untouched. Default import is a dry run that leaves the destination unchanged. Apply it, check claims, exclusions, workouts and room history, then repeat without duplicates. Keep interrupted-import and conflicting-history regression results with the evidence.
- [ ] `create_backup` produces a consistent file. Add a later record, follow the README restore procedure and confirm the later record is gone while the backed-up records remain.
- [ ] A synthetic sleep provider stores summary-only and stage-rich sessions, corrects them at higher revisions and retains local exclusions. Verify ordered deletion, stale replay, source-account error isolation, bounded list/detail cursors, admin-only exclusion, and unload/reload persistence on stable and minimum Home Assistant. Keep fixture evidence separate from real source qualification.
- [ ] A downloaded diagnostic contains counts and status without health values, titles, source payloads or credentials.

When inspecting a running database in Docker, run SQLite inside that container. Do not open the live bind-mounted file with host SQLite. Stop Home Assistant before replacing its database and remove the old WAL and SHM files as described in README.

## Ship and verify

- [ ] Tag `v<version>` on the verified main commit with an annotated tag and push it.
- [ ] Publish a GitHub release with plain notes from the changelog and an installable archive containing `custom_components/health_assistant`. Confirm the archive includes the tracked panel bundle and matching manifest version.
- [ ] Download the published artifact into another fresh configuration, install it, restart, add the integration and verify the version, summary sensors and panel.
- [ ] Confirm README CI, latest-release and license badges resolve.
- [ ] Report HACS availability accurately. Custom-repository use does not mean default-store inclusion. Submit to the default store only when the published integration meets its branding and validation requirements.
- [ ] Record the release URL, tag commit, artifact checksum and published-install results. Finish the release ticket and milestone, then remove completed worktrees, branches and disposable instances.
