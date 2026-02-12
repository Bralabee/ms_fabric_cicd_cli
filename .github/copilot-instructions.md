# GitHub Copilot Instructions for USF Fabric CLI CI/CD

Enterprise Microsoft Fabric deployment automation using a **modular architecture** around official Fabric CLI (~6,200 LOC across services, utils, and CLI layers).

**Current Version**: 1.7.5 (February 2026)

## 📏 Development Standards

### Code Quality & Formatting
*   **Linting**: `flake8` (Max line length: 88). Command: `flake8 src`
*   **Formatting**: `black` (Profile: black). Command: `black .`
*   **Type Safety**: `mypy`. Command: `mypy src`

## 🏗 Architecture Fundamentals

### Thin Wrapper Design Pattern
```
Configuration (YAML) → FabricDeployer (orchestrator) → FabricCLIWrapper → fabric CLI
                     ↓                                 ↓
                  FabricSecrets (12-Factor)      FabricGitAPI (REST)
                     ↓
            AuditLogger (JSONL compliance)
```

**Core Components** (`src/usf_fabric_cli/`):
- `cli.py`: Typer-based CLI orchestrator (deploy/destroy/validate/promote commands)
- `fabric_wrapper.py`: Thin abstraction over `fabric` CLI subprocess calls. **Supports generic item creation** via `create_item` for 54+ Fabric item types.
- `config.py`: YAML config loader with env-specific overrides + Jinja2 variable substitution
- `secrets.py`: Waterfall credential management (Env Vars → .env → Azure Key Vault)
- `git_integration.py`: Git connection automation via REST API (not CLI)
- `deployment_pipeline.py`: Fabric Deployment Pipelines REST API client (Dev→Test→Prod)
- `templating.py`: Jinja2 sandboxed engine for artifact transformation
- `audit.py`: Structured JSONL logging to `audit_logs/` for compliance
- `telemetry.py`: Lightweight usage tracking (optional)
- `exceptions.py`: Custom error handling classes

### Organization-Agnostic Design
All configurations use **environment variable substitution** (`${VAR_NAME}`). No hardcoded organization names.  
Template blueprints in `templates/blueprints/*.yaml` are customized via `scripts/dev/generate_project.py`.

## 🔐 Secret Management (CRITICAL)

**Waterfall Priority** (`src/usf_fabric_cli/utils/secrets.py:FabricSecrets`):
1. **Environment Variables** (production/CI/CD) - highest priority
2. **`.env` file** (local development) - `python-dotenv` auto-loaded
3. **Azure Key Vault** (optional) - via `DefaultAzureCredential` + `AZURE_KEYVAULT_URL`
4. **Error** - raise if required credentials missing

**Required Secrets**:
- `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID` (Service Principal)
- `FABRIC_TOKEN` (auto-generated from SP if missing)
- `FABRIC_CAPACITY_ID` (for workspace deployments)
- `AZURE_DEVOPS_PAT` or `GITHUB_TOKEN` (for Git integration)

**NEVER**:
- ❌ Hardcode credentials in code or config files
- ❌ Commit `.env`, `.env.*`, or `audit_logs/*.jsonl` (see `.gitignore`)
- ❌ Log secrets or tokens (obfuscation in `fabric_wrapper.py`)

## 🛠 Developer Workflows

### Environment Setup (REQUIRED FIRST)
**Always activate the conda environment before running any Python commands:**
```bash
# Create environment (first time only)
conda env create -f environment.yml

# Activate environment (REQUIRED for all operations)
conda activate fabric-cli-cicd

# Verify you're in the correct environment
conda env list  # Should show * next to fabric-cli-cicd
```

**All Python commands below assume `fabric-cli-cicd` conda environment is active.**

