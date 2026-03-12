# Fabric CLI CI/CD Makefile

# Shell detection: bash is required for all recipes.
# Windows: requires Git for Windows (https://git-scm.com) which provides bash.
#   GNU Make on Windows may start with cmd.exe OR sh.exe depending on PATH.
#   We use a polyglot test (cmd.exe preserves quotes in echo, POSIX shells strip
#   them) to detect the active shell, then locate bash accordingly.
#   Override: make SHELL=C:/custom/Git/bin/bash.exe
ifeq ($(OS),Windows_NT)
    ifeq ($(shell echo "test"),"test")
        # Make is using cmd.exe -- use 8.3 short path to avoid spaces
        SHELL := C:/PROGRA~1/Git/bin/bash.exe
    else
        # Make is using a POSIX shell (sh/bash from Git, MSYS2, or conda)
        SHELL := $(shell command -v bash 2>/dev/null || echo /usr/bin/bash)
    endif
    PYTHON := python
    PATHSEP := ;
else
    SHELL := /bin/bash
    PYTHON := python3
    PATHSEP := :
endif
.SHELLFLAGS := -c
PIP := pip
PYTEST := pytest

# Conda environment activation (use with shell commands)
CONDA_ENV := fabric-cli-cicd
CONDA_ACTIVATE := source ~/miniconda3/etc/profile.d/conda.sh && conda activate $(CONDA_ENV)

.PHONY: help setup install build test test-integration lint format clean \
	validate diagnose deploy promote onboard onboard-isolated \
	init-github-repo feature-workspace destroy bulk-destroy generate scaffold discover-folders \
	check-env typecheck security coverage ci version \
	pre-commit-install pre-commit-run \
	list-workspaces list-items \
	webapp-dev webapp-build \
	docker-build docker-validate docker-deploy docker-destroy \
	docker-shell docker-diagnose docker-generate docker-scaffold docker-discover-folders docker-init-repo \
	docker-feature-deploy docker-promote \
	docker-onboard docker-onboard-isolated docker-feature-workspace \
	docker-bulk-destroy docker-list-workspaces docker-list-items

# Check if conda environment is active
check-env:
	@if [ "$$CONDA_DEFAULT_ENV" != "$(CONDA_ENV)" ]; then \
		printf "\033[33m!  Warning: Conda environment '$(CONDA_ENV)' is not active.\033[0m\n"; \
		printf "\033[33m   Run: source ~/miniconda3/etc/profile.d/conda.sh && conda activate $(CONDA_ENV)\033[0m\n"; \
	fi

help: ## Show this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

version: ## Show current project version
	@grep 'version' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/'


##@ Environment Setup

setup: ## First-time project setup (creates conda env, installs deps, copies .env template)
	@if [ -x bin/setup.sh ] || chmod +x bin/setup.sh 2>/dev/null; then true; fi
	bash bin/setup.sh

install: check-env ## Install dependencies and package in editable mode
	$(PIP) install -r requirements-dev.txt
	$(PIP) install -e .

build: check-env ## Build Python package (wheel)
	$(PIP) install build
	$(PYTHON) -m build


##@ Code Quality

format: check-env ## Auto-format code (black + isort)
	black .
	isort .

lint: check-env ## Check code formatting and linting (non-destructive)
	black --check .
	isort --check-only .
	flake8 src

typecheck: check-env ## Run mypy type checking
	$(PYTHON) -m mypy src/usf_fabric_cli --ignore-missing-imports

security: check-env ## Run security scan (bandit)
	bandit -r src/ -ll -x "*/tests/*"

pre-commit-install: ## Install pre-commit hooks into local git repo
	pip install pre-commit
	pre-commit install

pre-commit-run: ## Run all pre-commit hooks on all files
	pre-commit run --all-files


##@ Testing

test: check-env ## Run unit tests
	$(PYTEST) -m "not integration"

test-integration: check-env ## Run integration tests (requires credentials)
	$(PYTEST) tests/integration -m integration

coverage: check-env ## Run tests with coverage report
	$(PYTEST) -m "not integration" --cov=usf_fabric_cli --cov-report=term-missing --cov-report=html

