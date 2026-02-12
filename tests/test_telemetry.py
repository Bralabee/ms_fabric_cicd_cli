"""
Unit tests for TelemetryClient (utils/telemetry.py).

Tests verify:
- JSONL event emission
- Disabled client writes nothing
- Environment variable disabling
- Log rotation at size threshold
"""

import json
import os
from unittest.mock import patch

import pytest

from usf_fabric_cli.utils.telemetry import TelemetryClient


class TestTelemetryEmit:
    """Tests for the emit() method."""

    def test_emit_writes_valid_jsonl(self, tmp_path):
        """emit() should write a valid JSONL line."""
        client = TelemetryClient(log_directory=str(tmp_path))
        client.emit(
            command="deploy",
            status="success",
            duration_ms=1500,
            metadata={"workspace": "test-ws"},
        )

        log_file = tmp_path / "fabric_cli_telemetry.jsonl"
        assert log_file.exists()

        with open(log_file, "r") as f:
            lines = f.readlines()

        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["command"] == "deploy"
        assert data["status"] == "success"
        assert data["duration_ms"] == 1500
        assert data["metadata"]["workspace"] == "test-ws"
        assert "timestamp" in data

    def test_emit_multiple_events(self, tmp_path):
        """Multiple emit() calls should append lines."""
        client = TelemetryClient(log_directory=str(tmp_path))
        for i in range(3):
            client.emit(command=f"cmd-{i}", status="success")

        log_file = tmp_path / "fabric_cli_telemetry.jsonl"
        with open(log_file, "r") as f:
            lines = f.readlines()

        assert len(lines) == 3
        for i, line in enumerate(lines):
            data = json.loads(line)
            assert data["command"] == f"cmd-{i}"


class TestTelemetryDisabled:
    """Tests for disabled telemetry client."""

    def test_disabled_client_writes_nothing(self, tmp_path):
        """Disabled client should not create any files."""
        client = TelemetryClient(log_directory=str(tmp_path), enabled=False)
        client.emit(command="deploy", status="success")

        log_file = tmp_path / "fabric_cli_telemetry.jsonl"
        assert not log_file.exists()

    def test_env_var_disables_telemetry(self, tmp_path):
        """DISABLE_FABRIC_TELEMETRY=1 should disable telemetry."""
        with patch.dict(
            os.environ,
            {"DISABLE_FABRIC_TELEMETRY": "1"},
        ):
            client = TelemetryClient(log_directory=str(tmp_path))
            client.emit(command="deploy", status="success")

        log_file = tmp_path / "fabric_cli_telemetry.jsonl"
        assert not log_file.exists()


class TestTelemetryRotation:
    """Tests for log file rotation."""

    def test_rotation_triggers_at_threshold(self, tmp_path):
        """Log should rotate when exceeding size threshold."""
        client = TelemetryClient(log_directory=str(tmp_path))

        log_file = tmp_path / "fabric_cli_telemetry.jsonl"
        # Write a large initial payload to simulate exceeding limit
        with open(log_file, "w") as f:
            f.write("x" * 100 + "\n")

        # Set a very low threshold for rotation
        with patch.object(
            type(client),
            "_max_log_size",
            new_callable=lambda: property(lambda self: 50),
        ):
            client.emit(command="deploy", status="success")

        # Original file should still exist (with new content)
        assert log_file.exists()

    def test_no_rotation_below_threshold(self, tmp_path):
        """Log should NOT rotate when below size threshold."""
        client = TelemetryClient(log_directory=str(tmp_path))

        client.emit(command="deploy", status="success")

        rotated = tmp_path / "fabric_cli_telemetry.jsonl.1"
        assert not rotated.exists()


class TestTelemetryEdgeCases:
    """Tests for edge cases in telemetry."""

    def test_missing_directory_created(self, tmp_path):
        """Should create log directory if it doesn't exist."""
        log_dir = tmp_path / "subdir" / "telemetry"
        client = TelemetryClient(log_directory=str(log_dir))
        client.emit(command="test", status="success")

        log_file = log_dir / "fabric_cli_telemetry.jsonl"
        assert log_file.exists()

    def test_default_directory(self):
        """Default constructor should not raise."""
        client = TelemetryClient()
        # Should not raise — just validates initialization
        assert client is not None


if __name__ == "__main__":
    pytest.main([__file__])
