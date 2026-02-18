# From Local to CI/CD: What Changed, Why, and How

> **Audience**: Engineers and stakeholders who used the CLI toolkit successfully on local machines or via Docker and need to understand the fixes required to make it work in automated CI/CD pipelines (GitHub Actions).

---

## Executive Summary

The USF Fabric CLI CI/CD toolkit (v1.5.0 → v1.7.0+) worked perfectly when run **locally** (with `make deploy`) or via **Docker** (`make docker-deploy`). However, when the same code was executed in **GitHub Actions** — a headless, ephemeral Linux runner — a cascade of failures revealed **five categories of hidden assumptions** baked into the codebase.

This document explains each problem, why it only appeared in CI/CD, and how it was fixed.

```
 ┌─────────────────────────────────────────────────────────────┐
 │              THE JOURNEY                                    │
 │                                                             │
 │  v1.5.0  Local ✅  Docker ✅  CI/CD ❌                      │
 │  v1.6.x  Local ✅  Docker ✅  CI/CD ⚠️  (partial)          │
 │  v1.7.0  Local ✅  Docker ✅  CI/CD ⚠️  (closer)           │
 │  v1.7.1  Local ✅  Docker ✅  CI/CD ✅                      │
 └─────────────────────────────────────────────────────────────┘
```

---

## Table of Contents

