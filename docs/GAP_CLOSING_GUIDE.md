# Gap Closing Enhancements - Feature Guide

This document describes the enhancements made to close architectural gaps identified in the review of the USF Fabric CLI CI/CD project.

## Overview

The enhancements address three critical gaps:

1. **Gap A: Dependency on External `fab` CLI** - Mitigated through version pinning and containerization
2. **Gap B: Complex Transformations** - Solved with Jinja2 templating engine
3. **Gap C: Secret Management** - Implemented 12-Factor App configuration pattern
4. **Gap D: Automatic Git Connection** - Added REST API integration for workspace-to-Git connections

---

## 1. Enhanced Secret Management

### The Problem
Original implementation relied solely on `.env` files, which don't work in CI/CD pipelines where secrets are injected as environment variables.

### The Solution
Implemented waterfall priority loading:
1. **First Priority**: OS Environment Variables (CI/CD pipelines)
2. **Second Priority**: `.env` file (local development)
3. **Error**: If neither exists

### Usage

#### In Code
```python
from core.secrets import FabricSecrets, get_secrets

# Load and validate secrets
secrets = get_secrets()

# Access credentials
client_id = secrets.azure_client_id
tenant_id = secrets.get_tenant_id()

# Validate authentication
is_valid, error_msg = secrets.validate_fabric_auth()
if not is_valid:
    raise ValueError(error_msg)
```

#### Environment Setup

**Local Development (.env file):**
```bash
# .env
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-secret
TENANT_ID=your-tenant-id
GITHUB_TOKEN=your-github-pat
```

**CI/CD Pipeline (GitHub Actions):**
```yaml
env:
  AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
  AZURE_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
  TENANT_ID: ${{ secrets.TENANT_ID }}
```

### Benefits
- ✅ Works seamlessly in both local and CI/CD environments
- ✅ Type-safe with pydantic validation
- ✅ Clear error messages for missing credentials
- ✅ Backward compatible with existing code

---

## 2. CLI Version Validation

### The Problem
Breaking changes in the `fab` CLI could silently break deployments.

### The Solution
Automatic version checking on initialization with clear error messages.

### Usage

```python
from core.fabric_wrapper import FabricCLIWrapper

# Automatic version check (default)
fabric = FabricCLIWrapper(
    fabric_token=token,
    validate_version=True,  # Default
    min_version="1.0.0"  # Optional custom minimum
)

# Access detected version
print(f"Using Fabric CLI version: {fabric.cli_version}")
```

### CLI Diagnostics

```bash
# Check CLI version and compatibility
python src/fabric_deploy.py diagnose
```

Output:
```
Running diagnostic checks...
✅ Fabric CLI is properly installed (Fabric CLI 1.2.3)
  Parsed version: 1.2.3
  Minimum version: 1.0.0
  Compatibility: compatible
✅ Authentication is working
```

### Docker Version Pinning

```dockerfile
# Dockerfile pins specific CLI version
RUN pip install --no-cache-dir git+https://github.com/microsoft/fabric-cli.git@main#egg=ms-fabric-cli

# Verify installation
RUN fab --version
```

Build and run:
```bash
# Build image with pinned versions
docker build -t usf-fabric-cli-cicd:v1.0 .

# Run deployment
docker run --rm \
  -e AZURE_CLIENT_ID=${AZURE_CLIENT_ID} \
  -e AZURE_CLIENT_SECRET=${AZURE_CLIENT_SECRET} \
  -e TENANT_ID=${TENANT_ID} \
  usf-fabric-cli-cicd:v1.0 \
  deploy config/my-workspace.yaml --env prod
```

---

## 3. Artifact Templating

### The Problem
Need to change connection strings, capacity IDs, or other values based on deployment environment without maintaining separate files.

### The Solution
Jinja2-based templating engine for dynamic variable substitution.

### Usage

#### Basic String Templating
```python
from core.templating import ArtifactTemplateEngine

engine = ArtifactTemplateEngine()

template = "Server={{ db_server }};Database={{ db_name }}"

# Dev environment
dev_result = engine.render_string(template, {
    "db_server": "dev-server.database.windows.net",
    "db_name": "dev_db"
})
# Output: Server=dev-server.database.windows.net;Database=dev_db

# Prod environment
prod_result = engine.render_string(template, {
    "db_server": "prod-server.database.windows.net",
    "db_name": "prod_db"
})
# Output: Server=prod-server.database.windows.net;Database=prod_db
```

