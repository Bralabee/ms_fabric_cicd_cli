# Docker Deployment Guide for Fabric CI/CD

> **Audience**: DevOps Engineers, CI/CD Pipeline Authors | **Time**: 20–30 min | **Deployment Path**: Docker
> **Difficulty**: Intermediate | **Prerequisites**: Docker installed, `.env` configured
> **See also**: [00_START_HERE.md](00_START_HERE.md) for orientation | [LOCAL_DEPLOYMENT_GUIDE.md](LOCAL_DEPLOYMENT_GUIDE.md) for non-Docker path | [CLI Reference](CLI_REFERENCE.md) for all Docker Make targets

This guide covers deploying Microsoft Fabric workspaces using the Dockerized CLI.
No Python, conda, or local dependencies required — everything runs inside the container.

### When to Use Docker vs Local Python

| Criterion | Docker | Local Python |
|-----------|--------|-------------|
| **No Python/conda needed** | ✅ | ❌ |
| **Consistent environment** | ✅ Identical everywhere | Varies by machine |
| **Multi-tenant isolation** | ✅ Separate `.env` per client | Manual env switching |
| **CI/CD pipeline use** | ✅ Recommended | Possible but messier |
| **Iterating on CLI source code** | ❌ Rebuild image each change | ✅ Instant with `pip install -e .` |
| **Interactive debugging** | Via `docker-shell` | Native tools |

**Recommendation**: Use Docker for deployments and CI/CD. Use local Python for developing the CLI itself.

## Prerequisites

