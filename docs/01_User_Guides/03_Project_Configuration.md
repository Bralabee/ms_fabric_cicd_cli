# Project Configuration Guide

> **Audience**: Config Authors, Platform Engineers | **Time**: 20–40 min | **Deployment Path**: All
> **Difficulty**: Intermediate | **Prerequisites**: Understanding of Fabric resource types
> **See also**: [Blueprint Catalog](07_Blueprint_Catalog.md) for templates | [CLI Reference](CLI_REFERENCE.md) for config format & commands | [00_START_HERE.md](00_START_HERE.md) for orientation

This guide covers how to create and customize project configuration files for the USF Fabric CLI CI/CD toolkit.

## Overview

Project configuration files are YAML documents that define what Fabric resources to deploy. They act as the "blueprint" for your deployment, specifying:

- **Workspace settings** — Name, display name, capacity, domain, Git integration
- **Folder structure** — Numbered convention (`000 Orchestrate`, `100 Ingest`, … `999 Libraries`)
- **Folder rules** — Post-Git-Sync item placement (moves items from workspace root into folders)
- **Security principals** — Admin, Member, Contributor, Viewer access assignments
- **Deployment pipeline** — Dev → Test → Prod promotion stage definitions
- **Resources (optional)** — Lakehouses, warehouses, notebooks, pipelines, and 54+ other Fabric item types
- **Environment overrides** — DEV/TEST/PROD-specific settings

> **Current Standard — Git-Sync-Only**: All current blueprint templates use a "Git-sync-only"
> strategy where the CLI manages the **workspace envelope** (workspace, folders, principals, Git
> connection, deployment pipeline) while **Fabric items** (lakehouses, notebooks, pipelines) are
> committed to Git and synced into the workspace by Fabric Git Sync. The `lakehouses:`,
> `notebooks:`, and `resources:` arrays in blueprints are intentionally empty (`[]`). After Git
> Sync places items at the workspace root, `fabric-cicd organize-folders` uses `folder_rules`
> to move them into the correct folders.
>
> The CLI still supports populating item arrays for legacy configs or testing, but new projects
> should follow the Git-sync-only pattern.

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

| Template Name | Use Case | Key Features |
|---------------|----------|--------------|
| `minimal_starter` | Learning, POCs, solo projects | Minimal config, small folder set |
| `basic_etl` | Simple data ingestion and transformation | Full numbered folders, folder_rules, deployment pipeline |
| `advanced_analytics` | Complex analytics with ML capabilities | Extended folder_rules, multi-environment overrides |
| `data_science` | Research and experimentation | Notebook-focused folder_rules, environments |
| `extensive_example` | Enterprise reference architecture | All config sections populated (reference only) |
| `medallion` | Medallion Architecture data product | 3-stage pipeline, comprehensive folder_rules |
| `realtime_streaming` | IoT and event-driven architectures | Eventstream/KQL folder_rules, real-time patterns |
| `compliance_regulated` | Healthcare, finance, government workloads | Enhanced audit config, strict principal controls |
| `data_mesh_domain` | Domain-driven data product architecture | Multi-domain structure, cross-domain sharing |
| `migration_hybrid` | Cloud migration projects | Combined lakehouse + warehouse patterns |
| `specialized_timeseries` | Time-series, APM, and log analytics | KQL/Eventstream folder_rules, time-series patterns |

> **Tip:** Review [07_Blueprint_Catalog.md](07_Blueprint_Catalog.md) for detailed descriptions of each template's resources and folder structures.

---

## Configuration Structure

A project configuration file contains the following key sections:

### Workspace Section

```yaml
workspace:
  name: "acme-iot-analytics"            # DNS-safe workspace identifier
  display_name: "Acme IoT Analytics"    # Human-readable name shown in Fabric portal
  description: "IoT analytics workspace"
  capacity_id: "${FABRIC_CAPACITY_ID}"  # Fabric capacity GUID
  domain: "${FABRIC_DOMAIN_NAME}"       # Optional: Fabric domain for governance

  # Git Integration (required for Git-sync-only strategy)
  git_repo: "${GIT_REPO_URL}"           # Azure DevOps or GitHub repo URL
  git_branch: "main"                    # Branch for Git integration
  git_directory: "/"                    # Root directory in repo
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | **Yes** | DNS-safe workspace name (lowercase, hyphens) |
| `display_name` | No | Human-readable name for the Fabric portal |
| `description` | No | Workspace description |
| `capacity_id` | **Yes** | Fabric capacity GUID (supports `${VAR}` substitution) |
| `domain` | No | Fabric domain name for governance grouping |
| `git_repo` | No | Git repository clone URL |
| `git_branch` | No | Git branch (default: `main`) |
| `git_directory` | No | Directory within repo (default: `/`) |

### Folders Section

All current blueprint templates use the **numbered folder convention** for consistent
navigation and governance across workspaces:

```yaml
folders:
  - "000 Orchestrate"   # Pipelines, DataflowGen2, scheduling
  - "100 Ingest"        # Eventstreams, data connectors
  - "200 Store"         # Lakehouses, warehouses
  - "300 Prepare"       # Notebooks, data transformation
  - "400 Model"         # Semantic models, KQL databases
  - "500 Visualize"     # Reports, dashboards
  - "999 Libraries"     # Shared libraries, environments
  - "Archive"           # Retired items
