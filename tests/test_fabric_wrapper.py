"""
Unit tests for Fabric CLI wrapper
"""

import json
import subprocess
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from usf_fabric_cli.services.fabric_wrapper import FabricCLIWrapper, FabricDiagnostics


class TestFabricCLIWrapper:

    def setup_method(self):
        """Setup test fixtures"""
        telemetry = MagicMock()
        telemetry.emit = MagicMock()

        # Patch subprocess.run to avoid actual CLI calls during init
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="Fabric CLI 1.0.0", returncode=0)
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

    @patch("subprocess.run")
    def test_delete_workspace(self, mock_run):
        """Test workspace deletion"""
        mock_run.return_value = Mock(stdout="", stderr="", returncode=0)

        result = self.fabric.delete_workspace("test-workspace")

        assert result["success"] is True
        args = mock_run.call_args[0][0]
        assert args == ["fab", "rm", "test-workspace.Workspace", "--force"]

    # ── PBI API fallback for workspace deletion ────────────────────

    @patch("usf_fabric_cli.services.fabric_wrapper.requests.delete")
    @patch("subprocess.run")
    def test_delete_workspace_pbi_fallback_on_unknown_error(
        self, mock_run, mock_pbi_delete
    ):
        """Test PBI API fallback when fab rm returns UnknownError."""
        import subprocess

        # fab rm fails with UnknownError
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["fab", "rm", "ws.Workspace", "--force"],
            stderr="x rm: [UnknownError] An unexpected error occurred",
        )

        # get_workspace_id needs to work (second call)
        def run_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if "rm" in cmd:
                raise subprocess.CalledProcessError(
                    returncode=1,
                    cmd=cmd,
                    stderr="x rm: [UnknownError] An unexpected error occurred",
                )
            # Return workspace ID for get_workspace
            return Mock(
                stdout='{"id": "ws-id-123", "displayName": "ws"}',
                stderr="",
                returncode=0,
            )

        mock_run.side_effect = run_side_effect

        # PBI API succeeds
        mock_pbi_response = Mock()
        mock_pbi_response.status_code = 200
        mock_pbi_delete.return_value = mock_pbi_response

        result = self.fabric.delete_workspace("ws")

        assert result["success"] is True
        assert result.get("method") == "pbi_api"
        mock_pbi_delete.assert_called_once()
        call_url = mock_pbi_delete.call_args[0][0]
        assert "groups/ws-id-123" in call_url

    @patch("usf_fabric_cli.services.fabric_wrapper.requests.delete")
    @patch("subprocess.run")
    def test_delete_workspace_pbi_fallback_204(self, mock_run, mock_pbi_delete):
        """Test PBI API fallback returns success on 204 (No Content)."""
        import subprocess

        def run_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if "rm" in cmd:
                raise subprocess.CalledProcessError(
                    returncode=1,
                    cmd=cmd,
                    stderr="x rm: [UnknownError] An unexpected error occurred",
                )
            return Mock(stdout='{"id": "ws-id-456"}', stderr="", returncode=0)

        mock_run.side_effect = run_side_effect

        mock_pbi_response = Mock()
        mock_pbi_response.status_code = 204
        mock_pbi_delete.return_value = mock_pbi_response

        result = self.fabric.delete_workspace("my-workspace")

        assert result["success"] is True
        assert result.get("method") == "pbi_api"

    @patch("subprocess.run")
    def test_delete_workspace_no_fallback_on_other_errors(self, mock_run):
        """Test that non-UnknownError failures do NOT trigger PBI fallback."""
        import subprocess

        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["fab", "rm", "ws.Workspace", "--force"],
            stderr="x rm: [NotFound] Workspace could not be found",
        )

        result = self.fabric.delete_workspace("ws")

        assert result["success"] is False
        assert "NotFound" in result.get("error", "")
        # No PBI API call should have been made — only fab rm

    @patch("usf_fabric_cli.services.fabric_wrapper.requests.delete")
    @patch("subprocess.run")
    def test_delete_workspace_pbi_fallback_also_fails(self, mock_run, mock_pbi_delete):
        """Test error message when both fab rm and PBI API fail."""
        import subprocess

        def run_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if "rm" in cmd:
                raise subprocess.CalledProcessError(
                    returncode=1,
                    cmd=cmd,
                    stderr="x rm: [UnknownError] An unexpected error occurred",
                )
            return Mock(stdout='{"id": "ws-id-789"}', stderr="", returncode=0)

        mock_run.side_effect = run_side_effect

        # PBI API also fails
        mock_pbi_response = Mock()
        mock_pbi_response.status_code = 403
        mock_pbi_response.text = "Forbidden"
        mock_pbi_delete.return_value = mock_pbi_response

        result = self.fabric.delete_workspace("ws")

        assert result["success"] is False
        assert "UnknownError" in result.get("error", "")
        assert "PBI API fallback also failed" in result.get("error", "")

    @patch("usf_fabric_cli.services.fabric_wrapper.requests.delete")
    @patch("subprocess.run")
    def test_delete_workspace_pbi_fallback_no_workspace_id(
        self, mock_run, mock_pbi_delete
    ):
        """Test PBI fallback fails gracefully when workspace ID not resolvable."""
        import subprocess

        def run_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if "rm" in cmd:
                raise subprocess.CalledProcessError(
                    returncode=1,
                    cmd=cmd,
                    stderr="x rm: [UnknownError] An unexpected error occurred",
                )
            # get_workspace returns nothing useful
            return Mock(stdout="{}", stderr="", returncode=0)

        mock_run.side_effect = run_side_effect

        result = self.fabric.delete_workspace("ghost-workspace")

        assert result["success"] is False
        assert "PBI API fallback also failed" in result.get("error", "")
        mock_pbi_delete.assert_not_called()  # Never reached PBI API

    @patch("subprocess.run")
    def test_delete_workspace_pbi_fallback_uses_cached_id(self, mock_run):
        """Test PBI fallback uses workspace ID from cache."""
        import subprocess

        # Pre-populate cache
        self.fabric._workspace_id_cache["cached-ws"] = "cached-id-001"

        def run_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if "rm" in cmd:
                raise subprocess.CalledProcessError(
                    returncode=1,
                    cmd=cmd,
                    stderr="x rm: [UnknownError] An unexpected error occurred",
                )
            return Mock(stdout="{}", stderr="", returncode=0)

        mock_run.side_effect = run_side_effect

        with patch(
            "usf_fabric_cli.services.fabric_wrapper.requests.delete"
        ) as mock_del:
            mock_del.return_value = Mock(status_code=200)
            result = self.fabric.delete_workspace("cached-ws")

        assert result["success"] is True
        assert result.get("method") == "pbi_api"
        call_url = mock_del.call_args[0][0]
        assert "groups/cached-id-001" in call_url

    def test_get_pbi_token_no_token_manager(self):
        """Test _get_pbi_token falls back to fabric_token when no TokenManager."""
        self.fabric._token_manager = None
        token = self.fabric._get_pbi_token()
        assert token == "fake-token"

    def test_get_pbi_token_with_token_manager(self):
        """Test _get_pbi_token acquires PBI-scoped token from TokenManager."""
        from usf_fabric_cli.services.fabric_wrapper import PBI_TOKEN_SCOPE

        mock_credential = MagicMock()
        mock_credential.get_token.return_value = Mock(token="pbi-scoped-token")
        mock_tm = MagicMock()
        mock_tm._credential = mock_credential

        self.fabric._token_manager = mock_tm
        token = self.fabric._get_pbi_token()

        assert token == "pbi-scoped-token"
        mock_credential.get_token.assert_called_once_with(PBI_TOKEN_SCOPE)

    def test_get_pbi_token_credential_error_falls_back(self):
        """Test _get_pbi_token falls back to fabric_token on credential error."""
        mock_credential = MagicMock()
        mock_credential.get_token.side_effect = ValueError("auth failure")
        mock_tm = MagicMock()
        mock_tm._credential = mock_credential

        self.fabric._token_manager = mock_tm
        token = self.fabric._get_pbi_token()

        assert token == "fake-token"

    @patch("subprocess.run")
    def test_delete_workspace_safety_blocks_populated(self, mock_run):
        """Test safety mode blocks deletion of populated workspaces."""
        # get_workspace_id → items API
        ws_response = Mock(stdout='{"id": "ws-safe-123"}', stderr="", returncode=0)
        items_response = Mock(
            stdout=json.dumps(
                {"value": [{"id": "i1", "type": "Lakehouse", "displayName": "lh1"}]}
            ),
            stderr="",
            returncode=0,
        )
        mock_run.side_effect = [ws_response, items_response]

        result = self.fabric.delete_workspace("protected-ws", safe=True)

        assert result["success"] is False
        assert result.get("blocked_by_safety") is True
        assert "1 item(s)" in result.get("error", "")
        assert "Lakehouse" in result.get("error", "")

    @patch("subprocess.run")
    def test_get_workspace_id_from_api(self, mock_run):
        """Test getting workspace ID from API response"""
        mock_run.return_value = Mock(
            stdout='{"id": "ws-abc-123", "displayName": "my-workspace"}',
            stderr="",
            returncode=0,
        )

        ws_id = self.fabric.get_workspace_id("my-workspace")

        assert ws_id == "ws-abc-123"

    @patch("subprocess.run")
    def test_get_workspace_id_cached(self, mock_run):
        """Test workspace ID cache hit avoids API call"""
        self.fabric._workspace_id_cache["cached-ws"] = "cached-id-999"

        ws_id = self.fabric.get_workspace_id("cached-ws")

        assert ws_id == "cached-id-999"
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_get_folder_id_found(self, mock_run):
        """Test getting folder ID when folder exists"""
        ws_response = Mock(stdout='{"id": "workspace-123"}', stderr="", returncode=0)
        folder_response = Mock(
            stdout='{"value": [{"id": "folder-789", "displayName": "Bronze"}]}',
            stderr="",
            returncode=0,
        )
        mock_run.side_effect = [ws_response, folder_response]

        folder_id = self.fabric.get_folder_id("test-ws", "Bronze", retries=1)

        assert folder_id == "folder-789"

    @patch("subprocess.run")
    def test_get_folder_id_not_found(self, mock_run):
        """Test getting folder ID when folder does not exist"""
        ws_response = Mock(stdout='{"id": "workspace-123"}', stderr="", returncode=0)
        folder_response = Mock(
            stdout='{"value": [{"id": "folder-789", "displayName": "Silver"}]}',
            stderr="",
            returncode=0,
        )
        mock_run.side_effect = [ws_response, folder_response]

        folder_id = self.fabric.get_folder_id("test-ws", "NonExistent", retries=1)

        assert folder_id is None

    @patch("subprocess.run")
    def test_create_notebook_without_file_path(self, mock_run):
        """Test notebook creation without file_path (empty notebook)"""
        workspace_response = Mock(
            stdout='{"id": "workspace-123"}', stderr="", returncode=0
        )
        create_response = Mock(
            stdout='{"id": "notebook-456", "displayName": "my-notebook"}',
            stderr="",
            returncode=0,
        )
        mock_run.side_effect = [workspace_response, create_response]

        result = self.fabric.create_notebook("test-ws", "my-notebook")

        assert result["success"] is True
        # Verify no definition payload for empty notebook
        create_call = mock_run.call_args_list[1]
        args = create_call[0][0]
        payload_idx = args.index("-i") + 1
        payload = json.loads(args[payload_idx])
        assert "definition" not in payload
        assert payload["type"] == "Notebook"

    @patch("subprocess.run")
    def test_create_notebook_with_py_file(self, mock_run):
        """Test notebook creation importing content from .py file"""
        import base64
        import tempfile

        workspace_response = Mock(
            stdout='{"id": "workspace-123"}', stderr="", returncode=0
        )
        create_response = Mock(
            stdout='{"id": "notebook-456", "displayName": "my-notebook"}',
            stderr="",
            returncode=0,
        )
        mock_run.side_effect = [workspace_response, create_response]

        # Create a temp .py file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("print('hello')")
            py_path = f.name

        try:
            result = self.fabric.create_notebook(
                "test-ws", "my-notebook", file_path=py_path
            )

            assert result["success"] is True
            # Verify definition payload contains base64 content
            create_call = mock_run.call_args_list[1]
            args = create_call[0][0]
            payload_idx = args.index("-i") + 1
            payload = json.loads(args[payload_idx])
            assert "definition" in payload
            assert payload["definition"]["format"] == "ipynb"
            assert len(payload["definition"]["parts"]) == 1
            part = payload["definition"]["parts"][0]
            assert part["payloadType"] == "InlineBase64"

            # Decode and verify notebook structure
            decoded = json.loads(base64.b64decode(part["payload"]).decode("utf-8"))
            assert decoded["nbformat"] == 4
            assert decoded["cells"][0]["source"] == "print('hello')"
        finally:
            import os

            os.unlink(py_path)

    @patch("subprocess.run")
    def test_create_notebook_with_ipynb_file(self, mock_run):
        """Test notebook creation importing content from .ipynb file"""
        import base64
        import tempfile

        workspace_response = Mock(
            stdout='{"id": "workspace-123"}', stderr="", returncode=0
        )
        create_response = Mock(stdout='{"id": "notebook-456"}', stderr="", returncode=0)
        mock_run.side_effect = [workspace_response, create_response]

        nb_content = json.dumps({"nbformat": 4, "cells": []})
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
            f.write(nb_content)
            nb_path = f.name

        try:
            result = self.fabric.create_notebook(
                "test-ws", "my-notebook", file_path=nb_path
            )

            assert result["success"] is True
            create_call = mock_run.call_args_list[1]
            args = create_call[0][0]
            payload_idx = args.index("-i") + 1
            payload = json.loads(args[payload_idx])
            decoded = base64.b64decode(
                payload["definition"]["parts"][0]["payload"]
            ).decode("utf-8")
            assert decoded == nb_content
        finally:
            import os

            os.unlink(nb_path)

    def test_read_notebook_definition_missing_file(self):
        """Test _read_notebook_definition with non-existent file"""
        result = self.fabric._read_notebook_definition("/nonexistent/path.py")
        assert result is None

    def test_read_notebook_definition_unsupported_extension(self):
        """Test _read_notebook_definition with unsupported extension"""
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("some content")
            txt_path = f.name

        try:
            result = self.fabric._read_notebook_definition(txt_path)
            assert result is None
        finally:
            import os

            os.unlink(txt_path)

    @patch("subprocess.run")
    def test_create_pipeline(self, mock_run):
        """Test pipeline creation via REST API"""
        workspace_response = Mock(
            stdout='{"id": "workspace-123"}', stderr="", returncode=0
        )
        create_response = Mock(
            stdout='{"id": "pipeline-456", "displayName": "etl-pipeline"}',
            stderr="",
            returncode=0,
        )
        mock_run.side_effect = [workspace_response, create_response]

        result = self.fabric.create_pipeline("test-ws", "etl-pipeline", "ETL job")

        assert result["success"] is True
        create_call = mock_run.call_args_list[1]
        args = create_call[0][0]
        payload_idx = args.index("-i") + 1
        payload = json.loads(args[payload_idx])
        assert payload["type"] == "DataPipeline"
        assert payload["displayName"] == "etl-pipeline"
        assert payload["description"] == "ETL job"

    @patch("subprocess.run")
    def test_create_warehouse(self, mock_run):
        """Test warehouse creation via REST API"""
        workspace_response = Mock(
            stdout='{"id": "workspace-123"}', stderr="", returncode=0
        )
        create_response = Mock(
            stdout='{"id": "wh-789", "displayName": "sales-warehouse"}',
            stderr="",
            returncode=0,
        )
        mock_run.side_effect = [workspace_response, create_response]

        result = self.fabric.create_warehouse("test-ws", "sales-warehouse")

        assert result["success"] is True
        create_call = mock_run.call_args_list[1]
        args = create_call[0][0]
        payload_idx = args.index("-i") + 1
        payload = json.loads(args[payload_idx])
        assert payload["type"] == "Warehouse"

    @patch("subprocess.run")
    def test_create_semantic_model(self, mock_run):
        """Test semantic model creation via REST API"""
        workspace_response = Mock(
            stdout='{"id": "workspace-123"}', stderr="", returncode=0
        )
        create_response = Mock(
            stdout='{"id": "sm-101", "displayName": "sales-model"}',
            stderr="",
            returncode=0,
        )
        mock_run.side_effect = [workspace_response, create_response]

        result = self.fabric.create_semantic_model(
            "test-ws", "sales-model", "Sales semantic model"
        )

        assert result["success"] is True
        create_call = mock_run.call_args_list[1]
        args = create_call[0][0]
        payload_idx = args.index("-i") + 1
        payload = json.loads(args[payload_idx])
        assert payload["type"] == "SemanticModel"
        assert payload["description"] == "Sales semantic model"

    @patch("subprocess.run")
    def test_create_item_generic(self, mock_run):
        """Test generic item creation (e.g., Eventstream, KQLDatabase)"""
        workspace_response = Mock(
            stdout='{"id": "workspace-123"}', stderr="", returncode=0
        )
        create_response = Mock(
            stdout='{"id": "es-202", "displayName": "iot-events"}',
            stderr="",
            returncode=0,
        )
        mock_run.side_effect = [workspace_response, create_response]

        result = self.fabric.create_item(
            "test-ws", "iot-events", "Eventstream", "IoT ingestion"
        )

        assert result["success"] is True
        create_call = mock_run.call_args_list[1]
        args = create_call[0][0]
        payload_idx = args.index("-i") + 1
        payload = json.loads(args[payload_idx])
        assert payload["type"] == "Eventstream"
        assert payload["displayName"] == "iot-events"
        assert payload["description"] == "IoT ingestion"

    @patch("subprocess.run")
    def test_add_workspace_principal_empty_id(self, mock_run):
        """Test that empty principal ID is silently skipped"""
        result = self.fabric.add_workspace_principal("test-ws", "", "Admin")

        assert result["success"] is True
        assert result.get("skipped") is True
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_add_workspace_principal_placeholder(self, mock_run):
        """Test that placeholder email principals are skipped"""
        result = self.fabric.add_workspace_principal(
            "test-ws", "user@your-company.com", "Member"
        )

        assert result["success"] is True
        assert result.get("skipped") is True
        mock_run.assert_not_called()

    @patch.dict("os.environ", {"AZURE_CLIENT_ID": "sp-client-id-123"})
    @patch("subprocess.run")
    def test_add_workspace_principal_deploying_sp_skipped(self, mock_run):
        """Test that deploying SP's own client ID is skipped"""
        result = self.fabric.add_workspace_principal(
            "test-ws", "sp-client-id-123", "Admin"
        )

        assert result["success"] is True
        assert result.get("skipped") is True
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_assign_to_domain(self, mock_run):
        """Test domain assignment"""
        mock_run.return_value = Mock(stdout="", stderr="", returncode=0)

        result = self.fabric.assign_to_domain("test-ws", "Sales")

        assert result["success"] is True
        args = mock_run.call_args[0][0]
        assert args[:2] == ["fab", "assign"]
        assert ".domains/Sales.Domain" in args
        assert "-W" in args
        assert "test-ws.Workspace" in args

    @patch("subprocess.run")
    def test_assign_to_domain_full_path(self, mock_run):
        """Test domain assignment with already-qualified domain name"""
        mock_run.return_value = Mock(stdout="", stderr="", returncode=0)

        result = self.fabric.assign_to_domain("test-ws", ".domains/Finance.Domain")

        assert result["success"] is True
        args = mock_run.call_args[0][0]
        # Should not double-prefix
        assert ".domains/Finance.Domain" in args
        assert ".domains/.domains/" not in " ".join(args)


