"""
Main Deployment CLI - Thin Wrapper Component 5/5
~50 LOC - CLI interface and orchestration

Key Learning Applied: Simple User Experience
- Single command deployment
- Progress tracking
- Clear error messages with remediation
- Support for any organization/project configuration
"""

import typer
import time
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.table import Table

from core.config import ConfigManager, get_environment_variables
from core.fabric_wrapper import FabricCLIWrapper, FabricDiagnostics
from core.git_integration import GitFabricIntegration
from core.audit import AuditLogger

app = typer.Typer(help="Fabric CLI CI/CD - Thin Wrapper Solution")
console = Console()


class FabricDeployer:
    """Main deployment orchestrator - coordinates all components"""
    
    def __init__(self, config_path: str, environment: str = None):
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.load_config(environment)
        self.environment = environment
        
        # Initialize components
        env_vars = get_environment_variables()
        self.fabric = FabricCLIWrapper(env_vars['FABRIC_TOKEN'])
        self.git = GitFabricIntegration(self.fabric)
        self.audit = AuditLogger()
        
        self.workspace_id = None
        self.items_created = 0
    
    def _wait_for_propagation(self, progress, seconds: int, message: str):
        """Wait with visual feedback"""
        task = progress.add_task(f"[yellow]{message}[/yellow]", total=seconds)
        for _ in range(seconds):
            time.sleep(1)
            progress.update(task, advance=1)
        progress.update(task, visible=False)

    def deploy(self, branch: str = None, force_branch_workspace: bool = False) -> bool:
        """Deploy workspace based on configuration"""
        
        start_time = time.time()
        
        # Determine workspace name (for feature branches)
        workspace_name = self.config.name
        if branch and branch != "main":
            if force_branch_workspace:
                workspace_name = self.git.get_workspace_name_from_branch(self.config.name, branch)
                console.print(f"[yellow]Creating branch-specific workspace: {workspace_name}[/yellow]")
        
        # Log deployment start
        self.audit.log_deployment_start(
            config_file=str(self.config_manager.config_path),
            environment=self.environment,
            branch=branch
        )
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            # Step 1: Create workspace
            task = progress.add_task("Creating workspace...", total=None)
            result = self._create_workspace(workspace_name)
            if not result["success"]:
                console.print(f"[red]Failed to create workspace: {result['error']}[/red]")
                return False
            progress.update(task, description="✅ Workspace created")
            
            # Wait for workspace propagation
            self._wait_for_propagation(progress, 5, "Waiting for workspace propagation...")
            
            # Step 2: Create folders
            task = progress.add_task("Creating folder structure...", total=None)
            self._create_folders()
            progress.update(task, description="✅ Folders created")
            
            # Wait for folder propagation
            self._wait_for_propagation(progress, 5, "Waiting for folder propagation...")
            
            # Step 3: Create items
            task = progress.add_task("Creating items...", total=None)
            self._create_items()
            progress.update(task, description="✅ Items created")
            
            # Wait for items propagation
            self._wait_for_propagation(progress, 5, "Waiting for items propagation...")
            
            # Step 4: Add principals
            task = progress.add_task("Adding principals...", total=None)
            self._add_principals()
            progress.update(task, description="✅ Principals added")
            
            # Step 5: Assign Domain (if configured)
            if self.config.domain:
                task = progress.add_task(f"Assigning to domain: {self.config.domain}...", total=None)
                self._assign_domain()
                progress.update(task, description="✅ Domain assigned")

            # Step 6: Connect Git (if configured)
            if self.config.git_repo:
                task = progress.add_task("Connecting Git...", total=None)
                git_branch = branch or self.config.git_branch
                self._connect_git(git_branch)
                progress.update(task, description="✅ Git connected")
        
        # Log completion
        duration = time.time() - start_time
        self.audit.log_deployment_complete(
            workspace_name, self.workspace_id, self.items_created, duration
        )
        
        # Show summary
        self._show_deployment_summary(workspace_name, duration)
        
        return True
    
    def _create_workspace(self, workspace_name: str) -> dict:
        """Create workspace"""
        # Note: CLI wrapper now expects capacity_name, but config has capacity_id
        # We will use capacity_id as capacity_name for now, assuming user configured it correctly
        # or we need to update config schema to support capacity_name
        capacity_name = self.config.capacity_id 
        
        # If capacity_id is a GUID, we might need to use capacityId parameter instead of capacityName
        # But CLI wrapper uses -P capacityName=...
        # Let's try to pass it as is, but if it fails, we might need to adjust wrapper
        
        # WORKAROUND: If capacity assignment fails, try creating without capacity
        # This allows deployment to proceed on Trial/Pro workspaces
        
        result = self.fabric.create_workspace(
            name=workspace_name,
            capacity_name=capacity_name,
            description=self.config.description
        )
        
        error_msg = str(result.get("error", "")).lower()
        
        data = result.get("data")
        error_code = ""
        if isinstance(data, dict):
            error_code = data.get("errorCode", "")
        
        if not result["success"] and (
            "capacity" in error_msg or 
            "entitynotfound" in error_msg or 
            "could not be found" in error_msg or
            error_code == "EntityNotFound"
        ):
            console.print("[yellow]Warning: Capacity assignment failed. Retrying without capacity...[/yellow]")
            result = self.fabric.create_workspace(
                name=workspace_name,
                capacity_name=None,
                description=self.config.description
            )
        
        if result["success"]:
            self.workspace_id = result.get("workspace_id")
            self.audit.log_workspace_creation(
                workspace_name, self.workspace_id, self.config.capacity_id
            )
        
        return result
    
    def _create_folders(self):
        """Create folder structure"""
        if self.config.folders:
            console.print("[blue]Creating folders...[/blue]")
            for folder in self.config.folders:
                result = self.fabric.create_folder(self.config.name, folder)
                if result["success"]:
                    console.print(f"  Created folder: {folder}")
    
    def _create_items(self):
        """Create all configured items"""
        
        workspace_name = self.config.name # We need name for CLI paths
        
        # Create lakehouses
        for lakehouse in self.config.lakehouses:
            result = self.fabric.create_lakehouse(
                workspace_name,
                lakehouse["name"],
                lakehouse.get("description", ""),
                folder=lakehouse.get("folder")
            )
            
            if result["success"]:
                self.audit.log_item_creation(
                    "Lakehouse", lakehouse["name"], self.workspace_id, 
                    self.config.name, lakehouse.get("folder")
                )
                if not result.get("reused"):
                    self.items_created += 1
        
        # Create warehouses
        for warehouse in self.config.warehouses:
            result = self.fabric.create_warehouse(
                workspace_name,
                warehouse["name"],
                warehouse.get("description", ""),
                folder=warehouse.get("folder")
            )
            
            if result["success"]:
                self.audit.log_item_creation(
                    "Warehouse", warehouse["name"], self.workspace_id,
                    self.config.name, warehouse.get("folder")
                )
                if not result.get("reused"):
                    self.items_created += 1
        
        # Create notebooks
        for notebook in self.config.notebooks:
            result = self.fabric.create_notebook(
                workspace_name,
                notebook["name"],
                notebook.get("file_path"),
                folder=notebook.get("folder")
            )
            
            if result["success"]:
                self.audit.log_item_creation(
                    "Notebook", notebook["name"], self.workspace_id,
                    self.config.name, notebook.get("folder")
                )
                if not result.get("reused"):
                    self.items_created += 1

        # Create pipelines
        for pipeline in self.config.pipelines:
            result = self.fabric.create_pipeline(
                workspace_name,
                pipeline["name"],
                pipeline.get("description", ""),
                folder=pipeline.get("folder")
            )
            
            if result["success"]:
                self.audit.log_item_creation(
                    "Pipeline", pipeline["name"], self.workspace_id,
                    self.config.name, pipeline.get("folder")
                )
                if not result.get("reused"):
                    self.items_created += 1

        # Create semantic models
        for model in self.config.semantic_models:
            result = self.fabric.create_semantic_model(
                workspace_name,
                model["name"],
                model.get("description", ""),
                folder=model.get("folder")
            )
            
            if result["success"]:
                self.audit.log_item_creation(
                    "SemanticModel", model["name"], self.workspace_id,
                    self.config.name, model.get("folder")
                )
                if not result.get("reused"):
                    self.items_created += 1
        
        # Create generic resources (Future-proof)
        for resource in self.config.resources:
            result = self.fabric.create_item(
                workspace_name,
                resource["name"],
                resource["type"],
                resource.get("description", ""),
                folder=resource.get("folder")
            )
            
            if result["success"]:
                self.audit.log_item_creation(
                    resource["type"], resource["name"], self.workspace_id,
                    self.config.name
                )
                if not result.get("reused"):
                    self.items_created += 1
    
    def _add_principals(self):
        """Add principals to workspace"""
        workspace_name = self.config.name
        for principal in self.config.principals:
            # Handle comma-separated lists of IDs (e.g. from env vars)
            principal_id_raw = principal["id"]
            if not principal_id_raw:
                continue
                
            # Split by comma if present, otherwise use as single item
            principal_ids = [pid.strip() for pid in principal_id_raw.split(',')] if ',' in principal_id_raw else [principal_id_raw]
            
            for pid in principal_ids:
                if not pid:
                    continue
                    
                result = self.fabric.add_workspace_principal(
                    workspace_name,
                    pid,
                    principal.get("role", "Member")
                )
                
                if result["success"]:
                    self.audit.log_principal_assignment(
                        pid, principal.get("role", "Member"),
                        self.workspace_id, self.config.name
                    )

    def _assign_domain(self):
        """Assign workspace to domain"""
        if self.config.domain:
            result = self.fabric.assign_to_domain(self.config.name, self.config.domain)
            if result["success"]:
                console.print(f"  Assigned to domain: {self.config.domain}")
            else:
                console.print(f"[red]❌ Failed to assign domain: {result.get('error')}[/red]")
                console.print(f"[yellow]   Note: Ensure the Service Principal is a Domain Contributor or Fabric Admin.[/yellow]")
    
    def _connect_git(self, branch: str):
        """Connect workspace to Git"""
        workspace_name = self.config.name
        result = self.fabric.connect_git(
            workspace_name,
            self.config.git_repo,
            branch,
            self.config.git_directory
        )
        
        if result["success"]:
            self.audit.log_git_connection(
                self.config.git_repo, branch, self.workspace_id, self.config.name
            )
    
    def _show_deployment_summary(self, workspace_name: str, duration: float):
        """Show deployment summary"""
        
        summary_table = Table(title=f"Deployment Summary: {workspace_name}")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="green")
        
        summary_table.add_row("Workspace ID", self.workspace_id or "N/A")
        summary_table.add_row("Items Created", str(self.items_created))
        summary_table.add_row("Duration", f"{duration:.2f} seconds")
        summary_table.add_row("Environment", self.environment or "default")
        
        console.print(summary_table)
        console.print(f"\n[green]✅ Deployment completed successfully![/green]")


