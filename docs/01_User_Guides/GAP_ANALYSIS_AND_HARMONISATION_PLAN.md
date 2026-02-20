# Documentation Gap Analysis & Harmonisation Plan

> **Date**: Generated February 2026
> **Scope**: `usf_fabric_cli_cicd` (CLI library) + `edp_fabric_consumer_repo/EDPFabric` (consumer)
> **Objective**: Identify documentation gaps preventing users from understanding how to start and successfully deploy via CLI, Python, Docker, or GitHub Workflows — and propose a harmonisation plan.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Inventory of Existing Documentation](#2-inventory-of-existing-documentation)
3. [Deployment Path Audit](#3-deployment-path-audit)
   - 3.1 [Local Python / Conda](#31-local-python--conda)
   - 3.2 [Docker](#32-docker)
   - 3.3 [GitHub Actions CI/CD](#33-github-actions-cicd)
   - 3.4 [CLI Command-Line](#34-cli-command-line)
4. [Cross-Cutting Gaps](#4-cross-cutting-gaps)
5. [Gap Severity Matrix](#5-gap-severity-matrix)
6. [Harmonisation Plan](#6-harmonisation-plan)
7. [Proposed Document Architecture](#7-proposed-document-architecture)
8. [Implementation Roadmap](#8-implementation-roadmap)

---

## 1. Executive Summary

Across both repositories, there are **~7,500 lines of documentation** spanning 17 distinct files. The content is technically accurate and individually comprehensive. However, **no single document guides a user from zero to a successful deployment** via any of the four supported paths.

### Key Findings

| # | Finding | Severity |
|---|---------|----------|
| G1 | **No start-to-finish journey** — prerequisites, setup, config, deploy, and verify are fragmented across 5+ files per path | Critical |
| G2 | **Two repos, no bridge** — CLI repo docs and consumer repo docs exist in isolation; no document connects them | Critical |
| G3 | **Audience confusion** — 6+ guides target different audiences (operators, CLI developers, clients, learners) with no routing guide | High |
| G4 | **Massive content overlap** — quick start appears in 6 places; troubleshooting in 3; blueprint info in 3; creates maintenance burden and inconsistency risk | High |
| G5 | **Two competing CI/CD guides** — CLI Guide 10 uses `fabric_cicd_test_repo` as reference; consumer `02_REPLICATION_GUIDE` uses `EDPFabric`; different workflows, different structures | High |
| G6 | **No decision guide** — users can't determine when to use local vs Docker vs CI/CD, or single-project vs multi-project, or CLI `promote` vs `selective_promote.py` | Medium |
| G7 | **No quick-reference card** — no single-page listing of all commands, Make targets, env vars, secrets, and config keys | Medium |
| G8 | **Missing verification steps** — most guides end at "run the command" without explaining what success looks like in the Fabric portal | Medium |
| G9 | **Outdated content** — consumer repo `_archive/GETTING_STARTED.md` (931 lines) uses completely different architecture (layers-based, not current); version references vary (v1.7.7 to v1.7.14) | Low |

---

## 2. Inventory of Existing Documentation

### CLI Repo (`usf_fabric_cli_cicd/docs/01_User_Guides/`)

| # | File | Lines | Primary Audience | Deployment Path Covered |
|---|------|-------|-----------------|------------------------|
| 01 | `01_Usage_Guide.md` | 690 | Operators | Local Python, Make, Docker |
| 02 | `02_CLI_Walkthrough.md` | 318 | CLI Developers | CLI commands |
| 03 | `03_Project_Configuration.md` | 512 | Config Authors | YAML structure, blueprints |
| 04 | `04_Docker_Deployment.md` | 207 | DevOps Engineers | Docker |
| 05 | `05_Client_Tutorial.md` | ~250 | Clients | Operational overview |
| 06 | `06_Troubleshooting.md` | 613 | All | Debugging |
| 07 | `07_Blueprint_Catalog.md` | 835 | Config Authors | Template selection |
| 08 | `08_Educational_Guide.md` | 604 | Learners | All three ("Three Ways to Work") |
| 09 | `09_From_Local_to_CICD.md` | 572 | Engineers | Historical retrospective |
| 10 | `10_Feature_Branch_Workspace_Guide.md` | 1,144 | CI/CD Engineers | GitHub Actions |
| 11 | `11_Stabilisation_Changelog_Feb2026.md` | ~500 | Maintainers | Changelog (not a user guide) |
| — | `README.md` | 544 | All | Quick start |

**Subtotal**: ~5,789 lines across 12 files

### Consumer Repo (`edp_fabric_consumer_repo/EDPFabric/`)

| # | File | Lines | Primary Audience | Deployment Path Covered |
|---|------|-------|-----------------|------------------------|
| — | `README.md` | ~400 | Operators | GitHub Actions overview |
| 01 | `docs/01_WORKFLOW_OPTIONS.md` | ~260 | Architects | Single vs multi-project |
| 02 | `docs/02_REPLICATION_GUIDE.md` | 1,230 | New Teams | GitHub Actions (end-to-end) |
| 03 | `docs/03_E2E_VALIDATION_REPORT.md` | 319 | QA/Engineers | Live test results |
| — | `docs/E2E_TEST_LOG.md` | ~30 | Engineers | Brief test log |
| — | `CHANGELOG.md` | ~100 | Maintainers | Change history |
| — | `_archive/GETTING_STARTED.md` | 931 | (Outdated) | Legacy layers-based architecture |

**Subtotal**: ~3,270 lines across 7 files (excluding archive)

---

## 3. Deployment Path Audit

### 3.1 Local Python / Conda

**What exists:**

| Step | Covered? | Where |
|------|----------|-------|
| Install Python 3.11 | Partial | README mentions Python 3.11; no install instructions |
| Create conda environment | Missing in guides | Only in `.github/copilot-instructions.md` (not user-facing) |
| Install CLI (`pip install -e .` or `pip install git+...`) | Scattered | README, Guide 01, Guide 08, Replication Guide §11 |
| Generate project config | ✅ | Guide 03, Guide 07 |
| Set environment variables (`.env`) | Partial | Guide 01 mentions `.env`; no template walkthrough |
| Run `fabric-cicd deploy` | ✅ | Guide 01, Guide 02, README |
| Run `make deploy` | ✅ | Guide 01 (Makefile reference table) |
| Verify deployment in Fabric portal | Missing | No guide shows portal verification steps |
| Destroy / clean up | Partial | Guide 02 covers destroy scenarios |

**Gaps identified:**

1. **No conda guide in user-facing docs** — `conda activate fabric-cli-cicd` is critical but only documented in copilot-instructions. Users reading the guides would use `pip install` in their system Python.
2. **No `.env.template` walkthrough** — the `.env.template` file exists in the CLI repo but no guide walks through filling it out field by field.
3. **No portal verification** — after running `fabric-cicd deploy`, what should the user see? No screenshots, no checklist, no expected output description.
4. **`pip install -e .` vs `pip install git+...@tag`** — two different install methods for two different use cases (contributor vs consumer) but never explained together.

### 3.2 Docker

**What exists:**

| Step | Covered? | Where |
|------|----------|-------|
| Install Docker | Missing | Guide 04 assumes Docker is installed |
| Build image (`make docker-build`) | ✅ | Guide 04, README |
| Set `.env` file for Docker | Partial | Guide 04 mentions `ENVFILE` parameter |
| Run deployment (`make docker-deploy`) | ✅ | Guide 04 |
| Docker Compose for dev environment | Missing | No `docker-compose.yml` walkthrough |
| Multi-tenant pattern | Partial | Guide 04 mentions it; no worked example |
| Verify deployment | Missing | Same gap as local Python |
| When to use Docker vs other paths | Missing | No decision criteria |

**Gaps identified:**

1. **No Docker Compose walkthrough** — the Dockerfile exists but no compose file for the CLI repo; consumer repo doesn't use Docker at all.
2. **Guide 04 is only 207 lines** — the shortest deployment guide, yet Docker has the most setup complexity (Docker installation, image building, volume mounts, env file management, network configuration).
3. **No "Why Docker?"** — no doc explains when Docker is the right choice (e.g., CI/CD pipelines that can't install conda, air-gapped environments, reproducible builds).
4. **Consumer repo has zero Docker coverage** — the consumer repo is 100% GitHub Actions; Docker is only a CLI repo concept.

### 3.3 GitHub Actions CI/CD

**What exists:**

| Step | Covered? | Where |
|------|----------|-------|
| Understand two-repo model | ✅ | Replication Guide §3.2 |
| Create/fork consumer repo | ✅ | Replication Guide §3.1 |
| Configure GitHub Secrets | ✅ | Replication Guide §5, Consumer README |
| Configure repo variables | ✅ | Replication Guide §5.2 |
| Choose single vs multi-project | ✅ | Workflow Options doc, Replication Guide §4 |
| Run setup workflow | ✅ | Replication Guide §7 |
| Feature branch lifecycle | ✅ | Replication Guide §8, Consumer README |
| Promotion (Dev→Test→Prod) | ✅ | Replication Guide §9 |
| Troubleshooting | ✅ | Replication Guide §11, CLI Guide 06 |
| Verification | Partial | Replication Guide §10 has checklist but no portal screenshots |
| `selective_promote.py` vs CLI `promote` | Partial | Workflow Options doc mentions it; no deep comparison |

**Gaps identified:**

1. **TWO COMPETING GUIDES** — This is the most critical GitHub Actions gap:
   - CLI repo `10_Feature_Branch_Workspace_Guide.md` (1,144 lines) covers the full lifecycle using `fabric_cicd_test_repo` as the consumer reference.
   - Consumer repo `02_REPLICATION_GUIDE.md` (1,230 lines) covers the same lifecycle using `EDPFabric` as the consumer reference.
   - They diverge in workflow implementations, project structures, promotion engines (`selective_promote.py` vs CLI `promote`), and even naming conventions.
   - **A new user reading both would be confused about which is canonical.**

2. **No bridge document** — No doc says: "Step 1: Read the CLI repo docs to understand the tool. Step 2: Fork the consumer repo template. Step 3: Follow the Replication Guide."

3. **Prerequisites span both repos** — SP creation, capacity setup, and PAT creation are in the consumer Replication Guide. CLI installation and config generation are in the CLI repo. A user must read across both repos to assemble the full prerequisite list.

4. **Consumer repo `_archive/GETTING_STARTED.md`** (931 lines) is dangerously confusing — it uses a completely different architecture (layers: Core/Store/Prepare/Ingest/Orchestrate, `infrastructure.json` config format, `fabric-cicd` Python package, different workflow patterns). A user discovering this file would be led completely astray.

### 3.4 CLI Command-Line

**What exists:**

| Step | Covered? | Where |
|------|----------|-------|
| `fabric-cicd deploy` | ✅ | Guide 01, 02, README |
| `fabric-cicd destroy` | ✅ | Guide 02 |
| `fabric-cicd promote` | ✅ | Guide 02, 10 |
| `fabric-cicd validate` | ✅ | Guide 01 |
| `fabric-cicd onboard` | ✅ | Guide 02, README |
| `fabric-cicd organize-folders` | Partial | Mentioned in workflow YAML; not in user guides |
| CLI flag reference (`--rollback-on-failure`, `--selective`, `--safe`, `--force-branch-workspace`, `--wait-for-git-sync`, `--note`) | Scattered | No single reference page |
| Exit codes (0, 2) | Partial | Guide 10 mentions exit code 2 for safety |
| Error messages and meanings | Partial | Guide 06 troubleshooting covers some |

**Gaps identified:**

1. **No CLI reference page** — there is no `man`-page-style document listing every command, every flag, and every exit code in one place. The closest is Guide 02 (walkthrough style, narrative) and Guide 01 (Makefile targets, not CLI directly).
2. **`organize-folders` undocumented** — This command appears in consumer workflow YAML files but has no user guide entry.
3. **CLI flags are scattered** — `--selective` appears in promote workflow YAML, `--safe` in Guide 10, `--rollback-on-failure` in setup workflow YAML, `--force-branch-workspace` in feature-create workflow YAML, `--wait-for-git-sync` in promote workflow YAML, `--note` in promote workflow YAML. No single reference.
4. **No examples of expected output** — what does a successful `fabric-cicd deploy` print? What does a failed one print? No example output shown anywhere.

---

## 4. Cross-Cutting Gaps

### G1: No Single Start-to-Finish Journey (Critical)

**The core problem**: A user arriving fresh cannot follow a single document from "I have nothing" to "I have a working Fabric CI/CD deployment."

The closest candidates and why they fall short:

| Candidate | Lines | Why it falls short |
|-----------|-------|--------------------|
| Consumer `02_REPLICATION_GUIDE.md` | 1,230 | Best attempt. Covers prerequisites → setup → deploy → verify. **But**: only covers GitHub Actions path; assumes CLI repo is already available; no local/Docker path. |
| CLI `10_Feature_Branch_Workspace_Guide.md` | 1,144 | Covers full lifecycle with workflow YAML. **But**: references a different consumer repo (`fabric_cicd_test_repo`); assumes prerequisites are done. |
| CLI `01_Usage_Guide.md` | 690 | Covers Make targets and scenarios. **But**: starts at "you have the CLI installed"; no prerequisites; ends at "run the command" with no verification. |
| CLI `08_Educational_Guide.md` | 604 | Best conceptual framework ("Three Ways to Work"). **But**: educational/overview — not step-by-step; doesn't cover prerequisites. |

### G2: Two Repos, No Bridge (Critical)

The two-repo model (CLI library + consumer repo) is architecturally sound but documentationally broken:

- **CLI repo docs** never mention the consumer repo concept (except in Guide 10, which references a different consumer repo).
- **Consumer repo docs** reference the CLI repo only as a dependency to install.
- **No document explains**: "You will work with TWO repositories. The CLI repo provides the tool. The consumer repo provides YOUR project configuration and workflows."

### G3: Audience Confusion (High)

Six different guides target different audiences with no routing:

| Guide | Implicit Audience | Explicit Audience Declaration |
|-------|-------------------|-------------------------------|
| Guide 01 (Usage Guide) | Operators, DevOps | None |
| Guide 02 (CLI Walkthrough) | CLI power users | None |
| Guide 05 (Client Tutorial) | Clients, stakeholders | "Client-Facing" in title |
| Guide 08 (Educational Guide) | Learners, new team members | "Educational" in title |
| Guide 10 (Feature Branch Guide) | CI/CD engineers | None |
| Consumer Replication Guide | New teams replicating the setup | Stated in intro |

**No guide says**: "If you are a ___, start with ___."

### G4: Content Overlap (High)

| Topic | Appears in | Maintenance Risk |
|-------|-----------|------------------|
| Quick start / getting started | README, Guide 01, Guide 02, Guide 05, Guide 08, Guide 10, Consumer README, Replication Guide | 8 locations |
| Troubleshooting | Guide 06, Replication Guide §11, E2E Report | 3 locations |
| Blueprint / template info | Guide 03, Guide 07, Guide 08 | 3 locations |
| Feature branch lifecycle | Guide 02, Guide 10, Consumer README, Replication Guide | 4 locations |
| Secrets / env var setup | Guide 01, Guide 10, Consumer README, Replication Guide | 4 locations |

Each overlap creates a risk that content drifts between copies. For example, the `CLI_REPO_REF` version appears as `v1.7.7` in one doc and `v1.7.14` in another.

### G5: Competing CI/CD Guides (High)

| Aspect | CLI Guide 10 | Consumer Replication Guide |
|--------|-------------|---------------------------|
| Reference consumer repo | `fabric_cicd_test_repo` | `EDPFabric` |
| Promotion engine | CLI `fabric-cicd promote` | `selective_promote.py` (REST API) |
| Multi-project support | Not covered | Full coverage (Option A vs B) |
| Prerequisites | Assumes done | Covers SP, capacity, PAT from scratch |
| `git_directory` | Not covered | Full coverage (per-project isolation) |
| `folder_rules` / `organize-folders` | Not covered | Covered in workflow YAML |
| Workspace access (two-tier model) | Not covered | Full coverage |
| Project templates | Not covered | `_templates/standard_data_product/` |

The consumer repo has evolved significantly beyond what Guide 10 documents. Guide 10 is now effectively outdated as a consumer repo setup guide.

### G6: No Decision Guide (Medium)

Users face three key decisions with no documented guidance:

1. **Deployment path**: Local Python vs Docker vs GitHub Actions
   - When is each appropriate? Cost/benefit tradeoffs?

2. **Repo strategy**: Single-project vs multi-project (Option A vs B)
   - Consumer `01_WORKFLOW_OPTIONS.md` covers this well, but only for CI/CD path.

3. **Promotion engine**: CLI `promote` vs `selective_promote.py`
   - Only mentioned in consumer `01_WORKFLOW_OPTIONS.md` with minimal context.

### G7: No Quick-Reference Card (Medium)

Missing: A single page (printable/bookmarkable) with:
- All `fabric-cicd` CLI commands and flags
- All Make targets
- All required env vars / secrets
- All YAML config keys
- Common command sequences for each deployment path

### G8: Missing Verification Steps (Medium)

Almost every guide ends at "run the command" without explaining what success looks like:
- What appears in the Fabric portal after `fabric-cicd deploy`?
- What does the Deployment Pipeline look like?
- How do you confirm Git sync is working?
- What does a successful promotion look like?

The consumer Replication Guide §10 has a verification checklist (the best example), but it's the only place.

### G9: Outdated Content (Low)

- `_archive/GETTING_STARTED.md` (931 lines) uses a completely different architecture. It should have a prominent deprecation banner or be deleted.
- Version references vary: v1.7.7, v1.7.8, v1.7.14 across different docs.
- Guide 10 references `fabric_cicd_test_repo` which has different workflow patterns than the current `EDPFabric` consumer.

---

## 5. Gap Severity Matrix

| ID | Gap | Severity | Impact | Effort to Fix |
|----|-----|----------|--------|---------------|
| G1 | No start-to-finish journey | **Critical** | Users cannot self-serve; every onboarding requires hand-holding | High (new document + restructure) |
| G2 | Two repos, no bridge | **Critical** | Users don't understand the architecture; read wrong docs | Medium (bridge document) |
| G3 | Audience confusion | **High** | Users read wrong guide, waste time, get frustrated | Medium (routing guide + headers) |
| G4 | Content overlap | **High** | Maintenance burden; inconsistency risk; confusing for users | High (consolidation) |
| G5 | Competing CI/CD guides | **High** | Contradictory instructions; users follow outdated patterns | Medium (deprecate one, update other) |
| G6 | No decision guide | **Medium** | Users make wrong deployment path choice; require support | Low (new 1-page doc) |
| G7 | No quick-reference card | **Medium** | Users can't quickly look up commands/flags/vars | Low (new 1-page doc) |
| G8 | Missing verification steps | **Medium** | Users don't know if deployment succeeded | Medium (add to each guide) |
| G9 | Outdated content | **Low** | Confusion if users discover archive files | Low (deprecation banners) |

---

## 6. Harmonisation Plan

### Principle: "One Journey, Multiple Depths"

Replace the current "many overlapping guides" model with a **layered documentation architecture**:

```
Layer 1: ORIENTATION (5 min read)
  "What is this system? Which path do I take? What repo do I need?"

Layer 2: END-TO-END JOURNEY (30-60 min per path)
  "Follow these steps from zero to working deployment."
  One guide per deployment path. No overlap.

Layer 3: DEEP REFERENCE (lookup as needed)
  "Full details on a specific topic."
  CLI reference, config reference, troubleshooting, blueprints.
```

### Action 1: Create a Master Orientation Guide (fixes G1, G2, G3, G6)

**New file**: `docs/00_START_HERE.md` (in BOTH repos, or cross-linked)

Contents:
1. **What is this system?** — 3-paragraph explanation of the CLI + consumer two-repo model
2. **Who are you?** — Audience routing table:
   - "I'm setting up CI/CD for a new Fabric project" → Replication Guide
   - "I'm deploying locally during development" → Local Deployment Guide
   - "I'm building Docker images for CI pipelines" → Docker Guide
   - "I'm exploring what this tool can do" → Educational Guide
   - "I need to troubleshoot a failed deployment" → Troubleshooting Guide
3. **Which deployment path?** — Decision matrix:
   - Local Python: for development, testing, one-off deployments
   - Docker: for reproducible builds, air-gapped environments
   - GitHub Actions: for production CI/CD automation
4. **Prerequisites checklist** — Single canonical list of ALL prerequisites (SP, capacity, PAT, Python, conda, Docker) with links to detailed instructions in the Replication Guide

### Action 2: Create One Canonical End-to-End Guide per Path (fixes G1, G4)

#### Path A: Local Python Deployment Guide (NEW)

**New file**: `docs/01_User_Guides/LOCAL_DEPLOYMENT_GUIDE.md`

Combines content from: Guide 01, Guide 02, Guide 08, README

Structure:
1. Prerequisites (link to master list)
2. Install Python & create conda environment
3. Install the CLI (`pip install -e .` for contributors, `pip install git+...` for consumers)
4. Generate project configuration (link to Guide 03 / Guide 07 for deep dive)
5. Set up `.env` file (walkthrough of `.env.template`)
6. Deploy: `fabric-cicd deploy config.yaml --env dev`
7. Verify in Fabric portal (checklist + expected results)
8. Common next steps (destroy, promote, feature workspace)

#### Path B: Docker Deployment Guide (EXPAND existing Guide 04)

**Update file**: `docs/01_User_Guides/04_Docker_Deployment.md`

Add:
1. Docker installation prerequisites
2. When to choose Docker (decision criteria)
3. Complete worked example from Dockerfile → deploy → verify
4. `.env` file setup for Docker
5. Docker Compose for local development pattern
6. Verification steps

#### Path C: GitHub Actions CI/CD Guide (CONSOLIDATE)

**Canonical guide**: Consumer repo `docs/02_REPLICATION_GUIDE.md` (already 1,230 lines and comprehensive)

Actions:
- **Deprecate CLI Guide 10** — add a banner: "This guide references `fabric_cicd_test_repo`. For the current canonical CI/CD setup guide, see the consumer repo's Replication Guide."
- **Update Consumer Replication Guide** to link back to CLI repo for deep topics (blueprints, config syntax, troubleshooting)
- Ensure all workflow patterns in the consumer repo are documented (including `organize-folders`)

### Action 3: Create CLI Command Reference (fixes G7)

**New file**: `docs/01_User_Guides/CLI_REFERENCE.md`

Structure:
```
## Commands

### fabric-cicd deploy
  Usage: fabric-cicd deploy <config.yaml> --env <env> [options]
  Options:
    --rollback-on-failure    Roll back created items on failure
    --branch <name>          Override Git branch
    --force-branch-workspace Create branch workspace even if exists
  Exit codes: 0 (success), 1 (failure)

### fabric-cicd destroy
  ...

### fabric-cicd promote
  Usage: fabric-cicd promote --pipeline-name <name> --source-stage <stage> [options]
  Options:
    --target-stage <stage>   Target stage (default: auto-infer next)
    --selective              Skip unsupported item types
    --wait-for-git-sync <s>  Wait N seconds for Fabric Git Sync
    --note <text>            Deployment note
  Exit codes: 0 (success), 1 (failure)

### fabric-cicd organize-folders
  ...

### fabric-cicd validate
  ...

### fabric-cicd onboard
  ...

## Environment Variables
  (complete table of all env vars with defaults and descriptions)

## Make Targets
  (complete table from Guide 01, verified against current Makefile)
```

### Action 4: Add Verification Sections to All Guides (fixes G8)

For each deployment path guide, add a "Verify Your Deployment" section:

```markdown
## Verify Your Deployment

After running the deploy command, confirm these in the Fabric portal:

| Check | Where to Look | Expected Result |
|-------|---------------|-----------------|
| Workspace exists | Fabric Portal → Workspaces | `<name>` appears with correct capacity |
| Git sync active | Workspace → Source control | Connected to `main` branch |
| Git directory correct | Workspace → Source control → Settings | Shows `/<project>` |
| Folders created | Workspace → Browse | 8 folders visible |
| Pipeline exists | Deployment Pipelines | Pipeline with 3 stages |
| Principals assigned | Workspace → Manage access | SP + groups listed |
```

### Action 5: Resolve Competing Guides (fixes G5)

1. **CLI Guide 10** (`10_Feature_Branch_Workspace_Guide.md`): Add deprecation banner at top:
   ```
   > ⚠️ **Note**: This guide references `fabric_cicd_test_repo` as the consumer
   > repo template. For the current production-ready consumer repo setup, see the
   > [EDPFabric Replication Guide](link). This guide remains available as a
   > reference for the CLI's feature branch capabilities.
   ```

2. **Consumer Replication Guide** (`02_REPLICATION_GUIDE.md`): Add a "CLI Deep Dive" section linking to CLI repo docs for:
   - Blueprint catalog (Guide 07)
   - Configuration syntax (Guide 03)
   - Troubleshooting (Guide 06)
   - CLI command reference (new)

### Action 6: Clean Up Overlap and Outdated Content (fixes G4, G9)

1. **Archive/deprecate these files** with banners:
   - `_archive/GETTING_STARTED.md` — add: "⚠️ ARCHIVED: This guide uses a legacy architecture. See the [current Replication Guide](link)."
   - `09_From_Local_to_CICD.md` — rename to `HISTORICAL_Local_to_CICD_Migration.md` (valuable for context but not a user guide)
   - `11_Stabilisation_Changelog_Feb2026.md` — move to a `CHANGELOG` or `docs/03_Project_Reports/` (not a user guide)

2. **Reduce overlap by converting to links**: In guides that repeat content available elsewhere, replace duplicated sections with cross-references:
   ```markdown
   ## Prerequisites
   See the [Master Prerequisites Checklist](00_START_HERE.md#prerequisites).
   ```

3. **Version alignment**: Search-and-replace all version references to use the current version (v1.7.14) or use a placeholder that's easy to update globally.

### Action 7: Add Audience Headers to Every Guide (fixes G3)

Every guide should start with a standard header block:

```markdown
> **Audience**: CI/CD Engineers setting up automated Fabric deployments
> **Time**: 45–90 minutes
> **Prerequisites**: Service Principal, Fabric Capacity, GitHub PAT
> **Deployment Path**: GitHub Actions CI/CD
> **Difficulty**: Intermediate
```

---

## 7. Proposed Document Architecture

### CLI Repo (`usf_fabric_cli_cicd/docs/01_User_Guides/`)

```
docs/01_User_Guides/
├── 00_START_HERE.md                  ← NEW: Orientation, routing, decision matrix
├── 01_LOCAL_DEPLOYMENT_GUIDE.md      ← NEW: End-to-end local Python path
├── 02_CLI_REFERENCE.md               ← NEW: Man-page-style command reference
├── 03_Project_Configuration.md       ← KEEP: Config syntax deep reference
├── 04_Docker_Deployment.md           ← EXPAND: Full Docker path
├── 05_Blueprint_Catalog.md           ← KEEP (was 07): Template deep reference
├── 06_Troubleshooting.md             ← KEEP: Combined troubleshooting
├── 07_Educational_Guide.md           ← KEEP (was 08): Conceptual overview
└── archive/
    ├── HISTORICAL_Local_to_CICD.md   ← MOVED from 09 (historical context)
    ├── HISTORICAL_Stabilisation.md   ← MOVED from 11 (changelog)
    ├── SUPERSEDED_Usage_Guide.md     ← MOVED from 01 (superseded by new guides)
    ├── SUPERSEDED_CLI_Walkthrough.md ← MOVED from 02 (superseded by CLI Reference)
    └── SUPERSEDED_Client_Tutorial.md ← MOVED from 05 (merged into Orientation)
```

### Consumer Repo (`edp_fabric_consumer_repo/EDPFabric/docs/`)

```
docs/
├── 00_START_HERE.md                  ← NEW: Consumer-specific orientation
├── 01_WORKFLOW_OPTIONS.md            ← KEEP: Single vs multi-project
├── 02_REPLICATION_GUIDE.md           ← KEEP: Canonical CI/CD end-to-end (enhance with links)
├── 03_E2E_VALIDATION_REPORT.md       ← KEEP: Test evidence
├── 04_QUICK_REFERENCE.md             ← NEW: Secrets, vars, commands cheat sheet
└── archive/
    ├── GETTING_STARTED.md            ← MOVED: Add deprecation banner
    └── E2E_TEST_LOG.md               ← MOVED: Low-value
```

### Cross-Repo Link Map

```
CLI 00_START_HERE ──────────► Consumer 00_START_HERE
                                    │
CLI LOCAL_DEPLOYMENT_GUIDE ◄────────┤ (for local debugging)
CLI Docker_Deployment ◄─────────────┤ (for Docker path)
                                    │
CLI CLI_REFERENCE ◄─────────────────┤ (for command details)
CLI Project_Configuration ◄─────────┤ (for YAML syntax)
CLI Blueprint_Catalog ◄────────────┤ (for template selection)
CLI Troubleshooting ◄──────────────┤ (for debugging)
                                    │
Consumer REPLICATION_GUIDE ◄────────┘ (canonical CI/CD guide)
Consumer WORKFLOW_OPTIONS ◄─── (architecture decision)
```

---

## 8. Implementation Roadmap

### Phase 1: Quick Wins (1-2 days)

| Action | Files | Impact |
|--------|-------|--------|
| Add deprecation banners to archived/outdated files | `_archive/GETTING_STARTED.md`, CLI Guide 09, CLI Guide 11 | Prevents confusion (G9) |
| Add audience headers to all existing guides | All 12 CLI guides + 3 consumer guides | Helps routing (G3) |
| Add verification checklists to existing guides | Guides 01, 02, 04; Consumer Replication Guide | Users know success (G8) |
| Version alignment sweep | All docs | Consistency (G9) |

### Phase 2: New Documents (3-5 days)

| Action | New File | Impact |
|--------|----------|--------|
| Create Master Orientation Guide | CLI `00_START_HERE.md` + Consumer `00_START_HERE.md` | Fixes G1, G2, G3, G6 |
| Create Local Deployment Guide | CLI `01_LOCAL_DEPLOYMENT_GUIDE.md` | Fixes G1 for local path |
| Create CLI Command Reference | CLI `02_CLI_REFERENCE.md` | Fixes G7 |
| Create Consumer Quick Reference | Consumer `04_QUICK_REFERENCE.md` | Fixes G7 |
| Expand Docker Guide | CLI `04_Docker_Deployment.md` | Fixes G1 for Docker path |

### Phase 3: Consolidation (3-5 days)

| Action | Impact |
|--------|--------|
| Deprecate CLI Guide 10 with banner pointing to Consumer Replication Guide | Fixes G5 |
| Replace duplicated sections in all guides with cross-reference links | Fixes G4 |
| Move superseded guides (01, 02, 05, 09, 11) to `archive/` folder | Reduces noise (G4) |
| Update Consumer Replication Guide with back-links to CLI deep-dive docs | Completes G2 bridge |

### Phase 4: Ongoing Maintenance

| Practice | Frequency |
|----------|-----------|
| Version reference audit (search all docs for version strings) | Every release |
| Cross-repo link validation (ensure all links resolve) | Monthly |
| Single-source enforcement (any repeated content must be a link, not a copy) | Every PR review |
| Orientation guide update (new features, new paths) | Quarterly |

---

## Appendix: Files Read During This Audit

### CLI Repo (`usf_fabric_cli_cicd`)
- `docs/01_User_Guides/01_Usage_Guide.md` (690 lines)
- `docs/01_User_Guides/02_CLI_Walkthrough.md` (318 lines)
- `docs/01_User_Guides/03_Project_Configuration.md` (512 lines)
- `docs/01_User_Guides/04_Docker_Deployment.md` (207 lines)
- `docs/01_User_Guides/05_Client_Tutorial.md` (~250 lines)
- `docs/01_User_Guides/06_Troubleshooting.md` (613 lines)
- `docs/01_User_Guides/07_Blueprint_Catalog.md` (835 lines)
- `docs/01_User_Guides/08_Educational_Guide.md` (604 lines)
- `docs/01_User_Guides/09_From_Local_to_CICD.md` (572 lines)
- `docs/01_User_Guides/10_Feature_Branch_Workspace_Guide.md` (1,144 lines)
- `docs/01_User_Guides/11_Stabilisation_Changelog_Feb2026.md` (~500 lines)
- `README.md` (544 lines)

### Consumer Repo (`edp_fabric_consumer_repo/EDPFabric`)
- `README.md` (~400 lines)
- `docs/01_WORKFLOW_OPTIONS.md` (~260 lines)
- `docs/02_REPLICATION_GUIDE.md` (1,230 lines)
- `docs/03_E2E_VALIDATION_REPORT.md` (319 lines)
- `docs/E2E_TEST_LOG.md` (~30 lines)
- `CHANGELOG.md` (~100 lines)
- `_archive/GETTING_STARTED.md` (931 lines — first 200 lines read)
- `_archive/README.md` (~15 lines)
- `.github/workflows/setup-base-workspaces.yml` (141 lines)
- `.github/workflows/promote-dev-to-test.yml` (229 lines)
- `.github/workflows/feature-workspace-create.yml` (152 lines)
- `config/projects/_templates/standard_data_product/base_workspace.yaml` (204 lines — first 100)
- `config/projects/edp/base_workspace.yaml` (132 lines)
- `config/projects/edp/feature_workspace.yaml` (~75 lines)
