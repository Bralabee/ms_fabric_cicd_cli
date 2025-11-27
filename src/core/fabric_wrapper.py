"""Fabric CLI Wrapper - Thin Wrapper Component 2/5."""

from __future__ import annotations

import json
import logging
import subprocess
import time
import re
from typing import Any, Dict, List, Optional
import os

from core.exceptions import FabricCLIError, FabricCLINotFoundError, FabricTelemetryError
from core.telemetry import TelemetryClient

logger = logging.getLogger(__name__)


class FabricCLIWrapper:
    """Thin wrapper around Fabric CLI with idempotency and error handling."""

    def __init__(self, fabric_token: str, telemetry_client: Optional[TelemetryClient] = None):
        self.fabric_token = fabric_token
        self.telemetry = telemetry_client or TelemetryClient()
        self._last_command: List[str] | None = None
        self._setup_auth()
    
    def _setup_auth(self):
        """Setup Fabric CLI authentication"""
        # We rely on explicit login with Service Principal if credentials are available.
        # This ensures the CLI has a valid token in its cache.
        
        client_id = os.getenv('AZURE_CLIENT_ID')
        client_secret = os.getenv('AZURE_CLIENT_SECRET')
        tenant_id = os.getenv('TENANT_ID') or os.getenv('AZURE_TENANT_ID')
        
        if client_id and client_secret and tenant_id:
            try:
                logger.info("Attempting to login to Fabric CLI with Service Principal...")
                
                # Logout first to clear any stale state
                try:
                    subprocess.run(['fab', 'auth', 'logout'], capture_output=True, check=False)
                except Exception:
                    pass

                # We use subprocess directly here to avoid infinite recursion if we used _run_fabric_command
                # Using short flags -u and -p as per some CLI versions preference
                cmd = ['fab', 'auth', 'login', '--username', client_id, '--password', client_secret, '--tenant', tenant_id]
                
                subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.info("Successfully logged in to Fabric CLI")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to login to Fabric CLI: {e.stderr}")
                # We don't raise here, as we might still be able to run if there's an existing token,
                # although unlikely if explicit login failed.
    
    def _emit_telemetry(self, event: str, command: List[str], duration: float, **extra: Any) -> None:
        payload = {
            "command": " ".join(command),
            "duration_ms": round(duration * 1000, 2),
            **extra,
        }
        try:
            self.telemetry.emit(event, payload)
        except FabricTelemetryError as exc:
            logger.debug("Telemetry write failed: %s", exc)

    def _run_command(self, command: List[str]) -> dict:
        """Run Fabric CLI command"""
        try:
            # Use 'fabric-cli' instead of 'fab' if 'fab' is not found
            executable = "fabric-cli"
            
            # Construct command
            full_command = [executable] + command
            
            # Prepare environment
            env = os.environ.copy()
            # Remove SP credentials to force use of cached token from _setup_auth
            env.pop('AZURE_CLIENT_ID', None)
            env.pop('AZURE_CLIENT_SECRET', None)
            env.pop('AZURE_TENANT_ID', None)
            env.pop('TENANT_ID', None)
            env.pop('FABRIC_TOKEN', None)
            env.pop('AZURE_ACCESS_TOKEN', None)
            
            # Run command
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                env=env
            )
            return {"success": True, "data": result.stdout}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_command(self, command: List[str], check_existence: bool = False) -> Dict[str, Any]:
        try:
            return self._run_fabric_command(command, check_existence)
        except FabricCLIError as exc:
            return {"success": False, "error": str(exc), "exception": exc}

    def _run_fabric_command(self, command: List[str], check_existence: bool = False) -> Dict[str, Any]:
        """Execute Fabric CLI command with error handling and telemetry."""
        # The Microsoft Fabric CLI command is 'fab', not 'fabric'
        # But we are using 'fabric-cli' executable now
        full_command = ['fab'] + command
        start_time = time.time()
        self._last_command = full_command

        # Prepare environment
        env = os.environ.copy()
        # Remove SP credentials to force use of cached token from _setup_auth
        env.pop('AZURE_CLIENT_ID', None)
        env.pop('AZURE_CLIENT_SECRET', None)
        env.pop('AZURE_TENANT_ID', None)
        env.pop('TENANT_ID', None)
        env.pop('FABRIC_TOKEN', None)
        env.pop('AZURE_ACCESS_TOKEN', None)

        try:
            logger.info("Executing: %s", ' '.join(full_command))
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                check=True,
                env=env
            )

            payload: Dict[str, Any] = {"success": True, "data": None}
            if result.stdout.strip():
                try:
                    payload["data"] = json.loads(result.stdout)
                except json.JSONDecodeError:
                    payload["data"] = result.stdout.strip()

            self._emit_telemetry(
                "fabric_cli.success",
                full_command,
                time.time() - start_time,
                reused=payload.get("reused", False)
            )
            return payload

        except FileNotFoundError as exc:
            error = FabricCLINotFoundError(full_command)
            self._emit_telemetry("fabric_cli.failure", full_command, time.time() - start_time, error=str(error))
            logger.error("Fabric CLI binary not found: %s", exc)
            raise error from exc

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else ""
            output_msg = e.stdout.strip() if e.stdout else ""
            full_msg = f"{error_msg} {output_msg}"

            if check_existence and ("already exists" in full_msg.lower() or
                                    "duplicate" in full_msg.lower() or
                                    "already has a role assigned" in full_msg.lower() or
                                    "an item with the same name exists" in full_msg.lower()):
                logger.debug("Item already exists - continuing (idempotent)")
                payload = {"success": True, "data": "already_exists", "reused": True}
                self._emit_telemetry("fabric_cli.success", full_command, time.time() - start_time, reused=True)
                return payload

            error = FabricCLIError(full_command, e.returncode, full_msg or str(e), e.stdout)
            self._emit_telemetry(
                "fabric_cli.failure",
                full_command,
                time.time() - start_time,
                error=str(error)
            )
            logger.error("Fabric CLI error: %s", full_msg)
            raise error
    
    def _item_exists(self, path: str) -> bool:
        """Check if an item exists using 'fab exists'"""
        try:
            # 'fab exists' returns exit code 0 if exists, non-zero if not
            # We use subprocess directly to avoid raising exceptions on non-zero
            cmd = ['fab', 'exists', path]
            result = subprocess.run(cmd, capture_output=True, check=False)
            return result.returncode == 0
        except Exception:
            return False

    def create_workspace(self, name: str, capacity_name: str = None, description: str = "") -> Dict[str, Any]:
        """Create workspace with idempotency"""
        
        # Check existence first
        if self._item_exists(f"{name}.Workspace"):
            logger.info(f"Workspace {name} already exists. Retrieving details...")
            workspace_info = self.get_workspace(name)
            workspace_id = None
            if workspace_info.get("success") and workspace_info.get("data"):
                data = workspace_info["data"]
                if isinstance(data, dict) and "result" in data and "data" in data["result"] and len(data["result"]["data"]) > 0:
                     workspace_id = data["result"]["data"][0].get("id")
                else:
                     workspace_id = data.get("id")
            
            return {"success": True, "data": "already_exists", "reused": True, "workspace_id": workspace_id}

        # Use 'mkdir' with -P capacityName=...
        command = ["mkdir", f"{name}.Workspace"]
        
        if capacity_name:
             command.extend(["-P", f"capacityName={capacity_name}"])

        # Description is not directly supported by mkdir -P for workspace in CLI help, 
        # but we can try to set it later if needed. For now, we skip it to avoid errors.
        
        result = self._execute_command(command, check_existence=True)

        if result.get("success"):
            # Wait for propagation
            time.sleep(5)
            
            # We need to return the workspace ID for other operations
            # 'fab get name.Workspace' should return details
            workspace_info = self.get_workspace(name)
            if workspace_info.get("success") and workspace_info.get("data"):
                data = workspace_info["data"]
                # Handle nested structure from CLI
                if isinstance(data, dict) and "result" in data and "data" in data["result"] and len(data["result"]["data"]) > 0:
                     result["workspace_id"] = data["result"]["data"][0].get("id")
                else:
                     result["workspace_id"] = data.get("id")

        return result
    
    def delete_workspace(self, name: str) -> Dict[str, Any]:
        """Delete workspace"""
        command = ["rm", f"{name}.Workspace", "--force"]
        return self._execute_command(command)

    def get_workspace(self, name: str) -> Dict[str, Any]:
        """Get workspace by name"""
        command = ["get", f"{name}.Workspace", "-q", ".", "--output_format", "json"]
        return self._execute_command(command)
    
    def create_folder(self, workspace_name: str, folder_name: str) -> Dict[str, Any]:
        """Create folder in workspace"""
        path = f"{workspace_name}.Workspace/{folder_name}"
        if self._item_exists(path):
            logger.info(f"Folder {folder_name} already exists.")
            return {"success": True, "data": "already_exists", "reused": True}

        command = ["mkdir", path]
        return self._execute_command(command, check_existence=True)
    
    def create_lakehouse(self, workspace_name: str, name: str, description: str = "", folder: str = None) -> Dict[str, Any]:
        """Create lakehouse"""
        if folder:
            path = f"{workspace_name}.Workspace/{folder}/{name}.Lakehouse"
        else:
            path = f"{workspace_name}.Workspace/{name}.Lakehouse"
            
        if self._item_exists(path):
            logger.info(f"Lakehouse {name} already exists.")
            return {"success": True, "data": "already_exists", "reused": True}

        command = ["mkdir", path]
        return self._execute_command(command, check_existence=True)
    
    def create_warehouse(self, workspace_name: str, name: str, description: str = "", folder: str = None) -> Dict[str, Any]:
        """Create warehouse"""
        if folder:
            path = f"{workspace_name}.Workspace/{folder}/{name}.Warehouse"
        else:
            path = f"{workspace_name}.Workspace/{name}.Warehouse"
            
        if self._item_exists(path):
            logger.info(f"Warehouse {name} already exists.")
            return {"success": True, "data": "already_exists", "reused": True}

        command = ["mkdir", path]
        return self._execute_command(command, check_existence=True)
    
    def create_notebook(self, workspace_name: str, name: str, file_path: str = None, folder: str = None) -> Dict[str, Any]:
        """Create notebook"""
        if folder:
            path = f"{workspace_name}.Workspace/{folder}/{name}.Notebook"
        else:
            path = f"{workspace_name}.Workspace/{name}.Notebook"
            
        if self._item_exists(path):
            logger.info(f"Notebook {name} already exists.")
            return {"success": True, "data": "already_exists", "reused": True}

        command = ["mkdir", path]
        # If file_path is provided, we might need to import content. 
        # CLI 'mkdir' creates empty. 'import' might be needed for content.
        return self._execute_command(command, check_existence=True)
    
    def create_pipeline(self, workspace_name: str, name: str, description: str = "", folder: str = None) -> Dict[str, Any]:
        """Create data pipeline"""
        if folder:
            path = f"{workspace_name}.Workspace/{folder}/{name}.DataPipeline"
        else:
            path = f"{workspace_name}.Workspace/{name}.DataPipeline"
            
        if self._item_exists(path):
            logger.info(f"Pipeline {name} already exists.")
            return {"success": True, "data": "already_exists", "reused": True}

        command = ["mkdir", path]
        return self._execute_command(command, check_existence=True)

    def create_semantic_model(self, workspace_name: str, name: str, description: str = "", folder: str = None) -> Dict[str, Any]:
        """Create semantic model"""
        if folder:
            path = f"{workspace_name}.Workspace/{folder}/{name}.SemanticModel"
        else:
            path = f"{workspace_name}.Workspace/{name}.SemanticModel"
            
        if self._item_exists(path):
            logger.info(f"Semantic Model {name} already exists.")
            return {"success": True, "data": "already_exists", "reused": True}

        command = ["mkdir", path]
        return self._execute_command(command, check_existence=True)
    
    def create_item(self, workspace_name: str, name: str, item_type: str, description: str = "", folder: str = None) -> Dict[str, Any]:
        """Create any generic Fabric item (Future-proof)"""
        # Ensure item_type is capitalized correctly if needed, but usually CLI is case-insensitive or expects PascalCase
        # We assume user provides correct type e.g. "Eventstream"
        
        if folder:
            path = f"{workspace_name}.Workspace/{folder}/{name}.{item_type}"
        else:
            path = f"{workspace_name}.Workspace/{name}.{item_type}"
            
        if self._item_exists(path):
            logger.info(f"{item_type} {name} already exists.")
            return {"success": True, "data": "already_exists", "reused": True}

        command = ["mkdir", path]
        return self._execute_command(command, check_existence=True)
    
    def add_workspace_principal(self, workspace_name: str, principal_id: str,
                               role: str = "Member") -> Dict[str, Any]:
        """Add principal (user/service principal) to workspace"""
        # Skip placeholder emails
        if not principal_id or "your-company.com" in principal_id or "example.com" in principal_id:
            logger.warning(f"Skipping placeholder principal: {principal_id}")
            return {"success": True, "message": "Skipped placeholder principal", "skipped": True}

        # Use 'acl set'
        command = [
            "acl", "set", f"{workspace_name}.Workspace",
            "--identity", principal_id,
            "--role", role,
            "--force"  # Skip confirmation prompt
        ]
        return self._execute_command(command, check_existence=True)
    
    def _parse_git_url(self, git_url: str) -> Dict[str, str]:
        """Parse Git URL to extract details"""
        # Azure DevOps URL formats:
        # 1. https://dev.azure.com/{org}/{project}/_git/{repo}
        # 2. https://{org}.visualstudio.com/{project}/_git/{repo}
        
        # Format 1 (ADO)
        match1 = re.search(r'https://dev\.azure\.com/([^/]+)/([^/]+)/_git/([^/]+)', git_url)
        if match1:
            return {
                "gitProviderType": "AzureDevOps",
                "organizationName": match1.group(1),
                "projectName": match1.group(2),
                "repositoryName": match1.group(3)
            }
            
        # Format 2 (ADO)
        match2 = re.search(r'https://([^.]+)\.visualstudio\.com/([^/]+)/_git/([^/]+)', git_url)
        if match2:
            return {
                "gitProviderType": "AzureDevOps",
                "organizationName": match2.group(1),
                "projectName": match2.group(2),
                "repositoryName": match2.group(3)
            }

        # GitHub URL format
        # https://github.com/{owner}/{repo}
        match3 = re.search(r'https://github\.com/([^/]+)/([^/.]+)(?:\.git)?', git_url)
        if match3:
             return {
                "gitProviderType": "GitHub",
                "ownerName": match3.group(1),
                "repositoryName": match3.group(2)
            }
            
        return {}

    def connect_git(self, workspace_name: str, git_repo: str, branch: str = "main",
                   directory: str = "/") -> Dict[str, Any]:
        """Connect workspace to Git repository"""
        
        # 1. Get Workspace ID
        workspace_info = self.get_workspace(workspace_name)
        workspace_id = None
        if workspace_info.get("success") and workspace_info.get("data"):
            data = workspace_info["data"]
            if isinstance(data, dict) and "result" in data and "data" in data["result"] and len(data["result"]["data"]) > 0:
                 workspace_id = data["result"]["data"][0].get("id")
            else:
                 workspace_id = data.get("id")
        
        if not workspace_id:
            return {"success": False, "error": f"Could not find workspace ID for {workspace_name}"}

        # 2. Parse Git URL
        git_details = self._parse_git_url(git_repo)
        if not git_details:
            return {"success": False, "error": f"Could not parse Git URL: {git_repo}. Expected Azure DevOps or GitHub URL."}
        
        # 3. Construct Payload
        provider_type = git_details.get("gitProviderType", "AzureDevOps")
        
        if provider_type == "GitHub":
             payload = {
                "gitProviderDetails": {
                    "gitProviderType": "GitHub",
                    "ownerName": git_details["ownerName"],
                    "repositoryName": git_details["repositoryName"],
                    "branchName": branch,
                    "directoryName": directory
                }
            }
        else:
            # Azure DevOps
            payload = {
                "gitProviderDetails": {
                    "gitProviderType": "AzureDevOps",
                    "organizationName": git_details["organizationName"],
                    "projectName": git_details["projectName"],
                    "repositoryName": git_details["repositoryName"],
                    "branchName": branch,
                    "directoryName": directory
                }
            }
        
        # 4. Call Fabric API
        # Endpoint: POST https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/git/connect
        endpoint = f"v1/workspaces/{workspace_id}/git/connect"
        
        # Use 'fab api' command
        # fab api <endpoint> -X POST -i <json_string>
        command = [
            "api", endpoint,
            "-X", "POST",
            "-i", json.dumps(payload)
        ]
        
        logger.info(f"Connecting workspace {workspace_name} to Git repo {git_repo}...")
        return self._execute_command(command)
    
    def list_workspace_items(self, workspace_name: str) -> Dict[str, Any]:
        """List all items in workspace"""
        command = ["ls", f"{workspace_name}.Workspace"]
        return self._execute_command(command)
    
    def get_folder_id(self, workspace_name: str, folder_name: str) -> Optional[str]:
        """Get folder ID by name"""
        # Not supported
        return None
    
    def wait_for_operation(self, operation_id: str, max_wait_seconds: int = 300) -> bool:
        """Wait for long-running operation to complete"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait_seconds:
            command = ["operation", "show", "--operation-id", operation_id]
            result = self._execute_command(command)
            
            if result.get("success") and result.get("data"):
                status = result["data"].get("status", "Unknown")
                if status in ["Succeeded", "Completed"]:
                    return True
                elif status in ["Failed", "Cancelled"]:
                    logger.error(f"Operation {operation_id} failed with status: {status}")
                    return False
            
            time.sleep(10)  # Wait 10 seconds before checking again
        
        logger.error(f"Operation {operation_id} timed out after {max_wait_seconds} seconds")
        return False


class FabricDiagnostics:
    """Diagnostic utilities for troubleshooting"""
    
    def __init__(self, cli_wrapper: FabricCLIWrapper):
        self.cli = cli_wrapper
    
    def validate_fabric_cli_installation(self) -> Dict[str, Any]:
        """Validate Fabric CLI is properly installed"""
        try:
            result = subprocess.run(
                ['fab', '--version'],
                capture_output=True,
                text=True,
                check=True
            )
            return {
                "success": True,
                "version": result.stdout.strip(),
                "message": "Fabric CLI is properly installed"
            }
        except (subprocess.CalledProcessError, FileNotFoundError):
            return {
                "success": False,
                "error": "Fabric CLI not found or not properly installed",
                "remediation": "Install Fabric CLI: https://github.com/microsoft/fabric-cli"
            }
    
    def validate_authentication(self) -> Dict[str, Any]:
        """Validate Fabric authentication is working"""
        # Test with a simple command that requires auth
        # 'fab ls' lists workspaces
        command = ["ls"]
        result = self.cli._execute_command(command)
        
        if result.get("success"):
            return {
                "success": True,
                "message": "Authentication is working"
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Authentication failed"),
                "remediation": "Check FABRIC_TOKEN environment variable"
            }
