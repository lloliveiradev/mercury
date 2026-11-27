# Architecture decision records

One decision per file, numbered in the order it was made. An accepted ADR is never edited to change its decision: a new ADR supersedes it and both link to each other. Typos may be fixed.

Each ADR has: context, decision, alternatives considered, consequences (including the accepted costs), failure modes, an observability plan and revisit triggers.

| ADR                                                       | Decision                                                                 | Status                                      |
| --------------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------- |
| [0001](0001-mvp-scope-and-datasets.md)                    | IBGE spine, PRF accidents and INMET weather for Brazil, 2022–2025        | Accepted                                    |
| [0002](0002-layered-storage.md)                           | Parquet, then Postgres with PostGIS, then ClickHouse                     | Accepted                                    |
| [0003](0003-clickhouse-analytical-engine.md)              | Keep ClickHouse, with a benchmark that compares the alternatives         | Accepted                                    |
| [0004](0004-python-and-hybrid-transformation.md)          | Python; SQL files; dbt for marts; an ORM only for control tables         | Accepted                                    |
| [0005](0005-dagster-orchestrator.md)                      | Orchestrate with Dagster                                                 | Accepted                                    |
| [0006](0006-evidence-publication-web-app-deferred.md)     | Evidence from a snapshot now; defer the Next.js web app                  | Accepted                                    |
| [0007](0007-monorepo-layout-testing-ci.md)                | Monorepo, uv and pnpm, test pyramid with a recovery test, GitHub Actions | Accepted                                    |
| [0008](0008-aws-static-publication-and-local-emulator.md) | Static site on AWS through Terraform; AWS Emulator as the local stand-in | Accepted; local stand-in superseded by 0010 |
| [0010](0010-seaweedfs-local-object-store.md)              | SeaweedFS as the local S3-compatible store                               | Accepted                                    |

Number 0009 is reserved for the analysis design, due before the phase 05 spec.
