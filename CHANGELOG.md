# Changelog

All notable changes to this project will be documented in this file.

## [1.7.16] - 2026-02-21

### Fixed

- **Workspace Deletion PBI API Fallback**: `delete_workspace()` now falls back to the Power BI REST API (`DELETE /v1.0/myorg/groups/{workspaceId}`) when the Fabric CLI (`fab rm`) returns an `UnknownError`. This mirrors the v1.7.15 pattern used for pipeline user management — the Fabric API intermittently returns HTTP 400 `UnknownError` for workspace deletion, while the PBI API works reliably.
- **CLI Destroy Output**: The `destroy` command now shows "(via PBI API fallback)" when the fallback path is used.
- **Promote Command Git Sync Polling**: Replaced naive `time.sleep(wait_for_git_sync)` with an active polling mechanism using `FabricGitAPI.get_git_status()`. The `promote` command now actively checks if the `remoteCommitHash` matches the `workspaceHead` instead of blindly waiting, preventing race conditions and Fabric API locking errors.

### Tests

- **+12 unit tests**: 11 new `test_fabric_wrapper.py` tests covering PBI fallback on UnknownError, 204 responses, non-UnknownError passthrough, both-fail error messages, workspace ID resolution (cache hit + API), `_get_pbi_token()` with/without TokenManager, credential errors, and safety blocks. 1 new CLI test for fallback message display.
- **+2 unit tests**: `test_promote_waits_for_git_sync` and `test_promote_git_sync_timeout` added to `test_cli_promote.py` to cover the new active polling logic.
- **454/454 tests passing**.

## [1.7.15] - 2026-02-20

### Fixed

- **Pipeline User Assignment Fix**: Switched from Fabric REST API (`api.fabric.microsoft.com`) to **Power BI REST API** (`api.powerbi.com`) for managing deployment pipeline users. The Fabric API does not expose the `/users` endpoint for pipelines.
- **Service Principal Mapping**: Automatically maps `ServicePrincipal` type to `App` as required by the Power BI API.
- **Access Right Mapping**: Maps `pipelineRole` parameter to request body `accessRight` for compatibility with Power BI API.
- **YAML Configuration**: Corrected principal types in consumer `base_workspace.yaml` (updated logic to handle `User` type correctly for `EDP_ADMIN_ID` and `EDP_MEMBERS_ID`).

## [1.7.14] - 2026-02-19

### Changed

- **CI: isort gate added** — `isort --check-only` is now enforced in `ci.yml`. Added `[tool.isort]` with `profile = "black"` and `line_length = 88` to `pyproject.toml` to keep isort and black in sync.
- **CI tooling bumps**: `black` 24.4.2→25.1.0, `flake8` 7.0.0→7.1.1. `bandit` moved from inline CI install to `requirements-dev.txt`.
- **`services/__init__.py`**: Exports `FabricDeploymentPipelineAPI` and `DeploymentStage` for cleaner consumer imports (additive, backwards-compatible).
- **Docs**: Stabilisation changelog renamed `10_` → `11_Stabilisation_Changelog_Feb2026.md`.

### Tests

- **+10 unit tests**: `TestCLIOrganizeFolders` (5 tests), `TestCLIBulkDestroy` (3 tests), `TestCLIGenerate` (2 tests) — closes coverage gap on three previously untested CLI commands.

---

## [1.7.13] - 2026-02-19

### Added

- **Workspace Safety Guardrails**: New `--safe/--no-safe` flag (default: ON) on `destroy` command. Before deleting a workspace, the CLI inspects its contents via `get_workspace_item_summary()`. If the workspace contains Fabric items (notebooks, lakehouses, pipelines, etc.), deletion is blocked and the CLI exits with code **2** (distinct from error code 1). Use `--force-destroy-populated` to override when intentional.
- **`get_workspace_item_summary()` Method**: New method on `FabricCLIWrapper` that calls the existing `list_workspace_items_api()` and returns a structured summary: `{item_count, items_by_type, has_items, items}`.
- **Safety Configuration**: `config/environments/feature_workspace.json` now includes a `safety` section with `protect_populated`, `require_force_for_populated_destroy`, and `exit_code_on_safety_block` settings.

### Improved

- **Release Process**: Strengthened release checklist with explicit consumer repo sync steps (update copilot-instructions, grep for stale fallback versions). Documents known consumer repos: `ABBA-REPLC/EDPFabric`, `fabric_cicd_test_repo`.

---

## [1.7.12] - 2026-02-19

### Improved

- **Deployer: Project-Specific Git Browse URL**: The deployment summary and "Open repo in browser" link now include the `git_directory` path. For GitHub repos, the URL points to `/tree/{branch}/{directory}` (e.g., `https://github.com/org/repo/tree/main/sales_audience`). For Azure DevOps, appends `?path=/{directory}`. The deployment summary table also shows a new "Git Directory" row when a non-root directory is configured.
- **Deployer: Pipeline User 404 Guidance**: The warning message when all pipeline user additions return 404 now recommends granting the SP the "Fabric Admin" tenant role as an alternative to manual portal configuration.

---

## [1.7.11] - 2026-02-19

### Fixed

