# Delivery contract

Read [CONTRIBUTING.md](CONTRIBUTING.md) before changing code and [RELEASING.md](RELEASING.md) before preparing a release.

## Work and review

Work from a ready ticket with an objective, acceptance criteria, testing strategy, owner and release scope. Keep the spec, implementation plan and durable architecture decisions in the project tracker. Use one ticket, branch and dedicated worktree per agent. Record the branch, worktree, expected files and dependencies in the ticket plan before implementation.

Use lowercase branches such as `feature/...` or `fix/...`. Worktrees belong under `.worktrees/`. This repository is public: private tracker identifiers stay out of branch names, commits, pull requests, tags and shipped files. Source ships without comments or docstrings. Do not use em dashes or AI attribution trailers.

Run `mise run check` and `mise run ci` before pushing. Follow CONTRIBUTING for the pinned Python environments and explicit Node 22 override. Releases and changes to Home Assistant APIs or test dependencies must pass both the stable and minimum environments. Rebuild and commit the panel bundle whenever its source changes.

Every change needs a pull request. Required checks are Format, Lint, Test, Frontend, Validate with HACS Action and Validate with Hassfest. The aggregate Test check must include passing minimum and stable jobs. Do not accept a skipped or canceled required job as success.

An independent reviewer with fresh context must inspect the full diff at its exact head against the acceptance criteria and post an APPROVE or REQUEST CHANGES verdict on the ticket. Address findings, rerun affected checks and obtain approval on the resulting head before merging. Squash merge with a descriptive Conventional Commit message, then delete the branch.

## Completion gate

A feature ticket is Done only after its approved change is merged, CI and Validate pass on that main commit, documentation matches the implementation, and the ticket's required live checks have observed results. Record the pull request, commit, checks, known limitations and live evidence on the ticket. Remove the completed worktree and local branch after confirming they contain no uncommitted work.

A release ticket has the additional gate in RELEASING: clean and upgrade installs, lifecycle and feature checks, backup restore, publication, and installation of the published artifact. Finish the release milestone only after those checks pass. HACS default-store acceptance is a separate external process; do not claim it from custom-repository installation or validation alone.