### Standard Deployment Flow
```bash
# 1. Generate project config from template
# Available templates: basic_etl, advanced_analytics, realtime_streaming, compliance_regulated, etc.
# See docs/01_User_Guides/07_Blueprint_Catalog.md for full list.
python scripts/dev/generate_project.py "Acme Corp" "Sales Analytics" --template realtime_streaming
# Output: config/projects/acme_corp/sales_analytics.yaml

# 2. One-Click Onboard (preferred — generates config + deploys in one step)
make onboard org="Acme Corp" project="Sales Analytics" template=realtime_streaming

# 2b. Isolated repo mode (auto-creates a per-project GitHub repo)
make onboard-isolated org="Acme Corp" project="Sales" git_owner="MyGitHubOrg"

# 2c. Standalone repo init (GitHub or ADO)
make init-github-repo git_owner="MyOrg" repo="acme-sales"
python scripts/admin/utilities/init_ado_repo.py \
  --organization "your-ado-org" \
  --project "FabricProjects" \
  --repository "acme-sales-repo"

# 3. Deploy via Makefile (preferred) or direct CLI
make deploy config=config/projects/acme_corp/sales_analytics.yaml env=dev
# OR: python -m usf_fabric_cli.cli deploy config/projects/.../sales_analytics.yaml --env dev
```

### Testing Strategy
```bash
# Unit tests (mocked, no credentials required)
make test  # OR: pytest -m "not integration"

# Integration tests (requires real Fabric workspace + credentials in .env)
make test-integration  # OR: pytest tests/integration -m integration

# Pre-flight diagnostics (check CLI version, credentials, capacity access)
python scripts/admin/preflight_check.py --auto-install
```

### Docker Workflow
```bash
# Build image (installs Fabric CLI from GitHub)
make docker-build  # OR: docker build -t fabric-cli-cicd .

# Deploy using container (isolates dependencies)
make docker-deploy config=config/projects/.../project.yaml env=dev ENVFILE=.env
# ENVFILE parameter allows switching between .env, .env.prod, etc.
```

### Debugging Failed Deployments
1. **Check audit logs**: `audit_logs/fabric_operations_YYYY-MM-DD.jsonl` (structured JSON)
2. **Run diagnostics**: `python scripts/admin/preflight_check.py` (validates CLI, credentials, capacity)
3. **Validate config**: `make validate config=path/to/config.yaml` (schema + env var check)
4. **Check Git connectivity**: `python scripts/admin/utilities/debug_ado_access.py --organization X --project Y`
5. **List workspace items**: `python scripts/admin/utilities/list_workspace_items.py --workspace "workspace-name"`

## 📝 Configuration Patterns

### YAML Config Structure (`config/projects/org_name/project_name.yaml`)
```yaml
workspace:
  name: "acme-sales-analytics"  # Workspace name (becomes DNS-safe slug)
  capacity_id: "${FABRIC_CAPACITY_ID}"  # Env var substitution
  git_repo: "${GIT_REPO_URL}"  # Shared repo (from .env), or auto-set by --create-repo
  git_branch: "main"

# Generic Resource Definition (supports all Fabric item types)
resources:
  - type: "Eventstream"
    name: "iot_events"
    description: "Ingest from IoT Hub"
  - type: "KQLDatabase"
    name: "telemetry_db"
  - type: "Reflex"
    name: "alert_monitor"

folders: ["Bronze", "Silver", "Gold"]  # Lakehouse folder structure

lakehouses:
  - name: "raw_data_lakehouse"
    folder: "Bronze"
    description: "Raw ingestion layer"

notebooks:
  - name: "data_transformation"
    folder: "Notebooks"
    file_path: "templates/notebooks/transform.py"  # Import from file
    # Content embedded in definition will be rendered via Jinja2

environments:
  dev:
    workspace:
      capacity_id: "F2"  # Override for dev environment
  prod:
    workspace:
      capacity_id: "F64"  # Different capacity for prod
```

### Jinja2 Templating in Artifacts
Notebooks, pipelines, and semantic models support Jinja2 variables:
```python
# In notebook definition (embedded or file_path)
lakehouse_name = "{{ environment }}_data_lakehouse"  # Rendered: dev_data_lakehouse
connection_string = "{{ secrets.STORAGE_ACCOUNT_URL }}"
```