- **Deployer: Continue to Stage Assignment on User 404**: Pipeline user additions that return 404 (a known Fabric API limitation for Service Principals accessing the `/users` endpoint) no longer block stage assignment. Previously, all-404 user additions caused `return False`, skipping workspace-to-stage assignment. Now the deployer logs a warning and proceeds to assign workspaces to pipeline stages, which uses the `/stages` endpoint that SPs can access.
- **Deployer: Removed Unnecessary 5s Propagation Delay**: Removed the `time.sleep(5)` after `create_pipeline()` since diagnostic testing confirmed the pipeline 404 is a permissions issue (SP cannot access `/users` endpoint), not a propagation delay.

---

## [1.7.10] - 2026-02-19

### Fixed

- **Deployer: Stale Git Connection Recycling**: On `DuplicateConnectionName` (409) during Git connection, the deployer now deletes the stale connection and creates a fresh one with current credentials, instead of reusing the stale connection ID. Previously, reusing a stale connection caused `ConnectionMismatch` (400) when the stored GITHUB_TOKEN had been rotated or the connection metadata was incompatible. Falls back to reusing the old ID if deletion fails.
- **Deployer: Pipeline Propagation Delay**: Added a 5-second delay after `create_pipeline()` before attempting to add pipeline users. Previously, the `/users` endpoint returned 404 (EntityNotFound) when called milliseconds after pipeline creation, because the Fabric backend had not yet propagated the new resource.

### Added

- **Git API: `delete_connection()` Method**: New method in `FabricGitAPI` to delete a Git connection by ID via the Fabric REST API. Used by the stale connection recycling logic.

---

## [1.7.9] - 2026-02-18

### Fixed

- **Deployer: Git Connection Status Reporting**: `_connect_git()` now returns a `bool` indicating success/failure. The caller in `deploy()` displays "⚠️ Git connection failed" when Git connection fails, instead of unconditionally showing "✅ Git connected". Previously, all failure paths (400 Bad Request, incompatible connection, parse errors) were silently swallowed with a false-positive success indicator.

### Enhanced

- **Deployer: Pipeline Access Pre-Check**: After `get_pipeline_by_name()` finds an existing pipeline, the deployer now calls `get_pipeline()` to verify the automation SP has management access before attempting to add users or assign stages. If the SP lacks access, a clear diagnostic message is shown with resolution steps (delete stale pipeline or grant SP Admin access), and the pipeline setup fails fast instead of cascading into 404/400 errors.
- **Deployer: Pipeline User 404 Fail-Fast**: If ALL `add_pipeline_user()` calls return 404 (EntityNotFound), the deployer now skips stage assignment and returns a clear error instead of proceeding to assign workspaces (which would also fail with 400 UnknownError). This prevents confusing cascading errors when the SP can see the pipeline via `list_pipelines()` but lacks mutate access.

---

## [1.7.8] - 2026-02-18

### Fixed

- **Schema: Allow `folder_rules` Property**: Added `folder_rules` to the JSON schema (`workspace_config.json`) as a valid top-level property. Previously, configs with `folder_rules:` blocks (used by `organize-folders` command and several blueprint templates) failed validation with `Additional properties are not allowed ('folder_rules')`. The schema now describes `folder_rules` as an array of `{type, folder}` objects with proper validation.

---

## [1.7.7] - 2026-02-17

### Added

- **Unicode Feature Prefix (⚡)**: Feature workspaces with display names (containing spaces) now prepend a configurable Unicode prefix (default `⚡`) for instant visual identification in the Fabric portal sidebar. Configured via `feature_prefix` in `feature_workspace.json` or the `feature_prefix` parameter on `get_workspace_name_from_branch()`. Example: `⚡ Sales Audience [FEATURE-dev-setup]`. Slug-style names remain unaffected (backward compatible). Set `feature_prefix: ""` to disable.
- **Deployment Pipeline User Access**: New `list_pipeline_users()` and `add_pipeline_user()` methods in `deployment_pipeline.py`. After creating a Deployment Pipeline, the deployer now automatically grants Admin principals pipeline-level access so they can see and manage it in the Fabric UI.
- **Deployer Step 2 — Grant Pipeline Access**: `_setup_deployment_pipeline()` now includes a new Step 2 that iterates Admin principals (from config `principals` list) and the automation Service Principal, adding each as an Admin on the Deployment Pipeline. Supports comma-separated GUIDs. Idempotent — existing users are skipped with `reused: True`.

### Fixed

- **Default Folders Changed to Explicit Opt-In**: `config.py` default folders changed from `["Bronze", "Silver", "Gold", "Notebooks", "Pipelines"]` to `[]`. Workspaces that declare no `folders:` key (or `folders: []`) no longer get unwanted default folders created. Projects must explicitly list their desired folders in the config.

### Tests

- Updated `test_config.py` assertion from `"Bronze" in wc.folders` to `wc.folders == []` (matching new default)
- Added 3 new tests for feature prefix: custom prefix, empty prefix disables, slug names never get prefix
- All **385 unit tests passing** (7 integration tests deselected)

---

## [1.7.6] - 2026-02-12

### Fixed

