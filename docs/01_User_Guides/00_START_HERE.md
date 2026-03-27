# START HERE — Fabric CLI CI/CD Documentation Guide

> **Version**: 1.9.1 · **Last Updated**: 27 March 2026
>
> This is the **starting point** for all documentation. Read this page first to understand
> the system architecture, choose your deployment path, and find the right guide for your role.

---

## 1. What Is This System?

The **Fabric CLI CI/CD Framework** automates Microsoft Fabric workspace management — provisioning
workspaces, folders, security principals, Git connections, Deployment Pipelines, and folder
organization — from declarative YAML configuration files.

```
You write YAML  →  The CLI provisions the workspace envelope  →  Git Sync pulls in Fabric items
```

> **Current Standard — Git-Sync-Only**: The CLI manages the workspace envelope (workspace,
> folders, principals, Git connection, deployment pipeline). Fabric items (lakehouses, notebooks,
> pipelines) are committed to Git and synced into the workspace by Fabric Git Sync. After sync,
> `fabric-cicd organize-folders` moves items from the workspace root into configured folders.

### Two-Repository Architecture

The system uses **two repositories** that work together:

| Repository | Purpose | You Need It When |
|-----------|---------|-----------------|
| **CLI Library** (`usf_fabric_cli_cicd`) | The tool itself — CLI commands, deployment engine, config parser, Docker image | Always — this is the engine |
| **Consumer Repo** (e.g. `EDPFabric`) | Your project configs, GitHub Actions workflows, promotion scripts | Using GitHub Actions CI/CD |

```
┌─────────────────────────────┐     ┌──────────────────────────────┐
│  CLI Library Repo            │     │  Consumer Repo (YOUR project) │
│                              │     │                               │
│  • fabric-cicd CLI           │◄────│  • config/projects/*.yaml     │
│  • Deployment engine         │     │  • .github/workflows/*.yml    │
│  • Blueprint templates       │     │  • Makefile (make targets)    │
│  • Docker image              │     │  • Project-specific secrets   │
└─────────────────────────────┘     └──────────────────────────────┘
        ▲ installed at runtime via: pip install git+https://...@v1.9.1
```

**Key insight**: The CLI repo is a *shared product*. The consumer repo is *your project's configuration*.
You don't need to modify the CLI repo to deploy your workspaces.

---

## 2. Who Are You? (Start Here)

Find your role below and follow the recommended reading path:

### 🟢 "I'm setting up CI/CD for a new Fabric project"

You need the consumer repo setup — automated GitHub Actions workflows for the full lifecycle.

