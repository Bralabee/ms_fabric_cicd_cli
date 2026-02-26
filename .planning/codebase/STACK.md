# Technology Stack

**Analysis Date:** 2026-02-26

## Languages

**Primary:**
- Python 3.9+ - CLI core, backend services, data processing
- TypeScript 5.3.3 - Frontend webapp (React)
- YAML 6.0 - Configuration, blueprint templates, workflows

**Secondary:**
- Bash - Makefile targets, Docker entrypoints, utility scripts
- JSON - Package manifests, schema definitions, configuration

## Runtime

**Environment:**
- Python 3.11 (specified in pyproject.toml, Dockerfile, and CI)
- Node.js 18+ (implied by package.json)
- Docker (multi-stage builds for production)

**Package Manager:**
- pip (Python package manager)
- npm (Node.js package manager for frontend)
- Lockfile: `requirements.txt`, `requirements-dev.txt`, `package.json` (no package-lock.json committed)

## Frameworks

**Core (Python):**
- `typer>=0.9.0` - CLI framework, used for `usf_fabric_cli.cli:app` entrypoint
- `rich>=13.0.0` - Terminal UI and rich formatting for console output
- `pydantic>=2.5.0` / `pydantic-settings>=2.1.0` - Data validation and settings management

**Web Frontend:**
- `react>=18.2.0` - UI library
- `react-router-dom>=6.21.1` - Client-side routing
- `react-markdown>=9.0.1` - Markdown rendering in guides
- `vite>=5.0.10` - Frontend build tool and dev server

**UI Components (Frontend):**
- `@radix-ui/*` (accordion, dialog, icons, progress, scroll-area, select, tabs, toast) - Accessible component library
- `tailwindcss>=3.4.0` - Utility-first CSS framework
- `tailwindcss-animate>=1.0.7` - Animation utilities
- `lucide-react>=0.303.0` - Icon library
- `class-variance-authority>=0.7.0` - Variant management for components

**Testing:**
- `pytest>=7.4.0` - Python unit testing framework
- `pytest-cov>=4.1.0` - Coverage reporting
- `vitest>=1.1.3` - Frontend (TypeScript) test runner

**Build/Dev (Python):**
- `black==25.1.0` - Code formatter (line-length: 88)
- `isort>=5.13.0` - Import statement organizer (profile: black)
- `flake8==7.3.0` - Style guide enforcement
- `mypy>=1.5.0` - Static type checking

**Code Quality:**
- `bandit>=1.7.0` - Security vulnerability scanner

**Build/Dev (Frontend):**
- `@vitejs/plugin-react>=4.2.1` - React plugin for Vite
- `typescript>=5.3.3` - TypeScript compiler
- `autoprefixer>=10.4.16` - CSS vendor prefixes
- `postcss>=8.4.32` - CSS transformation
- `eslint>=8.56.0` - JavaScript linting
- `@typescript-eslint/eslint-plugin>=6.17.0` - TypeScript eslint rules
- `@typescript-eslint/parser>=6.17.0` - TypeScript parser for eslint

## Key Dependencies

**Critical (Azure):**
- `azure-identity>=1.15.0` - Azure AD authentication via Service Principal or DefaultAzureCredential
- `azure-keyvault-secrets>=4.7.0` - Azure Key Vault integration for secrets management
- `azure-storage-blob>=12.19.0` - Azure Blob Storage operations
- `ms-fabric-cli>=v1.3.1` - Microsoft Fabric CLI (installed from GitHub, January 2026 release)

**HTTP & API:**
- `requests>=2.31.0` - HTTP client for REST API calls to Fabric, GitHub, Azure DevOps APIs

**Configuration & Validation:**
- `pyyaml>=6.0` - YAML parsing for configuration files
- `jsonschema>=4.19.0` - JSON Schema validation
- `python-dotenv>=1.0.0` - Environment variable loading from .env files
- `jinja2>=3.1.2` - Template engine for configuration generation
- `packaging>=23.0` - Version parsing and comparison

**Git Integration:**
- `gitpython>=3.1.0` - Python Git bindings for repository operations

## Configuration

**Environment:**
- `.env` file required for local development (loads via `python-dotenv`)
- CI/CD uses GitHub Actions with `actions/setup-python@v6` for Python 3.11
- Docker image includes virtual environment `/opt/venv` with all dependencies pre-installed

**Build:**
- `pyproject.toml` - Project metadata, dependencies, build system (setuptools), entry points
- `Makefile` - Development, testing, and deployment automation
- `webapp/Makefile` - Frontend-specific build targets
- Dockerfile - Multi-stage production image (builder + runtime)
- `.github/workflows/ci.yml` - GitHub Actions CI pipeline

**Frontend:**
- `vite.config.ts` - Vite bundler configuration (implicit)
- `tsconfig.json` - TypeScript compiler options
- `.eslintrc` configuration (implicit in package.json linting)
- `tailwindcss` config file (implicit)
- `postcss.config.js` (implicit, for autoprefixer)

## Entry Points

**Python CLI:**
- `fabric-cicd` - Primary command-line entrypoint (installed via `fabric-cicd = "usf_fabric_cli.cli:app"`)
- `usf-fabric` - Backward-compatible alias entrypoint

**Frontend:**
- `webapp/frontend/package.json` scripts: `dev`, `build`, `preview`, `lint`, `test`
- Dev server: `vite` (runs on localhost:5173 by default)
- Production build: `vite build` → `dist/` directory

## Platform Requirements

**Development:**
- Python 3.11 (via `python3` command or conda environment `fabric-cli-cicd`)
- Node.js 18+ (for frontend development)
- pip package manager
- Git (for cloning and repository operations)
- Docker (for containerized development and deployment)
- conda (recommended, via miniconda3)

**Production:**
- Python 3.11-slim Docker image as base (from `python:3.11-slim`)
- Runtime system dependencies: git, curl (for healthchecks)
- Azure credentials (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID, or FABRIC_TOKEN)
- Fabric CLI v1.3.1 installed in Docker image

## Deployment Targets

**Docker:**
- Multi-stage Dockerfile builds `fabric-cli-cicd` image
- Runs as non-root user `fabric:fabric` (UID 1000) for security
- Entrypoint: `fabric-cicd` command
- Default command: `--help`
- Health check: `fab --version` every 30s

**Package Distribution:**
- Python wheel distribution via setuptools build system
- Published to PyPI (implied by wheel-based CI/CD)

## Version Management

- **CLI Version:** 1.7.17 (from `pyproject.toml`)
- **Python:** >=3.9 (minimum), 3.11 (recommended)
- **Node.js:** No explicit version constraint in package.json
- **Fabric CLI:** v1.3.1 (installed from GitHub)

---

*Stack analysis: 2026-02-26*
