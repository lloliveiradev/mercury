# ADR-0003: Keep ClickHouse as the analytical engine, with a benchmark that compares the alternatives

- **Status**: Accepted
- **Date**: 2026-11-20
- **Deciders**: Leo Oliveira (owner)

## Context

ClickHouse is the analytical store in ADR-0002. The honest question is whether it is needed at this volume. The volume is unknown until phase 00. The project owner wants to keep ClickHouse regardless, because it is a powerful engine that helps in several parts of the design: fast columnar aggregation, time-series functions, and the ability to read Parquet directly. That is an owner's decision, and it is recorded as such, not as a result of measurement.

The project exists to show engineering, architecture and data analysis. It does not exist to show ClickHouse.

## Decision

We will keep ClickHouse as the engine for facts, marts and findings. A reproducible **benchmark** will run the same central analytical queries on PostgreSQL, DuckDB over Parquet and ClickHouse. The benchmark does not decide whether ClickHouse stays; it documents where each engine fits and drives ClickHouse tuning (ordering key, partitioning, data types), with the hardware and versions stated.

The ClickHouse schema and queries are reviewed against ClickHouse best-practice rules (ordering key, data types, partitioning, query patterns).

## Alternatives considered

- **PostgreSQL only:** probably sufficient at small volume. Kept as a benchmark baseline, not chosen, because of the owner's decision.
- **DuckDB over Parquet:** very good for local analytics, but not a shared service. Benchmark baseline.
- **BigQuery or Athena:** cost, lock-in, no local reproduction.

## Consequences

**Positive**

- A strong engine for the hourly aggregation workload.
- Evidence-based documentation of when each engine wins, which is portfolio material by itself.
- The Parquet capability may simplify the pipeline (parked topic).

**Negative (accepted)**

- A third store to operate (ADR-0002).
- If the benchmark shows no advantage at this volume, the project still carries the engine. The report will say so honestly.

## Failure modes and mitigations

| Failure                              | Detection                                      | Mitigation                                                   |
| ------------------------------------ | ---------------------------------------------- | ------------------------------------------------------------ |
| Poor ordering key makes queries slow | Benchmark and query-plan inspection            | Tune ordering key and partitioning from the measured queries |
| Mutable data model fights the engine | Marts built only by full-partition replacement | Rebuild partitions; avoid updates and deletes                |
| Benchmark is not reproducible        | CI runs a small version                        | Script, versions and hardware recorded with the result       |

## Observability plan

Query duration, rows read and memory per benchmark query, stored with the benchmark result. In operation, row counts and load durations per partition.

## Revisit triggers

- The owner decides to simplify the stack.
- Operating ClickHouse (load code, schema changes) costs more effort than the analytics it enables, judged by the owner after phase 06.
