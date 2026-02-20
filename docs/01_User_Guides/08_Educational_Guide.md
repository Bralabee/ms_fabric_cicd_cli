# The Complete Guide to Fabric CLI CI/CD

> **Audience**: Platform Engineers, Data Engineers, DevOps, Team Leads | **Time**: 45–60 min | **Deployment Path**: Conceptual (all paths)
> **Difficulty**: Beginner | **Prerequisites**: None — conceptual overview
> **See also**: [00_START_HERE.md](00_START_HERE.md) for hands-on orientation | [Local Deployment Guide](LOCAL_DEPLOYMENT_GUIDE.md) for first deploy | [CLI Reference](CLI_REFERENCE.md) for commands

---

## 1. What Is This Project?

The **Fabric CLI CI/CD Framework** is an enterprise-grade deployment automation tool for Microsoft Fabric. It translates declarative YAML configuration files into fully provisioned Fabric workspaces — including Lakehouses, Warehouses, Pipelines, folders, security principals, Git connections, and Deployment Pipelines — using a **thin wrapper** around the official Microsoft Fabric CLI.

### The Core Idea

```
 You write YAML  →  The framework provisions Fabric  →  Your team works in a governed workspace
```

Instead of clicking through the Fabric Portal to create workspaces, add items, assign permissions, and connect Git — you describe the desired state in a configuration file and the framework makes it real.

### Design Principles

| Principle | What It Means |
|:---|:---|
| **Infrastructure as Code** | Every Fabric workspace is defined in a version-controlled YAML file |
| **Idempotent Operations** | Running `deploy` twice produces the same result — existing items are updated, not duplicated |
| **Atomic Rollback** | If deployment fails mid-way, all created items are cleaned up automatically (LIFO order) |
| **Environment Parity** | The same config deploys to Dev, Test, and Prod with environment-specific overrides |
| **Multi-Tenant** | Switch between organisations using different `.env` files (`ENVFILE=.env.ricoh`) |

### Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                     Entry Points                         │
│  make targets  │  python -m usf_fabric_cli.cli  │ Docker │
└──────────┬───────────────────┬───────────────────┬───────┘
           │                   │                   │
           ▼                   ▼                   ▼
┌────────────────────────────────────────────────────────────┐
│                    CLI Layer (cli.py)                       │
│  deploy │ validate │ destroy │ promote │ onboard │ generate │
│  list-workspaces │ list-items │ bulk-destroy │ init-github  │
└──────────────────────────┬─────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────┐
│                   Service Layer                             │
│  deployer.py        │  Orchestrates workspace deployment    │
│  fabric_wrapper.py  │  Wraps Fabric CLI (fab) commands      │
│  fabric_git_api.py  │  REST API client for Git integration  │
│  token_manager.py   │  Azure AD token refresh               │
│  config.py          │  YAML + environment overlay merging   │
│  deployment_pipeline│  Pipeline stage promotion (REST API)  │
└──────────────────────────┬─────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────┐
│           Microsoft Fabric REST API + Fabric CLI            │
└────────────────────────────────────────────────────────────┘
```

---

## 2. Three Ways to Work

There are **three distinct ways** to operate this framework. Each is a complete, self-sufficient workflow — choose the one that fits your role and context.

---

### Way 1: Local Python (Developer Workflow)

> **Best for**: Platform engineers with the conda environment installed locally.

#### Prerequisites

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd usf_fabric_cli_cicd

# 2. Create and activate the conda environment
conda env create -f environment.yml
source ~/miniconda3/etc/profile.d/conda.sh && conda activate fabric-cli-cicd

# 3. Install dependencies
make install

# 4. Configure credentials
cp .env.template .env
# Edit .env with your Service Principal details (see Section 4)

# 5. Verify everything works
make diagnose
```

**Expected output from `make diagnose`:**

```
✅ Fabric CLI detected at /home/user/miniconda3/envs/fabric-cli-cicd/bin/fab
   Version: fab version 1.3.1
✅ Required environment variables detected
```

#### End-to-End Walkthrough (Local)