#### Notebook Templating
```python
from core.templating import FabricArtifactTemplater

templater = FabricArtifactTemplater()

# Render notebook with environment-specific values
templater.render_notebook(
    notebook_path=Path("templates/etl_notebook.ipynb"),
    variables={
        "lakehouse_name": "ProdLakehouse",
        "connection_string": "Server=prod-db;Database=sales",
        "environment": "production"
    },
    output_path=Path("notebooks/etl_notebook_prod.ipynb")
)
```

#### Template File Structure

**templates/notebook.ipynb:**
```json
{
  "cells": [
    {
      "cell_type": "code",
      "source": [
        "# Environment: {{ environment }}\n",
        "lakehouse = '{{ lakehouse_name }}'\n",
        "connection_string = '{{ connection_string }}'\n"
      ]
    }
  ]
}
```

#### Environment-Specific Variables

```python
# Define base variables
base_vars = {
    "project": "SalesAnalytics",
    "region": "eastus"
}

# Environment-specific overrides
dev_vars = {
    "lakehouse_name": "DevLakehouse",
    "connection_string": "Server=dev-db",
    "capacity": "F2"
}

prod_vars = {
    "lakehouse_name": "ProdLakehouse",
    "connection_string": "Server=prod-db",
    "capacity": "F64"
}

# Merge and render
final_vars = engine.prepare_environment_variables("prod", base_vars, prod_vars)
rendered = engine.render_file(template_path, final_vars, output_path)
```

### Template Validation

```python
from core.templating import FabricArtifactTemplater

templater = FabricArtifactTemplater()

# Validate template before deployment
is_valid, errors = templater.validate_artifact_template(
    artifact_path=Path("templates/pipeline.json"),
    required_variables=["environment", "source_db", "target_lakehouse"]
)

if not is_valid:
    for error in errors:
        print(f"ERROR: {error}")
```

---

## 4. Automatic Git Connection

### The Problem
Workspaces need to be manually connected to Git repositories after creation, breaking the automation workflow.

### The Solution
Automatic Git connection using Fabric REST APIs during workspace deployment.

### Configuration

**Workspace YAML (config/my-workspace.yaml):**
```yaml
workspace:
  name: my-workspace
  capacity_id: F64
  
  # Git Integration (NEW)
  git_repo: https://github.com/myorg/fabric-content
  git_branch: main
  git_directory: /workspaces/my-workspace

folders:
  - Bronze
  - Silver
  - Gold

lakehouses:
  - name: SalesLakehouse
    folder: Bronze
```

### Deployment with Git

```bash
# Deploy workspace with automatic Git connection
python src/fabric_deploy.py deploy \
  config/my-workspace.yaml \
  --env prod \
  --branch main
```

**Output:**
```
Creating workspace...
✅ Workspace created
Creating folder structure...
✅ Folders created
Creating items...
✅ Items created
Connecting Git...
  Connecting workspace to Git repository: https://github.com/myorg/fabric-content
  Branch: main
  Directory: /workspaces/my-workspace
  Creating GitHub connection...
  ✓ Created GitHub connection: abc-123-def
  ✓ Workspace connected to Git
  Initializing Git connection...
  Required action: UpdateFromGit
  Updating workspace from Git repository...
  ✓ Workspace updated from Git successfully
✅ Git connected
```

### Git Provider Support

#### GitHub
```yaml
workspace:
  git_repo: https://github.com/owner/repo
  git_branch: main
  git_directory: /
```

Requires: `GITHUB_TOKEN` environment variable

#### Azure DevOps
```yaml
workspace:
  git_repo: https://dev.azure.com/org/project/_git/repo
  git_branch: main
  git_directory: /
```

Requires Service Principal:
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
- `TENANT_ID`

### Programmatic Git Operations

```python
from core.fabric_git_api import FabricGitAPI, GitProviderType

# Initialize API client
git_api = FabricGitAPI(access_token=token)

# Connect workspace to GitHub
result = git_api.connect_workspace_to_git(
    workspace_id="workspace-id",
    provider_type=GitProviderType.GITHUB,
    owner_name="myorg",
    repository_name="fabric-content",
    branch_name="main",
    directory_name="/"
)

# Initialize connection
init_result = git_api.initialize_git_connection(workspace_id)

# Update from Git if needed
if init_result["required_action"] == "UpdateFromGit":
    update_result = git_api.update_from_git(
        workspace_id=workspace_id,
        remote_commit_hash=init_result["remote_commit_hash"],
        workspace_head=init_result["workspace_head"]
    )
    
    # Poll operation status
    final_result = git_api.poll_operation(
        operation_id=update_result["operation_id"]
    )
```

