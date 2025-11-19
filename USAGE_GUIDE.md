# Usage Guide - Fabric CLI CI/CD Thin Wrapper

This guide demonstrates how to use the Fabric CLI CI/CD solution for any organization and project, incorporating all learnings from the original 1,830 LOC → 270 LOC optimization.

## Quick Start for Any Organization

### 1. Initial Setup

```bash
# Clone/setup the project
git clone <your-repo>
cd usf_fabric_cli_cicd

# Run setup script
chmod +x setup.sh
./setup.sh

# Optionally rerun the Python preflight if Fabric CLI/secrets change
python scripts/preflight_check.py --auto-install

# Activate environment
conda activate fabric-cli-cicd

# Configure your credentials
cp .env.template .env
vim .env  # Edit with your values
```

> **Note:** `python-dotenv` automatically loads `.env` whenever `fabric_deploy.py` runs, so you do not need to export secrets manually.

### 2. Generate Your Project Configuration

```bash
# Generate configuration for your organization
python scripts/generate_project.py \
  "Contoso Inc" \
  "Customer Analytics" \
  --template basic_etl \
  --capacity-id F64 \
  --git-repo https://github.com/contoso/customer-analytics

# This creates: config/contoso-inc-customer-analytics.yaml
```

### 3. Deploy Your First Workspace

```bash
# Validate configuration
python src/fabric_deploy.py validate config/contoso-inc-customer-analytics.yaml

# Deploy to development
python src/fabric_deploy.py deploy config/contoso-inc-customer-analytics.yaml --env dev

# Deploy feature branch (creates separate workspace)
python src/fabric_deploy.py deploy config/contoso-inc-customer-analytics.yaml \
  --env dev --branch feature/new-analytics --force-branch-workspace
```

## End-to-End Scenarios

### Scenario 1: Basic ETL Project for Manufacturing Company

```bash
# Generate configuration
python scripts/generate_project.py \
  "Acme Manufacturing" \
  "Production Analytics" \
  --template basic_etl \
  --capacity-id F32 \
  --git-repo https://github.com/acme/production-analytics

# Customize the generated config
vim config/acme-manufacturing-production-analytics.yaml
```

**Customization for Manufacturing:**
```yaml
# Custom folders for manufacturing
folders:
  - "Raw Sensors"      # IoT sensor data
  - "Production Lines" # Production line analytics
  - "Quality Control"  # QC data and reports
  - "Maintenance"      # Predictive maintenance
  - "Notebooks"        # Analysis notebooks

lakehouses:
  - name: "sensor_data_raw"
    folder: "Raw Sensors"
    description: "Raw IoT sensor data from production floor"
  
  - name: "production_metrics"
    folder: "Production Lines"
    description: "Processed production line metrics"

# Manufacturing team principals
principals:
  - id: "production-team@acme.com"
    role: "Contributor"
  - id: "quality-control@acme.com"
    role: "Viewer"
```

### Scenario 2: Advanced Analytics for Healthcare

```bash
# Generate healthcare analytics workspace
python scripts/generate_project.py \
  "HealthTech Solutions" \
  "Patient Outcomes Analytics" \
  --template advanced_analytics \
  --capacity-id F64 \
  --git-repo https://github.com/healthtech/patient-outcomes

# Deploy with HIPAA compliance considerations
python src/fabric_deploy.py deploy config/healthtech-solutions-patient-outcomes-analytics.yaml --env prod
```

**Healthcare Customization:**
```yaml
# HIPAA-compliant folder structure
folders:
  - "De-identified Data"  # PHI removed
  - "Clinical Analytics"  # Clinical insights
  - "Population Health"   # Population-level analysis
  - "ML Models"          # Predictive models
  - "Compliance Reports" # Audit and compliance

# Restricted access for healthcare
principals:
  - id: "clinical-data-team@healthtech.com"
    role: "Admin"
  - id: "data-scientists@healthtech.com"
    role: "Contributor"
  - id: "compliance-officers@healthtech.com"
    role: "Viewer"
```