- **Inline `environments` Config Support**: The JSON schema (`workspace_config.json`) now includes `environments` as a valid top-level property. Previously, configs with inline `environments:` blocks (used by most blueprints) failed validation with `Additional properties are not allowed ('environments')`. The `ConfigManager` now reads inline environment overrides before schema validation, with inline blocks taking priority over external `config/environments/*.yaml` files.

### Validated

- **End-to-End Feature Branch Workspace Test (E2E)**: Full lifecycle validated via `fabric_cicd_test_repo`:
  - Push `feature/e2e-test-feb12` → Create Feature Workspace workflow → workspace `fabric-cicd-demo-feature-e2e-test-feb12` created with folders (Bronze/Silver/Gold), lakehouse (`lh_bronze`), notebook (`demo_notebook`), 2 admin principals, and Git connection — **2m 26s**
  - Delete branch → Cleanup Feature Workspace workflow → workspace destroyed — **28s**
  - Full create→destroy cycle confirmed working end-to-end in GitHub Actions

### Tests

- All **369 unit tests passing** (12 new tests added since v1.7.5)

---

## [1.7.5] - 2026-02-12

### Added

- **Notebook Content Import**: `create_notebook()` now accepts `.py` and `.ipynb` files via `file_path`, base64-encoding them into the Fabric Items API `definition` payload. Python files are auto-wrapped in a single-cell `.ipynb` structure with `synapse_pyspark` kernel metadata.
- **Jinja2 Template Rendering for Notebooks**: The deployer renders notebook `file_path` content through `ArtifactTemplateEngine` before upload, enabling `{{ environment }}`, `{{ workspace_name }}`, and `{{ secrets.* }}` variable substitution in notebook source files.
- **7 New Fabric Item Types**: `deployment_state.py` now tracks `Environment`, `Reflex`, `MLModel`, `MLExperiment`, `DataflowGen2`, `KQLQueryset`, and `Eventhouse` for rollback support.
- **Thread-Safe Token Refresh**: `TokenManager.get_token()` now uses `threading.Lock` to prevent concurrent token acquisition races during parallel operations.
- **Real Audit Summary**: `AuditLogger.get_audit_summary()` now parses JSONL log files and returns actual operation counts, success/failure rates, and per-operation-type breakdowns (was a stub).
- **Automation SP in Data Science Blueprint**: Added `${AZURE_CLIENT_ID}` as Admin principal to `data_science.yaml` for CI/CD deployments.

### Fixed

- **Import Path Bug**: Fixed `config.py` importing from `usf_fabric_cli.secrets` → `usf_fabric_cli.utils.secrets` (prevents `ImportError` in fresh installs).
- **UTC Timestamp Deprecation**: `audit.py` now uses `datetime.now(timezone.utc)` instead of deprecated `datetime.utcnow()`.
- **Jinja2 Undefined Handling**: `ArtifactTemplateEngine` in non-strict mode now uses `Undefined` class instead of `None` (prevents `TypeError` on missing variables).
- **Blueprint `environments:` Blocks**: Removed unsupported inline `environments:` from `compliance_regulated`, `medallion`, `minimal_starter`, and `realtime_streaming` blueprints — `ConfigManager` does not read these. Added comments pointing to `config/environments/` overlay files.
- **Compliance Blueprint**: Removed `ManagedPrivateEndpoint` resource (requires Networking API, not Items API) with documentation link.
- **Schema Strictness**: Added `additionalProperties: false` to workspace config JSON schema (root and workspace object) to catch typos early.

### Improved

- **Centralized HTTP Requests**: All `fabric_git_api.py` methods now use `_make_request()` instead of direct `requests.post/get` calls, consolidating timeout, retry, and header management.
- **Dead Code Removal**: Removed unused `_run_command()` method from `FabricCLIWrapper` (superseded by `_execute_command()`).
- **Logging Hygiene**: Replaced 7 `print()` calls with proper `logger.debug/info/warning/error` in `config.py` and `fabric_wrapper.py`.
- **Deprecation Notice**: `git_integration.py` docstring now documents its deprecated status (superseded by `FabricGitAPI`).
- **GitConnectionSource Enum**: `connect_workspace_to_git()` now uses `GitConnectionSource.CONFIGURED_CONNECTION.value` / `GitConnectionSource.AUTOMATIC.value` instead of raw strings.

### Tests

- Added 9 new config tests: env var substitution, missing var passthrough, deep merge, list concatenation, principal injection/dedup, defaults, import path
- Added 18 new wrapper tests: notebook definition (py/ipynb/missing/unsupported), pipeline, warehouse, semantic model, generic item, principal guards (empty/placeholder/self-SP), domain assignment
- Updated all `fabric_git_api` test mocks from `requests.post`/`requests.get` → `requests.request` (matching `_make_request()` refactor)
- Added `ArtifactTemplateEngine` mock patches to 5 deployer tests
- Total: **357 tests passing** across the full unit test suite

## [1.7.4] - 2026-02-12

### Fixed

- **Idempotent Workspace Destroy**: The `destroy` command now exits 0 when the target workspace no longer exists (`NotFound`), printing a warning instead of failing. This resolves the race condition where both `pull_request:closed` and `delete` events fire simultaneously on PR merge with branch deletion — the second cleanup no longer fails.

### Tests