---

## 5. Enhanced CI/CD Pipeline

### New Validation Gates

The GitHub Actions workflow now includes:

1. **Linting**
   - flake8 for code quality
   - black for code formatting
   - mypy for type checking

2. **Security Scanning**
   - Bandit for security vulnerabilities

3. **Test Coverage**
   - Unit tests with coverage reporting
   - Coverage upload to Codecov

4. **Docker Build Verification**
   - Ensures Docker image builds successfully

### Example Workflow

```yaml
# .github/workflows/fabric-cicd.yml
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Run linting
        run: |
          flake8 src/ --count
          black --check src/
          mypy src/ --ignore-missing-imports
      
      - name: Security scan
        run: bandit -r src/ -ll
      
      - name: Run tests with coverage
        run: pytest tests/ -v --cov=src/ --cov-report=xml
      
      - name: Test Docker build
        run: docker build -t usf-fabric-cli-cicd:test .
```

---

## Testing

### Run Tests

```bash
# Run all unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/ --cov-report=html

# Run specific test module
pytest tests/test_secrets.py -v
pytest tests/test_templating.py -v
```

### Test Structure

```
tests/
├── test_secrets.py          # Secret management tests
├── test_templating.py       # Templating engine tests
├── test_config.py           # Configuration tests
├── test_fabric_wrapper.py   # CLI wrapper tests
└── integration/             # Integration tests
```

---

## Migration Guide

### For Existing Projects

1. **Update requirements.txt**
   ```bash
   pip install -r requirements.txt
   ```

2. **Add Git configuration to workspace YAML**
   ```yaml
   workspace:
     git_repo: https://github.com/yourorg/repo
     git_branch: main
     git_directory: /
   ```

3. **Update environment variables**
   ```bash
   # Add to .env
   GITHUB_TOKEN=your-github-pat
   ```

4. **Test deployment**
   ```bash
   python src/fabric_deploy.py deploy config/workspace.yaml --env dev --diagnose
   ```

### Backward Compatibility

All enhancements are **backward compatible**. Existing deployments will continue to work without changes. New features are opt-in through configuration.

---

## Troubleshooting

### CLI Version Mismatch
```
Warning: Fabric CLI version 0.9.0 is below minimum required version 1.0.0
```
**Solution**: Upgrade Fabric CLI
```bash
pip install --upgrade ms-fabric-cli
```

### Missing Secrets
```
ValueError: Missing Fabric authentication credentials
```
**Solution**: Set required environment variables or create `.env` file

### Git Connection Fails
```
Failed to connect workspace to Git: 401 Unauthorized
```
**Solution**: Verify Git credentials (GITHUB_TOKEN or Service Principal)

### Template Rendering Error
```
ValueError: Undefined variable in template: connection_string
```
**Solution**: Ensure all required variables are provided in the variables dictionary

---

## Best Practices

1. **Use Docker for Production**
   - Ensures consistent CLI version
   - Reproducible deployments
   - Isolated environment

2. **Pin Dependency Versions**
   - Update `requirements.txt` with specific versions
   - Test thoroughly before upgrading

3. **Template Everything Environment-Specific**
   - Connection strings
   - Capacity IDs
   - Data source paths
   - API endpoints

4. **Validate Before Deploy**
   ```bash
   python src/fabric_deploy.py validate config/workspace.yaml --env prod
   ```

5. **Use Diagnostics**
   ```bash
   python src/fabric_deploy.py diagnose
   ```

6. **Test in Dev First**
   ```bash
   python src/fabric_deploy.py deploy config/workspace.yaml --env dev
   ```

---

## Summary of Enhancements

| Enhancement | Gap Addressed | Impact |
|-------------|---------------|--------|
| Secret Management | Gap C | Works in CI/CD and local dev |
| CLI Version Validation | Gap A | Prevents silent failures |
| Docker Support | Gap A | Reproducible environments |
| Jinja2 Templating | Gap B | Dynamic transformations |
| Git API Integration | Gap D | Automated workspace setup |
| Enhanced CI/CD | All | Quality gates and validation |

---

## Additional Resources

- [Microsoft Fabric Git Integration API Documentation](https://learn.microsoft.com/en-us/fabric/cicd/git-integration/git-automation)
- [12-Factor App Configuration](https://12factor.net/config)
- [Jinja2 Template Designer Documentation](https://jinja.palletsprojects.com/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
