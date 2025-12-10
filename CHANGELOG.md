# Changelog

All notable changes to this project will be documented in this file.

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

### Changed
- **Makefile Overhaul**: Restructured `Makefile` with grouped targets (Local Development, Local Operations, Docker Operations) and improved help output.
- **Testing**: Fixed unit tests (`tests/test_fabric_wrapper.py`, `tests/test_secrets.py`) to mock external CLI calls and pass in the CI environment.
- **Environment**: Enforced strict usage of `fabric-cli-cicd` Conda environment.

### Fixed
- **Dependency Management**: Resolved issues with `requests` library in the base environment (though usage is now strictly in `fabric-cli-cicd`).
- **Test Reliability**: Patched `subprocess.run` mocks to handle different call signatures.
