# Project Configuration Guide

This guide covers how to create and customize project configuration files for the USF Fabric CLI CI/CD toolkit.

## Overview

Project configuration files are YAML documents that define what Fabric resources to deploy. They act as the "blueprint" for your deployment, specifying:

- **Workspace settings** - Name, capacity, Git integration
- **Resources** - Lakehouses, warehouses, notebooks, pipelines, and 54+ other Fabric item types
- **Folder structure** - Medallion architecture (Bronze/Silver/Gold) organization
- **Security principals** - Admin and contributor access assignments
- **Environment overrides** - DEV/TEST/PROD-specific settings

Without a valid configuration file, the CLI cannot deploy resources. Configuration files enable:

- **Reproducible deployments** across environments
- **Version-controlled infrastructure** via Git
- **Standardized resource naming** across projects
- **Consistent security assignments** for all workspaces

---

## Generation Methods

### Method 1: Using generate_project.py (Recommended)

The `generate_project.py` script creates a customized configuration from a blueprint template:

```bash
# Activate the conda environment first
conda activate fabric-cli-cicd

# Generate a project configuration
python -m usf_fabric_cli.scripts.dev.generate_project "Organization Name" "Project Name" --template <template_name>

# Example: Create a real-time streaming project for Acme Corp
python -m usf_fabric_cli.scripts.dev.generate_project "Acme Corp" "IoT Analytics" --template realtime_streaming
```

**Output location:** `config/projects/<org_slug>/<project_slug>.yaml`

For the example above: `config/projects/acme_corp/iot_analytics.yaml`

> **Tip:** Use quotes around organization and project names that contain spaces.

### Method 2: Copying a Blueprint Template

If you prefer manual customization, copy a blueprint template directly:

```bash
# List available templates
ls src/usf_fabric_cli/templates/blueprints/

# Copy a template to your project directory
mkdir -p config/projects/my_org
cp src/usf_fabric_cli/templates/blueprints/advanced_analytics.yaml config/projects/my_org/my_project.yaml

# Edit the file
code config/projects/my_org/my_project.yaml
```

> **Note:** When copying manually, you must replace all placeholder values (e.g., `${ORGANIZATION_NAME}`, `${PROJECT_NAME}`) yourself.

---

## Available Templates

The toolkit includes 11 pre-built blueprint templates for common use cases:

| Template Name | Use Case | Key Resources |
|---------------|----------|---------------|
| `minimal_starter` | Learning, POCs, solo projects | 1 Lakehouse, 1 Notebook, minimal configuration |
| `basic_etl` | Simple data ingestion and transformation | 1 Lakehouse, 2 Notebooks, Bronze/Silver/Gold folders |
| `advanced_analytics` | Complex analytics with ML capabilities | 2 Lakehouses, 1 Warehouse, Notebooks, Environments |
| `data_science` | Research and experimentation | Notebooks, Environments, ML Models |
| `extensive_example` | Enterprise reference architecture | Full suite of Fabric items (reference only) |
| `medallion` | Medallion Architecture (Bronze/Silver/Gold) | 3 Lakehouses, 1 Warehouse, 3 Notebooks, 1 Pipeline |
| `realtime_streaming` | IoT and event-driven architectures | Eventstream, KQL Database, Reflex, Lakehouse |
| `compliance_regulated` | Healthcare, finance, government workloads | Enhanced audit logging, strict access controls |
| `data_mesh_domain` | Domain-driven data product architecture | Multiple domains, data contracts, cross-domain sharing |
| `migration_hybrid` | Cloud migration projects | Combined lakehouse + warehouse, migration tooling |
| `specialized_timeseries` | Time-series, APM, and log analytics | KQL Database, Eventstream, time-series pipelines |

> **Tip:** Review [07_Blueprint_Catalog.md](07_Blueprint_Catalog.md) for detailed descriptions of each template's resources and folder structures.

---

