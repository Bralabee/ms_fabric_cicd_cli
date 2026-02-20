# Stabilisation Changelog: February 10–18, 2026

> **📁 HISTORICAL DOCUMENT** — This is a technical changelog, not a user guide.
> For current setup instructions, see [00_START_HERE.md](00_START_HERE.md).

**Project**: USF Fabric CLI CI/CD (`usf_fabric_cli_cicd`)
**Scope**: All changes across the CLI library, consumer repo (EDPFabric), and test repo (`fabric_cicd_test_repo`) to reach stable v1.7.7.
**Total**: 152 commits across 3 repositories (66 CLI, 38 consumer, 48 test repo) — from v1.7.0 through v1.7.7.

---

## Category 1: Architecture & Core Features

| # | Item | Version | Repo |
|---|------|---------|------|
| 1 | **Main-Centric Dev Workspace** — refactored `onboard.py` to default to Dev workspace on `main` branch (not feature branch). Added `--with-feature-branch` opt-in flag | v1.7.0 | CLI |
| 2 | **Automated Feature Workspace Lifecycle** — `feature-workspace-create.yml` (auto-create on `feature/*` push) + `feature-workspace-cleanup.yml` (auto-destroy on PR merge/branch delete) | v1.7.0 | CLI |
| 3 | **Fabric Deployment Pipeline Integration** — new `deployment_pipeline.py` service wrapping the Fabric Deployment Pipelines REST API (CRUD, stage management, deploy/promote, LRO polling, token refresh) | v1.7.0 | CLI |
| 4 | **`promote` CLI command** — `usf_fabric_cli promote --pipeline-name "Name" --source-stage Development` with auto-inferred target stage | v1.7.0 | CLI |
| 5 | **Notebook Content Import** — `create_notebook()` accepts `.py` and `.ipynb` files via `file_path`, base64-encoding into Fabric Items API payload | v1.7.5 | CLI |
| 6 | **Jinja2 Template Rendering for Notebooks** — `{{ environment }}`, `{{ workspace_name }}`, `{{ secrets.* }}` substitution in notebook source files | v1.7.5 | CLI |
| 7 | **7 New Fabric Item Types** — `Environment`, `Reflex`, `MLModel`, `MLExperiment`, `DataflowGen2`, `KQLQueryset`, `Eventhouse` added to rollback state | v1.7.5 | CLI |
| 8 | **Thread-Safe Token Refresh** — `TokenManager.get_token()` uses `threading.Lock` to prevent concurrent races | v1.7.5 | CLI |
| 9 | **Real Audit Summary** — `AuditLogger.get_audit_summary()` parses JSONL logs (was a stub) | v1.7.5 | CLI |
| 10 | **Deployment Pipeline User Access** — `list_pipeline_users()` + `add_pipeline_user()` auto-grant Admin principals pipeline-level access | v1.7.7 | CLI |
| 11 | **Unicode Feature Prefix (⚡)** — configurable prefix on display-name feature workspaces for visual identification in Fabric portal. `feature_prefix` parameter on `get_workspace_name_from_branch()` | v1.7.7 | CLI |
| 12 | **Git Repo Isolation (dual-mode)** — `--create-repo` flag auto-creates per-project GitHub/ADO repos. `init_github_repo.py` script. `onboard-isolated` Makefile target | v1.7.0 | CLI |
| 13 | **Unified CLI Entrypoint** — 11 Typer subcommands (`deploy`, `validate`, `diagnose`, `destroy`, `promote`, `onboard`, `generate`, `list-workspaces`, `list-items`, `bulk-destroy`, `init-github-repo`) giving Docker parity | v1.7.0 | CLI |

---

## Category 2: Bug Fixes — Git Integration

| # | Item | Version | Repo |
|---|------|---------|------|
| 14 | **GitHub 409 DuplicateConnectionName Recovery** — lookup existing connection by name + reuse instead of failing | v1.7.2 | CLI |
| 15 | **GitHub `myGitCredentials` SSO** — include `myGitCredentials` with `"source": "Automatic"` to resolve 400 InvalidInput | v1.7.2 | CLI |
| 16 | **WorkspaceAlreadyConnectedToGit** — 409 treated as idempotent success instead of error | v1.7.2 | CLI |
| 17 | **Clean CI/CD Log Messages** — 409 responses return structured `duplicate: True` / `already_initialized: True` flags instead of alarming error logs | v1.7.3 | CLI |
| 18 | **Feature workspace slash-to-dash** — replaced `/` with `-` in bracket notation workspace names (e.g., `[FEATURE-dev-setup]` not `[FEATURE/dev-setup]`) | v1.7.7 | CLI |
| 19 | **Bracket notation for display-name workspaces** — spaces in workspace names trigger `Base Name [FEATURE-desc]` instead of `base-name-feature-desc` slugs | v1.7.7 | CLI |

