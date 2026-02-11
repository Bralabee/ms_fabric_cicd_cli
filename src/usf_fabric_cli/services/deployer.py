"""
Microsoft Fabric deployment orchestrator with enterprise features.

Coordinates workspace creation, artifact deployment, Git integration,
and audit logging. Supports environment-specific deployments with
automatic credential management and template-based transformations.
"""

import time
import logging
import os
import re
from typing import Optional, Dict

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from usf_fabric_cli.utils.config import ConfigManager, get_environment_variables
from usf_fabric_cli.services.fabric_wrapper import FabricCLIWrapper
from usf_fabric_cli.services.git_integration import GitFabricIntegration
from usf_fabric_cli.services.deployment_state import DeploymentState, ItemType
from usf_fabric_cli.utils.audit import AuditLogger
from usf_fabric_cli.services.fabric_git_api import FabricGitAPI, GitProviderType
from usf_fabric_cli.utils.secrets import FabricSecrets

logger = logging.getLogger(__name__)
console = Console()


class FabricDeployer:
    """
    Orchestrates Microsoft Fabric workspace deployments with integrated
    secret management, Git connectivity, and audit logging.
    """

    def __init__(self, config_path: str, environment: Optional[str] = None):
        # Ensure .env is loaded
        from dotenv import load_dotenv

        load_dotenv()

        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.load_config(environment)
        self.environment = environment

        self.secrets: Optional[FabricSecrets] = None
        try:
            self.secrets = FabricSecrets.load_with_fallback()
            is_valid, error_msg = self.secrets.validate_fabric_auth()
            if not is_valid:
                raise ValueError(error_msg)

            # Ensure token is available in environment
            if self.secrets and not os.getenv("FABRIC_TOKEN"):
                if self.secrets.fabric_token:
                    os.environ["FABRIC_TOKEN"] = self.secrets.fabric_token
                elif (
                    self.secrets.azure_client_id
                    and self.secrets.azure_client_secret
                    and self.secrets.tenant_id
                ):
                    console.print(
                        "[blue]Generating Fabric token from secrets...[/blue]"
                    )
                    from azure.identity import ClientSecretCredential

                    cred = ClientSecretCredential(
                        tenant_id=self.secrets.tenant_id,
                        client_id=self.secrets.azure_client_id,
                        client_secret=self.secrets.azure_client_secret,
                    )
                    token = cred.get_token(
                        "https://api.fabric.microsoft.com/.default"
                    ).token
                    os.environ["FABRIC_TOKEN"] = token

            env_vars = get_environment_variables()
        except ImportError:
            env_vars = get_environment_variables()
            self.secrets = None

        self.fabric = FabricCLIWrapper(env_vars["FABRIC_TOKEN"])
        self.git = GitFabricIntegration(self.fabric)
        self.git_api = FabricGitAPI(env_vars["FABRIC_TOKEN"])
        self.audit = AuditLogger()

        self.workspace_id = None
        self.items_created = 0
        self.deployment_state = DeploymentState()
        self._git_browse_url = None  # Browsable Git repo URL

    def _wait_for_propagation(self, progress, seconds: int, message: str):
        """Wait with visual feedback"""
        task = progress.add_task(f"[yellow]{message}[/yellow]", total=seconds)
        for _ in range(seconds):
            time.sleep(1)
            progress.update(task, advance=1)
        progress.update(task, visible=False)

    def deploy(
        self,
        branch: Optional[str] = None,
        force_branch_workspace: bool = False,
        rollback_on_failure: bool = False,
    ) -> bool:
        """Deploy workspace based on configuration

        Args:
            branch: Git branch to use
            force_branch_workspace: Create separate workspace for feature branch
            rollback_on_failure: If True, delete all created items on failure
        """

        start_time = time.time()
        self.deployment_state.start_deployment()

        # Determine workspace name (for feature branches)
        workspace_name = self.config.name
        if branch and branch != "main":
            if force_branch_workspace:
                workspace_name = self.git.get_workspace_name_from_branch(
                    self.config.name, branch
                )
                console.print(
                    f"[yellow]Creating branch-specific workspace: "
                    f"{workspace_name}[/yellow]"
                )

        # Log deployment start
        self.audit.log_deployment_start(
            config_file=str(self.config_manager.config_path),
            environment=self.environment,
            branch=branch,
        )

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:

                # Step 1: Create workspace
                task = progress.add_task("Creating workspace...", total=None)
                result = self._create_workspace(workspace_name)
                if not result["success"]:
                    console.print(
                        f"[red]Failed to create workspace: {result['error']}[/red]"
                    )
                    raise RuntimeError(f"Workspace creation failed: {result['error']}")

                # Track workspace for rollback
                self.deployment_state.record(
                    ItemType.WORKSPACE,
                    workspace_name,
                    workspace_name,
                    item_id=self.workspace_id,
                )
                progress.update(task, description="✅ Workspace created")

                # Wait for workspace propagation
                self._wait_for_propagation(
                    progress, 5, "Waiting for workspace propagation..."
                )

                # Step 2: Create folders
                task = progress.add_task("Creating folder structure...", total=None)
                self._create_folders()
                progress.update(task, description="✅ Folders created")

                # Wait for folder propagation
                self._wait_for_propagation(
                    progress, 5, "Waiting for folder propagation..."
                )

                # Step 3: Create items
                task = progress.add_task("Creating items...", total=None)
                self._create_items()
                progress.update(task, description="✅ Items created")

                # Wait for items propagation
                self._wait_for_propagation(
                    progress, 5, "Waiting for items propagation..."
                )

                # Step 4: Add principals
                task = progress.add_task("Adding principals...", total=None)
                self._add_principals()
                progress.update(task, description="✅ Principals added")

                # Step 5: Assign Domain (if configured)
                if self.config.domain:
                    task = progress.add_task(
                        f"Assigning to domain: {self.config.domain}...", total=None
                    )
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

        except Exception as e:
            console.print(f"[red]Deployment failed: {e}[/red]")

            if rollback_on_failure and self.deployment_state.item_count > 0:
                console.print(
                    f"[yellow]Rolling back {self.deployment_state.item_count} "
                    f"created items...[/yellow]"
                )
                rollback_result = self.deployment_state.rollback(self.fabric)

                if rollback_result["success"]:
                    console.print(
                        f"[green]✅ Rollback complete: {rollback_result['deleted']} "
                        f"items deleted[/green]"
                    )
                else:
                    console.print(
                        f"[red]Rollback completed with errors: "
                        f"{rollback_result['deleted']} deleted, "
                        f"{rollback_result['failed']} failed[/red]"
                    )
            elif self.deployment_state.item_count > 0:
                console.print(
                    "[yellow]Tip: Use --rollback-on-failure to auto-clean partial "
                    "deployments[/yellow]"
                )

            return False

    def _create_workspace(self, workspace_name: str) -> dict:
        """Create workspace"""
        # Note: CLI wrapper now expects capacity_name, but config has capacity_id
        # We will use capacity_id as capacity_name for now, assuming user configured
        # it correctly
        # or we need to update config schema to support capacity_name
        capacity_name = self.config.capacity_id

        # If capacity_id is a GUID, we might need to use capacityId parameter instead
        # of capacityName
        # But CLI wrapper uses -P capacityName=...
        # Let's try to pass it as is, but if it fails, we might need to adjust wrapper

        # WORKAROUND: If capacity assignment fails, try creating without capacity
        # This allows deployment to proceed on Trial/Pro workspaces

        result = self.fabric.create_workspace(
            name=workspace_name,
            capacity_name=capacity_name,
            description=self.config.description,
        )

        error_msg = str(result.get("error", "")).lower()

        data = result.get("data")
        error_code = ""
        if isinstance(data, dict):
            error_code = data.get("errorCode", "")

        if not result["success"] and (
            (
                "capacity" in error_msg
                or "entitynotfound" in error_msg
                or "could not be found" in error_msg
                or error_code == "EntityNotFound"
            )
            and "insufficientpermissionsovercapacity" not in error_msg
        ):
            console.print(
                "[yellow]Warning: Capacity assignment failed. Retrying without "
                "capacity...[/yellow]"
            )
            result = self.fabric.create_workspace(
                name=workspace_name,
                capacity_name=None,
                description=self.config.description,
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

        workspace_name = self.config.name  # We need name for CLI paths

        # Create lakehouses
        for lakehouse in self.config.lakehouses:
            result = self.fabric.create_lakehouse(
                workspace_name,
                lakehouse["name"],
                lakehouse.get("description", ""),
                folder=lakehouse.get("folder"),
            )

            if result["success"]:
                self.audit.log_item_creation(
                    "Lakehouse",
                    lakehouse["name"],
                    self.workspace_id,
                    self.config.name,
                    lakehouse.get("folder"),
                )
                if not result.get("reused"):
                    self.items_created += 1

        # Create warehouses
        for warehouse in self.config.warehouses:
            result = self.fabric.create_warehouse(
                workspace_name,
                warehouse["name"],
                warehouse.get("description", ""),
                folder=warehouse.get("folder"),
            )

            if result["success"]:
                self.audit.log_item_creation(
                    "Warehouse",
                    warehouse["name"],
                    self.workspace_id,
                    self.config.name,
                    warehouse.get("folder"),
                )
                if not result.get("reused"):
                    self.items_created += 1

        # Create notebooks
        for notebook in self.config.notebooks:
            result = self.fabric.create_notebook(
                workspace_name,
                notebook["name"],
                notebook.get("file_path"),
                folder=notebook.get("folder"),
            )

            if result["success"]:
                self.audit.log_item_creation(
                    "Notebook",
                    notebook["name"],
                    self.workspace_id,
                    self.config.name,
                    notebook.get("folder"),
                )
                if not result.get("reused"):
                    self.items_created += 1

        # Create pipelines
        for pipeline in self.config.pipelines:
            result = self.fabric.create_pipeline(
                workspace_name,
                pipeline["name"],
                pipeline.get("description", ""),
                folder=pipeline.get("folder"),
            )

            if result["success"]:
                self.audit.log_item_creation(
                    "Pipeline",
                    pipeline["name"],
                    self.workspace_id,
                    self.config.name,
                    pipeline.get("folder"),
                )
                if not result.get("reused"):
                    self.items_created += 1

        # Create semantic models
        for model in self.config.semantic_models:
            result = self.fabric.create_semantic_model(
                workspace_name,
                model["name"],
                model.get("description", ""),
                folder=model.get("folder"),
            )

            if result["success"]:
                self.audit.log_item_creation(
                    "SemanticModel",
                    model["name"],
                    self.workspace_id,
                    self.config.name,
                    model.get("folder"),
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
                folder=resource.get("folder"),
            )

            if result["success"]:
                self.audit.log_item_creation(
                    resource["type"],
                    resource["name"],
                    self.workspace_id,
                    self.config.name,
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
            principal_ids = (
                [pid.strip() for pid in principal_id_raw.split(",")]
                if "," in principal_id_raw
                else [principal_id_raw]
            )

            for pid in principal_ids:
                if not pid:
                    continue

                result = self.fabric.add_workspace_principal(
                    workspace_name, pid, principal.get("role", "Member")
                )

                if result["success"]:
                    self.audit.log_principal_assignment(
                        pid,
                        principal.get("role", "Member"),
                        self.workspace_id,
                        self.config.name,
                    )

    def _assign_domain(self):
        """Assign workspace to domain"""
        if self.config.domain:
            result = self.fabric.assign_to_domain(self.config.name, self.config.domain)
            if result["success"]:
                console.print(f"  Assigned to domain: {self.config.domain}")
            else:
                console.print(
                    f"[red]❌ Failed to assign domain: {result.get('error')}[/red]"
                )
                console.print(
                    "[yellow]   Note: Ensure the Service Principal is a Domain "
                    "Contributor or Fabric Admin.[/yellow]"
                )

    def _connect_git(self, branch: str):
        """
        Connect workspace to Git repository using Fabric Git REST APIs.

        This implements Gap Closing Enhancement: Automatic Git Connection
        """
        if not self.workspace_id:
            console.print("[red]Cannot connect Git: Workspace ID not available[/red]")
            return

        workspace_name = self.config.name
        git_repo = self.config.git_repo
        git_directory = self.config.git_directory or "/"

        console.print(
            f"[blue]Connecting workspace to Git repository: {git_repo}[/blue]"
        )
        console.print(f"  Branch: {branch}")
        console.print(f"  Directory: {git_directory}")

        # Parse Git URL to determine provider type and extract details
        git_details = self._parse_git_repo_url(git_repo)
        if not git_details:
            console.print(
                "[yellow]Warning: Could not parse Git URL. Skipping Git "
                "connection.[/yellow]"
            )
            return

        provider_type = git_details["provider_type"]

        try:
            # Step 1: Check if we need to create a connection (for authentication)
            connection_id = None

            if self.secrets:
                # Use new secrets module to get Git credentials
                if provider_type == GitProviderType.GITHUB:
                    is_valid, error_msg = self.secrets.validate_git_auth("github")
                    if is_valid and self.secrets.github_token:
                        # Create GitHub connection
                        console.print("[blue]Creating GitHub connection...[/blue]")
                        conn_result = self.git_api.create_git_connection(
                            display_name=f"GitHub-{workspace_name}",
                            provider_type=GitProviderType.GITHUB,
                            credential_type="Key",
                            credential_value=self.secrets.github_token,
                            repository_url=git_repo,
                        )

                        if conn_result["success"]:
                            connection_id = conn_result["connection"]["id"]
                            console.print(
                                f"[green]✓ Created GitHub connection: "
                                f"{connection_id}[/green]"
                            )
                        else:
                            console.print(
                                f"[yellow]Warning: Could not create connection: "
                                f"{conn_result.get('error')}[/yellow]"
                            )
                            console.print(
                                "[yellow]Attempting connection without explicit "
                                "credentials...[/yellow]"
                            )

                elif provider_type == GitProviderType.AZURE_DEVOPS:
                    # Check for Service Principal credentials
                    if (
                        self.secrets.azure_client_id
                        and self.secrets.azure_client_secret
                    ):
                        # Create Azure DevOps connection with Service Principal
                        console.print(
                            "[blue]Creating Azure DevOps connection...[/blue]"
                        )
                        # Reconstruct clean URL without credentials
                        clean_repo_url = (
                            f"https://dev.azure.com/{git_details['organization']}/"
                            f"{git_details['project']}/_git/{git_details['repo']}"
                        )

                        conn_result = self.git_api.create_git_connection(
                            display_name=f"AzureDevOps-{workspace_name}",
                            provider_type=GitProviderType.AZURE_DEVOPS,
                            credential_type="ServicePrincipal",
                            credential_value=self.secrets.azure_client_secret,
                            repository_url=clean_repo_url,
                            tenant_id=self.secrets.get_tenant_id(),
                            client_id=self.secrets.azure_client_id,
                        )

                        if conn_result["success"]:
                            connection_id = conn_result["connection"]["id"]
                            console.print(
                                f"[green]✓ Created Azure DevOps connection: "
                                f"{connection_id}[/green]"
                            )
                        else:
                            # Check if it's a duplicate connection
                            error_msg = str(conn_result.get("error", ""))
                            response_body = conn_result.get("response", "")

                            if (
                                "DuplicateConnectionName" in response_body
                                or "Conflict" in error_msg
                            ):
                                console.print(
                                    "[yellow]Connection name already exists. "
                                    "Trying to find existing connection...[/yellow]"
                                )
                                existing_conn = self.git_api.get_connection_by_name(
                                    f"AzureDevOps-{workspace_name}"
                                )
                                if existing_conn:
                                    connection_id = existing_conn["id"]
                                    console.print(
                                        f"[green]✓ Found existing connection: "
                                        f"{connection_id}[/green]"
                                    )
                                else:
                                    console.print(
                                        "[red]Could not find existing connection "
                                        "despite conflict error.[/red]"
                                    )
                            else:
                                console.print(
                                    f"[yellow]Warning: Could not create connection: "
                                    f"{conn_result.get('error')}[/yellow]"
                                )
                                console.print(
                                    "[yellow]Attempting connection without "
                                    "explicit credentials...[/yellow]"
                                )

            # Step 2: Connect workspace to Git
            console.print("[blue]Connecting workspace to Git repository...[/blue]")

            if provider_type == GitProviderType.GITHUB:
                result = self.git_api.connect_workspace_to_git(
                    workspace_id=self.workspace_id,
                    provider_type=GitProviderType.GITHUB,
                    connection_id=connection_id,
                    owner_name=git_details["owner"],
                    repository_name=git_details["repo"],
                    branch_name=branch,
                    directory_name=git_directory,
                )
            else:  # Azure DevOps
                result = self.git_api.connect_workspace_to_git(
                    workspace_id=self.workspace_id,
                    provider_type=GitProviderType.AZURE_DEVOPS,
                    connection_id=connection_id,
                    organization_name=git_details["organization"],
                    project_name=git_details["project"],
                    repository_name=git_details["repo"],
                    branch_name=branch,
                    directory_name=git_directory,
                )

            if not result["success"]:
                console.print(
                    f"[red]Failed to connect workspace to Git: "
                    f"{result.get('error')}[/red]"
                )
                console.print(
                    f"[yellow]Details: {result.get('details', 'N/A')}[/yellow]"
                )
                return

            console.print("[green]✓ Workspace connected to Git[/green]")

            # Show the browsable Git repo URL
            if provider_type == GitProviderType.GITHUB:
                browse_url = (
                    f"https://github.com/"
                    f"{git_details['owner']}/{git_details['repo']}"
                )
            else:
                browse_url = (
                    f"https://dev.azure.com/"
                    f"{git_details['organization']}/"
                    f"{git_details['project']}/"
                    f"_git/{git_details['repo']}"
                )
            self._git_browse_url = browse_url
            console.print(
                f"[bold cyan]🔗 Open repo in browser:[/bold cyan] "
                f"{browse_url}"
            )

            # Step 3: Initialize the Git connection
            console.print("[blue]Initializing Git connection...[/blue]")
            init_result = self.git_api.initialize_git_connection(self.workspace_id)

            if not init_result["success"]:
                console.print(
                    f"[yellow]Warning: Could not initialize Git connection: "
                    f"{init_result.get('error')}[/yellow]"
                )
                return

            required_action = init_result.get("required_action", "None")
            console.print(f"[blue]Required action: {required_action}[/blue]")

            # Step 4: Handle required action (UpdateFromGit if needed)
            if required_action == "UpdateFromGit":
                console.print("[blue]Updating workspace from Git repository...[/blue]")
                update_result = self.git_api.update_from_git(
                    workspace_id=self.workspace_id,
                    remote_commit_hash=init_result["remote_commit_hash"],
                    workspace_head=init_result["workspace_head"],
                )

                if update_result["success"]:
                    # Poll the operation
                    operation_id = update_result["operation_id"]
                    console.print(f"[blue]Polling operation {operation_id}...[/blue]")

                    poll_result = self.git_api.poll_operation(
                        operation_id=operation_id,
                        retry_after=update_result.get("retry_after", 5),
                    )

                    if poll_result["success"]:
                        console.print(
                            "[green]✓ Workspace updated from Git successfully[/green]"
                        )
                    else:
                        console.print(
                            f"[yellow]Warning: Git update operation status: "
                            f"{poll_result.get('status')}[/yellow]"
                        )
                else:
                    console.print(
                        f"[yellow]Warning: Could not update from Git: "
                        f"{update_result.get('error')}[/yellow]"
                    )

            # Log successful connection
            self.audit.log_git_connection(
                git_repo, branch, self.workspace_id, workspace_name
            )

        except Exception as e:
            console.print(f"[red]Error connecting to Git: {e}[/red]")
            import traceback

            console.print(f"[red]{traceback.format_exc()}[/red]")

    def _parse_git_repo_url(self, git_url: str) -> Optional[Dict[str, str]]:
        """
        Parse Git repository URL to extract provider type and details.

        Supports:
        - GitHub: https://github.com/owner/repo
        - Azure DevOps: https://dev.azure.com/org/project/_git/repo

        Returns:
            Dictionary with provider_type and extracted details, or None if parsing
            fails
        """
        # GitHub pattern
        github_pattern = (
            r"(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/]+?)" r"(?:\.git)?/?$"
        )
        github_match = re.match(github_pattern, git_url)

        if github_match:
            return {
                "provider_type": GitProviderType.GITHUB,
                "owner": github_match.group(1),
                "repo": github_match.group(2),
            }

        # Azure DevOps pattern
        ado_pattern = (
            r"(?:https?://)?(?:[^@]+@)?dev\.azure\.com/([^/]+)/([^/]+)/_git/([^/]+)/?$"
        )
        ado_match = re.match(ado_pattern, git_url)

        if ado_match:
            return {
                "provider_type": GitProviderType.AZURE_DEVOPS,
                "organization": ado_match.group(1),
                "project": ado_match.group(2),
                "repo": ado_match.group(3),
            }

        # Could not parse
        logger.warning(f"Could not parse Git URL: {git_url}")
        return None

    def _show_deployment_summary(
        self, workspace_name: str, duration: float
    ):
        """Show deployment summary"""

        summary_table = Table(
            title=f"Deployment Summary: {workspace_name}"
        )
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="green")

        summary_table.add_row(
            "Workspace ID", self.workspace_id or "N/A"
        )
        summary_table.add_row(
            "Items Created", str(self.items_created)
        )
        summary_table.add_row(
            "Duration", f"{duration:.2f} seconds"
        )
        summary_table.add_row(
            "Environment", self.environment or "default"
        )
        if self._git_browse_url:
            summary_table.add_row(
                "Git Repository", self._git_browse_url
            )

        console.print(summary_table)
        console.print(
            "\n[green]✅ Deployment completed successfully![/green]"
        )
