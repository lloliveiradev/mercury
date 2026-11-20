# ADR-0007: Use a monorepo with uv and pnpm workspaces, a test pyramid with a recovery test, and GitHub Actions

- **Status**: Accepted
- **Date**: 2026-11-20
- **Deciders**: Leo Oliveira (owner)

## Context

The project has Python pipelines and libraries, a dbt project, a JavaScript report, a reserved Next.js app and infrastructure code. It is built by one developer who operates it. The owner prefers monorepos and reuses the repository conventions of their other projects (agent rules, ADRs, specs, hooks, CI).

A common monorepo scaffold generates a DDD layout with a bounded context per domain, which does not fit a data platform: Dagster, dbt and Evidence are not DDD services. The layout here keeps the `apps/` and `libs/` convention without per-domain layers.

Test strategy matters because the product is a set of published numbers. A bug in an analysis is not a crash; it is a wrong claim.

## Decision

**Layout.**

```
apps/pipelines   Dagster project (Python) and the dbt project
apps/report      Evidence
apps/web         Next.js (reserved)
libs/datasets    manifest and connector per source
libs/geo         spatial join and distance rules
libs/quality     reusable contracts and checks
libs/findings    statistical analysis, pure Python
configs/         shared tool configuration
tools/           repository scripts and the phase 00 spikes
infra/           docker, terraform
docs/            adr, specs, plans, design
data/            ignored by git
```

Libraries are separate packages so that they can be tested without Dagster; any app may use them.

**Tooling.** `uv` workspace for Python, `pnpm` workspace for JavaScript, Make as the entry point, lefthook for hooks, gitleaks in hooks and CI, GitHub Actions for CI. Versions are pinned in phase 01 after checking the vendors' documentation.

**Tests, from cheapest to most expensive.**

1. Unit tests of pure transformations and of the statistics (pytest).
2. Contract tests per dataset: schema, nullability, ranges.
3. Integration tests with Postgres/PostGIS and ClickHouse in containers, on tiny fixtures.
4. dbt tests and Dagster asset checks on the marts.
5. **Recovery test:** synthetic accidents, stations and weather with a known embedded effect, exercised through the real join and model. The analysis must recover the effect; unrelated series, built with the autocorrelation and seasonality of real series, must not pass as significant after multiple-comparison correction; and a deliberately wrong station assignment must visibly attenuate the estimate. Standard errors account for autocorrelation.

**Data in the repository.** No real data and no large fixtures in git: only synthetic or generated data. This avoids size and licensing questions.

**CI.** Lint, unit, integration with `docker compose` services (the same definitions as local), dbt build on fixtures, report build, gitleaks, and, on `main`, publication (ADR-0008).

## Alternatives considered

- **A DDD scaffold per domain (the usual monorepo template):** wrong shape for this project.
- **One package per source from the start:** more manifests and boilerplate than the code justifies. `libs/` stays small until reuse is real.
- **A polyrepo (pipelines, report, web):** complicates the single-command reproduction.
- **Real data samples as fixtures:** size and licence risk, and brittle tests.

## Consequences

**Positive**

- One clone, one command to reproduce.
- The recovery test protects the project's central claim: statistical honesty.
- Secrets and data hygiene are enforced by tooling, not memory.

**Negative (accepted)**

- Two workspace systems (uv and pnpm).
- Integration tests with containers are slower than unit tests.
- Synthetic fixtures do not catch every real-data quirk; phase 00 and the contract tests cover the gap.

## Failure modes and mitigations

| Failure                            | Detection                         | Mitigation                           |
| ---------------------------------- | --------------------------------- | ------------------------------------ |
| `libs/` grows without reuse        | Review at each phase close        | Flatten into `apps/pipelines`        |
| Local and CI environments diverge  | CI uses the same compose services | Single source of service definitions |
| A real credential reaches a commit | gitleaks hook and CI              | Rotate, then rewrite history         |

## Observability plan

CI duration and flaky-test tracking per job; test counts by level in the CI summary.

## Revisit triggers

- Integration tests exceed the time the owner accepts in CI: split into nightly and per-pull-request sets.
- A second deployable service appears with a different release rhythm: reconsider the repository split.
