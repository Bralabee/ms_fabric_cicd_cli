# External Integrations

**Analysis Date:** 2026-02-26

## APIs & External Services

**Microsoft Fabric Platform:**
- Fabric REST API v1 - `https://api.fabric.microsoft.com/v1`
  - SDK/Client: `ms-fabric-cli>=v1.3.1` (GitHub: microsoft/fabric-cli)
  - Auth: FABRIC_TOKEN or Azure Service Principal (AZURE_CLIENT_ID + AZURE_CLIENT_SECRET)
  - Purpose: Workspace creation, deployment, item management, git integration
  - Implementation: `src/usf_fabric_cli/services/fabric_wrapper.py`, `src/usf_fabric_cli/services/fabric_api_base.py`

**Microsoft Fabric Git APIs:**
- Workspace-to-Git connection automation
  - Base: `https://api.fabric.microsoft.com/v1`
  - Client: `src/usf_fabric_cli/services/fabric_git_api.py`
  - Auth: Bearer token from FABRIC_TOKEN or Azure Service Principal
  - Purpose: Connect workspaces to GitHub/Azure DevOps repos, manage git connections
  - Features: Support for GitHub and Azure DevOps providers, auto-retry with exponential backoff

**Microsoft Fabric Deployment Pipeline APIs:**
- Promotion through deployment pipeline stages
  - Client: `src/usf_fabric_cli/services/deployment_pipeline.py`
  - Auth: Bearer token
  - Purpose: Move items between Dev/Test/Prod stages, manage promotion workflows

**GitHub API:**
- REST API v3 at `https://api.github.com`
  - SDK/Client: `requests>=2.31.0` (direct HTTP)
  - Auth: GITHUB_TOKEN (Personal Access Token with `repo` scope)
  - Purpose: Create and initialize GitHub repositories
  - Implementation: `src/usf_fabric_cli/scripts/admin/utilities/init_github_repo.py`
  - Endpoints: POST `/user/repos` (create repo), POST `/repos/{owner}/{repo}` (initialize)

**Azure DevOps API:**
- REST API at `https://dev.azure.com/{org}/_apis/`
  - SDK/Client: `requests>=2.31.0` (direct HTTP with Basic auth)
  - Auth: AZURE_DEVOPS_PAT (Personal Access Token)
  - Purpose: Create and initialize Azure DevOps repositories
  - Implementation: `src/usf_fabric_cli/scripts/admin/utilities/init_ado_repo.py`

## Data Storage

**Local File System:**
- Configuration files: `config/projects/[org]/[project].yaml`
- Blueprint templates: `src/usf_fabric_cli/templates/blueprints/*.yaml`
- Schemas: `src/usf_fabric_cli/schemas/*.json`
- Generated projects stored in `config/` directory structure

**Azure Blob Storage (Optional):**
- Package: `azure-storage-blob>=12.19.0`
- Purpose: Long-term backup or artifact storage (optional integration)
- Auth: Azure Service Principal credentials

## Caching

**In-Memory Token Cache:**
- Token Manager maintains session-scoped token cache
- Class: `src/usf_fabric_cli/services/token_manager.py`
- Behavior: Proactive refresh 60 seconds before expiry
- No persistent cache across CLI invocations

**No External Caching Service:**
- Redis, Memcached, or other caching layers not integrated

## Authentication & Identity

**Azure Service Principal Authentication:**
- Provider: Azure AD
- Implementation: `src/usf_fabric_cli/utils/secrets.py`
- Method: `ClientSecretCredential` from `azure-identity>=1.15.0`
- Environment Variables:
  - `AZURE_CLIENT_ID` - Service Principal app ID
  - `AZURE_CLIENT_SECRET` - Service Principal secret
  - `AZURE_TENANT_ID` or `TENANT_ID` - Azure AD tenant ID
- Scope: `https://api.fabric.microsoft.com/.default` for Fabric API access

**Direct Token Authentication:**
- Alternative method using pre-acquired access token
- Environment Variable: `FABRIC_TOKEN`
- Use case: CI/CD pipelines where token is managed externally

**Azure Key Vault Integration (Optional):**
- Package: `azure-keyvault-secrets>=4.7.0`
- Purpose: Centralized secrets management
- Environment Variable: `AZURE_KEYVAULT_URL` (e.g., `https://{vault-name}.vault.azure.net`)
- Fallback Priority: ENV vars → .env file → Key Vault
- Implementation: `src/usf_fabric_cli/utils/secrets.py` method `_get_from_keyvault()`

**GitHub Personal Access Token:**
- Environment Variable: `GITHUB_TOKEN`
- Scope Required: `repo` (full repository access)
- Use case: Repository creation and initialization

**Azure DevOps Personal Access Token:**
- Environment Variable: `AZURE_DEVOPS_PAT`
- Scope Required: Code (full) and Project & Team (read/write)
- Use case: ADO repository creation and initialization

## Monitoring & Observability

