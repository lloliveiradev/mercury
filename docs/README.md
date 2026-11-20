# Mercury documentation

Mercury is a portfolio data platform: open Brazilian datasets are conformed to one municipality-and-time spine, analysed with statistical rigor and published as reproducible findings. It is a study and portfolio project. It never runs in production.

## Where to start

| If you want to know                                          | Read                                 |
| ------------------------------------------------------------ | ------------------------------------ |
| What the project is, its scope and its decisions at a glance | [`design/brief.md`](design/brief.md) |
| How the system is structured                                 | [`architecture.md`](architecture.md) |
| What is done, what comes next and in which order             | [`roadmap.md`](roadmap.md)           |
| The rules and acceptance criteria of a delivery phase        | [`specs/`](specs/README.md)          |
| Why a structural decision was made                           | [`adr/`](adr/)                       |
| The rules for editing the repository, for people and agents  | [`../AGENTS.md`](../AGENTS.md)       |

Implementation plans written before each phase live in `plans/`.

## How the documents relate

- The **brief** is the approved target. It changes only with the owner's approval.
- **Specs** turn the brief into phases. Each phase updates `architecture.md` when it changes something it describes.
- **ADRs** record one decision each. An accepted ADR is not edited to change its decision: a new ADR supersedes it.
- **Architecture** describes the system as designed and marks what is planned with the phase that delivers it.
- When a document and the code disagree, the code wins and the document is fixed.

## Language

All documentation is in English.