```bash
# ── Step 1: Generate a project configuration ──────────────────────
make generate org="Acme Corp" project="Sales Analytics" template=medallion

# Output:
# ✅ Generated configuration: config/projects/acme_corp/sales_analytics.yaml
# 📝 Next steps:
#    1. Review and edit config/projects/acme_corp/sales_analytics.yaml
#    2. Validate: make validate config=config/projects/acme_corp/sales_analytics.yaml
#    3. Deploy: make deploy config=config/projects/acme_corp/sales_analytics.yaml env=dev

# ── Step 2: Review the generated YAML ─────────────────────────────
cat config/projects/acme_corp/sales_analytics.yaml

# ── Step 3: Validate the configuration ────────────────────────────
make validate config=config/projects/acme_corp/sales_analytics.yaml

# ── Step 4: Deploy to Development ─────────────────────────────────
make deploy config=config/projects/acme_corp/sales_analytics.yaml env=dev

# ── Step 5: Verify in Fabric Portal ───────────────────────────────
make list-workspaces
make list-items workspace="acme-corp-sales-analytics"

# ── Step 6: Promote Dev → Test ────────────────────────────────────
make promote pipeline="Acme Corp-Sales Analytics Pipeline" source=Development target=Test

# ── Step 7: Cleanup when done ─────────────────────────────────────
make destroy config=config/projects/acme_corp/sales_analytics.yaml
```

#### Feature Branch Isolation

```bash
# Create and deploy to an isolated workspace
git checkout -b feature/inventory-opt
make deploy config=config/projects/acme_corp/sales_analytics.yaml env=dev \
  branch=feature/inventory-opt

# Or use the onboard shortcut:
make feature-workspace org="Acme Corp" project="Sales Analytics"

# When done, destroy the feature workspace
make destroy config=config/projects/acme_corp/sales_analytics.yaml
```

---

### Way 2: Docker (Multi-Tenant / Contributor Workflow)

> **Best for**: Contributors without conda, CI runners, or multi-tenant operations across different clients.

#### Prerequisites

```bash
# Only Docker is required — no Python, no conda
docker --version   # Ensure Docker is installed

# Build the image (once)
make docker-build
```

#### End-to-End Walkthrough (Docker)

```bash
# ── Step 1: Generate configuration ────────────────────────────────
make docker-generate org="Ricoh" project="Sales" template=basic_etl ENVFILE=.env.ricoh

# ── Step 2: Validate ──────────────────────────────────────────────
make docker-validate config=config/projects/ricoh/sales.yaml ENVFILE=.env.ricoh

# ── Step 3: Deploy ────────────────────────────────────────────────
make docker-deploy config=config/projects/ricoh/sales.yaml env=dev ENVFILE=.env.ricoh

# ── Step 4: Verify ────────────────────────────────────────────────
make docker-list-workspaces ENVFILE=.env.ricoh
make docker-list-items workspace="ricoh-sales" ENVFILE=.env.ricoh

# ── Step 5: Promote ──────────────────────────────────────────────
make docker-promote pipeline="Ricoh-Sales Pipeline" source=Development target=Test ENVFILE=.env.ricoh

# ── Step 6: Feature branch deploy ─────────────────────────────────
make docker-feature-deploy \
  config=config/projects/ricoh/sales.yaml \
  env=dev \
  branch=feature/new-analytics \
  ENVFILE=.env.ricoh

# ── Step 7: Clean up ─────────────────────────────────────────────
make docker-destroy config=config/projects/ricoh/sales.yaml ENVFILE=.env.ricoh

# ── Interactive troubleshooting ───────────────────────────────────
make docker-shell ENVFILE=.env.ricoh
# You are now inside the container with all tools ready
```

#### Multi-Tenant Pattern

The Docker workflow enables switching between organisations via `ENVFILE`:

```bash
# Client A — uses .env (default)
make docker-deploy config=config/projects/clientA/project.yaml env=dev

# Client B — uses .env.ricoh
make docker-deploy config=config/projects/clientB/project.yaml env=dev ENVFILE=.env.ricoh

# Client C — uses .env.jtoye
make docker-deploy config=config/projects/clientC/project.yaml env=dev ENVFILE=.env.jtoye
```

Each `.env` file contains tenant-specific Service Principal credentials, capacity IDs, and principal mappings.

---

### Way 3: CI/CD (GitHub Actions — Automated Workflow)

> **Best for**: Teams that want fully automated promotion and feature workspace lifecycle.

#### Overview

Four GitHub Actions workflows provide end-to-end automation:

| Workflow | File | Trigger | What It Does |
|:---|:---|:---|:---|
| **CI Pipeline** | `fabric-cicd.yml` | Push to any branch | Lint, type-check, test, security scan |
| **Feature Workspace** | `feature-workspace-create.yml` | Push to `feature/*` | Creates an isolated Fabric workspace for the branch |
| **Feature Cleanup** | `feature-workspace-cleanup.yml` | PR merge / branch delete | Destroys the feature workspace |
| **Deploy to Fabric** | `deploy-to-fabric.yml` | Push to `main` / Manual | Auto-promotes Dev → Test; manual Test → Prod |

#### Setup: GitHub Secrets

Configure these secrets in your repository settings (**Settings → Secrets → Actions**):

| Secret | Description |
|:---|:---|
| `AZURE_TENANT_ID` | Azure AD tenant identifier |
| `AZURE_CLIENT_ID` | Service Principal application ID |
| `AZURE_CLIENT_SECRET` | Service Principal secret value |
| `FABRIC_CAPACITY_ID` | Target Fabric capacity |
| `FABRIC_PIPELINE_NAME` | Deployment Pipeline display name |
| `FABRIC_GITHUB_TOKEN` | PAT with `repo` scope for Git integration |

#### End-to-End Walkthrough (CI/CD)

```
Developer pushes feature/inventory-opt
        │
        ▼
┌─────────────────────────────────────┐
│  feature-workspace-create.yml       │
│  Creates: acme-sales-inventory-opt  │
│  Connected to feature branch        │
└──────────────┬──────────────────────┘
               │ Developer works in isolated workspace
               │
        PR merged to main
               │
               ▼
┌─────────────────────────────────────┐
│  feature-workspace-cleanup.yml      │
│  Destroys: acme-sales-inventory-opt │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  deploy-to-fabric.yml               │
│  Auto-promotes: Dev → Test          │
│  (Manual trigger for Test → Prod)   │
└─────────────────────────────────────┘
```

**What happens on push to `main`:**

1. The `deploy-to-fabric.yml` workflow fires automatically
2. It authenticates using `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET`
3. It runs: `python -m usf_fabric_cli.cli promote --pipeline-name "$FABRIC_PIPELINE_NAME" --source-stage Development --target-stage Test`
4. A GitHub Step Summary is posted confirming promotion

**Manual Production promotion:**

1. Go to **Actions → Promote via Deployment Pipeline → Run workflow**
2. Select `Source: Test`, `Target: Production`
3. Add a deployment note
4. The workflow requires environment approval if targeting Production

---

## 3. Multi-Agent Specialisation Patterns

The codebase is structured around **specialist responsibility zones**. Each "agent" handles a well-defined domain. This architecture enables parallel development and clear debugging boundaries.

```
┌─────────────────────────────────────────────────────┐
│                     CLI Agent                        │
│  cli.py — Parses user input, routes to services      │
├──────────┬──────────┬──────────┬────────────────────┤
│          │          │          │                     │
▼          ▼          ▼          ▼                     ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌──────────┐ ┌────────────┐
│Deploy │ │Config │ │  Git  │ │ Pipeline │ │  Quality   │
│Agent  │ │Agent  │ │Agent  │ │  Agent   │ │  Agent     │
├───────┤ ├───────┤ ├───────┤ ├──────────┤ ├────────────┤
│deploy │ │config │ │fabric │ │deploy-   │ │black       │
│er.py  │ │.py    │ │_git_  │ │ment_     │ │flake8      │
│fabric │ │templ- │ │api.py │ │pipeline  │ │mypy        │
│_wrap- │ │ating  │ │git_   │ │.py       │ │pytest      │
│per.py │ │.py    │ │integ  │ │          │ │bandit      │
│token  │ │       │ │ration │ │          │ │            │
│_mgr   │ │       │ │.py    │ │          │ │            │
└───────┘ └───────┘ └───────┘ └──────────┘ └────────────┘
```

| Agent | Responsibility | Key Files |
|:---|:---|:---|
| **CLI Agent** | User-facing command parsing and routing | `cli.py` |
| **Deploy Agent** | Workspace creation, item provisioning, principal assignment, rollback | `deployer.py`, `fabric_wrapper.py`, `token_manager.py` |
| **Config Agent** | YAML loading, template rendering, environment overlay merging | `config.py`, `templating.py`, `generate_project.py` |
| **Git Agent** | GitHub/ADO REST API integration, workspace-to-repo connection | `fabric_git_api.py`, `git_integration.py` |
| **Pipeline Agent** | Deployment Pipeline creation, stage assignment, promotion | `deployment_pipeline.py` |
| **Quality Agent** | Formatting, linting, type-checking, testing, security scanning | `Makefile` targets: `format`, `lint`, `typecheck`, `test`, `security`, `ci` |
| **Onboard Agent** | Full 6-phase bootstrap orchestration | `onboard.py` (src/usf_fabric_cli/scripts/dev) |

