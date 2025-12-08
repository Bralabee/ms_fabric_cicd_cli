"""
Unit tests for Fabric CLI wrapper
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json

from src.core.fabric_wrapper import FabricCLIWrapper, FabricDiagnostics


class TestFabricCLIWrapper:

    def setup_method(self):
        """Setup test fixtures"""
        telemetry = MagicMock()
        telemetry.emit = MagicMock()
        # Disable version check to avoid subprocess call during init
        self.fabric = FabricCLIWrapper(
            "fake-token", telemetry_client=telemetry, validate_version=False
        )

    @patch("subprocess.run")
    def test_create_workspace_success(self, mock_run):
        """Test successful workspace creation"""

        # Mock responses for sequence of calls:
        # 1. _item_exists -> False
        # 2. create command -> Success

        mock_exists = Mock(stdout="false", stderr="", returncode=0)
        mock_create = Mock(
            stdout='{"id": "workspace-123", "displayName": "test-workspace"}',
            stderr="",
            returncode=0,
        )

        mock_run.side_effect = [mock_exists, mock_create]

        # Use a GUID capacity to trigger the API path which returns JSON
        result = self.fabric.create_workspace(
            "test-workspace", "00000000-0000-0000-0000-000000000000", "Test description"
        )

        assert result["success"] is True
        assert result.get("workspace_id") == "workspace-123"

        # Verify commands
        assert mock_run.call_count == 2

        # Check first call (exists)
        args0 = mock_run.call_args_list[0][0][0]
        assert args0 == ["fab", "exists", "test-workspace.Workspace"]

        # Check second call (create)
        args1 = mock_run.call_args_list[1][0][0]
        assert args1[:2] == ["fab", "api"]
        assert "workspaces" in args1[2]
        assert "-X" in args1
        assert "post" in args1

    @patch("subprocess.run")
    def test_create_workspace_already_exists(self, mock_run):
        """Test workspace creation when workspace already exists (idempotency)"""

        # Mock responses:
        # 1. _item_exists -> True
        # 2. get_workspace -> Success

        mock_exists = Mock(stdout="true", stderr="", returncode=0)
        mock_get = Mock(
            stdout='{"id": "workspace-123", "displayName": "test-workspace"}',
            stderr="",
            returncode=0,
        )

        mock_run.side_effect = [mock_exists, mock_get]

        result = self.fabric.create_workspace("test-workspace", "F64")

        assert result["success"] is True
        assert result.get("reused") is True
        assert result.get("workspace_id") == "workspace-123"

    @patch("subprocess.run")
    def test_create_lakehouse_with_folder(self, mock_run):
        """Test lakehouse creation in specific folder"""

        # Mock responses:
        # 1. get_workspace_id -> get_workspace -> success
        # 2. get_folder_id -> list folders -> success (found)
        # 3. get_workspace_id (again inside create_lakehouse) -> success
        # 4. create_lakehouse -> api call -> success

        workspace_response = Mock(
            stdout='{"id": "workspace-123"}', stderr="", returncode=0
        )
        folders_response = Mock(
            stdout='{"value": [{"id": "folder-456", "displayName": "test-folder"}]}',
            stderr="",
            returncode=0,
        )
        create_response = Mock(
            stdout='{"id": "lakehouse-123", "displayName": "test-lakehouse"}',
            stderr="",
            returncode=0,
        )

        # Sequence:
        # get_folder_id calls:
        #   get_workspace_id -> get_workspace -> workspace_response
        #   api folders -> folders_response
        # create_lakehouse calls:
        #   get_workspace_id -> get_workspace -> workspace_response
        #   api items -> create_response

        mock_run.side_effect = [
            workspace_response,
            folders_response,
            workspace_response,
            create_response,
        ]

        result = self.fabric.create_lakehouse(
            "test-workspace", "test-lakehouse", "Test lakehouse", "test-folder"
        )

        assert result["success"] is True

        # Verify the create command payload
        create_call = mock_run.call_args_list[3]
        args = create_call[0][0]
        assert args[:2] == ["fab", "api"]

        # Find the JSON payload
        payload_idx = args.index("-i") + 1
        payload = json.loads(args[payload_idx])

        assert payload["folderId"] == "folder-456"
        assert payload["displayName"] == "test-lakehouse"
        assert payload["type"] == "Lakehouse"

    @patch("subprocess.run")
    def test_diagnostic_fabric_cli_installed(self, mock_run):
        """Test Fabric CLI installation check"""

        mock_run.return_value = Mock(stdout="Fabric CLI 1.0.0", stderr="", returncode=0)

        diagnostics = FabricDiagnostics(self.fabric)
        result = diagnostics.validate_fabric_cli_installation()

        assert result["success"] is True
        assert "1.0.0" in result["version"]

    @patch("subprocess.run")
    def test_diagnostic_fabric_cli_not_installed(self, mock_run):
        """Test Fabric CLI not installed"""

        mock_run.side_effect = FileNotFoundError("fabric command not found")

        diagnostics = FabricDiagnostics(self.fabric)
        result = diagnostics.validate_fabric_cli_installation()

        assert result["success"] is False
        assert "not found" in result["error"]
        assert "remediation" in result


if __name__ == "__main__":
    pytest.main([__file__])
