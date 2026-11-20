# infra/terraform

A validated shell arrives in phase 01 and the real resources in phase 08 (static site on S3 and CloudFront, GitHub OIDC role). No `terraform apply` runs before the owner sets a spending ceiling and a budget alert ([ADR-0008](../../docs/adr/0008-aws-static-publication-and-local-emulator.md)). State files and `.tfvars` are never committed.
