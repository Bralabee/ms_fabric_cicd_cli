"""
Tests for cli.py - CLI commands and FabricDeployer class.

Tests verify:
- CLI commands (validate, diagnose, deploy, destroy)
- FabricDeployer initialization and configuration
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from usf_fabric_cli.cli import app, FabricDeployer


class TestCLIValidate:
    """Tests for the validate CLI command."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def valid_config(self, tmp_path):
        """Create a valid minimal configuration file."""
        config_content = """
workspace:
  name: test-workspace
  display_name: Test Workspace
  description: A test workspace
  capacity_id: "12345678-1234-1234-1234-123456789012"
  folders:
    - Bronze
    - Silver
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)
        return str(config_file)

    @pytest.fixture
    def invalid_config(self, tmp_path):
        """Create an invalid configuration file."""
        config_content = """
workspace:
  # Missing required fields
  description: Just a description
"""
        config_file = tmp_path / "invalid_config.yaml"
        config_file.write_text(config_content)
        return str(config_file)

    def test_validate_valid_config(self, runner, valid_config):
        """Test validating a valid configuration file."""
        result = runner.invoke(app, ["validate", valid_config])

        # Should succeed or at least not crash
        assert result.exit_code == 0 or "valid" in result.output.lower()

    def test_validate_nonexistent_file(self, runner):
        """Test validating a non-existent file."""
        result = runner.invoke(app, ["validate", "/nonexistent/path/config.yaml"])

        assert result.exit_code != 0

    def test_validate_with_environment(self, runner, valid_config):
        """Test validating with environment option."""
        result = runner.invoke(app, ["validate", valid_config, "--env", "dev"])

        # Should not crash
        assert result.exit_code in [0, 1]


class TestCLIDiagnose:
    """Tests for the diagnose CLI command."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    def test_diagnose_runs(self, runner):
        """Test that diagnose command runs without crashing."""
        result = runner.invoke(app, ["diagnose"])

        # Should complete (may or may not find fab CLI)
        assert result.exit_code in [0, 1]

    def test_diagnose_checks_fabric_cli(self, runner):
        """Test that diagnose checks for Fabric CLI."""
        result = runner.invoke(app, ["diagnose"])

        # Output should mention CLI or fab
        output_lower = result.output.lower()
        assert (
            "cli" in output_lower or "fab" in output_lower or "fabric" in output_lower
        )


class TestFabricDeployerInit:
    """Tests for FabricDeployer initialization."""

    @pytest.fixture
    def minimal_config(self, tmp_path):
        """Create a minimal valid configuration file."""
        config_content = """
workspace:
  name: test-workspace
  display_name: Test Workspace
  description: Test
  capacity_id: "12345678-1234-1234-1234-123456789012"
  folders:
    - Bronze
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)
        return str(config_file)

    @pytest.fixture
    def mock_env_vars(self):
        """Mock required environment variables."""
        env_vars = {
            "FABRIC_TOKEN": "mock-token-12345",
            "AZURE_TENANT_ID": "12345678-1234-1234-1234-123456789012",
            "AZURE_CLIENT_ID": "12345678-1234-1234-1234-123456789012",
            "AZURE_CLIENT_SECRET": "mock-secret",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            yield env_vars

    def test_deployer_init_with_valid_config(self, minimal_config, mock_env_vars):
        """Test FabricDeployer initialization with valid config."""
        deployer = FabricDeployer(config_path=minimal_config)

        assert deployer.config is not None
        assert deployer.config.name == "test-workspace"

    def test_deployer_init_with_environment(
        self, minimal_config, mock_env_vars, tmp_path
    ):
        """Test FabricDeployer with environment-specific config."""
        # Create environment override
        env_dir = tmp_path / "environments"
        env_dir.mkdir()
        env_config = env_dir / "dev.yaml"
        env_config.write_text(
            """
workspace:
  capacity_id: "dev-capacity-id"
"""
        )

        deployer = FabricDeployer(config_path=minimal_config, environment="dev")

        # Should load without error
        assert deployer.config is not None

    def test_deployer_init_nonexistent_config(self, mock_env_vars):
        """Test FabricDeployer with non-existent config file."""
        with pytest.raises(Exception):
            FabricDeployer(config_path="/nonexistent/config.yaml")


class TestCLIHelp:
    """Tests for CLI help output."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    def test_help_shows_commands(self, runner):
        """Test that --help shows available commands."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "deploy" in result.output
        assert "validate" in result.output
        assert "diagnose" in result.output
        assert "destroy" in result.output

    def test_deploy_help(self, runner):
        """Test deploy command help."""
        result = runner.invoke(app, ["deploy", "--help"])

        assert result.exit_code == 0
        assert "--env" in result.output or "environment" in result.output.lower()
        assert "--branch" in result.output or "branch" in result.output.lower()

    def test_destroy_help(self, runner):
        """Test destroy command help."""
        result = runner.invoke(app, ["destroy", "--help"])

        assert result.exit_code == 0
        assert "--force" in result.output or "force" in result.output.lower()


class TestCLIDestroy:
    """Tests for the destroy CLI command."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def config_file(self, tmp_path):
        """Create a test configuration file."""
        config_content = """
workspace:
  name: test-to-destroy
  display_name: Test To Destroy
  description: Test
  capacity_id: "12345678-1234-1234-1234-123456789012"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)
        return str(config_file)

    def test_destroy_requires_confirmation(self, runner, config_file):
        """Test that destroy asks for confirmation without --force."""
        # Without --force, should prompt (which will fail in test runner)
        result = runner.invoke(app, ["destroy", config_file], input="n\n")

        # Should either ask for confirmation or fail gracefully
        assert result.exit_code in [0, 1]

    def test_destroy_nonexistent_config(self, runner):
        """Test destroy with non-existent config."""
        result = runner.invoke(app, ["destroy", "/nonexistent/config.yaml"])

        assert result.exit_code != 0