---

## Category 3: Bug Fixes — Deployment & Runtime

| # | Item | Version | Repo |
|---|------|---------|------|
| 20 | **Idempotent Workspace Destroy** — `destroy` exits 0 when workspace already gone (NotFound), resolving race between `pull_request:closed` and `delete` events | v1.7.4 | CLI |
| 21 | **Default Folders Opt-In** — changed defaults from `["Bronze", "Silver", "Gold", "Notebooks", "Pipelines"]` to `[]`. No more unwanted folders | v1.7.7 | CLI |
| 22 | **Import Path Bug** — `config.py` importing from `usf_fabric_cli.secrets` → `usf_fabric_cli.utils.secrets` | v1.7.5 | CLI |
| 23 | **UTC Timestamp Deprecation** — `datetime.now(timezone.utc)` instead of `datetime.utcnow()` | v1.7.5 | CLI |
| 24 | **Jinja2 Undefined Handling** — `ArtifactTemplateEngine` uses `Undefined` class instead of `None` | v1.7.5 | CLI |
| 25 | **Blueprint `environments:` blocks** — removed unsupported inline blocks from 4 blueprints | v1.7.5 | CLI |
| 26 | **Inline `environments` Config Support** — JSON schema + `ConfigManager` now support inline `environments:` blocks | v1.7.6 | CLI |
| 27 | **Compliance Blueprint** — removed `ManagedPrivateEndpoint` (requires Networking API, not Items API) | v1.7.5 | CLI |
| 28 | **Schema `additionalProperties: false`** — catches config typos early | v1.7.5 | CLI |
| 29 | **Auto-generate FABRIC_TOKEN from SP** — `secrets` module generates token from Service Principal credentials when `FABRIC_TOKEN` is unset | v1.7.6 | CLI |
| 30 | **Governance SP Injection** — `_enrich_principals()` injects mandatory SPs into Test/Prod workspaces (not just Dev) | v1.7.0/v1.7.7 | CLI |
| 31 | **REST API payload for roleAssignments** — corrected API body format | v1.7.1 | CLI |
| 32 | **REST API + workspace ID cache** — all operations use REST API with cached workspace IDs | v1.7.1 | CLI |
| 33 | **Principal assignment visibility** — error detection improvements | v1.7.1 | CLI |
| 34 | **Encryption fallback for CI/CD** — `encryption_fallback` enabled for environments without keyring | v1.7.1 | CLI |
| 35 | **Phantom `get_fabric_token` import** — replaced with inline `az` CLI token acquisition in workflows | v1.7.0 | CLI |
| 36 | **Stale `src.core` imports** — replaced legacy `from src.core` with `usf_fabric_cli` paths in 4 admin scripts | v1.7.0 | CLI |
| 37 | **`list_workspace_items.py` rewrite** — replaced broken auth flow with `get_environment_variables()` pattern | v1.7.0 | CLI |
| 38 | **`GITHUB_TOKEN_FABRIC` → `FABRIC_GITHUB_TOKEN`** — renamed secret to avoid GitHub reserved name collision | v1.7.1 | CLI |

---

## Category 4: Bug Fixes — Consumer Repo Promotion Workflows

