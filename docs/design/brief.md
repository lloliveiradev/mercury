# Mercury: architecture brief

- **Status:** Decisions approved by the owner on 2026-11-20; this written document awaits the owner's review
- **Date:** 2026-11-20
- **Stage:** validation (an idea; no code, no users)
- **Owner:** Leo Oliveira

This brief turns the idea into a scope, a first cut (MVP) and a set of decisions. Each decision has its own ADR in [`../adr/`](../adr/). Specs for the delivery phases are in [`../specs/`](../specs/README.md).

## 1. Context

**Stage.** Validation. Nothing is built. The first job is to prove that the idea works on real data with the smallest possible stack.

**Reader.** The people who evaluate the project are engineers and data leads. They open the repository and a published report, not a running system. The project is also the owner's practice ground: the owner writes the product code by hand.

**Team.** One developer, part-time, who also operates everything that runs. This keeps the number of moving parts low and makes every component an operating cost.

**Constraints.**

- Reproducible on a developer laptop with one command (`docker compose`), without cloud access.
- Open data only. No personal data: the person-level files of any source are out of scope (LGPD).
- No real data and no secrets in git. Credentials in history are expensive to undo, so secret scanning is part of the baseline.
- Cloud cost: no resource is created before the owner sets a spending ceiling and a budget alert.

**Assumptions** are listed in section 9. Each has the cheapest way to check it, and phase 00 checks them.

## 2. Problem and north

Public datasets about the same places and times live in separate silos, with different grains (a weather reading per station per hour, an accident per occurrence, a census figure per municipality), different file formats that drift between years, and no shared keys. Asking "does X move with Y?" first requires a data platform that aligns them, and then an analysis that does not fool itself.

**North.** Mercury aligns heterogeneous public datasets on a common municipality-and-time spine and publishes reproducible findings, with every architecture decision documented and measured.

**What a reader should conclude in five minutes.** The author designs data platforms end to end (ingestion, modelling, storage layers, orchestration, quality, publication) and treats data with statistical rigor.

**Anti-goals.** Mercury is not a generic BI tool, does not accept uploads, is not real time, and does not claim causation. A technology is added only when a requirement needs it.

## 3. Scope

**Research question of the MVP.**

> Does rain increase road accidents on federal highways, and by how much, after controlling for hour of day, weekday, holidays and the seasonal pattern of each location?

The weather variables actually available (precipitation, and possibly humidity, temperature and wind) are confirmed in phase 00. Precipitation is the primary exposure. The hypotheses are written down in the phase 07 spec **before** results are looked at, and the set is small, to keep multiple-comparison control honest.

**Analysis design constraints.** The unit of analysis and the model fix the grain of the facts (phase 05) and of the marts (phase 06), so they are decided in an ADR (ADR-0009) **before the phase 05 spec**, not in phase 07. That ADR settles at least:

- Where the weather of an accident comes from: preferably the nearest station to the accident's coordinates within a distance limit (if phase 00 confirms coordinates), a municipality reference point only as a fallback. Weather taken from the wrong place pulls the estimated effect toward zero.
- One explicit time zone. INMET states that its station data is in UTC; PRF times are local, and Brazil spans several offsets. All timestamps are converted by a stated, tested rule before any join.
- How PRF municipality names are matched to IBGE codes, and the quality check for unmatched names.
- The model and its uncertainty: seasonality per location (rainy seasons differ by region) and standard errors that account for autocorrelation in hourly series.
- The holiday calendar: national and state holidays from a versioned calendar, with the source chosen in that ADR.
- No effect is estimated on real data before the hypotheses are written. The engine benchmark of phase 06 measures performance on aggregates only.

**Core flows.**

1. Ingest a source for a year range, reproducibly and idempotently.
2. Conform it to the municipality-and-time spine, behind quality gates.
3. Compute findings: associations with controls, intervals and correction for multiple comparisons.
4. Publish a report from a snapshot of the findings.
5. Onboard a new dataset by a manifest, a connector and tests (proven in version 2 with the toll traffic dataset).

**MVP cut.**

| Must have                                                                        | Later                                                             | Never                                            |
| -------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------ |
| IBGE municipality spine                                                          | ANTT toll-plaza traffic volume (exposure denominator, v2)         | Uploads of arbitrary datasets                    |
| PRF accidents, per occurrence, 2022–2025                                         | Census 2010 commute-time dataset (tests dataset onboarding)       | Person-level files (personal data)               |
| INMET hourly weather, 2022–2025                                                  | Senatran fleet and Census 2022 population by municipality (rates) | Real-time ingestion                              |
| Layers: Parquet → Postgres/PostGIS → ClickHouse                                  | Next.js web app for exploration                                   | Causal claims                                    |
| Dagster, dbt marts, findings, recovery test, Evidence report, static publication | Pipeline running on AWS                                           | A graph database without a graph-shaped question |
| Engine benchmark (Postgres, DuckDB on Parquet, ClickHouse) on the same queries   | Prediction models                                                 |                                                  |

