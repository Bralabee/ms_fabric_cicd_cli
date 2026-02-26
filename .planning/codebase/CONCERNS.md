# Codebase Concerns

**Analysis Date:** 2026-02-26

## Tech Debt

### Broad Exception Handling (Multiple Files)

**Issue:** Multiple locations use bare `except Exception:` blocks that swallow all exceptions, making debugging difficult.

**Files:**
- `src/usf_fabric_cli/services/fabric_wrapper.py:178, 186, 347, 1358, 1398, 1946`
- `src/usf_fabric_cli/services/deployment_pipeline.py:380, 467`
- `src/usf_fabric_cli/services/deployment_state.py:323`
- `src/usf_fabric_cli/services/fabric_git_api.py:368`
- `src/usf_fabric_cli/services/git_integration.py:64, 113, 292`
- `src/usf_fabric_cli/scripts/dev/onboard.py:557, 658`
- `src/usf_fabric_cli/utils/secrets.py:299`
- `src/usf_fabric_cli/cli.py:743`
- `src/usf_fabric_cli/utils/retry.py:203`

**Impact:** Errors are silently swallowed with `pass` statements, making it impossible to diagnose failures during development. Some exceptions in critical paths like authentication (`fabric_wrapper.py:178-187`) hide login failures that should block deployment.

**Fix approach:** Replace bare `except Exception:` with specific exception types. Log warnings/errors before handling silently. Example from `secrets.py` shows best practice — log the error before returning None.

---

### Deprecated Modules Without Removal Timeline

**Issue:** Two modules are marked `DEPRECATED` but still referenced in codebase.

**Files:**
- `src/usf_fabric_cli/utils/config.py:372` — `DEPRECATED: Use core.secrets.get_secrets() instead for new code.`
- `src/usf_fabric_cli/services/git_integration.py:5` — `DEPRECATED: The deployer now uses FabricGitAPI (fabric_git_api.py) directly`

**Impact:** Unclear whether these are safe to remove or actively used. No deprecation timeline documented. Maintenance burden increases as deprecated code must still be tested and maintained.

**Fix approach:** Document removal timeline (e.g., "deprecated in v1.7, removal planned v2.0"). Create GitHub issues tracking each deprecation with target removal date.

---

### Large Monolithic Files

**Issue:** Several files exceed 1500 lines of code, making them difficult to understand and test.

**Files:**
- `src/usf_fabric_cli/services/fabric_wrapper.py:1975 lines` — Thin wrapper that has accumulated too much logic
- `src/usf_fabric_cli/services/deployer.py:1649 lines` — Main orchestrator combining workspace creation, Git, pipelines, templating
- `src/usf_fabric_cli/services/deployment_pipeline.py:1036 lines` — Deployment pipeline API with complex promotion logic
- `src/usf_fabric_cli/scripts/dev/onboard.py:905 lines` — Onboarding script with mixed concerns

**Impact:** Difficult to navigate, test in isolation, or understand dependencies. Higher cognitive load for contributors. Changes to one feature risk breaking others.

**Fix approach:** Break down into smaller, single-responsibility modules. Example: Extract `fabric_wrapper.py` workspace operations into `workspace_manager.py`, authentication into `auth_manager.py`.

---

## Known Bugs / Recent Fixes

**Note:** Version 1.7.17 (Feb 25, 2026) recently fixed several issues listed below. These are documented for context.

### Polling Busy-Loop Floor (Now Fixed in v1.7.17)

**Previous Issue:** Long-running operation polling loops used bare `time.sleep(retry_after)` which could cause CPU spinning if Fabric API returned `Retry-After: 0`.

**Files:**
- `src/usf_fabric_cli/services/deployment_pipeline.py:621`
- `src/usf_fabric_cli/services/fabric_git_api.py:627`

**Status:** FIXED — Now uses `time.sleep(max(retry_after, 2))` to enforce minimum 2-second floor.

**Residual Concern:** Maximum timeout is hardcoded as `max_attempts * retry_after` (default 600s for deployments). If API is slow, operations may timeout before completion. No user-configurable timeout.

---

### Workspace Deletion Transient Errors (Now Fixed in v1.7.16)

**Previous Issue:** `fab rm` command returned transient `UnknownError` when deleting workspaces.

**Files:** `src/usf_fabric_cli/services/fabric_wrapper.py:delete_workspace()`

**Status:** FIXED — Now falls back to Power BI REST API (`DELETE /v1.0/myorg/groups/{workspaceId}`) on UnknownError.

**Residual Concern:** Two-step deletion adds latency. Power BI API could also fail; fallback has no fallback.

---