```

> **Note**: The numbered prefix ensures folders appear in pipeline-stage order in the
> Fabric portal. This convention is enforced across all current blueprints and consumer
> repo templates.

### Folder Rules Section

Fabric Git Sync places all items at the **workspace root**. After sync completes,
`fabric-cicd organize-folders` uses these rules to move items into their designated folders:

```yaml
folder_rules:
  - type: DataPipeline
    folder: "000 Orchestrate"
  - type: DataflowGen2
    folder: "000 Orchestrate"
  - type: Eventstream
    folder: "100 Ingest"
  - type: Lakehouse
    folder: "200 Store"
  - type: Warehouse
    folder: "200 Store"
  - type: Notebook
    folder: "300 Prepare"
  - type: SemanticModel
    folder: "400 Model"
  - type: Report
    folder: "500 Visualize"
  - type: Environment
    folder: "999 Libraries"
```

You can also match by item name for fine-grained placement:

```yaml
folder_rules:
  - type: Notebook
    name: nb_orchestrate     # Specific notebook goes to Orchestrate
    folder: "000 Orchestrate"
  - type: Notebook            # All other notebooks go to Prepare
    folder: "300 Prepare"
```

> **Usage**: After Git Sync or deployment, run:
> ```bash
> fabric-cicd organize-folders config/projects/acme_corp/sales.yaml --env dev
> # Add --dry-run to preview moves without executing
> ```

### Lakehouses Section

> **Git-sync-only note**: In the current standard, lakehouses are committed to Git and
> synced by Fabric. This array is `[]` in current blueprints. Use it only if your workflow
> requires the CLI to create lakehouses directly.

```yaml
lakehouses:
  - name: "raw_data_lakehouse"
    folder: "200 Store"
    description: "Raw ingestion layer for all data sources"
  - name: "curated_lakehouse"
    folder: "200 Store"
    description: "Cleansed and validated data"
```

### Warehouses Section

> **Git-sync-only note**: Same as lakehouses — this array is `[]` in current blueprints.

```yaml
warehouses:
  - name: "reporting_warehouse"
    folder: "200 Store"
    description: "Star schema for BI reporting"
```

### Notebooks Section

> **Git-sync-only note**: Same as lakehouses — this array is `[]` in current blueprints.
> Notebooks are committed to Git and synced into the workspace.

```yaml
notebooks:
  - name: "bronze_to_silver_transform"
    folder: "300 Prepare"
    file_path: "src/usf_fabric_cli/templates/notebooks/transform.py"  # Import from file
    description: "Data cleansing and validation"
  - name: "silver_to_gold_aggregate"
    folder: "300 Prepare"
    content: |
      # Inline notebook content
      lakehouse_name = "{{ environment }}_curated_lakehouse"
```

### Pipelines Section

> **Git-sync-only note**: Same as lakehouses — this array is `[]` in current blueprints.

```yaml
pipelines:
  - name: "daily_ingestion_pipeline"
    folder: "000 Orchestrate"
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

Define who gets access to the workspace. Only `id` and `role` are required:

```yaml
principals:
  - id: "${AZURE_CLIENT_ID}"
    role: "Admin"
    description: "Deployment Service Principal"
  - id: "${ADDITIONAL_ADMIN_PRINCIPAL_ID}"
    role: "Admin"
    description: "Platform team security group"
  - id: "${ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID}"
    role: "Contributor"
    description: "Project contributors"
```

| Field | Required | Description |
|-------|----------|-------------|
| `id` | **Yes** | Object ID (GUID) of a user, group, or service principal in Entra ID |
| `role` | **Yes** | One of: `Admin`, `Member`, `Contributor`, `Viewer` |
| `description` | No | Human-readable label for documentation |

> **Note**: The schema does **not** include a `type` field. The CLI auto-detects whether
> the principal is a user, group, or service principal from the Entra ID object ID.

### Deployment Pipeline Section

Define a Fabric Deployment Pipeline for Dev → Test → Prod promotion:

```yaml
deployment_pipeline:
  name: "Acme Sales Pipeline"
  stages:
    - name: "Development"
      workspace: "acme-sales-dev"
    - name: "Test"
      workspace: "acme-sales-test"
      capacity_id: "${FABRIC_TEST_CAPACITY_ID}"
    - name: "Production"
      workspace: "acme-sales-prod"
      capacity_id: "${FABRIC_PROD_CAPACITY_ID}"
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | **Yes** | Deployment Pipeline display name in Fabric |
| `stages[].name` | **Yes** | Stage name (e.g., `Development`, `Test`, `Production`) |
| `stages[].workspace` | **Yes** | Workspace name for this stage |
| `stages[].capacity_id` | No | Override capacity for this stage |

> **Usage**: After deploy, promote content between stages:
> ```bash
> fabric-cicd promote --pipeline-name "Acme Sales Pipeline" --source-stage Development --target-stage Test
> ```

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
- [ ] Folders use the numbered convention (`000 Orchestrate`, `100 Ingest`, etc.)
- [ ] `folder_rules` map item types to the correct folders
- [ ] Principals have correct Object IDs and roles
- [ ] Deployment pipeline stages match your promotion strategy
- [ ] Notebook file paths exist (if using `file_path` in non-Git-sync configs)

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
    folder: "200 Store"
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
    folder: "200 Store"
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
    folder: "300 Prepare"
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
        role: "Admin"
```

---

## Next Steps

- **[04_Docker_Deployment.md](04_Docker_Deployment.md)** - Learn how to deploy via Docker
- **[02_CLI_Walkthrough.md](02_CLI_Walkthrough.md)** - DEV → TEST → PROD promotion workflows
- **[07_Blueprint_Catalog.md](07_Blueprint_Catalog.md)** - Detailed template documentation
