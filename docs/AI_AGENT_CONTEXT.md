# AI Agent Context & Project Architecture

> Reference for AI Assistants working on this codebase

## Project Identity

**Name**: USF Fabric CLI CI/CD
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

### 1. Monorepo / Shared Repository

* **Context**: The project creates workspaces based on **Feature Branches** in a shared Git repository (`GIT_REPO_URL`).
* **Constraint**: It does *not* create new repos. It isolates work via branches (`feature/project-name`).
* **Agent Rule**: When asked to "create a new project", assume a new *folder configuration* and *feature branch*, not a new Git repo.

### 2. Configuration Waterfall

Configuration is resolved in this strict order (managed by `ConfigManager`):

1. **Environment Variables** (Highest priority, used in CI/CD).
2. **.env files** (Local development only).
3. **YAML Config** (Project definitions).
4. **Defaults**.

### 3. Credential Management

* **12-Factor App**: Secrets never stored in code.
* **Fabric**: `FABRIC_TOKEN` is auto-generated from `AZURE_CLIENT_ID` + `SECRET` if missing.
* **Git**: `GITHUB_TOKEN` is required for the "Unifed Onboarding" flow to create branches.
  * *Constraint*: Token user must have **Write** access to the repo.

## Core Workflows

### 1. Unified Onboarding (`make onboard`)

**Command**: `make onboard org=Acme project=Sales template=medallion`
**Process**:

1. Generates YAML config in `config/projects/`.
2. Creates `feature/sales` branch locally.
3. **Pushes** branch to origin (critical step).
4. Deploys Fabric Workspace and connects it to the branch.

### 2. Medallion Architecture

**Template**: `templates/blueprints/medallion.yaml`
**Standard**:

* `Bronze` (Raw)
* `Silver` (Enriched)
* `Gold` (Curated)
**Agent Rule**: Future data engineering tasks should adhere to this separation.

## Deployment Logic

* **Atomic Rollbacks**: If a deployment fails, `DeploymentState` attempts to delete created items (LIFO).
* **Propagation Latency**: Fabric API item creation (Lakehouses/Warehouses) may fail if the Workspace ID hasn't propagated. Retries or Git Sync resolve this.

## Directory Structure

* `src/usf_fabric_cli`: Core package.
* `scripts/dev`: Developer tools (`generate_project.py`, `onboard.py`).
* `scripts/admin`: Admin tools (`preflight_check.py`).
* `config/`: Usage configurations (ignored by git except templates).
* `webapp/`: Documentation/Dashboard frontend.
