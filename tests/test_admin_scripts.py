"""
Smoke tests and unit tests for admin/utility scripts at 0% coverage.

Covers:
- bulk_destroy (parse_workspace_list, bulk_destroy dry-run)
- preflight_check (_validate_auth_vars, REQUIRED_ENV_VARS)
- analyze_migration (CustomSolutionAnalyzer pure-logic methods)
- debug_ado_access (import smoke + typer app exists)
- debug_connection (import smoke + typer app exists)
- init_ado_repo (import smoke + function signatures)
- init_github_repo (_headers, get_repo, create_repo)
- list_workspace_items (import smoke)
- list_workspaces (import smoke)
"""

import os
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# ═══════════════════════════════════════════════════════════════════
# 1. Import Smoke Tests — verify every script can be imported
# ═══════════════════════════════════════════════════════════════════


class TestImportSmoke:
    """Verify all admin/utility scripts import without errors."""

    def test_import_bulk_destroy(self):
        from usf_fabric_cli.scripts.admin import bulk_destroy  # noqa: F401

        assert hasattr(bulk_destroy, "parse_workspace_list")
        assert hasattr(bulk_destroy, "bulk_destroy")
        assert hasattr(bulk_destroy, "main")

    def test_import_preflight_check(self):
        from usf_fabric_cli.scripts.admin import preflight_check  # noqa: F401

        assert hasattr(preflight_check, "REQUIRED_ENV_VARS")
        assert hasattr(preflight_check, "_validate_auth_vars")
        assert hasattr(preflight_check, "run_preflight")
        assert hasattr(preflight_check, "main")

    def test_import_analyze_migration(self):
        from usf_fabric_cli.scripts.admin.utilities import (  # noqa: F401
            analyze_migration,
        )

        assert hasattr(analyze_migration, "CustomSolutionAnalyzer")
        assert hasattr(analyze_migration, "main")

    @patch("usf_fabric_cli.utils.secrets.FabricSecrets")
    def test_import_debug_ado_access(self, _mock_secrets):
        from usf_fabric_cli.scripts.admin.utilities import (  # noqa: F401
            debug_ado_access,
        )

        assert hasattr(debug_ado_access, "app")
        assert hasattr(debug_ado_access, "main")

    @patch("usf_fabric_cli.utils.secrets.FabricSecrets")
    def test_import_debug_connection(self, _mock_secrets):
        from usf_fabric_cli.scripts.admin.utilities import (  # noqa: F401
            debug_connection,
        )

        assert hasattr(debug_connection, "app")
        assert hasattr(debug_connection, "main")

    def test_import_init_ado_repo(self):
        from usf_fabric_cli.scripts.admin.utilities import init_ado_repo  # noqa: F401

        assert hasattr(init_ado_repo, "get_ado_token")
        assert hasattr(init_ado_repo, "get_repo_id")
        assert hasattr(init_ado_repo, "create_repo")
        assert hasattr(init_ado_repo, "app")

    def test_import_init_github_repo(self):
        from usf_fabric_cli.scripts.admin.utilities import (  # noqa: F401
            init_github_repo,
        )

        assert hasattr(init_github_repo, "GITHUB_API")
        assert hasattr(init_github_repo, "_headers")
        assert hasattr(init_github_repo, "get_repo")
        assert hasattr(init_github_repo, "create_repo")
        assert hasattr(init_github_repo, "app")

    def test_import_list_workspace_items(self):
        from usf_fabric_cli.scripts.admin.utilities import (  # noqa: F401
            list_workspace_items,
        )

        assert hasattr(list_workspace_items, "list_workspace_items")
        assert hasattr(list_workspace_items, "main")

    def test_import_list_workspaces(self):
        from usf_fabric_cli.scripts.admin.utilities import list_workspaces  # noqa: F401

        assert hasattr(list_workspaces, "list_workspaces")
        assert hasattr(list_workspaces, "main")


# ═══════════════════════════════════════════════════════════════════
# 2. bulk_destroy — parse_workspace_list
# ═══════════════════════════════════════════════════════════════════


