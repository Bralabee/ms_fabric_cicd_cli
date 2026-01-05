# Fabric CLI CI/CD - Interactive Guide

An interactive web application that provides **comprehensive, actionable step-by-step guidance** for using the Microsoft Fabric CLI CI/CD Enterprise Deployment Framework. Every scenario includes real terminal commands, Make targets, CLI entry points, and expected outputs.

## Features

- **Actionable Command Guidance**: Every scenario includes exact `make` commands, CLI syntax, and Python scripts
- **Real Expected Outputs**: See exactly what successful execution looks like
- **Interactive Progress Tracking**: Track your progress through each guide
- **Code Snippets with Copy**: Easily copy commands and code examples
- **Blueprint Templates**: Visual guide to all 10 production-ready templates
- **Troubleshooting**: Comprehensive error diagnosis with utility scripts
- **Search Functionality**: Find specific topics quickly
- **Dark/Light Mode**: Accessible UI with theme support

## What You'll Learn

Each scenario provides **production-ready commands** you can run immediately:

| Scenario | Key Commands |
|----------|--------------|
| Getting Started | `make install`, `make diagnose`, `make help` |
| Project Generation | `python scripts/generate_project.py` with all 10 templates |
| Local Deployment | `make validate`, `make deploy`, `make destroy`, `make bulk-destroy` |
| Docker Deployment | `make docker-build`, `make docker-deploy`, `make docker-shell`, `make docker-generate` |
| Feature Branches | `make docker-feature-deploy`, feature workspace naming |
| Git Integration | `init_ado_repo.py`, `debug_ado_access.py`, `make docker-init-repo` |
| Troubleshooting | `make diagnose`, `preflight_check.py`, audit log analysis |

## Architecture

```
webapp/
├── backend/           # FastAPI Python backend
│   ├── app/          # Application code
│   │   ├── api/      # API routes
│   │   ├── content/  # YAML scenario definitions
│   │   └── models/   # Pydantic models
│   ├── tests/        # Backend tests
│   └── requirements.txt
├── frontend/         # React TypeScript frontend
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── pages/       # Page components
│   │   ├── hooks/       # Custom hooks
│   │   └── lib/         # Utilities
│   └── package.json
└── docker-compose.yml  # Development orchestration
```

## Quick Start

### Docker (Recommended for Deployment)

```bash
# From webapp directory
make docker-build   # Build images
make docker-up      # Start containers
```

Application will be available at **http://localhost:8080**

```bash
make docker-logs    # View logs
make docker-down    # Stop containers
```

### Development Mode

```bash
# From webapp directory
make dev
```

This starts both backend (port 8001) and frontend (port 5173) with hot-reload.

### Manual Setup

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Available Scenarios

Each scenario provides **complete command references** with expected outputs:

1. **Getting Started** - Complete environment setup
   - Conda environment: `conda activate fabric-cli-cicd`
   - Package installation: `make install`
   - Service Principal & `.env` configuration
   - CLI entry points: `fabric-cicd`, Make targets, scripts
   - Preflight diagnostics: `make diagnose`, `preflight_check.py`

2. **Project Generation** - Blueprint templates and config generation
   - All 10 templates with detailed use cases
   - `python scripts/generate_project.py "Org" "Project" --template <template>`
   - Generated YAML structure walkthrough
   - Customization guidance

3. **Local Deployment** - Deploy without Docker
   - Validation: `make validate config=...`
   - Deployment: `make deploy config=... env=...`
   - Verification: `list_workspace_items.py`
   - Destroy: `make destroy`, `make bulk-destroy`

4. **Docker Deployment** - Containerized enterprise deployments
   - `make docker-build`, `make docker-shell ENVFILE=.env`
   - All Docker commands: `docker-diagnose`, `docker-validate`, `docker-deploy`, `docker-destroy`
   - `make docker-generate`, `make docker-init-repo`
   - Multi-tenant support, CI/CD patterns

5. **Feature Branch Workflows** - Isolated development workspaces
   - `make docker-feature-deploy config=... env=dev branch=feature/x`
   - Workspace naming conventions
   - Bulk cleanup: `make bulk-destroy file=...`
   - Complete GitHub Actions CI/CD example

6. **Git Integration** - Version control for Fabric workspaces
   - `init_ado_repo.py`, `debug_ado_access.py`
   - `make docker-init-repo`
   - YAML config: `git_repo`, `git_branch` settings
   - Common Git connectivity errors

7. **Troubleshooting** - Comprehensive diagnostic guide
   - `make diagnose`, `preflight_check.py`
   - Audit log investigation (`audit_logs/`)
   - All utility scripts reference
   - Common error patterns: auth, permissions, capacity, Docker, Git

## Blueprint Templates

The guide covers all 10 production-ready blueprints:

| Template | Best For | Complexity |
|----------|----------|------------|
| minimal_starter | Learning, POCs | ★☆☆☆☆ |
| basic_etl | Standard ETL pipelines | ★★☆☆☆ |
| advanced_analytics | ML/AI workloads | ★★★☆☆ |
| data_science | Research & experimentation | ★★☆☆☆ |
| extensive_example | Enterprise reference | ★★★★☆ |
| realtime_streaming | IoT, events, real-time | ★★★★☆ |
| compliance_regulated | Healthcare, Finance, Gov | ★★★★★ |
| data_mesh_domain | Domain-driven orgs | ★★★★☆ |
| migration_hybrid | Cloud migration projects | ★★★★☆ |
| specialized_timeseries | Time-series, APM, logs | ★★★★☆ |

## API Documentation

Once running, visit http://localhost:8001/docs for the interactive API documentation.

## Technology Stack

- **Backend**: FastAPI, Python 3.11+, Pydantic v2
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui
- **Testing**: pytest (backend), vitest (frontend)

## Deployment Options

### 🐳 Docker Quick Start (Recommended)

The fastest way to get started locally or share with others:

```bash
cd webapp

# Option 1: Quick start script (build + run)
./docker-quickstart.sh

# Option 2: Using Make
make docker-build    # Build images
make docker-up       # Start containers
```

**Access the application at http://localhost:8080**

```bash
# Other Docker commands
make docker-logs     # View container logs
make docker-status   # Show container status
make docker-down     # Stop containers
make docker-clean    # Remove images and volumes
```

### ☁️ Azure Container Apps Deployment

Deploy to Azure Container Apps with a single command:

```bash
cd webapp

# Preview deployment (no changes made)
make deploy-azure-dryrun

# Deploy to Azure
make deploy-azure
```

The script will:
1. Create a resource group and Azure Container Registry
2. Build and push Docker images
3. Create Container Apps Environment
4. Deploy backend (internal ingress) and frontend (external ingress)
5. Output the public URL

**Prerequisites:**
- Azure CLI installed (`az login` completed)
- Docker running locally
- Sufficient Azure permissions (Contributor role)

**Customization:**
```bash
# Custom resource names and location
./deploy-azure.sh --name my-fabric-guide --location westus2

# Use existing images (skip build)
./deploy-azure.sh --skip-build --tag v1.0.0
```

**Teardown:**
```bash
az group delete --name fabric-cli-guide-rg --yes --no-wait
```

### Manual Docker Deployment

```bash
# Build images
docker compose build

# Start containers
docker compose up -d

# For production with resource limits
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Environment Variables

Copy `.env.template` to `.env` and customize:

```bash
# Azure Container Registry (for production)
ACR_NAME=fabriccliguide
TAG=latest

# Backend Configuration
CORS_ORIGINS=http://localhost:8080
LOG_LEVEL=info
```

