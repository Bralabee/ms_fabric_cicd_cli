"""
Microsoft Fabric CLI - Command-line interface for deployment automation.

This module provides the CLI entry points using Typer. The actual deployment
logic is in services/deployer.py (FabricDeployer class).
"""

import logging
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console

from usf_fabric_cli.exceptions import FabricCLIError, handle_cli_error
from usf_fabric_cli.scripts.admin.bulk_destroy import bulk_destroy as bulk_destroy_fn
from usf_fabric_cli.scripts.admin.utilities.init_github_repo import (
    init_github_repo as init_github_repo_fn,
)
from usf_fabric_cli.scripts.dev.generate_project import generate_project_config
from usf_fabric_cli.scripts.dev.onboard import onboard_project
from usf_fabric_cli.services.deployer import FabricDeployer
from usf_fabric_cli.services.fabric_wrapper import FabricCLIWrapper, FabricDiagnostics
from usf_fabric_cli.utils.config import ConfigManager, get_environment_variables

# Ensure .env vars are loaded for all CLI commands, including those that
# read env vars directly (e.g., init-github-repo reads GITHUB_TOKEN).
load_dotenv(encoding="utf-8")

logger = logging.getLogger(__name__)
logging.getLogger("azure").setLevel(logging.WARNING)


app = typer.Typer(help="Fabric CLI CI/CD - Enterprise Deployment Framework")
console = Console()


@app.command()
def deploy(
    config: str = typer.Argument(..., help="Path to configuration file"),
    environment: Optional[str] = typer.Option(
        None, "--env", "-e", help="Environment (dev/staging/prod)"
    ),
    branch: Optional[str] = typer.Option(
        None, "--branch", "-b", help="Git branch to use"
    ),
    force_branch_workspace: bool = typer.Option(
        False,
        "--force-branch-workspace",
        help="Create separate workspace for feature branch",
    ),
    rollback_on_failure: bool = typer.Option(
        False,
        "--rollback-on-failure",
        help="Automatically delete created items if deployment fails",
    ),
    validate_only: bool = typer.Option(
        False, "--validate-only", help="Only validate configuration"
    ),
    diagnose: bool = typer.Option(
        False, "--diagnose", help="Run diagnostic checks before deployment"
    ),
):
    """Deploy Fabric workspace based on configuration"""

    if diagnose:
        console.print("[blue]Running pre-flight diagnostics...[/blue]")
        try:
            # We can't use the diagnose command directly as it's a separate command
            # So we'll instantiate the diagnostics class here
            env_vars = get_environment_variables(validate_vars=True)
            fabric = FabricCLIWrapper(env_vars["FABRIC_TOKEN"])
            diagnostics = FabricDiagnostics(fabric)

            cli_check = diagnostics.validate_fabric_cli_installation()
            if not cli_check["success"]:
                handle_cli_error(
                    "validate Fabric CLI installation",
                    cli_check["error"],
                    "Ensure the Microsoft Fabric CLI is installed"
                    " and available in your PATH.",
                )

            auth_check = diagnostics.validate_authentication()
            if not auth_check["success"]:
                handle_cli_error(
                    "validate authentication",
                    auth_check["error"],
                    "Run 'fab auth login' to authenticate with Fabric,"
                    " or check your configuration.",
                )

            console.print("[green][OK] Pre-flight checks passed[/green]")
        except (FabricCLIError, KeyError, ValueError) as e:
            handle_cli_error(
                "run diagnostics",
                e,
                "Check your internet connection and authentication tokens.",
            )

    if validate_only:
        console.print("[blue]Validating configuration...[/blue]")
        try:
            config_manager = ConfigManager(config, validate_env=False)
            config_manager.load_config(environment)
            console.print("[green][OK] Configuration is valid[/green]")
            return
        except (ValueError, FileNotFoundError, KeyError) as e:
            handle_cli_error(
                "validate configuration",
                e,
                "Verify that your configuration file and environment"
                " variables are correctly set.",
            )

    try:
        deployer = FabricDeployer(config, environment)
        success = deployer.deploy(branch, force_branch_workspace, rollback_on_failure)

        if not success:
            raise typer.Exit(1)

    except (FabricCLIError, ValueError, KeyError, FileNotFoundError) as e:
        handle_cli_error(
            "deploy workspace",
            e,
            "Review the configuration and ensure all referenced files"
            " exist and are accessible.",
        )


@app.command()
def validate(
    config: str = typer.Argument(..., help="Path to configuration file"),
    environment: Optional[str] = typer.Option(None, "--env", "-e", help="Environment"),
):
    """Validate configuration file"""

    try:
        config_manager = ConfigManager(config, validate_env=False)
        workspace_config = config_manager.load_config(environment)

        console.print("[green][OK] Configuration is valid[/green]")
        console.print(f"Workspace: {workspace_config.name}")
        console.print(f"Capacity ID: {workspace_config.capacity_id}")
        console.print(f"Folders: {', '.join(workspace_config.folders or [])}")
        console.print(f"Lakehouses: {len(workspace_config.lakehouses or [])}")
        console.print(f"Warehouses: {len(workspace_config.warehouses or [])}")
        console.print(f"Notebooks: {len(workspace_config.notebooks or [])}")

        # Validate folder references -- check that items and folder_rules
        # reference folders that actually exist in the folders list
        defined_folders = set(workspace_config.folders or [])
        warnings = []

        # Check item folder references
        for section_name, items in [
            ("lakehouses", workspace_config.lakehouses or []),
            ("warehouses", workspace_config.warehouses or []),
            ("notebooks", workspace_config.notebooks or []),
            ("pipelines", workspace_config.pipelines or []),
            ("semantic_models", workspace_config.semantic_models or []),
            ("resources", workspace_config.resources or []),
        ]:
            for item in items:
                folder_ref = item.get("folder", "")
                if folder_ref and folder_ref not in defined_folders:
                    item_name = item.get("name", "unnamed")
                    warnings.append(
                        f"{section_name}.{item_name} references folder "
                        f"'{folder_ref}' which is not in folders list"
                    )

        # Check folder_rules references
        for rule in workspace_config.folder_rules or []:
            folder_ref = rule.get("folder", "")
            rule_type = rule.get("type", "unknown")
            if folder_ref and folder_ref not in defined_folders:
                warnings.append(
                    f"folder_rules[type={rule_type}] references folder "
                    f"'{folder_ref}' which is not in folders list"
                )

        if warnings:
            console.print(
                f"\n[yellow][!] {len(warnings)} folder reference warning(s):[/yellow]"
            )
            for w in warnings:
                console.print(f"  [yellow]- {w}[/yellow]")
        else:
            console.print("[green][OK] All folder references are valid[/green]")

    except (ValueError, FileNotFoundError, KeyError) as e:
        handle_cli_error(
            "validate configuration",
            e,
            "Ensure the config file is valid JSON/YAML and the environment exists.",
        )