**Rendering context** (`src/usf_fabric_cli/utils/templating.py`):
- `environment`: Current env (dev/test/prod)
- `workspace_name`: Workspace display name
- `capacity_id`: Fabric capacity ID
- `secrets.*`: Access to secrets from `FabricSecrets` (use sparingly)

## 🔗 Integration Points

### Fabric CLI Dependency
- **Installation**: `pip install git+https://github.com/microsoft/fabric-cli.git@v1.3.1#egg=ms-fabric-cli`
- **Version Check**: `src/usf_fabric_cli/services/fabric_wrapper.py:_validate_cli_version()` ensures min version
- **Command Pattern**: All CLI calls via `_run_command()` with `--output json` for parsing

### Git Integration (REST API, not CLI)
- **Why REST?**: Fabric CLI doesn't support Git connections yet (as of v1.0)
- **Implementation**: `src/usf_fabric_cli/services/fabric_git_api.py:FabricGitAPI` uses Fabric REST API
- **Supported Providers**: Azure DevOps, GitHub (via `GitProviderType` enum)
- **Authentication**: Uses same Service Principal as Fabric operations

### Azure DevOps Prerequisites
Service Principal must have:
1. **Basic** access level in ADO Organization Settings → Users
2. **Contributor** role in target ADO project
3. **Admin** role in Fabric workspace (defined in config YAML `principals` section)

## 🧪 Code Conventions

### Error Handling
- **Custom Exceptions**: `src/usf_fabric_cli/exceptions.py` (`FabricCLIError`, `FabricCLINotFoundError`)
- **Idempotency**: All operations check existence before creation (avoid "already exists" errors)
- **Retry Logic**: Implemented in `src/usf_fabric_cli/utils/retry.py` (exponential backoff with jitter, decorator pattern, HTTP retry helper)

### Logging
- **Standard Library**: Use `logging` module (not `print()`)
- **Rich Output**: User-facing messages via `rich.console.Console` for formatting
- **Audit Trail**: All operations logged to `audit_logs/*.jsonl` via `AuditLogger`

### Testing Marks
- `@pytest.mark.integration` - requires credentials + real Fabric workspace
- Default (no mark) - unit tests with mocks, safe for CI/CD

## 🚨 Common Pitfalls

1. **Not Using Conda Environment**: ALWAYS run `conda activate fabric-cli-cicd` before any Python operations. Check with `conda env list` to verify.
2. **Entry Point Not Available**: Run `make install` or `pip install -e .` to enable the `fabric-cicd` command (alternative: use `python -m usf_fabric_cli.cli`)
3. **Service Principal Permissions**: Most deployment failures = missing SP permissions (workspace admin, ADO contributor)
4. **Capacity Exhausted**: F2 (trial) has low limits. Use `scripts/admin/utilities/list_workspaces.py` to audit capacity usage
5. **Git Branch Workspaces**: Feature workspaces are now CI/CD-managed (auto-created/destroyed by GitHub Actions). Manual cleanup only needed if workflows fail.
6. **Template Undefined Variables**: Jinja2 `StrictUndefined` mode raises errors. Check `templating.py` rendering context.

## 📦 Packaging & Distribution

- **Wheel Build**: `make build` → `dist/usf_fabric_cli-1.7.3-py3-none-any.whl`
- **Entry Point**: `pyproject.toml` defines `fabric-cicd` command → `usf_fabric_cli.cli:app`
- **Docker Image**: `Dockerfile` installs wheel + Fabric CLI, runs as non-root user

## � Interactive Learning Guide (`webapp/`)

The project includes an interactive web application for learning and utilizing the CLI toolkit.

### Architecture
- **Backend**: FastAPI (Python 3.11+) - `webapp/backend/`
  - REST API for scenarios, search, and progress tracking
  - Content stored in YAML files under `app/content/scenarios/`
  - Models in `app/models.py` (Pydantic v2)
- **Frontend**: React + TypeScript + Tailwind CSS - `webapp/frontend/`
  - shadcn/ui component patterns
  - React Query for data fetching
  - Progress tracking with local state
  - Code-split bundles for better caching

