# Contributing to Mercury

Mercury is a Python and TypeScript monorepo for a data platform: `apps/` holds the deployable pieces (pipelines, report, and later a web app) and `libs/` holds the shared libraries. The task runner is Make. Day-to-day rules for people and coding agents live in [`AGENTS.md`](AGENTS.md). This guide is the contributor path: setup, branches, commits, pull requests and how to check your work.

The project is in its design phase: the repository holds documentation and tooling, and the code arrives phase by phase ([`docs/specs/README.md`](docs/specs/README.md)).

## Prerequisites

Today, for hooks and documentation checks:

- Node.js (for `npx prettier`)
- `lefthook` and `gitleaks` (`brew install lefthook gitleaks`)

Phase 01 adds the pinned toolchain: Docker with Compose, `uv` for Python and `pnpm` for JavaScript. This file is updated in that phase.

## Setup

```bash
make install-hooks
make help
```

## Branch naming

Branch from `main`. Never commit on `main`.

- Phase work uses `phase/<NN>-<slug>`, one pull request per phase, as [`docs/specs/README.md`](docs/specs/README.md) describes.
- Every other branch is `<type>/<short-description>` in lowercase kebab-case, where `<type>` is a [Conventional Commits](https://www.conventionalcommits.org/) type: `docs/adr-numbering`, `fix/station-join`.

## Commits

Commit subjects are English and follow Conventional Commits. Lefthook rejects anything else:

```text
type(scope): subject
```

`type` is one of `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `build`, `ci`, `perf`, `style`, `revert`. `scope` is optional (`pipelines`, `geo`, `report`, `repo`). A breaking change may use `type(scope)!: subject`. The subject is at least three characters.

On every commit, Lefthook runs Prettier on staged Markdown, YAML, JSON and web files, gitleaks (when installed) and the Conventional Commits check. Do not skip hooks with `--no-verify` unless the owner asks.

Check the commit author before the first commit: the address in `git config user.email` becomes public history. Use an address you are willing to publish, for example the GitHub no-reply address. The pre-commit hook refuses a commit when no repository-local author is set, so a global address is never used by accident.

## Pull requests

Open the pull request against `main` with the template in [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md), fill every section, and keep it English. Never force-push and never merge your own pull request: the owner reviews and merges.

## Verify before you finish

```bash
make docs-check
make scan-secrets
```

Test and pipeline targets are added by the phase that creates them.

## Conduct and security

Everyone follows the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities privately, as [`SECURITY.md`](SECURITY.md) describes.