@app.command()
def diagnose():
    """Run diagnostic checks"""

    console.print("[blue]Running diagnostic checks...[/blue]")

    try:
        env_vars = get_environment_variables(validate_vars=True)
        fabric = FabricCLIWrapper(env_vars["FABRIC_TOKEN"])
        diagnostics = FabricDiagnostics(fabric)

        # Check Fabric CLI installation
        cli_check = diagnostics.validate_fabric_cli_installation()
        if cli_check["success"]:
            console.print(f"[green][OK] Fabric CLI: {cli_check['version']}[/green]")
        else:
            handle_cli_error(
                "validate Fabric CLI installation",
                cli_check["error"],
                "Install the Microsoft Fabric CLI and ensure it's in your PATH.",
            )

        # Check authentication
        auth_check = diagnostics.validate_authentication()
        if auth_check["success"]:
            console.print("[green][OK] Authentication: Valid[/green]")
        else:
            handle_cli_error(
                "validate authentication",
                auth_check["error"],
                "Run 'fab auth login' to authenticate with Microsoft Fabric.",
            )

        # Check API connectivity
        api_check = diagnostics.validate_api_connectivity()
        if api_check["success"]:
            console.print(
                f"[green][OK] API Connectivity: {api_check['workspaces_count']} "
                "workspaces accessible[/green]"
            )
        else:
            console.print(f"[red][ERROR] API Connectivity: {api_check['error']}[/red]")

        console.print("\n[green]All diagnostic checks completed![/green]")

    except (FabricCLIError, KeyError, ValueError) as e:
        handle_cli_error(
            "run diagnostics",
            e,
            "Check your network connection and verify authentication"
            " tokens are active.",
        )


