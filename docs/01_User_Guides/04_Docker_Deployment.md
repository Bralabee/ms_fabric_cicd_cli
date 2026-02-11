# Docker Deployment Guide for Fabric CI/CD

This guide provides detailed instructions on how to use the Dockerized version of the Fabric CI/CD tool. This approach is recommended for third-party integrators and CI/CD pipelines as it ensures a consistent environment with all dependencies pre-installed.

## Prerequisites

- **Docker**: Ensure Docker is installed and running on your machine.
- **Environment Variables**: You need a `.env` file with valid credentials.

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
  
principals:
  - id: "d0555555-5555-5555-5555-555555555555" # User Object ID
    role: "Admin"
  - id: "88e55555-5555-5555-5555-555555555555" # Service Principal Object ID
    role: "Contributor"
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
  - id: "d0555555-5555-5555-5555-555555555555" # Admin User Object ID
    role: "Admin"
  - id: "e0555555-5555-5555-5555-555555555555" # Member User Object ID
    role: "Member"
  - id: "88e55555-5555-5555-5555-555555555555" # Service Principal Object ID
    role: "Contributor"
```

Supported Roles: `Admin`, `Member`, `Contributor`, `Viewer`.

## 6. Troubleshooting

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

## 7. Interactive Learning Webapp

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