### Pipeline User Assignment Permissions (Now Fixed in v1.7.15)

**Previous Issue:** Service Principals cannot access the `/users` endpoint on Fabric API for deployment pipelines.

**Files:** `src/usf_fabric_cli/services/deployment_pipeline.py:list_pipeline_users()`, `add_pipeline_user()`

**Status:** FIXED — Switched from Fabric REST API to Power BI REST API (`api.powerbi.com`).

**Residual Concern:** Inconsistent API choice across product (some operations use Fabric API, others Power BI API). Maintenance burden if Microsoft changes either API.

---

## Security Considerations

### Subprocess Command Execution

**Risk:** Fabric CLI commands are executed via `subprocess.run()` without shell escaping analysis.

**Files:**
- `src/usf_fabric_cli/services/fabric_wrapper.py` — Multiple subprocess calls (lines 94, 173, 183, 204, 264, 345, 1915)
- `src/usf_fabric_cli/services/token_manager.py:219, 227, 247`
- `src/usf_fabric_cli/scripts/admin/preflight_check.py:20, 67`
- `src/usf_fabric_cli/scripts/dev/onboard.py:58, 633, 692`

**Current mitigation:** All subprocess calls use `subprocess.run(cmd_list, shell=False)` with command arguments as list, not string. This prevents shell injection.

**Recommendations:**
1. Document that command lists must never be built from untrusted input
2. Add type hints to enforce list construction (not string formatting)
3. Audit any dynamic command construction (none found currently, but good to formalize)

---

### Secrets in Error Messages

**Risk:** CLI commands include usernames and credentials that could appear in error logs.

**Files:**
- `src/usf_fabric_cli/services/fabric_wrapper.py:192-202` — Fabric CLI login command includes `--username` and `--password` flags
- Error messages from `subprocess.CalledProcessError` could include these in `e.stderr`

**Current mitigation:** Error handling logs `e.stderr` but command list is not included, so credentials are not directly logged.

**Recommendations:**
1. Redact credentials from error messages before logging
2. Never include full command line in exception messages
3. Test that stderr from failed auth commands doesn't leak passwords

---

### Azure Key Vault Error Handling

**Issue:** Azure Key Vault connection failures are logged but may not prevent deployment from proceeding with missing secrets.

**Files:** `src/usf_fabric_cli/utils/secrets.py:69-80`

**Status:** FIXED in v1.7.17 — Now logs `logger.warning()` instead of silently failing.

**Residual Concern:** Fallback to `None` allows deployment to continue without credentials, which could cause cascading API failures later. No validation that required secrets are actually present.

---

## Performance Bottlenecks

### Polling Timeout Calculation

**Problem:** Polling operations use fixed `max_attempts` (default 60) × fixed `retry_after` (default 10s) = 600s max timeout. This is not user-configurable.

**Files:**
- `src/usf_fabric_cli/services/deployment_pipeline.py:581-632` — `poll_operation()` hardcodes 600s max
- Large deployments with 200+ items may exceed this timeout
- Promotion with auto-exclusion retries (line 745) can take 30s between attempts

**Impact:** Very large deployments fail with vague "Operation timed out" error. Users have no way to increase timeout without code changes.

**Improvement path:** Add `--max-wait` / `--poll-timeout` CLI parameter that gets passed through to `poll_operation()` and `promote()` calls.

---

### Workspace Name Cache

**Problem:** Workspace name → ID cache (`fabric_wrapper.py:78`) is in-memory only, not shared across parallel processes.

**Files:** `src/usf_fabric_cli/services/fabric_wrapper.py:78, 427-430`

**Impact:** If multiple deployment processes run in parallel, each maintains separate cache. After REST API workspace creation, subsequent CLI operations might fail because cache doesn't know about the new workspace. Subsequent lookups force inefficient CLI calls.

**Improvement path:** Persist cache to temporary file or Redis if parallel deployments are expected. Currently single-process deployments only.

---

### Git Status Polling

**Problem:** `promote()` command now polls `get_git_status()` in active loop (v1.7.16 change) waiting for `remoteCommitHash` match. No timeout on polling loop.

**Files:** `src/usf_fabric_cli/services/fabric_git_api.py` (implied from CHANGELOG entry)

**Impact:** If Git sync fails silently, polling loop could hang indefinitely.

**Recommendations:** Add explicit timeout and maximum retry count to Git sync polling.

---

## Fragile Areas

### Feature Prefix Unicode Character

**Issue:** Feature workspace names prepend Unicode character (`⚡` by default, configurable in `feature_workspace.json`).

**Files:**
- `src/usf_fabric_cli/services/deployer.py` — Uses feature_prefix in workspace naming
- `config/environments/feature_workspace.json` — Contains `feature_prefix` setting

