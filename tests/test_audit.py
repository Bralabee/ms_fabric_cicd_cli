"""
Tests for audit.py - Compliance audit logging.

Tests verify:
- JSONL log file creation
- Operation logging format
- All logging methods work correctly
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from core.audit import AuditLogger


class TestAuditLogger:
    """Tests for AuditLogger class."""

    @pytest.fixture
    def test_log_dir(self, tmp_path):
        """Create a unique test directory for logs."""
        log_dir = tmp_path / "test_audit_logs"
        log_dir.mkdir(exist_ok=True)
        yield str(log_dir)
        # Cleanup handled by tmp_path fixture

    @pytest.fixture
    def audit_logger(self, test_log_dir):
        """Create an AuditLogger instance with test directory."""
        # Create a unique logger name to avoid handler accumulation
        import logging

        logger_name = f"fabric_audit_test_{id(self)}"

        logger = AuditLogger(log_directory=test_log_dir)
        # Override the logger to use a unique instance
        logger.logger = logging.getLogger(logger_name)
        logger.logger.handlers = []  # Clear any existing handlers
        handler = logging.FileHandler(logger.log_file)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)

        yield logger

        # Close handlers to release file handles
        for h in logger.logger.handlers[:]:
            h.close()
            logger.logger.removeHandler(h)

    def _read_log(self, audit_logger):
        """Flush and read log file."""
        for handler in audit_logger.logger.handlers:
            handler.flush()
        if audit_logger.log_file.exists():
            with open(audit_logger.log_file, "r") as f:
                return f.readlines()
        return []

    def test_init_creates_log_directory(self, tmp_path):
        """Test that AuditLogger creates the log directory if it already exists."""
        log_dir = tmp_path / "audit_logs"
        logger = AuditLogger(log_directory=str(log_dir))

        assert log_dir.exists()
        assert logger.log_directory == log_dir

    def test_log_file_has_date_suffix(self, audit_logger):
        """Test that log file name includes today's date."""
        expected_date = datetime.now().strftime("%Y-%m-%d")
        assert expected_date in str(audit_logger.log_file)
        assert str(audit_logger.log_file).endswith(".jsonl")

    def test_log_operation_writes_jsonl(self, audit_logger):
        """Test that log_operation writes valid JSONL."""
        audit_logger.log_operation(
            operation="test_operation",
            workspace_id="ws-123",
            workspace_name="test-workspace",
            details={"key": "value"},
            success=True,
        )

        lines = self._read_log(audit_logger)
        assert len(lines) >= 1

        record = json.loads(lines[-1])
        assert record["operation"] == "test_operation"
        assert record["workspace_id"] == "ws-123"
        assert record["workspace_name"] == "test-workspace"
        assert record["success"] is True
        assert record["details"]["key"] == "value"
        assert "timestamp" in record

    def test_log_operation_with_error(self, audit_logger):
        """Test logging a failed operation with error message."""
        audit_logger.log_operation(
            operation="failed_operation", success=False, error="Something went wrong"
        )

        lines = self._read_log(audit_logger)
        record = json.loads(lines[-1])

        assert record["success"] is False
        assert record["error"] == "Something went wrong"

    def test_log_workspace_creation(self, audit_logger):
        """Test workspace creation logging."""
        audit_logger.log_workspace_creation(
            workspace_name="my-workspace", workspace_id="ws-456", capacity_id="cap-789"
        )

        lines = self._read_log(audit_logger)
        record = json.loads(lines[-1])

        assert record["operation"] == "workspace_create"
        assert record["workspace_name"] == "my-workspace"
        assert record["details"]["capacity_id"] == "cap-789"

    def test_log_item_creation(self, audit_logger):
        """Test item creation logging."""
        audit_logger.log_item_creation(
            item_type="Lakehouse",
            item_name="raw_data",
            workspace_id="ws-123",
            workspace_name="test-ws",
            folder_name="Bronze",
        )

        lines = self._read_log(audit_logger)
        record = json.loads(lines[-1])

        assert record["operation"] == "item_create"
        assert record["details"]["item_type"] == "Lakehouse"
        assert record["details"]["item_name"] == "raw_data"
        assert record["details"]["folder_name"] == "Bronze"

    def test_log_item_creation_without_folder(self, audit_logger):
        """Test item creation without folder."""
        audit_logger.log_item_creation(
            item_type="Warehouse",
            item_name="analytics_dw",
            workspace_id="ws-123",
            workspace_name="test-ws",
        )

        lines = self._read_log(audit_logger)
        record = json.loads(lines[-1])

        assert record["operation"] == "item_create"
        assert "folder_name" not in record["details"]

    def test_log_principal_assignment(self, audit_logger):
        """Test principal assignment logging."""
        audit_logger.log_principal_assignment(
            principal_id="user@example.com",
            role="Admin",
            workspace_id="ws-123",
            workspace_name="test-ws",
        )

        lines = self._read_log(audit_logger)
        record = json.loads(lines[-1])

        assert record["operation"] == "principal_assign"
        assert record["details"]["principal_id"] == "user@example.com"
        assert record["details"]["role"] == "Admin"

    def test_log_git_connection(self, audit_logger):
        """Test Git connection logging."""
        audit_logger.log_git_connection(
            git_repo="https://github.com/org/repo",
            branch="main",
            workspace_id="ws-123",
            workspace_name="test-ws",
        )

        lines = self._read_log(audit_logger)
        record = json.loads(lines[-1])

        assert record["operation"] == "git_connect"
        assert record["details"]["git_repo"] == "https://github.com/org/repo"
        assert record["details"]["branch"] == "main"

    def test_log_deployment_start(self, audit_logger):
        """Test deployment start logging."""
        audit_logger.log_deployment_start(
            config_file="config/test.yaml", environment="dev", branch="feature/test"
        )

        lines = self._read_log(audit_logger)
        record = json.loads(lines[-1])

        assert record["operation"] == "deployment_start"
        assert record["details"]["config_file"] == "config/test.yaml"
        assert record["details"]["environment"] == "dev"
        assert record["details"]["branch"] == "feature/test"

    def test_log_deployment_start_without_branch(self, audit_logger):
        """Test deployment start without branch."""
        audit_logger.log_deployment_start(
            config_file="config/test.yaml", environment="prod"
        )

        lines = self._read_log(audit_logger)
        record = json.loads(lines[-1])

        assert record["operation"] == "deployment_start"
        assert "branch" not in record["details"]

    def test_log_deployment_complete(self, audit_logger):
        """Test deployment completion logging."""
        audit_logger.log_deployment_complete(
            workspace_name="test-ws",
            workspace_id="ws-123",
            items_created=5,
            duration_seconds=30.567,
        )

        lines = self._read_log(audit_logger)
        record = json.loads(lines[-1])

        assert record["operation"] == "deployment_complete"
        assert record["details"]["items_created"] == 5
        assert record["details"]["duration_seconds"] == 30.57  # Rounded

    def test_multiple_operations_logged(self, audit_logger):
        """Test that multiple operations create multiple lines."""
        audit_logger.log_operation(operation="op1")
        audit_logger.log_operation(operation="op2")
        audit_logger.log_operation(operation="op3")

        lines = self._read_log(audit_logger)

        # Should have at least 3 lines
        assert len(lines) >= 3

        # Last 3 should be our operations
        ops = [json.loads(line)["operation"] for line in lines[-3:]]
        assert ops == ["op1", "op2", "op3"]

    def test_user_field_present(self, audit_logger):
        """Test that user field is present in log record."""
        audit_logger.log_operation(operation="test")

        lines = self._read_log(audit_logger)
        record = json.loads(lines[-1])

        # Should have a user field (either from env or 'unknown')
        assert "user" in record

    def test_timestamp_format(self, audit_logger):
        """Test that timestamp is in ISO format with Z suffix."""
        audit_logger.log_operation(operation="test")

        lines = self._read_log(audit_logger)
        record = json.loads(lines[-1])

        assert record["timestamp"].endswith("Z")
        # Should be parseable as ISO format
        datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))

    def test_get_audit_summary(self, audit_logger):
        """Test audit summary method."""
        summary = audit_logger.get_audit_summary(days=7)

        assert "audit_log_file" in summary
        assert "format" in summary
        assert summary["format"] == "JSONL - one JSON record per line"
        assert "retention" in summary
