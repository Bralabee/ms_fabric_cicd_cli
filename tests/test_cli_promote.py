import os
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from usf_fabric_cli.cli import app


class TestCLIPromote:
    """Tests for the promote CLI command."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_env_vars(self):
        """Mock required environment variables."""
        env_vars = {
            "FABRIC_TOKEN": "mock-token",
            "AZURE_TENANT_ID": "tenant-id",
            "AZURE_CLIENT_ID": "client-id",
            "AZURE_CLIENT_SECRET": "secret",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            yield env_vars

    def test_promote_args_passed_correctly(self, runner, mock_env_vars):
        """Verify promote calls API with correct arguments."""
        with patch(
            "usf_fabric_cli.services.deployment_pipeline.FabricDeploymentPipelineAPI"
        ) as MockAPI:
            # Setup mock
            mock_api_instance = MagicMock()
            mock_api_instance.get_pipeline_by_name.return_value = {
                "id": "pipe-123",
                "displayName": "My Pipeline",
            }
            mock_api_instance.promote.return_value = {"success": True}
            MockAPI.return_value = mock_api_instance

            # Run command
            result = runner.invoke(
                app,
                [
                    "promote",
                    "--pipeline-name",
                    "My Pipeline",
                    "--source-stage",
                    "Development",
                    "--target-stage",
                    "Test",
                    "--note",
                    "Test deployment",
                ],
            )

            # Verify call
            assert result.exit_code == 0
            mock_api_instance.promote.assert_called_once_with(
                pipeline_id="pipe-123",
                source_stage_name="Development",
                target_stage_name="Test",
                note="Test deployment",
                wait=True,
            )

    def test_promote_api_failure_handles_error(self, runner, mock_env_vars):
        """Verify promote handles API failure correctly."""
        with patch(
            "usf_fabric_cli.services.deployment_pipeline.FabricDeploymentPipelineAPI"
        ) as MockAPI:
            # Setup mock to fail
            mock_api_instance = MagicMock()
            mock_api_instance.get_pipeline_by_name.return_value = {"id": "pipe-123"}
            mock_api_instance.promote.return_value = {
                "success": False,
                "error": "API Error",
            }
            MockAPI.return_value = mock_api_instance

            # Run command
            result = runner.invoke(app, ["promote", "--pipeline-name", "My Pipeline"])

            # Verify failure
            assert result.exit_code == 1
            assert "Promotion failed" in result.output
            assert "API Error" in result.output

    def test_promote_pipeline_not_found(self, runner, mock_env_vars):
        """Verify promote handles missing pipeline error."""
        with patch(
            "usf_fabric_cli.services.deployment_pipeline.FabricDeploymentPipelineAPI"
        ) as MockAPI:
            # Setup mock to return None for pipeline
            mock_api_instance = MagicMock()
            mock_api_instance.get_pipeline_by_name.return_value = None
            MockAPI.return_value = mock_api_instance

            # Run command
            result = runner.invoke(
                app, ["promote", "--pipeline-name", "NonExistent Pipeline"]
            )

            # Verify failure
            assert result.exit_code == 1
            assert "not found" in result.output

    def test_promote_target_inference(self, runner, mock_env_vars):
        """Verify promote infers target stage if omitted."""
        with patch(
            "usf_fabric_cli.services.deployment_pipeline.FabricDeploymentPipelineAPI"
        ) as MockAPI:
            mock_api_instance = MagicMock()
            mock_api_instance.get_pipeline_by_name.return_value = {"id": "pipe-123"}
            mock_api_instance.promote.return_value = {"success": True}
            MockAPI.return_value = mock_api_instance

            # Run command without target stage
            result = runner.invoke(
                app,
                [
                    "promote",
                    "--pipeline-name",
                    "My Pipeline",
                    "--source-stage",
                    "Development",
                ],
            )

            assert result.exit_code == 0
            # Backend logic in cli.py passes None to api.promote if target_stage is None
            # The API class handles the inference.
            # CLI passes: source_stage="Development", target_stage=None
            mock_api_instance.promote.assert_called_once()
            call_args = mock_api_instance.promote.call_args[1]
            assert call_args["source_stage_name"] == "Development"
            assert call_args["target_stage_name"] is None

    def test_promote_exception_handling(self, runner, mock_env_vars):
        """Verify promote handles unexpected exceptions."""
        with patch(
            "usf_fabric_cli.services.deployment_pipeline.FabricDeploymentPipelineAPI"
        ) as MockAPI:
            # Setup mock to raise exception
            MockAPI.side_effect = Exception("Unexpected Crash")

            # Run command
            result = runner.invoke(app, ["promote", "--pipeline-name", "Pipe"])

            # Verify failure
            assert result.exit_code == 1
            assert "Promote failed" in result.output
            assert "Unexpected Crash" in result.output
