# Fabric CLI CI/CD - Enterprise Deployment Framework

Enterprise-grade Microsoft Fabric deployment automation leveraging the official Fabric CLI with 12-Factor App configuration management, Jinja2 artifact templating, and REST API Git integration. Designed for organization-agnostic operation with a clean, modular architecture.

> **🎉 February 2026 Update:** Version **1.7.0** — CI/CD architecture refactoring: main-centric Dev workspace, automated feature workspace lifecycle, and Fabric Deployment Pipeline integration for Dev→Test→Prod promotion. See [CHANGELOG.md](CHANGELOG.md) for details.

> **🔄 Modern Successor:** This project is the evolution of [usf-fabric-cicd](../usf-fabric-cicd), providing a full-featured enterprise CLI framework built around the official Fabric CLI with comprehensive CI/CD, Git integration, and deployment pipeline support.

## Core Capabilities

- **Automated Deployment**: Idempotent workspace provisioning with intelligent state management
- **Secret Management**: 12-Factor App compliant credential handling (Environment Variables → .env fallback → Azure Key Vault)
- **Artifact Templating**: Jinja2 engine for environment-specific artifact transformation
- **Git Integration**: REST API-driven repository connections for Azure DevOps and GitHub
- **Audit Compliance**: Structured JSONL logging for regulatory requirements
- **Branch Isolation**: CI/CD-managed feature workspaces (auto-create on push, auto-destroy on merge)
- **Deployment Pipelines**: Fabric Deployment Pipeline integration for stage promotion (Dev→Test→Prod)

## Architecture

```
┌─────────────────────────────────────┐
│   Configuration Layer              │  (YAML-driven)
└────────────┬────────────────────────┘
             │
    ┌────────┴────────────┐
    │                     │
┌───▼─────────────┐  ┌───▼──────────────────┐
│  Fabric CLI     │  │ Thin Wrapper         │
│  (core engine)  │  │ (modular CLI layer)  │
└─────────────────┘  └──────────────────────┘
```

## Quick Start

### 1. Environment Setup

```bash
# Create and activate conda environment
conda env create -f environment.yml
conda activate fabric-cli-cicd

# Install dependencies and package in editable mode
make install

# Verify Fabric CLI installation and dependencies
python scripts/admin/preflight_check.py --auto-install

# Configure authentication credentials
cp .env.template .env
# Edit .env with Service Principal credentials:
#   AZURE_CLIENT_ID       - Service Principal application ID
#   AZURE_CLIENT_SECRET   - Service Principal secret value
#   AZURE_TENANT_ID       - Azure AD tenant identifier
#   FABRIC_TOKEN          - Direct token (optional, auto-generated from SP)
#   AZURE_KEYVAULT_URL    - Azure Key Vault URL (optional, for production)

```

### Prerequisites

- **Fabric Capacity**: An active Microsoft Fabric capacity (F2 or higher).
- **Service Principal**: An Azure Service Principal with `Contributor` access to your Fabric capacity.
- **GitHub Token**: A GitHub Personal Access Token (PAT) with `repo` scope, set as `GITHUB_TOKEN` in `.env`.
- **Python**: Python 3.9+ installed.

If using Azure DevOps with a Service Principal, ensure the following:

1. **Service Principal Access Level**: The Service Principal must have **Basic** access level in Azure DevOps Organization Settings -> Users.
2. **Project Permissions**: The Service Principal must be added to the **Contributors** group of the target Azure DevOps Project.
3. **Fabric Tenant Settings**: Enable "Service principals can use Fabric APIs" and "Service principals can create workspaces" in Fabric Admin Portal.
4. **Workspace Admin**: The Service Principal must be assigned the **Admin** role in the workspace configuration (`project.yaml`).

### 3. Configure Your Project

```

### 3. End-to-End Workflow (From Scratch)

Follow these steps to deploy a new project from scratch:

**Step 1: Generate Project Configuration**
Use the template generator to create a standardized configuration file. Choose from **11 production-ready blueprints**:

```bash
# Standard ETL (Medallion architecture)
python scripts/dev/generate_project.py "Contoso Inc" "Finance Analytics" --template basic_etl

