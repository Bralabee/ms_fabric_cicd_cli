# Fabric CLI CI/CD - Enterprise Deployment Framework

Enterprise-grade Microsoft Fabric deployment automation leveraging the official Fabric CLI with 12-Factor App configuration management, Jinja2 artifact templating, and REST API Git integration. Designed for organization-agnostic operation with 85% code reduction from traditional enterprise frameworks.

## Core Capabilities

- **Automated Deployment**: Idempotent workspace provisioning with intelligent state management
- **Secret Management**: 12-Factor App compliant credential handling (Environment Variables → .env fallback)
- **Artifact Templating**: Jinja2 engine for environment-specific artifact transformation
- **Git Integration**: REST API-driven repository connections for Azure DevOps and GitHub
- **Audit Compliance**: Structured JSONL logging for regulatory requirements
- **Branch Isolation**: Feature branch workspaces for parallel development workflows  

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
│  (90% of work)  │  │ (~270 LOC)           │
└─────────────────┘  └──────────────────────┘
```

## Quick Start

### 1. Environment Setup

```bash
# Create and activate conda environment
conda env create -f environment.yml
conda activate fabric-cli-cicd

# Verify Fabric CLI installation and dependencies
python scripts/preflight_check.py --auto-install

# Configure authentication credentials
cp .env.template .env
# Edit .env with Service Principal credentials:
#   AZURE_CLIENT_ID       - Service Principal application ID
#   AZURE_CLIENT_SECRET   - Service Principal secret value
#   AZURE_TENANT_ID       - Azure AD tenant identifier
#   FABRIC_TOKEN          - Direct token (optional, auto-generated from SP)

### 2. Azure DevOps Integration (Prerequisites)

If using Azure DevOps with a Service Principal, ensure the following:

1.  **Service Principal Access Level**: The Service Principal must have **Basic** access level in Azure DevOps Organization Settings -> Users.
2.  **Project Permissions**: The Service Principal must be added to the **Contributors** group of the target Azure DevOps Project.
3.  **Fabric Tenant Settings**: Enable "Service principals can use Fabric APIs" and "Service principals can create workspaces" in Fabric Admin Portal.
4.  **Workspace Admin**: The Service Principal must be assigned the **Admin** role in the workspace configuration (`project.yaml`).

### 3. Configure Your Project
```

### 2. Configure Your Project

```bash
# Generate project configuration from template
python scripts/generate_project.py "Your Org" "Project Name" \
  --template basic_etl \
  --capacity-id ${FABRIC_CAPACITY_ID} \
  --git-repo ${GIT_REPO_URL}

# Customize generated configuration
vim config/projects/your_org/your_project.yaml
```

### 3. Execute Deployment

> **Security Note:** The CLI automatically enforces mandatory security principals (Additional Admin/Contributor) on all workspaces by injecting them from your environment variables.

```bash
# Validate configuration syntax and structure
python src/fabric_deploy.py validate config/projects/your_org/your_project.yaml

# Deploy to development environment
python src/fabric_deploy.py deploy config/projects/your_org/your_project.yaml --env dev

# Deploy with automatic Git repository connection
python src/fabric_deploy.py deploy config/projects/your_org/your_project.yaml --env dev --connect-git

# Deploy feature branch to isolated workspace
# (Uses 'dev' config but creates a unique workspace name)
python src/fabric_deploy.py deploy config/projects/your_org/your_project.yaml \
  --env dev --branch feature/new-analytics --force-branch-workspace

# Production deployment with diagnostics
python src/fabric_deploy.py deploy config/projects/your_org/your_project.yaml --env prod --diagnose
```

## Utility Tools

The framework includes several utility scripts in `scripts/utilities/` to assist with setup and troubleshooting. These scripts automatically load credentials from your `.env` file.

### Initialize Azure DevOps Repository
Initializes an empty Azure DevOps repository with a `main` branch. This is required because Fabric Git integration fails if the target repository is completely empty (0 branches).

```bash
python scripts/utilities/init_ado_repo.py \
  --organization "your-org-name" \
  --project "your-project-name" \
  --repository "your-repo-name"
```

### Debug Azure DevOps Access
Verifies that your Service Principal has the correct permissions to access Azure DevOps.

```bash
python scripts/utilities/debug_ado_access.py \
  --organization "your-org-name" \
  --project "your-project-name"
```

### Debug Git Connection
Tests the connection to a Git repository using the configured credentials.

```bash
python scripts/utilities/debug_connection.py \
  --organization "your-org-name" \
  --project "your-project-name" \
  --repository "your-repo-name"
```

### List Workspace Items
Lists all items in a specified Fabric workspace to verify deployment.

```bash
python scripts/utilities/list_workspace_items.py --workspace "Workspace Name"
```

## Project Structure

```
src/
├── core/
│   ├── secrets.py         # 12-Factor App secret management with waterfall loading
│   ├── fabric_git_api.py  # REST API client for Git integration  
│   ├── templating.py      # Jinja2 artifact transformation engine
│   ├── config.py          # YAML configuration management
│   ├── fabric_wrapper.py  # Fabric CLI wrapper with version validation
│   ├── git_integration.py # Git synchronization
│   ├── audit.py          # Compliance audit logging
│   ├── telemetry.py      # Operational telemetry
│   └── exceptions.py     # Exception hierarchy
└── fabric_deploy.py       # Main deployment orchestrator

config/
├── projects/
│   ├── ProductA/
│   │   └── sales_project.yaml
│   └── ProductB/
│       └── finance_project.yaml
└── environments/
    ├── dev.yaml
    ├── staging.yaml
    └── prod.yaml

templates/
└── blueprints/
    ├── basic_etl.yaml
    ├── advanced_analytics.yaml
    └── data_science.yaml

scripts/
├── bulk_destroy.py        # Bulk cleanup utility
├── generate_project.py    # Project scaffolding
├── preflight_check.py     # Environment validation
└── utilities/
    ├── analyze_migration.py   # Migration analysis tool
    ├── list_workspaces.py     # Workspace listing tool
    └── list_workspace_items.py # Item listing tool
```

## Total LOC: ~270 (vs original 1,830)

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
- Automated testing
- Environment promotion (dev → staging → prod)
- Feature branch deployments
- Principal management

**Important:** For CI/CD pipelines to function, you must configure the required secrets (`AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`) in your GitHub repository settings. See [Usage Guide](docs/USAGE_GUIDE.md#troubleshooting) for details.

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
- ✅ Feature branch workflows
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

1. **Assessment** - Use `scripts/utilities/analyze_migration.py` to identify what can be replaced with CLI
2. **Migration** - Incremental replacement of custom components
3. **Validation** - Side-by-side testing during transition
4. **Deprecation** - Sunset plan for custom components

## Contributing

1. Follow the 270 LOC budget - justify any additions
2. Fabric CLI first - only add custom logic for genuine gaps
3. Configuration over code - make it reusable
4. Test thoroughly - both unit and integration tests
5. Document decisions - explain why custom code exists

## License

MIT License - Use freely in any organization.