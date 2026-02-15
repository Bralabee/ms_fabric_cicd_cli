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
"""

import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from usf_fabric_cli.services.deployment_pipeline import (
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
