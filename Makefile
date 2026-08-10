SYSTEM_PYTHON ?= python3
VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
SEMASVG ?= $(VENV)/bin/semasvg
VENV_READY := $(VENV)/.semasvg-ready

.DEFAULT_GOAL := help

.PHONY: help setup validate lint test check qa ci

help: ## Show the public developer commands.
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: $(VENV_READY) ## Create the local virtual environment and install the validator.
	$(PYTHON) -m pip install -e ./tools/validator

$(VENV_READY):
	$(SYSTEM_PYTHON) -m venv $(VENV)
	@touch $@

validate: ## Validate the public reference example and vocabularies.
	$(SEMASVG) validate examples/reference/renovation-demo
	$(SEMASVG) validate-vocabulary vocab

lint: ## Run the configured non-test static checks.
	$(SEMASVG) format examples/reference/renovation-demo --check

test: ## Run the validator test suite.
	$(PYTHON) -m unittest discover -s tools/validator/tests

check: test ## Run the validator test suite.

qa: ## Run validation, lint, and tests sequentially.
	$(MAKE) validate
	$(MAKE) lint
	$(MAKE) test

ci: setup ## Bootstrap a clean runner and run the complete QA suite.
	$(MAKE) qa
