# CLI Scenario Walkthrough: From Zero to Production

This guide provides a hands-on, step-by-step walkthrough of the core workflows in the USF Fabric CI/CD framework. It demonstrates how to use the command-line tools to manage the full lifecycle of a Microsoft Fabric data product, from initialization to production deployment.

## Prerequisites

Ensure your environment is set up:

```bash
# 1. Activate the environment
conda activate fabric-cli-cicd

# 2. Verify credentials are loaded
# Ensure .env exists with either FABRIC_TOKEN or AZURE_CLIENT_ID
grep -E "FABRIC_TOKEN|AZURE_CLIENT_ID" .env
```

---

## Scenario 1: Onboarding a New Data Product

**Goal:** You are starting a new project called "Supply Chain Analytics" for "Acme Corp". You need to set up the infrastructure (Workspace, Lakehouse, etc.) quickly.

### Step 1: Generate the Configuration
Instead of writing YAML from scratch, use the generator script to scaffold your project based on a standard blueprint.

```bash
# Run the generator
python scripts/generate_project.py \
  "Acme Corp" \
  "Supply Chain" \
  --template basic_etl

# Note: --capacity-id and --git-repo default to ${FABRIC_CAPACITY_ID} and ${GIT_REPO_URL}
# This ensures your configuration is portable and uses your .env file.
```

**Output:**
> ✅ Generated configuration: `config/projects/acme_corp/supply_chain.yaml`

### Step 2: Review and Customize
Open the generated file to verify the structure.

```bash
# Edit the file
vim config/projects/acme_corp/supply_chain.yaml
```

*Example Customization:*
```yaml
# config/projects/acme_corp/supply_chain.yaml
workspace:
  display_name: "Acme Supply Chain [{{ env }}]" # {{ env }} is auto-replaced
  
folders:
  - "Raw Data"
  - "Transformation"
  - "Gold Layer"

items:
  lakehouses:
    - name: "supply_chain_lakehouse"
```

### Step 3: Deploy to Development
Provision the initial environment.

> **Note on Security:** The CLI automatically injects mandatory security principals (Additional Admin and Contributor) defined in your environment variables (`ADDITIONAL_ADMIN_PRINCIPAL_ID`, etc.) into every workspace it creates. You do not need to manually add these to your YAML configuration.

```bash
# Validate first
python src/fabric_deploy.py validate config/projects/acme_corp/supply_chain.yaml

# Deploy to Dev
python src/fabric_deploy.py deploy \
  config/projects/acme_corp/supply_chain.yaml \
  --env dev
```

**Result:** A new workspace `acme-supply-chain-dev` is created with the specified Lakehouse, folders, and mandatory security principals.

---

## Scenario 2: The Feature Branch Workflow

**Goal:** You need to add a new "Inventory Optimization" module. You want to test this in isolation without breaking the shared DEV environment.

### Step 1: Create a Feature Branch
Standard Git workflow.

```bash
git checkout -b feature/inventory-opt
```

### Step 2: Deploy an Isolated Workspace
Use the `--force-branch-workspace` flag to tell the deployer to create a temporary workspace for this branch.

> **Note:** You do **not** need a separate YAML configuration file for feature branches. The CLI uses the `dev` environment configuration as a base and dynamically generates a unique workspace name (e.g., `acme-supply-chain-inventory-opt-dev`).

```bash
python src/fabric_deploy.py deploy \
  config/projects/acme_corp/supply_chain.yaml \
  --env dev \
  --branch feature/inventory-opt \
  --force-branch-workspace
```

**Result:**
- A new workspace `acme-supply-chain-feature-inventory-opt` is created.
- It is a clone of the Dev configuration but isolated.
- You can run your tests here safely.

---

## Scenario 3: Promoting to Production

**Goal:** Your feature is merged to `main`, and you are ready to deploy to the Production capacity.

### Step 1: Deploy to Prod
Switch the environment flag to `prod`. The tool automatically picks up production-specific settings (like Capacity IDs or Service Principals) from `config/environments/prod.yaml`.

```bash
python src/fabric_deploy.py deploy \
  config/projects/acme_corp/supply_chain.yaml \
  --env prod \
  --diagnose  # Enable extra diagnostics for prod
```

**Result:**
- The `acme-supply-chain-prod` workspace is updated.
- If it doesn't exist, it is created.
- If it exists, it is updated idempotently (only changes are applied).

---

## Scenario 4: Maintenance & Cleanup

**Goal:** The "Inventory Optimization" feature is merged, and you want to delete the temporary workspace to save capacity units.

### Step 1: Identify Workspaces
List your workspaces to find the one to delete.

```bash
python scripts/utilities/list_workspaces.py > workspaces.txt
grep "feature-inventory-opt" workspaces.txt
```

### Step 2: Bulk Destroy
Create a file with the workspaces to delete and run the bulk destroy script.

```bash
# Create a list file
echo "acme-supply-chain-feature-inventory-opt" > delete_list.txt

# Run bulk destroy
python scripts/bulk_destroy.py delete_list.txt
```

**Result:** The feature workspace is removed, freeing up capacity.

---

## Summary of Commands

| Task | Command |
|------|---------|
| **Scaffold** | `python scripts/generate_project.py ...` |
| **Validate** | `python src/fabric_deploy.py validate <config>` |
| **Deploy (Dev)** | `python src/fabric_deploy.py deploy <config> --env dev` |
| **Deploy (Feature)** | `python src/fabric_deploy.py deploy <config> --env dev --branch <name> --force-branch-workspace` |
| **Deploy (Prod)** | `python src/fabric_deploy.py deploy <config> --env prod` |
| **Cleanup** | `python scripts/bulk_destroy.py <list_file>` |

## Makefile Quick Reference (Local & Docker)

For day-to-day usage, the `Makefile` wraps the most common commands.

### Local Python

```bash
# Run unit tests
make test

# Validate a project config
make validate config=config/projects/acme_corp/supply_chain.yaml

# Deploy to dev
make deploy config=config/projects/acme_corp/supply_chain.yaml env=dev
```

### Docker (Multi-tenant via ENVFILE)

The Docker targets default to `.env`, but you can override the env file per organisation using `ENVFILE=...`.

```bash
# Build image
make docker-build

# Validate using Docker (Ricoh org)
make docker-validate \
  config=config/projects/ProductA/sales_project.yaml \
  ENVFILE=.env.ricoh

# Deploy to dev using Docker (Ricoh org)
make docker-deploy \
  config=config/projects/ProductA/sales_project.yaml \
  env=dev \
  ENVFILE=.env.ricoh

# Feature branch deploy using Docker
make docker-feature-deploy \
  config=config/projects/ProductA/sales_project.yaml \
  env=dev \
  branch=feature/new-analytics \
  ENVFILE=.env.ricoh

# Interactive shell inside the container
make docker-shell ENVFILE=.env.ricoh
```
