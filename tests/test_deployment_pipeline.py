"""
Tests for FabricDeploymentPipelineAPI service.

Tests verify:
- Pipeline CRUD operations (list, get, create, delete)
- Stage management (get stages, assign/unassign workspaces)
- Deployment (promote) between stages
- Long-running operation polling
- High-level promote() convenience method
- DeploymentStage.next_stage() logic
- Retry and token refresh behaviour
- Power BI API: token acquisition, principal type mapping,
  list_pipeline_users, add_pipeline_user
"""

import os
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
import requests

from usf_fabric_cli.services.deployment_pipeline import (
    PBI_API_BASE_URL,
    PBI_PRINCIPAL_TYPE_MAP,
    PBI_TOKEN_SCOPE,
    DeploymentStage,
    FabricDeploymentPipelineAPI,
)

# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def mock_env_vars():
    """Mock required environment variables."""
    env = {
        "FABRIC_TOKEN": "mock-token-12345",
        "AZURE_TENANT_ID": "12345678-1234-1234-1234-123456789012",
        "AZURE_CLIENT_ID": "12345678-1234-1234-1234-123456789012",
        "AZURE_CLIENT_SECRET": "mock-secret",
    }
    with patch.dict(os.environ, env, clear=False):
        yield env


@pytest.fixture
def api(mock_env_vars):
    """Create a FabricDeploymentPipelineAPI instance."""
    return FabricDeploymentPipelineAPI(access_token="mock-token-12345")


# ── DeploymentStage tests ─────────────────────────────────────────


class TestDeploymentStage:
    """Tests for DeploymentStage helper class."""

    def test_next_stage_dev_to_test(self):
        assert DeploymentStage.next_stage("Development") == "Test"

    def test_next_stage_test_to_prod(self):
        assert DeploymentStage.next_stage("Test") == "Production"

    def test_next_stage_prod_is_none(self):
        assert DeploymentStage.next_stage("Production") is None

    def test_next_stage_unknown_is_none(self):
        assert DeploymentStage.next_stage("UnknownStage") is None

    def test_order_list(self):
        assert DeploymentStage.ORDER == ["Development", "Test", "Production"]


# ── Pipeline CRUD tests ───────────────────────────────────────────