**Why fragile:** Unicode characters in resource names can cause issues with:
- Command-line parsing tools that don't handle UTF-8
- Export/import systems that strip non-ASCII
- Azure resource naming policies

**Safe modification:** Test workspace creation with Unicode feature prefix in multiple environments. Verify character survives round-trips through Azure REST APIs, CLI output, and Git branch names.

**Test coverage:** See `tests/test_deployer.py` for feature prefix tests (added in v1.7.7).

---

### Deployment Pipeline Stage Assignment

**Issue:** Workspace-to-stage assignment requires pipeline to exist and Service Principal to have Admin access. Multiple permission checks needed.

**Files:**
- `src/usf_fabric_cli/services/deployer.py:1300-1350` (approx) — `_setup_deployment_pipeline()` method
- `src/usf_fabric_cli/services/deployment_pipeline.py` — Underlying API calls

**Why fragile:**
1. If workspace doesn't have Admin role, assignment silently fails (404)
2. If pipeline doesn't exist in workspace, 404 is returned
3. If Service Principal lacks Admin on pipeline, another 404
4. All 404s are treated the same, making it hard to diagnose which resource is missing

**Safe modification:** Check prerequisites before attempting assignment:
1. Verify workspace exists and SP is Admin
2. Verify pipeline exists
3. Call `get_pipeline()` to verify SP has access before assignment

Already partially addressed in v1.7.9, but could be more explicit.

**Test coverage:** Currently limited to happy-path tests. Need tests for:
- Missing workspace
- Missing pipeline
- Insufficient permissions on each resource

---

### Selective Promotion with Auto-Exclusion

**Issue:** `selective_promote()` method attempts deployment, and on failure, automatically excludes the failing items and retries (max 3 times).

**Files:** `src/usf_fabric_cli/services/deployment_pipeline.py:738-960`

**Why fragile:**
1. Item IDs extracted from error response (`_extract_failing_item_ids()`) might not match source items
2. If extraction fails, original items list is unchanged and same items will fail again → infinite loop protection via `max_retries`
3. Pairing target items by name (`_build_selective_items()`) assumes display names are unique — duplicates break pairing

**Safe modification:**
1. Add validation that extracted IDs actually match items being deployed
2. Test with duplicate item names in target stage
3. Document that promotion success depends on unique item names

**Test coverage:** Tests for happy path (Warehouse/SQLEndpoint exclusion) exist, but:
- Missing: error extraction with malformed error responses
- Missing: duplicate item names scenario
- Missing: partial failure (some items fail, others succeed)

---

## Scaling Limits

### Configuration File Size

**Problem:** Configuration files contain nested structures for folders, artifacts, templates, and all environments inline. Single file can become unwieldy.

**Files:**
- `config/projects/{org}/{project}.yaml` — User configuration files
- Schema: `src/usf_fabric_cli/utils/config.py:validate_schema()`

**Current capacity:** No tested limit, but typical configs are < 100KB.

**Scaling path:** For large monorepos:
1. Support `$ref` in YAML to import environment configs from separate files (already supported via `config/environments/*.yaml`)
2. Add config composition/merging for large projects with many artifacts

---

### Deployment Item Count

**Problem:** Deployment pipeline promotion includes all items in a stage. For stages with 200+ items, promotion becomes slow and timeout-prone.

**Files:** `src/usf_fabric_cli/services/deployment_pipeline.py` — `promote()` / `selective_promote()`

**Current limit:** Default polling timeout is 600s. Promotion with 200+ items can exceed this.

**Scaling path:**
1. Add `--max-wait` parameter to increase timeout
2. Implement chunked deployment (promote items in batches) — requires Fabric API support
3. Filter deployment by item type (exclude rarely-changed types like warehouses)

---

### Concurrent Deployment Processes

**Problem:** Single-process deployments work fine. Multiple concurrent `fabric deploy` commands against same workspace can conflict.

**Files:**
- `src/usf_fabric_cli/services/deployment_state.py` — State tracking not process-safe
- `src/usf_fabric_cli/services/fabric_wrapper.py:78` — In-memory workspace ID cache not shared

**Current mitigation:** Deployments are typically triggered sequentially (CI/CD pipelines run jobs one at a time).

**Scaling path:** If parallel deployments needed:
1. Use file-based locking for state files
2. Use shared cache (Redis) for workspace IDs
3. Test concurrent creation of same workspace (should be idempotent)

---

## Dependencies at Risk

### Microsoft Fabric CLI Version Pinning

**Risk:** Direct Git install of `ms-fabric-cli@v1.3.1` in `requirements-dev.txt:19`.

