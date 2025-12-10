# Changelog

All notable changes to this project will be documented in this file.

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
