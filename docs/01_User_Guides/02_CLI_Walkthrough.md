# CLI Scenario Walkthrough: From Zero to Production

> **Audience**: CLI Power Users | **Time**: 30–45 min | **Deployment Path**: CLI commands
> **Difficulty**: Intermediate | **Prerequisites**: CLI installed, `.env` configured, conda active
> **See also**: [CLI Reference](CLI_REFERENCE.md) for all commands/flags | [00_START_HERE.md](00_START_HERE.md) for orientation

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
python -m usf_fabric_cli.scripts.dev.generate_project \
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
  - "000 Orchestrate"
  - "100 Ingest"
  - "200 Store"
  - "300 Prepare"
  - "400 Model"
  - "500 Visualize"
  - "999 Libraries"

# Items managed via Git Sync — arrays are intentionally empty
lakehouses: []
notebooks: []
```

### Step 3: Deploy to Development

Provision the initial environment.

> **Note on Security:** The CLI automatically injects mandatory security principals (Additional Admin and Contributor) defined in your environment variables (`ADDITIONAL_ADMIN_PRINCIPAL_ID`, etc.) into every workspace it creates. You do not need to manually add these to your YAML configuration.

```bash
# Validate first
make validate config=config/projects/acme_corp/supply_chain.yaml

# Deploy to Dev
make deploy config=config/projects/acme_corp/supply_chain.yaml env=dev
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
make docker-feature-deploy config=config/projects/acme_corp/supply_chain.yaml env=dev branch=feature/inventory-opt
# Or using CLI directly:
python -m usf_fabric_cli.cli deploy config/projects/acme_corp/supply_chain.yaml --env dev --branch feature/inventory-opt
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
make deploy config=config/projects/acme_corp/supply_chain.yaml env=prod
# Or using CLI directly:
python -m usf_fabric_cli.cli deploy config/projects/acme_corp/supply_chain.yaml --env prod
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
python -m usf_fabric_cli.scripts.admin.utilities.list_workspaces > workspaces.txt
grep "feature-inventory-opt" workspaces.txt
```

### Step 2: Bulk Destroy

Create a file with the workspaces to delete and run the bulk destroy script.

```bash
# Create a list file
echo "acme-supply-chain-feature-inventory-opt" > delete_list.txt

# Run bulk destroy
python -m usf_fabric_cli.scripts.admin.bulk_destroy delete_list.txt
```

**Result:** The feature workspace is removed, freeing up capacity.

---

## Scenario 5: Pipeline Promotion (Dev → Test → Prod)

**Goal:** Your Dev workspace has been tested and is ready for promotion through the Deployment Pipeline to Test, then to Production.

### Step 1: Promote from Development to Test

Use the `promote` command with the pipeline name. The pipeline is auto-created during onboarding (Scenario 6).

```bash
# Using Make
make promote pipeline="Acme Corp-Supply Chain Pipeline" source=Development target=Test

# Or using CLI directly
python -m usf_fabric_cli.cli promote \
  --pipeline-name "Acme Corp-Supply Chain Pipeline" \
  --source-stage Development \
  --target-stage Test \
  --note "Sprint 42 release"
```

**Result:**

- All artifacts from the Dev stage workspace are promoted to the Test workspace.
- The `--note` is recorded in the pipeline's deployment history.

### Step 2: Promote from Test to Production

After QA validation, promote to Production.

```bash
make promote pipeline="Acme Corp-Supply Chain Pipeline" source=Test target=Production
```

**Result:** Content is live in the Production workspace.

---

## Scenario 6: Full Onboarding (Single Command Bootstrap)

**Goal:** You want to bootstrap an entire environment — Dev workspace, Test workspace, Prod workspace, and a Deployment Pipeline — with a **single command** instead of doing Steps 1-3 of Scenario 1 manually.

### Step 1: Run Onboard

The `onboard` script automates the full 6-phase bootstrap process.

```bash
# Full bootstrap: Dev + Test + Prod + Pipeline
make onboard org="Acme Corp" project="Supply Chain" template=basic_etl

# Dry run (preview what would happen)
make onboard org="Acme Corp" project="Supply Chain" template=basic_etl dry_run=1

# Only Dev + Test (skip Prod)
make onboard org="Acme Corp" project="Supply Chain" template=basic_etl stages=dev,test
```

**Result:**

1. ✅ Configuration generated at `config/projects/acme_corp/supply_chain.yaml`
2. ✅ Dev workspace deployed (connected to Git `main` branch)
3. ✅ Test workspace created (empty — content arrives via pipeline promotion)
4. ✅ Prod workspace created (empty — content arrives via pipeline promotion)
5. ✅ Deployment Pipeline created and workspaces assigned to stages

### Isolated Git Repo Mode

For clients who need a dedicated repo:

```bash
make onboard-isolated org="Acme Corp" project="Supply Chain" template=basic_etl git_owner=acme-corp
```

This auto-creates a GitHub repo (`acme-corp/acme-corp-supply-chain`) before bootstrapping.

---

## Summary of Commands

| Task | Makefile Command | Direct CLI / Script |
|------|------------------|---------------------|
| **Scaffold** | `make generate org="Org" project="Proj" template=basic_etl` | `python -m usf_fabric_cli.scripts.dev.generate_project "Org" "Proj" --template basic_etl` |
| **Validate** | `make validate config=<config>` | `python -m usf_fabric_cli.cli validate <config>` |
| **Diagnose** | `make diagnose` | `python -m usf_fabric_cli.cli diagnose` |
| **Deploy (Dev)** | `make deploy config=<config> env=dev` | `python -m usf_fabric_cli.cli deploy <config> --env dev` |
| **Deploy (Feature)** | `make docker-feature-deploy config=<config> env=dev branch=<name>` | `python -m usf_fabric_cli.cli deploy <config> --env dev --branch <name> --force-branch-workspace` |
| **Deploy (Prod)** | `make deploy config=<config> env=prod` | `python -m usf_fabric_cli.cli deploy <config> --env prod` |
| **Promote** | `make promote pipeline="Name" source=Development target=Test` | `python -m usf_fabric_cli.cli promote --pipeline-name "Name" --source-stage Development` |
| **Destroy** | `make destroy config=<config>` | `python -m usf_fabric_cli.cli destroy <config> --force` |
| **Onboard (Full)** | `make onboard org="Org" project="Proj"` | `python -m usf_fabric_cli.scripts.dev.onboard --org "Org" --project "Proj"` |
| **Cleanup** | `make bulk-destroy file=<list_file>` | `python -m usf_fabric_cli.scripts.admin.bulk_destroy <list_file>` |
| **List Workspaces** | `make list-workspaces` | `python -m usf_fabric_cli.scripts.admin.utilities.list_workspaces` |
| **List Items** | `make list-items workspace="Name"` | `python -m usf_fabric_cli.scripts.admin.utilities.list_workspace_items --workspace "Name"` |
| **Init Repo** | `make init-github-repo git_owner="Owner" repo="Name"` | `python -m usf_fabric_cli.scripts.admin.utilities.init_github_repo --owner "Owner" --repo "Name"` |

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

# Full onboard using Docker
make docker-onboard org="Ricoh" project="Sales" ENVFILE=.env.ricoh

# List workspaces using Docker
make docker-list-workspaces ENVFILE=.env.ricoh

# List items in a workspace using Docker
make docker-list-items workspace="Ricoh-Sales-Dev" ENVFILE=.env.ricoh

# Interactive shell inside the container
make docker-shell ENVFILE=.env.ricoh
```
