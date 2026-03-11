#!/usr/bin/env python3
"""
Unified Onboarding Automation for Fabric Data Products.

Supports two modes:
  - Dev Setup (default): Full bootstrap -- creates Dev, Test,
    and Prod workspaces, creates a Fabric Deployment Pipeline,
    and assigns workspaces to stages.
  - Feature Workspace (--with-feature-branch): Creates an
    isolated workspace per feature branch (phases 1-2 only).

Git Integration Modes:
  - Shared Repo (default): All projects connect to the single
    GIT_REPO_URL from .env.
  - Isolated Repo (--create-repo): Auto-creates a per-project
    repo via GitHub or Azure DevOps API before Phase 1.

Orchestrates:
  Phase 0: [Optional] Git Repo Provisioning (--create-repo)
  Phase 1: Config Generation (via generate_project.py)
  Phase 2: Deploy Dev workspace (Git-connected)
  Phase 3: Create Test workspace (empty, no Git)
  Phase 4: Create Prod workspace (empty, no Git)
  Phase 5: Create Deployment Pipeline (via REST API)
  Phase 6: Assign workspaces to pipeline stages
"""

import argparse
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional, Set

from dotenv import load_dotenv

from usf_fabric_cli.scripts.admin.utilities.init_ado_repo import init_ado_repo
from usf_fabric_cli.scripts.admin.utilities.init_github_repo import init_github_repo
from usf_fabric_cli.scripts.dev.generate_project import generate_project_config

# Load .env so all env-var reads (GITHUB_TOKEN, FABRIC_CAPACITY_ID, etc.) work
# consistently with the rest of the project.
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("onboard")

# Default stages to provision
DEFAULT_STAGES = {"dev", "test", "prod"}


def run_command(command, cwd=None, check=True):
    """Run shell command with logging"""
    cmd_str = " ".join(command)
    logger.info("> Running: %s", cmd_str)
    try:
        result = subprocess.run(
            command, cwd=cwd, check=check, text=True, capture_output=True
        )
        return result
    except subprocess.CalledProcessError as e:
        logger.error("[ERROR] Command failed: %s", e.stderr)
        raise


def _resolve_capacity_id(stage: str) -> str:
    """Resolve the capacity ID for a given stage.

    Uses stage-specific env vars with fallback to FABRIC_CAPACITY_ID.

    Args:
        stage: One of 'dev', 'test', 'prod'.

    Returns:
        The resolved capacity ID string.
    """
    stage_env_map = {
        "test": "TEST_CAPACITY_ID",
        "prod": "PROD_CAPACITY_ID",
    }

    if stage in stage_env_map:
        stage_capacity = os.environ.get(stage_env_map[stage], "").strip()
        if stage_capacity:
            return stage_capacity

    # Fall back to default
    return os.environ.get("FABRIC_CAPACITY_ID", "${FABRIC_CAPACITY_ID}")


def _get_workspace_names(base_name: str) -> dict:
    """Derive Microsoft-convention workspace names for all stages.

    Microsoft recommendation:
      - Dev:  "{name}"
      - Test: "{name} [Test]"
      - Prod: "{name} [Production]"

    Args:
        base_name: The base workspace name (from config generation).

    Returns:
        Dict mapping stage -> workspace name.
    """
    return {
        "dev": base_name,
        "test": f"{base_name} [Test]",
        "prod": f"{base_name} [Production]",
    }


def _get_pipeline_name(org_name: str, project_name: str) -> str:
    """Derive pipeline display name.

    Uses FABRIC_PIPELINE_NAME env var if set, otherwise auto-derives.
    """
    env_name = os.environ.get("FABRIC_PIPELINE_NAME", "").strip()
    if env_name:
        return env_name
    return f"{org_name}-{project_name} Pipeline"