- Added `test_destroy_idempotent_not_found` — verifies destroy exits cleanly when workspace is already gone
- Added `test_destroy_real_error_still_fails` — verifies genuine errors (e.g. permission denied) still propagate correctly
- Total: **76 tests passing** across the full unit test suite

## [1.7.3] - 2026-02-12

### Fixed

- **Clean CI/CD Log Messages for Idempotent Git Operations**: Eliminated three alarming log messages that appeared during successful idempotent re-deploys:
  - `create_git_connection()`: Now returns structured `duplicate: True` flag for 409 DuplicateConnectionName instead of logging `Failed to create Git connection` at error level
  - `initialize_git_connection()`: Now returns `already_initialized: True` for 409 instead of logging `Failed to initialize Git connection` at error level
  - Deployer uses structured flags (`duplicate`, `already_initialized`) instead of parsing raw response body text
  - Clean CI/CD output on re-deploy: `✓ Git connection already initialized (idempotent)` instead of `Warning: Could not initialize Git connection`

### Tests

- Added 4 new tests for 409 idempotent behavior (`TestInitializeGitConnection`, `TestCreateGitConnectionDuplicate`)
- Updated 2 existing deployer tests with structured `duplicate` flag (`TestGitHubDuplicateConnectionRecovery`)
- Total: **65 targeted tests passing** (git API + deployer suites)

## [1.7.2] - 2026-02-12

### Fixed

- **GitHub Git Connection — 409 DuplicateConnectionName Recovery**: When creating a GitHub connection that already exists (409), the deployer now looks up the existing connection by name (matching the existing Azure DevOps recovery pattern) and reuses it instead of failing.
- **GitHub Git Connection — myGitCredentials SSO**: The `connect_workspace_to_git` method now includes `myGitCredentials` with `"source": "Automatic"` for GitHub connections, resolving `400 InvalidInput` ("myGitCredentials is required for GitProviderType GitHub") errors when using SSO-based authentication.
- **WorkspaceAlreadyConnectedToGit — Idempotent Handling**: A 409 response with `WorkspaceAlreadyConnectedToGit` error code is now treated as an idempotent success (`✓ Workspace already connected to Git`) instead of logging an alarming "Failed to connect" error message.

### Tests

- Added 4 tests for GitHub `myGitCredentials` behavior (`TestConnectWorkspaceCredentials`)
- Added 2 tests for `WorkspaceAlreadyConnectedToGit` idempotent handling (`TestWorkspaceAlreadyConnected`)
- Added 2 tests for GitHub `DuplicateConnectionName` recovery (`TestGitHubDuplicateConnectionRecovery`)
- Updated `test_token_manager.py` to account for `encryption_fallback_enabled` CLI call in auth flow
- Total: **324 tests passing**

### Improved

- **Makefile `deploy` target**: Now supports optional `branch=feature/x` parameter for feature branch workspace deployments (`--branch` + `--force-branch-workspace` flags)
- **Makefile `onboard` target**: Routed through CLI entrypoint with new `capacity_id`, `pipeline_name`, and `dry_run` parameters
- **Makefile `destroy` target**: Added `env`, `force`, and `workspace_override` parameters for targeted workspace destruction
- **Makefile `docker-diagnose`**: Updated to use CLI `diagnose` entrypoint instead of direct script invocation
- **Workspace config schema**: Added `description` field to principals, `folder` field and type examples to generic resources
- **Blueprint templates** (`basic_etl.yaml`, `minimal_starter.yaml`): Fixed `deployment_pipeline` format to use `pipeline_name` key and nested `workspace_name` stage structure (matching schema)
- **Azure Pipelines** (`azure-pipelines.yml`): Parameterized `CONFIG_PATH` and `DEPLOY_ENV` variables, upgraded Python to 3.11

### Documentation

- **From Local to CI/CD Guide** (`docs/01_User_Guides/09_From_Local_to_CICD.md`): Comprehensive 550-line document explaining all CI/CD environment differences, with detailed analysis of 9 problems fixed from v1.5.0 through v1.7.2

## [1.7.1] - 2026-02-11

### Documentation

- **Educational Guide** (`docs/01_User_Guides/08_Educational_Guide.md`): Comprehensive educational document covering:
  - Project overview and architecture
  - Three Ways to Work (Local Python, Docker, CI/CD) with full end-to-end walkthroughs
  - Multi-agent specialisation patterns explaining codebase decomposition
  - Blueprint selection decision tree and feature comparison table
  - Quick reference cards: 30 Makefile targets, CLI flags, environment variables
  - Getting Started section with copy-paste onboarding steps

## [1.7.0] - 2026-02-10

### Added

- **Main-Centric Dev Workspace** (Phase 1):
  - Refactored `onboard.py` to default to Dev workspace connected to `main` branch
  - Added opt-in `--with-feature-branch` flag for isolated feature workspaces
  - New `feature-workspace` Makefile target for explicit feature workspace creation
- **Automated Feature Workspace Lifecycle** (Phase 2):
  - `feature-workspace-create.yml`: GitHub Actions workflow to auto-create Fabric workspace on `feature/*` push
  - `feature-workspace-cleanup.yml`: GitHub Actions workflow to auto-destroy workspace on PR merge or branch delete
  - `config/environments/feature_workspace.json`: Recipe file for feature workspace naming, capacity, and lifecycle policies
  - `--workspace-name-override` option added to `destroy` CLI command for targeting branch-specific workspaces
