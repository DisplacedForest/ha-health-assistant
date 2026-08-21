# Health Assistant repository rules

Home Assistant custom integration, domain `health_assistant`, distributed
through HACS. This repository is open source: no ticket keys or Linear
identifiers anywhere in git history, branch names, worktree names, pull
requests, releases, tags, source, or documentation. Conventional Commits
without issue keys.

## Delivery process

- `main` is always releasable. Development happens on `feature/...`,
  `fix/...`, or `hotfix/...` branches, one branch per ticket, one worktree
  per agent under `.worktrees/`.
- Every branch merges through a squash-merged pull request after CI passes
  and an independent adversarial review approves on the Linear ticket.
- The backend/frontend boundary is architectural: nothing under
  `custom_components/health_assistant/frontend/` reaches into storage
  internals, and persistence code never imports frontend modules.
- The core integration never requires a cloud service. A change that adds
  one is wrong by definition.

## Verification

Run before every push, from the repo root with the venv active:

- `mise run check`: format check, lint, tests.
- `mise run ci`: what GitHub Actions runs on pull requests.
- `mise run security`: semgrep plus dependency audit.

CI is the authority. Until the integration bootstrap lands there are no
GitHub Actions workflows; they arrive with the first integration code and
must include ruff, pytest with pytest-homeassistant-custom-component, HACS
validation, and hassfest.

## Completion gate

A ticket is Done only when:

- Acceptance criteria on the Linear ticket are observed to pass.
- `mise run check` is green locally and required CI checks pass on the PR.
- Config entries still set up, unload, and reload cleanly when the change
  touches integration lifecycle.
- CHANGELOG.md has an `[Unreleased]` entry for user-facing changes.
- Documentation is updated or genuinely N/A.

## Releases

- Versions follow the Linear milestones (0.1.0, 0.2.0, ...). SemVer.
- A release bumps `custom_components/health_assistant/manifest.json`,
  moves `[Unreleased]` into a dated version section in CHANGELOG.md, tags
  `vX.Y.Z`, and publishes a GitHub release with those notes. The release
  workflow enforces manifest/tag/changelog agreement.
- README badges for CI, latest release, and license stay current.