**Files:**
- `requirements-dev.txt:19` — `git+https://github.com/microsoft/fabric-cli.git@v1.3.1#egg=ms-fabric-cli`
- `src/usf_fabric_cli/services/fabric_wrapper.py:36-38` — Defines `MINIMUM_CLI_VERSION` and `RECOMMENDED_CLI_VERSION`

**Risk:**
- v1.3.1 may have bugs that are fixed in later versions
- If Microsoft moves repository or changes versioning, pip install fails
- Direct Git install requires Git to be available in CI/CD (not always true for containers)

**Migration plan:**
1. Wait for ms-fabric-cli to be published on PyPI (currently not published)
2. Once available on PyPI, switch to: `ms-fabric-cli>=1.3.1,<2.0`
3. Add version check in CI to catch incompatibilities early

---

### Python Version Support

**Issue:** Only Python 3.9+ is officially tested. No upper bound specified.

**Files:**
- `environment.yml:8` — `python=3.9`
- `README.md:65` — "Python 3.9+ installed"

**Risk:** Type hints (PEP 604 union syntax `List[str] | None`) require Python 3.10+. Will fail on Python 3.9 if not using `from __future__ import annotations`.

**Current mitigation:** Most files use `from __future__ import annotations`, but not all:
- Missing in: `src/usf_fabric_cli/utils/audit.py`, `src/usf_fabric_cli/utils/telemetry.py`, others

**Recommendation:** Either:
1. Bump minimum Python to 3.10+, or
2. Consistently add `from __future__ import annotations` to all files, or
3. Use `typing.List[str]` instead of `list[str]` for compatibility

---

### Pydantic v2 Migration

**Issue:** Code uses Pydantic v2 (`pydantic>=2.5.0`). Pydantic v1 is incompatible.

**Files:**
- `requirements.txt:17` — `pydantic>=2.5.0`
- `src/usf_fabric_cli/utils/secrets.py:18-20` — Uses `pydantic_settings.BaseSettings` (v2 API)

**Risk:** If any transitive dependency requires Pydantic v1, pip dependency resolution will fail.

**Current mitigation:** Pinned to v2.5.0+, which prevents Pydantic v1 from being installed.

**Recommendation:** Monitor for Pydantic v3 release and plan upgrade when stable. Current code is on latest v2.x.

---

## Missing Critical Features

### No Credential Rotation / Token Refresh

**Issue:** Service Principal credentials in `.env` are static. If credentials rotate, deployment fails until `.env` is updated.

**Files:**
- `src/usf_fabric_cli/utils/secrets.py` — Reads credentials once at startup
- `src/usf_fabric_cli/services/token_manager.py` — Proactively refreshes tokens (v1.7+), but not credentials

**Impact:** Service Principal secret rotation requires manual `.env` update and redeployment. No graceful fallback.

**Improvement path:**
1. For Azure Key Vault users, support credential rotation by re-reading vault on each deployment
2. For direct `.env` users, document credential rotation procedure
3. Implement credential caching with TTL to avoid excessive vault reads

---

### No Workspace Export / Backup

**Issue:** Workspace state is not backed up before deployment. If deployment fails catastrophically, rollback only deletes created items, not pre-existing ones.

**Files:** `src/usf_fabric_cli/services/deployment_state.py` — Tracks created items for rollback, but not pre-existing state

**Impact:** Breaking changes to artifact definitions could corrupt or delete pre-existing items.

**Improvement path:**
1. Add optional `--backup` flag to create a snapshot of workspace before deploying
2. Store snapshot as Fabric notebook with item metadata
3. Provide `restore` command to re-upload items from backup

---

### No Dry-Run / Preview Mode

**Issue:** No way to validate deployment without actually creating/modifying items.

**Files:** `src/usf_fabric_cli/cli.py:55-57` — `--validate-only` flag exists but only validates configuration syntax, not actual deployment

**Impact:** Users have no way to preview what will be created/changed before committing.

**Improvement path:**
1. Extend `--validate-only` to include dry-run of workspace operations
2. Show what would be created/modified without actually doing it
3. Mock Fabric API responses for safe preview

---

## Test Coverage Gaps

### Untested Edge Cases in Polling

**What's not tested:**
- Polling timeout behavior (does it actually respect `max_attempts`?)
- Retry-After header with value 0 (busy-poll floor test exists but not comprehensive)
- Operation status transitions (Failed → polling again, should stop immediately)

**Files:** `src/usf_fabric_cli/services/deployment_pipeline.py:581-632`

**Risk:** Polling bugs cause silent failures or hangs in CI/CD pipelines.

