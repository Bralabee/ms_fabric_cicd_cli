# Troubleshooting Guide

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
python scripts/admin/utilities/debug_ado_access.py --organization your-org --project your-project
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
ls templates/blueprints/
# Copy a working template
cp templates/blueprints/basic_etl.yaml config/projects/myorg/myproject.yaml
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
python scripts/admin/utilities/debug_ado_access.py \
  --organization your-org \
  --project your-project \
  --repository your-repo
```

1. **Initialize repository first**:

```bash
python scripts/admin/utilities/init_ado_repo.py \
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
python scripts/admin/utilities/list_workspaces.py
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
   python scripts/admin/preflight_check.py
   ```

4. **Check Related Projects**:
   - `usf-fabric-cicd` - Original monolithic framework
   - `usf_fabric_monitoring` - Monitor Hub analysis
   - `fabric-purview-playbook-webapp` - Delivery playbook
