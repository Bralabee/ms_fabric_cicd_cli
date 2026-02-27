"""
Git Integration - Thin Wrapper Component 3/5
~60 LOC - Git + Fabric synchronization and branch management

DEPRECATED: The deployer now uses FabricGitAPI (fabric_git_api.py) directly
for workspace-to-Git connections via REST API. This module is retained for
local Git repository validation (branch checks, dirty-state detection) only.

Key Learning Applied: Feature Branch Workflows
- Support feature branch deployments
- Git repository validation
- Fabric workspace <-> Git connection automation
"""

import logging
from typing import Any, Dict, Optional

import git
from git import InvalidGitRepositoryError, Repo

from usf_fabric_cli.exceptions import FabricCLIError

logger = logging.getLogger(__name__)


class GitFabricIntegration:
    """Manages Git repository integration with Fabric workspaces"""

    def __init__(self, fabric_wrapper):
        self.fabric = fabric_wrapper
        self.repo = None

    def initialize_repo(self, repo_path: str = ".") -> Dict[str, Any]:
        """Initialize Git repository connection"""
        try:
            self.repo = Repo(repo_path)
            return {
                "success": True,
                "current_branch": self.repo.active_branch.name,
                "remote_url": self._get_remote_url(),
                "is_dirty": self.repo.is_dirty(),
            }
        except InvalidGitRepositoryError:
            return {
                "success": False,
                "error": f"No Git repository found at {repo_path}",
                "remediation": "Initialize Git repository: git init",
            }

    def validate_branch(self, branch_name: str) -> Dict[str, Any]:
        """Validate that branch exists and is accessible"""
        if not self.repo:
            return {"success": False, "error": "Repository not initialized"}

        try:
            # Check if branch exists locally
            local_branches = [ref.name.split("/")[-1] for ref in self.repo.heads]

            # Check if branch exists on remote
            remote_branches = []
            try:
                remote_branches = [
                    ref.name.split("/")[-1] for ref in self.repo.remote().refs
                ]
            except git.exc.GitCommandError:
                logger.warning("Could not fetch remote branches")

            branch_exists_local = branch_name in local_branches
            branch_exists_remote = branch_name in remote_branches

            return {
                "success": True,
                "branch_name": branch_name,
                "exists_local": branch_exists_local,
                "exists_remote": branch_exists_remote,
                "available": branch_exists_local or branch_exists_remote,
            }

        except (git.exc.GitCommandError, ValueError, OSError) as e:
            return {"success": False, "error": f"Error validating branch: {str(e)}"}

    def create_feature_branch(
        self, branch_name: str, base_branch: str = "main", push_to_remote: bool = False
    ) -> Dict[str, Any]:
        """
        Create and checkout a feature branch.
        Handles checking out existing branches gracefully.
        """
        if not self.repo:
            return {"success": False, "error": "Repository not initialized"}

        try:
            # Fetch latest
            try:
                self.repo.git.fetch("origin")
            except git.exc.GitCommandError as fetch_err:
                logger.warning("Git fetch warning: %s", fetch_err)

            # Check if branch exists
            if branch_name in self.repo.heads:
                logger.info("Branch '%s' exists. Checking out...", branch_name)
                self.repo.heads[branch_name].checkout()
                return {
                    "success": True,
                    "branch_name": branch_name,
                    "message": f"Checked out existing branch: {branch_name}",
                }

            # Create new branch from base
            logger.info(
                "Creating new branch '%s' from '%s'...", branch_name, base_branch
            )
            self.repo.git.checkout(base_branch)
            try:
                self.repo.git.pull("origin", base_branch)
            except git.exc.GitCommandError as exc:
                logger.debug("Ignore pull err (remote may be unreachable): %s", exc)

            new_branch = self.repo.create_head(branch_name)
            new_branch.checkout()

            if push_to_remote:
                logger.info("Pushing branch '%s' to remote...", branch_name)
                self.repo.git.push("--set-upstream", "origin", branch_name)

            return {
                "success": True,
                "branch_name": branch_name,
                "base_branch": base_branch,
                "pushed": push_to_remote,
                "message": f"Created and checked out branch: {branch_name}",
            }

        except (git.exc.GitCommandError, ValueError, OSError) as e:
            return {"success": False, "error": f"Error creating branch: {str(e)}"}

    def connect_workspace_to_git(
        self,
        workspace_id: str,
        git_repo_url: str,
        branch: str = "main",
        directory: str = "/",
    ) -> Dict[str, Any]:
        """Connect Fabric workspace to Git repository"""

        # Validate Git repository URL
        repo_validation = self._validate_git_repo_url(git_repo_url)
        if not repo_validation["success"]:
            return repo_validation

        # Validate branch exists
        branch_validation = self.validate_branch(branch)
        if not branch_validation["available"]:
            return {
                "success": False,
                "error": f"Branch '{branch}' not found",
                "remediation": f"Create branch: git checkout -b {branch}",
            }

        # Connect using Fabric CLI wrapper
        result = self.fabric.connect_git(workspace_id, git_repo_url, branch, directory)

        if result["success"]:
            logger.info(
                "Successfully connected workspace %s to %s:%s",
                workspace_id,
                git_repo_url,
                branch,
            )

        return result

    @staticmethod
    def _validate_workspace_name(name: str) -> None:
        """Validate that a workspace name is Fabric-safe.

        Fabric rejects workspace names containing:
          - Non-ASCII characters (e.g. emoji, accented letters)
          - The characters ``.`` (period) and ``%`` (percent)

        Raises:
            ValueError: If the name contains forbidden characters,
                with a message listing the offending characters.
        """
        forbidden_chars = []
        for ch in name:
            if ord(ch) > 127:
                forbidden_chars.append(repr(ch))
            elif ch in ".%":
                forbidden_chars.append(repr(ch))

        if forbidden_chars:
            unique = sorted(set(forbidden_chars))
            raise ValueError(
                f"Workspace name contains characters not allowed by Fabric: "
                f"{', '.join(unique)}. "
                f"Fabric rejects non-ASCII characters and the symbols '.' / '%' "
                f"in workspace names with schema-enabled lakehouses. "
                f"Got: {name!r}"
            )

    @staticmethod
    def get_workspace_name_from_branch(
        base_workspace_name: str,
        branch: str,
        feature_prefix: str = "[F]",
    ) -> str:
        """Generate workspace name for feature branch.

        Naming convention:
          - Display names (contain spaces): prepend feature_prefix + append
            [FEATURE-<desc>]
            e.g. "Sales Report" + feature/fix-bug
              → "[F] Sales Report [FEATURE-fix-bug]"
          - Slug names (no spaces): append -feature-<desc>
            e.g. "my-project" + feature/fix-bug
              → "my-project-feature-fix-bug"

        The feature_prefix (default "[F]") provides instant visual
        identification of feature workspaces in the Fabric portal
        sidebar.  Set to empty string "" to disable.

        Note: The prefix must use only ASCII characters — Fabric
        rejects non-ASCII characters (e.g. emoji) and the symbols
        ``.`` / ``%`` in workspace names that contain schema-enabled
        lakehouses.

        Slashes are replaced with hyphens inside bracket notation because
        the Fabric CLI interprets '/' as a path separator, which breaks
        ``fab get`` and ``fab acl set`` operations.

        This keeps feature workspaces visually aligned with their
        parent [DEV]/[TEST]/[PROD] workspaces.

        Raises:
            ValueError: If the feature_prefix or final workspace name
                contains non-ASCII characters or forbidden symbols.
        """
        import re

        # Validate prefix early to fail fast on bad input
        if feature_prefix:
            GitFabricIntegration._validate_workspace_name(feature_prefix)

        if branch == "main" or branch == "master":
            return base_workspace_name

        # Strip any existing [ENV] tag from the base name
        base_clean = re.sub(r"\s*\[.*?\]\s*$", "", base_workspace_name).strip()

        # Extract description (strip feature/ prefix if present)
        branch_desc = branch
        if branch.startswith("feature/"):
            branch_desc = branch[len("feature/") :]

        # Display names (contain spaces) → bracket notation [FEATURE-<desc>]
        # Replace '/' with '-' — Fabric CLI treats '/' as a path separator
        if " " in base_clean:
            safe_desc = branch_desc.replace("/", "-")
            prefix = f"{feature_prefix} " if feature_prefix else ""
            result = f"{prefix}{base_clean} [FEATURE-{safe_desc}]"
            GitFabricIntegration._validate_workspace_name(result)
            return result

        # Slug names → hyphen notation (legacy behavior, no prefix)
        sanitized_branch = branch.replace("/", "-").replace("_", "-").lower()
        result = f"{base_clean}-{sanitized_branch}"
        GitFabricIntegration._validate_workspace_name(result)
        return result

    def sync_workspace_with_git(self, workspace_id: str) -> Dict[str, Any]:
        """Sync Fabric workspace with Git repository"""
        try:
            # Use Fabric CLI to sync
            command = ["git", "sync", "--workspace-id", workspace_id]
            result = self.fabric._execute_command(command)

            if result.get("success"):
                return {
                    "success": True,
                    "message": "Workspace synced with Git repository",
                }
            return result
        except FabricCLIError as exc:
            return {"success": False, "error": str(exc)}
        except (git.exc.GitCommandError, ValueError, OSError) as e:
            return {"success": False, "error": f"Error syncing workspace: {str(e)}"}

    def _get_remote_url(self) -> Optional[str]:
        """Get Git remote URL"""
        if not self.repo:
            return None

        try:
            remote = self.repo.remote("origin")
            return remote.url
        except git.exc.GitCommandError:
            return None

    def _validate_git_repo_url(self, repo_url: str) -> Dict[str, Any]:
        """Validate Git repository URL is accessible"""

        # Basic URL validation
        if not repo_url or not isinstance(repo_url, str):
            return {"success": False, "error": "Invalid repository URL"}

        # Check URL format
        valid_patterns = [
            repo_url.startswith("https://github.com/"),
            repo_url.startswith("https://dev.azure.com/"),
            repo_url.startswith("git@github.com:"),
            repo_url.startswith("git@ssh.dev.azure.com:"),
        ]

        if not any(valid_patterns):
            return {
                "success": False,
                "error": "Unsupported Git repository URL format",
                "remediation": "Use GitHub or Azure DevOps repository URL",
            }

        # Attempt repository accessibility check using git ls-remote
        try:
            import subprocess

            result = subprocess.run(
                ["git", "ls-remote", "--exit-code", repo_url],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                error_detail = (
                    result.stderr.strip() if result.stderr else "Unknown error"
                )
                return {
                    "success": False,
                    "error": f"Repository not accessible: {error_detail}",
                    "remediation": (
                        "Check repository URL and authentication credentials"
                    ),
                }
        except subprocess.TimeoutExpired:
            logger.warning("Repository accessibility check timed out for: %s", repo_url)
            # Continue anyway - let Fabric API handle final validation
        except FileNotFoundError:
            logger.warning("git command not found - skipping accessibility check")
        except (git.exc.GitCommandError, ValueError, OSError) as e:
            logger.debug("Repository accessibility check failed: %s", e)
            # Continue anyway - non-critical for basic validation

        return {"success": True, "repository_url": repo_url}

    def get_current_git_info(self) -> Dict[str, Any]:
        """Get current Git repository information"""
        if not self.repo:
            return {"success": False, "error": "Repository not initialized"}

        try:
            current_branch = self.repo.active_branch.name
            remote_url = self._get_remote_url()
            is_dirty = self.repo.is_dirty()

            # Get latest commit info
            latest_commit = self.repo.head.commit

            return {
                "success": True,
                "current_branch": current_branch,
                "remote_url": remote_url,
                "is_dirty": is_dirty,
                "latest_commit": {
                    "hash": latest_commit.hexsha[:8],
                    "message": latest_commit.message.strip(),
                    "author": str(latest_commit.author),
                    "date": latest_commit.committed_datetime.isoformat(),
                },
            }

        except (git.exc.GitCommandError, ValueError, OSError) as e:
            return {"success": False, "error": f"Error getting Git info: {str(e)}"}
