# Codebase Structure

**Analysis Date:** 2026-02-26

## Directory Layout

```
usf_fabric_cli_cicd/
├── src/usf_fabric_cli/              # Main Python package (installed as editable)
│   ├── cli.py                       # CLI entry point (Typer app)
│   ├── exceptions.py                # Custom exception types
│   ├── __init__.py                  # Package root
│   ├── services/                    # Core orchestration services
│   │   ├── deployer.py              # Main FabricDeployer orchestrator
│   │   ├── fabric_wrapper.py        # Thin wrapper around Fabric CLI
│   │   ├── fabric_git_api.py        # REST API-based Git integration
│   │   ├── fabric_api_base.py       # Base HTTP client for Fabric APIs
│   │   ├── deployment_pipeline.py   # Fabric Deployment Pipeline API
│   │   ├── deployment_state.py      # State tracking for rollback
│   │   ├── git_integration.py       # Local Git repository management
│   │   ├── token_manager.py         # Azure AD token refresh
│   │   └── __init__.py              # Service exports
│   ├── utils/                       # Utility modules
│   │   ├── config.py                # ConfigManager for YAML + env loading
│   │   ├── secrets.py               # FabricSecrets credential resolution
│   │   ├── audit.py                 # AuditLogger for JSONL compliance logging
│   │   ├── templating.py            # ArtifactTemplateEngine (Jinja2)
│   │   ├── retry.py                 # Exponential backoff retry logic
│   │   ├── telemetry.py             # TelemetryClient for usage tracking
│   │   └── __init__.py              # Utility exports
│   ├── scripts/                     # Standalone CLI scripts
│   │   ├── dev/                     # Developer-focused scripts
│   │   │   ├── generate_project.py  # Template-based config generation
│   │   │   ├── onboard.py           # End-to-end onboarding automation
│   │   │   └── __init__.py
│   │   ├── admin/                   # Admin/operator scripts
│   │   │   ├── preflight_check.py   # Installation verification
│   │   │   ├── bulk_destroy.py      # Batch workspace deletion
│   │   │   ├── utilities/           # Helper utilities
│   │   │   │   ├── init_github_repo.py       # GitHub repo initialization
│   │   │   │   ├── init_ado_repo.py         # Azure DevOps repo init
│   │   │   │   ├── debug_connection.py      # Connection debugging
│   │   │   │   ├── debug_ado_access.py      # ADO access debugging
│   │   │   │   ├── list_workspaces.py       # List Fabric workspaces
│   │   │   │   ├── list_workspace_items.py  # List workspace items
│   │   │   │   ├── analyze_migration.py     # Migration analysis
│   │   │   │   └── __init__.py
│   │   │   └── __init__.py
│   │   └── __init__.py
│   ├── templates/                   # Configuration templates
│   │   ├── blueprints/              # YAML blueprint templates
│   │   │   ├── medallion.yaml       # Standard medallion architecture
│   │   │   ├── realtime_streaming.yaml
│   │   │   ├── compliance_regulated.yaml
│   │   │   ├── [8 more blueprints]  # 11 total production-ready templates
│   │   │   └── __init__.py
│   │   └── __init__.py
│   └── schemas/                     # JSON schema validation files
│       └── config_schema.json       # Configuration validation schema
├── tests/                           # Test suite (pytest)
│   ├── conftest.py                  # Pytest fixtures and configuration
│   ├── test_cli.py                  # CLI command tests
│   ├── test_deployer.py             # FabricDeployer tests
│   ├── test_fabric_wrapper.py       # Fabric CLI wrapper tests
│   ├── test_fabric_git_api.py       # Git API integration tests
│   ├── test_config.py               # Configuration manager tests
│   ├── test_secrets.py              # Credential handling tests
│   ├── test_deployment_pipeline.py  # Pipeline API tests
│   ├── test_deployment_state.py     # State management tests
│   ├── test_git_integration.py      # Git integration tests
│   ├── test_templating.py           # Template engine tests
│   ├── test_audit.py                # Audit logging tests
│   ├── test_retry.py                # Retry logic tests
│   ├── test_telemetry.py            # Telemetry client tests
│   ├── test_token_manager.py        # Token manager tests
│   ├── test_generate_project.py     # Project generation tests
│   ├── test_onboard.py              # Onboarding tests
│   ├── test_cli_promote.py          # Pipeline promotion tests
│   ├── integration/                 # Integration tests
│   │   ├── test_diagnostics.py      # End-to-end diagnostics
│   │   ├── test_promote_e2e.py      # Pipeline promotion E2E
│   │   └── __init__.py
│   └── [additional test files]
├── webapp/                          # Optional interactive web UI
│   ├── backend/                     # FastAPI backend
│   │   ├── app/                     # FastAPI application
│   │   │   ├── main.py              # FastAPI app setup + routes
│   │   │   ├── models.py            # Pydantic models
│   │   │   ├── api/                 # API route groups
│   │   │   │   ├── scenarios.py     # Scenario endpoints
│   │   │   │   ├── search.py        # Search endpoints
│   │   │   │   ├── progress.py      # Progress tracking
│   │   │   │   └── __init__.py
│   │   │   ├── content/             # Content loading
│   │   │   │   ├── loader.py        # Scenario loader
│   │   │   │   └── __init__.py
│   │   │   └── __init__.py
│   │   ├── tests/                   # Backend tests
│   │   │   └── test_api.py          # API endpoint tests
│   │   └── fix_yaml.py              # YAML utility script
│   └── frontend/                    # React/TypeScript UI
│       ├── src/                     # TypeScript/TSX source
│       │   ├── App.tsx              # Root React component
│       │   ├── main.tsx             # React entry point
│       │   ├── pages/               # Page components
│       │   │   ├── HomePage.tsx
│       │   │   ├── ScenarioPage.tsx
│       │   │   ├── ProcessFlowPage.tsx
│       │   │   ├── ArchitecturePage.tsx
│       │   │   ├── SearchPage.tsx
│       │   │   └── [more pages]
│       │   ├── components/          # Reusable UI components
│       │   │   ├── Layout.tsx
│       │   │   ├── MarkdownContent.tsx
│       │   │   ├── CodeBlock.tsx
│       │   │   └── ui/              # Shadcn UI components
│       │   │       ├── button.tsx
│       │   │       ├── card.tsx
│       │   │       ├── input.tsx
│       │   │       ├── badge.tsx
│       │   │       └── [more UI components]
│       │   ├── lib/                 # Utilities
│       │   │   ├── api.ts           # API client
│       │   │   └── utils.ts         # Helper utilities
│       │   └── index.css            # Styles
│       ├── vite.config.ts           # Vite build config
│       ├── tsconfig.json            # TypeScript config
│       ├── package.json             # Frontend dependencies
│       └── index.html               # HTML entry point
├── config/                          # Workspace configurations (not in src)
│   ├── projects/                    # Project-specific YAML configs
│   │   ├── acme_corp/
│   │   ├── contoso/
│   │   ├── contoso_inc/
│   │   ├── edp_test_v17/
│   │   ├── finance/
│   │   ├── ProductA/
│   │   ├── ProductB/
│   │   └── [organization]/project.yaml  # Pattern: org/project-name.yaml
│   ├── environments/                # Environment-specific overrides
│   │   ├── dev.yaml                 # Development overrides
│   │   ├── staging.yaml             # Staging overrides
│   │   ├── prod.yaml                # Production overrides
│   │   ├── test.yaml                # Test overrides
│   │   └── feature_workspace.json   # Feature workspace config
│   └── workspaces_to_delete/        # Cleanup tracking
│       └── workspaces_to_delete.txt # List of workspaces for deletion
├── docs/                            # User and project documentation
│   ├── 01_User_Guides/              # End-user documentation
│   │   ├── 00_START_HERE.md         # Starting point for new users
│   │   ├── 01_Usage_Guide.md        # General usage patterns
│   │   ├── 02_CLI_Walkthrough.md    # CLI command walkthrough
│   │   ├── 03_Project_Configuration.md  # YAML config guide
│   │   ├── 04_Docker_Deployment.md  # Docker setup
│   │   ├── 05_Client_Tutorial.md    # Client library tutorial
│   │   ├── 06_Troubleshooting.md    # Common issues and fixes
│   │   ├── 07_Blueprint_Catalog.md  # 11 blueprint templates
│   │   ├── 08_Educational_Guide.md  # Learning guide
│   │   ├── 09_From_Local_to_CICD.md # Local → CI/CD progression
│   │   ├── 10_Feature_Branch_Workspace_Guide.md
│   │   ├── 11_Stabilisation_Changelog_Feb2026.md
│   │   ├── CLI_REFERENCE.md         # Command reference
│   │   ├── LOCAL_DEPLOYMENT_GUIDE.md
│   │   └── GAP_ANALYSIS_AND_HARMONISATION_PLAN.md
│   ├── 02_Strategy_and_Architecture/
│   │   ├── 01_Data_Product_Factory.md     # Architecture vision
│   │   └── 02_AI_Agent_Context.md         # AI/Claude context guide
│   └── 03_Project_Reports/          # Project milestones and reports
│       ├── 01_Current_State.md
│       ├── 02_Gap_Analysis.md
│       ├── [10 more reports]
│       └── 12_CICD_Architecture_Report.md
├── audit_logs/                      # JSONL audit logs (generated)
│   ├── fabric_cli_telemetry.jsonl
│   ├── fabric_operations_YYYY-MM-DD.jsonl
│   └── [daily rotated logs]
├── bin/                             # Shell scripts
│   ├── setup.sh                     # Environment setup
│   └── run_deployment.sh            # Deployment runner
├── .github/                         # GitHub Actions CI/CD
│   ├── workflows/                   # GitHub Actions workflows
│   │   ├── [CI/CD workflow files]
│   └── scripts/                     # Helper scripts for workflows
├── .env.template                    # Environment variable template
├── .env                             # Local environment (secrets - not committed)
├── .env.jtoye / .env.ricoh          # Org-specific env templates
├── .flake8                          # Flake8 linting config
├── .pre-commit-config.yaml          # Pre-commit hook config
├── Dockerfile                       # Docker build for webapp + CLI
├── Makefile                         # Make targets for common tasks
├── pyproject.toml                   # Python package metadata + tool config
├── pytest.ini                       # Pytest configuration
├── requirements.txt                 # Production dependencies
├── requirements-dev.txt             # Development dependencies
├── environment.yml                  # Conda environment spec
├── README.md                        # Project overview
├── CHANGELOG.md                     # Version history
├── LICENSE                          # License file
├── SECURITY.md                      # Security policy
├── CONTRIBUTING.md                  # Contribution guidelines
├── azure-pipelines.yml              # Azure Pipelines CI/CD config
└── .gitignore                       # Git ignore rules
```