| # | Item | Version | Repo |
|---|------|---------|------|
| 39 | **Skip empty workspace promotion** — exit gracefully when workspace has no deployable items | — | Consumer |
| 40 | **Selective promotion** — skip Warehouse/SQLEndpoint (SP can't deploy these) instead of failing entire promotion | — | Consumer |
| 41 | **LRO polling endpoint** — fixed `/v1/operations/{id}` endpoint for long-running operation polling | — | Consumer |
| 42 | **Auto-retry with GenericError exclusion** — retry promotion excluding items that fail with `GenericError` | — | Consumer |
| 43 | **Exit code 2 handling** — promote workflows treat exit code 2 (partial success) gracefully | — | Consumer |

---

## Category 5: CI/CD Pipeline & Quality Gate

| # | Item | Version | Repo |
|---|------|---------|------|
| 44 | **CI quality gate restored** — fixed all lint/format violations (flake8, black) | v1.7.5 | CLI |
| 45 | **Pre-commit hooks** — black, isort, flake8, bandit, detect-secrets, yamllint, trailing-whitespace, no-commit-to-branch | v1.7.5 | CLI |
| 46 | **mypy soft gate** — `continue-on-error: true` per project docs | v1.7.5 | CLI |
| 47 | **`requirements-dev.txt`** — separated dev/test deps from production | v1.7.0 | CLI |
| 48 | **Bandit B113** — added timeout to all `requests` calls | v1.7.5 | CLI |
| 49 | **Community files** — `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`, PR template, CODEOWNERS, Dependabot | v1.7.5 | CLI |
| 50 | **actions/checkout@v6 + actions/setup-python@v6** — upgraded across all workflow files | — | Test repo |
| 51 | **Multi-stage Dockerfile** — builder/runtime pattern (~60% smaller image) | v1.7.0 | CLI |
| 52 | **`.dockerignore` hardened** — excludes `webapp/`, `.agent/`, `.gemini/`, dev tooling | v1.7.0 | CLI |

---

## Category 6: Test Suite Growth

| # | Item | Starting | Final | Repo |
|---|------|----------|-------|------|
| 53 | **Total unit tests** | ~140 (v1.6.2) | **385** (v1.7.7) | CLI |
| 54 | **Config tests** (9 new) — env var substitution, missing var passthrough, deep merge, list concatenation, principal injection/dedup, defaults, import path | v1.7.5 | | CLI |
| 55 | **Wrapper tests** (18 new) — notebook definition (py/ipynb/missing/unsupported), pipeline, warehouse, semantic model, generic item, principal guards, domain assignment | v1.7.5 | | CLI |
| 56 | **Git API tests** — updated all mocks from `requests.post`/`requests.get` → `requests.request` | v1.7.5 | | CLI |
| 57 | **Deployment pipeline tests** (23 new) — CRUD, stage management, promotion, LRO polling | v1.7.0 | | CLI |
| 58 | **Onboard tests** (20 new) — main-centric, feature workspace, isolated repo flows | v1.7.0 | | CLI |
| 59 | **`_enrich_principals()` tests** (5 new) — governance SP injection | v1.7.0 | | CLI |
| 60 | **CLI promote tests** (7 new) — promote subcommand | v1.7.0 | | CLI |
| 61 | **Idempotent destroy tests** (2 new) — NotFound = success, real errors propagate | v1.7.4 | | CLI |
| 62 | **409 idempotent Git tests** (4 new) — DuplicateConnectionName, already initialized | v1.7.3 | | CLI |
| 63 | **GitHub credentials tests** (4 new) — `myGitCredentials` SSO | v1.7.2 | | CLI |
| 64 | **WorkspaceAlreadyConnected tests** (2 new) — idempotent handling | v1.7.2 | | CLI |
| 65 | **GitHub duplicate recovery tests** (2 new) | v1.7.2 | | CLI |
| 66 | **Feature prefix tests** (3 new) — custom prefix, empty prefix, slug names | v1.7.7 | | CLI |

---

## Category 7: E2E Live Validation (Against Real Fabric Tenant)

| # | Item | Repo |
|---|------|------|
| 67 | **Feature workspace create/destroy lifecycle** — `fabric_cicd_test_repo`: push `feature/e2e-test-feb12` → workspace provisioned (folders, lakehouse, notebook, principals, Git connection) in 2m 26s → delete branch → workspace destroyed in 28s | Test repo |
| 68 | **Idempotent re-deploy** — pushed same branch again → clean logs, no "Failed to create" errors | Test repo |
| 69 | **Product repo refactor E2E** — validated test repo restructure with parameterised config paths and convention-based lookup | Test repo |
| 70 | **Consumer repo: Sales Audience [DEV]** — deployed base workspace, Deployment Pipeline created, Test/Prod workspaces provisioned | Consumer |
| 71 | **Consumer repo: Dev→Test promotion** — automated promotion on push to main, LRO polling, selective item handling | Consumer |
| 72 | **Consumer repo: Test→Prod promotion** — manual `workflow_dispatch` with safety gate | Consumer |
| 73 | **Consumer repo: RE Sales Direct feature workspace** — `feature/re_sales_direct/dev-setup` → workspace created via GitHub Actions | Consumer |
| 74 | **Unicode prefix portal test** — deployed `⚡ Sales Audience [FEATURE-test-prefix]` → verified visibility in Fabric portal sidebar → user accounts added as Admin via REST API | CLI (local) |
| 75 | **Full redeploy cycle** — destroyed old feature workspaces → redeployed `Sales Audience [DEV]` → deployed `⚡ Sales Audience [FEATURE-sales_audience-dev-setup]` (workspace `6b2c6c06`) | CLI (local) |

---

## Category 8: Consumer Repo Build-Out (EDPFabric)

| # | Item | Repo |
|---|------|------|
| 76 | **Archive legacy content** — moved all pre-existing EDPFabric content to `_archive/` | Consumer |
| 77 | **CI/CD consumer structure** — 6 GitHub Actions workflows (setup, create, cleanup, promote ×2, CI) | Consumer |
| 78 | **Multi-project support** — project-prefixed env vars (`SA_` / `RE_SALES_`) for independent configs | Consumer |
| 79 | **Two-tier access control** — mandatory governance principals + project-specific principals in YAML | Consumer |
| 80 | **EDP → Sales Audience migration** — config, workflow run-names, docs all updated | Consumer |
| 81 | **Sales Audience project configs** — `base_workspace.yaml` + `feature_workspace.yaml` with `⚡` naming | Consumer |
| 82 | **RE Sales Direct project configs** — parallel project with independent workspace configs | Consumer |

---

## Category 9: Documentation

| # | Item | Repo |
|---|------|------|
| 83 | **Educational Guide** (550+ lines) — 3 ways to work, multi-agent patterns, blueprint decision tree, quick reference cards | CLI |
| 84 | **From Local to CI/CD Guide** (550+ lines) — 9 problems fixed from v1.5.0→v1.7.2, CI/CD environment analysis | CLI |
| 85 | **Feature Branch Guide** — updated for fully automated pipeline lifecycle | CLI |
| 86 | **Release process checklist** — mandatory 10-step release procedure | CLI |
| 87 | **25 documentation gap fixes** — deep audit across 6 user guides | CLI |
| 88 | **Docs directory restructure** — fixed numbering, moved floating docs into subdirectories | CLI |
| 89 | **Copilot instructions** — updated to reflect `git_integration.py` role, `feature_prefix`, `feature_workspace.json` | CLI |
| 90 | **Consumer repo README** — two-tier access control explained, docs numbered | Consumer |
| 91 | **E2E Validation Report** — full 3-phase lifecycle results documented | Consumer/Test |
| 92 | **Replication Guide** — how to fork/replicate the test repo for new projects | Test repo |
| 93 | **Workflow Options** — Option A (single-project) vs Option B (multi-project) comparison | Test repo |

---

## Category 10: Code Quality & Refactoring

| # | Item | Repo |
|---|------|------|
| 94 | **Consolidated `scripts/` + `templates/` into `src/` package** | CLI |
| 95 | **Centralized HTTP requests** — all `fabric_git_api.py` methods use `_make_request()` | CLI |
| 96 | **Dead code removal** — unused `_run_command()` from `FabricCLIWrapper` | CLI |
| 97 | **Logging hygiene** — replaced 7 `print()` calls with `logger.*` in `config.py` and `fabric_wrapper.py` | CLI |
| 98 | **`GitConnectionSource` enum** — replaced raw strings with enum values | CLI |
| 99 | **Comprehensive Makefile audit** — 15 new targets (total 30+), fixed `.PHONY`, split lint/format | CLI |
| 100 | **Parameterized hardcoded values** — test configs and docs updated for reusability | CLI/Test |

---

## Summary

| Metric | Value |
|--------|-------|
| **Versions shipped** | v1.7.0 → v1.7.7 (8 releases in 9 days) |
| **Total commits** | 152 across 3 repos |
| **Unit tests** | 140 → **385** (+175%, net +245 tests) |
| **E2E validations** | 8 live Fabric tenant tests |
| **Bug fixes** | 38 |
| **New features** | 13 |
| **Documentation updates** | 11 docs created/overhauled |
| **Repos synced** | 5 remotes for CLI, 1 for consumer, 2 for test |

---

*Generated: 18 February 2026*