class TestBulkDestroyParseWorkspaceList:
    """Test the pure file-parsing logic of parse_workspace_list."""

    def test_basic_workspace_names(self, tmp_path):
        from usf_fabric_cli.scripts.admin.bulk_destroy import parse_workspace_list

        ws_file = tmp_path / "workspaces.txt"
        ws_file.write_text("Workspace1\nWorkspace2\nWorkspace3\n")

        result = parse_workspace_list(str(ws_file))
        assert result == ["Workspace1", "Workspace2", "Workspace3"]

    def test_strips_workspace_suffix(self, tmp_path):
        from usf_fabric_cli.scripts.admin.bulk_destroy import parse_workspace_list

        ws_file = tmp_path / "workspaces.txt"
        ws_file.write_text("MyProject.Workspace\nOtherProject.Workspace\n")

        result = parse_workspace_list(str(ws_file))
        assert result == ["MyProject", "OtherProject"]

    def test_skips_comments_headers_blank_lines(self, tmp_path):
        from usf_fabric_cli.scripts.admin.bulk_destroy import parse_workspace_list

        content = textwrap.dedent(
            """\
            # This is a comment
            Name  Type  Id

            ActualWorkspace
            # Another comment

            SecondWorkspace.Workspace
        """
        )
        ws_file = tmp_path / "workspaces.txt"
        ws_file.write_text(content)

        result = parse_workspace_list(str(ws_file))
        assert result == ["ActualWorkspace", "SecondWorkspace"]

    def test_empty_file_returns_empty_list(self, tmp_path):
        from usf_fabric_cli.scripts.admin.bulk_destroy import parse_workspace_list

        ws_file = tmp_path / "empty.txt"
        ws_file.write_text("")

        result = parse_workspace_list(str(ws_file))
        assert result == []

    def test_only_comments_returns_empty_list(self, tmp_path):
        from usf_fabric_cli.scripts.admin.bulk_destroy import parse_workspace_list

        ws_file = tmp_path / "comments.txt"
        ws_file.write_text("# Just a comment\n# Another\n")

        result = parse_workspace_list(str(ws_file))
        assert result == []

    def test_multicolumn_extracts_first_column(self, tmp_path):
        from usf_fabric_cli.scripts.admin.bulk_destroy import parse_workspace_list

        content = "MyWorkspace.Workspace  GUID-123  active\n"
        ws_file = tmp_path / "workspaces.txt"
        ws_file.write_text(content)

        result = parse_workspace_list(str(ws_file))
        assert result == ["MyWorkspace"]


class TestBulkDestroyDryRun:
    """Test bulk_destroy in dry-run mode (no real deletions)."""

    def test_dry_run_does_not_delete(self, tmp_path, capsys):
        from usf_fabric_cli.scripts.admin.bulk_destroy import bulk_destroy

        ws_file = tmp_path / "workspaces.txt"
        ws_file.write_text("TestWorkspace\n")

        bulk_destroy(str(ws_file), dry_run=True)

        captured = capsys.readouterr()
        assert "Dry Run" in captured.out
        assert "TestWorkspace" in captured.out

    def test_empty_file_dry_run(self, tmp_path, capsys):
        from usf_fabric_cli.scripts.admin.bulk_destroy import bulk_destroy

        ws_file = tmp_path / "empty.txt"
        ws_file.write_text("")

        bulk_destroy(str(ws_file), dry_run=True)

        captured = capsys.readouterr()
        assert "No workspaces found" in captured.out


# ═══════════════════════════════════════════════════════════════════
# 3. preflight_check — _validate_auth_vars
# ═══════════════════════════════════════════════════════════════════