### Scenario 3: Financial Services Risk Analytics

```bash
# Generate financial analytics workspace
python scripts/generate_project.py \
  "Global Bank Corp" \
  "Risk Analytics Platform" \
  --template advanced_analytics \
  --capacity-id F128 \
  --git-repo https://dev.azure.com/globalbank/risk-analytics

# Deploy with strict access controls
python src/fabric_deploy.py deploy config/global-bank-corp-risk-analytics-platform.yaml --env prod
```

**Financial Services Customization:**
```yaml
# Risk-focused folder structure
folders:
  - "Market Data"        # External market feeds
  - "Credit Risk"        # Credit risk models
  - "Operational Risk"   # Operational risk analysis
  - "Regulatory Reports" # Compliance reporting
  - "Stress Testing"     # Stress test scenarios

warehouses:
  - name: "risk_data_warehouse"
    folder: "Credit Risk"
    description: "Primary risk analytics warehouse"
  
  - name: "regulatory_reporting"
    folder: "Regulatory Reports" 
    description: "Regulatory compliance reporting"

# Financial services principals
principals:
  - id: "risk-management@globalbank.com"
    role: "Admin"
  - id: "quantitative-analysts@globalbank.com"
    role: "Contributor"
  - id: "regulators@globalbank.com"
    role: "Viewer"
```

## Feature Branch Workflows

### Development Workflow

```bash
# 1. Create feature branch
git checkout -b feature/customer-segmentation

# 2. Deploy feature-specific workspace (isolated testing)
python src/fabric_deploy.py deploy config/your-project.yaml \
  --env dev \
  --branch feature/customer-segmentation \
  --force-branch-workspace

# This creates workspace: "your-project-customer-segmentation"

# 3. Develop and test in isolated workspace
# 4. Merge to main when ready
# 5. Deploy to staging/production
```

### CI/CD Integration

The included GitHub Actions workflow automatically:

- **Pull Requests**: Creates feature branch workspaces
- **Develop Branch**: Deploys to development environment
- **Main Branch**: Deploys to staging → production

```yaml
# Customize .github/workflows/fabric-cicd.yml for your organization
env:
  FABRIC_TOKEN: ${{ secrets.YOUR_ORG_FABRIC_TOKEN }}
  TENANT_ID: ${{ secrets.YOUR_ORG_TENANT_ID }}
```

## Principal Management

### Adding Users and Groups

```yaml
# In your configuration file
principals:
  # Individual users
  - id: "john.doe@yourorg.com"
    role: "Admin"
  
  # Azure AD groups
  - id: "data-engineering-team@yourorg.com"
    role: "Contributor"
  
  # Service principals (for automation)
  - id: "12345678-1234-1234-1234-123456789012"  # Object ID
    role: "Contributor"
```

### Role Definitions

- **Admin**: Full workspace control
- **Contributor**: Can create/modify items
- **Viewer**: Read-only access

## Multi-Environment Management

### Environment-Specific Settings

```bash
# Development (smaller capacity, open access)
python src/fabric_deploy.py deploy config/project.yaml --env dev

# Staging (production-like, limited access)
python src/fabric_deploy.py deploy config/project.yaml --env staging

# Production (high capacity, restricted access)
python src/fabric_deploy.py deploy config/project.yaml --env prod
```

### Environment Overrides

Create `config/environments/{env}.yaml` files:

```yaml
# config/environments/prod.yaml
workspace:
  capacity_id: "F128"  # Higher capacity for production

principals:
  - id: "prod-admin@yourorg.com"
    role: "Admin"
  # More restrictive access in production
```

## Migration from Custom Solutions

### Analyze Existing Solution