1. Read this page (you're here)
2. → [EDPFabric Replication Guide](https://github.com/<org>/edp_fabric_consumer_repo/blob/main/EDPFabric/docs/02_REPLICATION_GUIDE.md) — complete end-to-end CI/CD setup (45–90 min)
3. → [Blueprint Catalog](07_Blueprint_Catalog.md) — choose a template for your project
4. → [Troubleshooting](06_Troubleshooting.md) — if anything goes wrong

### 🔵 "I'm deploying locally during development / testing"

You'll run the CLI directly on your machine — no GitHub Actions needed.

1. Read this page (you're here)
2. → [Local Deployment Guide](LOCAL_DEPLOYMENT_GUIDE.md) — from zero to deployed, step by step
3. → [Project Configuration](03_Project_Configuration.md) — customise your YAML config
4. → [CLI Reference](02_CLI_Walkthrough.md) — all commands and flags

### 🟡 "I'm building Docker images for CI pipelines"

You'll use the Docker image to run deployments in any CI/CD system.

1. Read this page (you're here)
2. → [Docker Deployment Guide](04_Docker_Deployment.md) — build, configure, deploy via Docker
3. → [CLI Reference](02_CLI_Walkthrough.md) — command details

### 🟣 "I'm exploring what this tool can do"

You want a conceptual overview before diving in.

1. Read this page (you're here)
2. → [Educational Guide](08_Educational_Guide.md) — "Three Ways to Work", architecture, concepts
3. → [Client Tutorial](05_Client_Tutorial.md) — high-level framework overview
4. → [Blueprint Catalog](07_Blueprint_Catalog.md) — see the 11 available templates

### 🔴 "I need to troubleshoot a failed deployment"

1. → [Troubleshooting Guide](06_Troubleshooting.md) — 11+ common issues with solutions
2. → [Consumer Replication Guide §11](https://github.com/<org>/edp_fabric_consumer_repo/blob/main/EDPFabric/docs/02_REPLICATION_GUIDE.md#11-troubleshooting) — CI/CD-specific issues

---

## 3. Which Deployment Path?

Choose your path based on your needs:

| Path | Best For | Setup Time | Requires |
|------|----------|------------|----------|
| **Local Python** | Development, testing, one-off deploys, learning | 15 min | Python 3.11, conda |
| **Docker** | Reproducible builds, air-gapped environments, non-Python CI | 20 min | Docker |
| **GitHub Actions** | Production CI/CD, team collaboration, automated lifecycle | 45–90 min | GitHub repo, Azure SP, Fabric capacity |

### Decision Guide

```
Do you need automated CI/CD for your team?
├── YES → GitHub Actions path
│         Will you have multiple projects in one repo?
│         ├── YES → Multi-project (Option B) — see Workflow Options doc
│         └── NO  → Single-project (Option A) — default
└── NO  → Are you running in an environment without Python/conda?
          ├── YES → Docker path
          └── NO  → Local Python path (simplest)
```

---

## 4. Prerequisites (Master Checklist)

Regardless of deployment path, you need these:

### Always Required

| Prerequisite | How to Get It | Verify With |
|-------------|---------------|-------------|
| **Azure Service Principal** | Azure Portal → Entra ID → App registrations → New registration + client secret | `az ad sp show --id $AZURE_CLIENT_ID` |
| **Fabric Capacity** | Fabric Admin Portal → Capacities → Assign or claim F2 trial | Fabric Portal → Admin → Capacity settings |
| **SP as Fabric Admin** | Fabric Admin Portal → Tenant settings → Service principals can use Fabric APIs → Enable | Deploy a test workspace |

### By Deployment Path

| Prerequisite | Local Python | Docker | GitHub Actions |
|-------------|:---:|:---:|:---:|
| Python 3.11+ | ✅ | — | — |
| conda (Miniconda/Anaconda) | ✅ | — | — |
| Docker Desktop/Engine | — | ✅ | — |
| GitHub account | — | — | ✅ |
| GitHub PAT (Fine-grained) | — | — | ✅ |
| Consumer repo (fork/copy) | — | — | ✅ |

### Required Environment Variables

Create a `.env` file in the CLI repo root (for local/Docker) or configure as GitHub Secrets (for CI/CD):

```dotenv
# Service Principal credentials (REQUIRED)
AZURE_CLIENT_ID=<your-sp-app-id>
AZURE_CLIENT_SECRET=<your-sp-secret>
AZURE_TENANT_ID=<your-tenant-id>

# Fabric capacity (REQUIRED)
FABRIC_CAPACITY_ID=<your-capacity-guid>

# Git integration (REQUIRED for Git-connected workspaces)
GITHUB_TOKEN=<your-fine-grained-pat>    # GitHub
# OR: AZURE_DEVOPS_PAT=<your-pat>      # Azure DevOps
```

---

## 5. Complete Guide Index

### Getting Started
| Guide | Description |
|-------|-------------|
| **[00_START_HERE.md](00_START_HERE.md)** | You are here — orientation, routing, decision matrix |
| **[LOCAL_DEPLOYMENT_GUIDE.md](LOCAL_DEPLOYMENT_GUIDE.md)** | End-to-end local Python deployment |

### Deployment Paths
| Guide | Description |
|-------|-------------|
| **[04_Docker_Deployment.md](04_Docker_Deployment.md)** | Docker build + deploy |
| **[EDPFabric Replication Guide](https://github.com/<org>/edp_fabric_consumer_repo/blob/main/EDPFabric/docs/02_REPLICATION_GUIDE.md)** | GitHub Actions CI/CD (canonical guide) |

### Configuration & Templates
| Guide | Description |
|-------|-------------|
| **[03_Project_Configuration.md](03_Project_Configuration.md)** | YAML config syntax and structure |
| **[07_Blueprint_Catalog.md](07_Blueprint_Catalog.md)** | 11 project templates with selection guidance |

### Reference
| Guide | Description |
|-------|-------------|
| **[02_CLI_Walkthrough.md](02_CLI_Walkthrough.md)** | All commands, flags, exit codes, env vars |
| **[01_Usage_Guide.md](01_Usage_Guide.md)** | Make targets reference and scenarios |
| **[06_Troubleshooting.md](06_Troubleshooting.md)** | Common issues and solutions |

### Deep Dives
| Guide | Description |
|-------|-------------|
| **[02_CLI_Walkthrough.md](02_CLI_Walkthrough.md)** | 6 narrative CLI scenarios |
| **[05_Client_Tutorial.md](05_Client_Tutorial.md)** | Client-facing framework overview |
| **[08_Educational_Guide.md](08_Educational_Guide.md)** | Conceptual guide — "Three Ways to Work" |

### Historical / Archive
| Guide | Description |
|-------|-------------|
| [09_From_Local_to_CICD.md](09_From_Local_to_CICD.md) | Retrospective: v1.5→v1.7 migration (historical) |
| [10_Feature_Branch_Workspace_Guide.md](10_Feature_Branch_Workspace_Guide.md) | Feature lifecycle using `fabric_cicd_test_repo` (superseded by Replication Guide) |
| [11_Stabilisation_Changelog_Feb2026.md](11_Stabilisation_Changelog_Feb2026.md) | Changelog for v1.7.0→v1.7.7 stabilisation (historical) |

---

## 6. Quick Command Cheat Sheet

```bash
# --- LOCAL PYTHON ---
conda activate fabric-cli-cicd
fabric-cicd deploy config/projects/org/project.yaml --env dev
fabric-cicd destroy config/projects/org/project.yaml --env dev
fabric-cicd validate config/projects/org/project.yaml

# --- DOCKER ---
make docker-build
make docker-deploy config=config/projects/org/project.yaml env=dev ENVFILE=.env

# --- MAKE TARGETS (local) ---
make deploy config=config/projects/org/project.yaml env=dev
make validate config=config/projects/org/project.yaml
make onboard org="Acme Corp" project="Analytics" template=basic_etl

# --- GENERATE CONFIG ---
make generate org="Acme" project="Sales" template=basic_etl
# Or: python -m usf_fabric_cli.scripts.dev.generate_project "Acme" "Sales" --template basic_etl
```

For the full command reference, see [02_CLI_Walkthrough.md](02_CLI_Walkthrough.md).
