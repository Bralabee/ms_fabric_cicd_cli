# Fabric CLI CI/CD - Thin Wrapper Solution

A configurable, organization-agnostic Fabric CI/CD solution that applies all learnings from the original 1,830 LOC project, now optimized to just ~270 LOC by leveraging Microsoft's official Fabric CLI.

## Key Principles Applied

✅ **Official Tools First** - 90% Fabric CLI, 10% thin wrapper  
✅ **Configurable** - Works for any organization/project  
✅ **Idempotent** - Safe to re-run deployments  
✅ **Audit Trail** - Compliance-ready logging  
✅ **Git Integration** - Feature branch workflows  
✅ **Principal Management** - Automated workspace access  

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

### 1. Setup Environment

```bash
# Create conda environment
conda env create -f environment.yml
conda activate fabric-cli-cicd

# Run the preflight helper to install/verify Fabric CLI
python scripts/preflight_check.py --auto-install

# Configure secrets once ready (.env is auto-loaded by python-dotenv)
cp .env.template .env
vim .env
```

### 2. Configure Your Project

```bash
# Copy template configuration
cp config/templates/basic_etl.yaml config/my_project.yaml

# Edit configuration for your organization
vim config/my_project.yaml
```

### 3. Deploy Workspace

```bash
# Deploy to development (FABRIC_TOKEN and TENANT_ID pulled from .env automatically)
python src/fabric_deploy.py deploy --config config/my_project.yaml --env dev

# Deploy feature branch
python src/fabric_deploy.py deploy --config config/my_project.yaml --env dev --branch feature/new-analytics

# Deploy to production
python src/fabric_deploy.py deploy --config config/my_project.yaml --env prod
```

## Project Structure

```
src/
├── core/
│   ├── config.py          # Configuration management (~50 LOC)
│   ├── fabric_wrapper.py  # Thin CLI wrapper (~80 LOC)
│   ├── git_integration.py # Git + Fabric sync (~60 LOC)
│   └── audit.py          # Audit logging (~30 LOC)
├── templates/
│   ├── etl_workspace.py   # ETL workspace template (~40 LOC)
│   └── analytics_workspace.py # Analytics template (~20 LOC)
└── fabric_deploy.py       # Main CLI (~50 LOC)

config/
├── templates/
│   ├── basic_etl.yaml
│   ├── advanced_analytics.yaml
│   └── data_science.yaml
└── environments/
    ├── dev.yaml
    ├── staging.yaml
    └── prod.yaml
```

## Total LOC: ~270 (vs original 1,830)

## Configuration Examples

See `config/templates/` for organization-agnostic templates that can be customized for any project.

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
- ✅ Folder structure (Bronze/Silver/Gold medallion)
- ✅ Item creation (Lakehouses, Warehouses, Notebooks, Pipelines)
- ✅ Git integration and branch management
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

## Learnings Applied

This project incorporates key learnings from the original implementation:

1. **Build vs Buy Assessment** - Use official tools wherever possible
2. **Progressive Complexity** - Start simple, add features incrementally  
3. **Stakeholder Alignment** - Configuration-driven, easy to understand
4. **Maintenance Focus** - Minimal custom code, maximum leverage
5. **Evolution Strategy** - Built to adapt as Fabric CLI evolves

## Migration from Custom Solutions

If migrating from a custom Fabric API solution:

1. **Assessment** - Use `scripts/analyze_custom_solution.py` to identify what can be replaced with CLI
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