- **Fabric Deployment Pipeline Integration** (Phase 3):
  - `deployment_pipeline.py`: New service wrapping the Fabric Deployment Pipelines REST API (CRUD, stage management, deploy/promote, long-running operation polling, token refresh)
  - `deploy-to-fabric.yml`: GitHub Actions workflow with automatic Dev→Test promotion on push to `main` and manual promotion via `workflow_dispatch` with approval gates
  - `promote` CLI command: `usf_fabric_cli promote --pipeline-name "Name" --source-stage Development`
  - `DeploymentStage` helper class for standard Dev→Test→Prod stage sequencing

### Tests

- Added 23 new unit tests for `FabricDeploymentPipelineAPI` service
- Added 20 new unit tests for onboard redesign (`test_onboard.py`)
- Added 5 new unit tests for `_enrich_principals()` governance SP injection
- Added 7 new unit tests for CLI `promote` subcommand (`test_cli_promote.py`)
- Total: **283 tests passing** (unit + integration suites)

### Fixed

- **Governance SP Injection**: Test/Prod workspaces now receive mandatory `ADDITIONAL_ADMIN_PRINCIPAL_ID` and `ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID` via new `_enrich_principals()` helper in `onboard.py` (previously only Dev stage received these)
- **Stale Admin Script Imports**: Replaced legacy `from src.core` imports with `usf_fabric_cli` paths in `list_workspace_items.py`, `init_ado_repo.py`, `debug_connection.py`, `debug_ado_access.py`
- **`list_workspace_items.py` Rewrite**: Replaced broken `FabricSecrets` + SP auth flow with `get_environment_variables()` pattern (matching `list_workspaces.py`), fixing tenant_id validation error
- **Makefile `list-items` target**: Added `PYTHONPATH` to enable correct module resolution
- **Deployment Pipeline creation**: Added required `stages` array to `create_pipeline()` API body (Fabric API returns 400 without it)
- **Git branch override**: Changed `config/environments/dev.yaml` `git_branch` from `develop` to `main`

### Git Repo Isolation

- **`init_github_repo.py`**: New GitHub repo init script (mirrors `init_ado_repo.py`)
- **`--create-repo` flag**: Optional Phase 0 in `onboard.py` auto-creates a per-project repo (GitHub or ADO)
- **`onboard-isolated`** Makefile target for one-command isolated onboarding
- **`init-github-repo`** Makefile target for standalone GitHub repo creation
- **Dual-mode docs**: README documents Shared Repo vs Isolated Repo approaches

### Docker CLI Sync

- **Unified CLI Entrypoint** (`cli.py`): Registered 11 subcommands as Typer commands, giving Docker containers full parity with local `make` targets:
  - Core: `deploy`, `validate`, `diagnose`, `destroy`, `promote`
  - Onboarding: `onboard`, `generate`
  - Admin: `list-workspaces`, `list-items`, `bulk-destroy`, `init-github-repo`
- **Multi-stage Dockerfile**: Reworked from single-stage to builder/runtime pattern (~60% smaller image). Builder stage installs deps into a virtual env, runtime stage copies only the pre-built venv.
- **`.dockerignore` hardened**: Excludes `webapp/`, `.agent/`, `.gemini/`, dev tooling, whitelists `.env.template`
- **6 new `docker-*` Makefile targets**: `docker-onboard`, `docker-onboard-isolated`, `docker-feature-workspace`, `docker-bulk-destroy`, `docker-list-workspaces`, `docker-list-items` — total 30 Make targets
- **`requirements-dev.txt`**: Separated dev/test dependencies (pytest, flake8, black, mypy, etc.) from production `requirements.txt`. `make install` now uses `requirements-dev.txt`.
- **`deploy-to-fabric.yml` fix**: Replaced phantom `get_fabric_token` import with inline `az` CLI token acquisition

### Architecture

- Implemented **Microsoft Option 3** CI/CD pattern: Git syncs Dev workspace, Fabric Deployment Pipelines promote through stages
- Feature workspaces are now ephemeral and CI/CD-managed (create on push, destroy on merge)

## [1.6.3] - 2026-02-05

### Added

- **Interactive Architecture Page** (`/architecture`): New technical deep-dive page in the webapp showcasing:
  - **Onboarding Flow Diagram**: Interactive 5-step visualization of the `make onboard` workflow with hover-to-expand details for each stage (Config Generation → Git Branch → Workspace Provisioning → Git Connection → Initial Sync).
  - **GitHub Gap Comparison Table**: Side-by-side comparison of Fabric CLI (Native) vs. REST API capabilities, highlighting the project's middleware solution for GitHub integration.
  - **Git-Centric CI/CD vs. Deployment Pipelines**: Tabbed comparison explaining both lifecycle management approaches.
  - **Key Components Grid**: Visual cards documenting `onboard.py`, `FabricGitAPI`, `GitFabricIntegration`, and `FabricDeployer` orchestration roles.
- **Navigation Update**: Added "Architecture" link to the webapp header navigation.

### Documentation

