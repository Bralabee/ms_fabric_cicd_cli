"""
Fabric Git Integration API - Gap Closing Enhancement 2/4
Implements workspace-to-Git repository connection automation

Key Features:
- Connect workspaces to Git repositories (GitHub, Azure DevOps)
- Initialize Git connections for newly created workspaces
- Support for both Service Principal and PAT authentication
- Long-running operation polling for async Git operations
- Automatic retry with exponential backoff for transient failures
- Based on official Microsoft Fabric Git APIs

References:
- https://learn.microsoft.com/en-us/fabric/cicd/git-integration/git-automation
- https://learn.microsoft.com/en-us/rest/api/fabric/core/git
"""

import logging
import time
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import requests

from usf_fabric_cli.services.fabric_api_base import FabricAPIBase
from usf_fabric_cli.utils.retry import (
    DEFAULT_BASE_DELAY,
    DEFAULT_MAX_DELAY,
    DEFAULT_MAX_RETRIES,
)

if TYPE_CHECKING:
    from usf_fabric_cli.services.token_manager import TokenManager

logger = logging.getLogger(__name__)


class GitProviderType(str, Enum):
    """Supported Git provider types"""

    GITHUB = "GitHub"
    AZURE_DEVOPS = "AzureDevOps"


class GitConnectionSource(str, Enum):
    """Git credential sources"""

    AUTOMATIC = "Automatic"  # SSO
    CONFIGURED_CONNECTION = "ConfiguredConnection"  # Service Principal or PAT