# Real-time streaming (IoT, events, Eventstreams + KQL)
python scripts/dev/generate_project.py "TechCorp" "IoT Platform" --template realtime_streaming

# Compliance-heavy (Healthcare, Finance, Government)
python scripts/dev/generate_project.py "HealthCo" "Patient Platform" --template compliance_regulated

# See all 11 templates: docs/01_User_Guides/07_Blueprint_Catalog.md
# Output: config/projects/{org_name}/{project_name}.yaml
```

**Step 2: Initialize Git Repository**

Two approaches are available — choose based on your team's needs:

| Mode | Description | Best For |
|------|-------------|----------|
| **Shared Repo** (default) | All projects connect to `GIT_REPO_URL` from `.env` | Monorepo / single codebase |
| **Isolated Repo** | Auto-creates a per-project repo (GitHub or ADO) | Per-project CI/CD isolation |

**Option A: Shared Repo (default)**

Set `GIT_REPO_URL` in `.env` and onboard normally — all workspaces connect to that single repo:

```bash
make onboard org="Contoso Inc" project="Finance Analytics"
```

**Option B: Isolated Repo (auto-created)**

Pass `--create-repo` to auto-create a dedicated project repo:

```bash
# GitHub (default provider)
make onboard-isolated org="Contoso" project="Finance" git_owner="MyGitHubOrg"

# Azure DevOps
make onboard-isolated org="Contoso" project="Finance" \
  git_owner="my-ado-org" git_provider=ado ado_project="MyAdoProject"
```

Or use the standalone repo init commands directly:

```bash
# GitHub
make init-github-repo git_owner="MyGitHubOrg" repo="contoso-finance"

# Azure DevOps
python scripts/admin/utilities/init_ado_repo.py \
  --organization "your-ado-org" \
  --project "your-ado-project" \
  --repository "contoso-finance" \
  --branch "main"
```

**Step 3: Deploy**

```bash
make deploy config=config/projects/contoso_inc/finance_analytics.yaml env=dev
```

### 3b. Accelerated "One-Click" Onboarding

```bash
# Shared repo (default — uses GIT_REPO_URL from .env)
make onboard org="Contoso Inc" project="Finance Analytics" template=medallion

# Isolated repo (auto-creates GitHub repo)
make onboard-isolated org="Contoso" project="Finance" git_owner="MyOrg"

# Feature workspace (isolated dev branch)
make feature-workspace org="TechCorp" project="IoT Platform"
```

The **default `onboard`** command will:

1. Generate the project configuration.
2. Deploy the Dev workspace connected to the `main` branch.

The **`feature-workspace`** command additionally:

1. Creates and checks out a standardized feature branch (e.g., `feature/iot-platform`).
2. Creates an isolated workspace connected to that feature branch.

### 4. Docker-Based Workflow

You can run the entire workflow inside a Docker container to ensure a consistent environment.

**Step 1: Build the Docker Image**

```bash
make docker-build
```

**Step 2: Generate Project Configuration (in Docker)**

```bash
make docker-generate org="Contoso Inc" project="Finance Analytics" template=basic_etl
```

**Step 3: Initialize Azure DevOps Repository (in Docker)**

```bash
make docker-init-repo org="your-ado-org" project="your-ado-project" repo="contoso-finance-repo"
```

**Step 4: Deploy (in Docker)**

```bash
make docker-deploy config=config/projects/contoso_inc/finance_analytics.yaml env=dev ENVFILE=.env
```

### 5. Execute Deployment

> **Security Note:** The CLI automatically enforces mandatory security principals (Additional Admin/Contributor) on all workspaces by injecting them from your environment variables.

```bash
# Validate configuration syntax and structure
make validate config=config/projects/your_org/your_project.yaml

