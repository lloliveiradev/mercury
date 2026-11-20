# infra/

Environment definitions. The apps run in any environment; this folder describes specific ones.

| Folder       | Describes                                                                             | Created in           |
| ------------ | ------------------------------------------------------------------------------------- | -------------------- |
| `docker/`    | The local stack: PostgreSQL with PostGIS, ClickHouse, an S3-compatible store, Dagster | phase 01             |
| `terraform/` | The static site on S3 and CloudFront and the GitHub OIDC role (ADR-0008)              | phase 01 (shell), 08 |

CI workflows live in `.github/workflows/`.

Rules: ports bound to `127.0.0.1`, no `latest` image tags, only `.env.example` with placeholder values is committed, and no cloud resource is created before the owner sets a spending ceiling.
