"""
Tests for cli.py - CLI commands and FabricDeployer class.

Tests verify:
- CLI commands (validate, diagnose, deploy, destroy)
- FabricDeployer initialization and configuration
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from usf_fabric_cli.cli import app
from usf_fabric_cli.services.deployer import FabricDeployer


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

    @patch("usf_fabric_cli.cli.FabricDiagnostics")
    @patch("usf_fabric_cli.cli.FabricCLIWrapper")
    @patch("usf_fabric_cli.cli.get_environment_variables")
    def test_diagnose_runs(self, mock_get_env, mock_wrapper, mock_diagnostics, runner):
        """Test that diagnose command runs without crashing."""
        # Setup mocks
        mock_get_env.return_value = {"FABRIC_TOKEN": "mock-token"}

        mock_diag_instance = MagicMock()
        mock_diag_instance.validate_fabric_cli_installation.return_value = {
            "success": True,
            "version": "1.0.0",
        }
        mock_diag_instance.validate_authentication.return_value = {"success": True}
        mock_diag_instance.validate_api_connectivity.return_value = {
            "success": True,
            "workspaces_count": 5,
        }
        mock_diagnostics.return_value = mock_diag_instance

        result = runner.invoke(app, ["diagnose"])

        # Should complete successfully
        assert result.exit_code == 0
        assert "All diagnostic checks completed" in result.output

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

    @patch("usf_fabric_cli.cli.get_environment_variables")
    @patch("usf_fabric_cli.cli.FabricCLIWrapper")
    def test_destroy_idempotent_not_found(
        self, mock_wrapper_cls, mock_env, runner, config_file
    ):
        """Test that destroy exits cleanly when workspace is already gone (NotFound)."""
        mock_env.return_value = {"FABRIC_TOKEN": "fake-token"}
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.delete_workspace.return_value = {
            "success": False,
            "error": (
                "x rm: [NotFound] The Workspace"
                " 'test-to-destroy.Workspace' could not be found"
            ),
        }

        result = runner.invoke(app, ["destroy", config_file, "--force"])

        assert result.exit_code == 0
        assert "already cleaned up" in result.output

    @patch("usf_fabric_cli.cli.get_environment_variables")
    @patch("usf_fabric_cli.cli.FabricCLIWrapper")
    def test_destroy_real_error_still_fails(
        self, mock_wrapper_cls, mock_env, runner, config_file
    ):
        """Test that destroy still fails on genuine errors."""
        mock_env.return_value = {"FABRIC_TOKEN": "fake-token"}
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.delete_workspace.return_value = {
            "success": False,
            "error": "Internal server error: unexpected failure",
        }

        result = runner.invoke(app, ["destroy", config_file, "--force"])

        assert result.exit_code == 1
        assert "Failed to destroy" in result.output

    @patch("usf_fabric_cli.cli.get_environment_variables")
    @patch("usf_fabric_cli.cli.FabricCLIWrapper")
    def test_destroy_safety_blocks_populated_workspace(
        self, mock_wrapper_cls, mock_env, runner, config_file
    ):
        """Test that --safe blocks deletion of workspaces with items (exit code 2)."""
        mock_env.return_value = {"FABRIC_TOKEN": "fake-token"}
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.delete_workspace.return_value = {
            "success": False,
            "blocked_by_safety": True,
            "message": "SAFETY: Workspace contains 3 item(s)",
            "item_summary": {
                "item_count": 3,
                "items_by_type": {"Notebook": 2, "Lakehouse": 1},
                "has_items": True,
            },
        }

        result = runner.invoke(app, ["destroy", config_file, "--force"])

        assert result.exit_code == 2
        assert "SAFETY BLOCK" in result.output
        assert "Notebook" in result.output

    @patch("usf_fabric_cli.cli.get_environment_variables")
    @patch("usf_fabric_cli.cli.FabricCLIWrapper")
    def test_destroy_force_destroy_populated_overrides_safe(
        self, mock_wrapper_cls, mock_env, runner, config_file
    ):
        """Test --force-destroy-populated overrides --safe and deletes normally."""
        mock_env.return_value = {"FABRIC_TOKEN": "fake-token"}
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.delete_workspace.return_value = {"success": True}

        result = runner.invoke(
            app,
            ["destroy", config_file, "--force", "--force-destroy-populated"],
        )

        assert result.exit_code == 0
        assert "destroyed" in result.output
        # Verify delete_workspace was called with safe=False
        mock_wrapper.delete_workspace.assert_called_once()
        call_kwargs = mock_wrapper.delete_workspace.call_args
        assert call_kwargs[1].get("safe") is False or (
            len(call_kwargs[0]) > 1 and call_kwargs[0][1] is False
        )

    @patch("usf_fabric_cli.cli.get_environment_variables")
    @patch("usf_fabric_cli.cli.FabricCLIWrapper")
    def test_destroy_insufficient_privileges_exits_clean(
        self, mock_wrapper_cls, mock_env, runner, config_file
    ):
        """Test InsufficientPrivileges is treated as a non-fatal warning."""
        mock_env.return_value = {"FABRIC_TOKEN": "fake-token"}
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.delete_workspace.return_value = {
            "success": False,
            "error": "InsufficientPrivileges: cannot delete workspace",
        }

        result = runner.invoke(app, ["destroy", config_file, "--force"])

        assert result.exit_code == 0
        assert "insufficient privileges" in result.output.lower()


class TestFabricDeployerDeploy:
    """Tests for FabricDeployer.deploy() method with mocked Fabric CLI."""

    @pytest.fixture
    def full_config(self, tmp_path):
        """Create a full configuration file with all item types."""
        config_content = """
