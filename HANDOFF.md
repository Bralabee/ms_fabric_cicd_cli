# HANDOFF — Bulk Destroy + Brownfield Scaffold + SC30GLD Deployment

**Date**: 2026-03-17
**Session**: Bulk destroy fix → scaffold improvements → SC30GLD onboarding
**Status**: SC30GLD deployed. PRs open. Individual user principals NOT propagated to TEST/PROD (see below).

---

## Goal

Fix bulk destroy (stuck in infinite loop), re-scaffold SC30GLD-DM30 - Opco Data Mart [DEV] as a brownfield project, and deploy Test/Prod workspaces + deployment pipeline.

## Completed Work

### 1. Bulk Destroy Rewrite
- Fixed workspace name parser (was splitting on whitespace, truncating multi-word names)
- Added full teardown: pipeline unbinding → item deletion → workspace deletion
- Upfront pipeline map (O(pipelines) scan once) instead of O(workspaces × pipelines)
- Added `--skip-pipeline-teardown`, `--skip-item-deletion` CLI flags
- Pagination safety on `list_workspace_items_api` (max_pages=50, duplicate token detection)
- Successfully destroyed 9 test workspaces (e2e_test_consumer, e2e_test_scaffold, edp_test_v17)

### 2. Brownfield Scaffold (`--brownfield`)
- New flag: emits discovered principals as active YAML entries with actual GUIDs
- Display-name detection: feature templates use base display name for spaced workspaces
- Context-aware next steps: detects existing project + workflow dropdown presence
- Checks both config dir AND workflow dropdown before declaring project exists
- Added to: scaffold_workspace.py (argparse), cli.py (Typer), Makefile (both repos)

### 3. SC30GLD-DM30 Deployment
- Re-scaffolded with `--brownfield` — 16 principals (3 governance env vars + 13 discovered GUIDs)
- Setup Base Workspaces workflow run #23173478356 — **SUCCESS**:
  - DEV: Already existed (idempotent)
  - TEST: Created (`8e06b14c`) with principals + folders
  - PROD: Created (`3e30e3b9`) with principals + folders
  - Pipeline: Created (`c10ecfab`) with 3 stages assigned

### 4. Docs & Version Bump
- Version: 1.8.3 → **1.8.4** across pyproject.toml, all docs, vendor wheel
- CHANGELOG: [Unreleased] moved to [1.8.4] - 2026-03-17
- Fixed 11 broken CLI_REFERENCE.md links → redirected to 02_CLI_Walkthrough.md
- Removed stale HANDOFF.md from feat/repoint-connections
- Updated Makefile scaffold/destroy targets with full docs in both repos
- 720 tests passing

## Remaining Work / Known Issues

### CRITICAL: Individual user principals NOT propagated to TEST/PROD
The deployer's `_setup_deployment_pipeline()` at line 1617 has:
```python
if not principal_id_raw or principal_id_raw.startswith("${"):
    continue
```
The hardcoded GUIDs (f21d0f2e, c1f65310) passed through correctly. But the logs only show 3 principals added to TEST/PROD:
- `4a4973a3` (Automation SP)
- `f21d0f2e` (IT Admin Group)
- `c1f65310` (EDP Support Group)

The 10 individual users (Kevin Quinlan, Gabor Balazs, etc.) and EMEA-JDE_2_FABRIC SP are NOT visible in the logs for TEST/PROD. **Investigate whether the deployer filtered them or if it's a log truncation issue.** Check the Fabric portal directly to confirm.

### Pipeline User Access Warnings (non-blocking)
- SP → 401 Unauthorized on PBI Pipeline Users API (known Fabric limitation — SP needs tenant Fabric Admin role)
- This doesn't affect functionality — SP has implicit access as pipeline creator

### FABRIC_DOMAIN_NAME not set
- Domain assignment skipped for all workspaces
- Cosmetic only — set `FABRIC_DOMAIN_NAME` secret in GitHub if needed

### PRs Open (not merged)
| Repo | Branch | PR |
|---|---|---|
| usf_fabric_cli_cicd | `feature/bulk-destroy-improvements` | [#68](https://github.com/BralaBee-LEIT/usf_fabric_cli_cicd_codebase/pull/68) |
| usf-fabric-cicd (mirror) | `feature/bulk-destroy-and-brownfield-scaffold` | [#17](https://github.com/BralaBee-LEIT/usf_fabric_cicd_codebase/pull/17) |
| EDPFabric (consumer) | `feature/docs-freshness-audit` | [#81](https://github.com/ABBA-REPLC/EDPFabric/pull/81) |

### Consumer repo has 2 uncommitted template files
```
M config/projects/_templates/sc30gld_dm30_opco_data_mart/base_workspace.yaml
M config/projects/_templates/sc30gld_dm30_opco_data_mart/feature_workspace.yaml
```
These are from the last `make scaffold` run. Either commit them or discard (the concrete project configs are already committed).

### bralabee remote (CLI repo)
Push to `Bralabee/ms_fabric_cicd_cli.git` returned 403 — credentials/access issue.

## Key Decisions

1. **Brownfield vs greenfield**: Existing workspaces use `--brownfield` to emit actual GUIDs instead of placeholder env vars. No GitHub Secrets needed for project-specific principals.
2. **Display-style names**: Feature workspaces use `"SC30GLD-DM30 - Opco Data Mart"` (not `${PROJECT_PREFIX}`) for readable Fabric portal names.
3. **SC30GLD_ADMIN_ID / SC30GLD_MEMBERS_ID**: These secrets DON'T EXIST and are NOT used. The configs use hardcoded GUIDs instead. The workflow env var exports for these are harmless dead code.

## Environment

- **Conda env**: `fabric-cli-cicd`
- **Python**: 3.11
- **Tests**: 720 passed (pytest tests/ -x)
- **CLI version**: 1.8.4 (pyproject.toml)
- **Vendor wheel**: usf_fabric_cli-1.8.4-py3-none-any.whl

## Resume Instructions

### To investigate missing user principals on TEST/PROD:
```bash
cd usf_fabric_cli_cicd
conda activate fabric-cli-cicd
set -a && source .env && set +a

# Check what's actually on the TEST workspace
python -c "
from usf_fabric_cli.scripts.admin.utilities.scaffold_workspace import _discover_principals
from usf_fabric_cli.services.fabric_wrapper import FabricCLIWrapper
from usf_fabric_cli.utils.config import get_environment_variables
env = get_environment_variables()
f = FabricCLIWrapper(env['FABRIC_TOKEN'])
for p in _discover_principals(f, 'SC30GLD-DM30 - Opco Data Mart [TEST]'):
    print(f'{p[\"type\"]:20s} {p[\"role\"]:12s} {p[\"id\"]}  # {p[\"description\"]}')
"
# Expect: should show all 16 principals if propagation worked
# If only 3, the deployer filtered the individual users — check line ~1617 in deployer.py
```

### To merge PRs:
1. Review and merge CLI PR #68
2. Review and merge Mirror PR #17
3. Review and merge Consumer PR #81
4. Tag: `git tag v1.8.4 && git push origin v1.8.4` (on CLI repo main after merge)