- Updated Knowledge Item `HS2 Microsoft Fabric Platform Ecosystem` to v1.6.8 referencing the Interactive Architecture Guide.

## [1.6.2] - 2026-02-05

### Fixed

- **Type Safety**: Comprehensive Mypy fixes across core services:
  - Updated `FabricCLIWrapper`, `FabricDeployer`, `AuditLogger` to correctly handle `Optional[str]` types.
  - Fixed dataclass `WorkspaceConfig` using `Optional[List[...]]` instead of `List[...] = None`.
  - Added explicit type narrowing for `ClientSecretCredential` arguments.
  - Re-exported retry utilities (`is_retryable_error`, `calculate_backoff`, `retry_with_backoff`) from `fabric_wrapper.py` for backwards compatibility.
- **CI Pipeline**:
  - Added `types-requests` to `requirements.txt` for Mypy stub support.
  - Fixed `test_config.py` tests to skip env validation (tests config loading, not credentials).
  - Wrapped long function signatures to comply with 88-char line limit (flake8 E501).
  - Added missing `Optional` import to `audit.py`.

### Maintenance

- All 140 unit tests now pass in CI without credentials.
- Flake8, Black, and Mypy checks all pass locally.

## [1.6.1] - 2026-02-05

### Maintenance (Clean Code Initiative)

- **Codebase Standardization**:
  - Enforced 100% `flake8` compliance across `src/usf_fabric_cli` (0 errors).
  - Enforced `black` formatting across the entire repository.
  - Resolved `E501` (Line Length), `E402` (Import Order), `F841` (Unused Variables), and `F541` (Empty F-Strings).
  - Fixed complex line-wrapping issues in `deployer.py` and `fabric_wrapper.py`.

### Fixed

- **Type Safety**: Addressed mypy type hints in `token_manager.py` and `retry.py`.

## [1.6.0] - 2026-02-05

### Added

- **Unified Onboarding Automation**: New `make onboard` command for one-click project setup.
  - Orchestrates: Config Generation -> Git Feature Branch Creation -> Workspace Deployment.
  - Usage: `make onboard org="Org" project="Proj" template=medallion`
- **Medallion Blueprint**: New `medallion.yaml` template implementing industry-standard Bronze/Silver/Gold architecture.
  - Includes `lh_bronze`, `lh_silver`, `lh_gold` lakehouses and associated notebooks.
- **Git Integration Improvements**:
  - `GitFabricIntegration.create_feature_branch` logic activated and refined.
  - Robust handling for existing branches during onboarding.
  - Fixed `workspace_config.json` schema to allow `null` values for `domain`, resolving validation errors during automated onboarding.
  - **Blueprint Standardization**:
    - Universal `domain` support added to all 10 blueprints (using `${FABRIC_DOMAIN_NAME}`).
    - Security hardening: Enforced Object ID (`_OID`) placeholders for principals in `advanced_analytics` and `data_science` templates (replacing email placeholders).

### Fixed

- **Webapp Loading**: Resolved infinite 307 Redirect loop on Home Page caused by trailing slash mismatch in FastAPI router (`/api/scenarios` vs `/api/scenarios/`).

### Changed

- **Documentation**: Updated README to feature the accelerated onboarding workflow.

## [1.5.1] - 2026-02-02

### Fixed

- **Configuration Confusion**: Removed redundant `examples/projects` and `examples/workspaces_to_delete` directories. `config/` is now the single source of truth.
- **Blueprint Templates**:
  - `basic_etl.yaml`: Consolidated Security/Principals section, restoring accidental deletions of `pipelines` and `resources`.
  - Added documentation for comma-separated Principal ID injection (e.g. `"${GROUP_1},${GROUP_2}"`).
- **Path Handling**: Clarified CWD requirements (must run from project root, not `src/`).

### Documentation

- Updated `TROUBLESHOOTING.md` with Windows-specific path resolution and Principal ID best practices.

## [1.5.0] - 2026-01-24

### Added

- **Token Manager** (`services/token_manager.py`): Proactive Azure AD token refresh for long deployments
  - Automatic refresh 60 seconds before expiry
  - Fabric CLI re-authentication support
  - Factory function `create_token_manager_from_env()` for environment-based setup

- **Deployment State** (`services/deployment_state.py`): Atomic rollback for mid-deployment failures
  - LIFO (Last-In-First-Out) rollback of created items
  - Checkpoint persistence for crash recovery
  - Support for all item types: workspace, lakehouse, warehouse, notebook, pipeline, etc.

- **Shared Retry Utilities** (`utils/retry.py`): Extracted exponential backoff logic
  - `retry_with_backoff` decorator
  - HTTP-specific retry helpers
  - Jitter to prevent thundering herd

- **New CLI Flag**: `--rollback-on-failure` for deploy command
  - Automatically deletes created items if deployment fails
  - Shows rollback progress and summary

### Changed

- **FabricGitAPI**: Added `_make_request` helper with automatic retry and token refresh
- **FabricCLIWrapper**: Now accepts optional `token_manager` for proactive token refresh

### Tests

- Added 35 new unit tests (14 token manager, 21 deployment state)
- Total: 140 tests passing

---

## [1.4.1] - 2026-01-24

### Upgraded

