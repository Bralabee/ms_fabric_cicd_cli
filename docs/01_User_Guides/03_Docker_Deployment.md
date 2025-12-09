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
1.  **Capacity Access**: The SP must be an admin or contributor on the Fabric Capacity.
2.  **Tenant Settings**: "Allow service principals to use Power BI APIs" must be enabled in the Fabric Admin Portal.

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
