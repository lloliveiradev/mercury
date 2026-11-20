# Delivery specs

These specs take Mercury from the [brief](../design/brief.md) to a published report. There is one spec per phase. A spec says **what** must be true when the phase ends and **which rules** the implementation must follow. It does not say how to split the work: the plan does, written before the phase starts.

The overall picture, including the phases without a spec yet, is in [`../roadmap.md`](../roadmap.md).

## Phases

| Phase | Spec                                                          | Depends on | Status                      |
| ----- | ------------------------------------------------------------- | ---------- | --------------------------- |
| 00    | [Source spike and assumption check](phase-00-source-spike.md) | none       | ready                       |
| 01    | [Walking skeleton](phase-01-walking-skeleton.md)              | 00         | ready                       |
| 02    | Spine: IBGE dimensions                                        | 01         | spec written when 01 closes |
| 03    | INMET ingestion                                               | 02         | spec written when 02 closes |
| 04    | PRF ingestion                                                 | 02         | spec written when 02 closes |
| 05    | Conformance and quality gates                                 | 03, 04     | spec written when 04 closes |
| 06    | ClickHouse marts and engine benchmark                         | 05         | spec written when 05 closes |
| 07    | Findings and recovery test                                    | 06         | spec written when 06 closes |
| 08    | Report and publication                                        | 07         | spec written when 07 closes |

Phases 03 and 04 can run in parallel after 02. Later phases get their spec only when the previous phase closes, so each spec uses what the previous phase learned. **ADR-0009 (analysis design: unit of analysis, model, time zone, station assignment, municipality matching, holiday calendar) must be accepted before the phase 05 spec is written**, because it fixes the grain of the facts and marts.

## How to run a phase

1. **Pick** the lowest-numbered phase whose dependencies are `done`. Set its status to `in progress` in the table above.
2. **Read** the spec, the brief sections it links, the ADRs it cites and `AGENTS.md`. When the spec and the brief disagree, raise the conflict (step 7).
3. **Plan.** Write `docs/plans/<YYYY-MM-DD>-phase-<NN>-<slug>.md` with the task list, the files each task touches and the test list. Before coding, add a **pre-mortem** section that answers:
   - which state transitions exist, including repeats (run twice, rerun a partition, change a manifest after a run);
   - what runs concurrently, and what protects it;
   - every config default involved, read from the code and not assumed;
   - which side effects happen before and after a commit or a load;
   - what the phase **removes**, not only what it adds.
4. **Implement** on a branch `phase/<NN>-<slug>`, tests first for pure logic. The owner writes the product code.
5. **Verify** with the commands in the spec's acceptance criteria and in `AGENTS.md`.
6. **Open one pull request** per phase, using the template.
7. **Close the phase.** After the owner merges, set the status to `done`, update `architecture.md` and `roadmap.md` for what changed, and write the spec of the next phase. If something in the brief or an ADR turned out wrong, write a new ADR that supersedes the old one.