@app.command()
def destroy(
    config: str = typer.Argument(..., help="Path to configuration file"),
    environment: Optional[str] = typer.Option(
        None, "--env", "-e", help="Environment (dev/staging/prod)"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force deletion without confirmation"
    ),
    workspace_name_override: Optional[str] = typer.Option(
        None,
        "--workspace-name-override",
        help="Override workspace name (e.g. for branch-specific feature workspaces)",
    ),
    branch: Optional[str] = typer.Option(
        None,
        "--branch",
        "-b",
        help=(
            "Git branch name -- derives workspace name using "
            "get_workspace_name_from_branch() (overrides "
            "--workspace-name-override)"
        ),
    ),
    feature_prefix: str = typer.Option(
        "[F]",
        "--feature-prefix",
        help="Feature workspace name prefix (use '' to disable)",
    ),
    safe: bool = typer.Option(
        True,
        "--safe/--no-safe",
        help=(
            "Safety mode: refuse to delete workspaces that contain "
            "Fabric items (default: enabled). Prevents accidental "
            "deletion of populated workspaces."
        ),
    ),
    force_destroy_populated: bool = typer.Option(
        False,
        "--force-destroy-populated",
        help=(
            "Override safety mode -- delete workspace even if it "
            "contains Fabric items. Use with caution."
        ),
    ),
    cleanup_repo: bool = typer.Option(
        False,
        "--cleanup-repo",
        help=(
            "Remove local repo files after workspace destruction: "
            "config directory, git sync directory, and workflow "
            "choice-list entries. Requires --force-destroy-populated."
        ),
    ),
):
    """Destroy Fabric workspace based on configuration.

    By default, safety mode is ON: workspaces containing Fabric items
    (lakehouses, notebooks, pipelines, etc.) will NOT be deleted.
    Use --force-destroy-populated to override this protection.
    """

    workspace_name = workspace_name_override  # Pre-initialize for error handler
    try:
        config_manager = ConfigManager(config)
        workspace_config = config_manager.load_config(environment)

        # Derive workspace name priority:
        # --branch -> --workspace-name-override -> config default
        if branch:
            from usf_fabric_cli.services.git_integration import GitFabricIntegration

            base_name = workspace_config.name
            workspace_name = GitFabricIntegration.get_workspace_name_from_branch(
                base_workspace_name=base_name,
                branch=branch,
                feature_prefix=feature_prefix,
            )
            console.print(
                f"[blue]Branch '{branch}' -> workspace: {workspace_name}[/blue]"
            )
        elif workspace_name_override:
            workspace_name = workspace_name_override
        else:
            workspace_name = workspace_config.name

        if not force:
            confirm = typer.confirm(
                f"Are you sure you want to destroy workspace '{workspace_name}'?"
            )
            if not confirm:
                console.print("[yellow]Aborted.[/yellow]")
                raise typer.Exit(0)

        # Determine effective safe mode: --force-destroy-populated overrides --safe
        effective_safe = safe and not force_destroy_populated

        console.print(f"[red]Destroying workspace: {workspace_name}[/red]")
        if effective_safe:
            console.print(
                "[blue][SAFETY] Safety mode ON -- populated workspaces "
                "will be protected[/blue]"
            )

        env_vars = get_environment_variables(validate_vars=True)
        fabric = FabricCLIWrapper(env_vars["FABRIC_TOKEN"])

        # -- Tear down deployment pipeline first (if configured) ----
        # Fabric refuses to delete workspaces connected to ALM pipelines.
        # When force flags are set, automatically unassign + delete the
        # pipeline before attempting workspace deletion.
        dp_config = workspace_config.deployment_pipeline
        if force_destroy_populated and dp_config:
            pipeline_name = dp_config.get("pipeline_name")
            if pipeline_name:
                from usf_fabric_cli.services.deployment_pipeline import (
                    FabricDeploymentPipelineAPI,
                )

                pipeline_api = FabricDeploymentPipelineAPI(
                    env_vars["FABRIC_TOKEN"],
                )
                pipeline = pipeline_api.get_pipeline_by_name(pipeline_name)
                if pipeline:
                    pipeline_id = pipeline["id"]
                    console.print(
                        f"[yellow]Tearing down pipeline: "
                        f"{pipeline_name} ({pipeline_id})[/yellow]"
                    )
                    # Unassign all workspaces from pipeline stages
                    stages_result = pipeline_api.get_pipeline_stages(pipeline_id)
                    if stages_result["success"]:
                        for stage in stages_result["stages"]:
                            if stage.get("workspaceId"):
                                unassign = pipeline_api.unassign_workspace_from_stage(
                                    pipeline_id, stage["id"]
                                )
                                stage_name = stage.get("displayName", stage["id"])
                                if unassign["success"]:
                                    console.print(
                                        f"  [dim]Unassigned workspace from "
                                        f"{stage_name} stage[/dim]"
                                    )
                                else:
                                    console.print(
                                        f"  [yellow][!] Failed to unassign "
                                        f"{stage_name}: "
                                        f"{unassign.get('error', '')}[/yellow]"
                                    )
                    # Delete the pipeline itself
                    del_result = pipeline_api.delete_pipeline(pipeline_id)
                    if del_result["success"]:
                        console.print(
                            f"  [green]* Pipeline '{pipeline_name}' deleted[/green]"
                        )
                    else:
                        console.print(
                            f"  [yellow][!] Failed to delete pipeline: "
                            f"{del_result.get('error', '')}[/yellow]"
                        )
                else:
                    console.print(
                        f"[dim]Pipeline '{pipeline_name}' not found -- "
                        "skipping pipeline teardown[/dim]"
                    )

        result = fabric.delete_workspace(workspace_name, safe=effective_safe)

        if result.get("blocked_by_safety"):
            summary = result.get("item_summary", {})
            console.print(
                f"[yellow][SAFETY] SAFETY BLOCK: Workspace '{workspace_name}' "
                f"contains {summary.get('item_count', '?')} item(s):[/yellow]"
            )
            for item_type, count in summary.get("items_by_type", {}).items():
                console.print(f"  [yellow]- {count}x {item_type}[/yellow]")
            console.print(
                "[yellow]Use --force-destroy-populated to override, "
                "or clean up items manually first.[/yellow]"
            )
            raise typer.Exit(2)  # Exit code 2 = blocked by safety

        if result["success"]:
            method = result.get("method", "fab_cli")
            if method == "pbi_api":
                console.print(
                    f"[green][OK] Workspace '{workspace_name}' destroyed "
                    "(via PBI API fallback)[/green]"
                )
            else:
                console.print(
                    f"[green][OK] Workspace '{workspace_name}' destroyed[/green]"
                )
        else:
            error_msg = result.get("error", "")
            error_str = str(error_msg)
            # Treat "not found" as success -- workspace already cleaned up (idempotent)
            if "NotFound" in error_str or "could not be found" in error_str.lower():
                console.print(
                    f"[yellow][!] Workspace '{workspace_name}'"
                    " not found -- already cleaned up[/yellow]"
                )
            # Treat InsufficientPrivileges as a non-fatal warning
            elif (
                "InsufficientPrivileges" in error_str
                or "insufficient" in error_str.lower()
            ):
                console.print(
                    f"[yellow][!] Workspace '{workspace_name}' -- "
                    "insufficient privileges to delete. "
                    "Manual cleanup may be required.[/yellow]"
                )
            else:
                handle_cli_error(
                    "destroy workspace",
                    error_msg,
                    "Check your Fabric API connectivity and permissions.",
                )

        # -- Repo cleanup (local files + workflow entries) ----------
        # Only runs when --cleanup-repo and --force-destroy-populated are
        # both set, and the workspace was successfully destroyed (or was
        # already gone).
        workspace_gone = result["success"] or (
            "NotFound" in str(result.get("error", ""))
            or "could not be found" in str(result.get("error", "")).lower()
        )
        if cleanup_repo and force_destroy_populated and workspace_gone:
            import re
            import shutil
            from pathlib import Path

            config_path = Path(config).resolve()
            # Derive project slug from config directory name
            # e.g., config/projects/ap_testing_si/base_workspace.yaml -> ap_testing_si
            project_slug = config_path.parent.name

            # Find repo root (walk up until we find .github/ or .git/)
            repo_root = config_path.parent
            while repo_root != repo_root.parent:
                if (repo_root / ".git").exists() or (repo_root / ".github").exists():
                    break
                repo_root = repo_root.parent
            # Safeguard: abort if we walked all the way to filesystem root
            has_git = (repo_root / ".git").exists()
            has_gh = (repo_root / ".github").exists()
            if not has_git and not has_gh:
                console.print(
                    "[red]ERROR: Could not find repo root (.git/ or .github/) "
                    "-- skipping repo cleanup to prevent accidental deletions.[/red]"
                )
                return

            console.print(
                f"\n[yellow]Cleaning up repo files for " f"'{project_slug}'...[/yellow]"
            )

            cleanup_errors = []

            # 1. Remove config directory (config/projects/<slug>/)
            try:
                config_dir = config_path.parent
                if config_dir.exists():
                    shutil.rmtree(config_dir)
                    console.print(
                        f"  [dim]Removed {config_dir.relative_to(repo_root)}/[/dim]"
                    )
            except Exception as cleanup_err:
                cleanup_errors.append(f"Config dir: {cleanup_err}")
                console.print(
                    f"  [yellow][!] Failed to remove config directory: "
                    f"{cleanup_err}[/yellow]"
                )

            # 2. Remove git sync directory (from git_directory in config)
            try:
                git_directory = workspace_config.git_directory
                if git_directory and git_directory != "/":
                    # git_directory is like "/ap_testing_si" -- strip leading /
                    sync_dir = repo_root / git_directory.lstrip("/")
                    if sync_dir.exists():
                        shutil.rmtree(sync_dir)
                        console.print(
                            f"  [dim]Removed "
                            f"{sync_dir.relative_to(repo_root)}/[/dim]"
                        )
            except Exception as cleanup_err:
                cleanup_errors.append(f"Git sync dir: {cleanup_err}")
                console.print(
                    f"  [yellow][!] Failed to remove git sync directory: "
                    f"{cleanup_err}[/yellow]"
                )

            # 3. Remove project from workflow choice lists
            try:
                workflows_dir = repo_root / ".github" / "workflows"
                if workflows_dir.exists():
                    # Match lines like "          - ap_testing_si"
                    # or "          - ap_testing_si  # comment"
                    # in YAML workflow_dispatch choice lists
                    pattern = re.compile(
                        r"^\s*-\s+" + re.escape(project_slug) + r"(\s*#.*)?\s*$"
                    )
                    for wf_path in sorted(workflows_dir.glob("*.yml")):
                        lines = wf_path.read_text().splitlines(keepends=True)
                        new_lines = [line for line in lines if not pattern.match(line)]
                        if len(new_lines) < len(lines):
                            wf_path.write_text("".join(new_lines))
                            removed = len(lines) - len(new_lines)
                            console.print(
                                f"  [dim]Removed {removed} entry/entries from "
                                f"{wf_path.name}[/dim]"
                            )
            except Exception as cleanup_err:
                cleanup_errors.append(f"Workflow entries: {cleanup_err}")
                console.print(
                    f"  [yellow][!] Failed to update workflow files: "
                    f"{cleanup_err}[/yellow]"
                )

            if cleanup_errors:
                console.print(
                    f"[yellow][!] Repo cleanup partially completed for "
                    f"'{project_slug}' -- {len(cleanup_errors)} step(s) "
                    f"failed. Manual cleanup may be needed.[/yellow]"
                )
            else:
                console.print(
                    f"[green][OK] Repo cleanup complete for "
                    f"'{project_slug}'[/green]"
                )

    except (typer.Exit, SystemExit):
        raise  # Re-raise exit codes (including safety block exit code 2)
    except (FabricCLIError, ValueError, KeyError) as e:
        error_str = str(e)
        # Treat "not found" as success -- workspace already cleaned up (idempotent)
        if "NotFound" in error_str or "could not be found" in error_str.lower():
            ws_display = workspace_name or "<unknown>"
            console.print(
                f"[yellow][!] Workspace '{ws_display}'"
                " not found -- already cleaned up[/yellow]"
            )
        # Treat InsufficientPrivileges as a non-fatal warning
        elif (
            "InsufficientPrivileges" in error_str or "insufficient" in error_str.lower()
        ):
            ws_display = workspace_name or "<unknown>"
            console.print(
                f"[yellow][!] Workspace '{ws_display}' -- "
                "insufficient privileges to delete. "
                "Manual cleanup may be required.[/yellow]"
            )
        else:
            handle_cli_error(
                "destroy workspace",
                e,
                "Check your Fabric API connectivity and permissions.",
            )


