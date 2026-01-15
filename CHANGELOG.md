# Changelog

All notable changes to this project will be documented in this file.

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