if __name__ == "__main__":
    pytest.main([__file__])


class TestRetryUtilities:
    """Tests for retry utilities."""

    def test_is_retryable_error_rate_limit(self):
        """Test detection of rate limit errors."""
        from usf_fabric_cli.services.fabric_wrapper import is_retryable_error

        assert is_retryable_error("Rate limit exceeded") is True
        assert is_retryable_error("Error 429: Too Many Requests") is True

    def test_is_retryable_error_service_unavailable(self):
        """Test detection of service unavailable errors."""
        from usf_fabric_cli.services.fabric_wrapper import is_retryable_error

        assert is_retryable_error("503 Service Unavailable") is True
        assert is_retryable_error("Service temporarily unavailable") is True

    def test_is_retryable_error_connection_issues(self):
        """Test detection of connection errors."""
        from usf_fabric_cli.services.fabric_wrapper import is_retryable_error

        assert is_retryable_error("Connection reset by peer") is True
        assert is_retryable_error("Connection refused") is True
        assert is_retryable_error("Request timed out") is True

    def test_is_retryable_error_non_retryable(self):
        """Test that non-retryable errors return False."""
        from usf_fabric_cli.services.fabric_wrapper import is_retryable_error

        assert is_retryable_error("Invalid credentials") is False
        assert is_retryable_error("Permission denied") is False
        assert is_retryable_error("Resource not found") is False

    def test_calculate_backoff_exponential(self):
        """Test exponential backoff calculation."""
        import random

        from usf_fabric_cli.services.fabric_wrapper import calculate_backoff

        random.seed(42)

        # First attempt: ~1s
        delay0 = calculate_backoff(0, 1.0, 30.0)
        assert 0.75 <= delay0 <= 1.25  # 1s ± 25%

        # Second attempt: ~2s
        delay1 = calculate_backoff(1, 1.0, 30.0)
        assert 1.5 <= delay1 <= 2.5  # 2s ± 25%

        # Third attempt: ~4s
        delay2 = calculate_backoff(2, 1.0, 30.0)
        assert 3.0 <= delay2 <= 5.0  # 4s ± 25%

    def test_calculate_backoff_max_delay(self):
        """Test that backoff respects max delay."""
        from usf_fabric_cli.services.fabric_wrapper import calculate_backoff

        # Very high attempt number should still respect max_delay
        delay = calculate_backoff(10, 1.0, 30.0)
        assert delay <= 30.0 * 1.25  # max_delay + jitter

    def test_retry_decorator_success_first_try(self):
        """Test retry decorator when function succeeds on first try."""
        from usf_fabric_cli.services.fabric_wrapper import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=3)
        def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_function()

        assert result == "success"
        assert call_count == 1

    def test_retry_decorator_success_after_retry(self):
        """Test retry decorator when function succeeds after retry."""
        from usf_fabric_cli.services.fabric_wrapper import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("503 Service Unavailable")
            return "success"

        result = flaky_function()

        assert result == "success"
        assert call_count == 2

    def test_retry_decorator_exhausts_retries(self):
        """Test retry decorator when all retries are exhausted."""
        from usf_fabric_cli.services.fabric_wrapper import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("429 Rate limited")

        with pytest.raises(Exception) as exc_info:
            always_fails()

        assert "429" in str(exc_info.value)
        assert call_count == 3  # Initial + 2 retries

    def test_retry_decorator_non_retryable_error(self):
        """Test that non-retryable errors are not retried."""
        from usf_fabric_cli.services.fabric_wrapper import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def permission_denied():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("Permission denied")

        with pytest.raises(Exception) as exc_info:
            permission_denied()

        assert "Permission denied" in str(exc_info.value)
        assert call_count == 1  # No retries for non-retryable errors


