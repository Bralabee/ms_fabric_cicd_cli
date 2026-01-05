# Fabric CLI CI/CD - Interactive Guide

An interactive web application that provides step-by-step guidance for using the Microsoft Fabric CLI CI/CD Enterprise Deployment Framework.

## Features

- **Chronological Walkthroughs**: Step-by-step guides organized by deployment scenario
- **Interactive Progress Tracking**: Track your progress through each guide
- **Code Snippets with Copy**: Easily copy commands and code examples
- **Blueprint Templates**: Visual guide to all 10 production-ready templates
- **Search Functionality**: Find specific topics quickly
- **Dark/Light Mode**: Accessible UI with theme support
- **Mobile Responsive**: Works on all device sizes

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

1. **Getting Started** - Prerequisites, environment setup, and credential configuration
2. **Project Generation** - Using blueprint templates to scaffold projects
3. **Configuration Deep Dive** - Understanding YAML configuration patterns
4. **Local Deployment** - Deploy using Python commands and Makefile
5. **Docker Deployment** - Containerized deployment workflows
6. **Feature Branch Workflows** - Parallel development with isolated workspaces
7. **Git Integration** - Azure DevOps and GitHub repository connections
8. **CI/CD Pipelines** - Automated deployment with GitHub Actions
9. **Troubleshooting** - Common issues and solutions

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

### Azure Container Apps

```bash
# Build and push to Azure Container Registry
az acr login --name <your-registry>
docker compose build
docker tag fabric-cli-guide-frontend <your-registry>.azurecr.io/fabric-cli-guide-frontend:latest
docker tag fabric-cli-guide-backend <your-registry>.azurecr.io/fabric-cli-guide-backend:latest
docker push <your-registry>.azurecr.io/fabric-cli-guide-frontend:latest
docker push <your-registry>.azurecr.io/fabric-cli-guide-backend:latest
```

### Environment Variables

For production, set these environment variables:
- `CORS_ORIGINS`: Allowed origins for CORS (default: `*`)
