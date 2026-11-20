# ADR-0001: Start with an IBGE spine, PRF accidents and INMET weather for Brazil, 2022–2025

- **Status**: Accepted
- **Date**: 2026-11-20
- **Deciders**: Leo Oliveira (owner)

## Context

The original idea was a generic platform where a user brings many datasets and correlates them. That idea is attractive but weak as a first cut: it becomes a business-intelligence product, spends the effort on interface and semantic layers, and it hides the hard and valuable part for a data engineer, which is aligning datasets with different grains and formats. It also invites spurious correlations, because testing many dataset pairs without controls produces false findings.

The project has one developer, working part-time, and the first goal is to validate the idea on real data. Source facts checked on 2026-11-20:

- PRF publishes yearly CSV files of accidents, 2022 to 2026 (2026 partial), grouped by occurrence or by person, with a data dictionary, and states that the data is open for any use.
- INMET publishes yearly ZIP archives of automatic-station CSVs (2000 to 2026) with hourly observations; the layout varies between years.
- IBGE exposes municipalities with 7-digit codes through a public API.
- ANTT publishes toll-plaza traffic volume as yearly CSV files under a Creative Commons Attribution licence; the 2024 file is about 293 MiB.

Not confirmed, and checked in phase 00: the PRF field list (whether the municipality is a name or an IBGE code, highway, kilometre, coordinates, weather condition), the INMET station catalogue and variable list, the time zones of both sources (INMET states UTC; PRF is expected to be local), the IBGE boundary files, and whether Brazil for four years fits on a laptop.

## Decision

We will start with a **spine plus two datasets**, for all of Brazil, 2022 to 2025:

- **Spine:** IBGE municipalities (code, name, state, boundary) and a time dimension.
- **Event:** PRF accidents, per occurrence only.
- **Exposure:** INMET hourly weather from automatic stations.

The MVP research question is: _does rain increase road accidents on federal highways, and by how much, after controlling for hour of day, weekday, holidays and the seasonal pattern of each location?_ Precipitation is the primary exposure; other variables are used only if phase 00 confirms them.

The ANTT toll-plaza traffic volume comes in version 2, as an exposure denominator (accident rate per vehicle) and as the proof that onboarding a new dataset costs a manifest, a connector and tests.

The person-level PRF files are excluded: they carry personal data (LGPD) and the question does not need them.

## Alternatives considered

- **Generic platform with dataset upload and automatic correlation:** fails the goal of showing data engineering and statistical rigor, and cannot be finished by one part-time developer.
- **ANTT in the MVP:** adds a second kind of join (plaza to highway and kilometre) and large files before the first finding exists.
- **A single state instead of Brazil:** faster first cycle, but weakens the coverage argument. Kept as the fallback if assumption A1 fails.
- **A Census 2010 commute-time dataset from an earlier prototype:** old data and an unconfirmed source. Kept as a candidate to test onboarding.

## Consequences

**Positive**

- A finite scope with a concrete, falsifiable question.
- The hard problem is real: station-to-municipality spatial join, hourly alignment and format drift.
- The coverage limits are explicit and reportable.

**Negative (accepted)**

- PRF covers federal highways only, so the findings do not describe urban traffic.
- INMET stations are sparse; municipalities without a close station cannot be analysed.
- Without the ANTT exposure, accident counts are not rates in the MVP.

## Failure modes and mitigations

| Failure                                    | Detection                       | Mitigation                                                   |
| ------------------------------------------ | ------------------------------- | ------------------------------------------------------------ |
| A source lacks the fields the join needs   | Phase 00 data-dictionary check  | Revisit the join design (ADR-0002) before building ingestion |
| Four years of Brazil do not fit the laptop | Phase 00 measurement (A1)       | Shrink to a few states, keeping the design identical         |
| A source changes terms or removes files    | Manifest records terms and date | Pin the retrieval date and checksums in every report         |

## Observability plan

Each dataset manifest records source URL, terms, retrieval date and checksum. Row counts and freshness per partition are asset metadata.

## Revisit triggers

- Phase 00 shows that PRF lacks municipality and coordinates, or INMET lacks station coordinates.
- Downloading and staging one year of each source exceeds what the owner accepts on the development machine (the owner sets the limit in phase 00).
- Weather coverage leaves fewer municipalities analysable than the owner accepts for a national claim.
