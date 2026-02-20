# Local Deployment Guide — From Zero to Deployed

> **Audience**: Developers, Platform Engineers | **Time**: 20–30 min | **Deployment Path**: Local Python
> **Difficulty**: Beginner–Intermediate | **Prerequisites**: See §1 below
> **See also**: [00_START_HERE.md](00_START_HERE.md) for orientation | [CLI Reference](CLI_REFERENCE.md) for all commands

This guide walks you through deploying a Microsoft Fabric workspace **from your local machine**
using the Fabric CLI CI/CD framework. By the end, you will have a fully provisioned Fabric
workspace with folders, security principals, and optional Git integration.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone & Set Up Environment](#2-clone--set-up-environment)
3. [Configure Credentials](#3-configure-credentials)
4. [Generate Project Configuration](#4-generate-project-configuration)
5. [Validate Configuration](#5-validate-configuration)
6. [Deploy](#6-deploy)
7. [Verify Your Deployment](#7-verify-your-deployment)
8. [Common Next Steps](#8-common-next-steps)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Prerequisites

Before starting, ensure you have:

| Requirement | How to Verify | How to Get It |
|-------------|--------------|---------------|
| **Python 3.11+** | `python3 --version` | [python.org/downloads](https://python.org/downloads) or `brew install python@3.11` |
| **conda (Miniconda)** | `conda --version` | [docs.conda.io/en/latest/miniconda.html](https://docs.conda.io/en/latest/miniconda.html) |
| **Git** | `git --version` | `apt install git` or `brew install git` |
| **Azure Service Principal** | `az ad sp show --id $AZURE_CLIENT_ID` | Azure Portal → Entra ID → App registrations → New |
| **Fabric Capacity** | Fabric Portal → Admin → Capacity | Request F2 trial or assign existing capacity |
| **SP has Fabric API access** | — | Fabric Admin Portal → Tenant settings → Enable "Service principals can use Fabric APIs" |

> **Note**: The Service Principal must be granted **Admin** role in the target Fabric workspace
> (the CLI does this automatically on first deploy).

---

## 2. Clone & Set Up Environment

```bash
# 1. Clone the CLI repository
git clone https://github.com/<org>/usf_fabric_cli_cicd.git
cd usf_fabric_cli_cicd

# 2. Create the conda environment (first time only)
conda env create -f environment.yml

# 3. Activate the environment (REQUIRED — do this every time)
conda activate fabric-cli-cicd

# 4. Verify you're in the right environment
conda env list
# Should show:  * fabric-cli-cicd  /path/to/envs/fabric-cli-cicd

# 5. Install the CLI in editable mode
pip install -e .

# 6. Verify the CLI is available
fabric-cicd --help
```

**Alternative (without conda):**
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

> **For consumers** (using the CLI as a dependency, not developing it):
> ```bash
> pip install git+https://github.com/<org>/usf_fabric_cli_cicd.git@v1.7.15
> ```

---

## 3. Configure Credentials

```bash
# Copy the template
cp .env.template .env

# Edit .env with your real values
nano .env   # or: code .env
```

Fill in **at minimum** these values in `.env`:

```dotenv
# === REQUIRED ===

# Service Principal (from Entra ID → App registrations)
AZURE_CLIENT_ID=<your-sp-app-id>
AZURE_CLIENT_SECRET=<your-sp-client-secret>
AZURE_TENANT_ID=<your-tenant-id>

# Fabric capacity (from Fabric Admin Portal → Capacity Settings)
FABRIC_CAPACITY_ID=<your-capacity-guid>

# Git integration (for Git-connected workspaces)
GITHUB_TOKEN=<your-fine-grained-pat>
GIT_REPO_URL=https://github.com/<org>/<repo>.git

# === GOVERNANCE (organisation-wide, injected into every workspace) ===
ADDITIONAL_ADMIN_PRINCIPAL_ID=<admin-security-group-oid>
ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID=<contributor-security-group-oid>

# === PROJECT-SPECIFIC ===
# Replace <PROJECT> with your project prefix (e.g. EDP, SALES)
# <PROJECT>_ADMIN_ID=<admin-oid>
# <PROJECT>_MEMBERS_ID=<member-oid1>,<member-oid2>
```

**Verify credentials load correctly:**
```bash
# Check .env is readable
grep -c "AZURE_CLIENT_ID" .env   # Should output: 1

# Run diagnostics
make diagnose
# Or: python -m usf_fabric_cli.scripts.admin.preflight_check
```

The diagnostics script checks: CLI version, credential validity, capacity access, and network connectivity.

---

## 4. Generate Project Configuration

You have three options:

### Option A: From a Blueprint Template (Recommended)

```bash
# See available templates
# (basic_etl, medallion, advanced_analytics, data_science, etc.)
# Full list: docs/01_User_Guides/07_Blueprint_Catalog.md

make generate org="Acme Corp" project="Sales Analytics" template=basic_etl
```

This creates: `config/projects/acme_corp/sales_analytics.yaml`

### Option B: One-Click Onboard (Generate + Deploy in One Step)

```bash
make onboard org="Acme Corp" project="Sales Analytics" template=basic_etl
```

This generates the config AND deploys immediately.

### Option C: Manual Configuration

Copy a blueprint template from the templates directory and edit:

```bash
mkdir -p config/projects/my_org
cp src/usf_fabric_cli/templates/blueprints/basic_etl.yaml \
   config/projects/my_org/my_project.yaml
nano config/projects/my_org/my_project.yaml
```

**Key fields to customise:**

```yaml
workspace:
  name: "my-project-dev"                # DNS-safe workspace name in Fabric
  display_name: "My Project (Dev)"      # Human-readable display name
  capacity_id: "${FABRIC_CAPACITY_ID}"  # Resolved from .env
  description: "My project workspace"

folders:                                  # Numbered folder convention
  - "000 Orchestrate"
  - "100 Ingest"
  - "200 Store"
  - "300 Prepare"
  - "400 Model"
  - "500 Visualize"
  - "999 Libraries"
  - "Archive"

principals:                               # Who gets access
  - id: "${MY_PROJECT_ADMIN_ID}"
    role: "Admin"
    description: "Project admin group"
```

For full YAML syntax, see [Project Configuration Guide](03_Project_Configuration.md).

---

## 5. Validate Configuration

Always validate before deploying:

```bash
make validate config=config/projects/acme_corp/sales_analytics.yaml

# Or directly:
fabric-cicd validate config/projects/acme_corp/sales_analytics.yaml
```

**Expected output (success):**
```
✅ Configuration is valid: config/projects/acme_corp/sales_analytics.yaml
   Workspace: acme-sales-analytics
   Folders: 8 defined
   Principals: 4 entries
   Folder Rules: 9 rules
   Deployment Pipeline: Acme Sales Pipeline (3 stages)
```

**Expected output (failure):**
```
❌ Validation failed:
   - Line 12: capacity_id references ${FABRIC_CAPACITY_ID} but this env var is not set
   - Line 45: principal role must be one of: Admin, Member, Contributor, Viewer
```

---

## 6. Deploy

```bash
# Deploy to dev environment
make deploy config=config/projects/acme_corp/sales_analytics.yaml env=dev

# Or directly via CLI:
fabric-cicd deploy config/projects/acme_corp/sales_analytics.yaml --env dev
```

**What happens during deployment:**

1. CLI reads the YAML config and resolves `${VAR}` placeholders from `.env`
2. Creates the workspace on the specified Fabric capacity
3. Creates the folder structure (`000 Orchestrate`, `100 Ingest`, etc.)
4. Assigns security principals (Admin, Member, Contributor, Viewer)
5. Connects to Git repository (if configured) — Fabric Git Sync then pulls items into the workspace
6. Creates Deployment Pipeline and assigns stage workspaces (if configured)
7. *(Optional)* Creates lakehouses, notebooks, and other resources **only if** the config arrays are populated (empty in Git-sync-only blueprints)

> **Git-sync-only workflow**: With current blueprints, the CLI provisions the workspace envelope
> (steps 1–6). Fabric items are managed through Git — after Git Sync places items at the workspace
> root, run `fabric-cicd organize-folders` to move them into the correct folders using `folder_rules`.

**Expected output (success):**
```
[INFO] Loading configuration: config/projects/acme_corp/sales_analytics.yaml
[INFO] Environment: dev
[INFO] Creating workspace: acme-sales-analytics-dev
[INFO]   ✅ Workspace created (ID: abc-123-def)
[INFO] Creating folders: 8 folders
[INFO]   ✅ Folders created
[INFO] Assigning principals: 4 entries
[INFO]   ✅ Principals assigned
[INFO] Connecting Git repository
[INFO]   ✅ Git connected (branch: main)
[INFO] Creating Deployment Pipeline: Acme Sales Pipeline
[INFO]   ✅ Pipeline created with 3 stages
[INFO] ──────────────────────────────────────
[INFO] ✅ Deployment complete: acme-sales-analytics-dev
```

**With rollback protection (recommended for new deployments):**
```bash
fabric-cicd deploy config/projects/acme_corp/sales_analytics.yaml --env dev --rollback-on-failure
```

If any step fails, previously created items are automatically cleaned up.

---

## 7. Verify Your Deployment

After a successful deployment, verify in the Fabric portal:

### Verification Checklist

| # | Check | Where to Look | Expected Result |
|---|-------|---------------|-----------------|
| 1 | Workspace exists | [Fabric Portal](https://app.fabric.microsoft.com) → Workspaces | Workspace named `acme-sales-analytics-dev` appears |
| 2 | Correct capacity | Workspace → Settings → License info | Shows the capacity you configured |
| 3 | Folders created | Workspace → Browse files | Numbered folders visible (`000 Orchestrate`, `100 Ingest`, etc.) |
| 4 | Principals assigned | Workspace → Manage access | Your SP + security groups listed with correct roles |
| 5 | Git connected | Workspace → Source control | Shows connected repo, branch, and directory (if configured) |
| 6 | Pipeline exists | Deployment Pipelines (left nav) | Pipeline with Dev/Test/Prod stages (if configured) |
| 7 | Items synced | Workspace → item list | Fabric items appear after Git Sync completes (Git-sync-only) |

### Quick CLI Verification

```bash
# List items in the deployed workspace
fabric-cicd list-items "acme-sales-analytics-dev"

# Or via admin utility:
python -m usf_fabric_cli.scripts.admin.utilities.list_workspace_items "acme-sales-analytics-dev"

# Organize items into folders (after Git Sync places items at root)
fabric-cicd organize-folders config/projects/acme_corp/sales_analytics.yaml --env dev --dry-run
```

---

## 8. Common Next Steps

### Deploy to Another Environment

```bash
# Deploy to test (uses config/environments/test.yaml overrides)
make deploy config=config/projects/acme_corp/sales_analytics.yaml env=test

# Deploy to prod
make deploy config=config/projects/acme_corp/sales_analytics.yaml env=prod
```

### Destroy a Workspace

```bash
# Destroy (with safety protection — won't delete if workspace has items)
fabric-cicd destroy config/projects/acme_corp/sales_analytics.yaml --env dev --safe

# Force destroy (deletes even if populated)
fabric-cicd destroy config/projects/acme_corp/sales_analytics.yaml --env dev
```

### Promote Through Deployment Pipeline

```bash
# Promote Dev → Test
make promote pipeline="Acme Sales Pipeline" source=Development target=Test

# Or via CLI:
fabric-cicd promote --pipeline-name "Acme Sales Pipeline" --source-stage Development --target-stage Test
```

### Create a Feature Branch Workspace

```bash
make deploy config=config/projects/acme_corp/sales_analytics.yaml env=dev branch=feature/new-report
```

### Move to CI/CD

When you're ready to automate, set up a consumer repo with GitHub Actions:
→ [EDPFabric Replication Guide](https://github.com/<org>/edp_fabric_consumer_repo/blob/main/EDPFabric/docs/02_REPLICATION_GUIDE.md)

---

## 9. Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `conda: command not found` | Miniconda not in PATH | Add to `.bashrc`: `export PATH="$HOME/miniconda3/bin:$PATH"` |
| `fabric-cicd: command not found` | CLI not installed in current env | Run `pip install -e .` in the CLI repo with conda env active |
| `Environment variable not set: FABRIC_CAPACITY_ID` | `.env` not loaded or var missing | Check `.env` file exists and contains the variable |
| `403 Forbidden` during workspace creation | SP lacks permissions | Enable "Service principals can use Fabric APIs" in Fabric Admin |
| `Capacity not found` | Wrong capacity GUID or SP lacks access | Verify GUID in Fabric Admin Portal; ensure SP has access to the capacity |
| `Workspace already exists` | Idempotent — not an error | CLI skips creation if workspace exists; items are updated in place |
| `Git connection failed` | PAT expired or lacks permissions | Regenerate PAT with `repo` scope; verify repo URL in config |
| `make: *** No rule to make target` | Wrong Make target name | Run `make help` to see all available targets |

For more issues, see the full [Troubleshooting Guide](06_Troubleshooting.md).
