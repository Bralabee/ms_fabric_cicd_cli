"""
Git Integration - Thin Wrapper Component 3/5
~60 LOC - Git + Fabric synchronization and branch management

Key Learning Applied: Feature Branch Workflows
- Support feature branch deployments
- Git repository validation
- Fabric workspace <-> Git connection automation
"""

import logging
from typing import Dict, Any, Optional

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
            except Exception:
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

        except Exception as e:
            return {"success": False, "error": f"Error validating branch: {str(e)}"}

    def create_feature_branch(
        self, branch_name: str, base_branch: str = "main"
    ) -> Dict[str, Any]:
        """Create and checkout a feature branch"""
        if not self.repo:
            return {"success": False, "error": "Repository not initialized"}

        try:
            # Ensure we're on the base branch and it's up to date
            self.repo.git.checkout(base_branch)

            # Try to pull latest changes
            try:
                self.repo.git.pull("origin", base_branch)
            except Exception as e:
                logger.warning(f"Could not pull latest changes: {e}")

            # Create and checkout new branch
            new_branch = self.repo.create_head(branch_name)
            new_branch.checkout()

            return {
                "success": True,
                "branch_name": branch_name,
                "base_branch": base_branch,
                "message": f"Created and checked out branch: {branch_name}",
            }

        except Exception as e:
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
                f"Successfully connected workspace {workspace_id} to {git_repo_url}:{branch}"
            )

        return result

    def get_workspace_name_from_branch(
        self, base_workspace_name: str, branch: str
    ) -> str:
        """Generate workspace name for feature branch"""
        if branch == "main" or branch == "master":
            return base_workspace_name

        # For feature branches, append branch name (sanitized)
        sanitized_branch = branch.replace("/", "-").replace("_", "-").lower()
        return f"{base_workspace_name}-{sanitized_branch}"

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
        except Exception as e:
            return {"success": False, "error": f"Error syncing workspace: {str(e)}"}

    def _get_remote_url(self) -> Optional[str]:
        """Get Git remote URL"""
        if not self.repo:
            return None

        try:
            remote = self.repo.remote("origin")
            return remote.url
        except Exception:
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
                error_detail = result.stderr.strip() if result.stderr else "Unknown error"
                return {
                    "success": False,
                    "error": f"Repository not accessible: {error_detail}",
                    "remediation": "Check repository URL and authentication credentials",
                }
        except subprocess.TimeoutExpired:
            logger.warning(f"Repository accessibility check timed out for: {repo_url}")
            # Continue anyway - let Fabric API handle final validation
        except FileNotFoundError:
            logger.warning("git command not found - skipping accessibility check")
        except Exception as e:
            logger.debug(f"Repository accessibility check failed: {e}")
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

        except Exception as e:
            return {"success": False, "error": f"Error getting Git info: {str(e)}"}
