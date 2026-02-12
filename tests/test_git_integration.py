"""
Unit tests for GitFabricIntegration.

Tests verify:
- Workspace name derivation from branches
- Repository initialization
- Branch validation
- Git URL validation
- Feature branch creation
- Workspace-to-Git connection
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from usf_fabric_cli.services.git_integration import GitFabricIntegration


class TestGetWorkspaceNameFromBranch:
    """Tests for workspace name derivation from branch names."""

    def setup_method(self):
        self.git = GitFabricIntegration(fabric_wrapper=MagicMock())

    def test_main_returns_base_name(self):
        """Main branch returns base workspace name unchanged."""
        result = self.git.get_workspace_name_from_branch("my-workspace", "main")
        assert result == "my-workspace"

    def test_master_returns_base_name(self):
        """Master branch returns base workspace name unchanged."""
        result = self.git.get_workspace_name_from_branch("my-workspace", "master")
        assert result == "my-workspace"

    def test_feature_branch_appends_sanitized_suffix(self):
        """Feature branches append a sanitized branch name."""
        result = self.git.get_workspace_name_from_branch(
            "my-workspace", "feature/add-auth"
        )
        assert result == "my-workspace-feature-add-auth"

    def test_underscores_replaced_with_hyphens(self):
        """Underscores in branch names should be replaced with hyphens."""
        result = self.git.get_workspace_name_from_branch("ws", "fix_bug_123")
        assert result == "ws-fix-bug-123"

    def test_branch_name_lowercased(self):
        """Branch names should be lowercased."""
        result = self.git.get_workspace_name_from_branch("ws", "Feature/MyFeature")
        assert result == "ws-feature-myfeature"

    def test_nested_branch_slashes_replaced(self):
        """Nested branch paths should have slashes replaced with hyphens."""
        result = self.git.get_workspace_name_from_branch("ws", "feature/team/auth")
        assert result == "ws-feature-team-auth"


class TestInitializeRepo:
    """Tests for Git repository initialization."""

    def setup_method(self):
        self.git = GitFabricIntegration(fabric_wrapper=MagicMock())

    @patch("usf_fabric_cli.services.git_integration.Repo")
    def test_valid_repo(self, mock_repo_class):
        """Should return success with repository info."""
        mock_repo = MagicMock()
        mock_repo.active_branch.name = "main"
        mock_repo.is_dirty.return_value = False
        mock_repo.remote.return_value.url = "https://github.com/org/repo"
        mock_repo_class.return_value = mock_repo

        result = self.git.initialize_repo("/valid/path")

        assert result["success"] is True
        assert result["current_branch"] == "main"
        assert result["is_dirty"] is False

    @patch("usf_fabric_cli.services.git_integration.Repo")
    def test_invalid_repo_path(self, mock_repo_class):
        """Should return failure for invalid Git repository path."""
        from git import InvalidGitRepositoryError

        mock_repo_class.side_effect = InvalidGitRepositoryError("/bad/path")

        result = self.git.initialize_repo("/bad/path")

        assert result["success"] is False
        assert "No Git repository" in result["error"]
        assert "remediation" in result


class TestValidateBranch:
    """Tests for branch validation."""

    def setup_method(self):
        self.git = GitFabricIntegration(fabric_wrapper=MagicMock())

    def test_no_repo_initialized(self):
        """Should fail if repo is not initialized."""
        result = self.git.validate_branch("main")
        assert result["success"] is False
        assert "not initialized" in result["error"]

    def test_branch_exists_locally(self):
        """Should detect locally available branches."""
        mock_repo = MagicMock()
        mock_head = MagicMock()
        mock_head.name = "main"
        mock_repo.heads = [mock_head]
        mock_repo.remote.return_value.refs = []
        self.git.repo = mock_repo

        result = self.git.validate_branch("main")
        assert result["success"] is True
        assert result["exists_local"] is True
        assert result["available"] is True

    def test_branch_not_found(self):
        """Should report branch not available."""
        mock_repo = MagicMock()
        mock_repo.heads = []
        mock_repo.remote.return_value.refs = []
        self.git.repo = mock_repo

        result = self.git.validate_branch("nonexistent")
        assert result["success"] is True
        assert result["available"] is False


class TestValidateGitRepoUrl:
    """Tests for Git repository URL validation."""

    def setup_method(self):
        self.git = GitFabricIntegration(fabric_wrapper=MagicMock())

    @patch("subprocess.run")
    def test_github_https_url(self, mock_run):
        """Should accept GitHub HTTPS URLs."""
        mock_run.return_value = Mock(returncode=0)

        result = self.git._validate_git_repo_url("https://github.com/org/repo")
        assert result["success"] is True

    @patch("subprocess.run")
    def test_ado_https_url(self, mock_run):
        """Should accept Azure DevOps HTTPS URLs."""
        mock_run.return_value = Mock(returncode=0)
        ado_url = "https://dev.azure.com/org/proj/_git/repo"
        result = self.git._validate_git_repo_url(ado_url)
        assert result["success"] is True

    def test_invalid_url_format(self):
        """Should reject unsupported URL formats."""
        result = self.git._validate_git_repo_url("https://gitlab.com/org/repo")
        assert result["success"] is False
        assert "Unsupported" in result["error"]

    def test_empty_url(self):
        """Should reject empty URLs."""
        result = self.git._validate_git_repo_url("")
        assert result["success"] is False

    def test_none_url(self):
        """Should reject None URLs."""
        result = self.git._validate_git_repo_url(None)
        assert result["success"] is False

    @patch("subprocess.run")
    def test_github_ssh_url(self, mock_run):
        """Should accept GitHub SSH URLs."""
        mock_run.return_value = Mock(returncode=0)

        result = self.git._validate_git_repo_url("git@github.com:org/repo")
        assert result["success"] is True


class TestCreateFeatureBranch:
    """Tests for feature branch creation."""

    def setup_method(self):
        self.git = GitFabricIntegration(fabric_wrapper=MagicMock())

    def test_no_repo_initialized(self):
        """Should fail if repo is not initialized."""
        result = self.git.create_feature_branch("feature/test")
        assert result["success"] is False
        assert "not initialized" in result["error"]

    def test_existing_branch_checkout(self):
        """Should checkout existing branch instead of creating."""
        mock_repo = MagicMock()
        mock_branch = MagicMock()
        mock_heads = MagicMock()
        mock_heads.__contains__ = MagicMock(return_value=True)
        mock_heads.__getitem__ = MagicMock(return_value=mock_branch)
        mock_repo.heads = mock_heads
        self.git.repo = mock_repo

        result = self.git.create_feature_branch("feature/test")
        assert result["success"] is True
        assert "existing" in result["message"].lower()

    def test_new_branch_creation(self):
        """Should create and checkout a new branch."""
        mock_repo = MagicMock()
        mock_repo.heads = MagicMock()
        mock_repo.heads.__contains__ = MagicMock(return_value=False)
        new_branch = MagicMock()
        mock_repo.create_head.return_value = new_branch
        self.git.repo = mock_repo

        result = self.git.create_feature_branch("feature/new", "main")
        assert result["success"] is True
        mock_repo.create_head.assert_called_once_with("feature/new")
        new_branch.checkout.assert_called_once()


class TestConnectWorkspaceToGit:
    """Tests for workspace-to-Git connection."""

    def setup_method(self):
        self.mock_fabric = MagicMock()
        self.git = GitFabricIntegration(fabric_wrapper=self.mock_fabric)

    def test_invalid_url_stops_connection(self):
        """Should not attempt connection with invalid URL."""
        result = self.git.connect_workspace_to_git(
            workspace_id="ws-123",
            git_repo_url="https://invalid.com/repo",
        )
        assert result["success"] is False
        self.mock_fabric.connect_git.assert_not_called()


class TestSyncWorkspaceWithGit:
    """Tests for workspace-Git sync."""

    def setup_method(self):
        self.mock_fabric = MagicMock()
        self.git = GitFabricIntegration(fabric_wrapper=self.mock_fabric)

    def test_sync_success(self):
        """Should return success on successful sync."""
        self.mock_fabric._execute_command.return_value = {"success": True}

        result = self.git.sync_workspace_with_git("ws-123")
        assert result["success"] is True

    def test_sync_failure(self):
        """Should return failure details on error."""
        self.mock_fabric._execute_command.side_effect = Exception("Network error")

        result = self.git.sync_workspace_with_git("ws-123")
        assert result["success"] is False
        assert "Network error" in result["error"]


class TestGetCurrentGitInfo:
    """Tests for getting current Git info."""

    def setup_method(self):
        self.git = GitFabricIntegration(fabric_wrapper=MagicMock())

    def test_no_repo(self):
        """Should return error if repo not initialized."""
        result = self.git.get_current_git_info()
        assert result["success"] is False
        assert "not initialized" in result["error"]

    def test_with_repo(self):
        """Should return full repo information."""
        mock_repo = MagicMock()
        mock_repo.active_branch.name = "main"
        mock_repo.is_dirty.return_value = True
        mock_repo.remote.return_value.url = "https://github.com/org/repo"

        mock_commit = MagicMock()
        mock_commit.hexsha = "abcdef1234567890"
        mock_commit.message = "test commit"
        mock_commit.author = "Test Author"
        mock_commit.committed_datetime.isoformat.return_value = "2026-01-01T00:00:00"
        mock_repo.head.commit = mock_commit

        self.git.repo = mock_repo

        result = self.git.get_current_git_info()
        assert result["success"] is True
        assert result["current_branch"] == "main"
        assert result["is_dirty"] is True
        assert result["latest_commit"]["hash"] == "abcdef12"


if __name__ == "__main__":
    pytest.main([__file__])
