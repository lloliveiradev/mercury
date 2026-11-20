# ADR-0008: Publish the static report on AWS through Terraform and use the AWS Emulator as the local stand-in

- **Status**: Accepted, with a compatibility spike in phase 00
- **Date**: 2026-11-20
- **Deciders**: Leo Oliveira (owner)

## Context

AWS is a widely used cloud. The project should give real, working use of it at low cost and low operational burden, without building heavy infrastructure for its own sake.

The report is a static site (ADR-0006), and the pipeline runs locally in this first cut.

AWS announced the **AWS Emulator** on 2026-11-11: a free, open-source local emulator that answers AWS API calls from the CLI and SDKs. Facts checked on 2026-11-20 from the AWS announcement and third-party write-ups:

- On macOS and Windows it runs in a container; AWS does not publish a ready-made image, and the documented Dockerfile is the route.
- At launch, IAM policies are not evaluated as AWS evaluates them, and each emulator behaves as a single account without cross-account or cross-Region behaviour.
- Coverage of CloudFront and IAM by AWS's own emulator was **not confirmed**.
- Older alternatives exist from third parties (Floci, MiniStack), with their own coverage claims.

The emulator is days old, so compatibility with the clients Mercury needs (boto3, Dagster IO, ClickHouse `s3()` with large Parquet files) must be verified, not assumed.

## Decision

We will:

1. Provision the **static site** with **Terraform**: an S3 bucket and a CloudFront distribution, published from GitHub Actions through **OIDC**, with no long-lived access keys.
2. Run the pipeline **locally**. In the local stack, the S3-compatible lake is the **AWS Emulator**, so the code uses the same S3 API and endpoint setting that it uses on AWS.
3. Gate the emulator in **phase 00**: it is adopted only if boto3, Dagster IO, ClickHouse `s3()` and large Parquet files work. Otherwise another S3-compatible store is used behind the same endpoint setting, after checking its maintenance status first, and this ADR is superseded for that part. Because AWS publishes no image, the local stack builds the emulator from its documented Dockerfile with the source tag or commit pinned.
4. Validate what the emulator cannot (CloudFront behaviour, IAM, the OIDC trust) with `terraform plan` and one real apply, behind a **budget alert**. No resource is created before the owner sets a spending ceiling.

## Alternatives considered

- **The whole pipeline on AWS now (ECS, RDS, a ClickHouse host):** best evidence, but cost, operations and account risk are high for a first cut. Deferred to version 2.
- **Host on Vercel:** simplest, but gives up the AWS evidence.
- **MinIO as the local stand-in:** its repository states that the community edition is in maintenance mode and distributed as source only, and its official images were withdrawn, so it is not a safe primary and only a candidate fallback. The owner also prefers the AWS-provided emulator, to avoid a different stack.
- **No local stand-in (test against real AWS):** slower, costs money and makes CI depend on credentials.

## Consequences

**Positive**

- Evidence of S3, CloudFront, IAM, OIDC and Terraform at low cost.
- The same S3 code path locally and in the cloud.
- No long-lived cloud credentials in CI.

**Negative (accepted)**

- The emulator is new: bugs and gaps are likely, and the fallback costs a configuration change.
- CloudFront and IAM cannot be fully validated locally, so some validation needs a real account.
- The pipeline itself is not yet proven on AWS.

## Failure modes and mitigations

| Failure                                  | Detection                                      | Mitigation                                                  |
| ---------------------------------------- | ---------------------------------------------- | ----------------------------------------------------------- |
| Emulator incompatible with a client      | Phase 00 spike; integration tests in CI        | Fall back to an S3-compatible store                         |
| Emulator behaviour differs from real AWS | Terraform plan and a real apply before release | Treat emulator results as development evidence only         |
| Unexpected cloud cost                    | Budget alert                                   | Ceiling set first; destroy with `terraform destroy`         |
| Public bucket exposure                   | Terraform policy review; block public access   | Serve only through CloudFront with restricted bucket access |

## Observability plan

CI logs the Terraform plan. A budget alert covers cost. CloudFront access logging is enabled only if the owner needs it and has set the cost ceiling.

## Revisit triggers

- Phase 00 shows the emulator incompatible: supersede the local stand-in part.
- The MVP is done and the owner sets a budget: write the ADR for running the scheduled pipeline on AWS.
- The emulator reaches CloudFront and IAM parity that makes the real-apply validation unnecessary.