# ═══════════════════════════════════════════════════════════════════
# Coverage Improvement: _validate_cli_version
# ═══════════════════════════════════════════════════════════════════


class TestValidateCliVersion:
    """Test _validate_cli_version paths to improve coverage."""

    def _make_wrapper(self):
        """Create wrapper with version validation disabled."""
        telemetry = MagicMock()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="Fabric CLI 1.0.0", returncode=0)
            wrapper = FabricCLIWrapper(
                "fake-token", telemetry_client=telemetry, validate_version=False
            )
        return wrapper

    @patch("subprocess.run")
    def test_successful_version_parse(self, mock_run):
        """Test parsing a valid version string."""
        mock_run.return_value = Mock(stdout="Fabric CLI 1.3.1", returncode=0)
        wrapper = self._make_wrapper()
        wrapper._validate_cli_version()
        assert wrapper.cli_version == "1.3.1"

    @patch("subprocess.run")
    def test_version_below_minimum(self, mock_run):
        """Test warning for version below minimum."""
        mock_run.return_value = Mock(stdout="Fabric CLI 0.0.1", returncode=0)
        wrapper = self._make_wrapper()
        wrapper._validate_cli_version()
        assert wrapper.cli_version == "0.0.1"

    @patch("subprocess.run")
    def test_file_not_found_raises(self, mock_run):
        """Test FileNotFoundError raises FabricCLINotFoundError."""
        from usf_fabric_cli.exceptions import FabricCLINotFoundError

        mock_run.side_effect = FileNotFoundError("fab not found")
        wrapper = self._make_wrapper()

        with pytest.raises(FabricCLINotFoundError):
            wrapper._validate_cli_version()

    @patch("subprocess.run")
    def test_timeout_sets_unknown(self, mock_run):
        """Test TimeoutExpired sets version to 'unknown'."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="fab", timeout=5)
        wrapper = self._make_wrapper()
        wrapper._validate_cli_version()
        assert wrapper.cli_version == "unknown"

    @patch("subprocess.run")
    def test_os_error_sets_unknown(self, mock_run):
        """Test OSError sets version to 'unknown'."""
        mock_run.side_effect = OSError("some error")
        wrapper = self._make_wrapper()
        wrapper._validate_cli_version()
        assert wrapper.cli_version == "unknown"

    @patch("subprocess.run")
    def test_unparseable_version_output(self, mock_run):
        """Test that unparseable version output sets 'unknown'."""
        mock_run.return_value = Mock(stdout="some random output", returncode=0)
        wrapper = self._make_wrapper()
        wrapper._validate_cli_version()
        assert wrapper.cli_version == "unknown"


# ═══════════════════════════════════════════════════════════════════
# Coverage Improvement: _parse_git_url
# ═══════════════════════════════════════════════════════════════════


class TestParseGitUrl:
    """Test _parse_git_url for all URL formats (pure function)."""

    def setup_method(self):
        telemetry = MagicMock()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="Fabric CLI 1.0.0", returncode=0)
            self.fabric = FabricCLIWrapper(
                "fake-token", telemetry_client=telemetry, validate_version=False
            )

    def test_ado_format_1(self):
        """Test Azure DevOps URL format: dev.azure.com/{org}/{project}/_git/{repo}"""
        url = "https://dev.azure.com/MyOrg/MyProject/_git/MyRepo"
        result = self.fabric._parse_git_url(url)
        assert result["gitProviderType"] == "AzureDevOps"
        assert result["organizationName"] == "MyOrg"
        assert result["projectName"] == "MyProject"
        assert result["repositoryName"] == "MyRepo"

    def test_ado_format_2(self):
        """Test Azure DevOps URL format: {org}.visualstudio.com/{project}/_git/{repo}"""
        url = "https://MyOrg.visualstudio.com/MyProject/_git/MyRepo"
        result = self.fabric._parse_git_url(url)
        assert result["gitProviderType"] == "AzureDevOps"
        assert result["organizationName"] == "MyOrg"
        assert result["projectName"] == "MyProject"
        assert result["repositoryName"] == "MyRepo"

    def test_github_format(self):
        """Test GitHub URL: https://github.com/{owner}/{repo}"""
        url = "https://github.com/my-org/my-repo"
        result = self.fabric._parse_git_url(url)
        assert result["gitProviderType"] == "GitHub"
        assert result["ownerName"] == "my-org"
        assert result["repositoryName"] == "my-repo"

    def test_github_format_with_git_suffix(self):
        """Test GitHub URL with .git suffix."""
        url = "https://github.com/my-org/my-repo.git"
        result = self.fabric._parse_git_url(url)
        assert result["gitProviderType"] == "GitHub"
        assert result["ownerName"] == "my-org"
        assert result["repositoryName"] == "my-repo"

    def test_unrecognized_url_returns_empty(self):
        """Test that unrecognized URLs return empty dict."""
        result = self.fabric._parse_git_url("https://gitlab.com/foo/bar")
        assert result == {}

    def test_empty_string_returns_empty(self):
        """Test that empty string returns empty dict."""
        result = self.fabric._parse_git_url("")
        assert result == {}