## Directory Purposes

**src/usf_fabric_cli/:**
- Purpose: Main Python package source code
- Contains: All production code for CLI, services, scripts, utilities
- Key files: `cli.py` (entry point), services for orchestration, utils for cross-cutting concerns
- Committed: Yes
- Generated: No

**tests/:**
- Purpose: Comprehensive test suite using pytest
- Contains: Unit tests, integration tests, fixtures, mocks
- Key files: `conftest.py` (fixtures), test_*.py (test modules)
- Committed: Yes
- Generated: No (except __pycache__)

**config/projects/:**
- Purpose: User-created workspace configuration files (YAML)
- Contains: Organization-specific workspace definitions
- Key files: `{org}/{project}.yaml` files following naming convention
- Committed: Yes (templates), but org-specific configs typically in separate repo
- Generated: Yes (via `generate_project` command)

**config/environments/:**
- Purpose: Environment-specific configuration overrides
- Contains: dev.yaml, staging.yaml, prod.yaml for deployment customization
- Key files: dev.yaml, staging.yaml, prod.yaml
- Committed: Yes
- Generated: No (manually maintained)

**webapp/backend/**:
- Purpose: FastAPI backend for interactive deployment guide
- Contains: API endpoints, Pydantic models, content loaders
- Key files: `app/main.py` (FastAPI app), `app/api/*.py` (route groups)
- Committed: Yes
- Generated: No

**webapp/frontend/**:
- Purpose: React/TypeScript UI for web-based deployment guide
- Contains: Pages, components, API client, utilities
- Key files: `src/App.tsx`, `src/pages/*.tsx`, `vite.config.ts`
- Committed: Yes
- Generated: No (source code), Yes (node_modules/)

**docs/:**
- Purpose: Comprehensive user and project documentation
- Contains: User guides, architecture documents, project reports
- Key files: START_HERE.md, CLI_REFERENCE.md, Blueprint_Catalog.md
- Committed: Yes
- Generated: Partially (reports generated during development)

**audit_logs/:**
- Purpose: JSONL-format operational audit logs
- Contains: Daily rotated logs of all Fabric operations
- Key files: fabric_operations_YYYY-MM-DD.jsonl, fabric_cli_telemetry.jsonl
- Committed: No (.gitignore)
- Generated: Yes (at runtime)

**bin/:**
- Purpose: Shell scripts for common operational tasks
- Contains: setup.sh (environment setup), run_deployment.sh (deployment runner)
- Committed: Yes
- Generated: No

**.github/workflows/:**
- Purpose: GitHub Actions CI/CD automation
- Contains: Workflow definitions for testing, deployment, promotion
- Committed: Yes
- Generated: No

## Key File Locations

**Entry Points:**
- `src/usf_fabric_cli/cli.py`: Main CLI entry point (Typer app with all commands)
- `src/usf_fabric_cli/scripts/dev/onboard.py`: Unified onboarding automation
- `webapp/backend/app/main.py`: FastAPI application

**Configuration:**
- `pyproject.toml`: Python package metadata, build config, tool settings
- `pytest.ini`: Pytest configuration
- `.flake8`: Flake8 linting rules
- `.pre-commit-config.yaml`: Pre-commit hooks
- `Dockerfile`: Docker build specification
- `.env.template`: Environment variable template

**Core Logic:**
- `src/usf_fabric_cli/services/deployer.py`: Main FabricDeployer orchestrator
- `src/usf_fabric_cli/services/fabric_wrapper.py`: Fabric CLI wrapper with idempotency
- `src/usf_fabric_cli/services/fabric_git_api.py`: Fabric Git REST API integration
- `src/usf_fabric_cli/utils/config.py`: Configuration loading and validation
- `src/usf_fabric_cli/utils/secrets.py`: Credential resolution

**Testing:**
- `tests/conftest.py`: Pytest fixtures and test configuration
- `tests/test_deployer.py`: Main orchestrator tests
- `tests/test_fabric_wrapper.py`: CLI wrapper tests
- `tests/test_config.py`: Configuration manager tests
- `tests/integration/`: End-to-end integration tests

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `fabric_wrapper.py`, `deployment_pipeline.py`)
- Test files: `test_{module}.py` (e.g., `test_deployer.py`)
- Configuration files: `{environment}.yaml` for overrides, `{org}/{project}.yaml` for projects
- Audit logs: `fabric_operations_YYYY-MM-DD.jsonl` (daily rotation)
- Markdown docs: `NN_Topic_Name.md` (numbered, space-separated, .md extension)

**Directories:**
- Package directories: `lowercase` without underscores (e.g., `services`, `utils`, `scripts`)
- Organization directories in config: lowercase with underscores (e.g., `acme_corp`, `contoso_inc`)
- Feature directories: kebab-case (e.g., `.github/workflows/`, `node_modules/`)

**Python Classes:**
- Classes: `PascalCase` (e.g., `FabricDeployer`, `FabricCLIWrapper`, `ConfigManager`)
- Exceptions: `PascalCase` ending with `Error` (e.g., `FabricCLIError`)

**Python Functions:**
- Functions: `snake_case` (e.g., `load_config()`, `validate_credentials()`)
- Private functions: `_leading_underscore()` (e.g., `_substitute_env_vars()`)

**Configuration Keys (YAML):**
- Top-level: `snake_case` (e.g., `git_repo`, `capacity_id`, `display_name`)
- Nested: `snake_case` (e.g., `folder_rules`, `deployment_pipeline`)

## Where to Add New Code

**New Feature (e.g., New Deployment Type):**
- Primary code: Create new service in `src/usf_fabric_cli/services/` (e.g., `new_deployment_api.py`)
- Integration point: Add method to `FabricDeployer` in `src/usf_fabric_cli/services/deployer.py`
- CLI command: Add command to `src/usf_fabric_cli/cli.py` using `@app.command()`
- Tests: Create `tests/test_new_deployment.py`

**New CLI Command:**
- Implementation: Create script in `src/usf_fabric_cli/scripts/{category}/{command_name}.py` (e.g., `dev/generate_project.py`)
- Entry point: Add Typer command in `src/usf_fabric_cli/cli.py` (e.g., `@app.command()`)
- Tests: Create `tests/test_{command_name}.py`

**New Utility Module:**
- Implementation: Create `src/usf_fabric_cli/utils/new_utility.py`
- Exported in: `src/usf_fabric_cli/utils/__init__.py`
- Tests: Create `tests/test_new_utility.py`

**New Configuration Template (Blueprint):**
- Template file: `src/usf_fabric_cli/templates/blueprints/{template_name}.yaml`
- Register: Add to `_load_blueprint()` in `scripts/dev/generate_project.py`
- Tests: Add test case in `tests/test_generate_project.py`

**New Workspace Configuration:**
- Location: `config/projects/{org_name}/{project_name}.yaml`
- Structure: Follow `WorkspaceConfig` dataclass in `src/usf_fabric_cli/utils/config.py`
- Example: `config/projects/acme_corp/sales.yaml`

**New Test:**
- Unit test: `tests/test_{module}.py` with pytest fixtures from `conftest.py`
- Integration test: `tests/integration/test_{scenario}.py`
- Use mock fixtures: Reference `conftest.py` for mocking patterns

**New API Endpoint (Backend):**
- Route definition: Create router in `webapp/backend/app/api/{endpoint}.py`
- Models: Define Pydantic models in `webapp/backend/app/models.py`
- Integration: Include router in `webapp/backend/app/main.py` with `@app.include_router()`

**New Frontend Component:**
- Component: Create in `webapp/frontend/src/components/{ComponentName}.tsx`
- Page: Create in `webapp/frontend/src/pages/{PageName}.tsx`
- Styling: Use Tailwind CSS classes or Shadcn UI components

## Special Directories

**build/ and dist/:**
- Purpose: Generated build artifacts
- Generated: Yes (via `python -m build`)
- Committed: No (.gitignore)
- Content: Compiled wheel files, source distributions

**__pycache__/:**
- Purpose: Python bytecode cache
- Generated: Yes (automatically by Python)
- Committed: No (.gitignore)
- Content: Compiled .pyc files

**.mypy_cache/:**
- Purpose: MyPy type checking cache
- Generated: Yes (via `mypy` command)
- Committed: No (.gitignore)
- Content: Type inference cache

**.pytest_cache/:**
- Purpose: Pytest cache for faster test runs
- Generated: Yes (automatically by pytest)
- Committed: No (.gitignore)
- Content: Test collection and state data

**.claude/:**
- Purpose: Claude AI assistant context and working files
- Generated: Yes (during AI-assisted development)
- Committed: No (.gitignore)
- Content: Context files, analysis, notes

**.coverage:**
- Purpose: Coverage report data
- Generated: Yes (via `pytest --cov`)
- Committed: No (.gitignore)
- Content: Line coverage statistics

**node_modules/ (in webapp/frontend/):**
- Purpose: NPM package dependencies
- Generated: Yes (via `npm install`)
- Committed: No (.gitignore)
- Content: Third-party JavaScript/TypeScript packages

---

*Structure analysis: 2026-02-26*