@app.command()
def deploy(
    config: str = typer.Argument(..., help="Path to configuration file"),
    environment: Optional[str] = typer.Option(None, "--env", "-e", help="Environment (dev/staging/prod)"),
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Git branch to use"),
    force_branch_workspace: bool = typer.Option(False, "--force-branch-workspace", help="Create separate workspace for feature branch"),
    validate_only: bool = typer.Option(False, "--validate-only", help="Only validate configuration"),
    diagnose: bool = typer.Option(False, "--diagnose", help="Run diagnostic checks before deployment")
):
    """Deploy Fabric workspace based on configuration"""
    
    if diagnose:
        console.print("[blue]Running pre-flight diagnostics...[/blue]")
        try:
            # We can't use the diagnose command directly as it's a separate command
            # So we'll instantiate the diagnostics class here
            env_vars = get_environment_variables()
            fabric = FabricCLIWrapper(env_vars['FABRIC_TOKEN'])
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
            config_manager = ConfigManager(config)
            workspace_config = config_manager.load_config(environment)
            console.print("[green]✅ Configuration is valid[/green]")
            return
        except Exception as e:
            console.print(f"[red]❌ Configuration validation failed: {e}[/red]")
            raise typer.Exit(1)
    
    try:
        deployer = FabricDeployer(config, environment)
        success = deployer.deploy(branch, force_branch_workspace)
        
        if not success:
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"[red]Deployment failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def validate(
    config: str = typer.Argument(..., help="Path to configuration file"),
    environment: Optional[str] = typer.Option(None, "--env", "-e", help="Environment")
):
    """Validate configuration file"""
    
    try:
        config_manager = ConfigManager(config)
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
        env_vars = get_environment_variables()
        fabric = FabricCLIWrapper(env_vars['FABRIC_TOKEN'])
        diagnostics = FabricDiagnostics(fabric)
        
        # Check Fabric CLI installation
        cli_check = diagnostics.validate_fabric_cli_installation()
        if cli_check["success"]:
            console.print(f"[green]✅ {cli_check['message']} ({cli_check['version']})[/green]")
        else:
            console.print(f"[red]❌ {cli_check['error']}[/red]")
            console.print(f"   Remediation: {cli_check['remediation']}")
        
        # Check authentication
        auth_check = diagnostics.validate_authentication()
        if auth_check["success"]:
            console.print(f"[green]✅ {auth_check['message']}[/green]")
        else:
            console.print(f"[red]❌ {auth_check['error']}[/red]")
            console.print(f"   Remediation: {auth_check['remediation']}")
            
    except Exception as e:
        console.print(f"[red]Diagnostics failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def destroy(
    config: str = typer.Argument(..., help="Path to configuration file"),
    environment: Optional[str] = typer.Option(None, "--env", "-e", help="Environment (dev/staging/prod)"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without confirmation")
):
    """Destroy Fabric workspace based on configuration"""
    
    try:
        config_manager = ConfigManager(config)
        workspace_config = config_manager.load_config(environment)
        workspace_name = workspace_config.name
        
        if not force:
            confirm = typer.confirm(f"Are you sure you want to DESTROY workspace '{workspace_name}'? This action cannot be undone.")
            if not confirm:
                console.print("[yellow]Operation cancelled[/yellow]")
                raise typer.Exit(0)
        
        console.print(f"[red]Destroying workspace: {workspace_name}[/red]")
        
        env_vars = get_environment_variables()
        fabric = FabricCLIWrapper(env_vars['FABRIC_TOKEN'])
        
        result = fabric.delete_workspace(workspace_name)
        
        if result["success"]:
            console.print(f"[green]✅ Workspace '{workspace_name}' destroyed successfully[/green]")
        else:
            console.print(f"[red]❌ Failed to destroy workspace: {result.get('error')}[/red]")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"[red]Destroy failed: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()