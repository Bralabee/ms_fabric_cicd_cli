# Fabric CLI CI/CD Makefile

PYTHON := python3
PIP := pip
PYTEST := pytest

.PHONY: help install test lint clean validate deploy destroy bulk-destroy

help: ## Show this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Local Development

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

##@ Local Operations

validate: ## Validate a configuration file (Usage: make validate config=path/to/config.yaml)
	@if [ -z "$(config)" ]; then \
	echo "\033[31mError: 'config' argument is missing.\033[0m"; \
	echo "Usage: make validate config=path/to/config.yaml"; \
	exit 1; \
	fi
	export PYTHONPATH=$${PYTHONPATH}:$(PWD)/src && $(PYTHON) -m core.cli validate $(config)

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
	export PYTHONPATH=$${PYTHONPATH}:$(PWD)/src && $(PYTHON) -m core.cli deploy $(config) --env $(env)

destroy: ## Destroy a workspace (Usage: make destroy config=path/to/config.yaml)
	@if [ -z "$(config)" ]; then \
	echo "\033[31mError: 'config' argument is missing.\033[0m"; \
	echo "Usage: make destroy config=path/to/config.yaml"; \
	exit 1; \
	fi
	export PYTHONPATH=$${PYTHONPATH}:$(PWD)/src && $(PYTHON) -m core.cli destroy $(config)

bulk-destroy: ## Bulk destroy workspaces from list (Usage: make bulk-destroy file=list.txt)
	@if [ -z "$(file)" ]; then echo "Error: file argument required. Usage: make bulk-destroy file=list.txt"; exit 1; fi
	$(PYTHON) scripts/bulk_destroy.py $(file)

##@ Docker Operations

DOCKER_IMAGE := fabric-cli-cicd
# Default env file for Docker runs. Override with `ENVFILE=.env.other` when needed.
ENVFILE ?= .env

docker-build: ## Build the Docker image
	docker build -t $(DOCKER_IMAGE) .

docker-validate: ## Validate config using Docker (Usage: make docker-validate config=... ENVFILE=.env)
	@if [ -z "$(config)" ]; then echo "Error: config argument required"; exit 1; fi
	docker run --rm --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) validate $(config)

docker-deploy: ## Deploy using Docker (Usage: make docker-deploy config=... env=dev ENVFILE=.env)
	@if [ -z "$(config)" ]; then echo "Error: config argument required"; exit 1; fi
	@if [ -z "$(env)" ]; then echo "Error: env argument required"; exit 1; fi
	docker run --rm --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) deploy $(config) --env $(env)

docker-destroy: ## Destroy using Docker (Usage: make docker-destroy config=... ENVFILE=.env)
	@if [ -z "$(config)" ]; then echo "Error: config argument required"; exit 1; fi
	docker run --rm --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) destroy $(config)

docker-shell: ## Run interactive shell in Docker container (Usage: make docker-shell ENVFILE=.env)
	docker run --rm -it --entrypoint /bin/bash --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE)

docker-diagnose: ## Run diagnostics in Docker (Usage: make docker-diagnose ENVFILE=.env)
	docker run --rm --env-file $(ENVFILE) $(DOCKER_IMAGE) python scripts/preflight_check.py

docker-generate: ## Generate project config in Docker (Usage: make docker-generate org="Org" project="Proj" template="basic_etl")
	@if [ -z "$(org)" ]; then echo "Error: org argument required"; exit 1; fi
	@if [ -z "$(project)" ]; then echo "Error: project argument required"; exit 1; fi
	docker run --rm --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) \
	python scripts/generate_project.py "$(org)" "$(project)" --template $(or $(template),basic_etl)

docker-init-repo: ## Initialize ADO repo in Docker (Usage: make docker-init-repo org="Org" project="Proj" repo="Repo")
	@if [ -z "$(org)" ]; then echo "Error: org argument required"; exit 1; fi
	@if [ -z "$(project)" ]; then echo "Error: project argument required"; exit 1; fi
	@if [ -z "$(repo)" ]; then echo "Error: repo argument required"; exit 1; fi
	docker run --rm --env-file $(ENVFILE) $(DOCKER_IMAGE) \
	python scripts/utilities/init_ado_repo.py --organization "$(org)" --project "$(project)" --repository "$(repo)"

docker-feature-deploy: ## Deploy feature workspace using Docker (Usage: make docker-feature-deploy config=... env=dev branch=feature/x)
	@if [ -z "$(config)" ]; then echo "Error: config argument required"; exit 1; fi
	@if [ -z "$(env)" ]; then echo "Error: env argument required"; exit 1; fi
	@if [ -z "$(branch)" ]; then echo "Error: branch argument required"; exit 1; fi
	docker run --rm --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) \
	deploy $(config) --env $(env) --branch $(branch) --force-branch-workspace