**Success metrics.**

- Leading: a stranger reproduces the published report from the public sources with the documented commands, at the pinned retrieval date. If a source was republished, checksums report the drift instead of failing silently.
- Guardrail: no finding is published without lineage, passing quality checks and a passing recovery test.

## 4. Data sources

Facts below were checked on 2026-11-20 against the public pages. What was **not** confirmed is marked, and phase 00 closes it.

| Role                   | Source                                                                                                                                            | Confirmed                                                                                                                               | Not confirmed (phase 00)                                                                    |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Spine                  | [IBGE localities API](https://servicodados.ibge.gov.br/api/docs/localidades)                                                                      | Municipality list with 7-digit codes (first two digits are the state)                                                                   | Municipal boundary files (URL and format)                                                   |
| Event: accidents       | [PRF open data](https://www.gov.br/prf/pt-br/acesso-a-informacao/dados-abertos/dados-abertos-da-prf)                                              | Yearly CSV, 2022–2026 (2026 partial), "grouped by occurrence" and "grouped by person"; data dictionary; use without licence restriction | Field list (municipality as name or IBGE code, highway, km, coordinates, weather condition) |
| Exposure: weather      | [INMET historical data](https://portal.inmet.gov.br/dadoshistoricos)                                                                              | Yearly ZIP of automatic-station CSVs (2000–2026); hourly observations; layout varies between years                                      | Station catalogue fields (coordinates), variable list, encoding per year                    |
| Exposure (v2): traffic | [ANTT toll-plaza traffic volume](https://dados.antt.gov.br/en/dataset/volume-trafego-praca-pedagio/resource/7f622637-a442-4f3c-8360-aebc41806ca3) | Yearly CSV, Creative Commons Attribution; the 2024 file is about 293 MiB                                                                | Columns, plaza-to-highway-and-km mapping                                                    |

Known coverage biases, to be stated in every report: PRF covers federal highways only; INMET stations do not exist in every municipality, so the join to a municipality uses the nearest station within a distance limit.

## 5. Decisions

| Decision              | Choice                                                                                                                | ADR                                                                                                                   |
| --------------------- | --------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| MVP scope             | IBGE spine, PRF, INMET; Brazil, 2022–2025; ANTT in v2                                                                 | [0001](../adr/0001-mvp-scope-and-datasets.md)                                                                         |
| Storage layers        | Parquet (raw) → Postgres/PostGIS (dimensions, spatial) → ClickHouse (facts, marts)                                    | [0002](../adr/0002-layered-storage.md)                                                                                |
| Analytical engine     | ClickHouse, kept by the owner; benchmark compares the alternatives                                                    | [0003](../adr/0003-clickhouse-analytical-engine.md)                                                                   |
| Language, transforms  | Python; SQL files for dimensions and loads; dbt for marts; SQLAlchemy and Alembic for control tables                  | [0004](../adr/0004-python-and-hybrid-transformation.md)                                                               |
| Orchestrator          | Dagster                                                                                                               | [0005](../adr/0005-dagster-orchestrator.md)                                                                           |
| Visualization         | Evidence now (static, from a snapshot); a Next.js app later                                                           | [0006](../adr/0006-evidence-publication-web-app-deferred.md)                                                          |
| Repository, tests, CI | Monorepo, uv and pnpm workspaces, Make, lefthook, gitleaks, GitHub Actions, recovery test                             | [0007](../adr/0007-monorepo-layout-testing-ci.md)                                                                     |
| Cloud                 | Terraform: S3 and CloudFront static site with GitHub OIDC; pipeline local; SeaweedFS as the local S3-compatible store | [0008](../adr/0008-aws-static-publication-and-local-emulator.md), [0010](../adr/0010-seaweedfs-local-object-store.md) |
| Analysis design       | Unit of analysis, model, time zone, station assignment: open                                                          | ADR-0009, due before phase 05                                                                                         |

## 6. Risks and failure modes

| Risk                                                               | Detection                                                    | Containment                                                                                                                         |
| ------------------------------------------------------------------ | ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| INMET layout drifts between years (dates, encoding, extra columns) | Contract test per source and year                            | Fail loudly at staging; per-year parsers behind one interface                                                                       |
| Partial or repeated ingestion                                      | Row-count reconciliation asset checks                        | Partitioned, idempotent assets; raw is immutable and re-runnable                                                                    |
| Station-to-municipality join assigns the wrong weather             | Distance statistics in a quality check                       | Distance limit; municipalities without a close station are flagged, not guessed                                                     |
| Spurious correlation published                                     | Recovery test with planted and null series                   | Controls and multiple-comparison correction are part of the analysis code                                                           |
| AWS Emulator is incompatible with a client we need                 | Phase 00 compatibility spike                                 | Fallback to an S3-compatible store behind the same endpoint setting (ADR-0008). Phase 00 hit this: SeaweedFS replaced it (ADR-0010) |
| Source terms or files change                                       | Manifest records terms and retrieval date; checksums         | Pin the retrieval date in every published report                                                                                    |
| Credential or real data committed                                  | gitleaks in hook and CI; `data/` ignored                     | Rotate, then rewrite history                                                                                                        |
| Cloud cost overrun                                                 | Budget alert on the account                                  | Ceiling set before any resource; the pipeline stays local                                                                           |
| Analysis design                                                    | Unit of analysis, model, time zone, station assignment: open | ADR-0009, due before phase 05                                                                                                       |

## 7. Observability plan

Day-one baseline for a batch platform, with no service to trace yet: structured logs, Dagster run and asset metadata (row counts, durations, freshness), and asset checks as health signals. Every published report shows the data retrieval date and the git commit. OpenTelemetry tracing is added when the first long-running service exists (the web API, ADR-0006).

## 8. Open questions for the owner

1. The spending ceiling for AWS, before phase 08.
2. The git author address for the public repository history (CONTRIBUTING explains why it matters).
3. The hypotheses for the report, written before results are seen (phase 07).
4. The analysis design of ADR-0009 (unit of analysis, model, station assignment, distance limit, time zone, holiday calendar, municipality matching), before the phase 05 spec. I will draft it for your review once phase 00 has answered what the sources contain.

### Parked topics (to discuss later)

- ClickHouse reading Parquet directly from the lake. It may remove the load step between the conformed layer and ClickHouse (ADR-0002, ADR-0003).
- A second consumer of ClickHouse for free exploration (Metabase) before the web app exists.
- Running the scheduled pipeline on AWS (ADR-0008, version 2).

## 9. Assumptions and how phase 00 checks them

| #   | Assumption                                                                                | Cheapest check                                                                                               |
| --- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| A1  | Brazil, 2022–2025, fits on a developer laptop (disk, time, memory)                        | Download one full year of each source and measure; inspect only the layout of the other years                |
| A2  | PRF per-occurrence files have municipality, highway, km and date and time                 | Read the data dictionary and one file                                                                        |
| A3  | PRF files have coordinates                                                                | Same                                                                                                         |
| A4  | INMET catalogue has station coordinates and the yearly files are parseable                | Read the catalogue and parse one station file per year, 2022 to 2025; check the time zone of the hour column |
| A5  | INMET provides precipitation hourly for most stations                                     | Count stations and missing values                                                                            |
| A6  | AWS Emulator serves S3 to boto3, Dagster and ClickHouse `s3()` with large Parquet files   | Compatibility spike (ADR-0008)                                                                               |
| A7  | The dbt adapter for ClickHouse supports the marts we need                                 | Read the adapter documentation and build one model                                                           |
| A8  | Evidence reads a Parquet snapshot (primary path); ClickHouse only for local development   | Build one page both ways                                                                                     |
| A9  | PRF records the weather condition per occurrence (a data-quality cross-check)             | Data dictionary                                                                                              |
| A10 | PRF gives the municipality as a name, not an IBGE code, and names can be matched to codes | Read one file; measure the share of names that match the IBGE list exactly and after normalisation           |
| A11 | INMET hours are UTC and PRF times are local time                                          | Check the file headers and documentation; the conversion rule is decided in ADR-0009                         |
| A12 | IBGE municipal boundary files exist in a format PostGIS loads                             | Locate one and load it                                                                                       |

## 10. First steps

1. Phase 00: source spike and assumption check ([spec](../specs/phase-00-source-spike.md)).
2. Phase 01: walking skeleton, an empty pipeline running through the real tooling and CI ([spec](../specs/phase-01-walking-skeleton.md)).
3. Then the data phases in the order of [`../specs/README.md`](../specs/README.md).
