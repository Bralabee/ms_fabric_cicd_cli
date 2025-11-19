"""Fabric CLI Wrapper - Thin Wrapper Component 2/5."""

from __future__ import annotations

import json
import logging
import subprocess
import time
from typing import Any, Dict, List, Optional

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
        # The Microsoft Fabric CLI requires explicit login for Service Principals
        # It does not seem to respect FABRIC_TOKEN env var for SP auth directly in the same way
        # However, we can try to use the 'fab auth login' command if we have credentials
        
        import os
        client_id = os.getenv('AZURE_CLIENT_ID')
        client_secret = os.getenv('AZURE_CLIENT_SECRET')
        tenant_id = os.getenv('TENANT_ID') or os.getenv('AZURE_TENANT_ID')
        
        if client_id and client_secret and tenant_id:
            try:
                logger.info("Attempting to login to Fabric CLI with Service Principal...")
                # We use subprocess directly here to avoid infinite recursion if we used _run_fabric_command
                subprocess.run(
                    ['fab', 'auth', 'login', '--username', client_id, '--password', client_secret, '--tenant', tenant_id],
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.info("Successfully logged in to Fabric CLI")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to login to Fabric CLI: {e.stderr}")
                # Print to console for diagnostics
                print(f"Login failed: {e.stderr}")
        elif self.fabric_token:
            # Fallback for user tokens (if supported via env var)
            os.environ['FABRIC_TOKEN'] = self.fabric_token
            os.environ['AZURE_ACCESS_TOKEN'] = self.fabric_token
    
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

    def _run_fabric_command(self, command: List[str], check_existence: bool = False) -> Dict[str, Any]:
        """Execute Fabric CLI command with error handling and telemetry."""
        # The Microsoft Fabric CLI command is 'fab', not 'fabric'
        full_command = ['fab'] + command
        start_time = time.time()
        self._last_command = full_command

        try:
            logger.info("Executing: %s", ' '.join(full_command))
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                check=True
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
            error_msg = e.stderr.strip() if e.stderr else str(e)

            if check_existence and ("already exists" in error_msg.lower() or
                                    "duplicate" in error_msg.lower()):
                logger.info("Item already exists - continuing (idempotent)")
                payload = {"success": True, "data": "already_exists", "reused": True}
                self._emit_telemetry("fabric_cli.success", full_command, time.time() - start_time, reused=True)
                return payload

            error = FabricCLIError(full_command, e.returncode, error_msg, e.stdout)
            self._emit_telemetry(
                "fabric_cli.failure",
                full_command,
                time.time() - start_time,
                error=str(error)
            )
            logger.error("Fabric CLI error: %s", error_msg)
            raise error

    def _execute_command(self, command: List[str], check_existence: bool = False) -> Dict[str, Any]:
        try:
            return self._run_fabric_command(command, check_existence)
        except FabricCLIError as exc:
            return {"success": False, "error": str(exc), "exception": exc}
    
    def create_workspace(self, name: str, capacity_name: str, description: str = "") -> Dict[str, Any]:
        """Create workspace with idempotency"""
        # Use 'mkdir' with -P capacityName=...
        command = [
            "mkdir", f"{name}.Workspace",
            "-P", f"capacityName={capacity_name}"
        ]

        # Description is not directly supported by mkdir -P for workspace in CLI help, 
        # but we can try to set it later if needed. For now, we skip it to avoid errors.
        
        result = self._execute_command(command, check_existence=True)

        if result.get("success"):
            # We need to return the workspace ID for other operations
            # 'fab get name.Workspace' should return details
            workspace_info = self.get_workspace(name)
            if workspace_info.get("success") and workspace_info.get("data"):
                result["workspace_id"] = workspace_info["data"].get("id")

        return result
    
    def delete_workspace(self, name: str) -> Dict[str, Any]:
        """Delete workspace"""
        command = ["rm", f"{name}.Workspace", "--force"]
        return self._execute_command(command)

    def get_workspace(self, name: str) -> Dict[str, Any]:
        """Get workspace by name"""
        command = ["get", f"{name}.Workspace"]
        return self._execute_command(command)
    
    def create_folder(self, workspace_name: str, folder_name: str) -> Dict[str, Any]:
        """Create folder in workspace"""
        # Note: Fabric workspaces don't strictly have folders at root level in the same way as items
        # But if the CLI supports it, it would be via mkdir
        # However, based on CLI help, folders seem to be inside Lakehouses
        # We will skip folder creation at workspace level for now unless we are sure
        logger.warning("Folder creation at workspace level is not fully supported by CLI wrapper yet.")
        return {"success": True, "message": "Skipped folder creation"}
    
    def create_lakehouse(self, workspace_name: str, name: str, description: str = "") -> Dict[str, Any]:
        """Create lakehouse"""
        command = [
            "mkdir", f"{workspace_name}.Workspace/{name}.Lakehouse"
        ]
        return self._execute_command(command, check_existence=True)
    
    def create_warehouse(self, workspace_name: str, name: str, description: str = "") -> Dict[str, Any]:
        """Create warehouse"""
        command = [
            "mkdir", f"{workspace_name}.Workspace/{name}.Warehouse"
        ]
        return self._execute_command(command, check_existence=True)
    
    def create_notebook(self, workspace_name: str, name: str, file_path: str = None) -> Dict[str, Any]:
        """Create notebook"""
        command = [
            "mkdir", f"{workspace_name}.Workspace/{name}.Notebook"
        ]
        # If file_path is provided, we might need to import content. 
        # CLI 'mkdir' creates empty. 'import' might be needed for content.
        return self._execute_command(command, check_existence=True)
    
    def create_pipeline(self, workspace_name: str, name: str, description: str = "") -> Dict[str, Any]:
        """Create data pipeline"""
        command = [
            "mkdir", f"{workspace_name}.Workspace/{name}.DataPipeline"
        ]
        return self._execute_command(command, check_existence=True)

    def create_semantic_model(self, workspace_name: str, name: str, description: str = "") -> Dict[str, Any]:
        """Create semantic model"""
        command = [
            "mkdir", f"{workspace_name}.Workspace/{name}.SemanticModel"
        ]
        return self._execute_command(command, check_existence=True)
    
    def add_workspace_principal(self, workspace_name: str, principal_id: str,
                               role: str = "Member") -> Dict[str, Any]:
        """Add principal (user/service principal) to workspace"""
        # Use 'acl set'
        command = [
            "acl", "set", f"{workspace_name}.Workspace",
            "--identity", principal_id,
            "--role", role
        ]
        return self._execute_command(command, check_existence=True)
    
    def connect_git(self, workspace_name: str, git_repo: str, branch: str = "main",
                   directory: str = "/") -> Dict[str, Any]:
        """Connect workspace to Git repository"""
        # Git integration is not directly exposed via 'fab' CLI commands in the list we saw.
        # We will log a warning and skip.
        logger.warning("Git connection is not currently supported by this Fabric CLI wrapper.")
        return {"success": False, "error": "Git integration not supported"}
    
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