ci: lint typecheck test security ## Run full CI quality suite (lint + typecheck + test + security)
	@printf "\033[32m[OK] All quality checks passed.\033[0m\n"

clean: ## Clean up cache and temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	rm -f *.log
	rm -rf htmlcov/


##@ Local Operations

validate: ## Validate a configuration file (Usage: make validate config=path/to/config.yaml)
	@if [ -z "$(config)" ]; then \
	printf "\033[31mError: 'config' argument is missing.\033[0m\n"; \
	echo "Usage: make validate config=path/to/config.yaml"; \
	exit 1; \
	fi
	export PYTHONPATH="$${PYTHONPATH}$(PATHSEP)$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.cli validate "$(config)"

diagnose: ## Run pre-flight system diagnostics
	export PYTHONPATH="$${PYTHONPATH}$(PATHSEP)$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.scripts.admin.preflight_check

generate: ## Generate project config (Usage: make generate org="Org" project="Proj" [template="medallion"])
	@if [ -z "$(org)" ]; then echo "Error: 'org' argument is missing."; exit 1; fi
	@if [ -z "$(project)" ]; then echo "Error: 'project' argument is missing."; exit 1; fi
	export PYTHONPATH="$${PYTHONPATH}$(PATHSEP)$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.scripts.dev.generate_project "$(org)" "$(project)" --template $(or $(template),medallion)

scaffold: ## Scaffold config from live workspace (Usage: make scaffold workspace="Name" [output=path] [feature=1] [pipeline="Name"] [slug=override])
	@if [ -z "$(workspace)" ]; then \
	printf "\033[31mError: 'workspace' argument is missing.\033[0m\n"; \
	echo "Usage: make scaffold workspace=\"My Workspace [DEV]\""; \
	echo ""; \
	echo "Options:"; \
	echo "  workspace  -- Name of the existing Fabric workspace to scan (required)"; \
	echo "  output     -- Output path for base_workspace.yaml (default: config/projects/_templates/<slug>/)"; \
	echo "  feature=1  -- (Required for CI/CD flow) Set feature=1 to also generate feature_workspace.yaml"; \
	echo "  pipeline   -- (Required for Prod promotion) Pipeline name to scaffold dev/test/prod stages"; \
	echo "  slug       -- Override the auto-generated project slug"; \
	echo "  test_ws    -- Explicit Test stage workspace name"; \
	echo "  prod_ws    -- Explicit Production stage workspace name"; \
	echo ""; \
	echo "Examples:"; \
	echo "  make scaffold workspace=\"EDP [DEV]\""; \
	echo "  make scaffold workspace=\"EDP [DEV]\" feature=1 pipeline=\"EDP - Pipeline\""; \
	echo "  make scaffold workspace=\"Sales\" slug=re_sales output=config/projects/_templates/re_sales/base_workspace.yaml"; \
	exit 1; \
	fi
	export PYTHONPATH="$${PYTHONPATH}$(PATHSEP)$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.scripts.admin.utilities.scaffold_workspace "$(workspace)" \
		$(if $(output),--output "$(output)",) \
		$(if $(feature),--include-feature-template,) \
		$(if $(pipeline),--pipeline-name "$(pipeline)",) \
		$(if $(slug),--project-slug "$(slug)",) \
		$(if $(test_ws),--test-workspace-name "$(test_ws)",) \
		$(if $(prod_ws),--prod-workspace-name "$(prod_ws)",)

discover-folders: ## Discover new folders from live workspace and update YAML config (Usage: make discover-folders config=path/to/config.yaml [workspace="Name"] [branch=feature/x] [dry_run=1])
	@if [ -z "$(config)" ]; then \
	printf "\033[31mError: 'config' argument is missing.\033[0m\n"; \
	echo "Usage: make discover-folders config=config/projects/edp/base_workspace.yaml workspace=\"EDP Feature\""; \
	echo ""; \
	echo "Options:"; \
	echo "  config     -- Path to base_workspace.yaml (required)"; \
	echo "  workspace  -- Name of the live workspace to scan"; \
	echo "  branch     -- Feature branch name (derives workspace name if workspace not given)"; \
	echo "  dry_run=1  -- Show what would change without writing"; \
	exit 1; \
	fi
	export PYTHONPATH="$${PYTHONPATH}$(PATHSEP)$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.scripts.admin.utilities.discover_folders "$(config)" \
		$(if $(workspace),--workspace "$(workspace)",) \
		$(if $(branch),--branch "$(branch)",) \
		$(if $(dry_run),--dry-run,)

