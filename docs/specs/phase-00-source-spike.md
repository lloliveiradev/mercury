# Phase 00: Source spike and assumption check

- **Status:** done (2026-11-27). Results in [`source-findings.md`](../design/source-findings.md); the store decision is [ADR-0010](../adr/0010-seaweedfs-local-object-store.md)
- **Depends on:** none
- **Briefs and ADRs:** [brief §9](../design/brief.md#9-assumptions-and-how-phase-00-checks-them), [ADR-0001](../adr/0001-mvp-scope-and-datasets.md), [ADR-0004](../adr/0004-python-and-hybrid-transformation.md), [ADR-0006](../adr/0006-evidence-publication-web-app-deferred.md), [ADR-0008](../adr/0008-aws-static-publication-and-local-emulator.md)

## Goal

Replace the assumptions the design rests on with measured facts, before any pipeline is built. The deliverable is a document, not product code.

## Scope

Check each assumption A1 to A12 in the brief and record the answer with evidence.

1. **Sources (A1 to A5, A9 to A12).** Download one full year of each MVP source (PRF per occurrence, INMET, IBGE spine and boundaries) and record: size on disk, row counts, time to download and to parse, memory used. For the other years, inspect the layout only (INMET: one station file per year; PRF: the header and first rows). Read the PRF data dictionary and the INMET station catalogue. Record the real field lists, encodings and date formats; the time zone of INMET hours and of PRF times; whether PRF gives the municipality as a name or an IBGE code, and the share of names that match the IBGE list; and the differences between years 2022 to 2025.
2. **AWS Emulator (A6).** Run it in a container on the development machine and test: S3 calls from the AWS SDK for Python, a large Parquet file written and read, ClickHouse reading it through `s3()` with a custom endpoint, and Dagster's S3 IO. Record what works, what fails and the behaviour on large files. If it fails, test one S3-compatible alternative the same way.
3. **dbt adapter for ClickHouse (A7).** Read the adapter's current documentation and build one trivial model and one test.
4. **Evidence (A8).** Build one page that reads ClickHouse and one that reads a Parquet file, and note which path is simpler.
5. **Throwaway stack.** The spikes of items 2 to 4 run from a throwaway compose file in `tools/spikes/`, because the real stack arrives in phase 01.

## Out of scope

- Any product code. Spike scripts are throwaway, live in `tools/spikes/` with a README, and must not be imported by product code.
- Committing downloaded data, even samples.
- Cloud resources.

## Rules

- No data in git (`data/` is ignored). Record URLs, retrieval dates and checksums instead.
- Use only the per-occurrence PRF file. Do not download the person-level files.
- Do not state a version or a limit from memory: read it from the vendor's documentation or from the tool itself.
- A refuted assumption leads to a new ADR that supersedes the affected one, not to a silent change of the brief.

## Deliverable

`docs/design/source-findings.md`, with a table of the assumptions A1 to A12 (confirmed, refuted or changed), the evidence for each, the measured volumes per source and year, and the decisions that follow (for example: keep Brazil 2022 to 2025 or shrink; emulator adopted or fallback; the join key for stations).

## Acceptance criteria

- Every assumption A1 to A12 has a recorded status and evidence.
- The measured volumes allow the owner to confirm or change the window in ADR-0001.
- The emulator compatibility result decides ADR-0008's local stand-in, in writing.
- The field lists of PRF and INMET are recorded, and the alignment section of `architecture.md` (station assignment, time zones, municipality matching) is confirmed or corrected, with the open parameters listed for ADR-0009.
- `make docs-check` and `make scan-secrets` pass, and no data file is tracked by git.

## Pre-mortem

- **Repeats:** downloads are idempotent by URL and year; a second run must not leave a half-written file that looks valid.
- **Source changes during the spike:** record retrieval dates and checksums, because yearly files can be republished.
- **Surprises in the files:** encodings, decimal separators and header lines vary; treat the first parse as exploration, not a design.
- **Personal data:** if a file unexpectedly contains personal fields, stop, do not store it, and record the finding.
- **What the phase removes:** nothing; it only adds knowledge and may remove assumptions from the design.
