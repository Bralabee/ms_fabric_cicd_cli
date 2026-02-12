"""
Unit tests for Fabric CLI wrapper
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json

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
        ws_response = Mock(
            stdout='{"id": "workspace-123"}', stderr="", returncode=0
        )
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
        ws_response = Mock(
            stdout='{"id": "workspace-123"}', stderr="", returncode=0
        )
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
        import tempfile
        import base64

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
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
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
            decoded = json.loads(
                base64.b64decode(part["payload"]).decode("utf-8")
            )
            assert decoded["nbformat"] == 4
            assert decoded["cells"][0]["source"] == "print('hello')"
        finally:
            import os

            os.unlink(py_path)

    @patch("subprocess.run")
    def test_create_notebook_with_ipynb_file(self, mock_run):
        """Test notebook creation importing content from .ipynb file"""
        import tempfile
        import base64

        workspace_response = Mock(
            stdout='{"id": "workspace-123"}', stderr="", returncode=0
        )
        create_response = Mock(
            stdout='{"id": "notebook-456"}', stderr="", returncode=0
        )
        mock_run.side_effect = [workspace_response, create_response]

        nb_content = json.dumps({"nbformat": 4, "cells": []})
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ipynb", delete=False
        ) as f:
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

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
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
        from usf_fabric_cli.services.fabric_wrapper import calculate_backoff
        import random

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
                raise Exception("503 Service Unavailable")
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
            raise Exception("429 Rate limited")

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
            raise Exception("Permission denied")

        with pytest.raises(Exception) as exc_info:
            permission_denied()

        assert "Permission denied" in str(exc_info.value)
        assert call_count == 1  # No retries for non-retryable errors
