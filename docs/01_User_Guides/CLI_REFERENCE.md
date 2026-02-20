# CLI & Makefile Reference

> **Audience**: All users | **Type**: Reference (look-up, not tutorial)
> **See also**: [LOCAL_DEPLOYMENT_GUIDE.md](LOCAL_DEPLOYMENT_GUIDE.md) for step-by-step walkthrough
> | [00_START_HERE.md](00_START_HERE.md) for orientation

Complete reference for all `fabric-cicd` CLI commands, Make targets, environment variables,
and exit codes. Use this as a quick look-up; for narrative guides, see the linked documents.

---

## Table of Contents

1. [CLI Commands](#1-cli-commands)
   - [deploy](#deploy)
   - [validate](#validate)
   - [diagnose](#diagnose)
   - [destroy](#destroy)
   - [promote](#promote)
   - [onboard](#onboard)
   - [generate](#generate)
   - [list-workspaces](#list-workspaces)
   - [list-items](#list-items)
   - [bulk-destroy](#bulk-destroy)
   - [organize-folders](#organize-folders)
   - [init-github-repo](#init-github-repo)
2. [Make Targets](#2-make-targets)
3. [Docker Make Targets](#3-docker-make-targets)
4. [Environment Variables](#4-environment-variables)
5. [Exit Codes](#5-exit-codes)
6. [Configuration File Format](#6-configuration-file-format)

---

## 1. CLI Commands

All commands are available via `fabric-cicd <command>` (after `pip install -e .`) or
`python -m usf_fabric_cli.cli <command>`.

### deploy

Deploy a Fabric workspace from a YAML configuration file.

```
fabric-cicd deploy <config> [OPTIONS]
```

| Argument / Flag | Required | Default | Description |
|----------------|----------|---------|-------------|
| `config` | **Yes** | — | Path to YAML config file |
| `--env`, `-e` | No | `None` | Environment: `dev`, `test`, `staging`, `prod` |
| `--branch`, `-b` | No | `None` | Git branch (creates branch workspace if set) |
| `--force-branch-workspace` | No | `False` | Create separate workspace for the branch |
| `--rollback-on-failure` | No | `False` | Auto-delete created items if deployment fails |
| `--validate-only` | No | `False` | Only validate config; do not deploy |
| `--diagnose` | No | `False` | Run pre-flight checks before deploying |

**Examples:**

```bash
# Deploy to dev
fabric-cicd deploy config/projects/acme/sales.yaml --env dev

# Deploy a feature branch workspace
fabric-cicd deploy config/projects/acme/sales.yaml --env dev --branch feature/new-report --force-branch-workspace

# Dry-run validation
fabric-cicd deploy config/projects/acme/sales.yaml --validate-only

# Deploy with rollback safety net
fabric-cicd deploy config/projects/acme/sales.yaml --env dev --rollback-on-failure
```

---

### validate

Validate a configuration file without deploying.

```
fabric-cicd validate <config> [OPTIONS]
```

| Argument / Flag | Required | Default | Description |
|----------------|----------|---------|-------------|
| `config` | **Yes** | — | Path to YAML config file |
| `--env`, `-e` | No | `None` | Environment to validate against |

Checks: YAML syntax, env var resolution, folder references (items referencing
a folder that exists in the `folders:` list), and structural validity.

---

### diagnose

Run diagnostic checks against the Fabric environment.

```
fabric-cicd diagnose
```

No arguments. Checks:
1. Fabric CLI installation and version
2. Service Principal authentication
3. API connectivity and workspace count

---

### destroy

Destroy a Fabric workspace.

```
fabric-cicd destroy <config> [OPTIONS]
```

| Argument / Flag | Required | Default | Description |
|----------------|----------|---------|-------------|
| `config` | **Yes** | — | Path to YAML config file |
| `--env`, `-e` | No | `None` | Environment |
| `--force`, `-f` | No | `False` | Skip confirmation prompt |
| `--workspace-name-override` | No | `None` | Override the workspace name from config |
| `--branch`, `-b` | No | `None` | Derive workspace name from branch (overrides `--workspace-name-override`) |
| `--feature-prefix` | No | `⚡` | Prefix for feature workspace names (use `''` to disable) |
| `--safe` / `--no-safe` | No | `True` | Refuse to delete workspaces containing Fabric items |
| `--force-destroy-populated` | No | `False` | Override `--safe` — delete even if workspace has items |

**Workspace name priority**: `--branch` > `--workspace-name-override` > config `workspace.name`

**Examples:**

```bash
# Safe destroy (default — will refuse if workspace has items)
fabric-cicd destroy config/projects/acme/sales.yaml --env dev --force

# Force destroy populated workspace
fabric-cicd destroy config/projects/acme/sales.yaml --force --force-destroy-populated

# Destroy a feature branch workspace by name
fabric-cicd destroy config/projects/acme/sales.yaml --branch feature/my-branch --force
```

---

### promote

Promote content through Fabric Deployment Pipeline stages.

```
fabric-cicd promote [OPTIONS]
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--pipeline-name`, `-p` | **Yes** | — | Deployment Pipeline display name |
| `--source-stage`, `-s` | No | `Development` | Source stage: `Development` or `Test` |
| `--target-stage`, `-t` | No | Auto-inferred | Target stage (auto: Dev→Test, Test→Prod) |
| `--note`, `-n` | No | `""` | Deployment note |
| `--wait` / `--no-wait` | No | `True` | Wait for promotion to complete |
| `--selective` | No | `False` | Exclude unsupported types and auto-retry failures |
| `--exclude-types` | No | `None` | Comma-separated types to exclude (default: `Warehouse,SQLEndpoint`) |
| `--wait-for-git-sync` | No | `0` | Wait N seconds for Fabric Git Sync before promoting |

**Examples:**

```bash
# Auto-promote Dev → Test
fabric-cicd promote --pipeline-name "Acme Sales Pipeline" --source-stage Development

# Promote Test → Prod with a note
fabric-cicd promote -p "Acme Sales Pipeline" -s Test -t Production -n "Release v2.1"

# Selective promotion (excludes Warehouse/SQLEndpoint by default)
fabric-cicd promote -p "Acme Sales Pipeline" --selective

# Wait for Git sync before promoting
fabric-cicd promote -p "Acme Sales Pipeline" --wait-for-git-sync 60
```

---

### onboard

Full bootstrap: generate config + deploy Dev + create Deployment Pipeline + provision Test/Prod.

```
fabric-cicd onboard [OPTIONS]
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--org` | **Yes** | — | Organization name |
| `--project` | **Yes** | — | Project name |
| `--template` | No | `medallion` | Blueprint template name |
| `--capacity-id` | No | `${FABRIC_CAPACITY_ID}` | Fabric capacity GUID |
| `--repo` | No | `${GIT_REPO_URL}` | Git repository URL |
| `--dry-run` | No | `False` | Simulate without deploying |
| `--with-feature-branch` | No | `False` | Also create a feature workspace |
| `--stages` | No | `dev,test,prod` | Comma-separated stages to provision |
| `--pipeline-name` | No | Auto-generated | Custom Deployment Pipeline name |
| `--test-workspace-name` | No | Auto-generated | Custom Test workspace name |
| `--prod-workspace-name` | No | Auto-generated | Custom Prod workspace name |
| `--create-repo` | No | `False` | Auto-create a project-specific Git repo |
| `--git-provider` | No | `github` | Git provider: `github` or `ado` |
| `--git-owner` | No | `None` | GitHub owner/org or ADO org name |
| `--ado-project` | No | `None` | Azure DevOps project name |

**Examples:**

```bash
# Standard onboard with medallion template
fabric-cicd onboard --org "Acme Corp" --project "Sales Analytics" --template medallion

# Onboard with isolated repo creation
fabric-cicd onboard --org "Acme" --project "Sales" --create-repo --git-owner "MyOrg"

# Dry run (no changes made)
fabric-cicd onboard --org "Acme" --project "Sales" --dry-run

# Only provision Dev + Test (skip Prod)
fabric-cicd onboard --org "Acme" --project "Sales" --stages dev,test
```

---

### generate

Generate a project configuration file from a blueprint template.

```
fabric-cicd generate <org_name> <project_name> [OPTIONS]
```

| Argument / Flag | Required | Default | Description |
|----------------|----------|---------|-------------|
| `org_name` | **Yes** | — | Organization name (e.g., `"Contoso Inc"`) |
| `project_name` | **Yes** | — | Project name (e.g., `"Customer Analytics"`) |
| `--template` | No | `basic_etl` | Blueprint template |
| `--capacity-id` | No | `${FABRIC_CAPACITY_ID}` | Fabric capacity GUID |
| `--git-repo` | No | `${GIT_REPO_URL}` | Git repository URL |

**Output**: `config/projects/<org_slug>/<project_slug>.yaml`

Available templates (see [Blueprint Catalog](07_Blueprint_Catalog.md)):
`basic_etl`, `medallion`, `advanced_analytics`, `data_science`, `realtime_streaming`,
`compliance_regulated`, `data_mesh_domain`, `extensive_example`, `migration_hybrid`,
`minimal_starter`, `specialized_timeseries`

---

### list-workspaces

List all Fabric workspaces accessible to the Service Principal.

```
fabric-cicd list-workspaces
```

No arguments. Outputs JSON.

---

### list-items

List items in a specific Fabric workspace.

```
fabric-cicd list-items <workspace>
```

| Argument | Required | Description |
|----------|----------|-------------|
| `workspace` | **Yes** | Workspace name |

---

### bulk-destroy

Destroy multiple workspaces from a text file.

```
fabric-cicd bulk-destroy <file> [OPTIONS]
```

| Argument / Flag | Required | Default | Description |
|----------------|----------|---------|-------------|
| `file` | **Yes** | — | Path to file (one workspace name per line) |
| `--dry-run` | No | `False` | Show what would be deleted |
| `--force` | No | `False` | Skip confirmation prompt |

---

### organize-folders

Move workspace items into folders based on `folder_rules` in the config.

```
fabric-cicd organize-folders <config> [OPTIONS]
```

| Argument / Flag | Required | Default | Description |
|----------------|----------|---------|-------------|
| `config` | **Yes** | — | Path to YAML config file |
| `--workspace`, `-w` | No | From config | Override workspace name |
| `--env`, `-e` | No | `None` | Environment |
| `--dry-run` | No | `False` | Show moves without executing |

Useful after Git Sync, which always places items at the workspace root.

---

### init-github-repo

Create and initialize a GitHub repository for Fabric Git integration.

```
fabric-cicd init-github-repo [OPTIONS]
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--owner` | **Yes** | — | GitHub user or organization |
| `--repo` | **Yes** | — | Repository name to create |
| `--branch` | No | `main` | Branch to ensure exists |
| `--private` / `--public` | No | `True` (private) | Repository visibility |

Requires `GITHUB_TOKEN` environment variable.

---

## 2. Make Targets

All local Make targets. Run `make help` for the full list.

### Environment Setup

| Target | Usage | Description |
|--------|-------|-------------|
| `setup` | `make setup` | Create conda env via `bin/setup.sh` |
| `install` | `make install` | `pip install -r requirements-dev.txt && pip install -e .` |
| `build` | `make build` | Build Python wheel |

### Code Quality

| Target | Usage | Description |
|--------|-------|-------------|
| `format` | `make format` | Run `black` and `isort` |
| `lint` | `make lint` | Run `flake8` |
| `typecheck` | `make typecheck` | Run `mypy src/` |
| `security` | `make security` | Run `bandit` security scan |
| `pre-commit` | `make pre-commit` | Run all pre-commit hooks |

### Testing

| Target | Usage | Description |
|--------|-------|-------------|
| `test` | `make test` | Run unit tests (no credentials needed) |
| `test-integration` | `make test-integration` | Run integration tests (needs `.env`) |
| `coverage` | `make coverage` | Run tests with coverage report |
| `ci` | `make ci` | Full CI pipeline (lint + test + build) |

### Local Operations

| Target | Usage | Description |
|--------|-------|-------------|
| `validate` | `make validate config=path.yaml` | Validate config |
| `diagnose` | `make diagnose` | Run pre-flight diagnostics |
| `generate` | `make generate org="Org" project="Proj" [template=basic_etl]` | Generate config from template |
| `deploy` | `make deploy config=path.yaml env=dev [branch=feature/x]` | Deploy workspace |
| `promote` | `make promote pipeline="Name" [source=Dev] [target=Test] [note="..."]` | Promote via pipeline |
| `onboard` | `make onboard org="Org" project="Proj" [template=medallion] [stages=dev,test,prod]` | Full bootstrap |
| `onboard-isolated` | `make onboard-isolated org="Org" project="Proj" git_owner="Owner"` | Bootstrap with auto-created repo |
| `feature-workspace` | `make feature-workspace org="Org" project="Proj"` | Create feature branch workspace |
| `destroy` | `make destroy config=path.yaml [env=dev] [force=1] [workspace_override="Name"]` | Destroy workspace |
| `bulk-destroy` | `make bulk-destroy file=list.txt` | Destroy workspaces from file |
| `init-github-repo` | `make init-github-repo git_owner="Owner" repo="Repo"` | Create GitHub repo |

### Admin Utilities

| Target | Usage | Description |
|--------|-------|-------------|
| `list-workspaces` | `make list-workspaces` | List all Fabric workspaces |
| `list-items` | `make list-items workspace="Name"` | List items in a workspace |
| `analyze-migration` | `make analyze-migration` | Analyze Fabric CLI migration options |

### Webapp

| Target | Usage | Description |
|--------|-------|-------------|
| `webapp-dev` | `make webapp-dev` | Start interactive guide in dev mode |
| `webapp-build` | `make webapp-build` | Build webapp Docker images |

---

## 3. Docker Make Targets

All Docker targets accept `ENVFILE=.env` (default) to specify which `.env` file to use.

| Target | Usage | Description |
|--------|-------|-------------|
| `docker-build` | `make docker-build` | Build Docker image |
| `docker-validate` | `make docker-validate config=... ENVFILE=.env` | Validate config in Docker |
| `docker-deploy` | `make docker-deploy config=... env=dev ENVFILE=.env` | Deploy in Docker |
| `docker-promote` | `make docker-promote pipeline="Name" [source=Dev]` | Promote in Docker |
| `docker-destroy` | `make docker-destroy config=... ENVFILE=.env` | Destroy in Docker |
| `docker-shell` | `make docker-shell ENVFILE=.env` | Interactive bash shell in container |
| `docker-diagnose` | `make docker-diagnose ENVFILE=.env` | Run diagnostics in Docker |
| `docker-generate` | `make docker-generate org="Org" project="Proj" [template=basic_etl]` | Generate config in Docker |
| `docker-init-repo` | `make docker-init-repo org="Org" project="Proj" repo="Repo"` | Init ADO repo in Docker |
| `docker-feature-deploy` | `make docker-feature-deploy config=... env=dev branch=feature/x` | Feature workspace via Docker |
| `docker-onboard` | `make docker-onboard org="Org" project="Proj" [stages=dev,test,prod]` | Full onboard in Docker |
| `docker-onboard-isolated` | `make docker-onboard-isolated org="Org" project="Proj" git_owner="Owner"` | Isolated onboard in Docker |
| `docker-feature-workspace` | `make docker-feature-workspace org="Org" project="Proj"` | Feature workspace in Docker |
| `docker-bulk-destroy` | `make docker-bulk-destroy file=list.txt` | Bulk destroy in Docker |
| `docker-list-workspaces` | `make docker-list-workspaces` | List workspaces in Docker |
| `docker-list-items` | `make docker-list-items workspace="Name"` | List items in Docker |

---

## 4. Environment Variables

Loaded from `.env` (copy from `.env.template`). See [LOCAL_DEPLOYMENT_GUIDE.md](LOCAL_DEPLOYMENT_GUIDE.md#3-configure-credentials) for walkthrough.

### Required

| Variable | Description |
|----------|-------------|
| `AZURE_CLIENT_ID` | Service Principal application (client) ID |
| `AZURE_CLIENT_SECRET` | Service Principal client secret |
| `AZURE_TENANT_ID` | Azure Entra ID tenant ID |
| `FABRIC_CAPACITY_ID` | Primary Fabric capacity GUID |

### Git Integration (required for Git-connected workspaces)

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub fine-grained PAT (with `repo` scope) |
| `GIT_REPO_URL` | Git repository clone URL |

### Multi-Stage Capacity (optional, for environment promotion)

| Variable | Description |
|----------|-------------|
| `FABRIC_TEST_CAPACITY_ID` | Capacity for Test workspaces |
| `FABRIC_PROD_CAPACITY_ID` | Capacity for Prod workspaces |

### Governance Principals (optional, auto-injected into every workspace)

| Variable | Description |
|----------|-------------|
| `ADDITIONAL_ADMIN_PRINCIPAL_ID` | Security group OID → auto-granted Admin role |
| `ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID` | Security group OID → auto-granted Contributor role |

### Project-Specific Principals

Naming convention: `<PROJECT>_ADMIN_ID`, `<PROJECT>_MEMBERS_ID` (supports comma-separated GUIDs).

| Variable (example) | Description |
|--------------------|-------------|
| `EDP_ADMIN_ID` | EDP project admin group OID |
| `EDP_MEMBERS_ID` | EDP project member OIDs (comma-separated) |
| `RE_SALES_ADMIN_ID` | RE Sales admin group OID |

### Advanced / Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `AZURE_KEYVAULT_URL` | — | Key Vault URL (enables KV secret lookup) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `AUDIT_LOG_DIR` | `audit_logs` | Audit log output directory |
| `FABRIC_CLI_TELEMETRY` | `true` | Enable usage telemetry |
| `PROJECT_PREFIX` | — | Workspace name prefix |
| `FABRIC_DOMAIN_NAME` | — | Fabric domain to assign |
| `FABRIC_PIPELINE_NAME` | — | Default Deployment Pipeline name |

---

## 5. Exit Codes

| Code | Meaning | Typical Cause |
|------|---------|--------------|
| `0` | Success | Operation completed normally |
| `1` | General failure | Config error, auth failure, API error |
| `2` | Safety block (destroy only) | Workspace contains items and `--safe` is enabled |

---

## 6. Configuration File Format

Minimal configuration file:

```yaml
workspace:
  name: "my-workspace-dev"
  capacity_id: "${FABRIC_CAPACITY_ID}"
  description: "My project workspace"

folders:
  - "000 Orchestrate"
  - "100 Ingest"
  - "200 Store"
  - "300 Prepare"
  - "400 Model"
  - "500 Visualize"
  - "999 Libraries"
  - "Archive"

principals:
  - id: "${ADDITIONAL_ADMIN_PRINCIPAL_ID}"
    role: "Admin"
```

Extended configuration with all sections:

```yaml
workspace:
  name: "my-workspace-dev"
  display_name: "My Workspace (Dev)"
  capacity_id: "${FABRIC_CAPACITY_ID}"
  description: "My project workspace"
  domain: "${FABRIC_DOMAIN_NAME}"
  git_repo: "${GIT_REPO_URL}"
  git_branch: "main"
  git_directory: "/"

folders:
  - "000 Orchestrate"
  - "100 Ingest"
  - "200 Store"
  - "300 Prepare"
  - "400 Model"
  - "500 Visualize"
  - "999 Libraries"
  - "Archive"

folder_rules:              # For organize-folders command (post-Git-Sync)
  - type: DataPipeline
    folder: "000 Orchestrate"
  - type: Lakehouse
    folder: "200 Store"
  - type: Notebook
    folder: "300 Prepare"
  - type: SemanticModel
    folder: "400 Model"
  - type: Report
    folder: "500 Visualize"

# Item arrays below are EMPTY in Git-sync-only blueprints (current standard).
# Fabric items are committed to Git and synced by Fabric Git Sync.
# Populate these only if your workflow requires the CLI to create items directly.
lakehouses:
  - name: raw_lakehouse
    folder: "200 Store"
  - name: curated_lakehouse
    folder: "200 Store"

warehouses:
  - name: reporting_warehouse
    folder: "200 Store"

notebooks:
  - name: transform_notebook
    folder: "300 Prepare"
    file_path: "templates/notebooks/transform.py"

pipelines:
  - name: etl_pipeline
    folder: "000 Orchestrate"

semantic_models:
  - name: sales_model
    folder: "400 Model"

resources:                 # Generic Fabric item types (54+)
  - type: "Eventstream"
    name: "iot_events"
  - type: "KQLDatabase"
    name: "telemetry_db"

principals:
  - id: "${MY_PROJECT_ADMIN_ID}"
    role: "Admin"
    description: "Project admin group"
  - id: "${MY_PROJECT_MEMBERS_ID}"
    role: "Member"
    description: "Project team members"

deployment_pipeline:       # For promote command
  name: "My Project Pipeline"
  stages:
    - name: "Development"
      workspace: "my-workspace-dev"
    - name: "Test"
      workspace: "my-workspace-test"
    - name: "Production"
      workspace: "my-workspace-prod"

environments:              # Per-environment overrides
  dev:
    workspace:
      capacity_id: "${FABRIC_CAPACITY_ID}"
  test:
    workspace:
      capacity_id: "${FABRIC_TEST_CAPACITY_ID}"
  prod:
    workspace:
      capacity_id: "${FABRIC_PROD_CAPACITY_ID}"
```

For full details on configuration, see [Project Configuration Guide](03_Project_Configuration.md).
