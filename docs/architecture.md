# Architecture

This document describes Mercury as designed. Nothing is implemented yet: each part is marked with the phase that delivers it. The reasons for each choice are in [`adr/`](adr/); the scope is in [`design/brief.md`](design/brief.md).

## Data flow

```
 public sources                                                              consumers
 ──────────────                                                              ─────────
 IBGE (spine)  ─┐
 PRF accidents ─┼─► raw ─► staging ─► conformed ─► facts + marts ─► findings ─► snapshot ─► Evidence report
 INMET weather ─┘   │        │           │             │               │                    (static site)
                    │        │           │             │               └──► [later] Next.js web app
   object store ────┘        │           │             └─ ClickHouse (load assets, dbt models)
   (S3 API)                  │           └─ Postgres + PostGIS (dimensions, station mapping)
   files as received         │              and conformed fact files (Parquet)
                             └─ typed and cleaned Parquet
```

Dagster orchestrates every step as a partitioned asset, with quality checks next to the asset they protect.

## Zones and ownership

Each store has one role, and **every table or dataset has exactly one writer**. Other components read through the stores' interfaces and never write into something they do not own.

| Zone                   | Store                              | Holds                                                                                                        | Written by                          | Phase  |
| ---------------------- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------ | ----------------------------------- | ------ |
| raw                    | Object store (S3 API)              | Each source file exactly as received, immutable and checksummed, landed per retrieval date                   | ingestion assets (Python)           | 03–04  |
| staging                | Object store, Parquet              | Typed, cleaned data, one schema per source and year, validated by a contract; partitioned by source and year | staging assets (Python)             | 03–04  |
| conformed (dimensions) | Postgres + PostGIS                 | Municipality and time dimensions, station-to-municipality mapping                                            | conformance assets (Python and SQL) | 02, 05 |
| conformed (facts)      | Object store, Parquet              | Facts keyed by the spine, ready to load                                                                      | conformance assets (Python)         | 05     |
| facts                  | ClickHouse                         | The conformed facts as loaded                                                                                | load assets (Python client)         | 05–06  |
| marts                  | ClickHouse                         | Aggregated, modelled tables for one question each                                                            | dbt models, run by Dagster          | 06     |
| findings               | ClickHouse, and a Parquet snapshot | Effect estimates with intervals, tests and their metadata                                                    | analysis assets (Python)            | 07     |
| control                | Postgres                           | Ingestion runs, dataset catalogue, quality results                                                           | the pipelines (SQLAlchemy, Alembic) | 01     |

Dagster keeps its own metadata in a separate database inside the local Postgres instance. It is not a Mercury zone, and it is not a source of truth: every asset can be rebuilt from raw.

DDL ownership: Alembic owns all Postgres DDL, versioned SQL files own the ClickHouse tables that load assets fill, and dbt owns the models it creates.

## Alignment of sources (open parameters are decided in ADR-0009)

The join of weather to accidents is the core engineering problem, and the one most able to bias a result silently. The design constraints are:

- **Where the weather of an accident comes from.** Preferably the nearest station to the accident's coordinates within a distance limit, if phase 00 confirms coordinates. A municipality reference point is only a fallback. The municipality remains the reporting dimension.
- **One time zone.** INMET states that its station data is in UTC. PRF times are local, and Brazil spans several offsets. Every timestamp is converted by a stated rule before any join, and the conversion has tests. Yearly partitions are by the zone chosen for the analysis, so a local-time year may need data from two INMET files.
- **Municipality keys.** PRF may give the municipality as a name. Names are matched to IBGE codes by a stated rule, and a quality check reports the unmatched share.
- **Coverage.** Municipalities and hours without a close station are flagged, not guessed, and reports state the coverage.

## Components

| Component         | Role                                                       | Where             | Phase |
| ----------------- | ---------------------------------------------------------- | ----------------- | ----- |
| Pipelines         | Dagster project (Python) and the dbt project of the marts  | `apps/pipelines`  | 01    |
| Dataset libraries | Manifest and connector per source                          | `libs/datasets`   | 03–04 |
| Geo library       | Spatial join and distance rules                            | `libs/geo`        | 05    |
| Quality library   | Reusable contracts and checks                              | `libs/quality`    | 01–05 |
| Findings library  | Statistical analysis as pure Python                        | `libs/findings`   | 07    |
| Report            | Evidence project, built from the snapshot                  | `apps/report`     | 08    |
| Web app           | Next.js exploration app (reserved)                         | `apps/web`        | later |
| Local stack       | Postgres/PostGIS, ClickHouse, S3-compatible store, Dagster | `infra/docker`    | 01    |
| Cloud             | S3 and CloudFront for the static site, GitHub OIDC         | `infra/terraform` | 08    |

## Consistency and idempotency

- **Raw** is never rewritten. A new retrieval lands as a new, dated version; checksums detect when a source republished a file.
- **Staging, conformed facts, facts and marts** are partitioned (by year, and by month where the source allows) and idempotent: re-running a partition replaces it and never appends to it.
- **Dimensions** are not partitioned: they are small and rebuilt whole.
- At most one run per partition at a time.
- Analytics are eventually consistent by construction, because they are rebuilt from raw.

## Failure modes

The risks, their detection and containment are in [`design/brief.md`](design/brief.md#6-risks-and-failure-modes); each ADR lists the failure modes of its own decision.

## Observability

The day-one baseline is in [`design/brief.md`](design/brief.md#7-observability-plan).