# Deploy to development environment
make deploy config=config/projects/your_org/your_project.yaml env=dev
```

## Make Targets Reference (24 Available)

### Local Development

| Target | Description | Example |
|--------|-------------|---------|
| `install` | Install dependencies in editable mode | `make install` |
| `build` | Build Python wheel package | `make build` |
| `test` | Run unit tests (no credentials) | `make test` |
| `test-integration` | Run integration tests (requires credentials) | `make test-integration` |
| `lint` | Format and lint code | `make lint` |
| `clean` | Remove cache files | `make clean` |
| `help` | Show all available targets | `make help` |

### Local Operations

| Target | Description | Example |
|--------|-------------|---------|
| `validate` | Validate config file syntax | `make validate config=path/to/config.yaml` |
| `diagnose` | Run pre-flight system checks | `make diagnose` |
| `onboard` | Dev workspace on main (Config+Deploy) | `make onboard org="Org" project="Proj"` |
| `feature-workspace` | Isolated feature workspace with branch | `make feature-workspace org="Org" project="Proj"` |
| `deploy` | Deploy workspace from config | `make deploy config=path/to/config.yaml env=dev` |
| `destroy` | Destroy workspace from config | `make destroy config=path/to/config.yaml` |
| `bulk-destroy` | Bulk delete workspaces from list | `make bulk-destroy file=list.txt` |

### Docker Operations

All Docker targets accept `ENVFILE=.env.xxx` to specify which environment file to use (default: `.env`).

| Target | Description | Example |
|--------|-------------|---------|
| `docker-build` | Build Docker image | `make docker-build` |
| `docker-validate` | Validate config in container | `make docker-validate config=... ENVFILE=.env` |
| `docker-deploy` | Deploy workspace in container | `make docker-deploy config=... env=dev ENVFILE=.env` |
| `docker-destroy` | Destroy workspace in container | `make docker-destroy config=... ENVFILE=.env` |
| `docker-generate` | Generate project config in container | `make docker-generate org="Org" project="Proj" template=basic_etl` |
| `docker-init-repo` | Initialize ADO repo in container | `make docker-init-repo org="..." project="..." repo="..."` |
| `docker-shell` | Interactive shell in container | `make docker-shell ENVFILE=.env` |
| `docker-diagnose` | Run diagnostics in container | `make docker-diagnose ENVFILE=.env` |
| `docker-feature-deploy` | Deploy feature branch workspace | `make docker-feature-deploy config=... env=dev branch=feature/x` |

## CLI Flags Reference

### Deploy Command

```bash
python -m usf_fabric_cli.cli deploy CONFIG [OPTIONS]
```

| Flag | Short | Description |
|------|-------|-------------|
| `--env` | `-e` | Target environment (dev/staging/prod) |
| `--branch` | `-b` | Git branch to use for deployment |
| `--force-branch-workspace` | | Create isolated workspace for feature branch |
| `--rollback-on-failure` | | Auto-delete created items if deployment fails |
| `--validate-only` | | Validate config without deploying |
| `--diagnose` | | Run diagnostics before deployment |

### Destroy Command

```bash
python -m usf_fabric_cli.cli destroy CONFIG [OPTIONS]
```

| Flag | Short | Description |
|------|-------|-------------|
| `--env` | `-e` | Target environment (dev/staging/prod) |
| `--force` | `-f` | Skip confirmation prompt |
| `--workspace-name-override` | | Override workspace name (e.g., for branch-specific cleanup) |

### Promote Command

```bash
python -m usf_fabric_cli.cli promote [OPTIONS]
```

| Flag | Short | Description |
|------|-------|-------------|
| `--pipeline-name` | `-p` | Fabric Deployment Pipeline display name |
| `--source-stage` | `-s` | Source stage name (default: Development) |
| `--target-stage` | `-t` | Target stage name (auto-inferred if omitted) |
| `--note` | `-n` | Deployment note / description |

## Interactive Learning Guide

The project includes an **interactive web application** to help users understand and learn the CLI workflows:

```bash
cd webapp

# Option 1: Docker (Recommended)
./docker-quickstart.sh
# → Open http://localhost:8080