class TestPreflightValidateAuthVars:
    """Test auth validation logic (Token vs Service Principal)."""

    def test_fabric_token_present_returns_empty(self, monkeypatch):
        from usf_fabric_cli.scripts.admin.preflight_check import _validate_auth_vars

        monkeypatch.setenv("FABRIC_TOKEN", "a-valid-token")
        result = _validate_auth_vars()
        assert result == []

    def test_service_principal_complete_returns_empty(self, monkeypatch):
        from usf_fabric_cli.scripts.admin.preflight_check import _validate_auth_vars

        monkeypatch.delenv("FABRIC_TOKEN", raising=False)
        monkeypatch.setenv("AZURE_CLIENT_ID", "client-id")
        monkeypatch.setenv("AZURE_CLIENT_SECRET", "client-secret")
        monkeypatch.setenv("AZURE_TENANT_ID", "tenant-id")

        result = _validate_auth_vars()
        assert result == []

    def test_tenant_id_alternative_accepted(self, monkeypatch):
        from usf_fabric_cli.scripts.admin.preflight_check import _validate_auth_vars

        monkeypatch.delenv("FABRIC_TOKEN", raising=False)
        monkeypatch.setenv("AZURE_CLIENT_ID", "client-id")
        monkeypatch.setenv("AZURE_CLIENT_SECRET", "client-secret")
        monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
        monkeypatch.setenv("TENANT_ID", "tenant-id")

        result = _validate_auth_vars()
        assert result == []

    def test_nothing_set_returns_missing(self, monkeypatch):
        from usf_fabric_cli.scripts.admin.preflight_check import _validate_auth_vars

        for var in [
            "FABRIC_TOKEN",
            "AZURE_CLIENT_ID",
            "AZURE_CLIENT_SECRET",
            "AZURE_TENANT_ID",
            "TENANT_ID",
        ]:
            monkeypatch.delenv(var, raising=False)

        result = _validate_auth_vars()
        assert "FABRIC_TOKEN" in result
        assert any("AZURE_CLIENT_ID" in v for v in result)

    def test_partial_sp_missing_client_secret(self, monkeypatch):
        from usf_fabric_cli.scripts.admin.preflight_check import _validate_auth_vars

        monkeypatch.delenv("FABRIC_TOKEN", raising=False)
        monkeypatch.setenv("AZURE_CLIENT_ID", "client-id")
        monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)
        monkeypatch.setenv("AZURE_TENANT_ID", "tenant-id")

        result = _validate_auth_vars()
        assert "FABRIC_TOKEN" in result
        assert "AZURE_CLIENT_SECRET" in result

    def test_required_env_vars_constant(self):
        from usf_fabric_cli.scripts.admin.preflight_check import REQUIRED_ENV_VARS

        assert isinstance(REQUIRED_ENV_VARS, list)
        assert "FABRIC_TOKEN" in REQUIRED_ENV_VARS


# ═══════════════════════════════════════════════════════════════════
# 4. analyze_migration — CustomSolutionAnalyzer
# ═══════════════════════════════════════════════════════════════════


