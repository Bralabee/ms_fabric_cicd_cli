# Fabric CLI CI/CD - Enterprise Deployment Framework

Organization-agnostic Microsoft Fabric deployment automation using official Fabric CLI with enterprise-grade secret management, artifact templating, and Git integration.

## Core Capabilities

- Automated workspace deployment with idempotent operations
- 12-Factor App compliant secret management (Environment variables → .env fallback)
- Jinja2-based artifact templating for environment-specific configurations
- REST API integration for automatic Git repository connection
- Comprehensive audit logging for compliance
- Feature branch workspace isolation  

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

# Verify Fabric CLI installation
python scripts/preflight_check.py --auto-install

# Configure authentication
cp .env.template .env
# Edit .env with required credentials:
# - AZURE_CLIENT_ID: Service Principal application ID
# - AZURE_CLIENT_SECRET: Service Principal secret
# - TENANT_ID: Azure AD tenant ID
# Optional: FABRIC_TOKEN for direct token authentication
```

### 2. Configure Your Project

```bash
# Copy template configuration
cp examples/templates/basic_etl.yaml config/my_project.yaml

# Edit configuration for your organization
vim config/my_project.yaml
```

### 3. Execute Deployment

```bash
# Deploy to development environment
python src/fabric_deploy.py deploy config/my_project.yaml --env dev

# Deploy with automatic Git repository connection
python src/fabric_deploy.py deploy config/my_project.yaml --env dev --connect-git

# Deploy feature branch to isolated workspace
python src/fabric_deploy.py deploy config/my_project.yaml --env dev --branch feature/new-analytics

# Production deployment
python src/fabric_deploy.py deploy config/my_project.yaml --env prod
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
├── ProductA/
│   └── sales_project.yaml
├── ProductB/
│   └── finance_project.yaml
└── environments/
    ├── dev.yaml
    ├── staging.yaml
    └── prod.yaml

examples/
└── templates/
    ├── basic_etl.yaml
    ├── advanced_analytics.yaml
    └── data_science.yaml

scripts/
├── analyze_migration.py   # Migration analysis tool
├── bulk_destroy.py        # Bulk cleanup utility
├── generate_project.py    # Project scaffolding
└── preflight_check.py     # Environment validation
```

## Total LOC: ~270 (vs original 1,830)

## Configuration Examples

See `examples/templates/` for organization-agnostic templates that can be customized for any project.

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

1. **Assessment** - Use `scripts/analyze_migration.py` to identify what can be replaced with CLI
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