def _enrich_principals(principals: list) -> list:
    """Inject mandatory env-var principals (governance SP + admin).

    Mirrors the injection logic in ConfigManager._to_workspace_config()
    to ensure Test/Prod stages receive the same mandatory principals
    that Dev gets via the full deploy path.
    """
    enriched = list(principals)
    existing_ids = {p.get("id") for p in enriched if p.get("id")}

    admin_id = os.environ.get("ADDITIONAL_ADMIN_PRINCIPAL_ID", "")
    if admin_id and admin_id not in existing_ids and not admin_id.startswith("${"):
        enriched.append(
            {
                "id": admin_id,
                "role": "Admin",
                "description": "Mandatory Additional Admin",
            }
        )
        existing_ids.add(admin_id)

    contributor_id = os.environ.get("ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID", "")
    if (
        contributor_id
        and contributor_id not in existing_ids
        and not contributor_id.startswith("${")
    ):
        enriched.append(
            {
                "id": contributor_id,
                "role": "Contributor",
                "description": "Mandatory Additional Contributor",
            }
        )

    return enriched


def _create_empty_workspace(
    workspace_name: str,
    capacity_id: str,
    description: str,
    principals: list,
    dry_run: bool = False,
) -> Optional[str]:
    """Create an empty workspace (no Git, no folders, no items) for Test/Prod.

    Uses FabricCLIWrapper directly for efficiency.

    Args:
        workspace_name: Display name for the workspace.
        capacity_id: Fabric capacity ID.
        description: Workspace description.
        principals: List of principal dicts from config.
        dry_run: If True, simulate.

    Returns:
        workspace_id if created, None on failure or dry-run.
    """
    if dry_run:
        logger.info("  (Dry Run) Would create workspace: %s", workspace_name)
        logger.info("  (Dry Run) Capacity: %s", capacity_id)
        return None

    try:
        from usf_fabric_cli.services.fabric_wrapper import FabricCLIWrapper
        from usf_fabric_cli.utils.config import get_environment_variables

        env_vars = get_environment_variables()
        fabric = FabricCLIWrapper(env_vars["FABRIC_TOKEN"])

        # Create workspace
        result = fabric.create_workspace(
            name=workspace_name,
            capacity_name=capacity_id,
            description=description,
        )

        if not result["success"]:
            error_msg = str(result.get("error", "")).lower()
            data = result.get("data")
            error_code = ""
            if isinstance(data, dict):
                error_code = data.get("errorCode", "")

            # Retry without capacity if capacity not found
            if (
                "capacity" in error_msg
                or "entitynotfound" in error_msg
                or "could not be found" in error_msg
                or error_code == "EntityNotFound"
            ) and "insufficientpermissionsovercapacity" not in error_msg:
                logger.warning(
                    "  [!] Capacity assignment failed. Retrying without capacity..."
                )
                result = fabric.create_workspace(
                    name=workspace_name,
                    capacity_name=None,
                    description=description,
                )

        if not result["success"]:
            logger.error(
                "  [ERROR] Failed to create workspace: %s",
                result.get("error"),
            )
            return None

        workspace_id = result.get("workspace_id")
        logger.info(
            "  [OK] Workspace created: %s (ID: %s)",
            workspace_name,
            workspace_id,
        )

        # Add principals
        if principals:
            for principal in principals:
                principal_id_raw = principal.get("id", "")
                if not principal_id_raw or principal_id_raw.startswith("${"):
                    continue  # Skip unresolved env var placeholders

                principal_ids = (
                    [pid.strip() for pid in principal_id_raw.split(",")]
                    if "," in principal_id_raw
                    else [principal_id_raw]
                )

                for pid in principal_ids:
                    if not pid:
                        continue
                    p_result = fabric.add_workspace_principal(
                        workspace_name, pid, principal.get("role", "Member")
                    )
                    if p_result["success"]:
                        logger.info(
                            "  [OK] Principal added: %s (%s)",
                            pid,
                            principal.get("role"),
                        )

        return workspace_id

    except (
        ValueError,
        KeyError,
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as e:
        logger.error("  [ERROR] Workspace creation failed: %s", e)
        return None


def _create_deployment_pipeline(
    pipeline_name: str,
    workspace_ids: dict,
    dry_run: bool = False,
) -> bool:
    """Create a Deployment Pipeline and assign workspaces to stages.

    Args:
        pipeline_name: Display name for the pipeline.
        workspace_ids: Dict mapping stage name ('dev','test','prod') -> workspace_id.
        dry_run: If True, simulate.

    Returns:
        True on success, False on failure.
    """
    if dry_run:
        logger.info("  (Dry Run) Would create pipeline: %s", pipeline_name)
        for stage, ws_id in workspace_ids.items():
            logger.info("  (Dry Run) Would assign %s -> %s", stage, ws_id)
        return True

    try:
        from usf_fabric_cli.services.deployment_pipeline import (
            FabricDeploymentPipelineAPI,
        )
        from usf_fabric_cli.utils.config import get_environment_variables

        env_vars = get_environment_variables()
        api = FabricDeploymentPipelineAPI(access_token=env_vars["FABRIC_TOKEN"])

        # Check for existing pipeline
        existing = api.get_pipeline_by_name(pipeline_name)
        if existing:
            pipeline_id = existing["id"]
            logger.info(
                "  [i] Pipeline already exists: %s (ID: %s)", pipeline_name, pipeline_id
            )
        else:
            # Create pipeline
            result = api.create_pipeline(
                display_name=pipeline_name,
                description=(
                    "Deployment pipeline for content promotion"
                    " (Dev \u2192 Test \u2192 Prod)"
                ),
            )

            if not result["success"]:
                logger.error(
                    "  [ERROR] Failed to create pipeline: %s",
                    result.get("error"),
                )
                return False

            pipeline_id = result["pipeline"]["id"]
            logger.info(
                "  [OK] Pipeline created: %s (ID: %s)", pipeline_name, pipeline_id
            )

        # Get pipeline stages
        stages_result = api.get_pipeline_stages(pipeline_id)
        if not stages_result["success"]:
            logger.error(
                "  [ERROR] Failed to get pipeline stages: %s",
                stages_result.get("error"),
            )
            return False

        stages = stages_result["stages"]

        # Map stage display names to IDs
        stage_name_map = {
            "dev": "Development",
            "test": "Test",
            "prod": "Production",
        }

        for stage_key, ws_id in workspace_ids.items():
            if not ws_id:
                logger.warning(
                    "  [!] No workspace ID for %s. Skipping assignment.", stage_key
                )
                continue

            target_display_name = stage_name_map.get(stage_key)
            stage_obj = next(
                (s for s in stages if s["displayName"] == target_display_name),
                None,
            )

            if not stage_obj:
                logger.warning(
                    "  [!] Stage '%s' not found in pipeline.", target_display_name
                )
                continue

            assign_result = api.assign_workspace_to_stage(
                pipeline_id=pipeline_id,
                stage_id=stage_obj["id"],
                workspace_id=ws_id,
            )

            if assign_result["success"]:
                logger.info(
                    "  [OK] Assigned workspace -> %s stage",
                    target_display_name,
                )
            else:
                logger.error(
                    "  [ERROR] Failed to assign %s: %s",
                    stage_key,
                    assign_result.get("error"),
                )

        return True

    except (ValueError, KeyError, OSError, RuntimeError) as e:
        logger.error("  [ERROR] Pipeline setup failed: %s", e)
        return False


def _provision_repo(
    provider: str,
    owner: str,
    repo_name: str,
    *,
    ado_project: Optional[str] = None,
    branch: str = "main",
) -> Optional[str]:
    """Create a Git repo via GitHub or ADO API.

    Returns:
        Clone URL on success, ``None`` on failure.
    """
    import os

    if provider == "github":
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            logger.error(
                "GITHUB_TOKEN env var is required "
                "for --create-repo --git-provider github"
            )
            return None

        return init_github_repo(
            owner,
            repo_name,
            token,
            branch=branch,
        )

    elif provider == "ado":
        if not ado_project:
            logger.error("--ado-project is required when " "--git-provider ado")
            return None

        return init_ado_repo(
            owner,
            ado_project,
            repo_name,
            branch=branch,
        )

    else:
        logger.error("Unknown git provider: '%s'. Use 'github' or 'ado'.", provider)
        return None


def onboard_project(
    org_name: str,
    project_name: str,
    template: str,
    capacity_id: str,
    git_repo: Optional[str] = None,
    dry_run: bool = False,
    with_feature_branch: bool = False,
    stages: Optional[Set[str]] = None,
    pipeline_name_override: Optional[str] = None,
    test_workspace_name: Optional[str] = None,
    prod_workspace_name: Optional[str] = None,
    create_repo: bool = False,
    git_provider: str = "github",
    git_owner: Optional[str] = None,
    ado_project: Optional[str] = None,
):
    """Execute end-to-end onboarding workflow.

    Args:
        org_name: Organization name.
        project_name: Project name.
        template: Blueprint template name.
        capacity_id: Fabric capacity ID.
        git_repo: Git repository URL.
        dry_run: If True, simulate actions without executing.
        with_feature_branch: If True, creates an isolated
            feature workspace (phases 1-2 only).
        stages: Set of stages to provision.
        pipeline_name_override: Custom pipeline display name.
        test_workspace_name: Custom Test workspace name.
        prod_workspace_name: Custom Prod workspace name.
        create_repo: If True, auto-create a project-specific
            Git repo before config generation.
        git_provider: ``github`` (default) or ``ado``.
        git_owner: GitHub owner/org or ADO org name.
        ado_project: ADO project (required for ADO provider).
    """

    if stages is None:
        stages = DEFAULT_STAGES.copy()

    if with_feature_branch:
        mode = "Feature Workspace"
        total_steps = 3
    else:
        # Count steps dynamically based on requested stages
        total_steps = 1  # Config generation
        if create_repo:
            total_steps += 1  # Phase 0: repo provisioning
        if "dev" in stages:
            total_steps += 1  # Dev deploy
        if "test" in stages:
            total_steps += 1  # Test workspace
        if "prod" in stages:
            total_steps += 1  # Prod workspace
        # Pipeline + stage assignment
        if stages & {"test", "prod"}:
            total_steps += 2
        git_mode = "Isolated" if create_repo else "Shared"
        mode = f"Full Bootstrap ({', '.join(sorted(stages))}) " f"[Git: {git_mode}]"

    logger.info("Starting onboarding for %s / %s", org_name, project_name)
    logger.info("Template: %s", template)
    logger.info("Mode: %s", mode)

    current_step = 0

    # --- Phase 0: Git Repo Provisioning (optional) ----------------
    if create_repo and not with_feature_branch:
        current_step += 1
        logger.info(
            "\n[%s/%s] Provisioning Git repository (%s)...",
            current_step,
            total_steps,
            git_provider,
        )

        if not git_owner:
            logger.error("--git-owner is required when using --create-repo")
            return False

        org_slug = org_name.lower().replace(" ", "_")
        project_slug = project_name.lower().replace(" ", "_")
        repo_name = f"{org_slug}-{project_slug}".replace("_", "-")

        if dry_run:
            logger.info(
                "  (Dry Run) Would create %s repo: %s/%s",
                git_provider,
                git_owner,
                repo_name,
            )
            git_repo = f"https://placeholder/{repo_name}"
        else:
            git_repo = _provision_repo(
                git_provider,
                git_owner,
                repo_name,
                ado_project=ado_project,
            )
            if not git_repo:
                logger.error("Repo provisioning failed")
                return False
            logger.info("  [OK] Repo URL: %s", git_repo)
            # Show browsable web URL for user convenience
            web_url = git_repo.removesuffix(".git")
            logger.info("  Open in browser: %s", web_url)

    # --- Phase 1: Generate Configuration --------------------------
    current_step += 1
    logger.info("\n[%s/%s] Generating Configuration...", current_step, total_steps)
    try:
        if dry_run:
            logger.info("  (Dry Run) calling generate_project_config...")
            org_slug = org_name.lower().replace(" ", "_")
            project_slug = project_name.lower().replace(" ", "_")
            config_path = Path(f"config/projects/{org_slug}" f"/{project_slug}.yaml")
        else:
            config_path = generate_project_config(
                org_name,
                project_name,
                template,
                capacity_id,
                git_repo or "",
            )
    except (ValueError, OSError, RuntimeError) as e:
        logger.error("Failed to generate config: %s", e)
        return False

    # Load generated config for principal info (used in phases 3-4)
    principals = []
    if not dry_run and config_path and Path(config_path).exists():
        try:
            import yaml

            with open(config_path, "r") as f:
                loaded_config = yaml.safe_load(f)
            principals = loaded_config.get("principals", [])
        except (OSError, ValueError):
            logger.warning("  [!] Could not load principals from config.")

    # Inject mandatory env-var principals (governance SP + admin user)
    principals = _enrich_principals(principals)

    # Derive workspace names
    org_slug = org_name.lower().replace(" ", "_")
    project_slug = project_name.lower().replace(" ", "_")
    base_workspace_name = f"{org_slug}-{project_slug}".replace("_", "-")
    ws_names = _get_workspace_names(base_workspace_name)

    # Apply custom name overrides
    if test_workspace_name:
        ws_names["test"] = test_workspace_name
    if prod_workspace_name:
        ws_names["prod"] = prod_workspace_name

    branch_name = None  # Used only in feature-branch mode
    workspace_ids = {}  # Collect workspace IDs for pipeline assignment

    # --- Phase 2 (Feature mode): Create Feature Branch ------------
    if with_feature_branch:
        current_step += 1
        logger.info(
            "\n[%s/%s] Initializing Git Feature Branch...", current_step, total_steps
        )
        branch_name = f"feature/{project_name.lower().replace(' ', '-')}"

        if dry_run:
            logger.info("  (Dry Run) Would execute: git checkout -b %s", branch_name)
        else:
            try:
                result = run_command(
                    ["git", "branch", "--list", branch_name], check=False
                )
                if branch_name in result.stdout:
                    logger.warning(
                        "  Branch %s already exists. Checking out...", branch_name
                    )
                    run_command(["git", "checkout", branch_name])
                else:
                    run_command(["git", "checkout", "-b", branch_name])

                logger.info("  [OK] On branch: %s", branch_name)

                # Push branch to remote (Required for Fabric to see it)
                logger.info("  Pushing branch to remote...")
                run_command(["git", "push", "-u", "origin", branch_name])
                logger.info("  [OK] Branch pushed to origin")

            except (subprocess.SubprocessError, OSError) as e:
                logger.error("Failed to manage git branch: %s", e)
                return False

    # --- Phase 2 (Bootstrap mode): Deploy Dev Workspace -----------
    if "dev" in stages and not with_feature_branch:
        current_step += 1
        logger.info("\n[%s/%s] Deploying Dev Workspace...", current_step, total_steps)
        logger.info("  Workspace: %s", ws_names["dev"])
        logger.info("  Connected to main branch via Git")

        deploy_cmd = [
            "python3",
            "-m",
            "usf_fabric_cli.cli",
            "deploy",
            str(config_path),
            "--env",
            "dev",
        ]

        if dry_run:
            logger.info("  (Dry Run) Would execute: %s", " ".join(deploy_cmd))
        else:
            try:
                subprocess.run(deploy_cmd, check=True)
                logger.info("  [OK] Dev workspace deployed")

                # Capture workspace ID for pipeline assignment
                # Look up by name via Fabric REST API
                try:
                    import requests as req

                    from usf_fabric_cli.utils.config import get_environment_variables

                    env_vars = get_environment_variables()
                    token = env_vars["FABRIC_TOKEN"]
                    headers = {
                        "Authorization": f"Bearer {token}",
                    }
                    resp = req.get(
                        "https://api.fabric.microsoft.com" "/v1/workspaces",
                        headers=headers,
                        timeout=30,
                    )
                    if resp.ok:
                        for ws in resp.json().get("value", []):
                            if ws.get("displayName") == (ws_names["dev"]):
                                workspace_ids["dev"] = ws["id"]
                                break
                except (ValueError, KeyError, OSError, RuntimeError):
                    logger.warning(
                        "  [!] Could not retrieve Dev workspace ID for pipeline."
                    )

            except subprocess.CalledProcessError:
                logger.error("  [ERROR] Dev workspace deployment failed.")
                return False

    # --- Feature branch deploy (alternative to full bootstrap) ----
    if with_feature_branch:
        assert branch_name is not None, "branch_name must be set for feature mode"
        current_step += 1
        logger.info(
            "\n[%s/%s] Deploying Feature Workspace...", current_step, total_steps
        )

        deploy_cmd = [
            "python3",
            "-m",
            "usf_fabric_cli.cli",
            "deploy",
            str(config_path),
            "--env",
            "dev",
            "--branch",
            branch_name,
            "--force-branch-workspace",
        ]
        logger.info("  Creating feature workspace for branch: %s", branch_name)

        if dry_run:
            logger.info("  (Dry Run) Would execute: %s", " ".join(deploy_cmd))
            return True
        else:
            try:
                subprocess.run(deploy_cmd, check=True)
            except subprocess.CalledProcessError:
                logger.error("  [ERROR] Feature workspace deployment failed.")
                return False

        logger.info("\n[OK] Onboarding Complete!")
        logger.info("Config:    %s", config_path)
        logger.info("Branch:    %s", branch_name)
        logger.info("Workspace: feature-isolated (branch-specific)")
        return True

    # --- Phase 3: Create Test Workspace ---------------------------
    if "test" in stages:
        current_step += 1
        logger.info("\n[%s/%s] Creating Test Workspace...", current_step, total_steps)
        logger.info("  Workspace: %s", ws_names["test"])
        logger.info("  [i] Empty workspace (content delivered via pipeline promotion)")

        test_capacity = _resolve_capacity_id("test")
        test_ws_id = _create_empty_workspace(
            workspace_name=ws_names["test"],
            capacity_id=test_capacity,
            description=f"Test environment for {org_name} {project_name}",
            principals=principals,
            dry_run=dry_run,
        )
        if test_ws_id:
            workspace_ids["test"] = test_ws_id

    # --- Phase 4: Create Prod Workspace ---------------------------
    if "prod" in stages:
        current_step += 1
        logger.info(
            "\n[%s/%s] Creating Production Workspace...", current_step, total_steps
        )
        logger.info("  Workspace: %s", ws_names["prod"])
        logger.info("  [i] Empty workspace (content delivered via pipeline promotion)")

        prod_capacity = _resolve_capacity_id("prod")
        prod_ws_id = _create_empty_workspace(
            workspace_name=ws_names["prod"],
            capacity_id=prod_capacity,
            description=f"Production environment for {org_name} {project_name}",
            principals=principals,
            dry_run=dry_run,
        )
        if prod_ws_id:
            workspace_ids["prod"] = prod_ws_id

    # --- Phase 5-6: Create Pipeline & Assign Stages --------------
    if stages & {"test", "prod"}:
        # Phase 5: Create Pipeline
        current_step += 1
        pipeline_name = pipeline_name_override or _get_pipeline_name(
            org_name, project_name
        )
        logger.info(
            "\n[%s/%s] Creating Deployment Pipeline...", current_step, total_steps
        )
        logger.info("  Pipeline: %s", pipeline_name)

        # Phase 6: Assign Stages
        current_step += 1
        logger.info(
            "\n[%s/%s] Assigning Workspaces to Stages...", current_step, total_steps
        )

        if dry_run:
            logger.info("  (Dry Run) Would create pipeline: %s", pipeline_name)
            for stage_key in sorted(stages):
                logger.info(
                    "  (Dry Run) Would assign %s -> %s stage",
                    ws_names.get(stage_key, "N/A"),
                    stage_key.capitalize(),
                )
        else:
            success = _create_deployment_pipeline(
                pipeline_name=pipeline_name,
                workspace_ids=workspace_ids,
                dry_run=dry_run,
            )
            if not success:
                logger.error("  [ERROR] Pipeline setup failed.")
                logger.info(
                    "  [TIP] Tip: You can create the pipeline manually in the "
                    "Fabric Portal and assign workspaces there."
                )

    # --- Summary --------------------------------------------------
    logger.info("\n[OK] Onboarding Complete!")
    logger.info("Config:     %s", config_path)
    logger.info("Stages:     %s", ", ".join(sorted(stages)))
    if "dev" in stages:
        logger.info("Dev:        %s (connected to main)", ws_names["dev"])
    if "test" in stages:
        logger.info("Test:       %s (empty, pipeline-fed)", ws_names["test"])
    if "prod" in stages:
        logger.info("Production: %s (empty, pipeline-fed)", ws_names["prod"])
    if stages & {"test", "prod"}:
        pipeline_display = pipeline_name_override or _get_pipeline_name(
            org_name, project_name
        )
        logger.info("Pipeline:   %s", pipeline_display)

    return True


def main():
    parser = argparse.ArgumentParser(description="Onboard a new Fabric Data Product")
    parser.add_argument("--org", required=True, help="Organization Name")
    parser.add_argument("--project", required=True, help="Project Name")
    parser.add_argument(
        "--template",
        default="medallion",
        help="Blueprint template (default: medallion)",
    )
    parser.add_argument(
        "--capacity-id",
        default="${FABRIC_CAPACITY_ID}",
        help="Capacity ID placeholder",
    )
    parser.add_argument(
        "--repo", default="${GIT_REPO_URL}", help="Git Repo URL placeholder"
    )
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions")
    parser.add_argument(
        "--with-feature-branch",
        action="store_true",
        default=False,
        help=(
            "Create an isolated feature workspace connected to a new feature branch. "
            "Without this flag, a full bootstrap (Dev+Test+Prod+Pipeline) is created."
        ),
    )
    parser.add_argument(
        "--stages",
        default="dev,test,prod",
        help=(
            "Comma-separated list of stages to provision. "
            "Default: dev,test,prod. Example: --stages dev,test"
        ),
    )
    parser.add_argument(
        "--pipeline-name",
        default=None,
        help="Custom Deployment Pipeline name (auto-derived if not set)",
    )
    parser.add_argument(
        "--test-workspace-name",
        default=None,
        help="Custom Test workspace name (default: '{name} [Test]')",
    )
    parser.add_argument(
        "--prod-workspace-name",
        default=None,
        help=("Custom Prod workspace name " "(default: '{name} [Production]')"),
    )
    # -- Git Repo Isolation --
    parser.add_argument(
        "--create-repo",
        action="store_true",
        default=False,
        help=(
            "Auto-create a project-specific Git repo "
            "before config generation (isolated mode)."
        ),
    )
    parser.add_argument(
        "--git-provider",
        default="github",
        choices=["github", "ado"],
        help=("Git provider for --create-repo. " "Default: github."),
    )
    parser.add_argument(
        "--git-owner",
        default=None,
        help=("GitHub owner/org or ADO org name " "(required with --create-repo)."),
    )
    parser.add_argument(
        "--ado-project",
        default=None,
        help=("Azure DevOps project name " "(required with --git-provider ado)."),
    )

    args = parser.parse_args()

    # Parse stages
    requested_stages = {s.strip().lower() for s in args.stages.split(",")}
    valid_stages = {"dev", "test", "prod"}
    invalid = requested_stages - valid_stages
    if invalid:
        logger.error("Invalid stage(s): %s. Valid: %s", invalid, valid_stages)
        return 1

    success = onboard_project(
        args.org,
        args.project,
        args.template,
        args.capacity_id,
        args.repo,
        args.dry_run,
        args.with_feature_branch,
        stages=requested_stages,
        pipeline_name_override=args.pipeline_name,
        test_workspace_name=args.test_workspace_name,
        prod_workspace_name=args.prod_workspace_name,
        create_repo=args.create_repo,
        git_provider=args.git_provider,
        git_owner=args.git_owner,
        ado_project=args.ado_project,
    )

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