@app.command()
def promote(
    pipeline_name: str = typer.Option(
        ..., "--pipeline-name", "-p", help="Fabric Deployment Pipeline display name"
    ),
    source_stage: str = typer.Option(
        "Development",
        "--source-stage",
        "-s",
        help="Source stage to promote from (Development/Test)",
    ),
    target_stage: Optional[str] = typer.Option(
        None,
        "--target-stage",
        "-t",
        help="Target stage to promote to (auto-inferred if omitted)",
    ),
    note: str = typer.Option(
        "",
        "--note",
        "-n",
        help="Deployment note",
    ),
    wait: bool = typer.Option(
        True,
        "--wait/--no-wait",
        help="Wait for promotion to complete (default: wait)",
    ),
    selective: bool = typer.Option(
        False,
        "--selective",
        help=(
            "Use selective promotion -- excludes unsupported item types "
            "and retries with auto-exclusion of failing items"
        ),
    ),
    exclude_types: Optional[str] = typer.Option(
        None,
        "--exclude-types",
        help=(
            "Comma-separated item types to exclude when using --selective "
            "(default: Warehouse,SQLEndpoint)"
        ),
    ),
    wait_for_git_sync: int = typer.Option(
        0,
        "--wait-for-git-sync",
        help="Wait N seconds for Fabric Git Sync before promoting (0=skip)",
    ),
):
    """Promote content through Deployment Pipeline (Dev -> Test -> Prod)."""

    try:
        import time as _time

        from usf_fabric_cli.services.deployment_pipeline import (
            DeploymentStage,
            FabricDeploymentPipelineAPI,
        )
        from usf_fabric_cli.services.token_manager import create_token_manager_from_env

        env_vars = get_environment_variables(validate_vars=True)

        # Use TokenManager so long-running promotions can refresh tokens
        token_manager = create_token_manager_from_env()

        api = FabricDeploymentPipelineAPI(
            access_token=env_vars["FABRIC_TOKEN"],
            token_manager=token_manager,
        )

        pipeline = api.get_pipeline_by_name(pipeline_name)
        if not pipeline:
            handle_cli_error(
                "promote deployment pipeline",
                f"Pipeline '{pipeline_name}' not found",
                "Verify the exact pipeline name matches the Fabric UI.",
            )

        display_target = target_stage or DeploymentStage.next_stage(source_stage)
        console.print(f"[blue]Promoting: {source_stage} -> {display_target}[/blue]")

        # Wait for Fabric Git Sync if requested
        if wait_for_git_sync > 0:
            console.print(
                f"[blue]Waiting up to {wait_for_git_sync}s for Fabric "
                "Git Sync to complete...[/blue]"
            )

            # Fetch the source workspace ID from the pipeline
            source_ws_id = None
            stages_result = api.get_pipeline_stages(pipeline["id"])
            if stages_result.get("success"):
                for stage in stages_result.get("stages", []):
                    if stage.get("displayName") == source_stage:
                        source_ws_id = stage.get("workspaceId")
                        break

            if source_ws_id:
                from usf_fabric_cli.services.fabric_git_api import FabricGitAPI

                git_api = FabricGitAPI(
                    access_token=env_vars["FABRIC_TOKEN"],
                    token_manager=token_manager,
                )

                elapsed = 0
                poll_interval = 5

                # Active polling loop
                while elapsed < wait_for_git_sync:
                    status_res = git_api.get_git_status(source_ws_id)
                    if status_res.get("success"):
                        status_data = status_res.get("status", {})
                        remote_commit = status_data.get("remoteCommitHash")
                        ws_head = status_data.get("workspaceHead")

                        if remote_commit and remote_commit == ws_head:
                            short_hash = str(ws_head)[:7] if ws_head else "unknown"
                            console.print(
                                "[green][OK] Fabric Git Sync complete "
                                f"(Commit: {short_hash})[/green]"
                            )
                            break

                        short_remote = (
                            str(remote_commit)[:7] if remote_commit else "None"
                        )
                        short_head = str(ws_head)[:7] if ws_head else "None"
                        console.print(
                            f"[dim]   Syncing... (Head: {short_head}, "
                            f"Remote: {short_remote})[/dim]"
                        )
                    else:
                        error_str = str(status_res.get("error", ""))
                        if "WorkspaceNotConnectedToGit" in error_str:
                            console.print(
                                "[yellow][!] Workspace is not connected to Git. "
                                "Skipping wait.[/yellow]"
                            )
                            break
                        console.print(f"[yellow]   Status check: {error_str}[/yellow]")

                    _time.sleep(poll_interval)
                    elapsed += poll_interval

                if elapsed >= wait_for_git_sync:
                    console.print(
                        "[yellow][!] Git Sync polling timed out "
                        f"after {wait_for_git_sync}s[/yellow]"
                    )
            else:
                console.print(
                    "[yellow][!] Could not determine source workspace ID. "
                    "Falling back to naive sleep.[/yellow]"
                )
                _time.sleep(wait_for_git_sync)

        if selective:
            # Parse exclude types
            effective_excludes = None  # use default UNSUPPORTED_SP_TYPES
            if exclude_types:
                effective_excludes = {
                    t.strip() for t in exclude_types.split(",") if t.strip()
                }
                console.print(
                    f"[blue]Excluding item types: "
                    f"{', '.join(effective_excludes)}[/blue]"
                )

            result = api.selective_promote(
                pipeline_id=pipeline["id"],
                source_stage_name=source_stage,
                target_stage_name=target_stage,
                note=note,
                exclude_types=effective_excludes,
            )

            if result.get("no_items"):
                console.print(
                    f"[yellow][!] {result.get('message', 'No items')}[/yellow]"
                )
            elif result["success"]:
                msg = result.get("message", "Promotion succeeded")
                console.print(f"[green][OK] {msg}[/green]")
            else:
                handle_cli_error(
                    "promote selective items",
                    result.get("error", "unknown"),
                    "Check the target workspace for locking or permissions issues.",
                )
        else:
            result = api.promote(
                pipeline_id=pipeline["id"],
                source_stage_name=source_stage,
                target_stage_name=target_stage,
                note=note,
                wait=wait,
            )

            if result["success"]:
                console.print(
                    f"[green][OK] Promotion succeeded: {source_stage} -> "
                    f"{display_target}[/green]"
                )
            else:
                handle_cli_error(
                    "promote entire stage",
                    result.get("error", "unknown"),
                    "Check the target workspace for locking or permissions issues.",
                )

    except (FabricCLIError, ValueError, KeyError) as e:
        handle_cli_error(
            "promote deployment pipeline",
            e,
            "Verify the deployment pipeline ID and stage names.",
        )


# ----------------------------------------------------------------------
# Onboarding & Project Setup Commands
# ----------------------------------------------------------------------