# ═══════════════════════════════════════════════════════════════════
# Coverage Improvement: _item_exists
# ═══════════════════════════════════════════════════════════════════


class TestItemExists:
    """Test _item_exists method."""

    def setup_method(self):
        telemetry = MagicMock()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="Fabric CLI 1.0.0", returncode=0)
            self.fabric = FabricCLIWrapper(
                "fake-token", telemetry_client=telemetry, validate_version=False
            )

    @patch("subprocess.run")
    def test_item_exists_true(self, mock_run):
        """Test _item_exists returns True when item exists."""
        mock_run.return_value = Mock(stdout="true", stderr="", returncode=0)
        assert self.fabric._item_exists("test-workspace.Workspace") is True

    @patch("subprocess.run")
    def test_item_exists_false(self, mock_run):
        """Test _item_exists returns False when item does not exist."""
        mock_run.return_value = Mock(stdout="false", stderr="", returncode=0)
        assert self.fabric._item_exists("test-workspace.Workspace") is False

    @patch("subprocess.run")
    def test_item_exists_failure_returns_false(self, mock_run):
        """Test _item_exists returns False on error."""
        mock_run.side_effect = subprocess.SubprocessError("error")
        assert self.fabric._item_exists("test-workspace.Workspace") is False


# ═══════════════════════════════════════════════════════════════════
# Coverage Improvement: create_folder and get_workspace_item_summary
# ═══════════════════════════════════════════════════════════════════


