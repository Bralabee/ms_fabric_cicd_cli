# AI Agent Context & Project Architecture

> Reference for AI Assistants working on this codebase

## Project Identity

**Name**: USF Fabric CLI CI/CD
**Version**: 1.7.6 (February 2026)
**Purpose**: Enterprise wrapper for Microsoft Fabric CLI to enable standardized CI/CD, Monorepo support, and "One-Click" onboarding.
**Stack**: Python 3.11+, Fabric CLI (MS), Typer, Jinja2, YAML.

## Development Standards

### 1. Code Quality & Formatting

The project enforces strict coding standards to ensure maintainability and consistency.

* **Linting**: `flake8` is authoritative.
  * **Max Line Length**: 88 characters (matching Black).
  * **Configuration**: `.flake8` at project root.
  * **Command**: `flake8 src`
* **Formatting**: `black` is authoritative.
  * **Profile**: black (default).
  * **Command**: `black .`
* **Static Analysis**: `mypy` for type checking.
  * **Command**: `mypy src`
* **Pre-Commit (Recommended)**: Run `make test` or `make lint` before pushing.

### 2. Documentation

* **Docstrings**: Google-style docstrings for all functions and classes.
* **Type Hints**: Mandatory for all function arguments and return values.

## Critical Architectural Decisions

### 1. Dual-Mode Git Repository

* **Shared Repo (default)**: All projects connect to a single `GIT_REPO_URL` from `.env`. Workspaces are isolated via branches (`feature/project-name`).
* **Isolated Repo (opt-in)**: `--create-repo` flag auto-creates a per-project GitHub or ADO repo for full CI/CD isolation.
* **Agent Rule**: When asked to "create a new project", use the default shared mode unless the user specifically requests an isolated repo.

### 2. Main-Centric Development (v1.7.6)

* **Default**: `make onboard` creates a Dev workspace connected to `main` — no feature branch.
* **Isolated**: `make onboard-isolated` creates a per-project repo and onboards to it.
* **Opt-in**: `make feature-workspace` creates an isolated workspace on a new feature branch.
* **CI/CD Lifecycle**: Feature workspaces are auto-created by GitHub Actions on `feature/*` push and auto-destroyed on PR merge.

### 3. Configuration Waterfall

Configuration is resolved in this strict order (managed by `ConfigManager`):

1. **Environment Variables** (Highest priority, used in CI/CD).
2. **.env files** (Local development only).
3. **YAML Config** (Project definitions).
4. **Defaults**.

### 4. Credential Management

* **12-Factor App**: Secrets never stored in code.
* **Fabric**: `FABRIC_TOKEN` is auto-generated from `AZURE_CLIENT_ID` + `SECRET` if missing.
* **Git**: `GITHUB_TOKEN` is required for the "Unified Onboarding" flow to create branches.
  * *Constraint*: Token user must have **Write** access to the repo.

## Core Workflows

### 1. Unified Onboarding (`make onboard`)

**Default (main-centric)**: `make onboard org=Acme project=Sales template=medallion`
**Process**:

1. Generates YAML config in `config/projects/`.
2. Deploys Fabric Workspace connected to `main`.

**Feature workspace (opt-in)**: `make feature-workspace org=Acme project=Sales`
**Process**:

1. Generates YAML config.
2. Creates `feature/sales` branch locally + pushes to origin.
3. Deploys isolated Fabric Workspace connected to the feature branch.

**Isolated repo (opt-in)**: `make onboard-isolated org=Acme project=Sales git_owner=MyOrg`
**Process**:

1. Auto-creates a GitHub repo named `acme-sales`.
2. Generates YAML config with new repo URL.
3. Deploys Fabric Workspace connected to the new repo.

### 2. Deployment Pipeline Promotion (`promote` command)

**Command**: `usf_fabric_cli promote --pipeline-name "MyPipeline" --source-stage Development`
**Process**: Promotes content through Fabric Deployment Pipeline stages (Dev→Test→Prod).
**Automated**: GitHub Actions auto-promotes Dev→Test on push to `main`.

### 3. Medallion Architecture

**Template**: `src/usf_fabric_cli/templates/blueprints/medallion.yaml`
**Standard**:

* `Bronze` (Raw)
* `Silver` (Enriched)
* `Gold` (Curated)
**Agent Rule**: Future data engineering tasks should adhere to this separation.

## Deployment Logic

* **Atomic Rollbacks**: If a deployment fails, `DeploymentState` attempts to delete created items (LIFO).
* **Propagation Latency**: Fabric API item creation may fail if the Workspace ID hasn't propagated. Retries or Git Sync resolve this.

## Directory Structure

* `src/usf_fabric_cli`: Core package.
  * `cli.py`: Typer-based CLI orchestrator (deploy/destroy/validate/promote/onboard).
  * `exceptions.py`: Custom error handling classes.
  * `services/deployer.py`: Main deployment orchestrator.
  * `services/fabric_wrapper.py`: Thin abstraction over `fabric` CLI subprocess calls.
  * `services/fabric_git_api.py`: REST API client for Git integration (ADO + GitHub).
  * `services/fabric_api_base.py`: Base REST client with shared auth, retry, and error handling.
  * `services/deployment_pipeline.py`: Fabric Deployment Pipelines REST API client.
  * `services/deployment_state.py`: Atomic rollback state management.
  * `services/token_manager.py`: Thread-safe Azure AD token refresh.
  * `services/git_integration.py`: *(Deprecated)* Legacy Git sync — superseded by `fabric_git_api.py`.
  * `utils/config.py`: YAML config loader with env-specific overrides + Jinja2 substitution.
  * `utils/secrets.py`: Waterfall credential management (Env Vars → .env → Key Vault).
  * `utils/templating.py`: Jinja2 sandboxed engine for artifact transformation.
  * `utils/audit.py`: Structured JSONL logging for compliance.
  * `utils/telemetry.py`: Lightweight usage tracking (optional).
  * `utils/retry.py`: Exponential backoff with jitter, decorator pattern.
* `src/usf_fabric_cli/scripts/dev`: Developer tools (`generate_project.py`, `onboard.py`).
* `src/usf_fabric_cli/scripts/admin`: Admin tools (`preflight_check.py`, `init_github_repo.py`, `init_ado_repo.py`).
* `src/usf_fabric_cli/templates/blueprints/`: 11 project blueprint YAML templates.
* `config/`: Usage configurations (ignored by git except templates).
* `.github/workflows/`: CI/CD workflows (feature lifecycle, deployment pipeline promotion).
* `webapp/`: Interactive learning guide (FastAPI backend + React frontend).