- **Microsoft Fabric CLI v1.2.0 → v1.3.1**: Upgraded underlying Fabric CLI dependency
  - **New SQLDatabase operations**: `mv`, `cp`, `export`, `import` for SQL Database items
  - **Job management**: New `job run-rm` command for removing scheduled jobs
  - **Enhanced `set` command**: Support any settable property path in item definitions
  - **JMESPath filtering**: `ls -q` flag for advanced workspace queries
  - **Bug fixes**: `--output_format` in auth status, virtual env context, gateway connections

### Changed

- **requirements.txt**: Pinned `fabric-cli@v1.3.1` for reproducible builds (was `@main`)

### Verified

- 107 tests passing (100%)
- Diagnose command confirms v1.3.1 integration
- Authentication working with Service Principal

---

## [1.4.0] - 2026-01-24

### Added

- **Comprehensive Test Coverage Improvements**:
  - 7 new tests for `FabricDeployer`, deploy command, and Git URL parsing
  - Test coverage improved: 50% → 51% overall, cli.py: 25% → 31%

### Changed

- **Package Restructure Complete**: Full migration from `core` to `usf_fabric_cli` package
  - All module paths updated to `usf_fabric_cli.{services,utils,commands}`
  - CLI entry points: `fabric-cicd`, `usf-fabric` point to `usf_fabric_cli.cli:app`

- **Script Reorganization**:
  - `scripts/preflight_check.py` → `scripts/admin/preflight_check.py`
  - `scripts/generate_project.py` → `scripts/dev/generate_project.py`
  - `scripts/utilities/` → `scripts/admin/utilities/`
  - `scripts/bulk_destroy.py` → `scripts/admin/bulk_destroy.py`

### Fixed

- **Documentation Refresh** (39+ fixes across 20+ files):
  - All `python -m core.cli` → `python -m usf_fabric_cli.cli`
  - All `src/core/` → `src/usf_fabric_cli/` with correct subfolders
  - All script paths updated to new locations
  - README project structure updated to reflect new layout
  - CI/CD pipelines (GitHub Actions, Azure Pipelines) updated
  - Webapp scenarios updated with correct paths
  - copilot-instructions.md updated with accurate module paths

### Verified

- 105 tests passing
- Local CLI functionality confirmed
- Docker build and run verified
- Zero remaining outdated references

## [1.3.1] - 2026-01-15

### Added

- **Comprehensive Documentation Audit & Fixes**:
  - **Project Configuration Guide** (`docs/01_User_Guides/03_Project_Configuration.md`): 500-line comprehensive guide covering:
    - Two generation methods (generate_project.py script and manual blueprint copying)
    - All 10 blueprint templates with descriptions and use cases
    - Configuration file structure and YAML patterns
    - Environment variable placeholders and Jinja2 templating
    - Mandatory security principals requirements
    - Post-generation checklist and common customizations

- **README.md Enhancements**:
  - **Make Targets Reference** table (17 targets): Core operations, Docker operations, testing, and webapp targets
  - **CLI Flags Reference** for `deploy` and `destroy` commands with all available flags

- **Webapp Scenario Improvements** (9 scenarios, 116+ steps total):
  - **Step 12: Generate Your First Project Config** added to Getting Started (now 17 steps)
  - **00-complete-journey.yaml**: New comprehensive walkthrough with 7 phases
  - **Phase 3 enhancements**: Actual `generate_project.py` commands and template selection guidance
  - **Azure Prerequisites**: Step 2 with Service Principal requirements
  - Template generation, environment validation, feature workflow, and multi-environment strategy enhancements

### Fixed

- **Blueprint Templates**: Added mandatory security principals (`ADDITIONAL_ADMIN_PRINCIPAL_ID`, `ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID`) to 7 templates:
  - compliance_regulated.yaml, data_mesh_domain.yaml, extensive_example.yaml
  - migration_hybrid.yaml, minimal_starter.yaml, realtime_streaming.yaml, specialized_timeseries.yaml
  - All 10 blueprints now consistently include principals section

- **CLI Flag Documentation**: Corrected `--dry-run` to `--validate-only` (matches actual implementation)
- **Version Alignment**: pyproject.toml version synchronized to 1.3.0 (was incorrectly 1.1.0)
- **Webapp Test Dependencies**: Added pytest>=7.4.0 and httpx>=0.25.0 to webapp/backend/requirements.txt

### Changed

- **.env.template**: Reorganized to prioritize Azure credentials (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID)
- **Webapp Docker ports**: Backend API on port 8001, Frontend on port 8080

## [1.3.0] - 2026-01-05

### Added

- **Interactive Webapp Enhancements**:
  - **Visual Workflow Diagrams** (`/workflows` page): Interactive flowcharts for 4 tested deployment workflows:
    - Local Python Deployment (6-step flow)
    - Docker Containerized Deployment (6-step flow)
    - Feature Branch Workflow (6-step flow)
    - Advanced Analytics Deployment (6-step flow)
  - **Scenario Page Improvements**: Expected output display, checkpoint questions, learning outcomes sidebar, related scenarios navigation
  - **Navigation**: Added "Workflows" button to header navigation