class TestCreateFolderAndSummary:
    """Test create_folder and get_workspace_item_summary."""

    def setup_method(self):
        telemetry = MagicMock()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="Fabric CLI 1.0.0", returncode=0)
            self.fabric = FabricCLIWrapper(
                "fake-token", telemetry_client=telemetry, validate_version=False
            )

    @patch.object(FabricCLIWrapper, "get_workspace_id", return_value="ws-id-123")
    @patch.object(FabricCLIWrapper, "get_folder_id", return_value="folder-id-456")
    def test_create_folder_already_exists(self, mock_folder_id, mock_ws_id):
        """Test create_folder returns success when folder already exists."""
        result = self.fabric.create_folder("test-workspace", "Bronze")
        assert result["success"] is True
        assert result["data"] == "already_exists"
        assert result["reused"] is True
        assert result["id"] == "folder-id-456"

    @patch.object(FabricCLIWrapper, "get_workspace_id", return_value="ws-id-123")
    @patch.object(FabricCLIWrapper, "get_folder_id", return_value=None)
    @patch.object(
        FabricCLIWrapper,
        "_execute_command",
        return_value={
            "success": True,
            "data": {"id": "new-folder-id", "displayName": "Bronze"},
        },
    )
    def test_create_folder_new(self, mock_exec, mock_folder_id, mock_ws_id):
        """Test create_folder creates a new folder via API."""
        result = self.fabric.create_folder("test-workspace", "Bronze")
        assert result["success"] is True

    @patch.object(
        FabricCLIWrapper,
        "list_workspace_items_api",
        return_value=[
            {"type": "Lakehouse", "displayName": "lh1"},
            {"type": "Lakehouse", "displayName": "lh2"},
            {"type": "Notebook", "displayName": "nb1"},
            {"type": "Pipeline", "displayName": "pl1"},
        ],
    )
    def test_get_workspace_item_summary(self, mock_items):
        """Test get_workspace_item_summary aggregates by type."""
        result = self.fabric.get_workspace_item_summary("test-workspace")
        assert result["item_count"] == 4
        assert result["has_items"] is True
        assert result["items_by_type"]["Lakehouse"] == 2
        assert result["items_by_type"]["Notebook"] == 1
        assert result["items_by_type"]["Pipeline"] == 1
        assert len(result["items"]) == 4