class FabricGitAPI(FabricAPIBase):
    """
    Client for Fabric Git Integration REST APIs.

    This module addresses the requirement to automatically connect
    created workspaces to Git repositories for proper CI/CD workflows.
    Includes automatic retry with exponential backoff for transient failures
    (inherited from ``FabricAPIBase``).
    """

    def __init__(
        self,
        access_token: str,
        base_url: str = "https://api.fabric.microsoft.com/v1",
        token_manager: Optional["TokenManager"] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
    ):
        """
        Initialize Fabric Git API client.

        Args:
            access_token: Azure AD access token for Fabric API
            base_url: Fabric API base URL
            token_manager: Optional TokenManager for proactive token refresh
            max_retries: Maximum retry attempts for transient failures
            base_delay: Initial backoff delay in seconds
            max_delay: Maximum backoff delay in seconds
        """
        super().__init__(
            access_token=access_token,
            base_url=base_url,
            token_manager=token_manager,
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
        )

    def create_git_connection(
        self,
        display_name: str,
        provider_type: GitProviderType,
        credential_type: str,
        credential_value: str,
        repository_url: Optional[str] = None,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a Git provider credentials connection.

        Args:
            display_name: Connection display name
            provider_type: GitProviderType.GITHUB or GitProviderType.AZURE_DEVOPS
            credential_type: 'Key' for PAT, 'ServicePrincipal' for SP
            credential_value: PAT token or SP secret
            repository_url: Optional specific repository URL
            tenant_id: Required for ServicePrincipal
            client_id: Required for ServicePrincipal

        Returns:
            Connection details including connection ID
        """
        url = f"{self.base_url}/connections"

        # Build connection details based on provider type
        if provider_type == GitProviderType.GITHUB:
            connection_type = "GitHubSourceControl"
            connection_details: Dict[str, Any] = {
                "type": connection_type,
                "creationMethod": f"{connection_type}.Contents",
            }

            # Add repository URL if provided
            if repository_url:
                connection_details["parameters"] = [
                    {"dataType": "Text", "name": "url", "value": repository_url}
                ]

            # Build credential details
            if credential_type == "Key":
                credential_details = {
                    "credentials": {"credentialType": "Key", "key": credential_value}
                }
            else:
                raise ValueError("GitHub only supports PAT (Key) authentication")

        elif provider_type == GitProviderType.AZURE_DEVOPS:
            connection_type = "AzureDevOpsSourceControl"
            connection_details = {
                "type": connection_type,
                "creationMethod": f"{connection_type}.Contents",
            }

            # Add repository URL if provided
            if repository_url:
                connection_details["parameters"] = [
                    {"dataType": "Text", "name": "url", "value": repository_url}
                ]

            # Build credential details
            if credential_type == "ServicePrincipal":
                if not tenant_id or not client_id:
                    raise ValueError(
                        "ServicePrincipal requires tenant_id and client_id"
                    )

                credential_details = {
                    "credentials": {
                        "credentialType": "ServicePrincipal",
                        "tenantId": tenant_id,
                        "servicePrincipalClientId": client_id,
                        "servicePrincipalSecret": credential_value,
                    }
                }
            else:
                raise ValueError(
                    "Azure DevOps only supports ServicePrincipal authentication"
                )
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")

        # Build request body
        request_body = {
            "displayName": display_name,
            "connectivityType": "ShareableCloud",
            "connectionDetails": connection_details,
            "credentialDetails": credential_details,
        }

        try:
            response = self._make_request("POST", url, json=request_body)

            result = response.json()
            logger.info("Created Git connection: %s", result.get("id"))
            return {"success": True, "connection": result}

        except requests.exceptions.RequestException as e:
            # Check for 409 DuplicateConnectionName -- expected in
            # idempotent re-deploys, not a real error
            if hasattr(e, "response") and e.response is not None:
                if e.response.status_code == 409:
                    response_text = e.response.text
                    logger.info(
                        "Connection creation returned 409 (duplicate): %s",
                        response_text,
                    )
                    return {
                        "success": False,
                        "duplicate": True,
                        "error": str(e),
                        "response": response_text,
                    }
                logger.error("Failed to create Git connection: %s", e)
                logger.error("Response Status: %s", e.response.status_code)
                logger.error("Response Body: %s", e.response.text)
            else:
                logger.error("Failed to create Git connection: %s", e)

            return {
                "success": False,
                "error": str(e),
                "response": (
                    e.response.text
                    if hasattr(e, "response") and e.response is not None
                    else None
                ),
            }

    def list_connections(self) -> Dict[str, Any]:
        """
        List all Git connections available to the user.

        Returns:
            List of connections with their IDs and details
        """
        url = f"{self.base_url}/connections"

        try:
            response = self._make_request("GET", url)

            result = response.json()
            connections = result.get("value", [])

            logger.info("Found %s Git connections", len(connections))
            return {"success": True, "connections": connections}

        except requests.exceptions.RequestException as e:
            logger.error("Failed to list connections: %s", e)
            return {"success": False, "error": str(e)}

    def get_connection_by_name(self, display_name: str) -> Optional[Dict[str, Any]]:
        """Find a connection by its display name."""
        result = self.list_connections()
        if result["success"]:
            for conn in result["connections"]:
                if conn.get("displayName") == display_name:
                    return conn
        return None

    def delete_connection(self, connection_id: str) -> Dict[str, Any]:
        """
        Delete a Git connection by ID.

        Useful for recycling stale connections that cause ConnectionMismatch
        errors when reused with different credentials.

        Args:
            connection_id: The connection GUID to delete.

        Returns:
            ``{"success": True}`` or ``{"success": False, "error": "..."}``
        """
        url = f"{self.base_url}/connections/{connection_id}"

        try:
            self._make_request("DELETE", url)
            logger.info("Deleted Git connection %s", connection_id)
            return {"success": True}
        except requests.exceptions.RequestException as e:
            logger.error("Failed to delete connection %s: %s", connection_id, e)
            return {"success": False, "error": str(e)}

    def connect_workspace_to_git(
        self,
        workspace_id: str,
        provider_type: GitProviderType,
        connection_id: Optional[str] = None,
        organization_name: Optional[str] = None,
        project_name: Optional[str] = None,
        repository_name: Optional[str] = None,
        owner_name: Optional[str] = None,
        branch_name: str = "main",
        directory_name: str = "/",
    ) -> Dict[str, Any]:
        """
        Connect a workspace to a Git repository.

        Args:
            workspace_id: Fabric workspace ID
            provider_type: GitProviderType.GITHUB or GitProviderType.AZURE_DEVOPS
            connection_id: Connection ID for authentication (optional for SSO)
            organization_name: Azure DevOps organization name
            project_name: Azure DevOps project name
            repository_name: Repository name
            owner_name: GitHub owner/org name
            branch_name: Git branch to connect to
            directory_name: Directory within repo

        Returns:
            Connection result
        """
        url = f"{self.base_url}/workspaces/{workspace_id}/git/connect"

        # Build git provider details
        if provider_type == GitProviderType.AZURE_DEVOPS:
            if not all([organization_name, project_name, repository_name]):
                raise ValueError(
                    "Azure DevOps requires organization_name, project_name, and "
                    "repository_name"
                )

            git_provider_details = {
                "gitProviderType": "AzureDevOps",
                "organizationName": organization_name,
                "projectName": project_name,
                "repositoryName": repository_name,
                "branchName": branch_name,
                "directoryName": directory_name,
            }
        elif provider_type == GitProviderType.GITHUB:
            if not all([owner_name, repository_name]):
                raise ValueError("GitHub requires owner_name and repository_name")

            git_provider_details = {
                "gitProviderType": "GitHub",
                "ownerName": owner_name,
                "repositoryName": repository_name,
                "branchName": branch_name,
                "directoryName": directory_name,
            }
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")

        # Build request body
        request_body = {"gitProviderDetails": git_provider_details}

        # Add credentials - required for GitHub, optional for Azure DevOps
        if connection_id:
            request_body["myGitCredentials"] = {
                "source": GitConnectionSource.CONFIGURED_CONNECTION.value,
                "connectionId": connection_id,
            }
        elif provider_type == GitProviderType.GITHUB:
            # GitHub provider REQUIRES myGitCredentials even for SSO
            request_body["myGitCredentials"] = {
                "source": GitConnectionSource.AUTOMATIC.value,
            }
            logger.info("Using automatic SSO authentication for GitHub")
        else:
            # Azure DevOps can use automatic SSO without explicit credentials
            logger.info("Using automatic SSO authentication")

        try:
            self._make_request("POST", url, json=request_body)

            logger.info("Connected workspace %s to Git", workspace_id)
            return {"success": True, "message": "Workspace connected to Git"}

        except requests.exceptions.RequestException as e:
            # Handle "already connected" as idempotent success
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_body = e.response.json()
                    error_code = error_body.get("errorCode", "")
                except ValueError:
                    error_code = ""

                if error_code == "WorkspaceAlreadyConnectedToGit":
                    logger.info(
                        "Workspace %s is already connected to Git", workspace_id
                    )
                    return {
                        "success": True,
                        "message": "Workspace already connected to Git",
                        "already_connected": True,
                    }

            logger.error("Failed to connect workspace to Git: %s", e)
            error_detail = (
                e.response.text
                if hasattr(e, "response") and e.response is not None
                else str(e)
            )
            return {"success": False, "error": str(e), "details": error_detail}

    def initialize_git_connection(
        self,
        workspace_id: str,
        initialization_strategy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initialize Git connection for a workspace.

        This must be called after connecting a workspace to Git.
        It determines whether to update from Git or if no action is needed.

        Args:
            workspace_id: Fabric workspace ID
            initialization_strategy: Optional strategy for resolving conflicts
                between workspace and Git content. Accepted values:
                - "PreferWorkspace": Keep workspace content on conflict
                - "PreferRemote": Overwrite workspace with Git content
                - None (default): Let the Fabric API decide (current behavior)

        Returns:
            Initialization result with requiredAction field
        """
        url = f"{self.base_url}/workspaces/{workspace_id}/git/initializeConnection"

        # Build request body -- empty preserves backward-compatible behavior
        body: Dict[str, Any] = {}
        if initialization_strategy:
            body["initializationStrategy"] = initialization_strategy
            logger.info(
                "Using initialization strategy '%s' for workspace %s",
                initialization_strategy,
                workspace_id,
            )

        try:
            response = self._make_request("POST", url, json=body)

            result = response.json()
            required_action = result.get("requiredAction", "None")

            logger.info(
                "Initialized Git connection for workspace %s. " "Required action: %s",
                workspace_id,
                required_action,
            )
            return {
                "success": True,
                "required_action": required_action,
                "remote_commit_hash": result.get("remoteCommitHash"),
                "workspace_head": result.get("workspaceHead"),
            }

        except requests.exceptions.RequestException as e:
            # 409 means workspace Git connection is already initialized
            # -- this is expected on idempotent re-deploys
            if hasattr(e, "response") and e.response is not None:
                if e.response.status_code == 409:
                    logger.info(
                        "Git connection already initialized for "
                        "workspace %s (idempotent)",
                        workspace_id,
                    )
                    return {
                        "success": True,
                        "already_initialized": True,
                        "required_action": "None",
                    }
            logger.error("Failed to initialize Git connection: %s", e)
            return {"success": False, "error": str(e)}

    def update_from_git(
        self,
        workspace_id: str,
        remote_commit_hash: str,
        workspace_head: Optional[str] = None,
        conflict_resolution_policy: Optional[str] = None,
        allow_override_items: bool = False,
    ) -> Dict[str, Any]:
        """
        Update workspace with commits from Git.

        This is a long-running operation. Use poll_operation to check status.

        Args:
            workspace_id: Fabric workspace ID
            remote_commit_hash: Remote commit hash from initialize_git_connection
            workspace_head: Workspace head from initialize_git_connection.
                            May be None only after Initialize Connection.
            conflict_resolution_policy: "PreferRemote" or "PreferWorkspace".
                                        Required when conflicts exist.
            allow_override_items: Consent to override incoming items.

        Returns:
            Operation details including operation_id
        """
        url = f"{self.base_url}/workspaces/{workspace_id}/git/updateFromGit"

        request_body: Dict[str, Any] = {
            "remoteCommitHash": remote_commit_hash,
        }

        if workspace_head:
            request_body["workspaceHead"] = workspace_head

        if conflict_resolution_policy:
            request_body["conflictResolution"] = {
                "conflictResolutionType": "Workspace",
                "conflictResolutionPolicy": conflict_resolution_policy,
            }

        if allow_override_items:
            request_body["options"] = {
                "allowOverrideItems": True,
            }

        try:
            response = self._make_request("POST", url, json=request_body)

            # Extract operation ID from headers
            operation_id = response.headers.get("x-ms-operation-id")
            retry_after = int(response.headers.get("Retry-After", "5"))

            logger.info("Started update from Git operation: %s", operation_id)
            return {
                "success": True,
                "operation_id": operation_id,
                "retry_after": retry_after,
            }

        except requests.exceptions.RequestException as e:
            logger.error("Failed to update from Git: %s", e)
            return {"success": False, "error": str(e)}

    def commit_to_git(
        self,
        workspace_id: str,
        message: str,
        items: Optional[List[Dict[str, str]]] = None,
        workspace_head: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Commit workspace changes to Git.

        This is a long-running operation. Use poll_operation to check status.

        Args:
            workspace_id: Fabric workspace ID
            message: Commit comment (max 300 chars)
            items: Optional list of specific items to commit
                   Each item: {"logicalId": "...", "objectId": "..."}
            workspace_head: Full SHA hash the workspace is synced to
                            (from get_git_status)

        Returns:
            Operation details including operation_id
        """
        url = f"{self.base_url}/workspaces/{workspace_id}/git/commitToGit"

        request_body: Dict[str, Any] = {
            "mode": "Selective" if items else "All",
            "comment": message,
        }

        if workspace_head:
            request_body["workspaceHead"] = workspace_head

        if items:
            request_body["items"] = items

        try:
            response = self._make_request("POST", url, json=request_body)

            # Extract operation ID from headers
            operation_id = response.headers.get("x-ms-operation-id")
            retry_after = int(response.headers.get("Retry-After", "5"))

            logger.info("Started commit to Git operation: %s", operation_id)
            return {
                "success": True,
                "operation_id": operation_id,
                "retry_after": retry_after,
            }

        except requests.exceptions.RequestException as e:
            logger.error("Failed to commit to Git: %s", e)
            return {"success": False, "error": str(e)}

    def get_git_status(self, workspace_id: str) -> Dict[str, Any]:
        """
        Get Git status for workspace (pending changes).

        This API supports LRO -- may return 202 with an operation ID.

        Args:
            workspace_id: Fabric workspace ID

        Returns:
            Git status including changes to commit and incoming changes,
            or operation_id if the request is still processing (202).
        """
        url = f"{self.base_url}/workspaces/{workspace_id}/git/status"

        try:
            response = self._make_request("GET", url)

            # LRO: 202 means status computation is in progress
            if response.status_code == 202:
                operation_id = response.headers.get("x-ms-operation-id")
                retry_after = int(response.headers.get("Retry-After", "30"))
                logger.info("Git status is being computed (LRO): %s", operation_id)
                return {
                    "success": True,
                    "lro": True,
                    "operation_id": operation_id,
                    "retry_after": retry_after,
                }

            result = response.json()
            return {"success": True, "status": result}

        except requests.exceptions.RequestException as e:
            logger.error("Failed to get Git status: %s", e)
            return {"success": False, "error": str(e)}

    def get_git_connection(self, workspace_id: str) -> Dict[str, Any]:
        """
        Get Git connection details for a workspace.

        Args:
            workspace_id: Fabric workspace ID

        Returns:
            Git connection details
        """
        url = f"{self.base_url}/workspaces/{workspace_id}/git/connection"

        try:
            response = self._make_request("GET", url)

            result = response.json()
            return {"success": True, "connection": result}

        except requests.exceptions.RequestException as e:
            logger.error("Failed to get Git connection: %s", e)
            return {"success": False, "error": str(e)}

    def disconnect_from_git(self, workspace_id: str) -> Dict[str, Any]:
        """
        Disconnect workspace from Git.

        Args:
            workspace_id: Fabric workspace ID

        Returns:
            Disconnection result
        """
        url = f"{self.base_url}/workspaces/{workspace_id}/git/disconnect"

        try:
            self._make_request("POST", url, json={})

            logger.info("Disconnected workspace %s from Git", workspace_id)
            return {"success": True, "message": "Workspace disconnected from Git"}

        except requests.exceptions.RequestException as e:
            logger.error("Failed to disconnect from Git: %s", e)
            return {"success": False, "error": str(e)}

    def poll_operation(
        self, operation_id: str, max_attempts: int = 60, retry_after: int = 5
    ) -> Dict[str, Any]:
        """
        Poll a long-running operation until completion.

        Args:
            operation_id: Operation ID from update_from_git or commit_to_git
            max_attempts: Maximum polling attempts
            retry_after: Seconds to wait between attempts

        Returns:
            Final operation status
        """
        url = f"{self.base_url}/operations/{operation_id}"

        for attempt in range(max_attempts):
            try:
                response = self._make_request("GET", url)

                result = response.json()
                status = result.get("status", "Unknown")

                logger.debug(
                    "Operation %s status: %s (attempt %s/%s)",
                    operation_id,
                    status,
                    attempt + 1,
                    max_attempts,
                )

                if status in ["Succeeded", "Failed", "Cancelled"]:
                    return {
                        "success": status == "Succeeded",
                        "status": status,
                        "result": result,
                    }

                # Continue polling
                time.sleep(max(retry_after, 2))

            except requests.exceptions.RequestException as e:
                logger.error("Failed to poll operation: %s", e)
                return {"success": False, "error": str(e)}

        # Timeout
        logger.error(
            "Operation %s timed out after %s seconds",
            operation_id,
            max_attempts * retry_after,
        )
        return {"success": False, "error": "Operation timed out", "status": "Timeout"}