deploy: ## Deploy a workspace (Usage: make deploy config=path/to/config.yaml env=dev [branch=feature/x])
	@if [ -z "$(config)" ]; then \
	printf "\033[31mError: 'config' argument is missing.\033[0m\n"; \
	echo "Usage: make deploy config=path/to/config.yaml env=dev"; \
	exit 1; \
	fi
	@if [ -z "$(env)" ]; then \
	printf "\033[31mError: 'env' argument is missing.\033[0m\n"; \
	echo "Usage: make deploy config=path/to/config.yaml env=dev"; \
	exit 1; \
	fi
	export PYTHONPATH="$${PYTHONPATH}$(PATHSEP)$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.cli deploy "$(config)" --env "$(env)" \
		$(if $(branch),--branch "$(branch)" --force-branch-workspace,)

promote: ## Promote through Deployment Pipeline stages (Usage: make promote pipeline="Name" [source=Dev] [target=Test] [note="msg"])
	@if [ -z "$(pipeline)" ]; then echo "Error: 'pipeline' argument is missing."; exit 1; fi
	export PYTHONPATH="$${PYTHONPATH}$(PATHSEP)$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.cli promote \
		--pipeline-name "$(pipeline)" \
		$(if $(source),--source-stage $(source),) \
		$(if $(target),--target-stage $(target),) \
		$(if $(note),--note "$(note)",)

onboard: ## Full bootstrap: Dev+Test+Prod + Pipeline (Usage: make onboard org="Org" project="Proj" [stages="dev,test,prod"] [capacity_id=...] [dry_run=1])
	@if [ -z "$(org)" ]; then echo "Error: 'org' argument is missing."; exit 1; fi
	@if [ -z "$(project)" ]; then echo "Error: 'project' argument is missing."; exit 1; fi
	export PYTHONPATH="$${PYTHONPATH}$(PATHSEP)$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.cli onboard \
		--org "$(org)" --project "$(project)" --template $(or $(template),medallion) \
		$(if $(stages),--stages $(stages),) \
		$(if $(capacity_id),--capacity-id $(capacity_id),) \
		$(if $(pipeline_name),--pipeline-name "$(pipeline_name)",) \
		$(if $(dry_run),--dry-run,)

onboard-isolated: ## Bootstrap with auto-created project repo (Usage: make onboard-isolated org="Org" project="Proj" git_owner="Owner")
	@if [ -z "$(org)" ]; then echo "Error: 'org' argument is missing."; exit 1; fi
	@if [ -z "$(project)" ]; then echo "Error: 'project' argument is missing."; exit 1; fi
	@if [ -z "$(git_owner)" ]; then echo "Error: 'git_owner' argument is missing."; exit 1; fi
	export PYTHONPATH="$${PYTHONPATH}$(PATHSEP)$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.scripts.dev.onboard --org "$(org)" --project "$(project)" --template $(or $(template),medallion) \
		--create-repo --git-provider $(or $(git_provider),github) --git-owner "$(git_owner)" \
		$(if $(ado_project),--ado-project "$(ado_project)",) $(if $(stages),--stages $(stages),)

init-github-repo: ## Create & initialize a GitHub repo (Usage: make init-github-repo git_owner="Owner" repo="Repo")
	@if [ -z "$(git_owner)" ]; then echo "Error: 'git_owner' argument is missing."; exit 1; fi
	@if [ -z "$(repo)" ]; then echo "Error: 'repo' argument is missing."; exit 1; fi
	export PYTHONPATH="$${PYTHONPATH}$(PATHSEP)$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.scripts.admin.utilities.init_github_repo --owner "$(git_owner)" --repo "$(repo)" $(if $(branch),--branch $(branch),)

