# Fabric CI/CD — Full End-to-End Lifecycle Guide

> **Version**: 1.7.6 | **Last validated**: 15 February 2026
>
> **⚠️ NOTE**: This guide references `fabric_cicd_test_repo` as the consumer repository template.
> For the **current production-ready consumer repo** (`EDPFabric`) with multi-project support,
> two-tier access control, `selective_promote.py`, and `git_directory` isolation, see the
> [EDPFabric Replication Guide](https://github.com/<org>/edp_fabric_consumer_repo/blob/main/EDPFabric/docs/02_REPLICATION_GUIDE.md).
>
> This guide remains useful as a **CLI capability reference** for the feature branch lifecycle and
> Deployment Pipeline promotion commands.

This guide walks through the **complete lifecycle** of Microsoft Fabric workspace management — from initial environment setup (Dev/Test/Prod), through feature branch development in isolated workspaces, to automated promotion through a Fabric Deployment Pipeline.

---

## Table of Contents

### Phase 1 — Environment Setup (the START)
1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Prerequisites](#3-prerequisites)
4. [Repository Setup](#4-repository-setup)
5. [Configure GitHub Secrets](#5-configure-github-secrets)
6. [Create the Project Configs](#6-create-the-project-configs)
7. [Set Up GitHub Actions Workflows](#7-set-up-github-actions-workflows)
8. [Deploy Base Workspaces (Dev/Test/Prod)](#8-deploy-base-workspaces-devtestprod)

### Phase 2 — Feature Branch Development (the MIDDLE)
9. [End-to-End: Automated (CI/CD) Path](#9-end-to-end-automated-cicd-path)
10. [End-to-End: Manual (Local CLI) Path](#10-end-to-end-manual-local-cli-path)

### Phase 3 — Promotion to Production (the END)
11. [Automatic Promotion: Dev → Test](#11-automatic-promotion-dev--test)
12. [Manual Promotion: Test → Prod](#12-manual-promotion-test--prod)

### Support
13. [Monitoring & Verification](#13-monitoring--verification)
14. [Troubleshooting](#14-troubleshooting)
15. [Reference](#15-reference)

---

## 1. Overview

This guide covers the **Microsoft-recommended Option 3** pattern for Fabric CI/CD — the full lifecycle from environment setup through feature development to production deployment.

**Complete Lifecycle:**

```
 PHASE 1 — SETUP                PHASE 2 — DEVELOP                PHASE 3 — PROMOTE
 ───────────────                 ─────────────────                ─────────────────
 Deploy Dev workspace            Push feature/X                   PR merged to main
 Deploy Test workspace           → Feature workspace created      → Feature workspace destroyed
 Deploy Prod workspace           → Developer works in isolation   → Dev workspace Git-syncs main
 Create Deployment Pipeline      → PR created for review          → Auto-promote Dev → Test
 Connect workspaces to stages    → Code review & approval         → Manual promote Test → Prod
```

**Benefits:**
- **Isolation**: Each feature gets its own Fabric workspace — no conflicts
- **Automation**: Workspaces are created/destroyed automatically by GitHub Actions
- **Promotion**: Content flows Dev → Test → Prod via Fabric Deployment Pipeline
- **Safety**: Production promotion requires manual confirmation ("PROMOTE")
- **Efficiency**: Capacity is freed automatically when features complete

---

## 2. Architecture

```
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                    PHASE 1: INITIAL SETUP (run once)                     │
 │                                                                          │
 │  workflow_dispatch → setup-base-workspaces.yml                           │
 │    → fabric-cicd deploy base_workspace.yaml --env dev                    │
 │      → Creates: <prefix>-dev (Git-synced to main)                       │
 │      → Auto-creates Deployment Pipeline: <prefix>-pipeline              │
 │      → Auto-creates: <prefix>-test → assigns to Test stage              │
 │      → Auto-creates: <prefix>-prod → assigns to Prod stage              │
 │                                                                          │
 │  ✅ Fully automated — no manual Fabric portal steps required             │
 └──────────────────────────────────────────────────────────────────────────┘

 ┌──────────────────────────────────────────────────────────────────────────┐
 │              PHASE 2: FEATURE BRANCH WORKSPACE (per feature)             │
 │                                                                          │
 │  git push feature/X → feature-workspace-create.yml                       │
 │    → fabric-cicd deploy --branch feature/X --force-branch-workspace      │
 │      → Creates: <prefix>-feature-X (with folders, items, Git)           │
 │                                                                          │
 │  Developer works in isolated workspace (Fabric portal)                   │
 │                                                                          │
 │  PR merged / branch deleted → feature-workspace-cleanup.yml              │
 │    → fabric-cicd destroy --workspace-name-override <ws-name>             │
 │      → Destroys feature workspace, frees capacity                       │
 └──────────────────────────────────────────────────────────────────────────┘

 ┌──────────────────────────────────────────────────────────────────────────┐
 │               PHASE 3: PROMOTION PIPELINE (after merge)                  │
 │                                                                          │
 │  main updated → Fabric Git Sync → Dev workspace auto-syncs              │
 │                                                                          │
 │  push to main → promote-dev-to-test.yml (automatic)                      │
 │    → fabric-cicd promote --pipeline-name "..." -s Development -t Test    │
 │      → Dev content promoted to Test workspace                           │
 │                                                                          │
 │  workflow_dispatch → promote-test-to-prod.yml (manual + confirmation)    │
 │    → fabric-cicd promote --pipeline-name "..." -s Test -t Production     │
 │      → Test content promoted to Production workspace                    │
 └──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Prerequisites

### Azure / Fabric

| Requirement | Details |
|:---|:---|
| **Azure Entra ID Service Principal** | With `Client ID`, `Client Secret`, and `Tenant ID` |
| **Fabric Capacity** | An active capacity (e.g., F2 trial, F64 production) |
| **SP Workspace Permissions** | The Service Principal must be able to create workspaces on the capacity |
| **Fabric Deployment Pipeline** | Auto-created by the deployer during Phase 1 setup (no manual steps) |
| **Fabric Domain** (optional) | If your config specifies a domain, the SP needs domain assignment rights |

### GitHub

| Requirement | Details |
|:---|:---|
| **GitHub Repository** | A "consumer" repo that holds config + workflows (e.g., `fabric_cicd_test_repo`) |
| **Personal Access Token (PAT)** | Classic PAT with `repo` scope — used for Fabric ↔ GitHub Git integration |
| **GitHub Actions enabled** | Repository must have Actions enabled |

### Local Development (for manual path)

| Requirement | Details |
|:---|:---|
| **Python 3.11+** | Via conda or system Python |
| **Conda environment** | `conda activate fabric-cli-cicd` |
| **CLI installed** | `pip install -e .` in the `usf_fabric_cli_cicd` repo |
| **`.env` file** | With all required credentials (see [Section 5](#5-configure-github-secrets)) |

---

## 4. Repository Setup

### Option A: Fork the reference consumer repo

```bash
# Fork via GitHub UI first, then clone your fork
git clone https://github.com/<your-org>/<your-consumer-repo>.git
cd <your-consumer-repo>
```

> **Reference repo**: See the `fabric_cicd_test_repo` for a ready-to-use template
> with all workflows and configs pre-configured.

### Option B: Create a new consumer repo

```bash
# Create the repo (GitHub CLI)
gh repo create your-org/fabric-feature-demo --private --clone
cd fabric-feature-demo

# Create directory structure
mkdir -p config/projects/demo
mkdir -p .github/workflows
```

---

## 5. Configure GitHub Secrets

Navigate to **Settings → Secrets and variables → Actions** in your consumer repo and add:

| Secret Name | Value | Purpose |
|:---|:---|:---|
| `AZURE_TENANT_ID` | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` | Azure Entra ID tenant |
| `AZURE_CLIENT_ID` | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` | Service Principal application ID |
| `AZURE_CLIENT_SECRET` | `<secret-value>` | Service Principal credential |
| `FABRIC_CAPACITY_ID` | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` | Fabric capacity GUID |
| `FABRIC_GITHUB_TOKEN` | `ghp_xxxxxxxxxxxxx` | GitHub PAT with `repo` scope |
| `DEV_ADMIN_OBJECT_ID` | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` | Object ID of user/group for workspace admin |

> **Tip**: For the local CLI path, put these same values in a `.env` file in the CLI repo root. See `.env.template` for the format.

---

## 6. Create the Project Configs

Two YAML configs are needed — one for the **base Dev workspace** (connected to `main`) and one for the **feature workspaces** (created per-branch).

### 6a. Base Workspace Config (`base_workspace.yaml`)

This config defines the **main Dev workspace** — the source of truth connected to the `main` branch, plus the Deployment Pipeline configuration for promoting content Dev → Test → Prod.

**File**: `config/projects/demo/base_workspace.yaml`

```yaml
# ─────────────────────────────────────────────────────────────────
# Base Workspace Configuration — Dev (source of truth)
# ─────────────────────────────────────────────────────────────────

workspace:
  name: ${PROJECT_PREFIX}-dev
  display_name: ${PROJECT_PREFIX} - Development
  description: Main Dev workspace synced to main branch
  capacity_id: ${FABRIC_CAPACITY_ID}
  git_repo: ${GIT_REPO_URL}
  git_branch: main
  git_directory: /

environments:
  dev:
    workspace:
      name: ${PROJECT_PREFIX}-dev
      capacity_id: ${FABRIC_CAPACITY_ID}

folders:
  - "000 Orchestrate"
  - "100 Ingest"
  - "200 Store"
  - "300 Prepare"
  - "400 Model"
  - "500 Visualize"
  - "999 Libraries"
  - "Archive"

# Items managed via Git Sync — arrays intentionally empty
lakehouses: []
notebooks: []

principals:
  - id: ${DEV_ADMIN_OBJECT_ID}
    role: Admin
    description: Workspace admin for portal access

# ─────────────────────────────────────────────────────────────────
# Deployment Pipeline — Dev → Test → Prod promotion
# ─────────────────────────────────────────────────────────────────
deployment_pipeline:
  pipeline_name: ${PROJECT_PREFIX}-pipeline
  stages:
    development:
      workspace_name: ${PROJECT_PREFIX}-dev
      capacity_id: ${FABRIC_CAPACITY_ID}
    test:
      workspace_name: ${PROJECT_PREFIX}-test
      capacity_id: ${FABRIC_CAPACITY_ID}
    production:
      workspace_name: ${PROJECT_PREFIX}-prod
      capacity_id: ${FABRIC_CAPACITY_ID}
```

### 6b. Feature Workspace Config (`feature_workspace_demo.yaml`)

This config defines what each **feature branch workspace** looks like — isolated, temporary, and automatically suffixed with the branch name.

**File**: `config/projects/demo/feature_workspace_demo.yaml`

```yaml
# ─────────────────────────────────────────────────────────────────
# Feature Workspace Configuration
# ─────────────────────────────────────────────────────────────────

workspace:
  name: ${PROJECT_PREFIX}              # Base name (branch suffix appended automatically)
  display_name: ${PROJECT_PREFIX}
  description: Feature branch workspace for isolated development
  capacity_id: ${FABRIC_CAPACITY_ID}
  git_repo: ${GIT_REPO_URL}           # Set by GitHub Actions or .env
  git_branch: main
  git_directory: /

# Inline environment overrides (v1.7.6+)
environments:
  dev:
    workspace:
      name: ${PROJECT_PREFIX}
      capacity_id: ${FABRIC_CAPACITY_ID}

# Folder structure (numbered convention)
folders:
  - "000 Orchestrate"
  - "100 Ingest"
  - "200 Store"
  - "300 Prepare"
  - "400 Model"
  - "500 Visualize"
  - "999 Libraries"
  - "Archive"

# Items managed via Git Sync — arrays intentionally empty
lakehouses: []
notebooks: []

# Access control
principals:
  - id: ${DEV_ADMIN_OBJECT_ID}
    role: Admin
    description: Workspace admin for portal access
```

### Key points

- **`workspace.name`** is the **base name**. When `--force-branch-workspace` is used, the CLI appends the branch name as a suffix (e.g., `<prefix>-feature-my-feature`)
- **`${VAR_NAME}`** placeholders are resolved from environment variables or `.env`
- **`environments:`** block (v1.7.6+) allows inline per-environment overrides — these take priority over external files in `config/environments/`
- The deploying Service Principal automatically gets Admin access; you don't need to list it

---

## 7. Set Up GitHub Actions Workflows

Six workflows cover the full lifecycle. All live in `.github/workflows/`.

| # | Workflow File | Trigger | Purpose |
|:--|:---|:---|:---|
| 1 | `ci.yml` | Push/PR to `main` | Validate YAML syntax and check for hardcoded secrets |
| 2 | `setup-base-workspaces.yml` | `workflow_dispatch` | One-time: provision Dev workspace + Deployment Pipeline |
| 3 | `feature-workspace-create.yml` | Push to `feature/**` | Create feature workspace |
| 4 | `feature-workspace-cleanup.yml` | PR merge / `workflow_dispatch` | Destroy feature workspace |
| 5 | `promote-dev-to-test.yml` | Push to `main` | Auto-promote Dev → Test |
| 6 | `promote-test-to-prod.yml` | `workflow_dispatch` + confirm | Manual promote Test → Prod |

> **Note**: All workflows use **parameterised variables** with fallback defaults.
> Set `PROJECT_PREFIX`, `CLI_REPO_URL`, `CLI_REPO_REF`, and `FABRIC_CLI_VERSION`
> as **repository variables** (Settings → Variables) to customise for your project.
> See the [REPLICATION_GUIDE](../../../fabric_cicd_test_repo/docs/REPLICATION_GUIDE.md) for full setup instructions.

### 7a. Setup Workflow (`setup-base-workspaces.yml`)

Run once to provision the Dev workspace. The deployer **automatically** creates the Deployment Pipeline, Test, and Prod workspaces.

```yaml
name: Setup Base Workspaces

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to deploy'
        required: true
        default: 'dev'
        type: choice
        options: [dev]

jobs:
  setup-base-workspaces:
    runs-on: ubuntu-latest
    env:
      AZURE_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
      AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
      AZURE_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
      FABRIC_CAPACITY_ID: ${{ secrets.FABRIC_CAPACITY_ID }}
      GITHUB_TOKEN_FABRIC: ${{ secrets.FABRIC_GITHUB_TOKEN }}
      GITHUB_TOKEN: ${{ secrets.FABRIC_GITHUB_TOKEN }}
      GIT_REPO_URL: ${{ github.server_url }}/${{ github.repository }}
      DEV_ADMIN_OBJECT_ID: ${{ secrets.DEV_ADMIN_OBJECT_ID }}
      PROJECT_PREFIX: ${{ vars.PROJECT_PREFIX || 'fabric-cicd-demo' }}

    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: '3.11'

      - name: Install CLI
        run: |
          pip install --upgrade pip
          pip install ms-fabric-cli==${{ vars.FABRIC_CLI_VERSION || '1.3.1' }}
          pip install "git+https://${{ secrets.FABRIC_GITHUB_TOKEN }}@${{ vars.CLI_REPO_URL || 'github.com/your-org/your-cli-repo' }}.git@${{ vars.CLI_REPO_REF || 'v1.7.6' }}"

      - name: Verify credentials
        run: |
          for var in AZURE_TENANT_ID AZURE_CLIENT_ID AZURE_CLIENT_SECRET FABRIC_CAPACITY_ID GITHUB_TOKEN_FABRIC DEV_ADMIN_OBJECT_ID; do
            if [ -z "${!var}" ]; then
              echo "::error::Required secret $var is not configured"
              exit 1
            fi
          done

      - name: Deploy Dev workspace
        run: |
          fabric-cicd deploy config/projects/demo/base_workspace.yaml --env ${{ inputs.environment }}
```

### 7b. Create Workflow (`feature-workspace-create.yml`)

**File**: `.github/workflows/feature-workspace-create.yml`

```yaml
name: Create Feature Workspace

on:
  push:
    branches:
      - 'feature/**'

concurrency:
  group: feature-ws-${{ github.ref_name }}
  cancel-in-progress: false

jobs:
  create-feature-workspace:
    if: startsWith(github.ref, 'refs/heads/feature/')
    runs-on: ubuntu-latest

    env:
      AZURE_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
      AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
      AZURE_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
      GITHUB_TOKEN_FABRIC: ${{ secrets.FABRIC_GITHUB_TOKEN }}
      GITHUB_TOKEN: ${{ secrets.FABRIC_GITHUB_TOKEN }}
      FABRIC_CAPACITY_ID: ${{ secrets.FABRIC_CAPACITY_ID }}
      DEV_ADMIN_OBJECT_ID: ${{ secrets.DEV_ADMIN_OBJECT_ID }}
      GIT_REPO_URL: ${{ github.server_url }}/${{ github.repository }}
      PROJECT_PREFIX: ${{ vars.PROJECT_PREFIX || 'fabric-cicd-demo' }}

    steps:
      - uses: actions/checkout@v6
        with:
          ref: ${{ github.ref }}

      - uses: actions/setup-python@v6
        with:
          python-version: '3.11'

      - name: Install CLI tool
        run: |
          pip install --upgrade pip
          pip install ms-fabric-cli==${{ vars.FABRIC_CLI_VERSION || '1.3.1' }}
          pip install "git+https://${{ secrets.FABRIC_GITHUB_TOKEN }}@${{ vars.CLI_REPO_URL || 'github.com/your-org/your-cli-repo' }}.git@${{ vars.CLI_REPO_REF || 'v1.7.6' }}"

      - name: Extract branch info
        id: branch
        run: |
          BRANCH_NAME="${{ github.ref_name }}"
          FEATURE_NAME="${BRANCH_NAME#feature/}"
          WORKSPACE_SUFFIX=$(echo "$FEATURE_NAME" | sed 's/[^a-zA-Z0-9_-]/_/g')
          echo "branch_name=$BRANCH_NAME" >> $GITHUB_OUTPUT
          echo "feature_name=$FEATURE_NAME" >> $GITHUB_OUTPUT

      - name: Verify credentials
        run: |
          for var in AZURE_TENANT_ID AZURE_CLIENT_ID AZURE_CLIENT_SECRET FABRIC_CAPACITY_ID; do
            if [ -z "${!var}" ]; then
              echo "::error::Required secret $var is not configured"
              exit 1
            fi
          done

      - name: Deploy feature workspace
        env:
          CONFIG_OVERRIDE: ${{ vars.FEATURE_WORKSPACE_CONFIG || '' }}
        run: |
          if [ -n "$CONFIG_OVERRIDE" ]; then
            CONFIG_FILE="$CONFIG_OVERRIDE"
          else
            CONFIG_FILE=$(find config/projects -name "feature_*.yaml" -type f | head -1)
          fi

          fabric-cicd deploy \
            "$CONFIG_FILE" \
            --env dev \
            --branch "${{ steps.branch.outputs.branch_name }}" \
            --force-branch-workspace
```

### 7c. Cleanup Workflow (`feature-workspace-cleanup.yml`)

**File**: `.github/workflows/feature-workspace-cleanup.yml`

```yaml
name: Cleanup Feature Workspace

on:
  pull_request:
    types: [closed]
    branches: [main]
  workflow_dispatch:
    inputs:
      branch_name:
        description: 'Feature branch name (e.g., feature/my-feature)'
        required: true
        type: string

concurrency:
  group: cleanup-${{ github.event.pull_request.head.ref || inputs.branch_name || 'manual' }}
  cancel-in-progress: false

jobs:
  cleanup-feature-workspace:
    if: >
      (github.event_name == 'pull_request' && github.event.pull_request.merged == true &&
       startsWith(github.event.pull_request.head.ref, 'feature/')) ||
      github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest

    env:
      AZURE_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
      AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
      AZURE_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
      PROJECT_PREFIX: ${{ vars.PROJECT_PREFIX || 'fabric-cicd-demo' }}

    steps:
      - uses: actions/checkout@v6

      - uses: actions/setup-python@v6
        with:
          python-version: '3.11'

      - name: Install CLI tool
        run: |
          pip install --upgrade pip
          pip install ms-fabric-cli==${{ vars.FABRIC_CLI_VERSION || '1.3.1' }}
          pip install "git+https://${{ secrets.FABRIC_GITHUB_TOKEN }}@${{ vars.CLI_REPO_URL || 'github.com/your-org/your-cli-repo' }}.git@${{ vars.CLI_REPO_REF || 'v1.7.6' }}"

      - name: Extract branch info
        id: branch
        run: |
          if [ "${{ github.event_name }}" == "pull_request" ]; then
            BRANCH_NAME="${{ github.event.pull_request.head.ref }}"
          else
            BRANCH_NAME="${{ inputs.branch_name }}"
          fi
          echo "branch_name=$BRANCH_NAME" >> $GITHUB_OUTPUT

      - name: Destroy feature workspace
        env:
          CONFIG_OVERRIDE: ${{ vars.FEATURE_WORKSPACE_CONFIG || '' }}
        run: |
          if [ -n "$CONFIG_OVERRIDE" ]; then
            CONFIG_FILE="$CONFIG_OVERRIDE"
          else
            CONFIG_FILE=$(find config/projects -name "feature_*.yaml" -type f | head -1)
          fi

          BRANCH="${{ steps.branch.outputs.branch_name }}"
          WS_SUFFIX=$(echo "${BRANCH}" | tr '/' '-' | tr '_' '-' | tr '[:upper:]' '[:lower:]')
          BASE_NAME=$(python -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['workspace']['name'])")
          WS_NAME="${BASE_NAME}-${WS_SUFFIX}"

          echo "🧹 Destroying feature workspace: $WS_NAME"

          fabric-cicd destroy \
            "$CONFIG_FILE" \
            --force \
            --workspace-name-override "$WS_NAME"
```

### 7d. Dev → Test Promotion Workflow (`promote-dev-to-test.yml`)

Automatically triggers when code is merged to `main`. Waits for Fabric Git Sync, then promotes content from Development to Test stage via the Deployment Pipeline.

```yaml
name: Promote Dev → Test

on:
  push:
    branches: [main]
    paths-ignore:
      - '**.md'
      - '.github/CODEOWNERS'
      - '.github/dependabot.yml'
      - '.github/copilot-instructions.md'
      - '.github/PULL_REQUEST_TEMPLATE.md'
  workflow_dispatch:

concurrency:
  group: promote-dev-to-test
  cancel-in-progress: false

jobs:
  promote-dev-to-test:
    runs-on: ubuntu-latest
    env:
      AZURE_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
      AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
      AZURE_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
      PROJECT_PREFIX: ${{ vars.PROJECT_PREFIX || 'fabric-cicd-demo' }}

    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: '3.11'

      - name: Install CLI
        run: |
          pip install --upgrade pip
          pip install ms-fabric-cli==${{ vars.FABRIC_CLI_VERSION || '1.3.1' }}
          pip install "git+https://${{ secrets.FABRIC_GITHUB_TOKEN }}@${{ vars.CLI_REPO_URL || 'github.com/your-org/your-cli-repo' }}.git@${{ vars.CLI_REPO_REF || 'v1.7.6' }}"

      - name: Wait for Fabric Git Sync
        run: |
          echo "⏳ Waiting 60s for Fabric to sync main branch to Dev workspace..."
          for i in $(seq 1 6); do
            echo "  ⏱️  Waiting... (${i}0s / 60s)"
            sleep 10
          done

      - name: Promote Dev → Test
        run: |
          # Read pipeline name from config, resolving ${VAR} patterns
          PIPELINE_NAME=$(python -c "
          import os, re, yaml
          config = yaml.safe_load(open('config/projects/demo/base_workspace.yaml'))
          name = config.get('deployment_pipeline', {}).get('pipeline_name', '')
          name = re.sub(r'\\\$\{(\w+)\}', lambda m: os.environ.get(m.group(1), m.group(0)), name)
          print(name)
          ")

          echo "🚀 Promoting via pipeline: $PIPELINE_NAME"
          fabric-cicd promote \
            --pipeline-name "$PIPELINE_NAME" \
            --source-stage Development \
            --target-stage Test \
            --note "Auto-promoted from commit ${{ github.sha }}"
```

> **How the `re.sub` regex works**: The YAML config contains `${PROJECT_PREFIX}-pipeline`.
> The Python snippet reads this string and replaces `${VAR}` patterns with the
> corresponding environment variable values. Since `PROJECT_PREFIX` is set as an
> env var in the workflow, the pipeline name resolves correctly at runtime.

### 7e. Test → Prod Promotion Workflow (`promote-test-to-prod.yml`)

Manual trigger with a safety gate — the operator must type "PROMOTE" to confirm.

```yaml
name: Promote Test → Production

on:
  workflow_dispatch:
    inputs:
      confirm_promotion:
        description: 'Type PROMOTE to confirm production deployment'
        required: true
        type: string

jobs:
  safety-gate:
    runs-on: ubuntu-latest
    steps:
      - name: Validate confirmation
        if: inputs.confirm_promotion != 'PROMOTE'
        run: |
          echo "::error::Production promotion rejected. You must type PROMOTE to confirm."
          exit 1

  rejected:
    needs: safety-gate
    if: failure()
    runs-on: ubuntu-latest
    steps:
      - name: Rejection notice
        run: echo "❌ Production promotion was rejected — 'PROMOTE' not entered."

  promote:
    needs: safety-gate
    runs-on: ubuntu-latest
    env:
      AZURE_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
      AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
      AZURE_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
      PROJECT_PREFIX: ${{ vars.PROJECT_PREFIX || 'fabric-cicd-demo' }}

    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: '3.11'

      - name: Install CLI
        run: |
          pip install --upgrade pip
          pip install ms-fabric-cli==${{ vars.FABRIC_CLI_VERSION || '1.3.1' }}
          pip install "git+https://${{ secrets.FABRIC_GITHUB_TOKEN }}@${{ vars.CLI_REPO_URL || 'github.com/your-org/your-cli-repo' }}.git@${{ vars.CLI_REPO_REF || 'v1.7.6' }}"

      - name: Promote Test → Production
        env:
          DEPLOY_NOTE: "Production promotion by ${{ github.actor }} at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        run: |
          PIPELINE_NAME=$(python3 -c "
          import os, re, yaml
          cfg = yaml.safe_load(open('config/projects/demo/base_workspace.yaml'))
          name = cfg['deployment_pipeline']['pipeline_name']
          name = re.sub(r'\\\$\{(\w+)\}', lambda m: os.environ.get(m.group(1), m.group(0)), name)
          print(name)
          ")

          echo "🚀 Promoting $PIPELINE_NAME: Test → Production"
          fabric-cicd promote \
            --pipeline-name "$PIPELINE_NAME" \
            --source-stage Test \
            --target-stage Production \
            --note "$DEPLOY_NOTE"
```

> **Safety**: The `rejected` job provides a clear message when the safety gate fails.
> The promote job only runs if the safety gate succeeds (`needs: safety-gate`).

---

## 8. Deploy Base Workspaces (Dev/Test/Prod)

This is a **one-time setup** to create the permanent environment before any feature work begins.

The deployer **automatically** handles everything — no manual Fabric portal steps required.

### Step 1: Run the setup workflow

```
GitHub → Actions → Setup Base Workspaces → Run workflow
```

The workflow deploys `base_workspace.yaml` which triggers the following automated sequence:

1. **Dev workspace** created with folders, lakehouse, notebook, and Git connection to `main`
2. **Deployment Pipeline** `<prefix>-pipeline` auto-created (or reused if it exists)
3. **Test workspace** `<prefix>-test` auto-created with capacity assigned
4. **Prod workspace** `<prefix>-prod` auto-created with capacity assigned
5. **All workspaces assigned** to their respective pipeline stages (Development / Test / Production)

> **Timing**: The full setup completes in approximately **3 minutes** (validated E2E: 3m 6s).

### Step 2: Verify

After the workflow completes successfully, verify in the Fabric portal:

| Check | Expected |
|:---|:---|
| Dev workspace | Numbered folders (000–999), Git-synced to `main` |
| Deployment Pipeline | `<prefix>-pipeline` with 3 stages |
| Test workspace | Exists, assigned to Test stage (empty — awaiting first promotion) |
| Prod workspace | Exists, assigned to Production stage (empty — awaiting promotion) |
| SP admin access | Service Principal is Admin on all three workspaces |

> **Note**: Test and Prod workspaces start empty — content will be promoted from Dev via the pipeline.

---

## 9. End-to-End: Automated (CI/CD) Path

This is the primary path — GitHub Actions handles everything automatically.

### Step 1: Create a feature branch and push

```bash
cd fabric_cicd_test_repo

# Create a new feature branch
git checkout main
git pull origin main
git checkout -b feature/my-data-product

# Make a change (any file — the push triggers the workflow)
echo "# Feature: My Data Product" > FEATURE_NOTES.md
git add FEATURE_NOTES.md
git commit -m "feat: start my-data-product feature"

# Push to trigger workspace creation
git push origin feature/my-data-product
```

### Step 2: Monitor workspace creation

```bash
# Watch the workflow run
gh run list --limit 1
gh run watch <run-id>

# Or view in the browser
gh run view <run-id> --web
```

**Expected output**: The workflow runs for ~2 minutes (validated: 2m 14s) and creates:
- Workspace: `<prefix>-feature-my-data-product`
- Folders: 000 Orchestrate, 100 Ingest, 200 Store, etc.
- Items synced from Git
- Admin principals assigned
- Git connection to `feature/my-data-product` branch

### Step 3: Develop in the feature workspace

Open the workspace in the [Fabric portal](https://app.fabric.microsoft.com):
1. Navigate to your workspace (`<prefix>-feature-my-data-product`)
2. Edit notebooks, create pipelines, build semantic models
3. Changes are tracked in the Git-connected feature branch

### Step 4: Create a Pull Request

```bash
# Push any remaining changes
git add -A && git commit -m "feat: complete data product" && git push

# Create a PR
gh pr create \
  --title "feat: my-data-product" \
  --body "Adds the my-data-product feature workspace artifacts." \
  --base main
```

### Step 5: Merge and clean up

```bash
# Merge the PR (triggers cleanup workflow)
gh pr merge --squash --delete-branch
```

**Or** delete the branch directly:

```bash
git push origin --delete feature/my-data-product
```

### Step 6: Verify cleanup

```bash
# Watch the cleanup workflow
gh run list --limit 1
gh run watch <run-id>
```

**Expected**: Workspace `<prefix>-feature-my-data-product` is destroyed, capacity freed.

---

## 10. End-to-End: Manual (Local CLI) Path

Use this path for local testing or when you need to create/destroy workspaces without GitHub Actions.

### Step 1: Set up the CLI environment

```bash
# Navigate to the CLI repo
cd usf_fabric_cli_cicd

# Activate conda environment
conda activate fabric-cli-cicd

# Install in editable mode (if not already)
pip install -e .

# Verify the CLI works
fabric-cicd --help
```

### Step 2: Configure credentials

Create a `.env` file in the CLI repo root (copy from `.env.template`):

```bash
# .env
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=<your-secret>
FABRIC_CAPACITY_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
FABRIC_GITHUB_TOKEN=ghp_xxxxxxxxxxxxx
GIT_REPO_URL=https://github.com/your-org/your-consumer-repo
DEV_ADMIN_OBJECT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### Step 3: Deploy the feature workspace

```bash
# Deploy with branch workspace mode
fabric-cicd deploy \
  path/to/config/projects/demo/feature_workspace_demo.yaml \
  --env dev \
  --branch feature/my-feature \
  --force-branch-workspace
```

**Or via Make target:**

```bash
make deploy \
  config=path/to/feature_workspace_demo.yaml \
  env=dev \
  branch=feature/my-feature
```

### Step 4: Verify in Fabric portal

1. Open [app.fabric.microsoft.com](https://app.fabric.microsoft.com)
2. Search for workspace `<prefix>-feature-my-feature`
3. Confirm folders, lakehouse, notebook, and Git connection are present

### Step 5: Destroy the feature workspace

```bash
# Derive the workspace name (replace <prefix> with your PROJECT_PREFIX value)
WS_NAME="<prefix>-feature-my-feature"

# Destroy
fabric-cicd destroy \
  path/to/config/projects/demo/feature_workspace_demo.yaml \
  --force \
  --workspace-name-override "$WS_NAME"
```

---

## 11. Automatic Promotion: Dev → Test

After a feature branch is merged to `main` and the feature workspace is destroyed, the **real payoff** begins — the merged code is automatically promoted through the Deployment Pipeline.

### What happens automatically

1. **Git Sync**: Fabric detects `main` was updated → Dev workspace syncs the latest content
2. **GitHub Action**: `promote-dev-to-test.yml` triggers on push to `main`
3. **Promotion**: CLI calls `fabric-cicd promote --source-stage Development --target-stage Test`
4. **Result**: All content from Dev workspace is deployed to Test workspace

### Monitor the promotion

```bash
# Watch the promote workflow
gh run list --workflow promote-dev-to-test.yml --limit 1
gh run watch <run-id>
```

### Verify in Fabric portal

1. Open the **Deployment Pipeline** (`<prefix>-pipeline`)
2. Confirm the **Test** stage shows the promoted content
3. Verify items (lakehouses, notebooks) match the Dev workspace

### Manual fallback

If the workflow fails or you need to promote manually:

```bash
fabric-cicd promote \
  --pipeline-name "<prefix>-pipeline" \
  --source-stage Development \
  --target-stage Test \
  --note "Manual promotion"
```

---

## 12. Manual Promotion: Test → Prod

Production promotion is **intentionally manual** with a safety gate to prevent accidental deployments.

### Step 1: Verify Test environment

Before promoting to production, confirm the Test workspace is healthy:
1. Open the Test workspace in Fabric portal
2. Run data pipelines / notebooks to validate
3. Review the Deployment Pipeline stage comparison

### Step 2: Trigger the production promotion

```
GitHub → Actions → Promote Test → Production → Run workflow
```

**You must type `PROMOTE` in the confirmation field.** Any other value will be rejected.

### Step 3: Monitor

```bash
gh run list --workflow promote-test-to-prod.yml --limit 1
gh run watch <run-id>
```

### Step 4: Verify production

1. Open the **Production** workspace in Fabric portal
2. Confirm all content matches the Test workspace
3. Verify data connections and security settings

### Manual fallback (CLI)

```bash
fabric-cicd promote \
  --pipeline-name "<prefix>-pipeline" \
  --source-stage Test \
  --target-stage Production \
  --note "Production release by $(whoami)"
```

> **Warning**: Production promotion cannot be undone through the Deployment Pipeline. To revert, promote the previous content from Test again.

---

## 13. Monitoring & Verification

### GitHub Actions

```bash
# List recent workflow runs
gh run list --repo your-org/your-consumer-repo --limit 5

# View a specific run's logs
gh run view <run-id> --log

# View the workflow summary in browser
gh run view <run-id> --web
```

### Fabric Portal

1. **Workspaces list**: Check that the feature workspace appears (create) or disappears (cleanup)
2. **Workspace contents**: Verify folders, lakehouses, notebooks are provisioned
3. **Git connection**: In workspace settings → Git integration, confirm branch connection
4. **Admin access**: In workspace settings → Manage access, confirm principal assignments
5. **Deployment Pipeline**: Open the pipeline → verify stage assignments and promotion status

### Audit Logs (Local CLI)

```bash
# Check the most recent audit log
cat audit_logs/fabric_operations_$(date +%Y-%m-%d).jsonl | python -m json.tool | tail -50
```

---

## 14. Troubleshooting

### Workflow doesn't trigger

| Cause | Fix |
|:---|:---|
| Branch doesn't match `feature/**` | Ensure branch name starts with `feature/` (e.g., `feature/xyz`) |
| Actions disabled on repo | Enable in Settings → Actions → General |
| Workflow file not on default branch | Workflow YAMLs must exist on `main` for `create` events |

### Workspace creation fails

| Error | Cause | Fix |
|:---|:---|:---|
| `AADSTS7000215` | Expired or invalid Service Principal secret | Rotate the secret in Azure portal, update `AZURE_CLIENT_SECRET` secret |
| `Insufficient capacity` | F2 trial exhausted | Free capacity by destroying unused workspaces, or use a larger capacity |
| `Additional properties are not allowed ('environments')` | CLI version < 1.7.6 | Upgrade to v1.7.6+ (see [Troubleshooting §15](06_Troubleshooting.md#15-inline-environments-schema-validation-error)) |
| `Repository not found` | Wrong `FABRIC_GITHUB_TOKEN` or repo is private | Verify PAT has `repo` scope and can access the consumer repo |
| `WorkspaceAlreadyConnectedToGit` | Re-push to same branch | Safe to ignore — CLI handles this idempotently |

### Cleanup workflow doesn't trigger

| Cause | Fix |
|:---|:---|
| PR not merged (just closed) | The cleanup workflow only fires on `merged == true` or branch delete |
| Branch deleted before PR | Use `git push origin --delete feature/X` — the `delete` event triggers cleanup |
| Workspace already deleted | Safe — `fabric-cicd destroy` is idempotent |

### Common local CLI issues

```bash
# Check the CLI is installed correctly
which fabric-cicd

# Verify credentials are loaded
python -c "from usf_fabric_cli.utils.secrets import FabricSecrets; s=FabricSecrets(); print(f'Tenant: {s.tenant_id[:8]}...')"

# Run preflight diagnostics
python -m usf_fabric_cli.scripts.admin.preflight_check
```

### Promotion issues

| Error | Cause | Fix |
|:---|:---|:---|
| `Pipeline not found` | Pipeline name mismatch or pipeline not yet created | Re-run setup workflow, or verify `pipeline_name` in `base_workspace.yaml` |
| `No workspaces assigned to stage` | Setup workflow didn't complete fully | Re-run `setup-base-workspaces.yml` — it auto-creates and assigns all stages |
| `Promotion rejected` (Test→Prod) | Didn't type `PROMOTE` | Re-run the workflow and type `PROMOTE` exactly |
| `Content conflict` | Items modified directly in Test/Prod | Resolve in Fabric portal, then re-promote |
| `Insufficient permissions` | SP not admin on target workspace | Re-run setup workflow (auto-assigns SP as Admin), or add manually in portal |
| `403 Forbidden` on promote | `FABRIC_TOKEN` not generated | Upgrade to CLI v1.7.6+ which auto-generates tokens from SP credentials |

---

## 15. Reference

### CLI Command Reference

| Command | Purpose |
|:---|:---|
| `fabric-cicd deploy <config> --env dev` | Deploy base workspace |
| `fabric-cicd deploy <config> --env dev --branch feature/X --force-branch-workspace` | Create a feature workspace |
| `fabric-cicd destroy <config> --force --workspace-name-override <name>` | Destroy a specific workspace |
| `fabric-cicd promote --pipeline-name <name> -s Development -t Test` | Promote Dev → Test |
| `fabric-cicd promote --pipeline-name <name> -s Test -t Production` | Promote Test → Prod |
| `fabric-cicd validate <config>` | Validate config without deploying |
| `fabric-cicd deploy --help` | Show all deploy options |
| `fabric-cicd promote --help` | Show all promote options |

### Workspace Naming Convention

The feature workspace name is derived from:

```
<base-name>-<branch-suffix>
```

Where:
- `<base-name>` = `workspace.name` from the YAML config
- `<branch-suffix>` = branch name with `/` → `-`, `_` → `-`, lowercased

**Examples:**

| Branch | Base Name | Workspace Name |
|:---|:---|:---|
| `feature/my-data-product` | `<prefix>` | `<prefix>-feature-my-data-product` |
| `feature/JIRA-123` | `<prefix>` | `<prefix>-feature-jira-123` |
| `feature/add_kql_support` | `analytics-hub` | `analytics-hub-feature-add-kql-support` |

### Workflow Triggers

| Workflow | Event | Condition |
|:---|:---|:---|
| `setup-base-workspaces.yml` | `workflow_dispatch` | Manual — run once during initial setup |
| `feature-workspace-create.yml` | `push` to `feature/**` | Always |
| `feature-workspace-create.yml` | `create` (branch) | Branch starts with `feature/` |
| `feature-workspace-cleanup.yml` | `pull_request` closed | `merged == true` AND head branch is `feature/*` |
| `feature-workspace-cleanup.yml` | `delete` (branch) | Deleted branch starts with `feature/` |
| `promote-dev-to-test.yml` | `push` to `main` | Ignores `.md` file changes |
| `promote-test-to-prod.yml` | `workflow_dispatch` | Requires typing `PROMOTE` to confirm |

### Timing Expectations

| Operation | Typical Duration |
|:---|:---|
| Base workspace setup (Phase 1) | ~3 minutes (validated: 3m 6s) |
| Workspace creation (feature) | ~2 minutes (validated: 2m 14s) |
| Workspace destruction | ~30 seconds (validated: 27s) |
| CI install + setup | ~60 seconds |
| Fabric Git Sync (main) | 10–30 seconds |
| Dev → Test promotion | ~1 minute (validated: 1m 14s) |
| Test → Prod promotion | ~1 minute (validated: 48s) |

---

*Document created: 12 February 2026 | Updated: 15 February 2026 | CLI version: 1.7.6*

*E2E lifecycle validated: 15 February 2026 — all 3 phases passed (setup, feature branch, promotion).*

> **`<prefix>` notation**: Throughout this document, `<prefix>` refers to the value of the
> `PROJECT_PREFIX` repository variable (default: `fabric-cicd-demo`). Set this variable in
> GitHub → Settings → Secrets and variables → Actions → Variables.