@app.command()
def onboard(
    org: str = typer.Option(..., "--org", help="Organization name"),
    project: str = typer.Option(..., "--project", help="Project name"),
    template: str = typer.Option("medallion", "--template", help="Blueprint template"),
    capacity_id: str = typer.Option(
        "${FABRIC_CAPACITY_ID}", "--capacity-id", help="Fabric capacity ID"
    ),
    repo: str = typer.Option("${GIT_REPO_URL}", "--repo", help="Git repository URL"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Simulate actions without making changes"
    ),
    with_feature_branch: bool = typer.Option(
        False, "--with-feature-branch", help="Create isolated feature workspace"
    ),
    stages: str = typer.Option(
        "dev,test,prod", "--stages", help="Comma-separated stages to provision"
    ),
    pipeline_name: Optional[str] = typer.Option(
        None, "--pipeline-name", help="Custom Deployment Pipeline name"
    ),
    test_workspace_name: Optional[str] = typer.Option(
        None, "--test-workspace-name", help="Custom Test workspace name"
    ),
    prod_workspace_name: Optional[str] = typer.Option(
        None, "--prod-workspace-name", help="Custom Prod workspace name"
    ),
    create_repo: bool = typer.Option(
        False, "--create-repo", help="Auto-create a project-specific Git repo"
    ),
    git_provider: str = typer.Option(
        "github", "--git-provider", help="Git provider (github/ado)"
    ),
    git_owner: Optional[str] = typer.Option(
        None, "--git-owner", help="GitHub owner/org or ADO org name"
    ),
    ado_project: Optional[str] = typer.Option(
        None, "--ado-project", help="Azure DevOps project name"
    ),
):
    """Onboard a new Fabric Data Product (full bootstrap: Dev+Test+Prod+Pipeline)"""
    try:
        requested_stages = {s.strip().lower() for s in stages.split(",")}
        valid_stages = {"dev", "test", "prod"}
        invalid = requested_stages - valid_stages
        if invalid:
            handle_cli_error(
                "parse target stages",
                f"Invalid stage(s) provided: {invalid}",
                f"Use a comma-separated list of valid stages: {valid_stages}",
            )

        success = onboard_project(
            org,
            project,
            template,
            capacity_id,
            repo,
            dry_run,
            with_feature_branch,
            stages=requested_stages,
            pipeline_name_override=pipeline_name,
            test_workspace_name=test_workspace_name,
            prod_workspace_name=prod_workspace_name,
            create_repo=create_repo,
            git_provider=git_provider,
            git_owner=git_owner,
            ado_project=ado_project,
        )
        if not success:
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except (FabricCLIError, ValueError, KeyError) as e:
        handle_cli_error(
            "onboard new project",
            e,
            "Check template names, capacity ID permissions,"
            " and repository configuration.",
        )


@app.command()
def generate(
    org_name: str = typer.Argument(..., help="Organization name (e.g., 'Contoso Inc')"),
    project_name: str = typer.Argument(
        ..., help="Project name (e.g., 'Customer Analytics')"
    ),
    template: str = typer.Option(
        "basic_etl", "--template", help="Configuration template to use"
    ),
    capacity_id: str = typer.Option(
        "${FABRIC_CAPACITY_ID}", "--capacity-id", help="Fabric capacity ID"
    ),
    git_repo: str = typer.Option(
        "${GIT_REPO_URL}", "--git-repo", help="Git repository URL"
    ),
):
    """Generate project configuration from a blueprint template"""
    try:
        generate_project_config(org_name, project_name, template, capacity_id, git_repo)
    except (ValueError, OSError) as e:
        handle_cli_error(
            "generate project configuration",
            e,
            "Ensure the template exists and you have write permissions"
            " to the destination directory.",
        )


# ----------------------------------------------------------------------
# Admin Utility Commands
# ----------------------------------------------------------------------


@app.command("list-workspaces")
def list_workspaces():
    """List all Fabric workspaces"""
    import json

    try:
        env_vars = get_environment_variables()
        token = env_vars.get("FABRIC_TOKEN") or ""
        if not token:
            handle_cli_error(
                "list workspaces",
                "FABRIC_TOKEN is not set",
                "Export FABRIC_TOKEN in your environment or set it in your .env file.",
            )

        fabric = FabricCLIWrapper(token)
        console.print("[blue]Listing workspaces...[/blue]")

        result = fabric._execute_command(["ls", "--output_format", "json"])
        if result.get("success"):
            data = result.get("data")
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError as exc:
                    logger.debug("Failed to decode workspace list JSON: %s", exc)
            console.print(json.dumps(data, indent=2))
        else:
            handle_cli_error(
                "list workspaces",
                result.get("error", "unknown"),
                "Check your Fabric API connectivity and token permissions.",
            )
    except typer.Exit:
        raise
    except (FabricCLIError, KeyError, ValueError, OSError, RuntimeError) as e:
        handle_cli_error("list workspaces", e, "Check your Fabric API connectivity.")


@app.command("list-items")
def list_items(
    workspace: str = typer.Argument(..., help="Workspace name to list items from"),
):
    """List items in a Fabric workspace"""
    try:
        env_vars = get_environment_variables()
        token = env_vars.get("FABRIC_TOKEN") or ""
        if not token:
            handle_cli_error(
                "list items",
                "FABRIC_TOKEN is not set",
                "Export FABRIC_TOKEN in your environment or set it in your .env file.",
            )

        fabric = FabricCLIWrapper(token)
        console.print(f"[blue]Listing items in workspace '{workspace}'...[/blue]")

        result = fabric.list_workspace_items(workspace)
        if result.get("success"):
            data = result.get("data")
            items = data or []
            console.print(f"Found {len(items)} items:\n")
            console.print(f"  {'Name':<40} {'Type':<25} {'Description'}")
            console.print(f"  {'-' * 40} {'-' * 25} {'-' * 30}")
            for item in items:
                name = item.get("displayName", "N/A")
                item_type = item.get("type", "N/A")
                desc = item.get("description", "")
                console.print(f"  {name:<40} {item_type:<25} {desc}")
        else:
            handle_cli_error(
                "list items",
                result.get("error", "unknown"),
                "Verify the workspace name and your access permissions.",
            )
    except typer.Exit:
        raise
    except (FabricCLIError, KeyError, ValueError) as e:
        handle_cli_error(
            "list items", e, "Verify the workspace name and your access permissions."
        )


@app.command("bulk-destroy")
def bulk_destroy(
    file: str = typer.Argument(
        ..., help="Path to file containing workspace list (one name per line)"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be deleted"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompt"),
    skip_pipeline_teardown: bool = typer.Option(
        False,
        "--skip-pipeline-teardown",
        help="Skip deployment pipeline unassignment before deletion",
    ),
    skip_item_deletion: bool = typer.Option(
        False,
        "--skip-item-deletion",
        help="Skip deleting workspace items before workspace deletion",
    ),
):
    """Bulk destroy workspaces from a list file.

    Performs full teardown per workspace: (1) unassign from deployment
    pipelines, (2) delete all workspace items, (3) delete the workspace.

    The input file should have one workspace display name per line.
    Lines starting with # are comments.
    """
    from pathlib import Path

    if not Path(file).exists():
        handle_cli_error(
            "bulk destroy",
            f"File '{file}' not found",
            "Provide a valid path to a text file containing workspace names.",
        )

    try:
        bulk_destroy_fn(
            file,
            dry_run,
            force,
            teardown_pipelines=not skip_pipeline_teardown,
            delete_items=not skip_item_deletion,
        )
    except typer.Exit:
        raise
    except (FabricCLIError, KeyError, ValueError, OSError) as e:
        handle_cli_error("bulk destroy", e, "Check your file format and permissions.")