feature-workspace: ## Create isolated feature workspace (Usage: make feature-workspace org="Org" project="Proj")
	@if [ -z "$(org)" ]; then echo "Error: 'org' argument is missing."; exit 1; fi
	@if [ -z "$(project)" ]; then echo "Error: 'project' argument is missing."; exit 1; fi
	export PYTHONPATH="$${PYTHONPATH}$(PATHSEP)$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.scripts.dev.onboard --org "$(org)" --project "$(project)" --template $(or $(template),medallion) --with-feature-branch

destroy: ## Destroy a workspace (Usage: make destroy config=path/to/config.yaml [env=dev] [force=1] [workspace_override="Name"])
	@if [ -z "$(config)" ]; then \
	printf "\033[31mError: 'config' argument is missing.\033[0m\n"; \
	echo "Usage: make destroy config=path/to/config.yaml [env=dev] [force=1] [workspace_override=Name]"; \
	exit 1; \
	fi
	export PYTHONPATH="$${PYTHONPATH}$(PATHSEP)$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.cli destroy "$(config)" \
		$(if $(env),--env "$(env)",) \
		$(if $(force),--force,) \
		$(if $(workspace_override),--workspace-name-override "$(workspace_override)",)

bulk-destroy: ## Bulk destroy workspaces from list (Usage: make bulk-destroy file=list.txt)
	@if [ -z "$(file)" ]; then echo "Error: file argument required. Usage: make bulk-destroy file=list.txt"; exit 1; fi
	export PYTHONPATH="$${PYTHONPATH}$(PATHSEP)$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.scripts.admin.bulk_destroy $(file)


##@ Admin Utilities

list-workspaces: ## List all Fabric workspaces
	export PYTHONPATH="$${PYTHONPATH}$(PATHSEP)$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.scripts.admin.utilities.list_workspaces

list-items: ## List items in a workspace (Usage: make list-items workspace="Name")
	@if [ -z "$(workspace)" ]; then echo "Error: 'workspace' argument is missing."; exit 1; fi
	export PYTHONPATH="$${PYTHONPATH}$(PATHSEP)$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.scripts.admin.utilities.list_workspace_items "$(workspace)"

analyze-migration: ## Analyze what can be replaced with Fabric CLI (Usage: make analyze-migration)
	export PYTHONPATH="$${PYTHONPATH}$(PATHSEP)$(PWD)/src" && $(PYTHON) -m usf_fabric_cli.scripts.admin.utilities.analyze_migration


##@ Webapp (Interactive Guide)

webapp-dev: ## Start the Interactive Guide webapp in dev mode
	$(MAKE) -C webapp dev

webapp-build: ## Build the webapp Docker images
	$(MAKE) -C webapp docker-build


##@ Docker Operations

DOCKER_IMAGE := fabric-cli-cicd
# Default env file for Docker runs. Override with `ENVFILE=.env.other` when needed.
ENVFILE ?= .env
# On Windows, MSYS_NO_PATHCONV prevents Git Bash from converting Unix-style paths
# (like /app/config) into Windows paths when passing arguments to Docker.
ifeq ($(OS),Windows_NT)
    DOCKER_PREFIX := MSYS_NO_PATHCONV=1
else
    DOCKER_PREFIX :=
endif

docker-build: ## Build the Docker image
	$(DOCKER_PREFIX) docker build -t $(DOCKER_IMAGE) .

docker-validate: ## Validate config using Docker (Usage: make docker-validate config=... ENVFILE=.env)
	@if [ -z "$(config)" ]; then echo "Error: config argument required"; exit 1; fi
	$(DOCKER_PREFIX) docker run --rm --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) validate "$(config)"

docker-deploy: ## Deploy using Docker (Usage: make docker-deploy config=... env=dev ENVFILE=.env)
	@if [ -z "$(config)" ]; then echo "Error: config argument required"; exit 1; fi
	@if [ -z "$(env)" ]; then echo "Error: env argument required"; exit 1; fi
	$(DOCKER_PREFIX) docker run --rm --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) deploy "$(config)" --env "$(env)"