```bash
# Analyze your current custom Fabric solution
python scripts/analyze_migration.py /path/to/your/custom/solution --output migration-report.json

# This generates:
# - LOC analysis
# - Component inventory
# - CLI replaceability assessment
# - Migration recommendations
```

### Migration Strategy

1. **Assessment Phase**
   - Run migration analyzer
   - Identify CLI-replaceable components
   - Estimate effort

2. **Incremental Migration**
   - Start with new projects using thin wrapper
   - Gradually migrate existing projects
   - Side-by-side comparison during transition

3. **Validation**
   - Deploy to development
   - Compare functionality with existing solution
   - Validate audit logs and compliance

## Advanced Configurations

### Custom Folder Structures

```yaml
# Retail analytics example
folders:
  - "Point of Sale"     # POS transaction data
  - "Inventory"         # Inventory management
  - "Customer Journey"  # Customer behavior analysis
  - "Seasonal Analysis" # Seasonal trend analysis
  - "Forecasting"       # Demand forecasting models
```

### Integration with External Systems

```yaml
# Git integration
workspace:
  git_repo: "https://github.com/yourorg/analytics"
  git_branch: "main"
  git_directory: "/fabric-workspace"

# Multiple git repositories
# (Configure through advanced deployment scripts)
```

### Custom Templates

Create your own template in `config/templates/`:

```yaml
# config/templates/retail_analytics.yaml
workspace:
  name: "retail-analytics-template"
  description: "Template for retail analytics projects"

folders:
  - "Point of Sale"
  - "Inventory"
  - "Customer Data"
  - "Marketing"

# Your specific retail analytics setup
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**
```bash
# Validate setup
python src/fabric_deploy.py diagnose

# Check environment variables
echo $FABRIC_TOKEN
echo $TENANT_ID
```

2. **Capacity Issues**
```bash
# Verify capacity ID exists and is accessible
# Update configuration with correct capacity
```

3. **Git Integration Issues**
```bash
# Validate Git repository access
git clone <your-repo-url>

# Check branch exists
git branch -a
```

4. **Principal Assignment Failures**
```bash
# Verify user/group exists in Azure AD
# Use Object ID for service principals, not Application ID
```

### Audit Trail

All operations are logged to `audit_logs/fabric_operations_YYYY-MM-DD.jsonl`:

```json
{"timestamp": "2024-01-01T10:00:00Z", "operation": "workspace_create", "workspace_name": "analytics", "success": true}
{"timestamp": "2024-01-01T10:01:00Z", "operation": "item_create", "details": {"item_type": "Lakehouse", "item_name": "raw_data"}}
```

Use for compliance reporting and troubleshooting.

## Best Practices

### 1. Configuration Management
- Use version control for configuration files
- Environment-specific overrides
- Template-based approach for consistency

### 2. Security
- Principle of least privilege for principals
- Environment-specific access controls
- Service principal for automation

### 3. Deployment Strategy
- Start with development environment
- Use feature branches for experimentation
- Gradual promotion through environments

### 4. Maintenance
- Regular template updates
- Monitor audit logs
- Update Fabric CLI regularly

### 5. Documentation
- Document organization-specific customizations
- Maintain environment setup guides
- Share templates across teams

## Support and Extension

This thin wrapper approach provides:

✅ **85% code reduction** (vs 1,830 LOC custom solutions)  
✅ **Configuration-driven** deployments  
✅ **Organization-agnostic** templates  
✅ **Feature branch** support  
✅ **Audit compliance** ready  
✅ **CI/CD integration** included  
✅ **Migration tools** for existing solutions  

For advanced scenarios not covered by Fabric CLI, extend the thin wrapper with minimal custom code (~30-50 LOC per feature).

The key principle: **Fabric CLI for 90% of operations, thin wrapper for the 10% gaps**.

---

**Next Steps:**
1. Generate your organization's configuration
2. Deploy to development environment
3. Set up CI/CD pipeline
4. Train team on new approach
5. Gradually migrate existing solutions