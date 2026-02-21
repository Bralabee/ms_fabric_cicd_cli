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
load_dotenv()

logger = logging.getLogger(__name__)


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
                console.print(f"[red]❌ {cli_check['error']}[/red]")
                raise typer.Exit(1)

            auth_check = diagnostics.validate_authentication()
            if not auth_check["success"]:
                console.print(f"[red]❌ {auth_check['error']}[/red]")
                raise typer.Exit(1)

            console.print("[green]✅ Pre-flight checks passed[/green]")
        except Exception as e:
            console.print(f"[red]Diagnostics failed: {e}[/red]")
            raise typer.Exit(1)

    if validate_only:
        console.print("[blue]Validating configuration...[/blue]")
        try:
            config_manager = ConfigManager(config, validate_env=False)
            config_manager.load_config(environment)
            console.print("[green]✅ Configuration is valid[/green]")
            return
        except Exception as e:
            console.print(f"[red]❌ Configuration validation failed: {e}[/red]")
            raise typer.Exit(1)

    try:
        deployer = FabricDeployer(config, environment)
        success = deployer.deploy(branch, force_branch_workspace, rollback_on_failure)

        if not success:
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Deployment failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def validate(
    config: str = typer.Argument(..., help="Path to configuration file"),
    environment: Optional[str] = typer.Option(None, "--env", "-e", help="Environment"),
):
    """Validate configuration file"""

    try:
        config_manager = ConfigManager(config, validate_env=False)
        workspace_config = config_manager.load_config(environment)

        console.print("[green]✅ Configuration is valid[/green]")
        console.print(f"Workspace: {workspace_config.name}")
        console.print(f"Capacity ID: {workspace_config.capacity_id}")
        console.print(f"Folders: {', '.join(workspace_config.folders or [])}")
        console.print(f"Lakehouses: {len(workspace_config.lakehouses or [])}")
        console.print(f"Warehouses: {len(workspace_config.warehouses or [])}")
        console.print(f"Notebooks: {len(workspace_config.notebooks or [])}")

        # Validate folder references — check that items and folder_rules
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
                f"\n[yellow]⚠️  {len(warnings)} folder reference warning(s):[/yellow]"
            )
            for w in warnings:
                console.print(f"  [yellow]• {w}[/yellow]")
        else:
            console.print("[green]✅ All folder references are valid[/green]")

    except Exception as e:
        console.print(f"[red]❌ Configuration validation failed: {e}[/red]")
        raise typer.Exit(1)


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
            console.print(f"[green]✅ Fabric CLI: {cli_check['version']}[/green]")
        else:
            console.print(f"[red]❌ Fabric CLI: {cli_check['error']}[/red]")
            raise typer.Exit(1)

        # Check authentication
        auth_check = diagnostics.validate_authentication()
        if auth_check["success"]:
            console.print("[green]✅ Authentication: Valid[/green]")
        else:
            console.print(f"[red]❌ Authentication: {auth_check['error']}[/red]")
            raise typer.Exit(1)

        # Check API connectivity
        api_check = diagnostics.validate_api_connectivity()
        if api_check["success"]:
            console.print(
                f"[green]✅ API Connectivity: {api_check['workspaces_count']} "
                "workspaces accessible[/green]"
            )
        else:
            console.print(f"[red]❌ API Connectivity: {api_check['error']}[/red]")

        console.print("\n[green]All diagnostic checks completed![/green]")

    except Exception as e:
        console.print(f"[red]Diagnostics failed: {e}[/red]")
        raise typer.Exit(1)


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
            "Git branch name — derives workspace name using "
            "get_workspace_name_from_branch() (overrides "
            "--workspace-name-override)"
        ),
    ),
    feature_prefix: str = typer.Option(
        "⚡",
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
            "Override safety mode — delete workspace even if it "
            "contains Fabric items. Use with caution."
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
        # --branch → --workspace-name-override → config default
        if branch:
            from usf_fabric_cli.services.git_integration import GitFabricIntegration

            base_name = workspace_config.name
            git = GitFabricIntegration.__new__(GitFabricIntegration)
            workspace_name = git.get_workspace_name_from_branch(
                base_workspace_name=base_name,
                branch=branch,
                feature_prefix=feature_prefix,
            )
            console.print(
                f"[blue]Branch '{branch}' → workspace: {workspace_name}[/blue]"
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
                "[blue]🛡️  Safety mode ON — populated workspaces "
                "will be protected[/blue]"
            )

        env_vars = get_environment_variables(validate_vars=True)
        fabric = FabricCLIWrapper(env_vars["FABRIC_TOKEN"])

        result = fabric.delete_workspace(workspace_name, safe=effective_safe)

        if result.get("blocked_by_safety"):
            summary = result.get("item_summary", {})
            console.print(
                f"[yellow]🛡️  SAFETY BLOCK: Workspace '{workspace_name}' "
                f"contains {summary.get('item_count', '?')} item(s):[/yellow]"
            )
            for item_type, count in summary.get("items_by_type", {}).items():
                console.print(f"  [yellow]• {count}x {item_type}[/yellow]")
            console.print(
                "[yellow]Use --force-destroy-populated to override, "
                "or clean up items manually first.[/yellow]"
            )
            raise typer.Exit(2)  # Exit code 2 = blocked by safety

        if result["success"]:
            method = result.get("method", "fab_cli")
            if method == "pbi_api":
                console.print(
                    f"[green]✅ Workspace '{workspace_name}' destroyed "
                    "(via PBI API fallback)[/green]"
                )
            else:
                console.print(
                    f"[green]✅ Workspace '{workspace_name}' destroyed[/green]"
                )
        else:
            error_msg = result.get("error", "")
            error_str = str(error_msg)
            # Treat "not found" as success — workspace already cleaned up (idempotent)
            if "NotFound" in error_str or "could not be found" in error_str.lower():
                console.print(
                    f"[yellow]⚠️  Workspace '{workspace_name}'"
                    " not found — already cleaned up[/yellow]"
                )
            # Treat InsufficientPrivileges as a non-fatal warning
            elif (
                "InsufficientPrivileges" in error_str
                or "insufficient" in error_str.lower()
            ):
                console.print(
                    f"[yellow]⚠️  Workspace '{workspace_name}' — "
                    "insufficient privileges to delete. "
                    "Manual cleanup may be required.[/yellow]"
                )
            else:
                console.print(f"[red]❌ Failed to destroy workspace: {error_msg}[/red]")
                raise typer.Exit(1)

    except (typer.Exit, SystemExit):
        raise  # Re-raise exit codes (including safety block exit code 2)
    except Exception as e:
        error_str = str(e)
        # Treat "not found" as success — workspace already cleaned up (idempotent)
        if "NotFound" in error_str or "could not be found" in error_str.lower():
            ws_display = workspace_name or "<unknown>"
            console.print(
                f"[yellow]⚠️  Workspace '{ws_display}'"
                " not found — already cleaned up[/yellow]"
            )
        # Treat InsufficientPrivileges as a non-fatal warning
        elif (
            "InsufficientPrivileges" in error_str or "insufficient" in error_str.lower()
        ):
            ws_display = workspace_name or "<unknown>"
            console.print(
                f"[yellow]⚠️  Workspace '{ws_display}' — "
                "insufficient privileges to delete. "
                "Manual cleanup may be required.[/yellow]"
            )
        else:
            console.print(f"[red]Destroy failed: {e}[/red]")
            raise typer.Exit(1)


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
            "Use selective promotion — excludes unsupported item types "
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
    """Promote content through Fabric Deployment Pipeline stages (Dev → Test → Prod)"""

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
            console.print(f"[red]❌ Pipeline '{pipeline_name}' not found[/red]")
            raise typer.Exit(1)

        display_target = target_stage or DeploymentStage.next_stage(source_stage)
        console.print(f"[blue]🚀 Promoting: {source_stage} → {display_target}[/blue]")

        # Wait for Fabric Git Sync if requested
        if wait_for_git_sync > 0:
            console.print(
                f"[blue]⏳ Waiting up to {wait_for_git_sync}s for Fabric "
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
                                "[green]✅ Fabric Git Sync complete "
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
                                "[yellow]⚠️  Workspace is not connected to Git. "
                                "Skipping wait.[/yellow]"
                            )
                            break
                        console.print(f"[yellow]   Status check: {error_str}[/yellow]")

                    _time.sleep(poll_interval)
                    elapsed += poll_interval

                if elapsed >= wait_for_git_sync:
                    console.print(
                        "[yellow]⚠️  Git Sync polling timed out "
                        f"after {wait_for_git_sync}s[/yellow]"
                    )
            else:
                console.print(
                    "[yellow]⚠️  Could not determine source workspace ID. "
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
                    f"[yellow]⚠️  {result.get('message', 'No items')}[/yellow]"
                )
            elif result["success"]:
                msg = result.get("message", "Promotion succeeded")
                console.print(f"[green]✅ {msg}[/green]")
            else:
                console.print(
                    f"[red]❌ Promotion failed: "
                    f"{result.get('error', 'unknown')}[/red]"
                )
                raise typer.Exit(1)
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
                    f"[green]✅ Promotion succeeded: {source_stage} → "
                    f"{display_target}[/green]"
                )
            else:
                console.print(
                    f"[red]❌ Promotion failed: "
                    f"{result.get('error', 'unknown')}[/red]"
                )
                raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Promote failed: {e}[/red]")
        raise typer.Exit(1)


