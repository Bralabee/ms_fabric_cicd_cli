"""
Microsoft Fabric CLI - Command-line interface for deployment automation.

This module provides the CLI entry points using Typer. The actual deployment
logic is in services/deployer.py (FabricDeployer class).
"""

import typer
import logging
from typing import Optional

from rich.console import Console

from usf_fabric_cli.utils.config import ConfigManager, get_environment_variables
from usf_fabric_cli.services.fabric_wrapper import FabricCLIWrapper, FabricDiagnostics
from usf_fabric_cli.services.deployer import FabricDeployer

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
):
    """Destroy Fabric workspace based on configuration"""

    try:
        config_manager = ConfigManager(config)
        workspace_config = config_manager.load_config(environment)

        workspace_name = workspace_name_override or workspace_config.name

        if not force:
            confirm = typer.confirm(
                f"Are you sure you want to destroy workspace '{workspace_name}'?"
            )
            if not confirm:
                console.print("[yellow]Aborted.[/yellow]")
                raise typer.Exit(0)

        console.print(f"[red]Destroying workspace: {workspace_name}[/red]")

        env_vars = get_environment_variables(validate_vars=True)
        fabric = FabricCLIWrapper(env_vars["FABRIC_TOKEN"])

        result = fabric.delete_workspace(workspace_name)

        if result["success"]:
            console.print(f"[green]✅ Workspace '{workspace_name}' destroyed[/green]")
        else:
            console.print(
                f"[red]❌ Failed to destroy workspace: {result.get('error')}[/red]"
            )
            raise typer.Exit(1)

    except Exception as e:
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
):
    """Promote content through Fabric Deployment Pipeline stages (Dev → Test → Prod)"""

    try:
        from usf_fabric_cli.services.deployment_pipeline import (
            FabricDeploymentPipelineAPI,
            DeploymentStage,
        )

        env_vars = get_environment_variables(validate_vars=True)

        api = FabricDeploymentPipelineAPI(access_token=env_vars["FABRIC_TOKEN"])

        pipeline = api.get_pipeline_by_name(pipeline_name)
        if not pipeline:
            console.print(f"[red]❌ Pipeline '{pipeline_name}' not found[/red]")
            raise typer.Exit(1)

        display_target = target_stage or DeploymentStage.next_stage(source_stage)
        console.print(f"[blue]🚀 Promoting: {source_stage} → {display_target}[/blue]")

        result = api.promote(
            pipeline_id=pipeline["id"],
            source_stage_name=source_stage,
            target_stage_name=target_stage,
            note=note,
            wait=True,
        )

        if result["success"]:
            console.print(
                f"[green]✅ Promotion succeeded: {source_stage} → "
                f"{display_target}[/green]"
            )
        else:
            console.print(
                f"[red]❌ Promotion failed: {result.get('error', 'unknown')}[/red]"
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
    import sys as _sys
    from pathlib import Path as _Path

    # Add scripts to path for onboard imports
    scripts_dir = _Path(__file__).resolve().parent.parent.parent / "scripts" / "dev"
    _sys.path.insert(0, str(scripts_dir))

    try:
        from onboard import onboard_project  # type: ignore[import]

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
    import sys as _sys
    from pathlib import Path as _Path

    scripts_dir = _Path(__file__).resolve().parent.parent.parent / "scripts" / "dev"
    _sys.path.insert(0, str(scripts_dir))

    try:
        from generate_project import generate_project_config  # type: ignore[import]

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
        import sys as _sys
        from pathlib import Path as _Path

        scripts_dir = (
            _Path(__file__).resolve().parent.parent.parent / "scripts" / "admin"
        )
        _sys.path.insert(0, str(scripts_dir))

        from bulk_destroy import bulk_destroy as _bulk_destroy  # type: ignore[import]

        _bulk_destroy(file, dry_run, force)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Bulk destroy failed: {e}[/red]")
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
        import sys as _sys
        from pathlib import Path as _Path

        scripts_dir = (
            _Path(__file__).resolve().parent.parent.parent
            / "scripts"
            / "admin"
            / "utilities"
        )
        _sys.path.insert(0, str(scripts_dir))

        from init_github_repo import init_github_repo as _init_repo  # type: ignore[import]

        token = os.getenv("GITHUB_TOKEN")
        if not token:
            console.print("[red]❌ GITHUB_TOKEN is not set[/red]")
            raise typer.Exit(1)

        clone_url = _init_repo(
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
            console.print(
                f"[bold cyan]🔗 Open in browser:[/bold cyan] {web_url}"
            )
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
