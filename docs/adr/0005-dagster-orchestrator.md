# ADR-0005: Orchestrate with Dagster

- **Status**: Accepted
- **Date**: 2026-11-20
- **Deciders**: Leo Oliveira (owner)

## Context

Data arrives in yearly or monthly drops, not as a stream. The orchestration requirement is therefore not scheduling. It is to **reprocess by partition** (for example only 2023), to **stop bad data before it moves on**, and to **show lineage** from each mart back to its sources.

Facts checked on 2026-11-20 against the vendors' documentation:

- Dagster models datasets as assets, supports asset checks next to an asset, represents dbt models as assets and can load dbt tests as asset checks (the `dagster-dbt` integration).
- Airflow 3 requires a scheduler, a DAG processor, an API server and a metadata database, with an optional triggerer.
- Prefect needs a server and workers; SQLite is the default database and Postgres is the production choice. The dbt integration was documented only by third parties in the sources found.

Market recognition of the tools should not drive the choice; the requirement does.

## Decision

We will orchestrate with **Dagster**. Each dataset zone is a partitioned asset, quality checks sit beside the asset they protect, and the dbt project of the marts loads into the same asset graph. The local stack runs the Dagster webserver and daemon with a Postgres instance for its own metadata.

## Alternatives considered

- **Airflow:** the best-known name, more components in the compose file, and the unit is the task, not the dataset.
- **Prefect:** lightweight to start, but not dataset-centred and with a dbt integration not confirmed from official documentation.
- **No orchestrator (Make and scripts):** would leave partition reruns, quality gates and lineage to hand-written code, which is the requirement.
- **Temporal:** a durable-workflow engine without the notions of dataset, partition or lineage.

## Consequences

**Positive**

- The orchestration model matches the problem: datasets, partitions, checks and lineage.
- The dbt marts join the same graph and show lineage in one interface.

**Negative (accepted)**

- Less name recognition than Airflow. The concepts (DAG, partition, sensor, backfill) are equivalent.
- One more service in the local stack.

## Failure modes and mitigations

| Failure                                       | Detection                       | Mitigation                                                           |
| --------------------------------------------- | ------------------------------- | -------------------------------------------------------------------- |
| A partition run fails midway                  | Run status and asset checks     | Partitions are idempotent; rerun the partition                       |
| Dagster metadata store is lost                | Webserver reports empty history | Assets are rebuildable from raw; metadata is not the source of truth |
| Orchestration code couples to storage details | Review                          | IO managers and resources isolate the stores                         |

## Observability plan

Run durations, row counts and freshness as asset metadata; asset check results as health.

## Revisit triggers

- A concrete need for Airflow appears (for example integrating with an existing Airflow deployment): port one small pipeline to Airflow as a separate exercise, without replacing Dagster in Mercury.
- Dagster's operational weight in the local stack becomes a barrier to the one-command reproduction goal.
