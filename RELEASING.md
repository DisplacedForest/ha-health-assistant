# Releasing

Every release runs the same gate. Nothing gets tagged until each box is checked
on the local dev Home Assistant instance.

## Pre-flight

- [ ] `mise run check` is green locally.
- [ ] CI and Validate workflows are green on `main`.
- [ ] `manifest.json` version, the changelog section, and the tag you are about
      to create all agree.
- [ ] The changelog's Unreleased entries have moved into a dated section for
      this version.

## Install gate

- [ ] Clean manual install: copy `custom_components/health_assistant` into a
      dev instance that has never run it, restart, add the integration, confirm
      setup completes and the database is created.
- [ ] Upgrade rehearsal: install this build over the previous dev build with
      existing data, restart, confirm setup completes and existing data is
      intact.
- [ ] Config entry lifecycle: unload, reload, and remove/re-add the entry
      without errors, with data surviving each step.

## Behavior gate

- [ ] Entities: summary sensors exist under one device, show real values after
      ingestion, and show unknown on a fresh install.
- [ ] Panel: the Health sidebar entry renders the overview and trends against
      live data.
- [ ] Entity ingestion: a mapped sensor's state change lands in the store with
      entity provenance.
- [ ] Manual ingestion: `add_observation`, `add_body_measurement`, and
      `add_workout` write records and are idempotent with an `external_id`.
- [ ] Backup round trip: `create_backup` produces a file, and the documented
      restore procedure brings the instance back to the backed-up state.
- [ ] Diagnostics download contains counts and status only, no health values.

## Ship

- [ ] Tag `v<version>` on `main` and push the tag.
- [ ] Publish the GitHub release with notes from the changelog section.
- [ ] Confirm README badges (CI, release, license) resolve against the new
      release.