**Priority:** HIGH — polling is critical path for deployment.

---

### Untested Error Paths in Fabric Wrapper

**What's not tested:**
- Workspace creation with duplicate name (idempotent handling)
- Role assignment to non-existent principal (404 handling)
- Large workspace with 200+ items (performance/timeout)
- Workspace deletion after items added (cleanup robustness)

**Files:** `src/usf_fabric_cli/services/fabric_wrapper.py` — Most complex file with many untested branches

**Risk:** Silent failures in production due to untested error conditions.

**Priority:** HIGH — high test coverage claimed (454 tests), but edge cases are sparse.

---

### Missing Integration Tests for Multi-Stage Pipelines

**What's not tested:**
- Full Dev → Test → Prod promotion flow
- Promotion with selective item exclusion across all stages
- Promotion rollback on failure

**Files:** `tests/integration/test_promote_e2e.py` — Only tests promotion, not full pipeline flow

**Risk:** Multi-stage pipelines are complex and breaking changes in one stage affect others.

**Priority:** MEDIUM — integration tests exist but incomplete.

---

### No Tests for Git Connection Stale State Recovery

**What's not tested:**
- DuplicateConnectionName (409) recovery with connection deletion and recreation
- ConnectionMismatch (400) with rotated credentials
- Git status polling timeout during promotion

**Files:**
- `src/usf_fabric_cli/services/deployer.py` — `_connect_git()` with stale connection handling
- `src/usf_fabric_cli/services/fabric_git_api.py` — Git sync polling

**Risk:** Git integration failures silently fail or hang deployments.

**Priority:** MEDIUM — Git integration is key feature but lightly tested.

---

## Code Quality Issues

### Inconsistent Error Context

**Problem:** Some error messages include full context (stack trace, command args), others just say "failed".

**Files:** Throughout `src/usf_fabric_cli/services/`

**Impact:** Hard to diagnose failures without enabling debug logging.

**Recommendation:** Standardize error messages to include:
1. What operation failed
2. Why it failed (error message from underlying API/CLI)
3. What to try next (recovery steps)

Example: `"Failed to create workspace 'sales-analytics': HTTP 409 Conflict (workspace already exists). Either delete the existing workspace or use --reuse-existing."`

---

### Magic Numbers and Timeouts

**Problem:** Hardcoded timeouts and retry values scattered throughout codebase.

**Files:**
- `src/usf_fabric_cli/services/deployment_pipeline.py:584, 585` — `max_attempts=60, retry_after=10`
- `src/usf_fabric_cli/services/fabric_wrapper.py:226, 234` — `timeout=300` (5 minutes)
- `src/usf_fabric_cli/services/deployment_pipeline.py:745` — `max_retries=3` (for auto-exclusion)
- Multiple `timeout=30` in HTTP requests

**Impact:** Difficult to tune behavior for large deployments without code changes.

**Recommendation:** Move all timeout/retry values to top-level constants or configuration file with documented defaults and rationale.

---

### Incomplete Input Validation

**Problem:** Some inputs are validated, others are not.

**Files:**
- `src/usf_fabric_cli/utils/config.py` — Validates configuration against JSON schema
- `src/usf_fabric_cli/services/fabric_git_api.py:309-310, 324-325` — Validates Git provider parameters
- `src/usf_fabric_cli/services/deployer.py` — No validation that workspace name is valid ASCII (recently added in v1.7.18 per changelog mentions)

**Impact:** Invalid inputs cause cascading errors in Fabric API instead of fast-fail validation.

**Recommendation:** Create `validation.py` module with validators for common inputs (workspace names, item names, principal IDs, Git URLs). Use consistently across all input points.

---

## Recommendations by Priority

### Critical (Security/Reliability)
1. Replace bare `except Exception:` blocks with specific exception types and logging
2. Add credential rotation support for long-running deployments
3. Validate polling loop respects max timeout (write explicit test)
4. Add user-configurable polling timeout to CLI

### High (Functionality)
1. Break down monolithic files (fabric_wrapper.py, deployer.py)
2. Add dry-run/preview mode
3. Document deprecation timelines and removal dates
4. Audit error messages for credential leakage

### Medium (Usability)
1. Standardize error messages with context and recovery steps
2. Move hardcoded timeouts to configuration
3. Add comprehensive Git integration tests
4. Test deployment with 200+ items (scaling limit validation)

### Low (Technical Debt)
1. Add workspace backup/export feature
2. Support Pydantic v3 when released
3. Wait for ms-fabric-cli on PyPI, migrate from Git install
4. Standardize Python 3.10+ type hints

---

*Concerns audit: 2026-02-26*