@app.command("organize-folders")
def organize_folders(
    config: str = typer.Argument(..., help="Path to configuration file"),
    workspace: Optional[str] = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Override workspace name (default: read from config)",
    ),
    environment: Optional[str] = typer.Option(
        None, "--env", "-e", help="Environment (dev/staging/prod)"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be moved without actually moving items",
    ),
):
    """Organize workspace items into folders after Git Sync.

    Fabric Git Sync always places items at the workspace root. This command
    reads the folder_rules from the config and moves items into their
    designated folders using the Fabric REST API.

    Example config entry (folder_rules):

        folder_rules:
          - type: Lakehouse
            folder: "200 Store"
          - type: Notebook
            name: nb_transform
            folder: "300 Prepare"
    """
    try:
        env_vars = get_environment_variables()
        token = env_vars.get("FABRIC_TOKEN") or ""
        if not token:
            handle_cli_error(
                "organize folders",
                "FABRIC_TOKEN is not set",
                "Export it in your environment.",
            )

        config_mgr = ConfigManager(config)
        cfg = config_mgr.load_config(environment)
        ws_name = workspace or cfg.name

        folder_rules = cfg.folder_rules or []
        if not folder_rules:
            console.print(
                "[yellow]No folder_rules defined in config "
                "-- nothing to organize.[/yellow]"
            )
            raise typer.Exit(0)

        fabric = FabricCLIWrapper(token)
        console.print(f"[blue]Organizing items in workspace '{ws_name}'...[/blue]")

        if dry_run:
            console.print("[yellow]DRY RUN -- no items will be moved.[/yellow]\n")
            items = fabric.list_workspace_items_api(ws_name)
            root_items = [it for it in items if not it.get("folderId")]
            console.print(f"  Items at root: {len(root_items)}")
            # Sort rules: name-specific first, then wildcards (matches
            # the ordering used by organize_items_into_folders)
            sorted_rules = sorted(
                folder_rules,
                key=lambda r: (0 if r.get("name") else 1, r.get("type", "")),
            )
            matched_ids: set = set()
            for rule in sorted_rules:
                target_type = rule.get("type", "")
                target_name = rule.get("name")
                target_folder = rule.get("folder", "")
                matched = [
                    it
                    for it in root_items
                    if it.get("id", "") not in matched_ids
                    and it.get("type", "").lower() == target_type.lower()
                    and (not target_name or it.get("displayName") == target_name)
                ]
                for item in matched:
                    matched_ids.add(item.get("id", ""))
                    console.print(
                        f"  Would move {item['type']} '{item['displayName']}' "
                        f"-> folder '{target_folder}'"
                    )
            raise typer.Exit(0)

        result = fabric.organize_items_into_folders(ws_name, folder_rules)
        console.print(
            f"\n[green][OK] Organize complete: "
            f"{result['moved']} moved, "
            f"{result['skipped']} skipped, "
            f"{result['failed']} failed[/green]"
        )
        for detail in result.get("details", []):
            status_icon = "*" if detail["status"] == "moved" else "X"
            console.print(
                f"  {status_icon} {detail.get('type', '')} "
                f"'{detail['item']}' -> {detail['folder']} "
                f"({detail['status']})"
            )

    except typer.Exit:
        raise
    except (FabricCLIError, KeyError, ValueError, OSError) as e:
        handle_cli_error(
            "organize folders",
            e,
            "Ensure your folder_rules map to existing structures.",
        )


@app.command("discover-folders")
def discover_folders_cmd(
    config: str = typer.Argument(..., help="Path to configuration file"),
    workspace: Optional[str] = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Name of the live workspace to scan",
    ),
    branch: Optional[str] = typer.Option(
        None,
        "--branch",
        "-b",
        help="Feature branch name (derives workspace name if --workspace not given)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would change without writing to the config file",
    ),
    prune: bool = typer.Option(
        False,
        "--prune",
        help=(
            "Remove folders and folder_rules from config that no longer "
            "exist in the live workspace"
        ),
    ),
):
    """Discover new folders from a live workspace and update the YAML config.

    Scans a workspace for folders and item placements not yet in the project's
    base_workspace.yaml, then adds them. With --prune, also removes folders
    and rules that no longer exist in the live workspace.

    Examples:

        fabric-cicd discover-folders config/projects/edp/base_workspace.yaml \\
            --workspace "EDP Feature-my-feature"

        fabric-cicd discover-folders config/projects/edp/base_workspace.yaml \\
            --branch feature/edp/new-reports --dry-run

        fabric-cicd discover-folders config/projects/edp/base_workspace.yaml \\
            --workspace "EDP [DEV]" --prune
    """
    try:
        from usf_fabric_cli.scripts.admin.utilities.discover_folders import (
            discover_folders,
        )

        result = discover_folders(
            config_path=config,
            workspace_name=workspace,
            branch=branch,
            dry_run=dry_run,
            prune=prune,
        )

        added = result["new_folders"] + result["new_rules"]
        pruned = result["stale_folders"] + result["stale_rules"]
        if added or pruned:
            parts = []
            if added:
                parts.append(
                    f"{result['new_folders']} new folder(s), "
                    f"{result['new_rules']} new rule(s)"
                )
            if pruned:
                parts.append(
                    f"{result['stale_folders']} stale folder(s), "
                    f"{result['stale_rules']} stale rule(s) pruned"
                )
            console.print(f"\n[green]{'; '.join(parts)}.[/green]")
            if not dry_run:
                console.print(f"[green]Updated: {result['config']}[/green]")
        else:
            console.print("[green]Config is up to date -- no changes needed.[/green]")

    except (ValueError, FileNotFoundError, KeyError, OSError, RuntimeError) as e:
        handle_cli_error(
            "discover folders",
            e,
            "Ensure the workspace exists and you have access.",
        )


@app.command("init-github-repo")
def init_github_repo(
    owner: str = typer.Option(..., "--owner", help="GitHub user or organization name"),
    repo: str = typer.Option(..., "--repo", help="Repository name to create"),
    branch: str = typer.Option("main", "--branch", help="Branch to ensure exists"),
    private: bool = typer.Option(
        True, "--private/--public", help="Repository visibility"
    ),
):
    """Create and initialize a GitHub repository for Fabric Git integration"""
    import os

    try:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            handle_cli_error(
                "initialize github repo",
                "GITHUB_TOKEN is not set",
                "Export a valid personal access token with repo scopes.",
            )

        clone_url = init_github_repo_fn(
            owner=owner,
            repo_name=repo,
            token=token,
            branch=branch,
            private=private,
        )
        if clone_url:
            console.print(f"[green][OK] Repository ready: {clone_url}[/green]")
            # Show the browsable web URL for convenience
            web_url = clone_url.removesuffix(".git")
            console.print(f"[bold cyan]Open in browser:[/bold cyan] {web_url}")
        else:
            handle_cli_error(
                "initialize github repo",
                "Process returned empty URL.",
                "Ensure the organization/user name is correct.",
            )
    except (FabricCLIError, KeyError, ValueError, OSError, RuntimeError) as e:
        handle_cli_error(
            "initialize github repo",
            e,
            "Ensure your GITHUB_TOKEN has the required repo scopes.",
        )