class TestCustomSolutionAnalyzer:
    """Test the migration analysis pure-logic methods."""

    def test_is_cli_replaceable_true(self):
        from usf_fabric_cli.scripts.admin.utilities.analyze_migration import (
            CustomSolutionAnalyzer,
        )

        analyzer = CustomSolutionAnalyzer("/nonexistent")
        for pattern in ["workspace", "lakehouse", "notebook", "folder", "git"]:
            assert analyzer._is_cli_replaceable(pattern) is True

    def test_is_cli_replaceable_false(self):
        from usf_fabric_cli.scripts.admin.utilities.analyze_migration import (
            CustomSolutionAnalyzer,
        )

        analyzer = CustomSolutionAnalyzer("/nonexistent")
        assert analyzer._is_cli_replaceable("capacity") is False
        assert analyzer._is_cli_replaceable("principal") is False
        assert analyzer._is_cli_replaceable("unknown") is False

    def test_determine_migration_complexity_low(self):
        from usf_fabric_cli.scripts.admin.utilities.analyze_migration import (
            CustomSolutionAnalyzer,
        )

        analyzer = CustomSolutionAnalyzer("/nonexistent")
        analyzer.analysis["total_loc"] = 200
        analyzer.analysis["components_found"] = []
        analyzer._determine_migration_complexity()
        assert "LOW" in analyzer.analysis["migration_complexity"]

    def test_determine_migration_complexity_medium(self):
        from usf_fabric_cli.scripts.admin.utilities.analyze_migration import (
            CustomSolutionAnalyzer,
        )

        analyzer = CustomSolutionAnalyzer("/nonexistent")
        analyzer.analysis["total_loc"] = 800
        analyzer.analysis["components_found"] = []
        analyzer._determine_migration_complexity()
        assert "MEDIUM" in analyzer.analysis["migration_complexity"]

    def test_determine_migration_complexity_high(self):
        from usf_fabric_cli.scripts.admin.utilities.analyze_migration import (
            CustomSolutionAnalyzer,
        )

        analyzer = CustomSolutionAnalyzer("/nonexistent")
        analyzer.analysis["total_loc"] = 2000
        analyzer.analysis["components_found"] = []
        analyzer._determine_migration_complexity()
        assert "HIGH" in analyzer.analysis["migration_complexity"]

    def test_determine_complexity_with_high_cli_compatibility(self):
        from usf_fabric_cli.scripts.admin.utilities.analyze_migration import (
            CustomSolutionAnalyzer,
        )

        analyzer = CustomSolutionAnalyzer("/nonexistent")
        analyzer.analysis["total_loc"] = 200
        analyzer.analysis["components_found"] = [
            {"cli_replaceable": True},
            {"cli_replaceable": True},
            {"cli_replaceable": True},
            {"cli_replaceable": True},
            {"cli_replaceable": True},
        ]
        analyzer._determine_migration_complexity()
        assert "High CLI compatibility" in analyzer.analysis["migration_complexity"]

    def test_determine_complexity_with_low_cli_compatibility(self):
        from usf_fabric_cli.scripts.admin.utilities.analyze_migration import (
            CustomSolutionAnalyzer,
        )

        analyzer = CustomSolutionAnalyzer("/nonexistent")
        analyzer.analysis["total_loc"] = 200
        analyzer.analysis["components_found"] = [
            {"cli_replaceable": True},
            {"cli_replaceable": False},
            {"cli_replaceable": False},
            {"cli_replaceable": False},
            {"cli_replaceable": False},
        ]
        analyzer._determine_migration_complexity()
        assert "Low CLI compatibility" in analyzer.analysis["migration_complexity"]

    def test_generate_recommendations_large_codebase(self):
        from usf_fabric_cli.scripts.admin.utilities.analyze_migration import (
            CustomSolutionAnalyzer,
        )

        analyzer = CustomSolutionAnalyzer("/nonexistent")
        analyzer.analysis["total_loc"] = 1500
        analyzer.analysis["components_found"] = [
            {"cli_replaceable": True, "name": "create_workspace"},
        ]
        analyzer.analysis["fabric_api_calls"] = []
        analyzer._generate_recommendations()

        recs = analyzer.analysis["recommendations"]
        assert len(recs) >= 1
        high_priority = [r for r in recs if r["priority"] == "HIGH"]
        assert len(high_priority) >= 1

    def test_generate_recommendations_with_cli_replaceable_components(self):
        from usf_fabric_cli.scripts.admin.utilities.analyze_migration import (
            CustomSolutionAnalyzer,
        )

        analyzer = CustomSolutionAnalyzer("/nonexistent")
        analyzer.analysis["total_loc"] = 100
        analyzer.analysis["components_found"] = [
            {"cli_replaceable": True, "name": "create_lakehouse"},
            {"cli_replaceable": True, "name": "create_notebook"},
        ]
        analyzer.analysis["fabric_api_calls"] = []
        analyzer._generate_recommendations()

        recs = analyzer.analysis["recommendations"]
        medium_recs = [r for r in recs if r["priority"] == "MEDIUM"]
        assert len(medium_recs) >= 1
        assert "2" in medium_recs[0]["action"]  # "Replace 2 components"

    def test_analyze_real_directory(self, tmp_path):
        """Analyze a temp directory with a small Python file."""
        from usf_fabric_cli.scripts.admin.utilities.analyze_migration import (
            CustomSolutionAnalyzer,
        )

        py_file = tmp_path / "deploy.py"
        py_file.write_text(
            textwrap.dedent(
                """\
            def create_workspace(name):
                pass

            def create_lakehouse(ws, name):
                pass

            def do_something():
                pass
        """
            )
        )

        analyzer = CustomSolutionAnalyzer(str(tmp_path))
        result = analyzer.analyze()

        assert result["total_files"] == 1
        assert result["total_loc"] > 0
        # Should find workspace and lakehouse functions
        component_names = [c["name"] for c in result["components_found"]]
        assert "create_workspace" in component_names
        assert "create_lakehouse" in component_names

    def test_generate_report(self, tmp_path):
        """Test report generation to a JSON file."""
        from usf_fabric_cli.scripts.admin.utilities.analyze_migration import (
            CustomSolutionAnalyzer,
        )

        analyzer = CustomSolutionAnalyzer(str(tmp_path))
        analyzer.analysis["total_files"] = 5
        analyzer.analysis["total_loc"] = 300
        analyzer.analysis["migration_complexity"] = "LOW"
        analyzer.analysis["recommendations"] = []

        output_file = str(tmp_path / "report.json")
        report = analyzer.generate_report(output_file)

        assert "analysis_summary" in report
        assert report["analysis_summary"]["total_files"] == 5
        assert Path(output_file).exists()


