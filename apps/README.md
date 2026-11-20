# apps/

Deployable pieces. Each subfolder is one unit that runs on its own. Apps wire libraries together and hold almost no business logic; logic lives in `libs/`. Apps depend on libs, never the reverse.

| App         | Role                                               | Created in           |
| ----------- | -------------------------------------------------- | -------------------- |
| `pipelines` | Dagster project (Python) and the dbt project       | phase 01             |
| `report`    | Evidence project, built from the findings snapshot | phase 01 (shell), 08 |
| `web`       | Next.js exploration app (reserved, see ADR-0006)   | later                |
