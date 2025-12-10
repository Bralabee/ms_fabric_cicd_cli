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

build: ## Build Python package (wheel)
	$(PIP) install build
	$(PYTHON) -m build

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
	@if [ -z "$(config)" ]; then \
		echo "\033[31mError: 'config' argument is missing.\033[0m"; \
		echo "Usage: make validate config=path/to/config.yaml"; \
		exit 1; \
	fi
	$(PYTHON) src/fabric_deploy.py validate $(config)

diagnose: ## Run pre-flight system diagnostics
	$(PYTHON) scripts/preflight_check.py

deploy: ## Deploy a workspace (Usage: make deploy config=path/to/config.yaml env=dev)
	@if [ -z "$(config)" ]; then \
		echo "\033[31mError: 'config' argument is missing.\033[0m"; \
		echo "Usage: make deploy config=path/to/config.yaml env=dev"; \
		exit 1; \
	fi
	@if [ -z "$(env)" ]; then \
		echo "\033[31mError: 'env' argument is missing.\033[0m"; \
		echo "Usage: make deploy config=path/to/config.yaml env=dev"; \
		exit 1; \
	fi
	$(PYTHON) src/fabric_deploy.py deploy $(config) --env $(env)

destroy: ## Destroy a workspace (Usage: make destroy config=path/to/config.yaml)
	@if [ -z "$(config)" ]; then \
		echo "\033[31mError: 'config' argument is missing.\033[0m"; \
		echo "Usage: make destroy config=path/to/config.yaml"; \
		exit 1; \
	fi
	$(PYTHON) src/fabric_deploy.py destroy $(config)

bulk-destroy: ## Bulk destroy workspaces from list (Usage: make bulk-destroy file=list.txt)
	@if [ -z "$(file)" ]; then echo "Error: file argument required. Usage: make bulk-destroy file=list.txt"; exit 1; fi
	$(PYTHON) scripts/bulk_destroy.py $(file)

# Docker Commands
DOCKER_IMAGE := fabric-cli-cicd

docker-build: ## Build the Docker image
	docker build -t $(DOCKER_IMAGE) .

docker-validate: ## Validate config using Docker (Usage: make docker-validate config=config/projects/...yaml ENVFILE=.env.ricoh)
	@if [ -z "$(config)" ]; then echo "Error: config argument required"; exit 1; fi
	docker run --rm --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) validate $(config)

docker-deploy: ## Deploy using Docker (Usage: make docker-deploy config=config/projects/...yaml env=dev ENVFILE=.env.ricoh)
	@if [ -z "$(config)" ]; then echo "Error: config argument required"; exit 1; fi
	@if [ -z "$(env)" ]; then echo "Error: env argument required"; exit 1; fi
	docker run --rm --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) deploy $(config) --env $(env)

docker-destroy: ## Destroy using Docker (Usage: make docker-destroy config=config/projects/...yaml ENVFILE=.env.ricoh)
	@if [ -z "$(config)" ]; then echo "Error: config argument required"; exit 1; fi
	docker run --rm --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) destroy $(config)

docker-shell: ## Run interactive shell in Docker container (Usage: make docker-shell ENVFILE=.env.ricoh)
	docker run --rm -it --entrypoint /bin/bash --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE)
	
# Default env file for Docker runs. Override with `ENVFILE=.env.other` when needed.
ENVFILE ?= .env

docker-feature-deploy: ## Deploy feature workspace using Docker (Usage: make docker-feature-deploy config=config/projects/...yaml env=dev branch=feature/x ENVFILE=.env.ricoh)
	@if [ -z "$(config)" ]; then echo "Error: config argument required"; exit 1; fi
	@if [ -z "$(env)" ]; then echo "Error: env argument required"; exit 1; fi
	@if [ -z "$(branch)" ]; then echo "Error: branch argument required"; exit 1; fi
	docker run --rm --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) \
		deploy $(config) --env $(env) --branch $(branch) --force-branch-workspace

diagnose: ## Run diagnostic checks
	$(PYTHON) src/fabric_deploy.py diagnose
