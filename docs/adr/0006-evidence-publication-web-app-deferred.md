# ADR-0006: Publish with Evidence from a snapshot now, and defer the Next.js web app

- **Status**: Accepted
- **Date**: 2026-11-20
- **Deciders**: Leo Oliveira (owner)

## Context

The findings must be presented with their conclusions in words, in a way a reader can open without running anything. A reader will not run `docker compose up`, so the published artefact must not depend on a running database.

Facts checked on 2026-11-20:

- Evidence builds a static site from SQL and Markdown; queries run at build time, so new data requires a rebuild; the output can be served by any static host.
- A ClickHouse connector for Evidence exists as a community package.
- One author reported that bundled query results made a deployment exceed a hosting provider's per-file size limit. This is a single anecdote.
- Metabase bundles a ClickHouse driver (partner support level); Superset documents `clickhouse-connect`.

The owner wants an interactive Next.js app later, for exploring the data and for richer dashboards.

## Decision

We will publish with **Evidence**, built from an exported **snapshot** (Parquet) of the findings and of the aggregated marts the charts need, so the public site does not depend on any database being online. The statistics are computed in the Python pipeline (a tested library), and Evidence only presents the results in SQL and charts.

The **contract** between analysis and presentation is the versioned `findings` table and the marts. A future Next.js app (`apps/web`, reserved) reads the same contract through a thin API. That app, its API and its authentication get their own ADR when the work starts.

Dashboard design (conclusion titles, one highlight per chart) follows the owner's dashboard guidelines (a conclusion as the title, one highlight per chart) when the report spec is written.

## Alternatives considered

- **Metabase or Superset:** need a running server and a database online; weak for narrative and for statistical rigor.
- **Observable Framework:** flexible, but more front-end code than data work.
- **A custom app now:** puts the effort on interface before there is a finding to show.
- **Evidence reading ClickHouse live:** requires the database to be online; kept only for local development.

## Consequences

**Positive**

- A reproducible, versioned report that opens from a URL.
- Statistics stay in tested code, not in the presentation layer.
- The later web app reuses the same contract.

**Negative (accepted)**

- Little free exploration until the web app exists.
- The ClickHouse connector is community-maintained; the fallback is the Parquet snapshot.
- Data freshness requires a rebuild and a republish.

## Failure modes and mitigations

| Failure                                    | Detection                          | Mitigation                                                                |
| ------------------------------------------ | ---------------------------------- | ------------------------------------------------------------------------- |
| Snapshot too large for the host            | Build output size check in CI      | Aggregate more before exporting; split files                              |
| Report shows stale data                    | Retrieval date shown on every page | Rebuild; the date and commit are part of the page                         |
| Connector breaks on a new Evidence release | CI build of the report             | The public build uses the snapshot, so only local development is affected |

## Observability plan

The report build is a CI job. Every page shows the data retrieval date and the git commit.

## Revisit triggers

- The owner needs free exploration before the web app: add Metabase over ClickHouse as a second consumer.
- The web app work starts: write its ADR (API shape, authentication, hosting) and decide whether Evidence stays.
