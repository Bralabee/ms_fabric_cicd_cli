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


if __name__ == "__main__":
    pytest.main([__file__])


class TestRetryUtilities:
    """Tests for retry utilities."""

    def test_is_retryable_error_rate_limit(self):
        """Test detection of rate limit errors."""
        from core.fabric_wrapper import is_retryable_error

        assert is_retryable_error("Rate limit exceeded") is True
        assert is_retryable_error("Error 429: Too Many Requests") is True

    def test_is_retryable_error_service_unavailable(self):
        """Test detection of service unavailable errors."""
        from core.fabric_wrapper import is_retryable_error

        assert is_retryable_error("503 Service Unavailable") is True
        assert is_retryable_error("Service temporarily unavailable") is True

    def test_is_retryable_error_connection_issues(self):
        """Test detection of connection errors."""
        from core.fabric_wrapper import is_retryable_error

        assert is_retryable_error("Connection reset by peer") is True
        assert is_retryable_error("Connection refused") is True
        assert is_retryable_error("Request timed out") is True

    def test_is_retryable_error_non_retryable(self):
        """Test that non-retryable errors return False."""
        from core.fabric_wrapper import is_retryable_error

        assert is_retryable_error("Invalid credentials") is False
        assert is_retryable_error("Permission denied") is False
        assert is_retryable_error("Resource not found") is False

    def test_calculate_backoff_exponential(self):
        """Test exponential backoff calculation."""
        from core.fabric_wrapper import calculate_backoff
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
        from core.fabric_wrapper import calculate_backoff

        # Very high attempt number should still respect max_delay
        delay = calculate_backoff(10, 1.0, 30.0)
        assert delay <= 30.0 * 1.25  # max_delay + jitter

    def test_retry_decorator_success_first_try(self):
        """Test retry decorator when function succeeds on first try."""
        from core.fabric_wrapper import retry_with_backoff

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
        from core.fabric_wrapper import retry_with_backoff

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
        from core.fabric_wrapper import retry_with_backoff

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
        from core.fabric_wrapper import retry_with_backoff

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
