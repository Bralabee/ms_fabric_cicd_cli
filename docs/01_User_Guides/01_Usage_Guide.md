# Usage Guide - Fabric CLI CI/CD Thin Wrapper

This guide demonstrates how to use the Fabric CLI CI/CD solution for any organization and project, leveraging the thin wrapper architecture around the official Fabric CLI.

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
python scripts/admin/preflight_check.py --auto-install

# Activate environment
conda activate fabric-cli-cicd

# Configure your credentials
cp .env.template .env
vim .env  # Edit with your values
```

> **Note:** `python-dotenv` automatically loads `.env` whenever the CLI runs, so you do not need to export secrets manually.

### 2. Generate Your Project Configuration

```bash
# Generate configuration for your organization
python scripts/dev/generate_project.py \
  "Contoso Inc" \
  "Customer Analytics" \
  --template basic_etl \
  --capacity-id ${FABRIC_CAPACITY_ID} \
  --git-repo ${GIT_REPO_URL}

# Note: --capacity-id and --git-repo are optional. If omitted, they default to ${FABRIC_CAPACITY_ID} and ${GIT_REPO_URL}
# This creates: config/projects/contoso_inc/customer_analytics.yaml
```

### 3. Deploy Your First Workspace

```bash
# Validate configuration
python -m usf_fabric_cli.cli validate config/projects/contoso_inc/customer_analytics.yaml

# Deploy to development
python -m usf_fabric_cli.cli deploy config/projects/contoso_inc/customer_analytics.yaml --env dev

# Deploy feature branch (creates separate workspace)
python -m usf_fabric_cli.cli deploy config/projects/contoso_inc/customer_analytics.yaml \
  --env dev --branch feature/new-analytics --force-branch-workspace
```

## Workflow for Multiple Projects

This tool is designed to manage multiple projects and organizations from a single codebase.

1.  **Create Specific Configs**:
    *   Create `config/projects/ProductA/config.yaml`
    *   Create `config/projects/ProductB/config.yaml`
2.  **Define Environments**:
    *   Ensure `config/environments/prod.yaml` contains your production secrets/capacity IDs.
3.  **Deploy with Specifics**:
    *   Run: `python -m usf_fabric_cli.cli deploy config/projects/ProductA/config.yaml --env prod`
    *   Run: `python -m usf_fabric_cli.cli deploy config/projects/ProductB/config.yaml --env dev`

The `ConfigManager` looks at the file you passed (`config/projects/ProductA/config.yaml`), loads it, and then automatically looks for the environment override in `config/environments/{env}.yaml` to merge them. This allows you to maintain one "structure" file per project, while sharing "environment" settings (like Service Principals or Capacities) across them if needed.

## End-to-End Scenarios

### Scenario 1: Basic ETL Project for Manufacturing Company

```bash
# Generate configuration
python scripts/dev/generate_project.py \
  "Acme Manufacturing" \
  "Production Analytics" \
  --template basic_etl \
  --capacity-id ${FABRIC_CAPACITY_ID} \
  --git-repo ${GIT_REPO_URL}

# Customize the generated config
vim config/projects/acme_manufacturing/production_analytics.yaml
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

# Future-Proof Generic Resources
# Use this for any Fabric item type not explicitly listed above
resources:
  - type: "Eventstream"
    name: "iot_ingestion"
    folder: "Raw Sensors"
    description: "Real-time IoT data stream"
  
  - type: "KQLDatabase"
    name: "sensor_logs"
    folder: "Raw Sensors"

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
python scripts/dev/generate_project.py \
  "HealthTech Solutions" \
  "Patient Outcomes Analytics" \
  --template advanced_analytics \
  --capacity-id F64 \
  --git-repo https://github.com/healthtech/patient-outcomes

# Deploy with HIPAA compliance considerations
python -m usf_fabric_cli.cli deploy config/projects/healthtech_solutions/patient_outcomes_analytics.yaml --env prod
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
python scripts/dev/generate_project.py \
  "Global Bank Corp" \
  "Risk Analytics Platform" \
  --template advanced_analytics \
  --capacity-id F128 \
  --git-repo https://dev.azure.com/globalbank/risk-analytics

# Deploy with strict access controls
python -m usf_fabric_cli.cli deploy config/projects/global_bank_corp/risk_analytics_platform.yaml --env prod
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
python -m usf_fabric_cli.cli deploy config/your-project.yaml \
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
  AZURE_TENANT_ID: ${{ secrets.YOUR_ORG_TENANT_ID }}