docker-promote: ## Promote using Docker (Usage: make docker-promote pipeline="Name" [source=Dev] [target=Test])
	@if [ -z "$(pipeline)" ]; then echo "Error: pipeline argument required"; exit 1; fi
	$(DOCKER_PREFIX) docker run --rm --env-file $(ENVFILE) $(DOCKER_IMAGE) promote \
		--pipeline-name "$(pipeline)" \
		$(if $(source),--source-stage $(source),) \
		$(if $(target),--target-stage $(target),) \
		$(if $(note),--note "$(note)",)

docker-destroy: ## Destroy using Docker (Usage: make docker-destroy config=... ENVFILE=.env)
	@if [ -z "$(config)" ]; then echo "Error: config argument required"; exit 1; fi
	$(DOCKER_PREFIX) docker run --rm --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) destroy "$(config)"

docker-shell: ## Run interactive shell in Docker container (Usage: make docker-shell ENVFILE=.env)
	$(DOCKER_PREFIX) docker run --rm -it --entrypoint /bin/bash --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE)

docker-diagnose: ## Run diagnostics in Docker (Usage: make docker-diagnose ENVFILE=.env)
	$(DOCKER_PREFIX) docker run --rm --env-file $(ENVFILE) $(DOCKER_IMAGE) diagnose

docker-generate: ## Generate project config in Docker (Usage: make docker-generate org="Org" project="Proj" template="basic_etl")
	@if [ -z "$(org)" ]; then echo "Error: org argument required"; exit 1; fi
	@if [ -z "$(project)" ]; then echo "Error: project argument required"; exit 1; fi
	$(DOCKER_PREFIX) docker run --rm --entrypoint python --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) \
	-m usf_fabric_cli.scripts.dev.generate_project "$(org)" "$(project)" --template $(or $(template),basic_etl)

docker-scaffold: ## Scaffold config from live workspace in Docker (Usage: make docker-scaffold workspace="Name" [feature=1] [pipeline="Name"] ENVFILE=.env)
	@if [ -z "$(workspace)" ]; then echo "Error: workspace argument required"; exit 1; fi
	$(DOCKER_PREFIX) docker run --rm --entrypoint python --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) \
	-m usf_fabric_cli.scripts.admin.utilities.scaffold_workspace "$(workspace)" \
	$(if $(output),--output "$(output)",) \
	$(if $(feature),--include-feature-template,) \
	$(if $(pipeline),--pipeline-name "$(pipeline)",) \
	$(if $(slug),--project-slug "$(slug)",) \
	$(if $(test_ws),--test-workspace-name "$(test_ws)",) \
	$(if $(prod_ws),--prod-workspace-name "$(prod_ws)",)

docker-discover-folders: ## Discover new folders from live workspace in Docker (Usage: make docker-discover-folders config=... [workspace="Name"] [branch=...] ENVFILE=.env)
	@if [ -z "$(config)" ]; then echo "Error: config argument required"; exit 1; fi
	$(DOCKER_PREFIX) docker run --rm --entrypoint python --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) \
	-m usf_fabric_cli.scripts.admin.utilities.discover_folders "$(config)" \
	$(if $(workspace),--workspace "$(workspace)",) \
	$(if $(branch),--branch "$(branch)",) \
	$(if $(dry_run),--dry-run,)

docker-init-repo: ## Initialize ADO repo in Docker (Usage: make docker-init-repo org="Org" project="Proj" repo="Repo")
	@if [ -z "$(org)" ]; then echo "Error: org argument required"; exit 1; fi
	@if [ -z "$(project)" ]; then echo "Error: project argument required"; exit 1; fi
	@if [ -z "$(repo)" ]; then echo "Error: repo argument required"; exit 1; fi
	$(DOCKER_PREFIX) docker run --rm --entrypoint python --env-file $(ENVFILE) $(DOCKER_IMAGE) \
	-m usf_fabric_cli.scripts.admin.utilities.init_ado_repo --organization "$(org)" --project "$(project)" --repository "$(repo)"

