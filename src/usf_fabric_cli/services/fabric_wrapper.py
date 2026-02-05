"""Fabric CLI Wrapper - Thin Wrapper Component 2/5."""

from __future__ import annotations

import json
import logging
import subprocess
import time
import re
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import os

from packaging import version

from usf_fabric_cli.exceptions import (
    FabricCLIError,
    FabricCLINotFoundError,
    FabricTelemetryError,
)
from usf_fabric_cli.utils.telemetry import TelemetryClient

# Re-export retry utilities for backwards compatibility
from usf_fabric_cli.utils.retry import (  # noqa: F401
    is_retryable_error,
    calculate_backoff,
    retry_with_backoff,
)

if TYPE_CHECKING:
    from usf_fabric_cli.services.token_manager import TokenManager

logger = logging.getLogger(__name__)

# Expected CLI version range (can be configured)
MINIMUM_CLI_VERSION = "1.0.0"
RECOMMENDED_CLI_VERSION = "1.0.0"


class FabricCLIWrapper:
    """Thin wrapper around Fabric CLI with idempotency and error handling."""

    def __init__(
        self,
        fabric_token: str,
        telemetry_client: Optional[TelemetryClient] = None,
        validate_version: bool = True,
        min_version: Optional[str] = None,
        token_manager: Optional["TokenManager"] = None,
    ):
        self.fabric_token = fabric_token
        self.telemetry = telemetry_client or TelemetryClient()
        self._last_command: List[str] | None = None
        self.cli_version: Optional[str] = None
        self.min_version = min_version or MINIMUM_CLI_VERSION
        self._token_manager = token_manager

        # Validate CLI version if requested
        if validate_version:
            self._validate_cli_version()

        self._setup_auth()

    def _validate_cli_version(self) -> None:
        """
        Validate that the installed Fabric CLI version meets minimum requirements.

        This addresses Gap A: Dependency on External CLI by ensuring version
        compatibility.
        """
        try:
            result = subprocess.run(
                ["fab", "--version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )

            # Parse version from output (e.g., "Fabric CLI 1.2.3" or just "1.2.3")
            version_output = result.stdout.strip()
            version_match = re.search(r"(\d+\.\d+\.\d+)", version_output)

            if version_match:
                self.cli_version = version_match.group(1)
                logger.info(f"Detected Fabric CLI version: {self.cli_version}")

                # Compare versions
                try:
                    if version.parse(self.cli_version) < version.parse(
                        self.min_version
                    ):
                        logger.warning(
                            f"Fabric CLI version {self.cli_version} is below minimum "
                            f"required version {self.min_version}. This may cause "
                            "compatibility issues."
                        )
                        logger.warning(
                            f"Recommended version: {RECOMMENDED_CLI_VERSION}"
                        )
                except Exception as e:
                    logger.debug(f"Could not compare versions: {e}")
            else:
                logger.warning(f"Could not parse CLI version from: {version_output}")
                self.cli_version = "unknown"

        except FileNotFoundError:
            error_msg = (
                "Fabric CLI ('fab' command) not found. Please install it:\n"
                "  pip install ms-fabric-cli\n"
                "Or see: https://github.com/microsoft/fabric-cli"
            )
            logger.error(error_msg)
            raise FabricCLINotFoundError(["fab", "--version"]) from None

        except subprocess.TimeoutExpired:
            logger.warning("Fabric CLI version check timed out")
            self.cli_version = "unknown"

        except Exception as e:
            logger.warning(f"Could not validate CLI version: {e}")
            self.cli_version = "unknown"

    def _setup_auth(self):
        """Setup Fabric CLI authentication"""
        # We rely on explicit login with Service Principal if credentials are available.
        # This ensures the CLI has a valid token in its cache.

        client_id = os.getenv("AZURE_CLIENT_ID")
        client_secret = os.getenv("AZURE_CLIENT_SECRET")
        tenant_id = os.getenv("TENANT_ID") or os.getenv("AZURE_TENANT_ID")

        # Sanitize credentials to handle inline comments in .env files
        # Docker's --env-file includes inline comments in the value
        if client_id:
            client_id = client_id.split(" #")[0].strip()
        if client_secret:
            client_secret = client_secret.split(" #")[0].strip()
        if tenant_id:
            tenant_id = tenant_id.split(" #")[0].strip()

        if client_id and client_secret and tenant_id:
            try:
                logger.info(
                    "Attempting to login to Fabric CLI with Service Principal..."
                )

                # Logout first to clear any stale state
                try:
                    subprocess.run(
                        ["fab", "auth", "logout"], capture_output=True, check=False
                    )
                except Exception:
                    pass

                # We use subprocess directly here to avoid infinite recursion if we
                # used _run_fabric_command
                # Using short flags -u and -p as per some CLI versions preference
                cmd = [
                    "fab",
                    "auth",
                    "login",
                    "--username",
                    client_id,
                    "--password",
                    client_secret,
                    "--tenant",
                    tenant_id,
                ]

                subprocess.run(cmd, capture_output=True, text=True, check=True)
                logger.info("Successfully logged in to Fabric CLI")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to login to Fabric CLI: {e.stderr}")
                # We don't raise here, as we might still be able to run if there's an
                # existing token,
                # although unlikely if explicit login failed.

    def _emit_telemetry(
        self, event: str, command: List[str], duration: float, **extra: Any
    ) -> None:
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
            env.pop("AZURE_CLIENT_ID", None)
            env.pop("AZURE_CLIENT_SECRET", None)
            env.pop("AZURE_TENANT_ID", None)
            env.pop("TENANT_ID", None)
            env.pop("FABRIC_TOKEN", None)
            env.pop("AZURE_ACCESS_TOKEN", None)

            # Run command
            result = subprocess.run(
                full_command, capture_output=True, text=True, env=env
            )
            return {"success": True, "data": result.stdout}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_command(
        self, command: List[str], check_existence: bool = False, timeout: int = 300
    ) -> Dict[str, Any]:
        try:
            return self._run_fabric_command(command, check_existence, timeout=timeout)
        except FabricCLIError as exc:
            return {"success": False, "error": str(exc), "exception": exc}

    def _run_fabric_command(
        self, command: List[str], check_existence: bool = False, timeout: int = 300
    ) -> Dict[str, Any]:
        """Execute Fabric CLI command with error handling and telemetry."""
        # Proactive token refresh for long deployments (>5 min)
        # This prevents authentication failures mid-deployment
        if self._token_manager:
            try:
                self._token_manager.ensure_fresh_auth(max_age_seconds=300)
            except Exception as e:
                logger.warning(
                    "Token refresh failed, continuing with existing auth: %s", e
                )

        # The Microsoft Fabric CLI command is 'fab', not 'fabric'
        full_command = ["fab"] + command
        start_time = time.time()
        self._last_command = full_command

        # Prepare environment
        env = os.environ.copy()
        # Remove SP credentials to force use of cached token from _setup_auth
        env.pop("AZURE_CLIENT_ID", None)
        env.pop("AZURE_CLIENT_SECRET", None)
        env.pop("AZURE_TENANT_ID", None)
        env.pop("TENANT_ID", None)
        env.pop("FABRIC_TOKEN", None)
        env.pop("AZURE_ACCESS_TOKEN", None)

        try:
            logger.info("Executing: %s", " ".join(full_command))
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                check=True,
                env=env,
                timeout=timeout,
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
                reused=payload.get("reused", False),
            )
            return payload

        except subprocess.TimeoutExpired:
            error_msg = f"Command timed out after {timeout} seconds"
            self._emit_telemetry(
                "fabric_cli.timeout",
                full_command,
                time.time() - start_time,
                error=error_msg,
            )
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        except FileNotFoundError as exc:
            error = FabricCLINotFoundError(full_command)
            self._emit_telemetry(
                "fabric_cli.failure",
                full_command,
                time.time() - start_time,
                error=str(error),
            )
            logger.error("Fabric CLI binary not found: %s", exc)
            raise error from exc

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else ""
            output_msg = e.stdout.strip() if e.stdout else ""
            full_msg = f"{error_msg} {output_msg}"

            if check_existence and (
                "already exists" in full_msg.lower()
                or "duplicate" in full_msg.lower()
                or "already has a role assigned" in full_msg.lower()
                or "an item with the same name exists" in full_msg.lower()
            ):
                logger.debug("Item already exists - continuing (idempotent)")
                payload = {"success": True, "data": "already_exists", "reused": True}
                self._emit_telemetry(
                    "fabric_cli.success",
                    full_command,
                    time.time() - start_time,
                    reused=True,
                )
                return payload

            cli_error = FabricCLIError(
                full_command, e.returncode, full_msg or str(e), e.stdout
            )
            self._emit_telemetry(
                "fabric_cli.failure",
                full_command,
                time.time() - start_time,
                error=str(cli_error),
            )
            logger.error("Fabric CLI error: %s", full_msg)
            raise cli_error

    def _item_exists(self, path: str) -> bool:
        """Check if an item exists using 'fab exists'"""
        try:
            # 'fab exists' returns exit code 0 always, but prints '* true' or '* false'
            cmd = ["fab", "exists", path]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return "true" in result.stdout.lower()
        except Exception:
            return False

    def create_workspace(
        self, name: str, capacity_name: Optional[str] = None, description: str = ""
    ) -> Dict[str, Any]:
        """Create workspace with idempotency"""
        print(
            f"DEBUG: create_workspace called with name='{name}', "
            f"capacity_name='{capacity_name}'"
        )

        # Check existence first
        if self._item_exists(f"{name}.Workspace"):
            logger.info(f"Workspace {name} already exists. Retrieving details...")
            workspace_info = self.get_workspace(name)
            workspace_id = None
            if workspace_info.get("success") and workspace_info.get("data"):
                data = workspace_info["data"]
                if (
                    isinstance(data, dict)
                    and "result" in data
                    and "data" in data["result"]
                    and len(data["result"]["data"]) > 0
                ):
                    workspace_id = data["result"]["data"][0].get("id")
                else:
                    workspace_id = data.get("id")

            return {
                "success": True,
                "data": "already_exists",
                "reused": True,
                "workspace_id": workspace_id,
            }

        # Check if capacity_name is a GUID
        is_guid = False
        if capacity_name:
            if re.match(
                r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                capacity_name.lower(),
            ):
                is_guid = True

        if is_guid:
            # Use API for GUID capacity
            payload = {
                "displayName": name,
                "description": description,
                "capacityId": capacity_name,
            }

            command = ["api", "workspaces", "-X", "post", "-i", json.dumps(payload)]

            result = self._execute_command(command)

            # Check for API errors in the response
            if result.get("success") and isinstance(result.get("data"), dict):
                response_data = result["data"]
                if response_data.get("status_code", 0) >= 400:
                    error_text = response_data.get("text", {})
                    error_message = (
                        error_text.get("message")
                        if isinstance(error_text, dict)
                        else str(error_text)
                    )
                    error_code = (
                        error_text.get("errorCode")
                        if isinstance(error_text, dict)
                        else "Unknown"
                    )

                    print(
                        f"Error creating workspace with capacity: {error_code} - "
                        f"{error_message}"
                    )
                    if error_code == "InsufficientPermissionsOverCapacity":
                        print(
                            "ACTION REQUIRED: The Service Principal needs 'Capacity "
                            "Admin' or 'Contributor' permissions on the Fabric "
                            "Capacity."
                        )

                    return {"success": False, "error": f"{error_code}: {error_message}"}

            if result.get("success"):
                # If status_code is missing or 2xx, assume success (though
                # _execute_command usually returns success=True even for 4xx if the
                # command ran)
                # We need to verify if the workspace was actually created.
                # However, for now, let's assume if we didn't catch a 4xx above, it
                # might be okay or we fall through.
                # Actually, if it failed, we should probably return False.
                pass

            if result.get("success"):
                # Check for API error in data (fab api returns 0 even on error)
                data = result.get("data")
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        pass

                # Handle fab api error response format
                if isinstance(data, dict):
                    if "errorCode" in data:
                        return {
                            "success": False,
                            "error": data.get("message"),
                            "data": data,
                        }
                    if "status_code" in data and data["status_code"] >= 400:
                        error_msg = "API Error"
                        if isinstance(data.get("text"), dict):
                            error_msg = data["text"].get("message", error_msg)
                        return {"success": False, "error": error_msg, "data": data}

                # Extract ID from response
                if isinstance(data, dict) and "id" in data:
                    result["workspace_id"] = data["id"]
                else:
                    # Fallback to get_workspace
                    time.sleep(2)
                    workspace_info = self.get_workspace(name)
                    if workspace_info.get("success") and workspace_info.get("data"):
                        data = workspace_info["data"]
                        if (
                            isinstance(data, dict)
                            and "result" in data
                            and "data" in data["result"]
                            and len(data["result"]["data"]) > 0
                        ):
                            result["workspace_id"] = data["result"]["data"][0].get("id")
                        else:
                            result["workspace_id"] = data.get("id")
            return result
        else:
            print("DEBUG: Not a GUID capacity. Using mkdir.")
            # Use 'mkdir' with -P capacityName=... (Legacy/Name-based)
            command = ["mkdir", f"{name}.Workspace"]

            if capacity_name:
                command.extend(["-P", f"capacityName={capacity_name}"])

            # Description is not directly supported by mkdir -P for workspace in CLI
            # help, but we can try to set it later if needed. For now, we skip it
            # to avoid errors.

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
                    if (
                        isinstance(data, dict)
                        and "result" in data
                        and "data" in data["result"]
                        and len(data["result"]["data"]) > 0
                    ):
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

    def get_workspace_id(self, name: str) -> Optional[str]:
        """Helper to get workspace ID"""
        workspace_info = self.get_workspace(name)
        if workspace_info.get("success") and workspace_info.get("data"):
            data = workspace_info["data"]
            if (
                isinstance(data, dict)
                and "result" in data
                and "data" in data["result"]
                and len(data["result"]["data"]) > 0
            ):
                return data["result"]["data"][0].get("id")
            else:
                return data.get("id")
        return None

    def get_folder_id(
        self, workspace_name: str, folder_name: str, retries: int = 5
    ) -> Optional[str]:
        """Get folder ID by name with retries for propagation"""
        workspace_id = self.get_workspace_id(workspace_name)
        if not workspace_id:
            return None

        for attempt in range(retries):
            # List folders using API
            command = ["api", f"workspaces/{workspace_id}/folders"]
            result = self._execute_command(command)

            if result.get("success"):
                data = result.get("data")
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        pass

                # Handle nested "text" field from fab api wrapper if present
                if (
                    isinstance(data, dict)
                    and "text" in data
                    and isinstance(data["text"], dict)
                ):
                    data = data["text"]

                if isinstance(data, dict) and "value" in data:
                    for folder in data["value"]:
                        if folder.get("displayName") == folder_name:
                            return folder.get("id")

            # Wait before retrying if not found
            if attempt < retries - 1:
                time.sleep(2)

        return None

    def create_folder(self, workspace_name: str, folder_name: str) -> Dict[str, Any]:
        """Create folder in workspace"""
        # Check if exists
        folder_id = self.get_folder_id(workspace_name, folder_name)
        if folder_id:
            logger.info(f"Folder {folder_name} already exists.")
            return {
                "success": True,
                "data": "already_exists",
                "reused": True,
                "id": folder_id,
            }

        workspace_id = self.get_workspace_id(workspace_name)
        if not workspace_id:
            return {"success": False, "error": f"Workspace {workspace_name} not found"}

        # Create using API
        payload = {"displayName": folder_name}
        command = [
            "api",
            f"workspaces/{workspace_id}/folders",
            "-X",
            "post",
            "-i",
            json.dumps(payload),
        ]
        return self._execute_command(command)

    def create_lakehouse(
        self,
        workspace_name: str,
        name: str,
        description: str = "",
        folder: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create lakehouse"""
        if folder:
            folder_id = self.get_folder_id(workspace_name, folder)
            if not folder_id:
                logger.warning(
                    f"Folder {folder} not found. Creating Lakehouse {name} at root."
                )
                folder_id = None
        else:
            folder_id = None

        if folder_id:
            workspace_id = self.get_workspace_id(workspace_name)
            if not workspace_id:
                return {
                    "success": False,
                    "error": f"Workspace {workspace_name} not found",
                }

            payload = {
                "displayName": name,
                "type": "Lakehouse",
                "description": description,
                "folderId": folder_id,
            }

            command = [
                "api",
                f"workspaces/{workspace_id}/items",
                "-X",
                "post",
                "-i",
                json.dumps(payload),
            ]
            return self._execute_command(command)
        else:
            path = f"{workspace_name}.Workspace/{name}.Lakehouse"
            if self._item_exists(path):
                return {"success": True, "data": "already_exists", "reused": True}
            command = ["mkdir", path]
            return self._execute_command(command, check_existence=True)

    def create_warehouse(
        self,
        workspace_name: str,
        name: str,
        description: str = "",
        folder: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create warehouse"""
        if folder:
            folder_id = self.get_folder_id(workspace_name, folder)
            if not folder_id:
                logger.warning(
                    f"Folder {folder} not found. Creating Warehouse {name} at root."
                )
                folder_id = None
        else:
            folder_id = None

        if folder_id:
            workspace_id = self.get_workspace_id(workspace_name)
            if not workspace_id:
                return {
                    "success": False,
                    "error": f"Workspace {workspace_name} not found",
                }

            payload = {
                "displayName": name,
                "type": "Warehouse",
                "description": description,
                "folderId": folder_id,
            }

            command = [
                "api",
                f"workspaces/{workspace_id}/items",
                "-X",
                "post",
                "-i",
                json.dumps(payload),
            ]
            return self._execute_command(command)
        else:
            path = f"{workspace_name}.Workspace/{name}.Warehouse"
            if self._item_exists(path):
                return {"success": True, "data": "already_exists", "reused": True}
            command = ["mkdir", path]
            return self._execute_command(command, check_existence=True)

    def create_notebook(
        self,
        workspace_name: str,
        name: str,
        file_path: Optional[str] = None,
        folder: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create notebook"""
        if folder:
            folder_id = self.get_folder_id(workspace_name, folder)
            if not folder_id:
                logger.warning(
                    f"Folder {folder} not found. Creating Notebook {name} at root."
                )
                folder_id = None
        else:
            folder_id = None

        if folder_id:
            workspace_id = self.get_workspace_id(workspace_name)
            if not workspace_id:
                return {
                    "success": False,
                    "error": f"Workspace {workspace_name} not found",
                }

            payload = {"displayName": name, "type": "Notebook", "folderId": folder_id}

            command = [
                "api",
                f"workspaces/{workspace_id}/items",
                "-X",
                "post",
                "-i",
                json.dumps(payload),
            ]
            return self._execute_command(command)
        else:
            path = f"{workspace_name}.Workspace/{name}.Notebook"
            if self._item_exists(path):
                return {"success": True, "data": "already_exists", "reused": True}
            command = ["mkdir", path]
            return self._execute_command(command, check_existence=True)

    def create_pipeline(
        self,
        workspace_name: str,
        name: str,
        description: str = "",
        folder: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create data pipeline"""
        if folder:
            folder_id = self.get_folder_id(workspace_name, folder)
            if not folder_id:
                logger.warning(
                    f"Folder {folder} not found. Creating Pipeline {name} at root."
                )
                folder_id = None
        else:
            folder_id = None

        if folder_id:
            workspace_id = self.get_workspace_id(workspace_name)
            if not workspace_id:
                return {
                    "success": False,
                    "error": f"Workspace {workspace_name} not found",
                }

            payload = {
                "displayName": name,
                "type": "DataPipeline",
                "description": description,
                "folderId": folder_id,
            }

            command = [
                "api",
                f"workspaces/{workspace_id}/items",
                "-X",
                "post",
                "-i",
                json.dumps(payload),
            ]
            return self._execute_command(command)
        else:
            path = f"{workspace_name}.Workspace/{name}.DataPipeline"
            if self._item_exists(path):
                return {"success": True, "data": "already_exists", "reused": True}
            command = ["mkdir", path]
            return self._execute_command(command, check_existence=True)

    def create_semantic_model(
        self,
        workspace_name: str,
        name: str,
        description: str = "",
        folder: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create semantic model"""
        if folder:
            folder_id = self.get_folder_id(workspace_name, folder)
            if not folder_id:
                logger.warning(
                    f"Folder {folder} not found. Creating SemanticModel {name} at root."
                )
                folder_id = None
        else:
            folder_id = None

        if folder_id:
            workspace_id = self.get_workspace_id(workspace_name)
            if not workspace_id:
                return {
                    "success": False,
                    "error": f"Workspace {workspace_name} not found",
                }

            payload = {
                "displayName": name,
                "type": "SemanticModel",
                "description": description,
                "folderId": folder_id,
            }

            command = [
                "api",
                f"workspaces/{workspace_id}/items",
                "-X",
                "post",
                "-i",
                json.dumps(payload),
            ]
            return self._execute_command(command)
        else:
            path = f"{workspace_name}.Workspace/{name}.SemanticModel"
            if self._item_exists(path):
                return {"success": True, "data": "already_exists", "reused": True}
            command = ["mkdir", path]
            return self._execute_command(command, check_existence=True)

    def create_item(
        self,
        workspace_name: str,
        name: str,
        item_type: str,
        description: str = "",
        folder: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create any generic Fabric item (Future-proof)"""
        if folder:
            folder_id = self.get_folder_id(workspace_name, folder)
            if not folder_id:
                logger.warning(
                    f"Folder {folder} not found. Creating {item_type} {name} at root."
                )
                folder_id = None
        else:
            folder_id = None

        if folder_id:
            workspace_id = self.get_workspace_id(workspace_name)
            if not workspace_id:
                return {
                    "success": False,
                    "error": f"Workspace {workspace_name} not found",
                }

            payload = {
                "displayName": name,
                "type": item_type,
                "description": description,
                "folderId": folder_id,
            }

            command = [
                "api",
                f"workspaces/{workspace_id}/items",
                "-X",
                "post",
                "-i",
                json.dumps(payload),
            ]
            return self._execute_command(command)
        else:
            path = f"{workspace_name}.Workspace/{name}.{item_type}"
            if self._item_exists(path):
                return {"success": True, "data": "already_exists", "reused": True}
            command = ["mkdir", path]
            return self._execute_command(command, check_existence=True)

    def add_workspace_principal(
        self, workspace_name: str, principal_id: str, role: str = "Member"
    ) -> Dict[str, Any]:
        """Add principal (user/service principal) to workspace"""
        # Skip empty or placeholder emails
        if not principal_id:
            # Silent skip for empty ID (handled by config warning)
            return {
                "success": True,
                "message": "Skipped empty principal",
                "skipped": True,
            }

        if "your-company.com" in principal_id or "example.com" in principal_id:
            logger.warning(f"Skipping placeholder principal: {principal_id}")
            return {
                "success": True,
                "message": "Skipped placeholder principal",
                "skipped": True,
            }

        # Check if principal_id looks like an email
        if "@" in principal_id and not re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            principal_id.lower(),
        ):
            logger.warning(
                f"Principal ID '{principal_id}' looks like an email. Fabric CLI/API "
                f"requires an Object ID (GUID)."
            )
            # We continue anyway, as the CLI might support it in future or if it's a
            # UPN that works in some contexts
            # But we log a warning.

        # Use 'acl set'
        command = [
            "acl",
            "set",
            f"{workspace_name}.Workspace",
            "--identity",
            principal_id,
            "--role",
            role,
            "--force",  # Skip confirmation prompt
        ]
        result = self._execute_command(command, check_existence=True)

        if not result.get("success"):
            error_msg = result.get("error", "")
            if "NotFound" in error_msg or "identity not found" in error_msg:
                logger.error(
                    f"Principal ID {principal_id} not found. Please verify the Object "
                    f"ID and ensure it exists in the tenant."
                )
                # Return success=True to avoid failing the entire deployment for one
                # missing user
                return {
                    "success": True,
                    "message": f"Principal {principal_id} not found (skipped)",
                    "skipped": True,
                }

        return result

    def _parse_git_url(self, git_url: str) -> Dict[str, str]:
        """Parse Git URL to extract details"""
        # Azure DevOps URL formats:
        # 1. https://dev.azure.com/{org}/{project}/_git/{repo}
        # 2. https://{org}.visualstudio.com/{project}/_git/{repo}

        # Format 1 (ADO)
        match1 = re.search(
            r"https://dev\.azure\.com/([^/]+)/([^/]+)/_git/([^/]+)", git_url
        )
        if match1:
            return {
                "gitProviderType": "AzureDevOps",
                "organizationName": match1.group(1),
                "projectName": match1.group(2),
                "repositoryName": match1.group(3),
            }

        # Format 2 (ADO)
        match2 = re.search(
            r"https://([^.]+)\.visualstudio\.com/([^/]+)/_git/([^/]+)", git_url
        )
        if match2:
            return {
                "gitProviderType": "AzureDevOps",
                "organizationName": match2.group(1),
                "projectName": match2.group(2),
                "repositoryName": match2.group(3),
            }

        # GitHub URL format
        # https://github.com/{owner}/{repo}
        match3 = re.search(r"https://github\.com/([^/]+)/([^/.]+)(?:\.git)?", git_url)
        if match3:
            return {
                "gitProviderType": "GitHub",
                "ownerName": match3.group(1),
                "repositoryName": match3.group(2),
            }

        return {}

    def connect_git(
        self,
        workspace_name: str,
        git_repo: str,
        branch: str = "main",
        directory: str = "/",
    ) -> Dict[str, Any]:
        """Connect workspace to Git repository"""

        # 1. Get Workspace ID
        workspace_info = self.get_workspace(workspace_name)
        workspace_id = None
        if workspace_info.get("success") and workspace_info.get("data"):
            data = workspace_info["data"]
            if (
                isinstance(data, dict)
                and "result" in data
                and "data" in data["result"]
                and len(data["result"]["data"]) > 0
            ):
                workspace_id = data["result"]["data"][0].get("id")
            else:
                workspace_id = data.get("id")

        if not workspace_id:
            return {
                "success": False,
                "error": f"Could not find workspace ID for {workspace_name}",
            }

        # 2. Parse Git URL
        git_details = self._parse_git_url(git_repo)
        if not git_details:
            return {
                "success": False,
                "error": (
                    f"Could not parse Git URL: {git_repo}. Expected Azure DevOps or "
                    "GitHub URL."
                ),
            }

        # 3. Construct Payload
        provider_type = git_details.get("gitProviderType", "AzureDevOps")

        if provider_type == "GitHub":
            payload = {
                "gitProviderDetails": {
                    "gitProviderType": "GitHub",
                    "ownerName": git_details["ownerName"],
                    "repositoryName": git_details["repositoryName"],
                    "branchName": branch,
                    "directoryName": directory,
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
                    "directoryName": directory,
                }
            }

        # 4. Call Fabric API
        # Endpoint: POST
        # https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/git/connect
        endpoint = f"v1/workspaces/{workspace_id}/git/connect"

        # Use 'fab api' command
        # fab api <endpoint> -X POST -i <json_string>
        command = ["api", endpoint, "-X", "post", "-i", json.dumps(payload)]

        logger.info(f"Connecting workspace {workspace_name} to Git repo {git_repo}...")
        return self._execute_command(command)

    def assign_to_domain(self, workspace_name: str, domain_name: str) -> Dict[str, Any]:
        """Assign workspace to a domain"""
        # Command: fab assign <domain_path> -W <workspace_path>
        # Example: fab assign .domains/Sales.Domain -W SalesWorkspace.Workspace

        # Ensure domain name has .Domain suffix if not present (though CLI might
        # handle it, best to be explicit based on ls output)
        # But wait, 'fab ls .domains' output shows names like "01 Strategy... .Domain"
        # The user might provide just "Sales" or the full name.
        # Let's assume the user provides the name and we might need to find the full
        # path or just try to use it.
        # Based on 'fab assign --help', example is '.domains/domain1.Domain'

        # We'll try to construct the path if it doesn't look like a path
        domain_path = domain_name
        if not domain_path.startswith(".domains/"):
            # If it doesn't end with .Domain, append it?
            # The CLI seems to use .Domain suffix for items.
            if not domain_path.endswith(".Domain"):
                domain_path = f"{domain_path}.Domain"
            domain_path = f".domains/{domain_path}"

        command = ["assign", domain_path, "-W", f"{workspace_name}.Workspace", "-f"]

        logger.info(f"Assigning workspace {workspace_name} to domain {domain_name}...")
        return self._execute_command(command, timeout=60)

    def list_workspace_items(self, workspace_name: str) -> Dict[str, Any]:
        """List all items in workspace"""
        command = ["ls", f"{workspace_name}.Workspace"]
        return self._execute_command(command)

    def wait_for_operation(
        self, operation_id: str, max_wait_seconds: int = 300
    ) -> bool:
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
                    logger.error(
                        f"Operation {operation_id} failed with status: {status}"
                    )
                    return False

            time.sleep(10)  # Wait 10 seconds before checking again

        logger.error(
            f"Operation {operation_id} timed out after {max_wait_seconds} seconds"
        )
        return False


class FabricDiagnostics:
    """Diagnostic utilities for troubleshooting"""

    def __init__(self, cli_wrapper: FabricCLIWrapper):
        self.cli = cli_wrapper

    def validate_fabric_cli_installation(self) -> Dict[str, Any]:
        """Validate Fabric CLI is properly installed with version checking"""
        try:
            result = subprocess.run(
                ["fab", "--version"], capture_output=True, text=True, check=True
            )

            version_output = result.stdout.strip()

            # Enhanced validation with version compatibility check
            validation_result = {
                "success": True,
                "version": version_output,
                "message": "Fabric CLI is properly installed",
            }

            # Check if we have a parsed version from the wrapper
            if self.cli.cli_version and self.cli.cli_version != "unknown":
                validation_result["parsed_version"] = self.cli.cli_version
                validation_result["minimum_version"] = self.cli.min_version

                try:
                    current = version.parse(self.cli.cli_version)
                    minimum = version.parse(self.cli.min_version)

                    if current < minimum:
                        validation_result["warning"] = (
                            f"CLI version {self.cli.cli_version} is below minimum "
                            f"required version {self.cli.min_version}. "
                            f"Consider upgrading to {RECOMMENDED_CLI_VERSION}."
                        )
                    elif current >= minimum:
                        validation_result["compatibility"] = "compatible"

                except Exception:
                    pass

            return validation_result

        except (subprocess.CalledProcessError, FileNotFoundError):
            return {
                "success": False,
                "error": "Fabric CLI not found or not properly installed",
                "remediation": (
                    "Install Fabric CLI: https://github.com/microsoft/fabric-cli"
                ),
                "install_command": "pip install ms-fabric-cli",
            }

    def validate_authentication(self) -> Dict[str, Any]:
        """Validate Fabric authentication is working"""
        # Test with a simple command that requires auth
        # 'fab ls' lists workspaces
        command = ["ls"]
        result = self.cli._execute_command(command)

        if result.get("success"):
            return {"success": True, "message": "Authentication is working"}
        else:
            return {
                "success": False,
                "error": result.get("error", "Authentication failed"),
                "remediation": "Check FABRIC_TOKEN environment variable",
            }
