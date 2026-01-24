> [!WARNING]
> **📜 HISTORICAL ARCHIVE - DO NOT USE FOR CURRENT DEVELOPMENT**
>
> This document is preserved for historical reference only. Code examples and import paths shown here reflect the **legacy `core.*` module structure** which was replaced with `usf_fabric_cli.*` in v1.4.0 (January 2026).
>
> **For current documentation, see:** [User Guides](../01_User_Guides/)

---

# Azure Key Vault Integration Guide

## Overview

The `usf-fabric-cli-cicd` project now supports Azure Key Vault as an optional secret management backend. This feature enables production-grade secret storage without breaking existing environment variable or `.env` file workflows.

## Architecture

### Priority Hierarchy (Waterfall)

The secrets module follows this fallback chain:

1. **Environment Variables** (Highest Priority)
   - System environment variables
   - Explicit `export` commands
   - CI/CD pipeline secrets

2. **`.env` File**
   - Local development
   - Automatically loaded by `python-dotenv`

3. **Azure Key Vault** (Production)
   - Only consulted if `AZURE_KEYVAULT_URL` is set
   - Uses `DefaultAzureCredential` for authentication
   - Gracefully falls back if secrets not found

4. **Error** (Lowest Priority)
   - Raises `ValueError` if required credentials are missing

### Key Features

- **Zero Breaking Changes**: Existing deployments continue to work without modification
- **Opt-In**: Key Vault is only used when explicitly configured
- **Graceful Degradation**: If Key Vault SDK is not installed, system falls back to environment variables
- **Managed Identity Support**: Uses `DefaultAzureCredential` (supports Managed Identity, Azure CLI, etc.)

---

## Setup Guide

### 1. Install Dependencies

The Key Vault SDK is already included in `requirements.txt`:

```bash
# If not already installed
conda activate fabric-cli-cicd
pip install -r requirements.txt
```

### 2. Create Azure Key Vault

```bash
# Azure CLI commands
az keyvault create \
  --name "your-fabric-vault" \
  --resource-group "your-rg" \
  --location "eastus"

# Grant yourself access (for local development)
az keyvault set-policy \
  --name "your-fabric-vault" \
  --upn "your-email@domain.com" \
  --secret-permissions get list
```

### 3. Store Secrets in Key Vault

Secret names in Key Vault use hyphens (e.g., `azure-client-id`), while environment variables use underscores (e.g., `AZURE_CLIENT_ID`). The system automatically handles this conversion.

```bash
# Store Service Principal credentials
az keyvault secret set --vault-name "your-fabric-vault" \
  --name "azure-client-id" --value "00000000-0000-0000-0000-000000000000"

az keyvault secret set --vault-name "your-fabric-vault" \
  --name "azure-client-secret" --value "your-secret-value"

az keyvault secret set --vault-name "your-fabric-vault" \
  --name "tenant-id" --value "00000000-0000-0000-0000-000000000000"

# Store Git credentials
az keyvault secret set --vault-name "your-fabric-vault" \
  --name "github-token" --value "ghp_xxxxxxxxxxxx"
```

### 4. Configure Environment

Add the Key Vault URL to your `.env` file:

```bash
# .env
AZURE_KEYVAULT_URL=https://your-fabric-vault.vault.azure.net/
```

**That's it!** The system will automatically pull secrets from Key Vault if they're not found in the environment.

---

## Usage Examples

### Local Development (Azure CLI Authentication)

```bash
# Login with Azure CLI
az login

# Set Key Vault URL
export AZURE_KEYVAULT_URL=https://your-fabric-vault.vault.azure.net/

# Run deployment (secrets pulled from Key Vault automatically)
make deploy config=config/projects/finance_project.yaml env=dev
```

### Production (Managed Identity)

When running in Azure (e.g., Azure Container Apps, Azure Functions, or VMs with Managed Identity):

1. **Assign Managed Identity** to your Azure resource
2. **Grant Key Vault Access** to the Managed Identity:
   ```bash
   az keyvault set-policy \
     --name "your-fabric-vault" \
     --object-id "<managed-identity-object-id>" \
     --secret-permissions get list
   ```
3. **Set Environment Variable**:
   ```bash
   AZURE_KEYVAULT_URL=https://your-fabric-vault.vault.azure.net/
   ```

The `DefaultAzureCredential` will automatically use the Managed Identity—**no client secrets needed!**

### Hybrid Configuration

You can mix environment variables and Key Vault:

```bash
# .env
AZURE_KEYVAULT_URL=https://your-fabric-vault.vault.azure.net/
FABRIC_TOKEN=override-token-from-env  # This takes priority over Key Vault
```