@app.command("scaffold")
def scaffold(
    workspace: str = typer.Argument(
        ..., help="Name of the existing Fabric workspace to scan"
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for base_workspace.yaml (default: config/projects/<slug>/)",
    ),
    include_feature_template: bool = typer.Option(
        False,
        "--include-feature-template",
        "-f",
        help="Legacy flag — feature template is now generated by default",
    ),
    pipeline_name: str = typer.Option(
        None,
        "--pipeline-name",
        "-p",
        help="Override the auto-inferred deployment pipeline name",
    ),
    skip_pipeline: bool = typer.Option(
        False,
        "--skip-pipeline",
        help="Do not include the deployment_pipeline section",
    ),
    skip_feature_template: bool = typer.Option(
        False,
        "--skip-feature-template",
        help="Do not generate feature_workspace.yaml",
    ),
    project_slug: str = typer.Option(
        None,
        "--project-slug",
        "-s",
        help="Override the auto-generated project slug",
    ),
    test_workspace_name: str = typer.Option(
        None,
        "--test-workspace-name",
        help="Explicit Test stage workspace name (overrides auto-inference)",
    ),
    prod_workspace_name: str = typer.Option(
        None,
        "--prod-workspace-name",
        help="Explicit Production stage workspace name (overrides auto-inference)",
    ),
    templatise: bool = typer.Option(
        False,
        "--templatise",
        "-t",
        help=(
            "Replace real workspace/pipeline names with CHANGE-ME placeholders, "
            "making the output a reusable template for 'make new-project'"
        ),
    ),
    brownfield: bool = typer.Option(
        False,
        "--brownfield",
        help=(
            "Emit discovered principals as active YAML entries with actual GUIDs "
            "instead of placeholder env vars. Use for existing workspaces that "
            "already have principals which need to propagate to Test/Prod/Feature."
        ),
    ),
):
    """Scaffold a YAML config from an existing Fabric workspace.

    Connects to a live workspace, discovers its folders and items,
    and generates deployer-compatible YAML config file(s).

    By default, generates both base_workspace.yaml (with deployment
    pipeline) and feature_workspace.yaml.  Use --skip-pipeline or
    --skip-feature-template to opt out of either.

    Examples:

        fabric-cicd scaffold "EDP [DEV]"

        fabric-cicd scaffold "SC30GLD [DEV]" --brownfield

        fabric-cicd scaffold "Sales [DEV]" -p "Sales - Pipeline"

        fabric-cicd scaffold "HR Analytics [DEV]" -t

        fabric-cicd scaffold "My WS" --skip-pipeline --skip-feature-template
    """
    try:
        from usf_fabric_cli.scripts.admin.utilities.scaffold_workspace import (
            scaffold_workspace,
        )

        results = scaffold_workspace(
            workspace_name=workspace,
            output_path=output,
            include_feature_template=include_feature_template,
            pipeline_name=pipeline_name,
            project_slug=project_slug,
            test_workspace_name=test_workspace_name,
            prod_workspace_name=prod_workspace_name,
            templatise=templatise,
            skip_pipeline=skip_pipeline,
            skip_feature_template=skip_feature_template,
            brownfield=brownfield,
        )

        if not results:
            handle_cli_error(
                "scaffold",
                "No output files were generated.",
                "Verify the workspace name and your access permissions.",
            )
    except typer.Exit:
        raise
    except (FabricCLIError, KeyError, ValueError, OSError) as e:
        handle_cli_error(
            "scaffold",
            e,
            "Verify the workspace name and your credentials "
            "(FABRIC_TOKEN or AZURE_CLIENT_ID/SECRET/TENANT_ID).",
        )


@app.command("repoint-connections")
def repoint_connections(
    config: str = typer.Argument(..., help="Path to configuration file"),
    workspace: Optional[str] = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Override workspace name (default: read from config)",
    ),
    environment: Optional[str] = typer.Option(
        None, "--env", "-e", help="Environment (dev/staging/prod)"
    ),
    source_pattern: str = typer.Option(
        "feature[-_].*",
        "--source-pattern",
        "-s",
        help="Regex pattern matching feature workspace names to repoint away from",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be repointed without making changes",
    ),
):
    """Repoint semantic model connections after Git Sync.

    After a feature branch is merged and Git Sync copies definitions into
    the Dev workspace, semantic model connections may still reference the
    feature workspace's lakehouses or warehouses.  This command detects
    those stale connections and updates them to point to the target
    workspace.

    Exit codes:
        0 = connections were repointed successfully
        1 = one or more models failed to repoint (API error)
        2 = nothing to repoint (no stale connections found)

    Example:

        fabric-cicd repoint-connections config/projects/edp/base_workspace.yaml

        fabric-cicd repoint-connections config/projects/edp/base_workspace.yaml \\
            --source-pattern "feature[-_].*" --dry-run
    """
    try:
        from usf_fabric_cli.services.datasource_repoint import (
            FabricDatasourceRepointAPI,
        )

        env_vars = get_environment_variables()
        token = env_vars.get("FABRIC_TOKEN") or ""
        if not token:
            handle_cli_error(
                "repoint connections",
                "FABRIC_TOKEN is not set",
                "Export FABRIC_TOKEN in your environment or set it in .env file.",
            )

        config_mgr = ConfigManager(config)
        cfg = config_mgr.load_config(environment)
        ws_name = workspace or cfg.name

        fabric = FabricCLIWrapper(token)
        workspace_id = fabric.get_workspace_id(ws_name)
        if not workspace_id:
            handle_cli_error(
                "repoint connections",
                f"Could not resolve workspace ID for '{ws_name}'",
                "Verify the workspace name and your access permissions.",
            )
            return

        console.print(
            f"[blue]Checking semantic model connections in '{ws_name}'...[/blue]"
        )
        if dry_run:
            console.print("[yellow]DRY RUN -- no changes will be made.[/yellow]\n")

        # Build the repoint API client (reuses the same token)
        token_manager = getattr(fabric, "_token_manager", None)
        repoint_api = FabricDatasourceRepointAPI(
            access_token=token,
            token_manager=token_manager,
        )

        result = repoint_api.repoint_workspace_models(
            workspace_id=workspace_id,
            target_workspace_name=ws_name,
            source_pattern=source_pattern,
            dry_run=dry_run,
        )

        summary = result.summary
        if summary["repointed"] > 0:
            mode = " (DRY RUN)" if dry_run else ""
            console.print(
                f"\n[green][OK] Repointed {summary['repointed']} "
                f"connection(s){mode}:[/green]"
            )
            for detail in summary["details"]["repointed"]:
                console.print(
                    f"  * {detail['model']}: {detail['from']} -> {detail['to']}"
                )

        if summary["skipped"] > 0:
            console.print(f"\n  Skipped: {summary['skipped']} model(s)")
            for detail in summary["details"]["skipped"]:
                console.print(f"    - {detail['model']}: {detail['reason']}")

        if summary["failed"] > 0:
            console.print(f"\n[red]  Failed: {summary['failed']} model(s)[/red]")
            for detail in summary["details"]["failed"]:
                console.print(f"    X {detail['model']}: {detail['reason']}")
            raise typer.Exit(1)

        if summary["repointed"] == 0:
            console.print(
                "[green]No connections needed repointing -- "
                "all connections already point to the correct workspace.[/green]"
            )
            # Exit 2 = graceful skip (nothing to do), matching the convention
            # used by organize-folders and promote commands.
            raise typer.Exit(2)

    except typer.Exit:
        raise
    except (FabricCLIError, KeyError, ValueError) as e:
        handle_cli_error(
            "repoint connections",
            e,
            "Verify the workspace name and your access permissions. "
            "The service principal must be the semantic model OWNER "
            "(not just workspace admin). If models were created by "
            "Git Sync, ownership may need to be taken over first.",
        )