# ═══════════════════════════════════════════════════════════════════
# Coverage Improvement: list_workspace_items_api (pagination)
# ═══════════════════════════════════════════════════════════════════


class TestListWorkspaceItemsApi:
    """Test list_workspace_items_api with pagination scenarios."""

    def setup_method(self):
        telemetry = MagicMock()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="Fabric CLI 1.0.0", returncode=0)
            self.fabric = FabricCLIWrapper(
                "fake-token", telemetry_client=telemetry, validate_version=False
            )

    @patch.object(FabricCLIWrapper, "get_workspace_id", return_value="ws-id-123")
    @patch.object(FabricCLIWrapper, "_execute_command")
    def test_single_page(self, mock_exec, mock_ws_id):
        """Test listing items with a single page (no continuation)."""
        mock_exec.return_value = {
            "success": True,
            "data": {
                "value": [
                    {"id": "1", "displayName": "item1", "type": "Lakehouse"},
                    {"id": "2", "displayName": "item2", "type": "Notebook"},
                ],
            },
        }
        items = self.fabric.list_workspace_items_api("test-workspace")
        assert len(items) == 2
        assert items[0]["displayName"] == "item1"

    @patch.object(FabricCLIWrapper, "get_workspace_id", return_value="ws-id-123")
    @patch.object(FabricCLIWrapper, "_execute_command")
    def test_with_continuation_token(self, mock_exec, mock_ws_id):
        """Test pagination via continuationToken."""
        page1 = {
            "success": True,
            "data": {
                "value": [{"id": "1", "displayName": "item1", "type": "Lakehouse"}],
                "continuationToken": "token-abc",
            },
        }
        page2 = {
            "success": True,
            "data": {
                "value": [{"id": "2", "displayName": "item2", "type": "Notebook"}],
            },
        }
        mock_exec.side_effect = [page1, page2]
        items = self.fabric.list_workspace_items_api("test-workspace")
        assert len(items) == 2
        assert mock_exec.call_count == 2

    @patch.object(FabricCLIWrapper, "get_workspace_id", return_value="ws-id-123")
    @patch.object(FabricCLIWrapper, "_execute_command")
    def test_with_continuation_uri(self, mock_exec, mock_ws_id):
        """Test pagination via continuationUri (full URL)."""
        page1 = {
            "success": True,
            "data": {
                "value": [{"id": "1", "displayName": "item1", "type": "Lakehouse"}],
                "continuationUri": (
                    "https://api.fabric.microsoft.com/v1/"
                    "workspaces/ws-id-123/items?continuationToken=xyz"
                ),
            },
        }
        page2 = {
            "success": True,
            "data": {
                "value": [{"id": "2", "displayName": "item2", "type": "Notebook"}],
            },
        }
        mock_exec.side_effect = [page1, page2]
        items = self.fabric.list_workspace_items_api("test-workspace")
        assert len(items) == 2

    @patch.object(FabricCLIWrapper, "get_workspace_id", return_value=None)
    def test_no_workspace_id_returns_empty(self, mock_ws_id):
        """Test returns empty list when workspace ID cannot be resolved."""
        items = self.fabric.list_workspace_items_api("unknown-workspace")
        assert items == []

    @patch.object(FabricCLIWrapper, "get_workspace_id", return_value="ws-id-123")
    @patch.object(FabricCLIWrapper, "_execute_command")
    def test_api_failure_returns_partial(self, mock_exec, mock_ws_id):
        """Test returns empty list on API failure."""
        mock_exec.return_value = {"success": False, "error": "API error"}
        items = self.fabric.list_workspace_items_api("test-workspace")
        assert items == []

    @patch.object(FabricCLIWrapper, "get_workspace_id", return_value="ws-id-123")
    @patch.object(FabricCLIWrapper, "_execute_command")
    def test_string_data_parsed_as_json(self, mock_exec, mock_ws_id):
        """Test that string response data is parsed as JSON."""
        mock_exec.return_value = {
            "success": True,
            "data": json.dumps(
                {"value": [{"id": "1", "displayName": "item1", "type": "Lakehouse"}]}
            ),
        }
        items = self.fabric.list_workspace_items_api("test-workspace")
        assert len(items) == 1

    @patch.object(FabricCLIWrapper, "get_workspace_id", return_value="ws-id-123")
    @patch.object(FabricCLIWrapper, "_execute_command")
    def test_nested_text_field(self, mock_exec, mock_ws_id):
        """Test that nested 'text' field is unwrapped."""
        mock_exec.return_value = {
            "success": True,
            "data": {
                "text": {
                    "value": [{"id": "1", "displayName": "item1", "type": "Lakehouse"}],
                }
            },
        }
        items = self.fabric.list_workspace_items_api("test-workspace")
        assert len(items) == 1


