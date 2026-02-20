# Troubleshooting Guide

> **Audience**: All users | **Deployment Path**: All | **Difficulty**: Varies per issue
> **See also**: [CLI Reference](CLI_REFERENCE.md) for command flags & exit codes | [Consumer repo troubleshooting](https://github.com/<org>/edp_fabric_consumer_repo/blob/main/EDPFabric/docs/02_REPLICATION_GUIDE.md#11-troubleshooting) for CI/CD-specific issues

## Common Issues and Solutions

### 1. Makefile Commands Fail with "Syntax error: Unterminated quoted string"

**Symptom**:

```bash
make validate config=config/projects/test/project.yaml
# Error: Syntax error: Unterminated quoted string
```

**Cause**: Path contains special characters (apostrophes, spaces) causing shell escaping issues.

**Solution**: ✅ **FIXED in v1.1.0**

The Makefile now properly quotes the PYTHONPATH variable. Update to the latest version:

```bash
git pull
make install
```

**Alternative**: Use direct Python command:

```bash
python -m usf_fabric_cli.cli validate config/projects/test/project.yaml
```

---

### 2. `fabric-cicd` Command Not Found

**Symptom**:

```bash
fabric-cicd --help
# fabric-cicd: command not found
```

**Cause**: Package not installed in editable mode, entry point not registered.

**Solution**: ✅ **FIXED in v1.1.0**

Run the install command which now includes entry point registration:

```bash
conda activate fabric-cli-cicd
make install
# OR
pip install -e .
```

**Verify Installation**:

```bash
fabric-cicd --help
# Should show CLI help
```

**Alternative**: Use Python module syntax:

```bash
python -m usf_fabric_cli.cli --help
```

---

### 3. Wrong Conda Environment Active

**Symptom**:

```bash
# Import errors or package not found errors
ModuleNotFoundError: No module named 'typer'
```

**Cause**: Running commands in base or wrong conda environment.

**Solution**:

```bash
# Check current environment
conda env list
# Look for * next to fabric-cli-cicd

# Activate correct environment
conda activate fabric-cli-cicd

# Verify
python -c "import typer; print('OK')"
```

---

### 4. Authentication Failures

**Symptom**:

```bash
fabric-cicd deploy config.yaml --env dev
# Error: Missing credentials
```

**Cause**: Missing or invalid credentials in environment.

**Solution**:

1. **Check .env file exists**:

```bash
ls -la .env
# Should show .env file
```

1. **Verify required variables**:

```bash
python -c "from usf_fabric_cli.utils.secrets import FabricSecrets; secrets = FabricSecrets.load_with_fallback(); print(secrets.validate_fabric_auth())"
# Should return (True, 'OK')
```

1. **Check specific credentials**:

```bash
# Don't print actual values!
python -c "import os; print('AZURE_CLIENT_ID:', 'SET' if os.getenv('AZURE_CLIENT_ID') else 'MISSING')"
python -c "import os; print('AZURE_CLIENT_SECRET:', 'SET' if os.getenv('AZURE_CLIENT_SECRET') else 'MISSING')"
python -c "import os; print('AZURE_TENANT_ID:', 'SET' if os.getenv('AZURE_TENANT_ID') else 'MISSING')"
```

1. **Copy template and edit**:

```bash
cp .env.template .env
nano .env  # Edit with your credentials
```

---

### 5. Windows Path & Module Errors

**Symptom**:

```bash
ModuleNotFoundError: No module named 'usf_fabric_cli'
```

**Cause**: Running commands from inside the `src/` directory or `PYTHONPATH` not set.

**Solution**:
Always run commands from the **project root** directory:

```powershell
# WRONG
cd src
python -m usf_fabric_cli.cli ...

# CORRECT
cd C:\path\to\usf_fabric_cli_cicd
python -m usf_fabric_cli.cli ...
```

---

### 6. Managing Large Lists of Principals

**Scenario**: You need to add 50+ users or groups to a workspace managed by a single environment variable.

**Solution**:
The `id` field in `principals` supports comma-separated values.

**In .env file**:

```ini
DATA_ENGINEERS_GROUP="guid1,guid2,guid3,guid4,..."
```

**In config YAML**:

```yaml
principals:
  - id: "${DATA_ENGINEERS_GROUP}"
    role: "Contributor"
```

The CLI will automatically parse this list and add each GUID individually.

---

### 7. Service Principal Permission Issues

**Symptom**:

```bash
# Deployment fails with 403 Forbidden or access denied
```

**Cause**: Service Principal lacks required permissions.

**Solution**:

**For Fabric Workspace Deployments**:

1. Service Principal needs **Admin** role in workspace (add in config YAML `principals` section)
2. Enable in Fabric Admin Portal → Tenant Settings:
   - ✅ "Service principals can use Fabric APIs"
   - ✅ "Service principals can create workspaces"

**For Azure DevOps Git Integration**:

1. **Basic** access level in ADO Organization Settings → Users
2. **Contributor** role in ADO project
3. Repository **Contribute** permissions

**Verify Permissions**:

```bash
python -m usf_fabric_cli.scripts.admin.utilities.debug_ado_access --organization your-org --project your-project
```

---

### 8. Docker Build Failures

**Symptom**:

```bash
make docker-build
# Error during build
```

**Cause**: Various (network, disk space, Docker daemon).

**Solutions**:

1. **Check Docker daemon**:

```bash
docker ps
# Should list running containers
```

1. **Clean up space**:

```bash
docker system prune -a
```

1. **Build with verbose output**:

```bash
docker build -t fabric-cli-cicd . --progress=plain
```

1. **Check Fabric CLI installation in container**:

```bash
docker run --rm fabric-cli-cicd fab --version
# Should show Fabric CLI version
```

---

### 9. Configuration Validation Errors

**Symptom**:

```bash
fabric-cicd validate config.yaml
# Error: Configuration validation failed
```

**Cause**: Invalid YAML syntax or missing required fields.

**Solution**:

1. **Check YAML syntax**:

```bash
python -c "import yaml; yaml.safe_load(open('config.yaml'))"
# Should not raise errors
```

1. **Verify against schema**:

```bash
fabric-cicd validate config.yaml
# Read error messages carefully
```

1. **Check environment variable substitution**:

```yaml
# In YAML
capacity_id: "${FABRIC_CAPACITY_ID}"

# Verify environment variable is set
echo $FABRIC_CAPACITY_ID
```

1. **Use template as reference**:

```bash
ls src/usf_fabric_cli/templates/blueprints/
# Copy a working template
cp src/usf_fabric_cli/templates/blueprints/basic_etl.yaml config/projects/myorg/myproject.yaml
```

---

### 10. Git Integration Failures

**Symptom**:

```bash
# Git connection or sync fails
Error: Repository not found
```

**Cause**: Incorrect repository URL or missing Git credentials.

**Solution**:

1. **Verify repository URL format**:

```yaml
# Azure DevOps
git_repo: "https://dev.azure.com/org/project/_git/repository"

# GitHub
git_repo: "https://github.com/owner/repository"
```

1. **Check Git credentials**:

```bash
# Azure DevOps
echo $AZURE_DEVOPS_PAT

# GitHub
echo $GITHUB_TOKEN
```

1. **Test repository access**:

```bash
python -m usf_fabric_cli.scripts.admin.utilities.debug_ado_access \
  --organization your-org \
  --project your-project \
  --repository your-repo

# General connection / API debugger
python -m usf_fabric_cli.scripts.admin.utilities.debug_connection
```

1. **Initialize repository first**:

```bash
# GitHub
make init-github-repo git_owner="your-org" repo="new-repo"

# Azure DevOps
python -m usf_fabric_cli.scripts.admin.utilities.init_ado_repo \
  --organization your-org \
  --project your-project \
  --repository new-repo
```

---

### 11. Capacity Issues

**Symptom**:

```bash
# Deployment fails with capacity errors
Error: Insufficient capacity
```

**Cause**: Fabric capacity exhausted or wrong capacity ID.

**Solution**:

1. **Check capacity ID**:

```bash
# Verify capacity ID format (GUID)
echo $FABRIC_CAPACITY_ID
# Should be like: 0749B635-C51B-46C6-948A-02F05D7FE177
```

1. **List existing workspaces on capacity**:

```bash
python -m usf_fabric_cli.scripts.admin.utilities.list_workspaces
# Check how many workspaces exist
```

1. **Try different capacity** (if available):

```yaml
# In config YAML
environments:
  dev:
    workspace:
      capacity_id: "F2"  # Trial capacity
  prod:
    workspace:
      capacity_id: "F64"  # Production capacity
```

---

### 12. Template Rendering Errors

**Symptom**:

```bash
# Deployment fails with template errors
Error: undefined variable 'environment'
```

**Cause**: Missing variables in template context.

**Solution**:

1. **Check available template variables**:
   - `environment`: Current environment (dev/test/prod)
   - `workspace_name`: Workspace display name
   - `capacity_id`: Fabric capacity ID
   - `secrets.*`: Access to secrets (use sparingly)

2. **Use strict mode validation**:

```python
from usf_fabric_cli.utils.templating import ArtifactTemplateEngine

engine = ArtifactTemplateEngine(strict_mode=True)
result = engine.render_string(
    "{{ environment }}_lakehouse",
    {"environment": "dev"}
)
```

1. **Extract required variables**:

```python
from usf_fabric_cli.utils.templating import ArtifactTemplateEngine

engine = ArtifactTemplateEngine()
variables = engine.extract_template_variables("{{ env }}_{{ name }}")
print(variables)  # ['env', 'name']
```

---

### 13. Deployment Pipeline / Promote Failures

**Symptom**:

```bash
fabric-cicd promote --pipeline-name "My Pipeline"
# Error: Pipeline 'My Pipeline' not found
```

**Cause**: Pipeline name is incorrect, or the Service Principal lacks permission to view/manage pipelines.

**Solutions**:

1. **Check pipeline name** (must match display name exactly, including spaces):

```bash
# Verify pipeline exists in Fabric portal
# or use: python -m usf_fabric_cli.scripts.admin.utilities.list_workspaces
```

1. **Check SP permissions**: The Service Principal must have "Admin" permissions to manage Deployment Pipelines. Enable in Fabric Admin Portal → Tenant Settings:
   - ✅ "Service principals can use Fabric APIs"
   - ✅ "Service principals can use deployment pipelines"

1. **Stage assignment fails**:
   - Ensure each workspace is only assigned to one pipeline at a time.
   - Workspace must not already be assigned to another pipeline stage.

1. **Promotion timeout**: Large workspaces may take several minutes. The CLI waits by default (`wait=True`).

---

### 14. Onboarding Failures

**Symptom**:

```bash
make onboard org="My Org" project="My Project"
# Error: Capacity assignment failed
```

**Cause**: Stage-specific capacity IDs are missing or invalid.

**Solutions**:

1. **Set stage-specific capacity IDs** (in `.env`):

```bash
# Default fallback
FABRIC_CAPACITY_ID=your-default-capacity-id

# Stage-specific overrides (optional)
FABRIC_CAPACITY_ID_TEST=your-test-capacity-id
FABRIC_CAPACITY_ID_PROD=your-prod-capacity-id
```

1. **Verify pipeline creation permissions**: Same as troubleshooting item 13 above.

1. **Use --dry-run first** to preview what would happen:

```bash
make onboard org="My Org" project="My Project" dry_run=1
```

---

## Quick Diagnostics Checklist

Run these commands to diagnose common issues:

```bash
# 1. Check environment
conda env list | grep fabric-cli-cicd

# 2. Verify Fabric CLI
fab --version

# 3. Test credentials
python -m usf_fabric_cli.cli diagnose

# 4. Validate configuration
fabric-cicd validate config/projects/your-org/your-project.yaml

# 5. Check entry point
which fabric-cicd

# 6. Run unit tests
make test

# 7. Check Docker
docker run --rm fabric-cli-cicd --help
```

---

### 15. Inline Environments Schema Validation Error

**Symptom**:

```bash
jsonschema.exceptions.ValidationError: Additional properties are not allowed ('environments' was unexpected)
```

**Cause**: CLI version older than v1.7.6. The JSON schema (`workspace_config.json`) did not include `environments` as a valid top-level property, so configs with inline `environments:` blocks failed validation.

**Solution**:

1. **Upgrade to v1.7.6+** (recommended):

```bash
pip install -e .  # In updated usf_fabric_cli_cicd repo
```

2. **Move environments to external files** (workaround for older CLIs):

```bash
# Remove `environments:` block from your project YAML
# Create separate files instead:
# config/environments/dev.yaml
# config/environments/test.yaml
# config/environments/prod.yaml
```

3. **Verify schema supports environments**:

```bash
# Check the schema includes 'environments' property
python -c "import json; s=json.load(open('src/usf_fabric_cli/schemas/workspace_config.json')); print('environments' in s['properties'])"
# Should print: True
```

---

## Getting Help

1. **Check Documentation**:
   - `README.md` - Setup and usage
   - `.github/copilot-instructions.md` - AI agent guide
   - `docs/03_Project_Reports/` - Implementation details

2. **Review Logs**:
   - `audit_logs/fabric_operations_*.jsonl` - Operation logs
   - `audit_logs/fabric_cli_telemetry.jsonl` - CLI telemetry

3. **Run Diagnostics**:

   ```bash
   python -m usf_fabric_cli.scripts.admin.preflight_check
   ```

4. **Check Related Projects**:
   - `usf-fabric-cicd` - Original monolithic framework
   - `usf_fabric_monitoring` - Monitor Hub analysis
   - `fabric-purview-playbook-webapp` - Delivery playbook
