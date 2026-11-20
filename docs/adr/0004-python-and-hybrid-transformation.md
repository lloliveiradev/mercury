# ADR-0004: Use Python, with SQL files for dimensions and loads, dbt for the marts, and an ORM only for control tables

- **Status**: Accepted
- **Date**: 2026-11-20
- **Deciders**: Leo Oliveira (owner)

## Context

The pipeline has four kinds of work: ingestion and cleaning of messy files, spatial alignment, aggregation into marts, and statistical analysis. Python is the standard language for data engineering and the owner knows it well. The data, statistics and orchestration libraries that matter here are in Python.

For SQL transformations the choices are plain SQL files, dbt, or a mix. The marts are declarative SQL that benefits from tests and lineage. The spatial join and the bulk loads are better as explicit SQL or code. The case for dbt rests on that use case.

Postgres will also hold small transactional control tables (runs, dataset catalogue, quality results) where an ORM pays off.

## Decision

We will use:

- **Python** for ingestion, staging, orchestration code, spatial-join orchestration and analysis.
- **SQL in versioned files** for dimensions, the spatial join and bulk loads into Postgres (`COPY`, PostGIS functions). ClickHouse loads use the ClickHouse client; reading Parquet directly through `s3()` is a parked topic.
- **dbt** only for the ClickHouse marts, with its tests and lineage, run through Dagster.
- **SQLAlchemy and Alembic** only for the Postgres control tables and the migrations of the Postgres schema.
- **DDL ownership:** Alembic owns all Postgres DDL, versioned SQL files own the ClickHouse tables that load assets fill, and dbt owns the models it creates.

The processing library for dataframes (Polars, pandas or DuckDB used in-process, never as a store, see ADR-0002) is not decided here: it is reversible and belongs to the phase specs.

## Alternatives considered

- **Plain Python and SQL everywhere:** maximum control, but tests, documentation and lineage of the marts would be hand-built.
- **dbt for every layer (Postgres and ClickHouse):** two adapters, and spatial work is not dbt's strength.
- **Go for the pipelines:** the ecosystem for dataframes, statistics and orchestration is thinner.
- **An ORM for everything:** poor fit for bulk loads, spatial queries and columnar analytics.

## Consequences

**Positive**

- Each tool is used where it pays.
- The marts get declarative tests and lineage.
- The control tables get typed models and versioned migrations.

**Negative (accepted)**

- Two ways of transforming data to explain and maintain.
- A dependency on the dbt adapter for ClickHouse, whose current state must be verified (assumption A7).

## Failure modes and mitigations

| Failure                                       | Detection                                           | Mitigation                                  |
| --------------------------------------------- | --------------------------------------------------- | ------------------------------------------- |
| The dbt adapter lacks a feature a mart needs  | Phase 00 and phase 06 builds                        | Write that mart as plain SQL run by Dagster |
| ORM models drift from the migrations          | A test that runs the migrations and compares        | Migrations are the source of truth          |
| Logic splits between Python and SQL unclearly | Review against the layer table in `architecture.md` | One owner of each rule, stated in the spec  |

## Observability plan

dbt test results are Dagster asset checks. Migrations run in CI against a clean Postgres.

## Revisit triggers

- The ClickHouse dbt adapter limits the marts in a way that costs more than writing them as SQL: fall back to plain SQL for that layer.
- The control tables stay trivial: replace the ORM with SQL and simple migrations.