# ═══════════════════════════════════════════════════════════════════
# Coverage Improvement: wait_for_operation
# ═══════════════════════════════════════════════════════════════════


class TestWaitForOperation:
    """Test wait_for_operation polling logic."""

    def setup_method(self):
        telemetry = MagicMock()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="Fabric CLI 1.0.0", returncode=0)
            self.fabric = FabricCLIWrapper(
                "fake-token", telemetry_client=telemetry, validate_version=False
            )

    @patch("time.sleep")
    @patch.object(FabricCLIWrapper, "_execute_command")
    def test_succeeds_immediately(self, mock_exec, mock_sleep):
        """Test operation succeeds on first poll."""
        mock_exec.return_value = {
            "success": True,
            "data": {"status": "Succeeded"},
        }
        result = self.fabric.wait_for_operation("op-123")
        assert result is True

    @patch("time.sleep")
    @patch.object(FabricCLIWrapper, "_execute_command")
    def test_completed_status(self, mock_exec, mock_sleep):
        """Test operation returns True for 'Completed' status."""
        mock_exec.return_value = {
            "success": True,
            "data": {"status": "Completed"},
        }
        result = self.fabric.wait_for_operation("op-123")
        assert result is True

    @patch("time.sleep")
    @patch.object(FabricCLIWrapper, "_execute_command")
    def test_fails(self, mock_exec, mock_sleep):
        """Test operation returns False for 'Failed' status."""
        mock_exec.return_value = {
            "success": True,
            "data": {"status": "Failed"},
        }
        result = self.fabric.wait_for_operation("op-123")
        assert result is False

    @patch("time.sleep")
    @patch.object(FabricCLIWrapper, "_execute_command")
    def test_cancelled(self, mock_exec, mock_sleep):
        """Test operation returns False for 'Cancelled' status."""
        mock_exec.return_value = {
            "success": True,
            "data": {"status": "Cancelled"},
        }
        result = self.fabric.wait_for_operation("op-123")
        assert result is False

    @patch("usf_fabric_cli.services.fabric_wrapper.time")
    @patch.object(FabricCLIWrapper, "_execute_command")
    def test_timeout(self, mock_exec, mock_time_mod):
        """Test operation times out after max_wait_seconds."""
        # time.time() is called for start and for each loop check
        mock_time_mod.time.side_effect = [0, 100, 200, 400]
        mock_time_mod.sleep = MagicMock()
        mock_exec.return_value = {
            "success": True,
            "data": {"status": "Running"},
        }
        result = self.fabric.wait_for_operation("op-123", max_wait_seconds=300)
        assert result is False

    @patch("usf_fabric_cli.services.fabric_wrapper.time")
    @patch.object(FabricCLIWrapper, "_execute_command")
    def test_succeeds_after_polling(self, mock_exec, mock_time_mod):
        """Test operation succeeds after a few polling cycles."""
        mock_time_mod.time.side_effect = [0, 10, 20, 30]
        mock_time_mod.sleep = MagicMock()
        mock_exec.side_effect = [
            {"success": True, "data": {"status": "Running"}},
            {"success": True, "data": {"status": "Running"}},
            {"success": True, "data": {"status": "Succeeded"}},
        ]
        result = self.fabric.wait_for_operation("op-123", max_wait_seconds=300)
        assert result is True


# ═══════════════════════════════════════════════════════════════════
# Coverage Improvement: move_item_to_folder
# ═══════════════════════════════════════════════════════════════════


class TestMoveItemToFolder:
    """Test move_item_to_folder method."""

    def setup_method(self):
        telemetry = MagicMock()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="Fabric CLI 1.0.0", returncode=0)
            self.fabric = FabricCLIWrapper(
                "fake-token", telemetry_client=telemetry, validate_version=False
            )

    @patch.object(FabricCLIWrapper, "get_workspace_id", return_value="ws-id-123")
    @patch.object(FabricCLIWrapper, "_execute_command", return_value={"success": True})
    def test_move_success(self, mock_exec, mock_ws_id):
        """Test successful item move."""
        result = self.fabric.move_item_to_folder(
            "test-workspace", "item-id-1", "folder-id-1", "MyNotebook"
        )
        assert result["success"] is True
        # Verify PATCH command was constructed correctly
        call_args = mock_exec.call_args[0][0]
        assert "patch" in call_args
        assert "items/item-id-1" in call_args[1]

    @patch.object(FabricCLIWrapper, "get_workspace_id", return_value=None)
    def test_move_no_workspace_id(self, mock_ws_id):
        """Test move fails when workspace ID cannot be resolved."""
        result = self.fabric.move_item_to_folder(
            "unknown-ws", "item-id-1", "folder-id-1"
        )
        assert result["success"] is False


