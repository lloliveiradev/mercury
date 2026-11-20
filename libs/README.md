# libs/

Shared libraries, organised by capability. Libraries do not depend on apps. Libraries are separate packages so that they can be tested without Dagster; any app may use them. A library that never gains a second user or a test boundary is flattened into its app (ADR-0007).

| Library    | Role                                          | Created in |
| ---------- | --------------------------------------------- | ---------- |
| `datasets` | Manifest and connector per source             | phase 03   |
| `geo`      | Spatial join and distance rules               | phase 05   |
| `quality`  | Reusable contracts and checks                 | phase 01   |
| `findings` | Statistical analysis as pure, testable Python | phase 07   |