**Result**: `FABRIC_TOKEN` comes from the environment, but `AZURE_CLIENT_ID` and other missing secrets are pulled from Key Vault.

---

## Code Examples

### Basic Usage

```python
from src.core.secrets import FabricSecrets

# Load secrets (automatically checks Key Vault if configured)
secrets = FabricSecrets.load_with_fallback()

# Access credentials
print(secrets.azure_client_id)  # Comes from env or Key Vault
print(secrets.tenant_id)
```

### Explicit Secret Retrieval

```python
from src.core.secrets import FabricSecrets

secrets = FabricSecrets()

# Get a specific secret with Key Vault fallback
api_key = secrets.get_secret("FABRIC_API_KEY", keyvault_name="fabric-api-key")

# Returns:
# 1. Environment variable FABRIC_API_KEY (if set)
# 2. Key Vault secret "fabric-api-key" (if AZURE_KEYVAULT_URL is set)
# 3. None (if not found)
```

### AI Agent Integration

```python
from langchain.agents import tool

@tool
def deploy_fabric_workspace(org_name: str, project_name: str, env: str = "dev"):
    """
    Deploys a Fabric workspace. Credentials are loaded from Key Vault (production)
    or environment variables (development) automatically.
    """
    from src.core.secrets import FabricSecrets
    
    # Security: The Agent never sees the credentials
    secrets = FabricSecrets.load_with_fallback()
    
    # Validate authentication
    is_valid, error_msg = secrets.validate_fabric_auth()
    if not is_valid:
        return f"❌ Authentication failed: {error_msg}"
    
    # Proceed with deployment (credentials loaded internally)
    # ...
```

---

## Troubleshooting

### Key Vault SDK Not Available

**Symptom**: Secrets are not loaded from Key Vault even though `AZURE_KEYVAULT_URL` is set.

**Cause**: `azure-keyvault-secrets` package is not installed.

**Solution**:
```bash
pip install azure-keyvault-secrets
```

### Authentication Errors

**Symptom**: `Azure.Identity.CredentialUnavailableException` or similar.

**Cause**: No valid authentication method available for `DefaultAzureCredential`.

**Solution**:
- **Local Dev**: Run `az login` before executing the script
- **Production**: Ensure Managed Identity is assigned and has Key Vault access

### Secret Not Found in Key Vault

**Symptom**: Deployment fails with "Missing authentication credentials."

**Cause**: Secret exists in environment but not in Key Vault (or vice versa).

**Solution**: Remember the priority order:
1. Check environment variables first (`echo $AZURE_CLIENT_ID`)
2. Check `.env` file
3. Verify Key Vault secret exists (`az keyvault secret show --vault-name ... --name ...`)

---

## Security Best Practices

### Development

```bash
# Use Azure CLI authentication (no secrets in .env)
az login
export AZURE_KEYVAULT_URL=https://dev-vault.vault.azure.net/
```

### Staging/Production

```bash
# Use Managed Identity (zero secrets in code or environment)
export AZURE_KEYVAULT_URL=https://prod-vault.vault.azure.net/
```

### Never Commit

- ❌ `.env` files with real credentials
- ❌ Key Vault URLs with embedded access tokens
- ✅ `.env.template` with placeholder values

---

## Migration Path

### Step 1: Test Locally
```bash
# Keep existing .env file
# Add Key Vault URL
echo "AZURE_KEYVAULT_URL=https://your-vault.vault.azure.net/" >> .env

# Run deployment (should work identically)
make deploy config=...
```

### Step 2: Gradually Move Secrets
```bash
# Move one secret at a time to Key Vault
az keyvault secret set --vault-name "your-vault" \
  --name "azure-client-id" --value "$AZURE_CLIENT_ID"

# Remove from .env
# Test deployment (should still work)
```

### Step 3: Production Deployment
```bash
# In production environment:
# 1. Assign Managed Identity
# 2. Set AZURE_KEYVAULT_URL only
# 3. Remove all secrets from environment variables
```

---

## Summary

| Feature | Before | After |
|---------|--------|-------|
| **Secret Storage** | `.env` file only | `.env` **or** Key Vault |
| **Production Security** | Secrets in environment | Secrets in Key Vault |
| **Authentication** | Client Secret | Managed Identity |
| **Breaking Changes** | N/A | **Zero** |

Azure Key Vault support is now fully integrated into the `usf-fabric-cli-cicd` project, providing enterprise-grade secret management without disrupting existing workflows.
