# Fabric CLI CI/CD Makefile

PYTHON := python3
PIP := pip
PYTEST := pytest

# Conda environment activation (use with shell commands)
CONDA_ENV := fabric-cli-cicd
CONDA_ACTIVATE := source ~/miniconda3/etc/profile.d/conda.sh && conda activate $(CONDA_ENV)

.PHONY: help install test lint clean validate deploy destroy bulk-destroy check-env

# Check if conda environment is active
check-env:
	@if [ "$$CONDA_DEFAULT_ENV" != "$(CONDA_ENV)" ]; then \
		echo "\033[33m⚠️  Warning: Conda environment '$(CONDA_ENV)' is not active.\033[0m"; \
		echo "\033[33m   Run: source ~/miniconda3/etc/profile.d/conda.sh && conda activate $(CONDA_ENV)\033[0m"; \
	fi

help: ## Show this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)


##@ Local Development

install: check-env ## Install dependencies and package in editable mode
	$(PIP) install -r requirements.txt
	$(PIP) install -e .

build: check-env ## Build Python package (wheel)
	$(PIP) install build
	$(PYTHON) -m build

test: check-env ## Run unit tests
	$(PYTEST) -m "not integration"

test-integration: check-env ## Run integration tests (requires credentials)
	$(PYTEST) tests/integration -m integration

lint: check-env ## Run code formatting and linting
	black src tests scripts bin
	-ruff check src tests scripts bin || true

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
	export PYTHONPATH="$${PYTHONPATH}:$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.cli validate $(config)

diagnose: ## Run pre-flight system diagnostics
	$(PYTHON) scripts/admin/preflight_check.py

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
	export PYTHONPATH="$${PYTHONPATH}:$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.cli deploy $(config) --env $(env)

onboard: ## Onboard a new project (Usage: make onboard org="Org" project="Proj")
	@if [ -z "$(org)" ]; then echo "Error: 'org' argument is missing."; exit 1; fi
	@if [ -z "$(project)" ]; then echo "Error: 'project' argument is missing."; exit 1; fi
	$(PYTHON) scripts/dev/onboard.py --org "$(org)" --project "$(project)" --template $(or $(template),medallion)

destroy: ## Destroy a workspace (Usage: make destroy config=path/to/config.yaml)
	@if [ -z "$(config)" ]; then \
	echo "\033[31mError: 'config' argument is missing.\033[0m"; \
	echo "Usage: make destroy config=path/to/config.yaml"; \
	exit 1; \
	fi
	export PYTHONPATH="$${PYTHONPATH}:$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.cli destroy $(config)

bulk-destroy: ## Bulk destroy workspaces from list (Usage: make bulk-destroy file=list.txt)
	@if [ -z "$(file)" ]; then echo "Error: file argument required. Usage: make bulk-destroy file=list.txt"; exit 1; fi
	$(PYTHON) scripts/admin/bulk_destroy.py $(file)

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
	docker run --rm --entrypoint python --env-file $(ENVFILE) $(DOCKER_IMAGE) scripts/admin/preflight_check.py

docker-generate: ## Generate project config in Docker (Usage: make docker-generate org="Org" project="Proj" template="basic_etl")
	@if [ -z "$(org)" ]; then echo "Error: org argument required"; exit 1; fi
	@if [ -z "$(project)" ]; then echo "Error: project argument required"; exit 1; fi
	docker run --rm --entrypoint python --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) \
	scripts/dev/generate_project.py "$(org)" "$(project)" --template $(or $(template),basic_etl)

docker-init-repo: ## Initialize ADO repo in Docker (Usage: make docker-init-repo org="Org" project="Proj" repo="Repo")
	@if [ -z "$(org)" ]; then echo "Error: org argument required"; exit 1; fi
	@if [ -z "$(project)" ]; then echo "Error: project argument required"; exit 1; fi
	@if [ -z "$(repo)" ]; then echo "Error: repo argument required"; exit 1; fi
	docker run --rm --entrypoint python --env-file $(ENVFILE) $(DOCKER_IMAGE) \
	scripts/admin/utilities/init_ado_repo.py --organization "$(org)" --project "$(project)" --repository "$(repo)"

docker-feature-deploy: ## Deploy feature workspace using Docker (Usage: make docker-feature-deploy config=... env=dev branch=feature/x)
	@if [ -z "$(config)" ]; then echo "Error: config argument required"; exit 1; fi
	@if [ -z "$(env)" ]; then echo "Error: env argument required"; exit 1; fi
	@if [ -z "$(branch)" ]; then echo "Error: branch argument required"; exit 1; fi
	docker run --rm --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) \
	deploy $(config) --env $(env) --branch $(branch) --force-branch-workspace

