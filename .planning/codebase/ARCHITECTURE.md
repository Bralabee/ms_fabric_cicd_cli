# Architecture

**Analysis Date:** 2026-02-26

## Pattern Overview

**Overall:** Layered CLI + Service-Oriented Architecture

**Key Characteristics:**
- Thin wrapper pattern around official Microsoft Fabric CLI
- Service-based orchestration with clear separation of concerns
- Configuration-driven deployment (YAML-based, org-agnostic)
- 12-Factor App compliance for credential management
- Modular CLI commands via Typer framework
- Embedded FastAPI web application for interactive guides

## Layers

**CLI Layer:**
- Purpose: Command-line entry points for deployment, onboarding, and administration
- Location: `src/usf_fabric_cli/cli.py`
- Contains: Typer command definitions, argument/option parsing
- Depends on: Services layer, configuration manager, secrets manager
- Used by: End users via `usf_fabric_cli` command (installed via pip)

**Service Orchestration Layer:**
- Purpose: Core deployment orchestration coordinating multiple services
- Location: `src/usf_fabric_cli/services/deployer.py` (main: `FabricDeployer` class)
- Contains: Deployment workflow, state management, error handling, audit logging
- Depends on: Fabric wrapper, git integration, deployment pipeline, token manager, audit logger
- Used by: CLI commands

**Fabric Integration Layer:**
- Purpose: Abstraction over Microsoft Fabric CLI and REST APIs
- Location: `src/usf_fabric_cli/services/` (multiple files)
- Contains:
  - `fabric_wrapper.py`: Thin wrapper around Fabric CLI with idempotency handling
  - `fabric_git_api.py`: REST API-based Fabric Git integration
  - `fabric_api_base.py`: Base HTTP client for Fabric API calls
  - `deployment_pipeline.py`: Fabric Deployment Pipeline API integration
- Depends on: Official Fabric CLI, Fabric REST API, Token manager
- Used by: Deployer, CLI commands

**Configuration & Secrets Layer:**
- Purpose: Load, validate, and manage configurations and credentials
- Location: `src/usf_fabric_cli/utils/`
- Contains:
  - `config.py`: Configuration loading with environment overrides and validation
  - `secrets.py`: 12-Factor App credential resolution (env vars → .env → Azure Key Vault)
  - `token_manager.py`: Azure AD token refresh for long-running deployments
- Depends on: YAML loader, Azure SDK, environment variables
- Used by: Deployer, services

**Utilities Layer:**
- Purpose: Cross-cutting concerns
- Location: `src/usf_fabric_cli/utils/`
- Contains:
  - `audit.py`: JSONL-format audit logging
  - `templating.py`: Jinja2-based artifact transformation
  - `retry.py`: Exponential backoff retry logic with idempotent error detection
  - `telemetry.py`: Telemetry event logging
- Depends on: Python standard library, external integrations
- Used by: All layers

**Script/CLI Tools Layer:**
- Purpose: Standalone scripts for project generation, onboarding, diagnostics
- Location: `src/usf_fabric_cli/scripts/`
- Contains:
  - `dev/generate_project.py`: Template-based project configuration generation
  - `dev/onboard.py`: End-to-end project onboarding automation
  - `admin/preflight_check.py`: Installation and dependency verification
  - `admin/bulk_destroy.py`: Batch workspace cleanup
  - `admin/utilities/`: Helper scripts for Git repo setup, diagnostics, migration analysis
- Depends on: Services layer, configuration manager
- Used by: CLI commands, CI/CD pipelines

**Web Application Layer (Optional):**
- Purpose: Interactive guide and scenario explorer for deployments
- Location: `webapp/`
- Contains:
  - `backend/`: FastAPI application with scenario, progress, and search APIs
  - `frontend/`: React/TypeScript UI with Vite build system
- Depends on: Core services (indirectly via content loader)
- Used by: Browser-based guided deployment

## Data Flow

**Deployment Flow (Core Workflow):**

1. **Initialization** (`deploy` CLI command)
   - Load `.env` or environment variables
   - Parse CLI arguments (config path, environment, branch, etc.)
   - Load configuration YAML from `config/projects/`

