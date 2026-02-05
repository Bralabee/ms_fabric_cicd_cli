# Changelog

All notable changes to this project will be documented in this file.

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
- **Blueprint Documentation**: Comprehensive `docs/BLUEPRINT_CATALOG.md` (11K+ lines) with:
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