## Configuration Structure

A project configuration file contains the following key sections:

### Workspace Section

```yaml
workspace:
  name: "acme-iot-analytics"          # Workspace display name
  capacity_id: "${FABRIC_CAPACITY_ID}" # Fabric capacity (F2, F64, etc.)
  git_repo: "${GIT_REPO_URL}"          # Optional: Azure DevOps or GitHub repo
  git_branch: "main"                   # Branch for Git integration
  git_directory: "/"                   # Root directory in repo
```

### Folders Section

```yaml
folders:
  - "Bronze"      # Raw data landing zone
  - "Silver"      # Cleansed and conformed data
  - "Gold"        # Business-ready aggregates
  - "Notebooks"   # Transformation logic
  - "Pipelines"   # Orchestration definitions
```

### Lakehouses Section

```yaml
lakehouses:
  - name: "raw_data_lakehouse"
    folder: "Bronze"
    description: "Raw ingestion layer for all data sources"
  - name: "curated_lakehouse"
    folder: "Silver"
    description: "Cleansed and validated data"
```

### Warehouses Section

```yaml
warehouses:
  - name: "reporting_warehouse"
    folder: "Gold"
    description: "Star schema for BI reporting"
```

### Notebooks Section

```yaml
notebooks:
  - name: "bronze_to_silver_transform"
    folder: "Notebooks"
    file_path: "src/usf_fabric_cli/templates/notebooks/transform.py"  # Import from file
    description: "Data cleansing and validation"
  - name: "silver_to_gold_aggregate"
    folder: "Notebooks"
    content: |
      # Inline notebook content
      lakehouse_name = "{{ environment }}_curated_lakehouse"
```

### Pipelines Section

```yaml
pipelines:
  - name: "daily_ingestion_pipeline"
    folder: "Pipelines"
    description: "Orchestrates daily data refresh"
```

### Generic Resources Section

For Fabric item types beyond the standard sections, use the `resources` array:

```yaml
resources:
  - type: "Eventstream"
    name: "iot_events"
    description: "Ingest from IoT Hub"
  - type: "KQLDatabase"
    name: "telemetry_db"
  - type: "Reflex"
    name: "alert_monitor"
  - type: "SemanticModel"
    name: "sales_model"
```

> **Note:** The `resources` section supports all 54+ Fabric item types via the `create_item` wrapper.

### Principals Section

```yaml
principals:
  - id: "${AZURE_CLIENT_ID}"
    type: "ServicePrincipal"
    role: "Admin"
  - id: "${ADDITIONAL_ADMIN_PRINCIPAL_ID}"
    type: "Group"
    role: "Admin"
  - id: "${ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID}"
    type: "Group"
    role: "Contributor"
```

### Environments Section

> **v1.7.6+**: Inline `environments:` blocks are now fully supported in the config schema. When defined inline, they take **priority** over external files in `config/environments/*.yaml`. The `environments` key is stripped before schema validation, so older CLI versions that don't support it will reject configs containing this block — upgrade to v1.7.6+.

```yaml
environments:
  dev:
    workspace:
      name: "acme-iot-analytics-dev"
      capacity_id: "${DEV_CAPACITY_ID}"
  test:
    workspace:
      name: "acme-iot-analytics-test"
      capacity_id: "${TEST_CAPACITY_ID}"
  prod:
    workspace:
      name: "acme-iot-analytics-prod"
      capacity_id: "${PROD_CAPACITY_ID}"
```

**How inline environments work:** During config loading, the CLI:
1. Extracts the `environments:` block from the YAML
2. Merges the selected environment's overrides into the base config (deep merge)
3. Strips the `environments` meta-key before JSON schema validation
4. Inline environments override external `config/environments/<env>.yaml` files

---

## Environment Variable Placeholders

Configuration files use `${VAR_NAME}` syntax for environment variable substitution. Common variables:

### Azure Authentication

