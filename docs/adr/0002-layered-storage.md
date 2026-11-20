# ADR-0002: Layer the storage as Parquet, then Postgres with PostGIS, then ClickHouse

- **Status**: Accepted
- **Date**: 2026-11-20
- **Deciders**: Leo Oliveira (owner)

## Context

The workloads differ by layer. Raw files must be kept as received and be reprocessable. Aligning stations to municipalities is spatial work (nearest point within a distance, point in polygon). Analysing hourly facts across many municipalities and years is columnar aggregation. A single store for all three is possible at small volume, but the project has two goals: a defensible architecture, and a portfolio that shows how each kind of store is used for what it does best.

The volume is unknown until phase 00 measures it (assumption A1). The general guidance for new projects is one relational database, adding a second store only for a measured need, because each store adds synchronization, backup and failure modes. This ADR deviates from that default knowingly: the workloads differ by layer, and the owner chose ClickHouse for the analytical layer (ADR-0003). The benchmark documents where each engine fits; it does not decide whether a layer exists.

## Decision

We will use three stores, each with one role, and every table or dataset has exactly one writer:

1. **Raw and staging: files on an S3-compatible store.** Raw holds each source file exactly as received, immutable and checksummed, landed per retrieval date. Staging holds typed, cleaned Parquet, partitioned by source and year. Cheap, reprocessable and portable.
2. **Conformed dimensions and the spatial mapping: PostgreSQL with PostGIS.** Municipality and time dimensions, the station-to-municipality mapping, and the control tables (ADR-0004). PostGIS is the right tool for the spatial join.
3. **Facts, marts and findings: ClickHouse.** Hourly facts keyed by municipality and hour, modelled marts, and the findings table.

Conformed facts are written as Parquet and loaded into ClickHouse by a load asset using the Python client. Dagster keeps its own metadata in a separate database; it is not a Mercury zone. Whether ClickHouse can read the lake directly and drop that load step is a parked topic.

## Alternatives considered

- **PostgreSQL only:** the simplest and probably sufficient at this volume. Not chosen as the design because of the owner's decision in ADR-0003, but it is the baseline in the benchmark.
- **DuckDB over Parquet as a shared compute layer or store:** excellent for local analytics. Not adopted as a store, to keep the count down; included in the benchmark. It may still be used in-process as a dataframe engine (ADR-0004).
- **A cloud warehouse (BigQuery, Athena):** adds cost and lock-in and cannot be reproduced with `docker compose up`.
- **A graph database:** no question in the MVP is graph-shaped. Not included; it would need a measured, graph-shaped need.

## Consequences

**Positive**

- Each store has a distinct workload, which makes the benchmark meaningful.
- Raw is reprocessable, so every other layer can be rebuilt.
- The layers map to ownership: one writer per zone.

**Negative (accepted)**

- Three stores to run, back up and keep in sync.
- Extra code to move data between zones.
- At small volume, Postgres alone might match the performance; the benchmark may show that.

## Failure modes and mitigations

| Failure                                               | Detection                             | Mitigation                                  |
| ----------------------------------------------------- | ------------------------------------- | ------------------------------------------- |
| Zones drift out of sync                               | Row-count reconciliation asset checks | Rebuild from raw; partitions are idempotent |
| Dimension keys differ between Postgres and ClickHouse | Referential checks at load time       | Surrogate keys generated once in Postgres   |
| Load into ClickHouse is partial                       | Count and checksum per partition      | Replace the whole partition, never append   |

## Observability plan

Row counts, durations and freshness per partition for each zone, and a reconciliation check between zones, all as Dagster asset metadata and checks.

## Revisit triggers

- The benchmark shows that the Parquet layer or the Postgres layer has no workload of its own (the ClickHouse layer is retained by ADR-0003).
- The sync code between zones grows beyond what the benefit justifies (the owner's call).
- ClickHouse can read the lake directly with acceptable behaviour: reopen the load step (parked topic).
