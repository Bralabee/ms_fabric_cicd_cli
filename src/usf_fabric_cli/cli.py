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


app = typer.Typer(help="Fabric CLI CI/CD - Thin Wrapper Solution")
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
        console.print(f"Folders: {', '.join(workspace_config.folders)}")
        console.print(f"Lakehouses: {len(workspace_config.lakehouses)}")
        console.print(f"Warehouses: {len(workspace_config.warehouses)}")
        console.print(f"Notebooks: {len(workspace_config.notebooks)}")

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
        console.print(
            f"[blue]🚀 Promoting: {source_stage} → {display_target}[/blue]"
        )

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


if __name__ == "__main__":
    app()