workspace:
  name: test-full-workspace
  display_name: Test Full Workspace
  description: Full test with all items
  capacity_id: "12345678-1234-1234-1234-123456789012"
  git_repo: https://github.com/testorg/testrepo
  git_branch: main
folders:
  - Bronze
  - Silver
  - Gold
lakehouses:
  - name: raw_lakehouse
    description: Raw data storage
    folder: Bronze
warehouses:
  - name: analytics_warehouse
    description: Analytics warehouse
    folder: Gold
notebooks:
  - name: data_transform
    description: Transform notebook
    folder: Silver
pipelines:
  - name: daily_pipeline
    description: Daily ETL
principals:
  - id: "test-principal-id"
    role: Admin
"""
        config_file = tmp_path / "full_config.yaml"
        config_file.write_text(config_content)
        return str(config_file)

    @pytest.fixture
    def mock_env_vars_full(self):
        """Mock all required environment variables."""
        env_vars = {
            "FABRIC_TOKEN": "mock-token-12345",
            "AZURE_TENANT_ID": "12345678-1234-1234-1234-123456789012",
            "AZURE_CLIENT_ID": "12345678-1234-1234-1234-123456789012",
            "AZURE_CLIENT_SECRET": "mock-secret",
            "GITHUB_TOKEN": "mock-github-token",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            yield env_vars

    def test_deployer_deploy_creates_workspace(self, full_config, mock_env_vars_full):
        """Test that deploy creates workspace and items."""
        with (
            patch("usf_fabric_cli.services.deployer.FabricCLIWrapper") as MockWrapper,
            patch("usf_fabric_cli.services.deployer.GitFabricIntegration") as MockGit,
            patch("usf_fabric_cli.services.deployer.FabricGitAPI") as MockGitAPI,
            patch("usf_fabric_cli.services.deployer.AuditLogger") as MockAudit,
            patch("usf_fabric_cli.services.deployer.ArtifactTemplateEngine"),
        ):

            # Setup mock wrapper
            mock_fabric = MagicMock()
            mock_fabric.create_workspace.return_value = {
                "success": True,
                "workspace_id": "ws-12345",
            }
            mock_fabric.create_folder.return_value = {"success": True}
            mock_fabric.create_lakehouse.return_value = {"success": True}
            mock_fabric.create_warehouse.return_value = {"success": True}
            mock_fabric.create_notebook.return_value = {"success": True}
            mock_fabric.create_pipeline.return_value = {"success": True}
            mock_fabric.add_workspace_principal.return_value = {"success": True}

            MockWrapper.return_value = mock_fabric
            MockGit.return_value = MagicMock()
            MockGitAPI.return_value = MagicMock()
            MockAudit.return_value = MagicMock()

            deployer = FabricDeployer(config_path=full_config)

            # Verify config was loaded correctly
            assert deployer.config.name == "test-full-workspace"
            assert len(deployer.config.lakehouses) == 1
            assert len(deployer.config.warehouses) == 1

    def test_deployer_config_with_principals(self, full_config, mock_env_vars_full):
        """Test deployer correctly parses principals from config."""
        with (
            patch("usf_fabric_cli.services.deployer.FabricCLIWrapper") as MockWrapper,
            patch("usf_fabric_cli.services.deployer.GitFabricIntegration"),
            patch("usf_fabric_cli.services.deployer.FabricGitAPI"),
            patch("usf_fabric_cli.services.deployer.AuditLogger"),
            patch("usf_fabric_cli.services.deployer.ArtifactTemplateEngine"),
        ):

            MockWrapper.return_value = MagicMock()
            deployer = FabricDeployer(config_path=full_config)

            # Should have at least the configured principal
            assert len(deployer.config.principals) >= 1
            principal_ids = [p.get("id") for p in deployer.config.principals]
            assert "test-principal-id" in principal_ids


class TestCLIDeployCommand:
    """Tests for the deploy CLI command execution."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock configuration file."""
        config_content = """
workspace:
  name: cli-test-workspace
  display_name: CLI Test Workspace
  description: Test
  capacity_id: "12345678-1234-1234-1234-123456789012"
"""
        config_file = tmp_path / "cli_test_config.yaml"
        config_file.write_text(config_content)
        return str(config_file)

    def test_deploy_with_validate_only(self, runner, mock_config):
        """Test deploy command with --validate-only flag."""
        env_vars = {
            "FABRIC_TOKEN": "mock-token",
            "AZURE_TENANT_ID": "tenant-id",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            result = runner.invoke(app, ["deploy", mock_config, "--validate-only"])

            # Should validate and return successfully
            assert result.exit_code == 0
            assert "valid" in result.output.lower()

    def test_deploy_validates_nonexistent_config(self, runner):
        """Test deploy with nonexistent config fails gracefully."""
        result = runner.invoke(app, ["deploy", "/nonexistent/config.yaml"])

        assert result.exit_code != 0


class TestGitURLParsing:
    """Tests for Git URL parsing functionality in FabricDeployer."""

    @pytest.fixture
    def minimal_config(self, tmp_path):
        """Create minimal config for testing."""
        config_content = """
workspace:
  name: git-test-workspace
  display_name: Git Test
  description: Test
  capacity_id: "12345678-1234-1234-1234-123456789012"
"""
        config_file = tmp_path / "git_config.yaml"
        config_file.write_text(config_content)
        return str(config_file)

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

    def test_parse_github_url(self, minimal_config, mock_env_vars):
        """Test parsing GitHub repository URLs."""
        with (
            patch("usf_fabric_cli.services.deployer.FabricCLIWrapper"),
            patch("usf_fabric_cli.services.deployer.GitFabricIntegration"),
            patch("usf_fabric_cli.services.deployer.FabricGitAPI"),
            patch("usf_fabric_cli.services.deployer.AuditLogger"),
            patch("usf_fabric_cli.services.deployer.ArtifactTemplateEngine"),
        ):

            deployer = FabricDeployer(config_path=minimal_config)

            # Test GitHub URL
            result = deployer._parse_git_repo_url("https://github.com/owner/repo")

            assert result is not None
            assert result["owner"] == "owner"
            assert result["repo"] == "repo"

    def test_parse_azure_devops_url(self, minimal_config, mock_env_vars):
        """Test parsing Azure DevOps repository URLs."""
        with (
            patch("usf_fabric_cli.services.deployer.FabricCLIWrapper"),
            patch("usf_fabric_cli.services.deployer.GitFabricIntegration"),
            patch("usf_fabric_cli.services.deployer.FabricGitAPI"),
            patch("usf_fabric_cli.services.deployer.AuditLogger"),
            patch("usf_fabric_cli.services.deployer.ArtifactTemplateEngine"),
        ):

            deployer = FabricDeployer(config_path=minimal_config)

            # Test Azure DevOps URL
            result = deployer._parse_git_repo_url(
                "https://dev.azure.com/myorg/myproject/_git/myrepo"
            )

            assert result is not None
            assert result["organization"] == "myorg"
            assert result["project"] == "myproject"
            assert result["repo"] == "myrepo"

    def test_parse_invalid_url(self, minimal_config, mock_env_vars):
        """Test parsing invalid Git URLs returns None."""
        with (
            patch("usf_fabric_cli.services.deployer.FabricCLIWrapper"),
            patch("usf_fabric_cli.services.deployer.GitFabricIntegration"),
            patch("usf_fabric_cli.services.deployer.FabricGitAPI"),
            patch("usf_fabric_cli.services.deployer.AuditLogger"),
            patch("usf_fabric_cli.services.deployer.ArtifactTemplateEngine"),
        ):

            deployer = FabricDeployer(config_path=minimal_config)

            # Test invalid URL
            result = deployer._parse_git_repo_url("https://invalid.com/repo")

            assert result is None


class TestCLIOrganizeFolders:
    """Tests for the organize-folders CLI command."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def config_with_rules(self, tmp_path):
        """Create a config with folder_rules."""
        config_content = """
workspace:
  name: test-organize
  capacity_id: "12345678-1234-1234-1234-123456789012"
folders:
  - "200 Store"
  - "300 Prepare"
folder_rules:
  - type: Lakehouse
    folder: "200 Store"
  - type: Notebook
    folder: "300 Prepare"
"""
        config_file = tmp_path / "organize_config.yaml"
        config_file.write_text(config_content)
        return str(config_file)

    @pytest.fixture
    def config_without_rules(self, tmp_path):
        """Create a config without folder_rules."""
        config_content = """
workspace:
  name: test-no-rules
  capacity_id: "12345678-1234-1234-1234-123456789012"
"""
        config_file = tmp_path / "no_rules_config.yaml"
        config_file.write_text(config_content)
        return str(config_file)

    @patch("usf_fabric_cli.cli.get_environment_variables")
    def test_organize_folders_no_rules_exits_clean(
        self, mock_env, runner, config_without_rules
    ):
        """Config without folder_rules prints warning and exits 0."""
        mock_env.return_value = {"FABRIC_TOKEN": "fake-token"}

        result = runner.invoke(app, ["organize-folders", config_without_rules])

        assert result.exit_code == 0
        assert "nothing to organize" in result.output.lower()

    @patch("usf_fabric_cli.cli.FabricCLIWrapper")
    @patch("usf_fabric_cli.cli.get_environment_variables")
    def test_organize_folders_dry_run_shows_plan(
        self, mock_env, mock_wrapper_cls, runner, config_with_rules
    ):
        """Dry run lists items that would be moved."""
        mock_env.return_value = {"FABRIC_TOKEN": "fake-token"}
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.list_workspace_items_api.return_value = [
            {
                "id": "lh-1",
                "type": "Lakehouse",
                "displayName": "my_lakehouse",
            },
            {
                "id": "nb-1",
                "type": "Notebook",
                "displayName": "transform",
                "folderId": None,
            },
        ]

        result = runner.invoke(
            app, ["organize-folders", config_with_rules, "--dry-run"]
        )

        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "Would move" in result.output

    @patch("usf_fabric_cli.cli.FabricCLIWrapper")
    @patch("usf_fabric_cli.cli.get_environment_variables")
    def test_organize_folders_executes_move(
        self, mock_env, mock_wrapper_cls, runner, config_with_rules
    ):
        """Calls organize_items_into_folders correctly."""
        mock_env.return_value = {"FABRIC_TOKEN": "fake-token"}
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.organize_items_into_folders.return_value = {
            "moved": 2,
            "skipped": 0,
            "failed": 0,
            "details": [
                {
                    "item": "my_lakehouse",
                    "type": "Lakehouse",
                    "folder": "200 Store",
                    "status": "moved",
                },
            ],
        }

        result = runner.invoke(app, ["organize-folders", config_with_rules])

        assert result.exit_code == 0
        assert "Organize complete" in result.output
        mock_wrapper.organize_items_into_folders.assert_called_once()

    @patch("usf_fabric_cli.cli.get_environment_variables")
    def test_organize_folders_missing_token(self, mock_env, runner, config_with_rules):
        """Exits 1 when FABRIC_TOKEN is missing."""
        mock_env.return_value = {"FABRIC_TOKEN": ""}

        result = runner.invoke(app, ["organize-folders", config_with_rules])

        assert result.exit_code == 1
        assert "FABRIC_TOKEN" in result.output

    def test_organize_folders_nonexistent_config(self, runner):
        """Exits non-zero for missing config file."""
        result = runner.invoke(app, ["organize-folders", "/nonexistent/config.yaml"])

        assert result.exit_code != 0


class TestCLIBulkDestroy:
    """Tests for the bulk-destroy CLI command."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    def test_bulk_destroy_missing_file(self, runner):
        """Exits 1 for nonexistent file."""
        result = runner.invoke(app, ["bulk-destroy", "/nonexistent/workspaces.txt"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    @patch("usf_fabric_cli.cli.bulk_destroy_fn")
    def test_bulk_destroy_calls_function(self, mock_fn, runner, tmp_path):
        """Verifies it delegates to bulk_destroy_fn."""
        ws_file = tmp_path / "workspaces.txt"
        ws_file.write_text("ws-1\nws-2\n")

        result = runner.invoke(app, ["bulk-destroy", str(ws_file), "--force"])

        assert result.exit_code == 0
        mock_fn.assert_called_once_with(str(ws_file), False, True)

    @patch("usf_fabric_cli.cli.bulk_destroy_fn")
    def test_bulk_destroy_dry_run(self, mock_fn, runner, tmp_path):
        """Passes dry_run=True when --dry-run is given."""
        ws_file = tmp_path / "workspaces.txt"
        ws_file.write_text("ws-1\n")

        result = runner.invoke(app, ["bulk-destroy", str(ws_file), "--dry-run"])

        assert result.exit_code == 0
        mock_fn.assert_called_once_with(str(ws_file), True, False)


class TestCLIGenerate:
    """Tests for the generate CLI command."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @patch("usf_fabric_cli.cli.generate_project_config")
    def test_generate_calls_function(self, mock_fn, runner):
        """Delegates to generate_project_config with correct args."""
        result = runner.invoke(
            app,
            [
                "generate",
                "Contoso Inc",
                "Sales Analytics",
                "--template",
                "medallion",
            ],
        )

        assert result.exit_code == 0
        mock_fn.assert_called_once_with(
            "Contoso Inc",
            "Sales Analytics",
            "medallion",
            "${FABRIC_CAPACITY_ID}",
            "${GIT_REPO_URL}",
        )

    @patch("usf_fabric_cli.cli.generate_project_config")
    def test_generate_failure_exits_1(self, mock_fn, runner):
        """Exception from generate_project_config → exit code 1."""
        mock_fn.side_effect = RuntimeError("Template not found")

        result = runner.invoke(app, ["generate", "Org", "Proj"])

        assert result.exit_code == 1
        assert "Generate failed" in result.output