2. **Configuration Resolution** (ConfigManager)
   - Load base YAML configuration
   - Apply environment-specific overrides (dev.yaml, staging.yaml, prod.yaml)
   - Substitute environment variables in config
   - Validate against JSON schema

3. **Credential Setup** (FabricSecrets)
   - Attempt to load FABRIC_TOKEN from environment
   - If missing, auto-generate from AZURE_CLIENT_ID + AZURE_CLIENT_SECRET
   - Validate Azure authentication
   - Create TokenManager for proactive token refresh during long deployments

4. **Workspace Creation** (FabricCLIWrapper)
   - Create workspace via `fab workspace create`
   - Cache workspace ID for subsequent operations
   - Handle idempotent "already exists" errors

5. **Folder Structure Creation**
   - Create numbered folders per configuration

6. **Item Creation** (Lakehouses, Warehouses, Notebooks, etc.)
   - Create items via `fab item create` commands
   - Template-transform item definitions via Jinja2 if needed

7. **Git Connection** (FabricGitAPI)
   - If git_repo specified in config, connect workspace to repo via REST API
   - Set branch and directory configuration

8. **Deployment Pipeline Setup** (if configured)
   - Create or link deployment pipeline stages
   - Configure stage workspaces (Dev, Test, Prod)

9. **Principal Assignment**
   - Assign users/service principals to workspace with specified roles
   - Handle idempotent role assignment errors

10. **Audit Logging** (AuditLogger)
    - Log all operations to JSONL file in `audit_logs/`
    - Include timestamps, operation results, error details

11. **Summary Output**
    - Display deployment results via Rich formatted tables

**Feature Branch Workspace Flow:**

1. Validate or create feature branch (e.g., `feature/project-name`)
2. Push branch to Git remote
3. Deploy workspace connected to feature branch instead of main
4. CI/CD pipeline auto-creates on `feature/*` push, auto-destroys on PR merge

**Token Refresh Flow (for long deployments):**

1. TokenManager monitors token expiration (Azure tokens expire ~60 min)
2. On expiration, auto-refreshes from Azure using AZURE_CLIENT_ID + SECRET
3. Updates FABRIC_TOKEN in environment and FabricCLIWrapper
4. Continues deployment without interruption

**State Management:**

- **Workspace State**: Tracked by `DeploymentState` class
  - Maintains mapping of workspace name → ID
  - Stores item creation results (IDs, errors)
  - Used for rollback on failure (if --rollback-on-failure enabled)
- **Git State**: Tracked by `GitFabricIntegration` and `FabricGitAPI`
  - Current branch, remote state, dirty-state detection
  - Workspace-Git connection status

## Key Abstractions

**FabricDeployer:**
- Purpose: Orchestrates entire deployment lifecycle
- Examples: `src/usf_fabric_cli/services/deployer.py`
- Pattern: Coordinator pattern with dependency injection

**FabricCLIWrapper:**
- Purpose: Thin wrapper providing idempotency, error handling, version validation
- Examples: `src/usf_fabric_cli/services/fabric_wrapper.py`
- Pattern: Facade pattern, wraps subprocess calls to Fabric CLI

**FabricGitAPI:**
- Purpose: REST API-based workspace-Git connection management
- Examples: `src/usf_fabric_cli/services/fabric_git_api.py`
- Pattern: API client pattern with retry logic

**ConfigManager:**
- Purpose: Loads YAML configs with environment overrides and validation
- Examples: `src/usf_fabric_cli/utils/config.py`
- Pattern: Configuration object pattern with schema validation

**FabricSecrets:**
- Purpose: 12-Factor App credential resolution (environment → .env → Azure Key Vault)
- Examples: `src/usf_fabric_cli/utils/secrets.py`
- Pattern: Fallback/chain of responsibility pattern

**ArtifactTemplateEngine:**
- Purpose: Jinja2-based transformation of item definitions for environment-specific configs
- Examples: `src/usf_fabric_cli/utils/templating.py`
- Pattern: Template engine pattern

**DeploymentState:**
- Purpose: Tracks deployment progress and created items for rollback capability
- Examples: `src/usf_fabric_cli/services/deployment_state.py`
- Pattern: State object pattern

## Entry Points

