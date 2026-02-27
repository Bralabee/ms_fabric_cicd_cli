# USF Fabric CLI — Stabilization

## What This Is

An incremental stabilization effort for the USF Fabric CLI, a Python-based deployment orchestration tool that wraps the Microsoft Fabric CLI. The CLI manages workspace creation, Git integration, deployment pipelines, and artifact templating for Microsoft Fabric environments. This project addresses critical security issues, code quality debt, and maintainability problems without restructuring the existing architecture.

## Core Value

Deployments are reliable, debuggable, and safe — credentials never leak, errors explain themselves, and the codebase is approachable for new contributors.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. Inferred from existing codebase. -->

- ✓ Config-driven YAML deployment orchestration — existing
- ✓ Azure AD Service Principal authentication — existing
- ✓ Azure Key Vault secrets management with env var fallback — existing
- ✓ Fabric workspace creation with idempotency — existing
- ✓ Fabric Git integration (GitHub + Azure DevOps) — existing
- ✓ Deployment pipeline management (Dev → Test → Prod promotion) — existing
- ✓ Selective promotion with auto-exclusion of failing items — existing
- ✓ Feature workspace lifecycle (create, deploy, teardown) — existing
- ✓ Template-based artifact generation via Jinja2 — existing
- ✓ JSONL audit logging — existing
- ✓ Exponential backoff retry logic — existing
- ✓ Token refresh for long-running deployments — existing
- ✓ Project onboarding automation — existing
- ✓ Preflight checks for installation validation — existing
- ✓ Interactive web app for deployment guides — existing
- ✓ Workspace name ASCII validation guard — existing (v1.7.18)
- ✓ Polling floor to prevent busy-loop on Retry-After: 0 — existing (v1.7.17)

### Active

<!-- Current scope. Building toward these. -->

- [ ] Azure client secret is never passed as a command-line argument (secure credential passing via stdin, env vars, or temp files)
- [ ] All bare `except Exception:` blocks replaced with specific exception types and proper logging
- [ ] Error messages include what failed, why, and what to try next
- [ ] Hardcoded timeouts and retry values extracted to named constants or configuration
- [ ] Deprecated modules removed (config.py legacy methods, git_integration.py)

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Breaking up monolithic files (fabric_wrapper.py, deployer.py) — incremental cleanup only, no architecture changes
- Full service layer restructure — deferred to future milestone
- Dry-run / preview mode — useful but separate feature work
- Workspace backup/export — separate feature work
- Credential rotation support — separate feature work
- Parallel deployment support — not needed currently

## Context

- **Brownfield project:** ~50+ Python source files, 454 existing tests, active CI/CD
- **Shared Windows terminal servers:** Primary deployment environment where credentials in process lists are visible via Task Manager and Windows event logs — this is the critical driver for the security fix
- **Recent fixes:** v1.7.15–v1.7.17 addressed polling floors, Key Vault logging, pipeline user permissions, and workspace deletion fallbacks
- **Codebase map available:** `.planning/codebase/` contains 7 documents from automated analysis

## Constraints

- **Backward compatibility**: CLI commands and YAML config format must not change in breaking ways
- **Test suite**: All 454 existing tests must remain green throughout every change
- **Incremental**: Each fix should be independently mergeable — no big-bang refactors
- **No architecture changes**: Service layer structure stays as-is; this is cleanup, not redesign

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Incremental cleanup over restructure | Minimize risk, keep shipping | — Pending |
| Security fix is top priority | Credential exposure on shared servers is a critical vulnerability | — Pending |
| All changes must be backward-compatible | CLI is in active use by deployment pipelines | — Pending |

---
*Last updated: 2026-02-26 after initialization*