# ═══════════════════════════════════════════════════════════════════
# 5. init_github_repo — pure helpers
# ═══════════════════════════════════════════════════════════════════


class TestInitGitHubRepoHelpers:
    """Test pure helper functions from init_github_repo."""

    def test_headers_format(self):
        from usf_fabric_cli.scripts.admin.utilities.init_github_repo import _headers

        result = _headers("test-token-123")
        assert result["Authorization"] == "Bearer test-token-123"
        assert "Accept" in result
        assert "X-GitHub-Api-Version" in result

    @patch("usf_fabric_cli.scripts.admin.utilities.init_github_repo.requests.get")
    def test_get_repo_found(self, mock_get):
        from usf_fabric_cli.scripts.admin.utilities.init_github_repo import get_repo

        mock_get.return_value = Mock(
            status_code=200,
            json=Mock(return_value={"name": "my-repo", "id": 123}),
        )
        result = get_repo("owner", "my-repo", "token")
        assert result is not None
        assert result["name"] == "my-repo"

    @patch("usf_fabric_cli.scripts.admin.utilities.init_github_repo.requests.get")
    def test_get_repo_not_found(self, mock_get):
        from usf_fabric_cli.scripts.admin.utilities.init_github_repo import get_repo

        mock_get.return_value = Mock(status_code=404)
        result = get_repo("owner", "my-repo", "token")
        assert result is None

    @patch("usf_fabric_cli.scripts.admin.utilities.init_github_repo.requests.get")
    def test_get_repo_error_raises(self, mock_get):
        import requests

        from usf_fabric_cli.scripts.admin.utilities.init_github_repo import get_repo

        mock_resp = Mock(status_code=500)
        mock_resp.raise_for_status.side_effect = requests.HTTPError("Server Error")
        mock_get.return_value = mock_resp

        with pytest.raises(requests.HTTPError):
            get_repo("owner", "my-repo", "token")


# ═══════════════════════════════════════════════════════════════════
# 6. init_ado_repo — pure helpers
# ═══════════════════════════════════════════════════════════════════


class TestInitAdoRepoHelpers:
    """Test pure helper functions from init_ado_repo."""

    @patch("usf_fabric_cli.scripts.admin.utilities.init_ado_repo.requests.get")
    def test_get_repo_id_found(self, mock_get):
        from usf_fabric_cli.scripts.admin.utilities.init_ado_repo import get_repo_id

        mock_get.return_value = Mock(
            status_code=200,
            json=Mock(return_value={"id": "repo-guid-123"}),
        )
        result = get_repo_id("my-org", "my-project", "my-repo", "token")
        assert result == "repo-guid-123"

    @patch("usf_fabric_cli.scripts.admin.utilities.init_ado_repo.requests.get")
    def test_get_repo_id_not_found(self, mock_get):
        from usf_fabric_cli.scripts.admin.utilities.init_ado_repo import get_repo_id

        mock_get.return_value = Mock(status_code=404)
        result = get_repo_id("my-org", "my-project", "my-repo", "token")
        assert result is None

    @patch("usf_fabric_cli.scripts.admin.utilities.init_ado_repo.requests.get")
    def test_get_repo_id_error_raises(self, mock_get):
        from usf_fabric_cli.scripts.admin.utilities.init_ado_repo import get_repo_id

        mock_get.return_value = Mock(status_code=403, text="Forbidden")
        with pytest.raises(Exception, match="Failed to get repository"):
            get_repo_id("my-org", "my-project", "my-repo", "token")

    @patch("usf_fabric_cli.scripts.admin.utilities.init_ado_repo.requests.post")
    def test_create_repo_success(self, mock_post):
        from usf_fabric_cli.scripts.admin.utilities.init_ado_repo import create_repo

        mock_post.return_value = Mock(
            status_code=201,
            json=Mock(return_value={"id": "new-repo-id", "name": "my-repo"}),
        )
        result = create_repo("my-org", "my-project", "my-repo", "token")
        assert result["id"] == "new-repo-id"

    @patch("usf_fabric_cli.scripts.admin.utilities.init_ado_repo.requests.post")
    def test_create_repo_failure_raises(self, mock_post):
        from usf_fabric_cli.scripts.admin.utilities.init_ado_repo import create_repo

        mock_post.return_value = Mock(status_code=400, text="Bad Request")
        with pytest.raises(Exception, match="Failed to create repository"):
            create_repo("my-org", "my-project", "my-repo", "token")