class TestPipelineCRUD:
    """Tests for pipeline CRUD operations."""

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.request")
    def test_list_pipelines_success(self, mock_request, api):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "value": [
                {"id": "pipe-1", "displayName": "My Pipeline"},
                {"id": "pipe-2", "displayName": "Other Pipeline"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        result = api.list_pipelines()

        assert result["success"] is True
        assert len(result["pipelines"]) == 2

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.request")
    def test_list_pipelines_failure(self, mock_request, api):
        mock_request.side_effect = requests.RequestException("Network error")

        result = api.list_pipelines()

        assert result["success"] is False
        assert "Network error" in result["error"]

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.request")
    def test_get_pipeline_success(self, mock_request, api):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "pipe-1",
            "displayName": "My Pipeline",
        }
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        result = api.get_pipeline("pipe-1")

        assert result["success"] is True
        assert result["pipeline"]["displayName"] == "My Pipeline"

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.request")
    def test_create_pipeline_success(self, mock_request, api):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "new-pipe",
            "displayName": "New Pipeline",
        }
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        result = api.create_pipeline("New Pipeline", "Description")

        assert result["success"] is True
        assert result["pipeline"]["id"] == "new-pipe"

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.request")
    def test_delete_pipeline_success(self, mock_request, api):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        result = api.delete_pipeline("pipe-to-delete")

        assert result["success"] is True

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.request")
    def test_get_pipeline_by_name_found(self, mock_request, api):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "value": [
                {"id": "pipe-1", "displayName": "My Pipeline"},
                {"id": "pipe-2", "displayName": "Other Pipeline"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        result = api.get_pipeline_by_name("Other Pipeline")

        assert result is not None
        assert result["id"] == "pipe-2"

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.request")
    def test_get_pipeline_by_name_not_found(self, mock_request, api):
        mock_response = MagicMock()
        mock_response.json.return_value = {"value": []}
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        result = api.get_pipeline_by_name("Nonexistent")

        assert result is None


# ── Stage management tests ────────────────────────────────────────


class TestStageManagement:
    """Tests for pipeline stage management."""

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.request")
    def test_get_pipeline_stages(self, mock_request, api):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "value": [
                {"id": "stage-1", "displayName": "Development", "order": 0},
                {"id": "stage-2", "displayName": "Test", "order": 1},
                {"id": "stage-3", "displayName": "Production", "order": 2},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        result = api.get_pipeline_stages("pipe-1")

        assert result["success"] is True
        assert len(result["stages"]) == 3

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.request")
    def test_assign_workspace_to_stage(self, mock_request, api):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        result = api.assign_workspace_to_stage("pipe-1", "stage-1", "ws-123")

        assert result["success"] is True

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.request")
    def test_unassign_workspace_from_stage(self, mock_request, api):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        result = api.unassign_workspace_from_stage("pipe-1", "stage-1")

        assert result["success"] is True


# ── Deployment (promote) tests ────────────────────────────────────


class TestDeployment:
    """Tests for deployment / promotion operations."""

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.request")
    def test_deploy_to_stage_success(self, mock_request, api):
        mock_response = MagicMock()
        mock_response.headers = {
            "x-ms-operation-id": "op-12345",
            "Retry-After": "10",
        }
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        result = api.deploy_to_stage(
            pipeline_id="pipe-1",
            source_stage_id="stage-1",
            target_stage_id="stage-2",
            note="Test deploy",
        )

        assert result["success"] is True
        assert result["operation_id"] == "op-12345"
        assert result["retry_after"] == 10

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.request")
    def test_deploy_to_stage_failure(self, mock_request, api):
        mock_exc = requests.RequestException("Deploy failed")
        mock_exc.response = MagicMock()
        mock_exc.response.text = "Server error"
        mock_request.side_effect = mock_exc

        result = api.deploy_to_stage("pipe-1", "stage-1", "stage-2")

        assert result["success"] is False

    @patch("usf_fabric_cli.services.deployment_pipeline.time.sleep")
    @patch("usf_fabric_cli.services.deployment_pipeline.requests.request")
    def test_poll_operation_success(self, mock_request, mock_sleep, api):
        # First poll: running; second poll: succeeded
        running = MagicMock()
        running.json.return_value = {"status": "Running"}
        running.raise_for_status = MagicMock()

        succeeded = MagicMock()
        succeeded.json.return_value = {"status": "Succeeded"}
        succeeded.raise_for_status = MagicMock()

        mock_request.side_effect = [running, succeeded]

        result = api.poll_operation("op-12345", max_attempts=5, retry_after=1)

        assert result["success"] is True
        assert result["status"] == "Succeeded"
        assert mock_sleep.call_count == 1

    @patch("usf_fabric_cli.services.deployment_pipeline.time.sleep")
    @patch("usf_fabric_cli.services.deployment_pipeline.requests.request")
    def test_poll_operation_timeout(self, mock_request, mock_sleep, api):
        running = MagicMock()
        running.json.return_value = {"status": "Running"}
        running.raise_for_status = MagicMock()
        mock_request.return_value = running

        result = api.poll_operation("op-12345", max_attempts=2, retry_after=1)

        assert result["success"] is False
        assert result["status"] == "Timeout"


# ── High-level promote() tests ────────────────────────────────────


class TestPromote:
    """Tests for the high-level promote() convenience method."""

    @patch("usf_fabric_cli.services.deployment_pipeline.time.sleep")
    @patch("usf_fabric_cli.services.deployment_pipeline.requests.request")
    def test_promote_dev_to_test(self, mock_request, mock_sleep, api):
        # Call 1: get stages
        stages_resp = MagicMock()
        stages_resp.json.return_value = {
            "value": [
                {"id": "s1", "displayName": "Development"},
                {"id": "s2", "displayName": "Test"},
                {"id": "s3", "displayName": "Production"},
            ]
        }
        stages_resp.raise_for_status = MagicMock()

        # Call 2: deploy
        deploy_resp = MagicMock()
        deploy_resp.headers = {
            "x-ms-operation-id": "op-999",
            "Retry-After": "5",
        }
        deploy_resp.raise_for_status = MagicMock()

        # Call 3: poll (succeeded)
        poll_resp = MagicMock()
        poll_resp.json.return_value = {"status": "Succeeded"}
        poll_resp.raise_for_status = MagicMock()

        mock_request.side_effect = [stages_resp, deploy_resp, poll_resp]

        result = api.promote(
            pipeline_id="pipe-1",
            source_stage_name="Development",
        )

        assert result["success"] is True

    def test_promote_no_next_stage(self, api):
        result = api.promote(
            pipeline_id="pipe-1",
            source_stage_name="Production",
        )

        assert result["success"] is False
        assert "No next stage" in result["error"]


# ── Token refresh tests ───────────────────────────────────────────


class TestTokenRefresh:
    """Tests for token refresh behavior."""

    def test_token_refresh_updates_headers(self, mock_env_vars):
        mock_tm = MagicMock()
        mock_tm.get_token.return_value = "new-token-value"

        api = FabricDeploymentPipelineAPI(
            access_token="old-token",
            token_manager=mock_tm,
        )

        api._refresh_token_if_needed()

        assert api.headers["Authorization"] == "Bearer new-token-value"
        assert api._access_token == "new-token-value"

    def test_token_refresh_noop_without_manager(self, mock_env_vars):
        api = FabricDeploymentPipelineAPI(access_token="token-abc")

        api._refresh_token_if_needed()

        # Stays the same
        assert api.headers["Authorization"] == "Bearer token-abc"


# ── PBI API constants tests ───────────────────────────────────────


class TestPBIConstants:
    """Tests for Power BI API constants and mapping table."""

    def test_pbi_api_base_url(self):
        assert PBI_API_BASE_URL == "https://api.powerbi.com/v1.0/myorg"

    def test_pbi_token_scope(self):
        assert PBI_TOKEN_SCOPE == "https://analysis.windows.net/powerbi/api/.default"

    def test_principal_type_map_service_principal(self):
        assert PBI_PRINCIPAL_TYPE_MAP["ServicePrincipal"] == "App"

    def test_principal_type_map_case_insensitive_sp(self):
        assert PBI_PRINCIPAL_TYPE_MAP["serviceprincipal"] == "App"

    def test_principal_type_map_app(self):
        assert PBI_PRINCIPAL_TYPE_MAP["App"] == "App"

    def test_principal_type_map_user(self):
        assert PBI_PRINCIPAL_TYPE_MAP["User"] == "User"

    def test_principal_type_map_group(self):
        assert PBI_PRINCIPAL_TYPE_MAP["Group"] == "Group"


# ── PBI token acquisition tests ───────────────────────────────────


class TestPBITokenAcquisition:
    """Tests for _get_pbi_headers() and _map_principal_type()."""

    def test_map_principal_type_sp_to_app(self, api):
        assert api._map_principal_type("ServicePrincipal") == "App"

    def test_map_principal_type_user_unchanged(self, api):
        assert api._map_principal_type("User") == "User"

    def test_map_principal_type_group_unchanged(self, api):
        assert api._map_principal_type("Group") == "Group"

    def test_map_principal_type_unknown_passthrough(self, api):
        """Unknown types are returned as-is (passthrough)."""
        assert api._map_principal_type("CustomPrincipal") == "CustomPrincipal"

    def test_get_pbi_headers_with_token_manager(self, mock_env_vars):
        """When TokenManager has a credential, acquire PBI-scoped token."""
        mock_credential = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "pbi-token-from-credential"
        mock_credential.get_token.return_value = mock_token

        mock_tm = MagicMock()
        mock_tm._credential = mock_credential
        mock_tm.get_token.return_value = "fabric-token"

        api = FabricDeploymentPipelineAPI(
            access_token="fabric-token",
            token_manager=mock_tm,
        )

        headers = api._get_pbi_headers()

        assert headers["Authorization"] == "Bearer pbi-token-from-credential"
        assert headers["Content-Type"] == "application/json"
        mock_credential.get_token.assert_called_once_with(PBI_TOKEN_SCOPE)

    def test_get_pbi_headers_fallback_to_fabric_token(self, mock_env_vars):
        """When no TokenManager, fall back to the Fabric token."""
        api = FabricDeploymentPipelineAPI(access_token="my-fabric-token")

        headers = api._get_pbi_headers()

        assert headers["Authorization"] == "Bearer my-fabric-token"

    def test_get_pbi_headers_credential_exception_fallback(self, mock_env_vars):
        """When credential.get_token raises, fall back to Fabric token."""
        mock_credential = MagicMock()
        mock_credential.get_token.side_effect = Exception("MSAL error")

        mock_tm = MagicMock()
        mock_tm._credential = mock_credential
        mock_tm.get_token.return_value = "fabric-token"

        api = FabricDeploymentPipelineAPI(
            access_token="fabric-token",
            token_manager=mock_tm,
        )

        headers = api._get_pbi_headers()

        # Falls back to Fabric token on error
        assert headers["Authorization"] == "Bearer fabric-token"

    def test_get_pbi_headers_caches_token(self, mock_env_vars):
        """PBI token is cached — second call doesn't re-acquire."""
        mock_credential = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "cached-pbi-token"
        mock_credential.get_token.return_value = mock_token

        mock_tm = MagicMock()
        mock_tm._credential = mock_credential
        mock_tm.get_token.return_value = "fabric-token"

        api = FabricDeploymentPipelineAPI(
            access_token="fabric-token",
            token_manager=mock_tm,
        )

        # First call acquires
        api._get_pbi_headers()
        # Second call should use cache
        api._get_pbi_headers()

        # get_token called only once
        assert mock_credential.get_token.call_count == 1

    def test_get_pbi_headers_no_credential_attribute(self, mock_env_vars):
        """When TokenManager exists but has no _credential, fall back."""
        mock_tm = MagicMock(spec=[])  # Empty spec — no _credential
        mock_tm.get_token = MagicMock(return_value="fabric-token")

        api = FabricDeploymentPipelineAPI(
            access_token="fabric-token",
            token_manager=mock_tm,
        )

        headers = api._get_pbi_headers()

        assert headers["Authorization"] == "Bearer fabric-token"


# ── Pipeline user management tests (PBI API) ──────────────────────


class TestPipelineUsers:
    """Tests for list_pipeline_users() and add_pipeline_user()."""

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.get")
    def test_list_pipeline_users_success(self, mock_get, api):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "value": [
                {
                    "identifier": "user-001",
                    "principalType": "User",
                    "accessRight": "Admin",
                },
                {
                    "identifier": "sp-001",
                    "principalType": "App",
                    "accessRight": "Admin",
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = api.list_pipeline_users("pipe-abc")

        assert result["success"] is True
        assert len(result["users"]) == 2
        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        assert "api.powerbi.com" in call_url
        assert "/pipelines/pipe-abc/users" in call_url

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.get")
    def test_list_pipeline_users_failure(self, mock_get, api):
        mock_get.side_effect = requests.RequestException("Connection refused")

        result = api.list_pipeline_users("pipe-abc")

        assert result["success"] is False
        assert "Connection refused" in result["error"]

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.post")
    def test_add_pipeline_user_success(self, mock_post, api):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = api.add_pipeline_user(
            pipeline_id="pipe-abc",
            identifier="group-guid-123",
            principal_type="Group",
            pipeline_role="Admin",
        )

        assert result["success"] is True
        # Verify the POST body
        call_kwargs = mock_post.call_args
        body = (
            call_kwargs[1]["json"]
            if "json" in call_kwargs[1]
            else call_kwargs.kwargs["json"]
        )
        assert body["principalType"] == "Group"
        assert body["accessRight"] == "Admin"
        assert body["identifier"] == "group-guid-123"

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.post")
    def test_add_pipeline_user_sp_mapped_to_app(self, mock_post, api):
        """ServicePrincipal type is automatically mapped to App."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = api.add_pipeline_user(
            pipeline_id="pipe-abc",
            identifier="sp-guid-456",
            principal_type="ServicePrincipal",
            pipeline_role="Admin",
        )

        assert result["success"] is True
        call_kwargs = mock_post.call_args
        body = (
            call_kwargs[1]["json"]
            if "json" in call_kwargs[1]
            else call_kwargs.kwargs["json"]
        )
        # Must be "App", not "ServicePrincipal"
        assert body["principalType"] == "App"

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.post")
    def test_add_pipeline_user_already_exists_409(self, mock_post, api):
        """409 Conflict (already exists) is handled as success with reused flag."""
        mock_exc = requests.HTTPError("409 Conflict")
        mock_resp = MagicMock()
        mock_resp.status_code = 409
        mock_resp.text = "User already exists"
        mock_exc.response = mock_resp

        mock_post_response = MagicMock()
        mock_post_response.raise_for_status.side_effect = mock_exc
        mock_post_response.status_code = 409
        mock_post.return_value = mock_post_response

        result = api.add_pipeline_user(
            pipeline_id="pipe-abc",
            identifier="existing-user",
            principal_type="User",
        )

        assert result["success"] is True
        assert result.get("reused") is True

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.post")
    def test_add_pipeline_user_network_failure(self, mock_post, api):
        mock_post.side_effect = requests.RequestException("Timeout")

        result = api.add_pipeline_user(
            pipeline_id="pipe-abc",
            identifier="user-guid",
            principal_type="User",
        )

        assert result["success"] is False
        assert "Timeout" in result["error"]

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.post")
    def test_add_pipeline_user_uses_pbi_url(self, mock_post, api):
        """Verify the POST goes to api.powerbi.com, not api.fabric."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        api.add_pipeline_user("pipe-abc", "id-123", "User")

        call_url = mock_post.call_args[0][0]
        assert "api.powerbi.com" in call_url
        assert "api.fabric.microsoft.com" not in call_url

    @patch("usf_fabric_cli.services.deployment_pipeline.requests.post")
    def test_add_pipeline_user_access_right_field(self, mock_post, api):
        """Verify the PBI API uses 'accessRight', not 'pipelineRole'."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        api.add_pipeline_user("pipe-abc", "id-123", "User", "Admin")

        body = mock_post.call_args[1]["json"]
        assert "accessRight" in body
        assert "pipelineRole" not in body