1. [The Mental Model: Three Execution Contexts](#1-the-mental-model)
2. [Problem 1: Keyring / Encryption Failure](#2-keyring-encryption)
3. [Problem 2: Workspace Name Resolution Race Condition](#3-workspace-name-resolution)
4. [Problem 3: Principal Assignment Silent Failures](#4-principal-assignment)
5. [Problem 4: Phantom Imports and Stale Module Paths](#5-phantom-imports)
6. [Problem 5: Workflow Placement — Library vs Consumer](#6-workflow-placement)
7. [Problem 6: Missing Dev Dependencies in CI](#7-missing-dev-deps)
8. [Bonus: Docker Image Optimisation](#8-docker-optimisation)
9. [Bonus: Deployment Visibility](#9-deployment-visibility)
10. [Architecture Decision: REST API Over CLI](#10-rest-api-decision)
11. [Summary of All Changes](#11-summary)
12. [Lessons Learned](#12-lessons-learned)

---

## 1. The Mental Model: Three Execution Contexts {#1-the-mental-model}

Understanding *why* these bugs existed requires understanding the three environments the code runs in:

| Aspect | Local (`make deploy`) | Docker (`make docker-deploy`) | CI/CD (GitHub Actions) |
|---|---|---|---|
| **Operating system** | Your workstation (Linux/Mac/Win) | Container (Debian slim) | Ubuntu 22.04 runner |
| **Desktop session** | Yes (GUI/keyring available) | No (but often skipped) | **No** (headless) |
| **Filesystem persistence** | Permanent home directory | Ephemeral container | **Ephemeral runner** |
| **Fab CLI state** | Cached from previous runs | Fresh each container start | **Fresh each workflow run** |
| **Network timing** | Single user, low latency | Single user, low latency | **Shared infra, variable latency** |
| **Secret source** | `.env` file | Mounted `.env` file | **GitHub Secrets (env vars)** |

The critical insight: **Locally, you accumulate state** — cached workspace IDs, authenticated CLI sessions, a working keyring. In CI/CD, **every run starts from absolute zero**. There is no desktop session, no prior auth, no cached metadata.

---

## 2. Problem 1: Keyring / Encryption Failure {#2-keyring-encryption}

### What Happened

The Fabric CLI (`fab`) stores authentication tokens encrypted via the OS keyring. On your laptop, this works transparently (GNOME Keyring, macOS Keychain, Windows Credential Manager). On a GitHub Actions runner — a headless Ubuntu VM with no desktop session — there is **no keyring backend**.

Every `fab` command failed with:

```
EncryptionFailed: No recommended backend was available.
```

### Why It Only Showed in CI/CD

Locally, your desktop environment provides a keyring. Docker containers _sometimes_ skip encryption if the CLI detects a non-interactive shell, but GitHub Actions runners have just enough of a TTY simulation to make the CLI _attempt_ encryption and fail.

### How It Was Fixed

Added a pre-auth configuration step in `fabric_wrapper.py` and `token_manager.py`:

```python
# Enable plaintext token fallback for CI/CD environments
# (GitHub Actions runners lack a desktop keyring)
try:
    subprocess.run(
        ["fab", "config", "set", "encryption_fallback_enabled", "true"],
        capture_output=True, check=False
    )
except Exception:
    pass
```

This tells the Fabric CLI: "If you can't encrypt the token, store it in plaintext." This is safe because CI/CD runners are ephemeral — the token is destroyed when the runner VM is recycled after the workflow completes.

**Commit**: `c53a84c` — *fix: enable encryption_fallback for CI/CD environments without keyring*

---

## 3. Problem 2: Workspace Name Resolution Race Condition {#3-workspace-name-resolution}

### What Happened

The deployment flow is:

1. **Create workspace** (via REST API with capacity GUID) → returns workspace ID
2. **Create items** (lakehouse, notebook, pipeline, etc.) inside the workspace
3. **Add principals** (users, service principals, security groups) to the workspace

Step 1 succeeded. Steps 2 and 3 **consistently failed** with:

```
Workspace not found: "acme-sales-dev"
```

### Why It Only Showed in CI/CD

When you create a workspace via the **Fabric REST API** (which the code does when a real capacity GUID is provided), the workspace is registered in Fabric's control plane. But the `fab` CLI resolves workspaces by **name via a different lookup endpoint**. There is a **propagation delay** — the workspace exists in the API but the CLI's name-based lookup hasn't indexed it yet.

Locally, this rarely surfaces because:
- You typically run commands with a slight delay between steps (reviewing output, etc.)
- The workspace may already exist from a previous run
- Local runs may use `fab mkdir` (path-based creation) which doesn't hit this race condition

In CI/CD, everything runs at maximum speed with no human pauses. The workspace is created in step 1, and 200ms later step 2 tries to look it up by name — and fails.

### How It Was Fixed

**Workspace ID Cache** — The core fix introduces an in-memory cache that maps workspace names to their IDs:

```python
class FabricCLIWrapper:
    def __init__(self, ...):
        # Cache workspace name → ID to avoid fab CLI lookup failures
        # after REST API-based workspace creation
        self._workspace_id_cache: Dict[str, str] = {}
```

When a workspace is created, its ID is immediately cached:

```python
def create_workspace(self, name, ...):
    # ... create workspace via REST API ...
    if workspace_id:
        self._workspace_id_cache[name] = workspace_id
    return result
```

All subsequent operations **check the cache first** before falling back to the `fab` CLI lookup:

```python
def get_workspace_id(self, name):
    # Check cache first (populated after REST API-based workspace creation)
    if name in self._workspace_id_cache:
        return self._workspace_id_cache[name]
    # Fallback to fab CLI lookup
    workspace_info = self.get_workspace(name)
    ...
```

**REST API for Item Creation** — Every item creation method (lakehouse, warehouse, notebook, pipeline, semantic model, generic items) was updated to prefer the REST API over `fab mkdir` when a workspace ID is available:

```python
def create_lakehouse(self, workspace_name, name, description=""):
    # Try REST API first (avoids fab CLI path-resolution issues)
    workspace_id = self.get_workspace_id(workspace_name)
    if workspace_id:
        payload = {
            "displayName": name,
            "type": "Lakehouse",
            "description": description,
        }
        command = [
            "api", f"workspaces/{workspace_id}/items",
            "-X", "post", "-i", json.dumps(payload)
        ]
        return self._execute_command(command, check_existence=True)
    # Fallback to fab mkdir
    ...
```

This eliminates the name-resolution dependency entirely for item creation.

**Commit**: `d8c26bc` — *fix: use REST API + workspace ID cache for all operations*

---

## 4. Problem 3: Principal Assignment Silent Failures {#4-principal-assignment}

### What Happened

This was the sneakiest bug. After creating a workspace and items, the code added principals (users and service principals) to the workspace. The deployment **reported success**, but when checking the workspace in the Fabric portal, **no principals had been added**.

There were actually **three nested problems**:

#### Problem 3a: Wrong API Payload Format

The old code used `fab acl set` which was unreliable with REST API-created workspaces. The fix switched to direct REST API calls, but the initial payload format was **wrong**:

```python
# ❌ WRONG — flat format (what was sent)
payload = {
    "identifier": principal_id,
    "principalType": "User",
    "workspaceRole": "Admin"
}

# ✅ CORRECT — nested format (what Fabric API expects)
payload = {
    "principal": {
        "id": principal_id,
        "type": "User"
    },
    "role": "Admin"
}
```

The `fab api` command returned exit code 0 (success) even though the Fabric API returned HTTP 400 (InvalidInput). The CLI silently swallowed the error.

#### Problem 3b: Unknown Principal Type

When adding a service principal to a workspace, the API requires specifying whether the ID represents a `User`, `ServicePrincipal`, or `Group`. The code didn't know which type the principal was. Guessing wrong returned a 400 error.

**Fix**: Try all three types in sequence:

```python
principal_types_to_try = ["User", "ServicePrincipal", "Group"]

for ptype in principal_types_to_try:
    payload = {
        "principal": {"id": principal_id, "type": ptype},
        "role": api_role,
    }
    resp = requests.post(url, headers=headers, json=payload)

    if resp.status_code == 201:
        # Success — this was the right type
        return {"success": True, "data": resp.json()}

    if resp.status_code == 409:
        # Already has a role assigned
        return {"success": True, "data": "already_exists", "reused": True}

    # 400 = wrong type, try next
```

#### Problem 3c: Self-Assignment Waste

The deploying Service Principal (identified by `AZURE_CLIENT_ID`) already has implicit Admin access as the workspace creator. Attempting to re-assign it via the API was wasteful and could produce confusing errors.

**Fix**: Skip self-assignment:

```python
sp_client_id = os.environ.get("AZURE_CLIENT_ID", "")
if sp_client_id and principal_id.lower() == sp_client_id.lower():
    return {
        "success": True,
        "message": "Deploying SP already has implicit Admin access",
        "skipped": True,
    }
```

### Why It Only Showed in CI/CD

Locally, you might test with a single admin user (yourself) who is already workspace owner. The principal assignment was a no-op that happened to succeed. In CI/CD, a Service Principal deploys the workspace and then tries to add *other* principals — a different code path that triggered all three sub-problems.

**Commits**: `34820e3`, `be608e3`

---

## 5. Problem 4: Phantom Imports and Stale Module Paths {#5-phantom-imports}

### What Happened

Several files imported from modules that didn't exist:

```python
# ❌ In deploy-to-fabric.yml (GitHub Actions workflow)
from usf_fabric_cli.utils.auth import get_fabric_token
# ModuleNotFoundError: No module named 'usf_fabric_cli.utils.auth'

# ❌ In admin utility scripts
from src.core.secrets import FabricSecrets
# ModuleNotFoundError: No module named 'src.core'
```

### Why It Only Showed in CI/CD

Locally, you rarely run the GitHub Actions workflow YAML directly. The admin utility scripts (`list_workspace_items.py`, `init_ado_repo.py`) might have been tested in an older project layout (`src/core/`) that was since refactored to `src/usf_fabric_cli/`. If you hadn't re-run those scripts since the refactor, you wouldn't notice.

In CI/CD, every import is executed fresh, and Python crashes immediately on a broken import path.

### How It Was Fixed

- Replaced `from usf_fabric_cli.utils.auth import get_fabric_token` with the correct `from usf_fabric_cli.utils.config import get_environment_variables` (which handles SP auth internally)
- Replaced all `from src.core.*` imports with `from usf_fabric_cli.*` equivalents
- Rewrote `list_workspace_items.py` to use the modern `get_environment_variables()` pattern

**Commits**: `7eda0cc`, `f9c802f`

---

## 6. Problem 5: Workflow Placement — Library vs Consumer {#6-workflow-placement}

### What Happened

The deployment workflows (`deploy-to-fabric.yml`, `feature-workspace-create.yml`, `feature-workspace-cleanup.yml`, `fabric-cicd.yml`) were defined **inside the library repository** (`usf_fabric_cli_cicd`). This caused:

1. Workflows triggered on every push to the library codebase (even documentation fixes)
2. Secrets had to be configured in the library repo instead of the consumer project
3. Feature branch pushes in the codebase repo attempted to create Fabric workspaces

### The Design Principle

The `usf_fabric_cli_cicd` repository is a **library/tool**. It should not deploy anything itself. Deployment workflows belong in **consumer repositories** — the project-specific repos that _use_ the CLI to manage their own Fabric workspaces.

```
┌──────────────────────────┐     ┌──────────────────────────────┐
│  usf_fabric_cli_cicd     │     │  your-consumer-repo          │
│  (LIBRARY)               │     │  (CONSUMER)                  │
│                          │     │                              │
│  ✅ pytest.yml           │     │  ✅ feature-workspace-        │
│  ✅ lint.yml             │     │     create.yml               │
│  ✅ build.yml            │     │  ✅ feature-workspace-        │
│  ❌ deploy-to-fabric.yml │────▶│     cleanup.yml              │
│  ❌ feature-workspace-*  │     │  ✅ deploy-to-fabric.yml     │
│                          │     │                              │
│  pip install → library   │     │  pip install usf_fabric_cli  │
└──────────────────────────┘     └──────────────────────────────┘
```

### How It Was Fixed

1. **Removed all deployment workflows** from the library repo (`490b3bd`)
2. **Moved workflows to the consumer repo** (`your-consumer-repo/.github/workflows/`)
3. Consumer workflow installs the CLI library as a pip dependency:

```yaml
# In your-consumer-repo/.github/workflows/feature-workspace-create.yml
- name: Install CLI tool
  run: |
    pip install ms-fabric-cli==${{ vars.FABRIC_CLI_VERSION || '1.3.1' }}
    pip install "git+https://${{ secrets.FABRIC_GITHUB_TOKEN }}@${{ vars.CLI_REPO_URL || 'github.com/your-org/your-cli-repo' }}.git@${{ vars.CLI_REPO_REF || 'v1.7.7' }}"
```

> **Note**: The `CLI_REPO_URL`, `CLI_REPO_REF`, and `FABRIC_CLI_VERSION` are configurable via
> GitHub repository variables. See the [Replication Guide](../../../fabric_cicd_test_repo/docs/REPLICATION_GUIDE.md) for details.

**Commit**: `490b3bd` — *chore: remove deployment workflows from library repo*

---

## 7. Problem 6: Missing Dev Dependencies in CI {#7-missing-dev-deps}

### What Happened

The CI/CD pipeline ran `pip install -r requirements.txt` and then attempted linting (`flake8`), formatting checks (`black`), type checking (`mypy`), and tests (`pytest`). All of these tools were uninstalled.

### Why It Only Showed in CI/CD

Locally (or in your conda environment), you'd installed these tools once and they persisted. In CI/CD, the runner starts with a bare Python installation every time.

### How It Was Fixed

Created `requirements-dev.txt` separating dev/test tools from production dependencies:

```
# requirements-dev.txt (dev/test only — NOT installed in production containers)
pytest>=7.0
pytest-cov>=4.0
flake8>=6.0
black>=23.0
mypy>=1.0
isort>=5.12
types-requests
```

The CI pipeline now installs both:

```yaml
- name: Install dependencies
  run: |
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
```

The production `Dockerfile` only installs `requirements.txt`, keeping the image lean.

**Commits**: `516d96c`, `4f724e2`

---

## 8. Bonus: Docker Image Optimisation {#8-docker-optimisation}

### What Changed

The Dockerfile was converted from a **single-stage** build to a **multi-stage** build:

```dockerfile
# Stage 1: Builder — installs all deps into a virtual env
FROM python:3.11-slim AS builder
WORKDIR /build
RUN apt-get install -y git  # Only needed to pip-install Fabric CLI from GitHub
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir git+https://github.com/microsoft/fabric-cli.git@v1.3.1

# Stage 2: Runtime — lean production image
FROM python:3.11-slim
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY src/ ./src/
COPY config/ ./config/
# ... only production files
```

### Why

- **~60% smaller image**: Build-time tools (compilers, headers) aren't carried into production
- **Faster CI/CD pulls**: Smaller images transfer faster in automated pipelines
- **Better caching**: Dependency layer only rebuilds when `requirements.txt` changes

### A `.dockerignore` was also added

Prevents copying `webapp/`, `.agent/`, `.gemini/`, test files, and other development artifacts into the container.

---

## 9. Bonus: Deployment Visibility {#9-deployment-visibility}

### What Changed

Before CI/CD testing, deployments to Fabric were **silent**. The code would create 5 lakehouses, 3 notebooks, and add 4 principals — and the only output was "Deployment complete". If something failed silently (like principal assignments), you'd never know.

After the fixes, every action produces visible console output:

```
Creating items...
  ✓ Lakehouse: raw_data_lakehouse (created)
  ✓ Lakehouse: curated_lakehouse (created)
  · Notebook: transform_notebook (exists)
  ✓ Pipeline: daily_refresh (created)

Adding workspace principals...
  ✓ Added principal a1b2c3d4... as ServicePrincipal/Contributor
  ⚠ Skipped principal e5f6g7h8...: Deploying SP already has implicit Admin access
  · Principal i9j0k1l2... already has Admin role
```

This was critical for CI/CD debugging: when a GitHub Actions run failed, the log now shows exactly which step, which item, and which error occurred.

**Commit**: `34820e3` — *fix: principal assignment visibility and error detection*

---

## 10. Architecture Decision: REST API Over CLI {#10-rest-api-decision}

### Before (v1.5.0)

```
Python Code → fab CLI (subprocess) → Fabric API
```

Every operation went through the `fab` CLI as a subprocess call. The CLI handled authentication, workspace resolution, and API calls.

### After (v1.7.1)

```
Python Code → REST API (requests.post)     [preferred path]
           → fab CLI (subprocess fallback)  [if workspace ID unknown]
```

### Why the Shift

| Concern | fab CLI | Direct REST API |
|---|---|---|
| Workspace name resolution | Requires internal lookup (slow, race-prone) | Uses cached workspace ID (instant) |
| Error visibility | Exit code 0 even on API 4xx | Full HTTP status code available |
| Payload control | Limited to CLI flags | Full JSON payload control |
| Token management | Internal (keyring-dependent) | Managed by our TokenManager |
| Debugging | Opaque subprocess output | Full request/response logging |

The CLI is still used as a **fallback** when workspace IDs aren't cached, and for operations where the CLI adds value (e.g., `fab auth login`, `fab config set`).

---

## 11. Summary of All Changes {#11-summary}

| # | Problem | Root Cause | Fix | When Found |
|---|---|---|---|---|
| 1 | Encryption/Keyring failure | No desktop keyring in CI/CD runners | `encryption_fallback_enabled = true` before auth | CI/CD |
| 2 | "Workspace not found" after creation | `fab` CLI name lookup races REST API creation | Workspace ID cache + REST API for all item creation | CI/CD |
| 3a | Principals silently not added | Wrong API payload format (flat vs nested) | Direct `requests.post()` with correct nested JSON | CI/CD |
| 3b | Wrong principal type 400 errors | Didn't know if ID was User/SP/Group | Try all three types in sequence | CI/CD |
| 3c | Self-assignment waste | Deploying SP re-assigning itself | Skip when `principal_id == AZURE_CLIENT_ID` | CI/CD |
| 4 | `ModuleNotFoundError` | Phantom/stale import paths from old refactors | Updated all imports to `usf_fabric_cli.*` | CI/CD |
| 5 | Workflows triggering on library pushes | Deployment workflows in library repo | Moved workflows to consumer repos | Design review |
| 6 | `flake8: command not found` | Dev tools not in `requirements.txt` | Created separate `requirements-dev.txt` | CI/CD |
| 7 | GitHub secret naming rejection | Secret name started with `GITHUB_` | Renamed to `FABRIC_GITHUB_TOKEN` | CI/CD |
| 8 | Large Docker image | Single-stage build with build tools | Multi-stage builder/runtime pattern | Optimisation |
| 9 | Silent deployment failures | No console output for item creation | Added `✓`/`·`/`⚠` status lines for every operation | Debugging |

---

## 12. Lessons Learned {#12-lessons-learned}

### 1. "Works on my machine" is not "works"

Local environments accumulate state, cached credentials, and implicit context. CI/CD is the **true test** of whether code is self-contained and reproducible.

### 2. Exit code 0 does not mean success

The Fabric CLI returns exit code 0 for many API-level failures. Always inspect response bodies, not just return codes. When possible, use direct HTTP calls where you control error handling.

### 3. Separate library from consumer

A reusable tool should produce a `pip install`-able package. Deployment workflows belong in the projects that consume the tool, not in the tool's own repository.

### 4. Make everything visible

Silent operations are the enemy of debugging. Every creation, assignment, and skip should print a status line. In CI/CD logs, this is all you have.

### 5. Separate prod and dev dependencies

Production containers don't need `pytest`, `flake8`, or `mypy`. Dev dependencies should live in a separate file and only be installed in CI/CD and local dev environments.

### 6. Race conditions hide in sequential thinking

When you mentally think "create workspace, then create lakehouse", you imagine a pause between steps. In automated systems, "then" means "immediately after" — and the target system may not be ready.

### 7. API payload formats are fragile

Always test API calls against the real endpoint. Documentation, CLI abstractions, and local mocks can all diverge from the actual API contract. The Fabric `roleAssignments` API expects `{"principal": {"id": ..., "type": ...}, "role": ...}` — not the flat format that seemed more intuitive.

---

## Quick Reference: The Fix Commits

| Commit | Short Description |
|---|---|
| `c53a84c` | Encryption fallback for headless CI/CD |
| `d8c26bc` | REST API + workspace ID cache for all operations |
| `34820e3` | Principal assignment visibility and error detection |
| `be608e3` | Correct Fabric roleAssignments API payload (nested format) |
| `7eda0cc` | Replace phantom `get_fabric_token` import |
| `f9c802f` | Replace stale `src.core` imports in admin scripts |
| `490b3bd` | Remove deployment workflows from library repo |
| `516d96c` | Install `requirements-dev.txt` in CI |
| `a9d9eb9` | Rename `GITHUB_TOKEN_FABRIC` → `FABRIC_GITHUB_TOKEN` |
| `5316a88` | Inject governance SP into Test/Prod stages |
| `2021c6d` | Support inline `environments` block in config schema and loader |

---

### v1.7.6: Inline Environments & E2E Validation

The final milestone addressed a subtle but impactful schema validation bug: project configs with inline `environments:` blocks (used by most blueprint templates) failed validation because the JSON schema had `additionalProperties: false` without listing `environments` as a valid property.

**Fixes applied:**
1. Added `environments` property definition to `workspace_config.json` schema
2. Updated `ConfigManager.load_config()` to extract inline environments *before* schema validation
3. Inline `environments:` blocks now take priority over external `config/environments/*.yaml` files

**E2E Validation:** Full feature branch workspace lifecycle tested via consumer repo:
- Create workflow: workspace provisioned with folders, lakehouse, notebook, principals, and Git connection (2m 26s)
- Cleanup workflow: workspace destroyed on branch delete (28s)
- 369 unit tests passing (backward-compatible change)

---

*Document generated: 12 February 2026 | Covers changes from v1.5.0 through v1.7.6*