# Option 2: Development mode (requires Python 3.11+ and Node.js 18+)
make install  # Install backend + frontend dependencies
make dev      # Start both servers (backend: 8001, frontend: 5173)
# → Open http://localhost:5173
```

### Features

- **Visual Workflow Diagrams**: Interactive flowcharts showing deployment processes step-by-step
- **8 Comprehensive Scenarios**: Getting Started, Project Generation, Local/Docker Deployment, Feature Branches, Git Integration, Environment Promotion, Troubleshooting
- **Progress Tracking**: Track your learning progress through each guide
- **Code Snippets with Copy**: Easily copy commands and configurations

### Azure Deployment

Deploy the webapp to Azure Container Apps:

```bash
cd webapp
make deploy-azure        # Full deployment
make deploy-azure-dryrun # Preview what will be deployed
```

See [webapp/README.md](webapp/README.md) for detailed documentation.

## Utility Tools

The framework includes several utility scripts in `scripts/admin/utilities/` to assist with setup and troubleshooting. These scripts automatically load credentials from your `.env` file.

### Initialize Azure DevOps Repository

Initializes an empty Azure DevOps repository with a `main` branch. This is required because Fabric Git integration fails if the target repository is completely empty (0 branches).

```bash
python scripts/admin/utilities/init_ado_repo.py \
  --organization "your-org-name" \
  --project "your-project-name" \
  --repository "your-repo-name"
```

### Debug Azure DevOps Access

Verifies that your Service Principal has the correct permissions to access Azure DevOps.

```bash
python scripts/admin/utilities/debug_ado_access.py \
  --organization "your-org-name" \
  --project "your-project-name"
```

### Debug Git Connection

Tests the connection to a Git repository using the configured credentials.

```bash
python scripts/admin/utilities/debug_connection.py \
  --organization "your-org-name" \
  --project "your-project-name" \
  --repository "your-repo-name"
```

### List Workspace Items

Lists all items in a specified Fabric workspace to verify deployment.

```bash
python scripts/admin/utilities/list_workspace_items.py --workspace "Workspace Name"
```

## Project Structure

```
src/
├── usf_fabric_cli/          # Main package (renamed from core)
│   ├── __init__.py          # Package exports with lazy loading
│   ├── cli.py               # Main deployment orchestrator (Entry Point)
│   ├── exceptions.py        # Exception hierarchy
│   ├── commands/            # CLI subcommands (future modularization)
│   ├── services/
│   │   ├── fabric_wrapper.py       # Fabric CLI wrapper with version validation
│   │   ├── fabric_git_api.py       # REST API client for Git integration
│   │   ├── git_integration.py      # Git synchronization logic
│   │   ├── token_manager.py        # Azure AD token refresh for long deployments
│   │   ├── deployment_state.py     # Atomic rollback state management
│   │   └── deployment_pipeline.py  # Fabric Deployment Pipelines REST API client
│   ├── utils/
│   │   ├── secrets.py       # 12-Factor App secret management
│   │   ├── config.py        # YAML configuration management
│   │   ├── templating.py    # Jinja2 artifact transformation engine
│   │   ├── audit.py         # Compliance audit logging
│   │   ├── telemetry.py     # Operational telemetry
│   │   └── retry.py         # Exponential backoff utilities
│   └── schemas/
│       └── workspace_config.json  # JSON schema for validation


config/
├── projects/              # Your organization configs
│   ├── {org_name}/
│   │   └── {project_name}.yaml
│   └── ...                # 7+ example orgs included
└── environments/
    ├── dev.yaml
    ├── staging.yaml
    ├── test.yaml
    ├── prod.yaml
    └── feature_workspace.json  # Feature workspace recipe & lifecycle policies

templates/
└── blueprints/            # 11 production-ready templates
    ├── basic_etl.yaml
    ├── advanced_analytics.yaml
    ├── data_science.yaml
    ├── realtime_streaming.yaml
    ├── compliance_regulated.yaml
    ├── data_mesh_domain.yaml
    ├── migration_hybrid.yaml
    ├── minimal_starter.yaml
    ├── specialized_timeseries.yaml
    └── extensive_example.yaml