docker-feature-deploy: ## Deploy feature workspace using Docker (Usage: make docker-feature-deploy config=... env=dev branch=feature/x)
	@if [ -z "$(config)" ]; then echo "Error: config argument required"; exit 1; fi
	@if [ -z "$(env)" ]; then echo "Error: env argument required"; exit 1; fi
	@if [ -z "$(branch)" ]; then echo "Error: branch argument required"; exit 1; fi
	$(DOCKER_PREFIX) docker run --rm --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) \
	deploy "$(config)" --env "$(env)" --branch "$(branch)" --force-branch-workspace

docker-onboard: ## Full bootstrap using Docker (Usage: make docker-onboard org="Org" project="Proj" [stages="dev,test,prod"] ENVFILE=.env)
	@if [ -z "$(org)" ]; then echo "Error: org argument required"; exit 1; fi
	@if [ -z "$(project)" ]; then echo "Error: project argument required"; exit 1; fi
	$(DOCKER_PREFIX) docker run --rm --entrypoint python --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) \
	-m usf_fabric_cli.scripts.dev.onboard --org "$(org)" --project "$(project)" --template $(or $(template),medallion) $(if $(stages),--stages $(stages),)

docker-onboard-isolated: ## Bootstrap with auto-created repo using Docker (Usage: make docker-onboard-isolated org="Org" project="Proj" git_owner="Owner" ENVFILE=.env)
	@if [ -z "$(org)" ]; then echo "Error: org argument required"; exit 1; fi
	@if [ -z "$(project)" ]; then echo "Error: project argument required"; exit 1; fi
	@if [ -z "$(git_owner)" ]; then echo "Error: git_owner argument required"; exit 1; fi
	$(DOCKER_PREFIX) docker run --rm --entrypoint python --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) \
	-m usf_fabric_cli.scripts.dev.onboard --org "$(org)" --project "$(project)" --template $(or $(template),medallion) \
	--create-repo --git-provider $(or $(git_provider),github) --git-owner "$(git_owner)" \
	$(if $(ado_project),--ado-project "$(ado_project)",) $(if $(stages),--stages $(stages),)

docker-feature-workspace: ## Create isolated feature workspace using Docker (Usage: make docker-feature-workspace org="Org" project="Proj" ENVFILE=.env)
	@if [ -z "$(org)" ]; then echo "Error: org argument required"; exit 1; fi
	@if [ -z "$(project)" ]; then echo "Error: project argument required"; exit 1; fi
	$(DOCKER_PREFIX) docker run --rm --entrypoint python --env-file $(ENVFILE) -v $$(pwd)/config:/app/config $(DOCKER_IMAGE) \
	-m usf_fabric_cli.scripts.dev.onboard --org "$(org)" --project "$(project)" --template $(or $(template),medallion) --with-feature-branch

docker-bulk-destroy: ## Bulk destroy workspaces using Docker (Usage: make docker-bulk-destroy file=list.txt ENVFILE=.env)
	@if [ -z "$(file)" ]; then echo "Error: file argument required. Usage: make docker-bulk-destroy file=list.txt"; exit 1; fi
	$(DOCKER_PREFIX) docker run --rm --entrypoint python --env-file $(ENVFILE) -v $$(pwd)/$(file):/app/$(file) $(DOCKER_IMAGE) \
	-m usf_fabric_cli.scripts.admin.bulk_destroy $(file)

docker-list-workspaces: ## List all Fabric workspaces using Docker (Usage: make docker-list-workspaces ENVFILE=.env)
	$(DOCKER_PREFIX) docker run --rm --entrypoint python --env-file $(ENVFILE) $(DOCKER_IMAGE) \
	-m usf_fabric_cli.scripts.admin.utilities.list_workspaces

docker-list-items: ## List items in a workspace using Docker (Usage: make docker-list-items workspace="Name" ENVFILE=.env)
	@if [ -z "$(workspace)" ]; then echo "Error: workspace argument required"; exit 1; fi
	$(DOCKER_PREFIX) docker run --rm --entrypoint python --env-file $(ENVFILE) $(DOCKER_IMAGE) \
	-m usf_fabric_cli.scripts.admin.utilities.list_workspace_items "$(workspace)"
