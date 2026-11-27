# Phase 01: Walking skeleton

- **Status:** ready (starts after phase 00)
- **Depends on:** 00
- **Briefs and ADRs:** [ADR-0002](../adr/0002-layered-storage.md), [ADR-0004](../adr/0004-python-and-hybrid-transformation.md), [ADR-0005](../adr/0005-dagster-orchestrator.md), [ADR-0007](../adr/0007-monorepo-layout-testing-ci.md), [ADR-0008](../adr/0008-aws-static-publication-and-local-emulator.md), [ADR-0010](../adr/0010-seaweedfs-local-object-store.md)

## Goal

An empty pipeline runs end to end through the real tooling, locally and in CI, before any dataset exists. Infrastructure problems surface now, when they are cheap.

## Scope

1. **Toolchain pinned** after checking the vendors' documentation: Python with `uv`, Node with `pnpm`, and the versions recorded in the repository. `CONTRIBUTING.md` is updated.
2. **Local stack in one command** (`make up`, `make down`, `make bootstrap`): PostgreSQL with PostGIS, ClickHouse, SeaweedFS as the S3-compatible store ([ADR-0010](../adr/0010-seaweedfs-local-object-store.md)), and Dagster (webserver, daemon and its metadata database). Health checks on every service. Service definitions are the single source for local and CI.
3. **One trivial asset round trip:** a Dagster asset writes a small Parquet file to the S3-compatible store, a second asset loads it into Postgres, a third loads it into ClickHouse, and a test queries all three and checks the counts. Synthetic data only.
4. **Control tables:** one SQLAlchemy model and one Alembic migration for a `dataset_run` table; the migration runs from `make`, and a test applies it to a clean database.
5. **Checks wired:** one asset check on the trivial asset, and one dbt model with one test, run through Dagster.
6. **CI:** jobs for lint (ruff and a type checker), unit tests (pytest), integration tests using the `docker compose` services from the same definitions, dbt build on fixtures, gitleaks and formatting. The workflow is green on `main`.
7. **Report shell:** an empty Evidence project that builds in CI.
8. **Terraform shell:** `infra/terraform` with provider, backend placeholder and an empty module layout that passes `terraform validate`. No apply.
9. **Hooks:** lefthook gains ruff and the type checker.
10. **Defaults decided:** `make down` keeps the volumes and a separate `make clean` removes them; Alembic owns all Postgres DDL and versioned SQL files own the ClickHouse DDL; Terraform uses a local backend until phase 08; Dagster runs at most one run per partition at a time.

## Out of scope

- Any real dataset, geography or statistics.
- A real Terraform apply and any cloud resource.
- The web app.

## Rules

- Secrets: only `.env.example` with placeholder values is committed; real values come from the local environment.
- Container ports are bound to `127.0.0.1`, never to all interfaces.
- No `latest` image tags; pin images after checking the vendors' documentation. The AWS Emulator is not part of this stack (ADR-0010). If a later phase adds it, it is the one exception: AWS publishes no image and serves the package only from `LTS/latest` (a versioned URL answered HTTP 403 on 2026-11-26), so its version cannot be pinned. Build it from its documented Dockerfile, keep the package signature check, and record the installed version with any result that depends on it.
- Every Makefile target has a `## comment` and appears in `make help`.
- Update `architecture.md` for what became real, and `CONTRIBUTING.md` for the new setup.

## Acceptance criteria

```bash
make bootstrap          # from a clean clone: installs, starts the stack, healthy
make test               # unit and integration tests pass
make down && make up    # state survives a restart and the trivial assets rerun cleanly
make docs-check
make scan-secrets
```

- The trivial round trip passes in CI and locally with identical results.
- Re-materializing the trivial assets twice leaves the same counts (idempotent).
- A new contributor can follow `CONTRIBUTING.md` and reach a green `make test` without asking.

## Pre-mortem

- **Repeats:** re-run an asset partition, restart a container mid-run, run migrations twice; counts and schema must not change.
- **Concurrency:** two materializations of the same partition; the loader replaces the partition atomically, it does not append.
- **Config defaults:** read every default from the images and tools actually used (ports, credentials, retention); do not assume them.
- **Side effects before and after load:** a failed ClickHouse load must not leave Postgres claiming success; the control table records the outcome last.
- **Differences between local and CI:** same compose definitions, different resources; flag any timing assumption.
- **What the phase removes:** the placeholder hygiene-only CI is replaced by the full pipeline, and `make` gains targets; nothing else is removed.
