"""
Tests for fabric_git_api.py - Fabric Git Integration REST API client.

Tests verify:
- Git connection creation for GitHub and Azure DevOps
- Workspace-to-Git connection workflows
- API response handling
- Error handling
"""

from unittest.mock import patch, MagicMock
import pytest

from usf_fabric_cli.services.fabric_git_api import (
    FabricGitAPI,
    GitProviderType,
    GitConnectionSource,
)


class TestFabricGitAPIInit:
    """Tests for FabricGitAPI initialization."""

    def test_init_with_default_base_url(self):
        """Test initialization with default base URL."""
        api = FabricGitAPI(access_token="test-token")

        # Check the base_url (access_token is stored in headers)
        assert "fabric.microsoft.com" in api.base_url

    def test_init_with_custom_base_url(self):
        """Test initialization with custom base URL."""
        api = FabricGitAPI(
            access_token="test-token", base_url="https://custom.api.com/v1"
        )

        assert api.base_url == "https://custom.api.com/v1"

    def test_headers_include_auth_token(self):
        """Test that headers include authorization token."""
        api = FabricGitAPI(access_token="my-secret-token")

        assert "Authorization" in api.headers
        assert "my-secret-token" in api.headers["Authorization"]
        assert "Bearer" in api.headers["Authorization"]


class TestGitProviderTypes:
    """Tests for Git provider type enums."""

    def test_github_provider_type(self):
        """Test GitHub provider type value."""
        assert GitProviderType.GITHUB.value == "GitHub"

    def test_azure_devops_provider_type(self):
        """Test Azure DevOps provider type value."""
        assert GitProviderType.AZURE_DEVOPS.value == "AzureDevOps"


class TestGitConnectionSource:
    """Tests for Git connection source enum."""

    def test_automatic_source(self):
        """Test Automatic connection source."""
        assert GitConnectionSource.AUTOMATIC.value == "Automatic"

    def test_configured_connection_source(self):
        """Test ConfiguredConnection source."""
        assert GitConnectionSource.CONFIGURED_CONNECTION.value == "ConfiguredConnection"


class TestListConnections:
    """Tests for list_connections method."""

    @pytest.fixture
    def api(self):
        """Create API instance."""
        return FabricGitAPI(access_token="test-token", max_retries=0)

    @patch("usf_fabric_cli.services.fabric_git_api.requests.request")
    def test_list_connections_success(self, mock_request, api):
        """Test successful listing of connections."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "value": [
                {"id": "conn-1", "displayName": "GitHub Connection"},
                {"id": "conn-2", "displayName": "ADO Connection"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        result = api.list_connections()

        assert result["success"] is True
        assert len(result["connections"]) == 2
        assert result["connections"][0]["id"] == "conn-1"
        mock_request.assert_called_once()

    @patch("usf_fabric_cli.services.fabric_git_api.requests.request")
    def test_list_connections_empty(self, mock_request, api):
        """Test listing when no connections exist."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"value": []}
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        result = api.list_connections()

        assert result["success"] is True
        assert result["connections"] == []


class TestGetConnectionByName:
    """Tests for get_connection_by_name method."""

    @pytest.fixture
    def api(self):
        """Create API instance."""
        return FabricGitAPI(access_token="test-token", max_retries=0)

    @patch("usf_fabric_cli.services.fabric_git_api.requests.request")
    def test_get_connection_by_name_found(self, mock_request, api):
        """Test finding a connection by name."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "value": [
                {"id": "conn-1", "displayName": "My Connection"},
                {"id": "conn-2", "displayName": "Other Connection"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        result = api.get_connection_by_name("My Connection")

        assert result is not None
        assert result["id"] == "conn-1"

    @patch("usf_fabric_cli.services.fabric_git_api.requests.request")
    def test_get_connection_by_name_not_found(self, mock_request, api):
        """Test when connection name not found."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"value": []}
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        result = api.get_connection_by_name("Nonexistent")

        assert result is None


class TestConnectWorkspaceToGit:
    """Tests for connect_workspace_to_git method."""

    @pytest.fixture
    def api(self):
        """Create API instance."""
        return FabricGitAPI(access_token="test-token")

    @patch("usf_fabric_cli.services.fabric_git_api.requests.post")
    def test_connect_github_repository(self, mock_post, api):
        """Test connecting workspace to GitHub repository."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = api.connect_workspace_to_git(
            workspace_id="ws-123",
            provider_type=GitProviderType.GITHUB,
            owner_name="owner",
            repository_name="my-repo",
            branch_name="main",
        )

        assert result["success"] is True
        mock_post.assert_called_once()

        # Verify request body structure
        call_args = mock_post.call_args
        assert "json" in call_args.kwargs

    @patch("usf_fabric_cli.services.fabric_git_api.requests.post")
    def test_connect_azure_devops_repository(self, mock_post, api):
        """Test connecting workspace to Azure DevOps repository."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = api.connect_workspace_to_git(
            workspace_id="ws-456",
            provider_type=GitProviderType.AZURE_DEVOPS,
            organization_name="my-ado-org",
            project_name="my-project",
            repository_name="my-repo",
            branch_name="develop",
        )

        assert result["success"] is True

    def test_connect_github_missing_params(self, api):
        """Test GitHub connection fails without required params."""
        with pytest.raises(ValueError, match="owner_name"):
            api.connect_workspace_to_git(
                workspace_id="ws-123",
                provider_type=GitProviderType.GITHUB,
                repository_name="my-repo",
            )

    def test_connect_azure_devops_missing_params(self, api):
        """Test Azure DevOps connection fails without required params."""
        with pytest.raises(ValueError, match="organization_name"):
            api.connect_workspace_to_git(
                workspace_id="ws-123",
                provider_type=GitProviderType.AZURE_DEVOPS,
                repository_name="my-repo",
            )


