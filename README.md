# Mercury

Mercury aligns heterogeneous open Brazilian datasets on a common municipality-and-time spine and publishes reproducible findings, with every architecture decision documented and measured.

> **Status: design phase.** The repository holds the design, the decisions and the tooling baseline. The product code arrives phase by phase; nothing described below is implemented yet.

## The question it starts with

> Does rain increase road accidents on federal highways, and by how much, after controlling for hour of day, weekday, holidays and the seasonal pattern of each location?

It is a small question on purpose. Answering it well needs the hard parts of a data platform: sources with different grains and drifting formats, a spatial join from weather stations to municipalities, quality gates, and an analysis that does not fool itself with seasonal correlation.

## How it is built

```
 IBGE ─┐
 PRF  ─┼─► raw ─► staging ─► conformed ─► marts ─► findings ─► snapshot ─► static report
 INMET ┘  Parquet           Postgres      ClickHouse                        (Evidence)
          (S3 API)          + PostGIS     (dbt models)
                        orchestrated by Dagster
```

- **An S3-compatible object store** for raw files (as received, immutable) and staging data (typed Parquet): partitioned and reprocessable.
- **PostgreSQL with PostGIS** for the dimensions and the spatial join.
- **ClickHouse** for hourly facts, marts and findings.
- **Python** for ingestion and statistics, **dbt** for the marts, **Dagster** for orchestration.
- **Evidence** for a static report built from a snapshot; a Next.js app for exploration comes later.
- **Terraform** for the static site on S3 and CloudFront, published with GitHub OIDC.

The reasons, the alternatives and the revisit triggers for each choice are in the [architecture decision records](docs/adr/).

## What makes the analysis defensible

- Association is never presented as causation.
- Weather effects are estimated with controls for hour, weekday, holidays and each location's seasonal pattern, with uncertainty that accounts for autocorrelation.
- Multiple comparisons are corrected, and the number of hypotheses tried is reported.
- Every analysis has a recovery test: a synthetic dataset with a known effect must be recovered, and unrelated series must not pass as significant.
- Coverage limits (federal highways only, stations only where they exist) are stated in every report.

## Repository layout

```
apps/      deployable pieces: pipelines, report, and later a web app
libs/      shared libraries: datasets, geo, quality, findings
infra/     local stack (docker) and cloud (terraform)
docs/      brief, architecture, ADRs, specs, plans
data/      local data, ignored by git
configs/   shared tool configuration
tools/     repository scripts and the phase 00 spikes
```

The folders under `apps/` and `libs/` appear with the phase that creates them; see [`docs/specs/`](docs/specs/README.md).

## Documentation

| Read                                           | To learn                                        |
| ---------------------------------------------- | ----------------------------------------------- |
| [`docs/design/brief.md`](docs/design/brief.md) | Scope, MVP cut, risks and decisions at a glance |
| [`docs/architecture.md`](docs/architecture.md) | How the system is structured                    |
| [`docs/adr/`](docs/adr/)                       | Why each structural decision was made           |
| [`docs/roadmap.md`](docs/roadmap.md)           | What is done and what comes next                |
| [`CONTRIBUTING.md`](CONTRIBUTING.md)           | Setup, branches, commits and pull requests      |

## Data and terms

Mercury uses open public data only and never stores personal data. Each source's terms and retrieval date are recorded in its manifest. No data is committed to this repository.

## Licence

[MIT](LICENSE)