# ──────────────────────────────────────────────────────────────────────
# Onboarding & Project Setup Commands
# ──────────────────────────────────────────────────────────────────────


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
            console.print(
                f"[red]❌ Invalid stage(s): {invalid}. Valid: {valid_stages}[/red]"
            )
            raise typer.Exit(1)

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
    except Exception as e:
        console.print(f"[red]Onboard failed: {e}[/red]")
        raise typer.Exit(1)


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
    except Exception as e:
        console.print(f"[red]❌ Generate failed: {e}[/red]")
        raise typer.Exit(1)


# ──────────────────────────────────────────────────────────────────────
# Admin Utility Commands
# ──────────────────────────────────────────────────────────────────────


@app.command("list-workspaces")
def list_workspaces():
    """List all Fabric workspaces"""
    import json

    try:
        env_vars = get_environment_variables()
        token = env_vars.get("FABRIC_TOKEN") or ""
        if not token:
            console.print("[red]❌ FABRIC_TOKEN is not set[/red]")
            raise typer.Exit(1)

        fabric = FabricCLIWrapper(token)
        console.print("[blue]Listing workspaces...[/blue]")

        result = fabric._execute_command(["ls", "--output_format", "json"])
        if result.get("success"):
            data = result.get("data")
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:
                    pass
            console.print(json.dumps(data, indent=2))
        else:
            console.print(f"[red]❌ {result.get('error')}[/red]")
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("list-items")
def list_items(
    workspace: str = typer.Argument(..., help="Workspace name to list items from"),
):
    """List items in a Fabric workspace"""
    try:
        env_vars = get_environment_variables()
        token = env_vars.get("FABRIC_TOKEN") or ""
        if not token:
            console.print("[red]❌ FABRIC_TOKEN is not set[/red]")
            raise typer.Exit(1)

        fabric = FabricCLIWrapper(token)
        console.print(f"[blue]Listing items in workspace '{workspace}'...[/blue]")

        result = fabric.list_workspace_items(workspace)
        if result.get("success"):
            data = result.get("data")
            items = data or []
            console.print(f"Found {len(items)} items:\n")
            console.print(f"  {'Name':<40} {'Type':<25} {'Description'}")
            console.print(f"  {'─' * 40} {'─' * 25} {'─' * 30}")
            for item in items:
                name = item.get("displayName", "N/A")
                item_type = item.get("type", "N/A")
                desc = item.get("description", "")
                console.print(f"  {name:<40} {item_type:<25} {desc}")
        else:
            console.print(f"[red]❌ {result.get('error')}[/red]")
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("bulk-destroy")
def bulk_destroy(
    file: str = typer.Argument(..., help="Path to file containing workspace list"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be deleted"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompt"),
):
    """Bulk destroy workspaces from a list file"""
    from pathlib import Path

    if not Path(file).exists():
        console.print(f"[red]❌ File '{file}' not found[/red]")
        raise typer.Exit(1)

    try:
        bulk_destroy_fn(file, dry_run, force)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Bulk destroy failed: {e}[/red]")
        raise typer.Exit(1)


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
            console.print("[red]❌ FABRIC_TOKEN is not set[/red]")
            raise typer.Exit(1)

        config_mgr = ConfigManager(config)
        cfg = config_mgr.load_config(environment)
        ws_name = workspace or cfg.name

        folder_rules = cfg.folder_rules or []
        if not folder_rules:
            console.print(
                "[yellow]No folder_rules defined in config "
                "— nothing to organize.[/yellow]"
            )
            raise typer.Exit(0)

        fabric = FabricCLIWrapper(token)
        console.print(f"[blue]Organizing items in workspace '{ws_name}'...[/blue]")

        if dry_run:
            console.print("[yellow]DRY RUN — no items will be moved.[/yellow]\n")
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
                        f"→ folder '{target_folder}'"
                    )
            raise typer.Exit(0)

        result = fabric.organize_items_into_folders(ws_name, folder_rules)
        console.print(
            f"\n[green]✅ Organize complete: "
            f"{result['moved']} moved, "
            f"{result['skipped']} skipped, "
            f"{result['failed']} failed[/green]"
        )
        for detail in result.get("details", []):
            status_icon = "✓" if detail["status"] == "moved" else "✗"
            console.print(
                f"  {status_icon} {detail.get('type', '')} "
                f"'{detail['item']}' → {detail['folder']} "
                f"({detail['status']})"
            )

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


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
            console.print("[red]❌ GITHUB_TOKEN is not set[/red]")
            raise typer.Exit(1)

        clone_url = init_github_repo_fn(
            owner=owner,
            repo_name=repo,
            token=token,
            branch=branch,
            private=private,
        )
        if clone_url:
            console.print(f"[green]✅ Repository ready: {clone_url}[/green]")
            # Show the browsable web URL for convenience
            web_url = clone_url.removesuffix(".git")
            console.print(f"[bold cyan]🔗 Open in browser:[/bold cyan] {web_url}")
        else:
            console.print("[red]❌ Failed to initialize repository[/red]")
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Init repo failed: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