| Variable | Description | Required |
|----------|-------------|----------|
| `AZURE_CLIENT_ID` | Service Principal Client ID | Yes |
| `AZURE_CLIENT_SECRET` | Service Principal Secret | Yes |
| `AZURE_TENANT_ID` | Azure AD Tenant ID | Yes |

### Fabric Resources

| Variable | Description | Required |
|----------|-------------|----------|
| `FABRIC_CAPACITY_ID` | Default Fabric capacity (e.g., `F2`, `F64`) | Yes |
| `DEV_CAPACITY_ID` | Development environment capacity | No |
| `TEST_CAPACITY_ID` | Test environment capacity | No |
| `PROD_CAPACITY_ID` | Production environment capacity | No |

### Security Principals

| Variable | Description | Required |
|----------|-------------|----------|
| `ADDITIONAL_ADMIN_PRINCIPAL_ID` | Entra ID group/user for Admin role | Yes* |
| `ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID` | Entra ID group/user for Contributor role | Yes* |
| `DEV_ADMIN_OBJECT_ID` | Dev environment admin (if different) | No |

> *Required for all templates as of v1.3.0

### Git Integration

| Variable | Description | Required |
|----------|-------------|----------|
| `GIT_REPO_URL` | Azure DevOps or GitHub repository URL | No |
| `AZURE_DEVOPS_PAT` | Personal Access Token for ADO | Conditional |
| `GITHUB_TOKEN` | GitHub Personal Access Token | Conditional |

### Example .env File

```bash
# Azure Authentication
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=your-secret-value
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Fabric Resources
FABRIC_CAPACITY_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
DEV_CAPACITY_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Security Principals (MANDATORY)
ADDITIONAL_ADMIN_PRINCIPAL_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Git Integration (Optional)
GIT_REPO_URL=https://dev.azure.com/org/project/_git/repo
AZURE_DEVOPS_PAT=your-ado-pat
```

---

## Mandatory Security Principals

As of **v1.3.0**, all blueprint templates require two security principal environment variables:

### ADDITIONAL_ADMIN_PRINCIPAL_ID

- **Purpose:** Grants Admin role to an Entra ID security group or user
- **Typical use:** Platform team or workspace owners who need full control
- **Permissions:** Create/delete items, manage workspace settings, assign roles

### ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID

- **Purpose:** Grants Contributor role to an Entra ID security group or user
- **Typical use:** Development team members who create and modify artifacts
- **Permissions:** Create/edit items, run notebooks and pipelines, read all data

### Why Mandatory?

1. **Security best practice:** Ensures human oversight beyond the Service Principal
2. **Break-glass access:** If SP credentials are rotated, admins retain access
3. **Audit compliance:** Named principals enable proper access tracking
4. **Team collaboration:** Contributors can work without SP credentials

### Finding Principal IDs

```bash
# Using Azure CLI
az ad group show --group "Fabric-Platform-Admins" --query id -o tsv
az ad user show --id "user@contoso.com" --query id -o tsv

# In Azure Portal
# Entra ID → Groups → Select group → Object ID
# Entra ID → Users → Select user → Object ID
```

---

## Post-Generation Checklist

After generating a configuration file, complete these steps:

### 1. Set Required Environment Variables

```bash
# Copy the template .env file
cp .env.example .env

# Edit with your values
code .env
```

Ensure these are set:

- [ ] `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`
- [ ] `FABRIC_CAPACITY_ID`
- [ ] `ADDITIONAL_ADMIN_PRINCIPAL_ID`
- [ ] `ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID`

### 2. Validate the Configuration

```bash
# Run validation (checks schema + env vars)
make validate config=config/projects/acme_corp/iot_analytics.yaml
```

### 3. Run Pre-flight Diagnostics

```bash
# Check CLI version, credentials, and capacity access
python -m usf_fabric_cli.scripts.admin.preflight_check
```

