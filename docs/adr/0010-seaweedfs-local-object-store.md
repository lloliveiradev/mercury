# ADR-0010: Use SeaweedFS as the local S3-compatible store

- **Status**: Accepted
- **Date**: 2026-11-27
- **Deciders**: Leo Oliveira (owner)
- **Supersedes**: the local stand-in part of [ADR-0008](0008-aws-static-publication-and-local-emulator.md) (decision items 2 and 3). The rest of ADR-0008 stands.

## Context

ADR-0008 chose the AWS Emulator as the local S3-compatible lake and gated it in phase 00: it is adopted only if boto3, Dagster IO, ClickHouse `s3()` and large Parquet files work. Otherwise another S3-compatible store is used behind the same endpoint setting.

Phase 00 ran that gate. The results are in [`source-findings.md`](../design/source-findings.md#s3-stores-dbt-and-evidence):

- On emulator build 1.0.611, boto3, Dagster's `S3PickleIOManager` and ClickHouse `s3()` on a small object worked. All four INMET year Parquets, 59.7 to 72.7 MiB each, were refused.
- The emulator limits `put_object` to 16 MiB, a bucket to 64 MiB and all buckets together to 128 MiB (aws/aws-emulator issues 67 and 73, open on 2026-11-26). One year of INMET staging does not fit in one object, and four years do not fit in the store.
- AWS serves the emulator package only from an `LTS/latest` URL, so a build cannot be pinned to a version.

Candidates were checked on 2026-11-26 from their repositories and release pages:

| Store     | Licence    | Checked release | Image                      | Note                                                |
| --------- | ---------- | --------------- | -------------------------- | --------------------------------------------------- |
| SeaweedFS | Apache-2.0 | 4.55            | `chrislusf/seaweedfs:4.55` | Multi-arch image; one process serves the S3 gateway |
| RustFS    | Apache-2.0 | 1.0.7           | `rustfs/rustfs:1.0.7`      | Younger project                                     |
| Garage    | AGPL-3.0   | 2.6.0           | `dxflrs/garage:v2.6.0`     | Built for multi-node clusters; needs a layout step  |
| MinIO     | —          | —               | —                          | Repository archived; already set aside in ADR-0008  |

SeaweedFS was then run through the same four checks as the emulator. All passed: ClickHouse read every row and every column of the four year Parquets through `s3()`, and the row counts equal the source.

## Decision

We will:

1. Use **SeaweedFS** as the S3-compatible store of the local stack and of CI, from phase 01 on, with the image pinned to a version tag.
2. Run it as **one process** (`weed server` with the filer and the S3 gateway), with one access key taken from environment variables, its port bound to loopback, and its data in a named volume.
3. Keep the store behind **one endpoint setting**. Code talks to the S3 API through boto3, Dagster's S3 resources and ClickHouse `s3()`. Nothing in product code names SeaweedFS, so the same code points at AWS S3 by changing the endpoint and the credentials.
4. Leave the **AWS Emulator out of the local stack**. It is not the lake. Whether it is used to rehearse the CloudFront and IAM calls of the publication is decided in the phase 08 spec.

## Alternatives considered

- **Keep the AWS Emulator and split files under 16 MiB:** the 128 MiB total still does not hold the staging data, and the file layout would follow a limit of the emulator instead of the data.
- **Wait for the emulator to lift the limit:** the issues are open with no date, and phase 01 needs a store now.
- **RustFS:** permissive licence and a single binary, but a younger project with less history to judge its maintenance. Not tested.
- **Garage:** AGPL-3.0, and it is designed for multi-node clusters, with a layout step that a single-node development stack does not need. Not tested.
- **MinIO:** set aside in ADR-0008; its repository is now archived.
- **No local store (use real S3):** costs money, makes CI depend on credentials, and ADR-0008 already rejected it.

## Consequences

**Positive**

- A year of staging Parquet fits, with room for the whole window.
- A pinned image, unlike the emulator package.
- Plain HTTP on the compose network: ClickHouse needs no custom CA bundle and no shared network namespace to reach the store.
- The S3 code path stays the same locally and on AWS.

**Negative (accepted)**

- The local stack is no longer an AWS-provided tool, which ADR-0008 preferred.
- SeaweedFS is not AWS S3. Only the calls of the phase 00 check are proven: bucket, put, get, delete, the Dagster pickle IO manager and ClickHouse `s3()`. Multipart upload, listing at scale, versioning and bucket policies are not.
- Addressing is path-style over HTTP, so the endpoint setting carries the scheme and the addressing style, not only the host.
- SeaweedFS preallocates volumes; the volume size limit has to be set for a laptop disk.

## Failure modes and mitigations

| Failure                                      | Detection                                        | Mitigation                                                       |
| -------------------------------------------- | ------------------------------------------------ | ---------------------------------------------------------------- |
| An S3 call the pipeline needs is unsupported | Integration tests in CI against the pinned image | Change the call, or supersede this ADR with another store        |
| Behaviour differs from AWS S3                | Terraform plan and one real apply (ADR-0008)     | Treat local results as development evidence only                 |
| An image upgrade changes behaviour           | Version pinned; the phase 00 check can be rerun  | Upgrade on purpose, in its own change                            |
| The store fills the developer's disk         | Volume size limit; `docker system df`            | Named volume removed with `make down` and its volume option      |
| Credentials of the local store reach git     | gitleaks in hooks and CI                         | Only placeholder values in `.env.example`; real values in `.env` |

## Observability plan

The service has a health check on the S3 gateway, and the local stack waits for it. The phase 01 round-trip test writes to and reads from the store on every CI run. The filer UI lists what was stored, on loopback, in the local stack only.

## Revisit triggers

- The AWS Emulator lifts the S3 size limits and AWS serves pinned versions. The phase 00 check tries the emulator on every run and will show it.
- The pipeline needs an S3 feature SeaweedFS does not serve.
- SeaweedFS changes its licence or stops publishing images.
- The scheduled pipeline moves to AWS (the ADR foreseen in ADR-0008), which replaces the local store with S3 for that environment.
