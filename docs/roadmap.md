# Roadmap

Status as of 2026-11-20: design approved by conversation, repository foundation created, no product code. The detail of each phase is in [`specs/`](specs/README.md).

## Now

| Phase | Name                              | State                |
| ----- | --------------------------------- | -------------------- |
| 00    | Source spike and assumption check | ready, next          |
| 01    | Walking skeleton                  | ready (spec written) |

## Then, in order

| Phase | Name                                  | Outcome                                                                         |
| ----- | ------------------------------------- | ------------------------------------------------------------------------------- |
| 02    | Spine: IBGE dimensions                | Municipality and time dimensions in Postgres/PostGIS                            |
| 03    | INMET ingestion                       | Raw and staging for weather, with contracts                                     |
| 04    | PRF ingestion                         | Raw and staging for accidents, with contracts                                   |
| 05    | Conformance and quality gates         | Station-to-municipality mapping, hourly alignment, quality checks               |
| 06    | ClickHouse marts and engine benchmark | dbt marts; reproducible benchmark across Postgres, DuckDB and ClickHouse        |
| 07    | Findings and recovery test            | Analysis with controls and correction; recovery test; pre-registered hypotheses |
| 08    | Report and publication                | Evidence report on S3 and CloudFront through Terraform                          |

Phases 03 and 04 can run in parallel after 02. Specs for phases 02 to 08 are written when the previous phase closes, so they use what that phase learned. ADR-0009 (analysis design) is due before the phase 05 spec.

## Later, without a spec yet

- ANTT toll-plaza traffic volume as the exposure denominator (also proves dataset onboarding).
- Next.js web app for exploration, with a thin API over the marts and findings.
- The scheduled pipeline running on AWS.
- Parked topics listed in [`design/brief.md`](design/brief.md#8-open-questions-for-the-owner).