### 4. Review Generated Resources

Open the YAML file and verify:

- [ ] Workspace name follows your naming conventions
- [ ] Correct number of lakehouses/warehouses
- [ ] Notebook file paths exist (if using `file_path`)
- [ ] Folder structure matches your architecture

### 5. Customize Environment Overrides (Optional)

```yaml
environments:
  dev:
    workspace:
      capacity_id: "${DEV_CAPACITY_ID}"  # Smaller capacity for dev
  prod:
    workspace:
      capacity_id: "${PROD_CAPACITY_ID}"  # Larger capacity for prod
```

### 6. Deploy to Development

```bash
# Deploy to dev environment first
make deploy config=config/projects/acme_corp/iot_analytics.yaml env=dev
```

---

## Common Customizations

### Changing the Workspace Name

Edit the `workspace.name` field:

```yaml
workspace:
  name: "my-custom-workspace-name"  # Must be DNS-safe (lowercase, hyphens)
```

> **Note:** Workspace names must be unique within your tenant.

### Adding Additional Lakehouses

Append to the `lakehouses` array:

```yaml
lakehouses:
  - name: "raw_data_lakehouse"
    folder: "Bronze"
    description: "Existing lakehouse"
  # Add new lakehouse
  - name: "archive_lakehouse"
    folder: "Archive"
    description: "Long-term data retention"
```

### Adding a Warehouse

```yaml
warehouses:
  - name: "analytics_warehouse"
    folder: "Gold"
    description: "Star schema for Power BI"
```

### Adding Generic Fabric Items

Use the `resources` section for any Fabric item type:

```yaml
resources:
  - type: "Eventstream"
    name: "realtime_events"
    description: "Event ingestion from IoT Hub"
  - type: "KQLDatabase"
    name: "operational_logs"
  - type: "DataPipeline"
    name: "orchestration_pipeline"
```

### Configuring Git Integration

Add Git settings to the workspace section:

```yaml
workspace:
  name: "my-workspace"
  capacity_id: "${FABRIC_CAPACITY_ID}"
  git_repo: "${GIT_REPO_URL}"
  git_branch: "main"
  git_directory: "/"
  git_provider: "AzureDevOps"  # or "GitHub"
```

Then set the corresponding environment variable:

```bash
# For Azure DevOps
GIT_REPO_URL=https://dev.azure.com/myorg/myproject/_git/myrepo
AZURE_DEVOPS_PAT=your-pat-token

# For GitHub
GIT_REPO_URL=https://github.com/myorg/myrepo
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
```

### Adding Environment-Specific Notebooks

```yaml
notebooks:
  - name: "data_processing"
    folder: "Notebooks"
    content: |
      # Environment-aware notebook
      env = "{{ environment }}"
      lakehouse = f"{env}_data_lakehouse"

      # Connection strings from secrets
      storage_url = "{{ secrets.STORAGE_ACCOUNT_URL }}"
```

### Configuring Multiple Environments

```yaml
environments:
  dev:
    workspace:
      name: "project-dev"
      capacity_id: "F2"  # Trial/dev capacity
    principals:
      - id: "${DEV_TEAM_GROUP_ID}"
        type: "Group"
        role: "Contributor"
  test:
    workspace:
      name: "project-test"
      capacity_id: "F8"
  prod:
    workspace:
      name: "project-prod"
      capacity_id: "F64"  # Production capacity
    principals:
      - id: "${PROD_ADMIN_GROUP_ID}"
        type: "Group"
        role: "Admin"
```

---

## Next Steps

- **[04_Docker_Deployment.md](04_Docker_Deployment.md)** - Learn how to deploy via Docker
- **[02_CLI_Walkthrough.md](02_CLI_Walkthrough.md)** - DEV → TEST → PROD promotion workflows
- **[07_Blueprint_Catalog.md](07_Blueprint_Catalog.md)** - Detailed template documentation
