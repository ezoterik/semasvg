.DEFAULT_GOAL := help

SYSTEM_PYTHON ?= python3
VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
SEMASVG ?= $(VENV)/bin/semasvg
SEMASVG_REQUIREMENTS ?= requirements-semasvg.txt
QA_JOBS ?= 2

ifneq ($(strip $(SEMASVG_SOURCE)),)
SEMASVG_INSTALL_ARGS := "$(SEMASVG_SOURCE)"
else
SEMASVG_INSTALL_ARGS := -r "$(SEMASVG_REQUIREMENTS)"
endif

.PHONY: help setup validate lint test check qa ci fix inspect

help: ## Show available commands.
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "%-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Create .venv and install the pinned SemaSVG toolchain.
	@test -n "$(SEMASVG_SOURCE)" || test -f "$(SEMASVG_REQUIREMENTS)" || \
		(echo "Copy requirements-semasvg.txt.example to requirements-semasvg.txt and pin a full commit hash, or set SEMASVG_SOURCE for a local checkout."; exit 2)
	$(SYSTEM_PYTHON) -m venv $(VENV)
	$(PYTHON) -m pip install $(SEMASVG_INSTALL_ARGS)

validate: ## Validate the canonical model.
	$(SEMASVG) validate model

lint: ## Check SVG formatting and derived labels.
	$(SEMASVG) format model --check
	$(SEMASVG) materialize-labels model --check

test: ## Smoke-test the project graph without writing files.
	$(SEMASVG) inspect-graph model > /dev/null

check: test ## Run the read-only graph smoke test.

qa: ## Run read-only checks with bounded keep-going diagnostics.
	$(SYSTEM_PYTHON) scripts/run_qa.py --semasvg "$(SEMASVG)" --jobs $(QA_JOBS) $(if $(filter 1,$(VERBOSE)),--verbose)

ci: ## Bootstrap the validator and run quality checks.
	$(MAKE) setup
	$(MAKE) qa

fix: ## Apply SVG formatting and derived-label updates.
	$(SEMASVG) format model
	$(SEMASVG) materialize-labels model

inspect: ## Print the project graph as JSON.
	$(SEMASVG) inspect-graph model