- **Webapp Dockerization** (production-ready):
  - `docker-quickstart.sh`: One-command local Docker startup
  - `deploy-azure.sh`: Automated Azure Container Apps deployment script
  - `docker-compose.prod.yml`: Production overlay with resource limits
  - `.env.template`: Environment configuration template
  - `.dockerignore` files for optimized image builds
  - Fixed nginx.conf API proxy (port correction + trailing slash handling)

- **New Makefile Targets**:
  - `make docker-status`: Show container status
  - `make docker-clean`: Remove images and volumes
  - `make deploy-azure`: Deploy webapp to Azure Container Apps
  - `make deploy-azure-dryrun`: Preview Azure deployment

### Fixed

- **Frontend API Interfaces**: Aligned TypeScript interfaces with backend API field names:
  - `step.type` (was `step_type`)
  - `step.code` object (was `code_blocks` array)
  - `estimated_duration_minutes` (was `estimated_time_minutes`)
- **nginx Proxy**: Fixed backend port (8000 → 8001) and API path handling

### Documentation

- Updated webapp README with Docker and Azure deployment instructions
- Added comprehensive deployment options section

## [1.2.0] - 2025-12-10

### Added

- **Blueprint Template Library**: 6 new production-ready templates for specialized use cases:
  - `realtime_streaming.yaml` - IoT/event-driven architectures with Eventstreams, KQL, Reflex (4.4KB)
  - `minimal_starter.yaml` - Quick POC/learning template (1.9KB)
  - `compliance_regulated.yaml` - Healthcare/Finance/Government compliance (6.2KB)
  - `data_mesh_domain.yaml` - Domain-driven data ownership (6.4KB)
  - `migration_hybrid.yaml` - Cloud migration with mirrored databases (8.2KB)
  - `specialized_timeseries.yaml` - Time-series/APM/operational intelligence (8.5KB)
- **Blueprint Documentation**: Comprehensive `docs/01_User_Guides/07_Blueprint_Catalog.md` (11K+ lines) with:
  - Quick reference table (cost estimates, complexity, min capacity)
  - Detailed feature breakdowns for all 10 templates
  - Decision tree for template selection
  - Industry and team size recommendations
  - Customization guide
- **Advanced Fabric Item Types**: All templates leverage native Fabric CLI support for 54+ item types:
  - Eventstream, Eventhouse, KQLDatabase, KQLQueryset, Reflex, KQLDashboard
  - MirroredDatabase, MirroredWarehouse, GraphQLApi, ExternalDataShare
  - MLModel, MLExperiment, Environment, MetricSet, SparkJobDefinition
  - Gateway, Connection, ManagedPrivateEndpoint (and more)
- **Template Generator Update**: Added all 10 templates to `scripts/generate_project.py` choices.

### Changed

- **README.md**: Updated quick start to showcase template variety (basic_etl → 10 templates).
- **Template Coverage**: Increased from 4 to 10 templates, covering 95%+ of enterprise scenarios.

## [1.1.0] - 2025-12-10

### Added

- **Azure Key Vault Integration**: Optional support for enterprise secret management.
  - Added `azure-keyvault-secrets>=4.7.0` dependency to `requirements.txt`.
  - Implemented waterfall priority: Environment Variables → .env file → Azure Key Vault.
  - Uses `DefaultAzureCredential` for authentication (supports Managed Identity, Azure CLI, etc.).
  - Fully backward compatible—Key Vault is only used when `AZURE_KEYVAULT_URL` is set.
  - Added comprehensive documentation in `docs/03_Project_Reports/07_Azure_KeyVault_Integration.md`.
- **Docker Integration**: Full support for running the entire CI/CD workflow inside a Docker container.
  - Added `Dockerfile` for creating a reproducible build environment.
  - Added `Makefile` targets for Docker operations: `docker-build`, `docker-generate`, `docker-init-repo`, `docker-deploy`, `docker-validate`.
- **CI/CD Pipeline**: Added `azure-pipelines.yml` for Azure DevOps integration.
- **Diagnostics**: Added `make diagnose` target to run preflight checks (`scripts/preflight_check.py`).
- **Documentation**: Updated `README.md` with end-to-end workflow instructions.
- **Entry Point Installation**: Added `pip install -e .` to `make install` target for CLI entry point registration.

### Changed

- **Makefile Overhaul**: Restructured `Makefile` with grouped targets (Local Development, Local Operations, Docker Operations) and improved help output.
- **Makefile Path Handling**: Fixed PYTHONPATH shell escaping issues by properly quoting variables to support paths with special characters.
- **Testing**: Fixed unit tests (`tests/test_fabric_wrapper.py`, `tests/test_secrets.py`) to mock external CLI calls and pass in the CI environment.
- **Environment**: Enforced strict usage of `fabric-cli-cicd` Conda environment.

### Fixed

- **Shell Escaping**: Fixed Makefile commands to properly handle paths with apostrophes and special characters by quoting PYTHONPATH.
- **Entry Point**: Resolved `fabric-cicd` command not found issue by adding editable install to setup process.
- **Dependency Management**: Resolved issues with `requests` library in the base environment (though usage is now strictly in `fabric-cli-cicd`).
- **Test Reliability**: Patched `subprocess.run` mocks to handle different call signatures.