**Logging:**
- Framework: Python's built-in `logging` module
- Implementation: `src/usf_fabric_cli/utils/audit.py` for audit logging
- Configuration: INFO level for normal operations, DEBUG available for troubleshooting
- Output: Console via `rich>=13.0.0` for formatted output

**Error Tracking:**
- No SaaS error tracking service (Sentry, Rollbar) integrated
- Errors logged locally and reported to console

**Telemetry (Fabric CLI):**
- Optional: Fabric CLI telemetry can be disabled
- Environment Variable: `DISABLE_FABRIC_TELEMETRY=1`
- Max log size: Configurable via `FABRIC_TELEMETRY_MAX_MB` (default: 50 MB)

## CI/CD & Deployment

**Hosting:**
- GitHub-based: Repository hosted on GitHub (for usf_fabric_cli_cicd)
- Docker Hub: Docker image pushed to registry (implied by Docker targets)
- Package Index: PyPI (wheel distribution)

**CI Pipeline:**
- Platform: GitHub Actions
- Workflow: `.github/workflows/ci.yml`
- Triggers: Push to `main` branch, Pull Request to `main`
- Steps:
  1. Checkout code
  2. Setup Python 3.11 with pip caching
  3. Install dependencies from `requirements-dev.txt`
  4. Lint with flake8, black, isort
  5. Type check with mypy (soft gate)
  6. Security scan with bandit
  7. Validate blueprint configs
  8. Run unit tests with coverage
  9. Upload coverage to CodeCov (optional)
  10. Build wheel distribution
  11. Smoke test installed wheel
  12. Test Docker build

**Deployment Orchestration:**
- Makefile targets for local and Docker-based deployments
- Targets: `deploy`, `promote`, `onboard`, `destroy`, `bulk-destroy`
- All operations can run locally (`make deploy`) or via Docker (`make docker-deploy`)

## Environment Configuration

**Required Environment Variables:**
- `AZURE_CLIENT_ID` - Azure AD Service Principal ID
- `AZURE_CLIENT_SECRET` - Service Principal secret (or use FABRIC_TOKEN instead)
- `AZURE_TENANT_ID` (or `TENANT_ID`) - Azure AD tenant
- `GITHUB_TOKEN` - For GitHub repo initialization (repo scope)
- `AZURE_DEVOPS_PAT` - For Azure DevOps repo initialization

**Optional Environment Variables:**
- `FABRIC_TOKEN` - Pre-acquired Fabric API token (alternative to Service Principal)
- `AZURE_KEYVAULT_URL` - Azure Key Vault URL for secrets management
- `FABRIC_CAPACITY_ID` - Default Fabric capacity for workspaces
- `FABRIC_PIPELINE_NAME` - Default deployment pipeline name
- `DISABLE_FABRIC_TELEMETRY` - Set to `1` to disable Fabric CLI telemetry

**Secrets Location:**
- Development: `.env` file (loaded via `python-dotenv`)
- Docker: Environment passed via `--env-file` flag or inline `-e VAR=value`
- CI/CD: GitHub Actions secrets (configured in repo settings)
- Production: Azure Key Vault (via AZURE_KEYVAULT_URL if configured)

## Webhooks & Callbacks

**Incoming Webhooks:**
- Not currently implemented
- CLI is stateless and pull-based

**Outgoing Webhooks:**
- No webhook dispatching to external systems
- Notifications via console output only

**Git Push Integration:**
- When deploying with `--branch` flag, code is pushed to Git repository
- Implementation: `src/usf_fabric_cli/services/git_integration.py`
- Purpose: Enable branch-based isolated feature workspaces

## Rate Limiting & Throttling

**Fabric API:**
- Auto-retry with exponential backoff (base delay: 0.1s, max delay: 30s)
- Default max retries: 3 attempts
- Implementation: `src/usf_fabric_cli/utils/retry.py`
- Handles transient failures (429 Too Many Requests, 503 Service Unavailable, etc.)

**GitHub API:**
- Rate limit: 60 requests/hour (unauthenticated) or 5,000/hour (authenticated with PAT)
- No custom throttling; relies on GitHub's standard limits

**Azure DevOps API:**
- No explicit rate limiting documented
- Standard Azure throttling applies

## API Authentication Patterns

**Bearer Token Pattern (Fabric APIs):**
```python
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}
requests.get("https://api.fabric.microsoft.com/v1/workspaces", headers=headers)
```

**Basic Auth Pattern (GitHub, Azure DevOps):**
```python
auth = (username, token)  # For GitHub: use "x-access-token" as username
requests.post("https://api.github.com/user/repos", auth=auth, json=...)
```

**Service Principal Flow:**
```
1. ClientSecretCredential.get_token(scope)
2. Returns AccessToken with expiry
3. TokenManager refreshes proactively 60s before expiry
4. Token injected into Fabric API bearer headers
```

---

*Integration audit: 2026-02-26*
