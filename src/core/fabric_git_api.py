"""
Fabric Git Integration API - Gap Closing Enhancement 2/4
Implements workspace-to-Git repository connection automation

Key Features:
- Connect workspaces to Git repositories (GitHub, Azure DevOps)
- Initialize Git connections for newly created workspaces
- Support for both Service Principal and PAT authentication
- Long-running operation polling for async Git operations
- Based on official Microsoft Fabric Git APIs

References:
- https://learn.microsoft.com/en-us/fabric/cicd/git-integration/git-automation
- https://learn.microsoft.com/en-us/rest/api/fabric/core/git
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional
from enum import Enum

import requests

from core.exceptions import FabricCLIError

logger = logging.getLogger(__name__)


class GitProviderType(str, Enum):
    """Supported Git provider types"""

    GITHUB = "GitHub"
    AZURE_DEVOPS = "AzureDevOps"


class GitConnectionSource(str, Enum):
    """Git credential sources"""

    AUTOMATIC = "Automatic"  # SSO
    CONFIGURED_CONNECTION = "ConfiguredConnection"  # Service Principal or PAT


class FabricGitAPI:
    """
    Client for Fabric Git Integration REST APIs.

    This module addresses the requirement to automatically connect
    created workspaces to Git repositories for proper CI/CD workflows.
    """

    def __init__(
        self, access_token: str, base_url: str = "https://api.fabric.microsoft.com/v1"
    ):
        """
        Initialize Fabric Git API client.

        Args:
            access_token: Azure AD access token for Fabric API
            base_url: Fabric API base URL
        """
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

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
                if not all([tenant_id, client_id]):
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
            response = requests.post(
                url, headers=self.headers, json=request_body, timeout=30
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"Created Git connection: {result.get('id')}")
            return {"success": True, "connection": result}

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create Git connection: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": e.response.text if hasattr(e, "response") else None,
            }

    def list_connections(self) -> Dict[str, Any]:
        """
        List all Git connections available to the user.

        Returns:
            List of connections with their IDs and details
        """
        url = f"{self.base_url}/connections"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()

            result = response.json()
            connections = result.get("value", [])

            logger.info(f"Found {len(connections)} Git connections")
            return {"success": True, "connections": connections}

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list connections: {e}")
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
                    "Azure DevOps requires organization_name, project_name, and repository_name"
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

        # Add credentials if connection_id provided
        if connection_id:
            request_body["myGitCredentials"] = {
                "source": "ConfiguredConnection",
                "connectionId": connection_id,
            }
        else:
            # Use automatic SSO
            logger.info("Using automatic SSO authentication")

        try:
            response = requests.post(
                url, headers=self.headers, json=request_body, timeout=30
            )
            response.raise_for_status()

            logger.info(f"Connected workspace {workspace_id} to Git")
            return {"success": True, "message": "Workspace connected to Git"}

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect workspace to Git: {e}")
            error_detail = e.response.text if hasattr(e, "response") else str(e)
            return {"success": False, "error": str(e), "details": error_detail}

    def initialize_git_connection(self, workspace_id: str) -> Dict[str, Any]:
        """
        Initialize Git connection for a workspace.

        This must be called after connecting a workspace to Git.
        It determines whether to update from Git or if no action is needed.

        Args:
            workspace_id: Fabric workspace ID

        Returns:
            Initialization result with requiredAction field
        """
        url = f"{self.base_url}/workspaces/{workspace_id}/git/initializeConnection"

        try:
            response = requests.post(url, headers=self.headers, json={}, timeout=30)
            response.raise_for_status()

            result = response.json()
            required_action = result.get("RequiredAction", "None")

            logger.info(
                f"Initialized Git connection for workspace {workspace_id}. Required action: {required_action}"
            )
            return {
                "success": True,
                "required_action": required_action,
                "remote_commit_hash": result.get("RemoteCommitHash"),
                "workspace_head": result.get("WorkspaceHead"),
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to initialize Git connection: {e}")
            return {"success": False, "error": str(e)}

    def update_from_git(
        self, workspace_id: str, remote_commit_hash: str, workspace_head: str
    ) -> Dict[str, Any]:
        """
        Update workspace with commits from Git.

        This is a long-running operation. Use poll_operation to check status.

        Args:
            workspace_id: Fabric workspace ID
            remote_commit_hash: Remote commit hash from initialize_git_connection
            workspace_head: Workspace head from initialize_git_connection

        Returns:
            Operation details including operation_id
        """
        url = f"{self.base_url}/workspaces/{workspace_id}/git/updateFromGit"

        request_body = {
            "remoteCommitHash": remote_commit_hash,
            "workspaceHead": workspace_head,
        }

        try:
            response = requests.post(
                url, headers=self.headers, json=request_body, timeout=30
            )
            response.raise_for_status()

            # Extract operation ID from headers
            operation_id = response.headers.get("x-ms-operation-id")
            retry_after = int(response.headers.get("Retry-After", "5"))

            logger.info(f"Started update from Git operation: {operation_id}")
            return {
                "success": True,
                "operation_id": operation_id,
                "retry_after": retry_after,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update from Git: {e}")
            return {"success": False, "error": str(e)}

    def commit_to_git(
        self,
        workspace_id: str,
        message: str,
        items: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Commit workspace changes to Git.

        This is a long-running operation. Use poll_operation to check status.

        Args:
            workspace_id: Fabric workspace ID
            message: Commit message
            items: Optional list of specific items to commit
                   Each item: {"logicalId": "...", "displayName": "...", "type": "..."}

        Returns:
            Operation details including operation_id
        """
        url = f"{self.base_url}/workspaces/{workspace_id}/git/commitToGit"

        request_body = {"mode": "Selective" if items else "All", "message": message}

        if items:
            request_body["items"] = items

        try:
            response = requests.post(
                url, headers=self.headers, json=request_body, timeout=30
            )
            response.raise_for_status()

            # Extract operation ID from headers
            operation_id = response.headers.get("x-ms-operation-id")
            retry_after = int(response.headers.get("Retry-After", "5"))

            logger.info(f"Started commit to Git operation: {operation_id}")
            return {
                "success": True,
                "operation_id": operation_id,
                "retry_after": retry_after,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to commit to Git: {e}")
            return {"success": False, "error": str(e)}

    def get_git_status(self, workspace_id: str) -> Dict[str, Any]:
        """
        Get Git status for workspace (pending changes).

        Args:
            workspace_id: Fabric workspace ID

        Returns:
            Git status including changes to commit and incoming changes
        """
        url = f"{self.base_url}/workspaces/{workspace_id}/git/status"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()

            result = response.json()
            return {"success": True, "status": result}

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get Git status: {e}")
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
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()

            result = response.json()
            return {"success": True, "connection": result}

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get Git connection: {e}")
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
            response = requests.post(url, headers=self.headers, json={}, timeout=30)
            response.raise_for_status()

            logger.info(f"Disconnected workspace {workspace_id} from Git")
            return {"success": True, "message": "Workspace disconnected from Git"}

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to disconnect from Git: {e}")
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
                response = requests.get(url, headers=self.headers, timeout=30)
                response.raise_for_status()

                result = response.json()
                status = result.get("status", "Unknown")

                logger.debug(
                    f"Operation {operation_id} status: {status} (attempt {attempt + 1}/{max_attempts})"
                )

                if status in ["Succeeded", "Failed", "Cancelled"]:
                    return {
                        "success": status == "Succeeded",
                        "status": status,
                        "result": result,
                    }

                # Continue polling
                time.sleep(retry_after)

            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to poll operation: {e}")
                return {"success": False, "error": str(e)}

        # Timeout
        logger.error(
            f"Operation {operation_id} timed out after {max_attempts * retry_after} seconds"
        )
        return {"success": False, "error": "Operation timed out", "status": "Timeout"}