@app.command("bind-direct-lake")
def bind_direct_lake(
    config: str = typer.Argument(..., help="Path to configuration file"),
    workspace: Optional[str] = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Override target workspace name (default: read from config)",
    ),
    source_workspace: Optional[str] = typer.Option(
        None,
        "--source-workspace",
        "-s",
        help="Source workspace name (the stage promoted FROM)",
    ),
    source_stage: Optional[str] = typer.Option(
        None,
        "--source-stage",
        help=(
            "Source pipeline stage name to derive source "
            "workspace (e.g., 'development', 'test'). "
            "Read from config deployment_pipeline.stages."
        ),
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be rebound without making changes",
    ),
):
    """Rebind Direct Lake semantic models after promotion.

    After a Fabric Deployment Pipeline promotes content from one stage
    to another, Direct Lake semantic models keep their OneLake bindings
    pointing to the source workspace's lakehouses.  This command detects
    those stale bindings and rebinds them to the target workspace.

    Requires either --source-workspace (explicit name) or --source-stage
    (reads the workspace name from the config's deployment_pipeline.stages).

    Exit codes:
        0 = connections were rebound successfully
        1 = one or more models failed to rebind (API error)
        2 = nothing to rebind (no stale connections found)

    Example:

        fabric-cicd bind-direct-lake \\
            config/projects/re_sales_direct/base_workspace.yaml \\
            --workspace "RE Sales [TEST]" \\
            --source-stage development

        fabric-cicd bind-direct-lake \\
            config/projects/re_sales_direct/base_workspace.yaml \\
            --source-workspace "RE Sales [DEV]" \\
            --workspace "RE Sales [TEST]" --dry-run
    """
    try:
        from usf_fabric_cli.services.datasource_repoint import (
            FabricDatasourceRepointAPI,
        )

        env_vars = get_environment_variables()
        token = env_vars.get("FABRIC_TOKEN") or ""
        if not token:
            handle_cli_error(
                "bind direct lake",
                "FABRIC_TOKEN is not set",
                "Export FABRIC_TOKEN in your environment or set it in .env file.",
            )

        config_mgr = ConfigManager(config)
        cfg = config_mgr.load_config()
        target_ws_name = workspace or cfg.name

        # Resolve source workspace name
        source_ws_name = source_workspace
        if not source_ws_name and source_stage:
            # Read from config deployment_pipeline.stages.<stage>.workspace_name
            # (env vars are already resolved by ConfigManager.load_config)
            pipeline_cfg = cfg.deployment_pipeline or {}
            stages = pipeline_cfg.get("stages", {})
            stage_cfg = stages.get(source_stage, {})
            source_ws_name = stage_cfg.get("workspace_name", "")

        if not source_ws_name:
            handle_cli_error(
                "bind direct lake",
                "Source workspace not specified",
                "Provide --source-workspace or --source-stage to identify "
                "the workspace that models were promoted FROM.",
            )
            return

        fabric = FabricCLIWrapper(token)

        # Resolve workspace IDs
        target_ws_id = fabric.get_workspace_id(target_ws_name)
        if not target_ws_id:
            handle_cli_error(
                "bind direct lake",
                f"Could not resolve workspace ID for target '{target_ws_name}'",
                "Verify the workspace name and your access permissions.",
            )
            return

        source_ws_id = fabric.get_workspace_id(source_ws_name)
        if not source_ws_id:
            handle_cli_error(
                "bind direct lake",
                f"Could not resolve workspace ID for source '{source_ws_name}'",
                "Verify the workspace name and your access permissions.",
            )
            return

        console.print(
            f"[blue]Rebinding Direct Lake models in '{target_ws_name}'...[/blue]"
        )
        console.print(f"[blue]  Source (promoted from): {source_ws_name}[/blue]")
        console.print(f"[blue]  Target (promoted to):  {target_ws_name}[/blue]")
        if dry_run:
            console.print("[yellow]DRY RUN — no changes will be made.[/yellow]\n")

        token_manager = getattr(fabric, "_token_manager", None)
        repoint_api = FabricDatasourceRepointAPI(
            access_token=token,
            token_manager=token_manager,
        )

        result = repoint_api.rebind_direct_lake_models(
            target_workspace_id=target_ws_id,
            source_workspace_id=source_ws_id,
            dry_run=dry_run,
        )

        summary = result.summary
        if summary["repointed"] > 0:
            mode = " (DRY RUN)" if dry_run else ""
            console.print(
                f"\n[green][OK] Rebound {summary['repointed']} "
                f"Direct Lake connection(s){mode}:[/green]"
            )
            for detail in summary["details"]["repointed"]:
                console.print(
                    f"  * {detail['model']}"
                    + (
                        f" ({detail.get('lakehouse', '')})"
                        if detail.get("lakehouse")
                        else ""
                    )
                    + f": {detail['from']} -> {detail['to']}"
                )

        if summary["skipped"] > 0:
            console.print(f"\n  Skipped: {summary['skipped']} model(s)")
            for detail in summary["details"]["skipped"]:
                console.print(f"    - {detail['model']}: {detail['reason']}")

        if summary["failed"] > 0:
            console.print(f"\n[red]  Failed: {summary['failed']} model(s)[/red]")
            for detail in summary["details"]["failed"]:
                console.print(f"    X {detail['model']}: {detail['reason']}")
            raise typer.Exit(1)

        if summary["repointed"] == 0:
            console.print(
                "[green]No Direct Lake connections needed rebinding — "
                "all connections already point to the correct workspace.[/green]"
            )
            raise typer.Exit(2)

    except typer.Exit:
        raise
    except (FabricCLIError, KeyError, ValueError) as e:
        handle_cli_error(
            "bind direct lake",
            e,
            "Verify the workspace names and your access permissions. "
            "The service principal must be the semantic model OWNER "
            "(not just workspace admin).",
        )


if __name__ == "__main__":
    app()
