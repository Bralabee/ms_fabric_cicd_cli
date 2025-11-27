# Fabric CLI CI/CD Makefile

PYTHON := python3
PIP := pip
PYTEST := pytest

.PHONY: help install test lint clean validate deploy destroy bulk-destroy

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	$(PIP) install -r requirements.txt

test: ## Run unit tests
	$(PYTEST) -m "not integration"

test-integration: ## Run integration tests (requires credentials)
	$(PYTEST) tests/integration -m integration

lint: ## Run code formatting and linting
	black src tests scripts
	ruff check src tests scripts

clean: ## Clean up cache and temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	rm -f *.log

validate: ## Validate a configuration file (Usage: make validate config=path/to/config.yaml)
	@if [ -z "$(config)" ]; then echo "Error: config argument required. Usage: make validate config=path/to/config.yaml"; exit 1; fi
	$(PYTHON) src/fabric_deploy.py validate $(config)

deploy: ## Deploy a workspace (Usage: make deploy config=path/to/config.yaml env=dev)
	@if [ -z "$(config)" ]; then echo "Error: config argument required. Usage: make deploy config=path/to/config.yaml env=dev"; exit 1; fi
	@if [ -z "$(env)" ]; then echo "Error: env argument required. Usage: make deploy config=path/to/config.yaml env=dev"; exit 1; fi
	$(PYTHON) src/fabric_deploy.py deploy $(config) --env $(env)

destroy: ## Destroy a workspace (Usage: make destroy config=path/to/config.yaml)
	@if [ -z "$(config)" ]; then echo "Error: config argument required. Usage: make destroy config=path/to/config.yaml"; exit 1; fi
	$(PYTHON) src/fabric_deploy.py destroy $(config)

bulk-destroy: ## Bulk destroy workspaces from list (Usage: make bulk-destroy file=list.txt)
	@if [ -z "$(file)" ]; then echo "Error: file argument required. Usage: make bulk-destroy file=list.txt"; exit 1; fi
	$(PYTHON) scripts/bulk_destroy.py $(file)

diagnose: ## Run diagnostic checks
	$(PYTHON) src/fabric_deploy.py diagnose