### How They Interact (Onboarding Flow)

```
Onboard Agent (onboard.py)
  ├── Phase 1: Config Agent → generate_project_config()
  ├── Phase 2: Deploy Agent → deploy Dev workspace
  ├── Phase 3: Deploy Agent → deploy Test workspace
  ├── Phase 4: Deploy Agent → deploy Prod workspace
  ├── Phase 5: Pipeline Agent → create Deployment Pipeline
  └── Phase 6: Git Agent → connect Dev workspace to repo
```

---

## 4. Environment Configuration Reference

### `.env` File Structure

The `.env` file follows the [12-Factor App](https://12factor.net/config) configuration pattern. It is automatically loaded by `python-dotenv`.

| Section | Variables | Purpose |
|:---|:---|:---|
| **Azure Config** | `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` | Service Principal authentication |
| **Fabric Config** | `FABRIC_CAPACITY_ID`, `TEST_CAPACITY_ID`, `PROD_CAPACITY_ID`, `FABRIC_DOMAIN_NAME` | Capacity and domain assignment |
| **Automation** | `GITHUB_TOKEN`, `GIT_REPO_URL`, `AUTOMATION_SP_ID` | Git integration and SP identity |
| **Governance** | `ADDITIONAL_ADMIN_PRINCIPAL_ID`, `ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID` | Mandatory security principals injected into every workspace |
| **Dev Principals** | `DEV_ADMIN_EMAIL`, `DEV_ADMIN_OBJECT_ID`, `DEV_MEMBERS_OBJECT_ID` | Dev environment access |
| **Staging/Prod** | `STAGING_ADMIN_EMAIL`, `PROD_ADMIN_EMAIL`, etc. | Environment-specific access |
| **Advanced** | `LOG_LEVEL`, `AUDIT_LOG_DIR` | Operational tuning |

---

## 5. Blueprint Selection Guide

Choose a template based on your project requirements:

```
  Start Here
      │
      ├── "I'm just learning" ──────────────────── minimal_starter ★☆☆☆☆
      │
      ├── "Standard ETL pipeline" ──────────────── basic_etl ★★☆☆☆
      │
      ├── "ML/AI workloads" ────────────────────── data_science ★★☆☆☆
      │                                             advanced_analytics ★★★☆☆
      │
      ├── "Medallion Architecture" ─────────────── medallion ★★★☆☆
      │
      ├── "Real-time / IoT" ────────────────────── realtime_streaming ★★★★☆
      │
      ├── "Time-series / APM" ──────────────────── specialized_timeseries ★★★★☆
      │
      ├── "Domain-driven design" ───────────────── data_mesh_domain ★★★★☆
      │
      ├── "Cloud migration" ────────────────────── migration_hybrid ★★★★☆
      │
      ├── "Enterprise reference" ───────────────── extensive_example ★★★★☆
      │
      └── "Regulated industry (HIPAA/PCI/SOX)" ── compliance_regulated ★★★★★
```

| Template | Configures | Use Case |
|:---|:---|:---|
| `minimal_starter` | 3 numbered folders, Git connection | POCs, learning |
| `basic_etl` | 8 numbered folders, folder_rules, Git integration | Standard data pipelines |
| `medallion` | 8 numbered folders, folder_rules, deployment pipeline | Medallion architecture |
| `advanced_analytics` | 8 numbered folders, folder_rules, Git integration | Analytics & ML workloads |
| `data_science` | 8 numbered folders, folder_rules, Git integration | Research & experimentation |
| `realtime_streaming` | 8 numbered folders, folder_rules, Git integration | IoT, real-time analytics |
| `specialized_timeseries` | 8 numbered folders, folder_rules, Git integration | APM, metrics, logs |
| `data_mesh_domain` | 8 numbered folders, folder_rules, domain config | Domain ownership |
| `migration_hybrid` | 8 numbered folders, folder_rules, Git integration | Cloud migration |
| `compliance_regulated` | 8 numbered folders, folder_rules, audit config | HIPAA, PCI, SOX compliance |
| `extensive_example` | All sections demonstrated, folder_rules | Enterprise reference |

---

## 6. Quick Reference Cards

### Makefile Targets (49 Total)

#### Setup & Quality

| Target | Description | Example |
|:---|:---|:---|
| `setup` | First-time project setup | `make setup` |
| `install` | Install deps in editable mode | `make install` |
| `format` | Auto-format with black + isort | `make format` |
| `lint` | Check formatting and linting | `make lint` |
| `typecheck` | Run mypy type checking | `make typecheck` |
| `test` | Run unit tests | `make test` |
| `test-integration` | Run integration tests | `make test-integration` |
| `coverage` | Tests with coverage report | `make coverage` |
| `security` | Run bandit security scan | `make security` |
| `ci` | Full CI suite (lint+type+test+security) | `make ci` |
| `clean` | Remove caches and temp files | `make clean` |
| `build` | Build wheel distribution | `make build` |
| `check-env` | Verify conda environment is active | `make check-env` |
| `version` | Show current project version | `make version` |
| `help` | Show all available targets | `make help` |
| `pre-commit-install` | Install pre-commit hooks | `make pre-commit-install` |
| `pre-commit-run` | Run pre-commit on all files | `make pre-commit-run` |

#### Core Operations

| Target | Description | Example |
|:---|:---|:---|
| `generate` | Scaffold project config | `make generate org="Org" project="Proj" template=medallion` |
| `validate` | Validate a config file | `make validate config=path/to/config.yaml` |
| `diagnose` | Pre-flight system check | `make diagnose` |
| `deploy` | Deploy workspace | `make deploy config=... env=dev` |
| `promote` | Promote via pipeline | `make promote pipeline="Name" source=Dev target=Test` |
| `onboard` | Full bootstrap (Dev+Test+Prod+Pipeline) | `make onboard org="Org" project="Proj"` |
| `onboard-isolated` | Bootstrap with new repo | `make onboard-isolated org="Org" project="Proj" git_owner="Owner"` |
| `feature-workspace` | Create feature workspace | `make feature-workspace org="Org" project="Proj"` |
| `destroy` | Destroy workspace | `make destroy config=path/to/config.yaml` |
| `bulk-destroy` | Bulk delete workspaces | `make bulk-destroy file=list.txt` |

#### Admin Utilities

| Target | Description | Example |
|:---|:---|:---|
| `list-workspaces` | List all Fabric workspaces | `make list-workspaces` |
| `list-items` | List workspace items | `make list-items workspace="Name"` |
| `init-github-repo` | Create a GitHub repo | `make init-github-repo git_owner="Owner" repo="Repo"` |
| `analyze-migration` | Assess migration potential | `make analyze-migration` |

#### Webapp Targets

| Target | Description | Example |
|:---|:---|:---|
| `webapp-dev` | Start webapp dev servers | `make webapp-dev` |
| `webapp-build` | Build webapp for production | `make webapp-build` |

#### Docker Targets

| Target | Description |
|:---|:---|
| `docker-build` | Build Docker image |
| `docker-validate` | Validate config in container |
| `docker-deploy` | Deploy in container |
| `docker-promote` | Promote in container |
| `docker-destroy` | Destroy in container |
| `docker-shell` | Interactive shell |
| `docker-diagnose` | Diagnostics in container |
| `docker-generate` | Generate config in container |
| `docker-onboard` | Full bootstrap in container |
| `docker-onboard-isolated` | Bootstrap with repo in container |
| `docker-feature-workspace` | Feature workspace in container |
| `docker-feature-deploy` | Feature deploy in container |
| `docker-bulk-destroy` | Bulk destroy in container |
| `docker-list-workspaces` | List workspaces in container |
| `docker-list-items` | List items in container |
| `docker-init-repo` | Create ADO repo in container |

### CLI Flags Reference

```bash
# Deploy
python -m usf_fabric_cli.cli deploy CONFIG [OPTIONS]
  --env / -e               Target environment (dev/staging/prod)
  --branch / -b            Git branch for deployment
  --force-branch-workspace Create isolated workspace for branch
  --rollback-on-failure    Auto-delete items if deploy fails
  --validate-only          Only validate, don't deploy
  --diagnose               Run pre-flight checks first

# Promote
python -m usf_fabric_cli.cli promote [OPTIONS]
  --pipeline-name / -p     Fabric Deployment Pipeline name (required)
  --source-stage / -s      Source stage (default: Development)
  --target-stage / -t      Target stage (auto-inferred if omitted)
  --note / -n              Deployment note

# Destroy
python -m usf_fabric_cli.cli destroy CONFIG [OPTIONS]
  --env / -e               Target environment
  --force                  Skip confirmation prompt
  --workspace-name-override Override workspace name
```

---

## 7. The Deployment Lifecycle

Every project follows this lifecycle, regardless of which way of working you choose:

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Generate │ ──▶│ Validate │ ──▶│  Deploy  │ ──▶│ Promote  │ ──▶│ Destroy  │
│  Config  │    │  Config  │    │ to Dev   │    │ Dev→Test │    │ Cleanup  │
└──────────┘    └──────────┘    │ to Test  │    │ Test→Prod│    └──────────┘
                                │ to Prod  │    └──────────┘
                                └──────────┘
```

### What Happens During Deploy

1. **Configuration Merge** — Project YAML + environment overlay (`config/environments/{env}.yaml`)
2. **Authentication** — Service Principal login via Azure Identity
3. **Validation** — Schema and credential checks
4. **Workspace** — Create or update (idempotent)
5. **Folders** — Create missing folder structure
6. **Items** — Provision Lakehouses, Warehouses, Pipelines, Notebooks, etc.
7. **Security** — Assign principals with roles (Admin, Member, Contributor, Viewer)
8. **Domain** — Assign workspace to Fabric Domain (if configured)
9. **Git** — Connect workspace to Git repository (GitHub or Azure DevOps)

### What Happens During Onboard

The `onboard` command executes a **6-phase bootstrap** in a single operation:

| Phase | Action | Output |
|:---|:---|:---|
| 1 | Generate project config from blueprint | `config/projects/{org}/{project}.yaml` |
| 2 | Deploy Dev workspace (connected to Git `main`) | Workspace with items + principals |
| 3 | Deploy Test workspace (empty — receives via pipeline) | Empty governed workspace |
| 4 | Deploy Prod workspace (empty — receives via pipeline) | Empty governed workspace |
| 5 | Create Deployment Pipeline (`{Org}-{Project} Pipeline`) | Pipeline with 3 stages |
| 6 | Assign workspaces to pipeline stages | Dev→Development, Test→Test, Prod→Production |

---

## 8. Audit Trail

All operations are logged to `audit_logs/fabric_operations_YYYY-MM-DD.jsonl`:

```json
{"timestamp": "2026-02-11T10:00:00Z", "operation": "workspace_create", "workspace_name": "acme-sales-dev", "success": true}
{"timestamp": "2026-02-11T10:01:00Z", "operation": "item_create", "details": {"item_type": "Lakehouse", "item_name": "raw_data"}}
```

Use these logs for compliance reporting, debugging, and operational auditing.

---

## 9. Companion Resources

| Resource | Location | Description |
|:---|:---|:---|
| **Interactive Guide** | `webapp/` → `http://localhost:8080` | Web-based step-by-step guide with copy-paste commands |
| **Usage Guide** | `docs/01_User_Guides/01_Usage_Guide.md` | Full reference documentation |
| **CLI Walkthrough** | `docs/01_User_Guides/02_CLI_Walkthrough.md` | Scenario-based walkthrough |
| **Project Configuration** | `docs/01_User_Guides/03_Project_Configuration.md` | Deep dive into YAML schema |
| **Docker Deployment** | `docs/01_User_Guides/04_Docker_Deployment.md` | Docker-specific guide |
| **Client Tutorial** | `docs/01_User_Guides/05_Client_Tutorial.md` | Non-technical stakeholder guide |
| **Troubleshooting** | `docs/01_User_Guides/06_Troubleshooting.md` | Error diagnosis reference |
| **Blueprint Catalog** | `docs/01_User_Guides/07_Blueprint_Catalog.md` | All 11 templates in detail |

---

## 10. Getting Started — Today

**If you're new, do this now:**

```bash
# 1. Set up your environment (one-time)
make setup
source ~/miniconda3/etc/profile.d/conda.sh && conda activate fabric-cli-cicd

# 2. Configure your credentials
cp .env.template .env
# Fill in: AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID, FABRIC_CAPACITY_ID

# 3. Verify your setup
make diagnose

# 4. Generate your first project
make generate org="My Company" project="My Project" template=basic_etl

# 5. Deploy to development
make deploy config=config/projects/my_company/my_project.yaml env=dev

# 6. Verify in Fabric Portal
make list-workspaces
```

**You're live.** Check the [CLI Walkthrough](02_CLI_Walkthrough.md) for the full scenario playbook.