```

## Principal Management

### Adding Users and Groups (Securely)

We recommend using environment variables for all principal IDs to keep sensitive information out of version control.

1. **Define variables in your configuration:**
```yaml
# In your configuration file (e.g., config/environments/prod.yaml)
principals:
  # Individual users
  - id: "${PROD_ADMIN_EMAIL}"
    role: "Admin"
  
  # Azure AD groups
  - id: "${PROD_VIEWERS_GROUP_ID}"
    role: "Viewer"
  
  # Service principals
  - id: "${AUTOMATION_SP_ID}"
    role: "Contributor"
```

2. **Set values in your `.env` file:**
```bash
PROD_ADMIN_EMAIL=john.doe@yourorg.com
PROD_VIEWERS_GROUP_ID=87654321-4321-4321-4321-210987654321
AUTOMATION_SP_ID=12345678-1234-1234-1234-123456789012
```

### Role Definitions

- **Admin**: Full workspace control
- **Contributor**: Can create/modify items
- **Viewer**: Read-only access

### Multi-Environment Management

### Environment-Specific Settings

Each environment (Dev, Staging, Prod) has its own configuration file in `config/environments/`. These files now use environment variables for principals to ensure security.

**Required Environment Variables:**

Ensure these are defined in your `.env` file (or CI/CD secrets):

**Development:**
- `DEV_ADMIN_EMAIL`: Email of the dev environment admin
- `DEV_ADMIN_OBJECT_ID`: Object ID for the dev admin group

**Staging:**
- `STAGING_ADMIN_EMAIL`: Email for staging admins
- `STAGING_QA_GROUP_ID`: Object ID for the QA team

**Production:**
- `PROD_ADMIN_EMAIL`: Email for production admins
- `PROD_VIEWERS_GROUP_ID`: Object ID for production viewers
- `PROD_AUTOMATION_SP_ID`: Object ID for the automation service principal

```bash
# Development (smaller capacity, open access)
python -m usf_fabric_cli.cli deploy config/project.yaml --env dev

# Staging (production-like, limited access)
python -m usf_fabric_cli.cli deploy config/project.yaml --env staging

# Production (high capacity, restricted access)
python -m usf_fabric_cli.cli deploy config/project.yaml --env prod
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
python scripts/admin/utilities/analyze_migration.py /path/to/your/custom/solution --output migration-report.json

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

Create your own template in `templates/blueprints/`:

```yaml
# templates/blueprints/retail_analytics.yaml
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
python -m usf_fabric_cli.cli diagnose

# Check environment variables
echo $FABRIC_TOKEN
echo $AZURE_TENANT_ID
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

### Bulk Workspace Cleanup

If you need to delete multiple workspaces (e.g., for cleanup), use the bulk destroy utility.

1. **Create a list file** (e.g., `workspaces_to_delete.txt`):
   ```text
   workspace-a
   workspace-b
   old-test-ws.Workspace
   ```
   *(Note: The script handles `fab list` output format automatically)*

2. **Run the script**:
   ```bash
   # Dry run (preview)
   python scripts/admin/bulk_destroy.py workspaces_to_delete.txt --dry-run

   # Execute
   python scripts/admin/bulk_destroy.py workspaces_to_delete.txt
   ```

### Audit Trail

All operations are logged to `audit_logs/fabric_operations_YYYY-MM-DD.jsonl`:

```json
{"timestamp": "2024-01-01T10:00:00Z", "operation": "workspace_create", "workspace_name": "analytics", "success": true}
{"timestamp": "2024-01-01T10:01:00Z", "operation": "item_create", "details": {"item_type": "Lakehouse", "item_name": "raw_data"}}
```

Use for compliance reporting and troubleshooting.

## Troubleshooting

### CI/CD Pipeline Failures

#### Authentication Failed (Exit Code 1)
If your CI/CD pipeline fails with `[AuthenticationFailed] Failed to get access token`, it means the GitHub Actions runner cannot authenticate with Microsoft Fabric.

**Solution:**
Ensure the following secrets are defined in your GitHub Repository Settings > Secrets and variables > Actions:

| Secret Name | Description |
|-------------|-------------|
| `AZURE_CLIENT_ID` | Service Principal Application ID |
| `AZURE_CLIENT_SECRET` | Service Principal Secret |
| `AZURE_TENANT_ID` | Azure AD Tenant ID |
| `FABRIC_CAPACITY_ID` | Fabric Capacity ID (for workspace creation) |

**Note:** Do not commit these values to `.env` files in the repository. Use GitHub Secrets for secure injection.

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

✅ **Fabric CLI-first** architecture (Fabric CLI handles 90% of operations)  
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