# ═══════════════════════════════════════════════════════════════════
# Coverage Improvement: organize_items_into_folders
# ═══════════════════════════════════════════════════════════════════


class TestOrganizeItemsIntoFolders:
    """Test organize_items_into_folders method."""

    def setup_method(self):
        telemetry = MagicMock()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="Fabric CLI 1.0.0", returncode=0)
            self.fabric = FabricCLIWrapper(
                "fake-token", telemetry_client=telemetry, validate_version=False
            )

    def test_empty_rules(self):
        """Test with empty folder_rules returns zero counts."""
        result = self.fabric.organize_items_into_folders("test-ws", [])
        assert result["moved"] == 0
        assert result["skipped"] == 0
        assert result["failed"] == 0

    @patch.object(FabricCLIWrapper, "list_workspace_items_api", return_value=[])
    def test_no_items_in_workspace(self, mock_items):
        """Test with no items to organize."""
        rules = [{"type": "Notebook", "folder": "Notebooks"}]
        result = self.fabric.organize_items_into_folders("test-ws", rules)
        assert result["moved"] == 0

    @patch.object(
        FabricCLIWrapper,
        "move_item_to_folder",
        return_value={"success": True},
    )
    @patch.object(
        FabricCLIWrapper,
        "_execute_command",
        return_value={
            "success": True,
            "data": {
                "value": [
                    {"id": "folder-nb-id", "displayName": "Notebooks"},
                ]
            },
        },
    )
    @patch.object(FabricCLIWrapper, "get_workspace_id", return_value="ws-id-123")
    @patch.object(
        FabricCLIWrapper,
        "list_workspace_items_api",
        return_value=[
            {
                "id": "nb-1",
                "displayName": "MyNotebook",
                "type": "Notebook",
            },
            {
                "id": "lh-1",
                "displayName": "MyLakehouse",
                "type": "Lakehouse",
                "folderId": "existing-folder",
            },
        ],
    )
    def test_moves_root_items_skips_existing(
        self, mock_items, mock_ws_id, mock_exec, mock_move
    ):
        """Test moves root items and skips items already in folders."""
        rules = [{"type": "Notebook", "folder": "Notebooks"}]
        result = self.fabric.organize_items_into_folders("test-ws", rules)
        assert result["moved"] == 1
        assert mock_move.call_count == 1

    @patch.object(FabricCLIWrapper, "get_workspace_id", return_value="ws-id-123")
    @patch.object(
        FabricCLIWrapper,
        "_execute_command",
        return_value={
            "success": True,
            "data": {"value": []},  # No folders exist
        },
    )
    @patch.object(
        FabricCLIWrapper,
        "list_workspace_items_api",
        return_value=[
            {"id": "nb-1", "displayName": "MyNotebook", "type": "Notebook"},
        ],
    )
    def test_folder_not_found_increments_failed(
        self, mock_items, mock_exec, mock_ws_id
    ):
        """Test rule with missing folder increments failed count."""
        rules = [{"type": "Notebook", "folder": "NonexistentFolder"}]
        result = self.fabric.organize_items_into_folders("test-ws", rules)
        assert result["failed"] == 1
        assert any(d["status"] == "folder_not_found" for d in result["details"])


# ═══════════════════════════════════════════════════════════════════
# Coverage Improvement: list_workspace_items (CLI)
# ═══════════════════════════════════════════════════════════════════


class TestListWorkspaceItems:
    """Test list_workspace_items (CLI-based)."""

    def setup_method(self):
        telemetry = MagicMock()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="Fabric CLI 1.0.0", returncode=0)
            self.fabric = FabricCLIWrapper(
                "fake-token", telemetry_client=telemetry, validate_version=False
            )

    @patch.object(
        FabricCLIWrapper,
        "_execute_command",
        return_value={"success": True, "data": "item1\nitem2\n"},
    )
    def test_list_workspace_items_success(self, mock_exec):
        """Test successful list_workspace_items call."""
        result = self.fabric.list_workspace_items("test-workspace")
        assert result["success"] is True
        # Verify the command uses the correct workspace path
        call_args = mock_exec.call_args[0][0]
        assert "ls" in call_args
        assert "test-workspace.Workspace" in call_args


# ═══════════════════════════════════════════════════════════════════
# Coverage Improvement: connect_git
# ═══════════════════════════════════════════════════════════════════


class TestConnectGit:
    """Test connect_git method."""

    def setup_method(self):
        telemetry = MagicMock()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="Fabric CLI 1.0.0", returncode=0)
            self.fabric = FabricCLIWrapper(
                "fake-token", telemetry_client=telemetry, validate_version=False
            )

    @patch.object(FabricCLIWrapper, "_execute_command", return_value={"success": True})
    @patch.object(
        FabricCLIWrapper,
        "get_workspace",
        return_value={"success": True, "data": {"id": "ws-id-123"}},
    )
    def test_connect_git_github(self, mock_get_ws, mock_exec):
        """Test connecting workspace to GitHub repo."""
        result = self.fabric.connect_git(
            "test-workspace",
            "https://github.com/my-org/my-repo",
            branch="main",
        )
        assert result["success"] is True

    @patch.object(
        FabricCLIWrapper,
        "get_workspace",
        return_value={"success": True, "data": {"id": "ws-id-123"}},
    )
    def test_connect_git_invalid_url(self, mock_get_ws):
        """Test connecting with an unrecognized Git URL fails."""
        result = self.fabric.connect_git(
            "test-workspace",
            "https://gitlab.com/foo/bar",
        )
        assert result["success"] is False
        assert "Could not parse" in result.get("error", "")

    @patch.object(
        FabricCLIWrapper,
        "get_workspace",
        return_value={"success": False, "data": None},
    )
    def test_connect_git_workspace_not_found(self, mock_get_ws):
        """Test error when workspace is not found."""
        result = self.fabric.connect_git(
            "nonexistent-workspace",
            "https://github.com/my-org/my-repo",
        )
        assert result["success"] is False