class TestGetGitStatus:
    """Tests for get_git_status method."""

    @pytest.fixture
    def api(self):
        """Create API instance."""
        return FabricGitAPI(access_token="test-token")

    @patch("usf_fabric_cli.services.fabric_git_api.requests.get")
    def test_get_git_status_success(self, mock_get, api):
        """Test getting Git status for workspace."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "workspaceHead": "abc123",
            "remoteCommitHash": "def456",
            "changes": [],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = api.get_git_status("ws-123")

        assert result["success"] is True
        assert "status" in result
        assert result["status"]["workspaceHead"] == "abc123"


class TestGetGitConnection:
    """Tests for get_git_connection method."""

    @pytest.fixture
    def api(self):
        """Create API instance."""
        return FabricGitAPI(access_token="test-token")

    @patch("usf_fabric_cli.services.fabric_git_api.requests.get")
    def test_get_git_connection_success(self, mock_get, api):
        """Test getting Git connection details."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "gitProviderDetails": {
                "organizationName": "my-org",
                "repositoryName": "my-repo",
                "branchName": "main",
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = api.get_git_connection("ws-123")

        assert result["success"] is True
        assert "connection" in result
        assert result["connection"]["gitProviderDetails"]["branchName"] == "main"


class TestDisconnectFromGit:
    """Tests for disconnect_from_git method."""

    @pytest.fixture
    def api(self):
        """Create API instance."""
        return FabricGitAPI(access_token="test-token")

    @patch(
        "usf_fabric_cli.services.fabric_git_api.requests.post"
    )  # disconnect uses POST, not DELETE
    def test_disconnect_success(self, mock_post, api):
        """Test disconnecting workspace from Git."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = api.disconnect_from_git("ws-123")

        assert result["success"] is True
        mock_post.assert_called_once()


class TestPollOperation:
    """Tests for poll_operation method."""

    @pytest.fixture
    def api(self):
        """Create API instance."""
        return FabricGitAPI(access_token="test-token")

    @patch("usf_fabric_cli.services.fabric_git_api.requests.get")
    @patch("usf_fabric_cli.services.fabric_git_api.time.sleep")
    def test_poll_operation_succeeds(self, mock_sleep, mock_get, api):
        """Test polling an operation until success."""
        # First call returns "Running", second returns "Succeeded"
        mock_response_running = MagicMock()
        mock_response_running.json.return_value = {"status": "Running"}
        mock_response_running.raise_for_status = MagicMock()

        mock_response_success = MagicMock()
        mock_response_success.json.return_value = {"status": "Succeeded"}
        mock_response_success.raise_for_status = MagicMock()

        mock_get.side_effect = [mock_response_running, mock_response_success]

        result = api.poll_operation("op-123", max_attempts=5, retry_after=1)

        assert result["success"] is True
        assert result["status"] == "Succeeded"
        assert mock_get.call_count == 2

    @patch("usf_fabric_cli.services.fabric_git_api.requests.get")
    @patch("usf_fabric_cli.services.fabric_git_api.time.sleep")
    def test_poll_operation_immediate_success(self, mock_sleep, mock_get, api):
        """Test polling when operation immediately succeeds."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "Succeeded"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = api.poll_operation("op-123")

        assert result["success"] is True
        assert result["status"] == "Succeeded"
        # Should only poll once
        assert mock_get.call_count == 1

    @patch("usf_fabric_cli.services.fabric_git_api.requests.get")
    @patch("usf_fabric_cli.services.fabric_git_api.time.sleep")
    def test_poll_operation_failed(self, mock_sleep, mock_get, api):
        """Test polling when operation fails."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "Failed",
            "error": "Something went wrong",
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = api.poll_operation("op-123")

        assert result["success"] is False
        assert result["status"] == "Failed"


class TestInitializeGitConnection:
    """Tests for initialize_git_connection method."""

    @pytest.fixture
    def api(self):
        """Create API instance."""
        return FabricGitAPI(access_token="test-token")

    @patch("usf_fabric_cli.services.fabric_git_api.requests.post")
    def test_initialize_success(self, mock_post, api):
        """Test initializing Git connection."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "RequiredAction": "UpdateFromGit",
            "RemoteCommitHash": "abc123",
            "WorkspaceHead": "def456",
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = api.initialize_git_connection("ws-123")

        assert result["success"] is True
        assert result["required_action"] == "UpdateFromGit"
