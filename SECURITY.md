# Security policy

## Supported versions

Mercury publishes no versioned releases. The supported line is `main`.

| Version | Supported |
| ------- | --------- |
| `main`  | yes       |

Mercury processes open public data only. It is a portfolio and study project and does not handle personal data, payments or credentials of third parties.

## Reporting a vulnerability

Report a vulnerability privately through GitHub Security Advisories: open the **Security** tab of this repository and choose **Report a vulnerability**.

Do not report a vulnerability in a public issue, discussion or pull request.

## Handling secrets

A credential committed to the repository is treated as an incident: rotate it first, then remove it from the history. Hooks and CI run gitleaks. The decisions behind the data and cloud setup are in [`docs/adr/`](docs/adr/).
