# mercury: root Makefile
#
# Conventions:
#   - Every public target has a `## comment`, shown by `make help`.
#   - Only targets that work today are listed. Targets for the pipelines, the
#     local stack and the report are added by the phase that creates them
#     (see docs/specs/README.md).
SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

C_RST := \033[0m
C_BLD := \033[1m
C_CYN := \033[36m

##@ General
.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage: $(C_BLD)make$(C_RST) $(C_CYN)<target>$(C_RST)\n"} \
		/^[a-zA-Z_0-9\/-]+:.*?##/ { printf "  $(C_CYN)%-22s$(C_RST) %s\n", $$1, $$2 } \
		/^##@/ { printf "\n$(C_BLD)%s$(C_RST)\n", substr($$0, 5) }' $(MAKEFILE_LIST)

##@ Hygiene
.PHONY: install-hooks
install-hooks: ## Install git hooks (lefthook)
	@command -v lefthook >/dev/null || { echo "lefthook not found. brew install lefthook"; exit 1; }
	lefthook install

.PHONY: uninstall-hooks
uninstall-hooks: ## Remove git hooks
	@command -v lefthook >/dev/null && lefthook uninstall || true

.PHONY: scan-secrets
scan-secrets: ## Scan the working tree and the history for secrets (gitleaks)
	@command -v gitleaks >/dev/null || { echo "gitleaks not found. brew install gitleaks"; exit 1; }
	gitleaks detect --redact --verbose

.PHONY: docs-check
docs-check: ## Check Markdown, YAML and JSON formatting (Prettier)
	@command -v npx >/dev/null || { echo "npx not found. Install Node.js."; exit 1; }
	npx --yes prettier --check "**/*.{md,yml,yaml,json}"

.PHONY: docs-fmt
docs-fmt: ## Format Markdown, YAML and JSON (Prettier)
	@command -v npx >/dev/null || { echo "npx not found. Install Node.js."; exit 1; }
	npx --yes prettier --write "**/*.{md,yml,yaml,json}"