### Quick Start
```bash
cd webapp
make install    # Install backend + frontend dependencies
make dev        # Start both servers (backend: 8001, frontend: 5173)
```

### Content Structure
Scenario YAML files in `webapp/backend/app/content/scenarios/`:
- `00-complete-journey.yaml` - End-to-end walkthrough (7 phases)
- `01-getting-started.yaml` - Environment setup, credentials (17 steps including project config generation)
- `02-project-generation.yaml` - Blueprint templates, all 11 templates covered
- `03-local-deployment.yaml` - Validate, deploy, idempotency, verify
- `04-docker-deployment.yaml` - Build, deploy, multi-tenant, debugging
- `05-feature-branch-workflows.yaml` - Isolation, branch workspaces, cleanup
- `06-git-integration.yaml` - Azure DevOps, GitHub, debugging
- `07-troubleshooting.yaml` - Common issues and solutions
- `08-environment-promotion.yaml` - DEV→TEST→PROD promotion, source repointing, Jinja2 templating

### Docker Ports
- **Backend API**: Port 8001 (FastAPI/uvicorn)
- **Frontend UI**: Port 8080 (nginx)

## 📚 Key Documentation Files

- **README.md**: Quick start, Make Targets Reference (24 targets), CLI Flags Reference
- **docs/01_User_Guides/03_Project_Configuration.md**: Comprehensive project config generation guide
- **docs/01_User_Guides/07_Blueprint_Catalog.md**: All 11 blueprint templates with selection guidance
- **.env.template**: Environment variable template with Azure credential structure

## 🔄 Environment Promotion (DEV → TEST → PROD)

### Promotion Pipeline
The CLI supports deploying the same configuration to multiple environments with automatic source repointing:
```bash
# Deploy to development
make deploy config=config/projects/acme_corp/sales.yaml env=dev

# Deploy to test (after DEV validation)
make deploy config=config/projects/acme_corp/sales.yaml env=test

# Deploy to production (after UAT approval)
make deploy config=config/projects/acme_corp/sales.yaml env=prod
```

### Environment Override Files
Located in `config/environments/`:
- `dev.yaml` - Development settings (F2/F4 capacity, broad access)
- `test.yaml` - Test/UAT settings (F8/F16 capacity, QA team access)
- `staging.yaml` - Pre-production settings (production-like)
- `prod.yaml` - Production settings (F32/F64 capacity, strict access)
- `feature_workspace.json` - Feature workspace recipe & lifecycle policies

### CI/CD Deployment Pipeline Promotion

Content promotion follows the Microsoft-recommended **Option 3** pattern:

1. **Git Sync** → Dev workspace syncs automatically from `main`
2. **Auto Dev→Test** → On push to `main`, GitHub Actions promotes via Fabric Deployment Pipeline
3. **Manual Test→Prod** → `workflow_dispatch` with approval gate

**CLI Promote Command:**
```bash
# Promote Dev → Test (auto-infers next stage)
python -m usf_fabric_cli.cli promote --pipeline-name "MyPipeline" --source-stage Development

# Promote to specific stage
python -m usf_fabric_cli.cli promote --pipeline-name "MyPipeline" -s Test -t Production
```

### Source Repointing Mechanisms
1. **Environment Variable Substitution** (`${VAR_NAME}`):
   - Different `.env` files per environment
   - CI/CD secrets per environment
   - Example: `${STORAGE_ACCOUNT_URL}` → different storage per env

2. **Jinja2 Templating** (`{{ env }}`):
   - Dynamic naming: `lakehouse_{{ env }}` → `lakehouse_dev`
   - Artifact content: Notebooks/pipelines with env-specific values

3. **Environment Override Merging**:
   - Base config + `config/environments/<env>.yaml`
   - Deep merge for dicts, concatenation for lists (principals)

## �🔗 Related Projects

- **usf-fabric-cicd**: Original monolithic framework (this CLI is the lightweight successor)
- **usf_fabric_monitoring**: Monitor Hub analysis for operational insights
- **fabric-purview-playbook-webapp**: Delivery playbook web application