scripts/
├── admin/                 # Administrative/operational scripts
│   ├── bulk_destroy.py    # Bulk cleanup utility
│   ├── preflight_check.py # Environment validation
│   └── utilities/         # Helper utilities
├── dev/                   # Developer workflow scripts
│   ├── generate_project.py  # Project scaffolding
│   └── onboard.py           # Unified onboarding (main-centric + feature)
```

## Total LOC: ~6,200 (src/) + ~2,600 (scripts/) + ~3,500 (tests/) — modular architecture

## Configuration Examples

See `templates/blueprints/` for organization-agnostic templates that can be customized for any project.

## Testing

```bash
# Run unit tests
pytest -m "not integration"

# Run integration tests (requires Fabric CLI + live token)
pytest tests/integration -m integration

# Full coverage
pytest --cov=src
```

## CI/CD Integration

GitHub Actions workflows included for:

| Workflow | Trigger | Purpose |
|:---|:---|:---|
| `fabric-cicd.yml` | Push/PR to `main` | Validation, linting, and testing |
| `feature-workspace-create.yml` | Push to `feature/*` | Auto-create Fabric workspace for feature branch |
| `feature-workspace-cleanup.yml` | PR merge / branch delete | Auto-destroy feature workspace |
| `deploy-to-fabric.yml` | Push to `main` / manual | Promote content via Deployment Pipeline (Dev→Test→Prod) |

### Deployment Pipeline Promotion

Content promotion follows the Microsoft-recommended **Option 3** pattern:

1. **Automatic:** Push to `main` → Dev workspace syncs via Git → auto-promote Dev→Test
2. **Manual:** `workflow_dispatch` with approval gate for Test→Prod promotions

**Required GitHub Secrets:**

| Secret | Purpose |
|:---|:---|
| `AZURE_TENANT_ID` | Azure AD tenant |
| `AZURE_CLIENT_ID` | Service Principal app ID |
| `AZURE_CLIENT_SECRET` | Service Principal secret |
| `FABRIC_CAPACITY_ID` | Fabric capacity for workspace creation |
| `GITHUB_TOKEN_FABRIC` | GitHub PAT for Git connections |
| `FABRIC_PIPELINE_NAME` | Deployment pipeline display name |

See [Blueprint Catalog](docs/01_User_Guides/07_Blueprint_Catalog.md) for configuration examples.

## Features

### Core Capabilities

- ✅ Workspace creation and management
- ✅ Folder structure (Bronze/Silver/Gold medallion) with item placement
- ✅ Item creation (Lakehouses, Warehouses, Notebooks, Pipelines)
- ✅ **Generic Resource Support** (Future-proof for any Fabric item type)
- ✅ Git integration (Azure DevOps & GitHub) and branch management
- ✅ Principal assignment and access control
- ✅ Idempotent deployments (rerun-safe)
- ✅ Comprehensive audit logging
- ✅ Multi-environment support
- ✅ Configuration validation

### Advanced Features

- ✅ Feature branch workflows (CI/CD-managed lifecycle)
- ✅ **Fabric Deployment Pipelines** (Dev→Test→Prod promotion)
- ✅ Capacity management
- ✅ Template-based deployments
- ✅ Error diagnostics and remediation
- ✅ Progress tracking and reporting
- ✅ **Bulk Workspace Cleanup** utility

## Learnings Applied

This project incorporates key learnings from the original implementation:

1. **Build vs Buy Assessment** - Use official tools wherever possible
2. **Progressive Complexity** - Start simple, add features incrementally  
3. **Stakeholder Alignment** - Configuration-driven, easy to understand
4. **Maintenance Focus** - Minimal custom code, maximum leverage
5. **Evolution Strategy** - Built to adapt as Fabric CLI evolves

## Migration from Custom Solutions

If migrating from a custom Fabric API solution:

1. **Assessment** - Use `scripts/admin/utilities/analyze_migration.py` to identify what can be replaced with CLI
2. **Migration** - Incremental replacement of custom components
3. **Validation** - Side-by-side testing during transition
4. **Deprecation** - Sunset plan for custom components

## Contributing

1. Fabric CLI first - only add custom logic for genuine gaps
2. Configuration over code - make it reusable
3. Test thoroughly - both unit and integration tests
4. Document decisions - explain why custom code exists

## License

MIT License - Use freely in any organization.