| Requirement | How to Verify | How to Install |
|-------------|--------------|----------------|
| **Docker Engine 20+** | `docker --version` | [docs.docker.com/get-docker](https://docs.docker.com/get-docker/) |
| **Docker Compose v2** (optional) | `docker compose version` | Included with Docker Desktop |
| **`.env` file** | `ls .env` | `cp .env.template .env && nano .env` |
| **Service Principal** | — | Azure Portal → Entra ID → App registrations |
| **Fabric Capacity** | — | Fabric Admin Portal → Capacity settings |

> **Tip**: On Linux without Docker Desktop, install Docker Engine via your package manager:
> `sudo apt install docker.io` (Ubuntu) or `sudo dnf install docker` (Fedora).

## 1. Configuration Setup

### Environment Variables (`.env`)

Create a `.env` file in the root directory with the following required variables:

```dotenv
# Service Principal Credentials
AZURE_CLIENT_ID=<your-client-id>
AZURE_CLIENT_SECRET=<your-client-secret>
AZURE_TENANT_ID=<your-tenant-id>

# Fabric Configuration
FABRIC_CAPACITY_ID=<your-capacity-id>

# Optional: Git Integration
GITHUB_TOKEN=<your-github-token>
```

### Project Configuration (`config/`)

Ensure your project configuration files are located in the `config/` directory. The Docker container mounts this directory to access your configurations.

Example `config/my_project.yaml`:

```yaml
workspace:
  name: "My_Project_Workspace"
  capacity_id: "${FABRIC_CAPACITY_ID}"

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
  - id: "d0555555-5555-5555-5555-555555555555"
    role: "Admin"
    description: "User Object ID"
  - id: "88e55555-5555-5555-5555-555555555555"
    role: "Contributor"
    description: "Service Principal Object ID"
```

## 2. Building the Docker Image

Build the Docker image using the provided Makefile command:

```bash
make docker-build
```

Or manually:

```bash
docker build -t fabric-cli-cicd .
```

> **Note:** The Docker image uses a **multi-stage build** (builder + runtime) for ~60% smaller images. The builder stage installs all dependencies into a virtual environment, and the runtime stage copies only the pre-built venv.

## 3. Validating Configuration

Before deploying, validate your configuration to ensure syntax and schema correctness.

Using Makefile:

```bash
make docker-validate config=config/my_project.yaml
```

Manually:

```bash
docker run --rm --env-file .env \
  -v $(pwd)/config:/app/config \
  fabric-cli-cicd \
  validate config/my_project.yaml
```

## 4. Deploying to Fabric

Deploy your workspace to the target environment (e.g., `dev`, `staging`, `prod`).

Using Makefile:

```bash
make docker-deploy config=config/my_project.yaml env=dev
```

Manually:

```bash
docker run --rm --env-file .env \
  -v $(pwd)/config:/app/config \
  fabric-cli-cicd \
  deploy config/my_project.yaml --env dev
```

### Important Note on Authentication

The Docker container is configured to use **Service Principal authentication**. Ensure your Service Principal has:

1. **Capacity Access**: The SP must be an admin or contributor on the Fabric Capacity.
2. **Tenant Settings**: "Allow service principals to use Power BI APIs" must be enabled in the Fabric Admin Portal.

## 5. Managing Principals

Adding users and service principals to your workspace is a critical step. Define them in your configuration file under the `principals` section.

**Important:** You must use **Object IDs (GUIDs)** for all principals. Email addresses are not supported.

```yaml
principals:
  - id: "d0555555-5555-5555-5555-555555555555"
    role: "Admin"
    description: "Admin User Object ID"
  - id: "e0555555-5555-5555-5555-555555555555"
    role: "Member"
    description: "Member User Object ID"
  - id: "88e55555-5555-5555-5555-555555555555"
    role: "Contributor"
    description: "Service Principal Object ID"
```

Supported Roles: `Admin`, `Member`, `Contributor`, `Viewer`.

## 6. End-to-End Worked Example

Complete walkthrough: from zero to a deployed Fabric workspace using only Docker.

```bash
# 1. Clone the repo
git clone https://github.com/<org>/usf_fabric_cli_cicd.git
cd usf_fabric_cli_cicd

# 2. Create .env from template
cp .env.template .env
nano .env  # Fill in AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID, FABRIC_CAPACITY_ID

# 3. Build the Docker image (~2-3 minutes first time)
make docker-build

# 4. Run diagnostics to verify credentials
make docker-diagnose ENVFILE=.env
# Expected: ✅ Fabric CLI: 1.3.x  ✅ Authentication: Valid  ✅ API Connectivity: N workspaces

# 5. Generate a project config
make docker-generate org="Acme Corp" project="Sales Analytics" template=basic_etl
# Creates: config/projects/acme_corp/sales_analytics.yaml

# 6. Validate the config
make docker-validate config=config/projects/acme_corp/sales_analytics.yaml ENVFILE=.env

# 7. Deploy!
make docker-deploy config=config/projects/acme_corp/sales_analytics.yaml env=dev ENVFILE=.env

# 8. Verify — list items in the new workspace
make docker-list-items workspace="acme-sales-analytics-dev" ENVFILE=.env
```

### Verification Checklist

After deployment, verify in the [Fabric Portal](https://app.fabric.microsoft.com):

| # | Check | Expected |
|---|-------|----------|
| 1 | Workspace exists | Named per config `workspace.name` |
| 2 | Capacity assigned | Matches `FABRIC_CAPACITY_ID` |
| 3 | Folders created | All numbered folders from `folders:` list visible |
| 4 | Principals assigned | SP + security groups with correct roles |
| 5 | Git connected | Source control shows repo + branch (if configured) |
| 6 | Items synced | Fabric items appear after Git Sync completes (Git-sync-only) |

## 7. Troubleshooting

### Interactive Shell

If you need to debug inside the container:

```bash
make docker-shell
```

### Common Issues

- **Capacity Assignment Failed**: Ensure the `FABRIC_CAPACITY_ID` is correct and the Service Principal has permissions on it.
- **Authentication Failed**: Verify `AZURE_CLIENT_ID` and `AZURE_CLIENT_SECRET` in your `.env` file.
- **Encryption Error**: The container automatically sets `encryption_fallback_enabled` to `true` to avoid keyring issues in headless environments.

### Multi-Tenant Deployments

You can manage multiple clients by using separate `.env` files per organisation:

```bash
# Deploy for Client A (uses Client A's service principal)
make docker-deploy config=config/projects/clientA/project.yaml env=dev ENVFILE=.env.clientA

# Deploy for Client B
make docker-deploy config=config/projects/clientB/project.yaml env=dev ENVFILE=.env.clientB
```

### Complete Docker Reference

| Target | Usage | Description |
|--------|-------|-------------|
| `docker-build` | `make docker-build` | Build the Docker image (multi-stage) |
| `docker-validate` | `make docker-validate config=<path>` | Validate configuration |
| `docker-deploy` | `make docker-deploy config=<path> env=<env>` | Deploy workspace |
| `docker-promote` | `make docker-promote pipeline="Name" [source=Dev] [target=Test]` | Promote via Deployment Pipeline |
| `docker-destroy` | `make docker-destroy config=<path>` | Destroy workspace |
| `docker-diagnose` | `make docker-diagnose` | Run diagnostics |
| `docker-generate` | `make docker-generate org="Org" project="Proj" [template=basic_etl]` | Generate project config |
| `docker-init-repo` | `make docker-init-repo git_owner=<owner> repo=<name>` | Initialize GitHub repo |
| `docker-feature-deploy` | `make docker-feature-deploy config=<path> env=dev branch=<name>` | Feature branch deploy |
| `docker-onboard` | `make docker-onboard org="Org" project="Proj"` | Full bootstrap (Dev+Test+Prod+Pipeline) |
| `docker-onboard-isolated` | `make docker-onboard-isolated org="Org" project="Proj" git_owner="Owner"` | Bootstrap with auto-created repo |
| `docker-feature-workspace` | `make docker-feature-workspace org="Org" project="Proj"` | Create isolated feature workspace |
| `docker-bulk-destroy` | `make docker-bulk-destroy file=<list>` | Bulk destroy workspaces from list |
| `docker-list-workspaces` | `make docker-list-workspaces` | List all accessible workspaces |
| `docker-list-items` | `make docker-list-items workspace="Name"` | List items in a workspace |
| `docker-shell` | `make docker-shell` | Interactive shell in container |

All Docker targets support `ENVFILE=.env.custom` for multi-tenant operations.

## 8. Interactive Learning Webapp

The project includes a Dockerized interactive webapp to guide you through all workflows:

```bash
cd webapp

# Quick start (builds and runs)
./docker-quickstart.sh
# → Open http://localhost:8080

# Or using Make
make docker-build
make docker-up
```

### Features

- **Visual Workflow Diagrams**: Step-by-step flowcharts for deployment processes
- **10 Guided Scenarios**: From environment setup to medallion onboarding
- **Code Snippets**: Copy-ready commands for each step

### Deploy Webapp to Azure

```bash
cd webapp
make deploy-azure  # Deploys to Azure Container Apps
```

See [webapp/README.md](../../webapp/README.md) for detailed documentation.
