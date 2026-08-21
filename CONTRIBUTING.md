# Contributing

Thanks for wanting to help. Health Assistant is early, so the fastest way to contribute right now is opening issues with real-world health data scenarios you want supported.

## Setup

You need Python 3.13+ and [mise](https://mise.jdx.dev/).

```bash
git clone https://github.com/DisplacedForest/ha-health-assistant.git
cd ha-health-assistant
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-test.txt
```

## Running checks

The repo answers to mise tasks, and CI runs the same things:

```bash
mise run check      # format, lint, test
mise run ci         # exactly what GitHub Actions runs
```

Everything must be green before you push.

## Local Home Assistant instance

Unit tests are not enough; changes should be smoke-tested against a real Home Assistant. With Docker running:

```bash
mise run ha
```

This boots a disposable Home Assistant (`ghcr.io/home-assistant/home-assistant:stable`) on http://localhost:8123 with this repo's `custom_components/` mounted into its config. Configuration persists in a gitignored `.ha-dev/` directory, so onboarding only happens once; delete `.ha-dev/` for a truly clean instance.

To pick up code changes, restart the container (Ctrl+C, then `mise run ha` again). Add the integration from Settings, then Devices & services, then Add integration, then search for Health Assistant.

## Branch and PR flow

- `main` is always releasable. All work happens on branches named like `feature/...` or `fix/...`.
- Every change merges through a pull request, and required CI checks must pass.
- Use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`, and so on.
- Squash merge, then delete the branch.
- Add a CHANGELOG entry under `[Unreleased]` for anything user-facing.

## What gets a change rejected

- Failing or skipped CI.
- New behavior without tests.
- Anything that adds a cloud dependency to the core integration. Local-first is the point.
- Coupling the frontend panel to storage internals. The backend/frontend boundary is deliberate.
- Code comments. The codebase ships uncommented; make the code say it instead.
- Unrelated changes bundled into the same PR.

## Reporting bugs

Use the bug report template and include your Home Assistant version, the integration version, and debug logs with anything sensitive removed.