**Primary CLI Entry Point:**
- Location: `src/usf_fabric_cli/cli.py`
- Triggers: `usf_fabric_cli deploy` command
- Responsibilities:
  - Parse CLI arguments
  - Load .env
  - Instantiate FabricDeployer
  - Call deployer.deploy() with config and options
  - Handle errors and display results

**Secondary CLI Commands:**
- `usf_fabric_cli onboard`: End-to-end onboarding (calls `dev/onboard.py`)
- `usf_fabric_cli generate-project`: Generate project config from templates
- `usf_fabric_cli promote`: Deployment pipeline promotion
- `usf_fabric_cli bulk-destroy`: Batch workspace deletion
- `usf_fabric_cli preflight-check`: Verify installation and dependencies
- `usf_fabric_cli init-github-repo`: Initialize GitHub integration
- Various admin utilities: `debug-ado-access`, `list-workspaces`, `list-workspace-items`, etc.

**Web Application Entry Point (Optional):**
- Location: `webapp/backend/app/main.py`
- Triggers: FastAPI server startup
- Responsibilities:
  - Load scenarios on startup (lifespan context manager)
  - Serve scenario endpoints
  - Provide search and progress tracking APIs
  - Serve frontend React app

**Script Entry Points:**
- `usf_fabric_cli.scripts.dev.generate_project`: Generate YAML configs from templates
- `usf_fabric_cli.scripts.dev.onboard`: Unified onboarding automation
- `usf_fabric_cli.scripts.admin.preflight_check`: Pre-deployment validation

## Error Handling

**Strategy:** Layered error handling with specific exception types and recovery mechanisms

**Custom Exceptions** (in `src/usf_fabric_cli/exceptions.py`):
- `FabricCLIError`: Base exception for CLI command failures (exit code, stderr, stdout capture)
- `FabricCLINotFoundError`: CLI binary not on PATH
- `FabricTelemetryError`: Telemetry logging failures

**Idempotency Patterns** (in `fabric_wrapper.py`):
- Detect "already exists" errors via pattern matching
- Return success for idempotent operations
- Patterns detected: "already exists", "duplicate", "already has a role assigned", "an item with the same name exists"

**Retry Logic** (in `src/usf_fabric_cli/utils/retry.py`):
- Exponential backoff with jitter
- Configurable max retries (default 3)
- Distinguish between retryable (transient) and fatal errors
- Common retryable patterns: rate limiting, timeout, transient network errors

**Rollback on Failure:**
- If `--rollback-on-failure` flag enabled, track created items in `DeploymentState`
- On failure, attempt to delete created workspaces/items via FabricCLIWrapper
- Logged to audit trail

**Validation:**
- Configuration validation via JSON schema before deployment
- Workspace name ASCII validation (no non-ASCII characters in feature workspace names)
- Branch existence validation
- Azure credential validation

## Cross-Cutting Concerns

**Logging:**
- Framework: Python `logging` module
- Approach: Named loggers per module, configurable via environment
- Audit: Separate JSONL-format audit logger (`AuditLogger`) for compliance

**Validation:**
- Configuration: JSON schema in `src/usf_fabric_cli/schemas/`
- Input validation: Workspace names, Git branches, capacity IDs
- Credential validation: Azure auth, Fabric token

**Authentication:**
- Credentials: Azure AD service principal (AZURE_CLIENT_ID + AZURE_CLIENT_SECRET)
- Token acquisition: Via Azure SDK or direct FABRIC_TOKEN
- Token refresh: Proactive refresh for deployments >60 min (via TokenManager)

**Audit & Compliance:**
- JSONL-format operational logs in `audit_logs/`
- Fields: timestamp, operation, workspace, status, error details
- Used for regulatory compliance and troubleshooting

**Templating:**
- Framework: Jinja2
- Use case: Environment-specific artifact transformation (notebook names, parameters, etc.)
- Example: `{{ environment }}_lakehouse` becomes `dev_lakehouse` in dev environment

**Telemetry:**
- Optional telemetry collection via `TelemetryClient`
- Captures usage statistics (commands run, deployment success/failure rates)
- Opt-in via environment configuration

---

*Architecture analysis: 2026-02-26*
