"""
Unit tests for FabricDeployer — the core deployment orchestrator.

Tests cover initialization, deploy orchestration, workspace creation,
item creation, principal assignment, domain assignment, Git connection,
and deployment summary.
"""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**overrides):
    """Return a minimal config SimpleNamespace mirroring ConfigManager output."""
    defaults = {
        "name": "test-workspace",
        "display_name": "Test Workspace",
        "description": "A test workspace",
        "capacity_id": "test-capacity",
        "domain": None,
        "git_repo": None,
        "git_branch": "main",
        "git_directory": "/",
        "folders": ["Bronze", "Silver"],
        "lakehouses": [{"name": "raw", "folder": "Bronze", "description": "Raw"}],
        "warehouses": [],
        "notebooks": [{"name": "nb1", "folder": "Silver"}],
        "pipelines": [],
        "semantic_models": [],
        "resources": [],
        "principals": [
            {"id": "user-1", "role": "Admin"},
        ],
        "deployment_pipeline": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _build_deployer(config=None, secrets=None):
    """Construct a FabricDeployer with fully-mocked dependencies."""
    with patch("dotenv.load_dotenv"):
        with patch("usf_fabric_cli.services.deployer.ConfigManager") as MockCM:
            cm = MockCM.return_value
            cm.load_config.return_value = config or _make_config()
            cm.config_path = "/fake/config.yaml"

            with patch("usf_fabric_cli.services.deployer.FabricSecrets") as MockSecrets:
                sec = secrets or MagicMock()
                sec.validate_fabric_auth.return_value = (True, "")
                sec.fabric_token = "fake-token"
                sec.azure_client_id = "cid"
                sec.azure_client_secret = "csecret"  # pragma: allowlist secret
                sec.tenant_id = "tid"
                MockSecrets.load_with_fallback.return_value = sec

                with patch(
                    "usf_fabric_cli.services.deployer.get_environment_variables",
                    return_value={"FABRIC_TOKEN": "fake-token"},
                ):
                    with patch(
                        "usf_fabric_cli.services.deployer.FabricCLIWrapper"
                    ) as MockWrapper:
                        with patch(
                            "usf_fabric_cli.services.deployer.GitFabricIntegration"
                        ):
                            with patch("usf_fabric_cli.services.deployer.FabricGitAPI"):
                                with patch(
                                    "usf_fabric_cli.services.deployer.AuditLogger"
                                ):
                                    from usf_fabric_cli.services.deployer import (
                                        FabricDeployer,
                                    )

                                    deployer = FabricDeployer.__new__(FabricDeployer)
                                    deployer.config_manager = cm
                                    deployer.config = cm.load_config.return_value
                                    deployer.environment = "dev"
                                    deployer.secrets = sec
                                    deployer.fabric = MockWrapper.return_value
                                    deployer.git = MagicMock()
                                    deployer.git_api = MagicMock()
                                    deployer.pipeline_api = MagicMock()
                                    deployer.audit = MagicMock()
                                    deployer.workspace_id = None
                                    deployer.items_created = 0
                                    deployer.deployment_state = MagicMock()
                                    deployer._effective_workspace_name = (
                                        deployer.config.name
                                    )
                                    deployer._git_browse_url = None
                                    return deployer


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFabricDeployerInit:
    """Tests for deployer construction and config loading."""

    @patch.dict(os.environ, {"FABRIC_TOKEN": "tok"}, clear=False)
    def test_init_loads_config(self):
        deployer = _build_deployer()
        assert deployer.config.name == "test-workspace"
        assert deployer.environment == "dev"

    @patch.dict(os.environ, {"FABRIC_TOKEN": "tok"}, clear=False)
    def test_init_sets_workspace_id_none(self):
        deployer = _build_deployer()
        assert deployer.workspace_id is None
        assert deployer.items_created == 0


class TestCreateWorkspace:
    """Tests for _create_workspace."""

    def test_create_workspace_success(self):
        deployer = _build_deployer()
        deployer.fabric.create_workspace.return_value = {
            "success": True,
            "workspace_id": "ws-123",
        }

        result = deployer._create_workspace("test-ws")

        assert result["success"] is True
        assert deployer.workspace_id == "ws-123"
        deployer.audit.log_workspace_creation.assert_called_once()

    def test_create_workspace_capacity_fallback(self):
        """When capacity fails, deployer retries without capacity."""
        deployer = _build_deployer()
        # First call: capacity failure
        deployer.fabric.create_workspace.side_effect = [
            {
                "success": False,
                "error": "Capacity EntityNotFound",
                "data": {"errorCode": "EntityNotFound"},
            },
            {"success": True, "workspace_id": "ws-456"},
        ]

        result = deployer._create_workspace("test-ws")

        assert result["success"] is True
        assert deployer.fabric.create_workspace.call_count == 2
        # Second call should have capacity_name=None
        second_call = deployer.fabric.create_workspace.call_args_list[1]
        assert second_call.kwargs.get("capacity_name") is None

    def test_create_workspace_failure(self):
        deployer = _build_deployer()
        deployer.fabric.create_workspace.return_value = {
            "success": False,
            "error": "Permission denied",
            "data": {},
        }

        result = deployer._create_workspace("test-ws")

        assert result["success"] is False
        assert deployer.workspace_id is None


class TestCreateFolders:
    """Tests for _create_folders."""

    def test_create_folders(self):
        deployer = _build_deployer()
        deployer.fabric.create_folder.return_value = {"success": True}

        deployer._create_folders()

        assert deployer.fabric.create_folder.call_count == 2
        deployer.fabric.create_folder.assert_any_call("test-workspace", "Bronze")
        deployer.fabric.create_folder.assert_any_call("test-workspace", "Silver")

    def test_create_folders_empty(self):
        config = _make_config(folders=[])
        deployer = _build_deployer(config=config)

        deployer._create_folders()

        deployer.fabric.create_folder.assert_not_called()


class TestCreateItems:
    """Tests for _create_items — all 6 item types."""

    def test_creates_lakehouses(self):
        deployer = _build_deployer()
        deployer.fabric.create_lakehouse.return_value = {"success": True}
        deployer.fabric.create_notebook.return_value = {"success": True}

        deployer._create_items()

        deployer.fabric.create_lakehouse.assert_called_once_with(
            "test-workspace", "raw", "Raw", folder="Bronze"
        )

    def test_creates_notebooks(self):
        deployer = _build_deployer()
        deployer.fabric.create_lakehouse.return_value = {"success": True}
        deployer.fabric.create_notebook.return_value = {"success": True}

        deployer._create_items()

        deployer.fabric.create_notebook.assert_called_once_with(
            "test-workspace", "nb1", None, folder="Silver"
        )

    def test_creates_warehouses(self):
        config = _make_config(
            lakehouses=[],
            notebooks=[],
            warehouses=[{"name": "wh1", "description": "WH", "folder": "Gold"}],
        )
        deployer = _build_deployer(config=config)
        deployer.fabric.create_warehouse.return_value = {"success": True}

        deployer._create_items()

        deployer.fabric.create_warehouse.assert_called_once_with(
            "test-workspace", "wh1", "WH", folder="Gold"
        )

    def test_creates_pipelines(self):
        config = _make_config(
            lakehouses=[],
            notebooks=[],
            pipelines=[{"name": "pipe1", "description": "P"}],
        )
        deployer = _build_deployer(config=config)
        deployer.fabric.create_pipeline.return_value = {"success": True}

        deployer._create_items()

        deployer.fabric.create_pipeline.assert_called_once()

    def test_creates_semantic_models(self):
        config = _make_config(
            lakehouses=[],
            notebooks=[],
            semantic_models=[{"name": "sm1", "description": "SM"}],
        )
        deployer = _build_deployer(config=config)
        deployer.fabric.create_semantic_model.return_value = {"success": True}

        deployer._create_items()

        deployer.fabric.create_semantic_model.assert_called_once()

    def test_creates_generic_resources(self):
        config = _make_config(
            lakehouses=[],
            notebooks=[],
            resources=[
                {
                    "type": "Eventstream",
                    "name": "es1",
                    "description": "ES",
                    "folder": "Streams",
                }
            ],
        )
        deployer = _build_deployer(config=config)
        deployer.fabric.create_item.return_value = {"success": True}

        deployer._create_items()

        deployer.fabric.create_item.assert_called_once_with(
            "test-workspace", "es1", "Eventstream", "ES", folder="Streams"
        )

    def test_items_created_counter(self):
        deployer = _build_deployer()
        deployer.fabric.create_lakehouse.return_value = {"success": True}
        deployer.fabric.create_notebook.return_value = {"success": True}

        deployer._create_items()

        assert deployer.items_created == 2

    def test_reused_items_not_counted(self):
        deployer = _build_deployer()
        deployer.fabric.create_lakehouse.return_value = {
            "success": True,
            "reused": True,
        }
        deployer.fabric.create_notebook.return_value = {
            "success": True,
            "reused": True,
        }

        deployer._create_items()

        assert deployer.items_created == 0


class TestAddPrincipals:
    """Tests for _add_principals."""

    def test_add_single_principal(self):
        deployer = _build_deployer()
        deployer.fabric.add_workspace_principal.return_value = {"success": True}

        deployer._add_principals()

        deployer.fabric.add_workspace_principal.assert_called_once_with(
            "test-workspace", "user-1", "Admin"
        )

    def test_add_comma_separated_principals(self):
        config = _make_config(principals=[{"id": "id1,id2,id3", "role": "Contributor"}])
        deployer = _build_deployer(config=config)
        deployer.fabric.add_workspace_principal.return_value = {"success": True}

        deployer._add_principals()

        assert deployer.fabric.add_workspace_principal.call_count == 3

    def test_skip_empty_principal_id(self):
        config = _make_config(principals=[{"id": "", "role": "Admin"}])
        deployer = _build_deployer(config=config)

        deployer._add_principals()

        deployer.fabric.add_workspace_principal.assert_not_called()

    def test_no_principals_configured(self):
        config = _make_config(principals=[])
        deployer = _build_deployer(config=config)

        deployer._add_principals()

        deployer.fabric.add_workspace_principal.assert_not_called()


class TestAssignDomain:
    """Tests for _assign_domain."""

    def test_assign_domain_success(self):
        config = _make_config(domain="analytics")
        deployer = _build_deployer(config=config)
        deployer.fabric.assign_to_domain.return_value = {"success": True}

        deployer._assign_domain()

        deployer.fabric.assign_to_domain.assert_called_once_with(
            "test-workspace", "analytics"
        )

    def test_skip_unresolved_domain(self):
        config = _make_config(domain="${FABRIC_DOMAIN_NAME}")
        deployer = _build_deployer(config=config)

        deployer._assign_domain()

        deployer.fabric.assign_to_domain.assert_not_called()

    def test_no_domain_configured(self):
        deployer = _build_deployer()
        assert deployer.config.domain is None

        deployer._assign_domain()

        deployer.fabric.assign_to_domain.assert_not_called()


class TestParseGitRepoUrl:
    """Tests for _parse_git_repo_url."""

    def test_parse_github_url(self):
        deployer = _build_deployer()
        result = deployer._parse_git_repo_url("https://github.com/myorg/myrepo")

        assert result is not None
        assert result["owner"] == "myorg"
        assert result["repo"] == "myrepo"

    def test_parse_github_url_with_git_suffix(self):
        deployer = _build_deployer()
        result = deployer._parse_git_repo_url("https://github.com/owner/repo.git")

        assert result is not None
        assert result["owner"] == "owner"
        assert result["repo"] == "repo"

    def test_parse_ado_url(self):
        deployer = _build_deployer()
        result = deployer._parse_git_repo_url(
            "https://dev.azure.com/myorg/myproject/_git/myrepo"
        )

        assert result is not None
        assert result["organization"] == "myorg"
        assert result["project"] == "myproject"
        assert result["repo"] == "myrepo"

    def test_parse_invalid_url_returns_none(self):
        deployer = _build_deployer()
        result = deployer._parse_git_repo_url("not-a-url")

        assert result is None


class TestGitHubDuplicateConnectionRecovery:
    """Tests for GitHub duplicate connection fallback in _connect_git.

    Verifies the fix where GitHub connections that fail with 409
    DuplicateConnectionName now recover by looking up the existing
    connection (matching the Azure DevOps behavior).
    """

    def test_github_duplicate_connection_recovers_existing(self):
        """When GitHub connection creation returns 409 DuplicateConnectionName,
        deployer should look up existing connection and use its ID."""
        config = _make_config(git_repo="https://github.com/test-org/test-repo")
        deployer = _build_deployer(config=config)
        deployer.workspace_id = "ws-123"
        deployer._effective_workspace_name = "test-workspace"

        # Mock secrets with a GitHub token
        deployer.secrets.github_token = "ghp_test_token"
        deployer.secrets.validate_git_auth.return_value = (True, "")

        # Step 1: create_git_connection returns 409 conflict
        deployer.git_api.create_git_connection.return_value = {
            "success": False,
            "duplicate": True,
            "error": "409 Client Error: Conflict for url",
            "response": (
                '{"errorCode":"DuplicateConnectionName","message":'
                '"The connection DisplayName input is already being '
                'used by another connection"}'
            ),
        }

        # Step 2: get_connection_by_name finds existing connection
        deployer.git_api.get_connection_by_name.return_value = {
            "id": "existing-conn-id-123",
            "displayName": "GitHub-test-workspace",
        }

        # Step 3: connect_workspace_to_git succeeds with the found ID
        deployer.git_api.connect_workspace_to_git.return_value = {
            "success": True,
            "message": "Workspace connected to Git",
        }
        deployer.git_api.initialize_git_connection.return_value = {
            "success": True,
            "required_action": "None",
        }

        deployer._connect_git(branch="main")

        # Verify it looked up the existing connection
        deployer.git_api.get_connection_by_name.assert_called_once_with(
            "GitHub-test-workspace"
        )

        # Verify connect_workspace_to_git was called with the recovered ID
        call_kwargs = deployer.git_api.connect_workspace_to_git.call_args.kwargs
        assert call_kwargs["connection_id"] == "existing-conn-id-123"

    def test_github_duplicate_connection_not_found_continues(self):
        """When GitHub 409 occurs but lookup finds nothing, should continue
        with connection_id=None (SSO fallback)."""
        config = _make_config(git_repo="https://github.com/org/repo")
        deployer = _build_deployer(config=config)
        deployer.workspace_id = "ws-123"
        deployer._effective_workspace_name = "test-workspace"

        deployer.secrets.github_token = "ghp_test_token"
        deployer.secrets.validate_git_auth.return_value = (True, "")

        # create_git_connection returns 409
        deployer.git_api.create_git_connection.return_value = {
            "success": False,
            "duplicate": True,
            "error": "409 Client Error: Conflict for url",
            "response": '{"errorCode":"DuplicateConnectionName"}',
        }

        # get_connection_by_name returns None
        deployer.git_api.get_connection_by_name.return_value = None

        # connect_workspace_to_git still called (with None connection_id)
        deployer.git_api.connect_workspace_to_git.return_value = {
            "success": True,
            "message": "Connected",
        }
        deployer.git_api.initialize_git_connection.return_value = {
            "success": True,
            "required_action": "None",
        }

        deployer._connect_git(branch="main")

        # connect_workspace_to_git should still be called (SSO fallback)
        deployer.git_api.connect_workspace_to_git.assert_called_once()
        call_kwargs = deployer.git_api.connect_workspace_to_git.call_args.kwargs
        assert call_kwargs["connection_id"] is None


class TestDeployOrchestration:
    """Tests for the top-level deploy() method."""

    def test_deploy_success(self):
        deployer = _build_deployer()
        deployer.fabric.create_workspace.return_value = {
            "success": True,
            "workspace_id": "ws-1",
        }
        deployer.fabric.create_folder.return_value = {"success": True}
        deployer.fabric.create_lakehouse.return_value = {"success": True}
        deployer.fabric.create_notebook.return_value = {"success": True}
        deployer.fabric.add_workspace_principal.return_value = {"success": True}

        result = deployer.deploy()

        assert result is True
        deployer.audit.log_deployment_start.assert_called_once()
        deployer.audit.log_deployment_complete.assert_called_once()

    def test_deploy_workspace_failure_returns_false(self):
        deployer = _build_deployer()
        deployer.deployment_state.item_count = 0
        deployer.fabric.create_workspace.return_value = {
            "success": False,
            "error": "Permission denied",
            "data": {},
        }

        result = deployer.deploy()

        assert result is False

    def test_deploy_with_branch_creates_branch_workspace(self):
        deployer = _build_deployer()
        deployer.git.get_workspace_name_from_branch.return_value = (
            "test-workspace-feature-x"
        )
        deployer.fabric.create_workspace.return_value = {
            "success": True,
            "workspace_id": "ws-branch",
        }
        deployer.fabric.create_folder.return_value = {"success": True}
        deployer.fabric.create_lakehouse.return_value = {"success": True}
        deployer.fabric.create_notebook.return_value = {"success": True}
        deployer.fabric.add_workspace_principal.return_value = {"success": True}

        result = deployer.deploy(branch="feature/x", force_branch_workspace=True)

        assert result is True
        deployer.fabric.create_workspace.assert_called_once_with(
            name="test-workspace-feature-x",
            capacity_name="test-capacity",
            description="A test workspace",
        )

    def test_deploy_triggers_git_connect_when_configured(self):
        config = _make_config(git_repo="https://github.com/org/repo")
        deployer = _build_deployer(config=config)
        deployer.fabric.create_workspace.return_value = {
            "success": True,
            "workspace_id": "ws-1",
        }
        deployer.fabric.create_folder.return_value = {"success": True}
        deployer.fabric.create_lakehouse.return_value = {"success": True}
        deployer.fabric.create_notebook.return_value = {"success": True}
        deployer.fabric.add_workspace_principal.return_value = {"success": True}

        result = deployer.deploy()

        assert result is True

    def test_deploy_skips_domain_when_none(self):
        deployer = _build_deployer()
        deployer.fabric.create_workspace.return_value = {
            "success": True,
            "workspace_id": "ws-1",
        }
        deployer.fabric.create_folder.return_value = {"success": True}
        deployer.fabric.create_lakehouse.return_value = {"success": True}
        deployer.fabric.create_notebook.return_value = {"success": True}
        deployer.fabric.add_workspace_principal.return_value = {"success": True}

        result = deployer.deploy()

        assert result is True
        deployer.fabric.assign_to_domain.assert_not_called()


class TestDeploymentPipelineSetup:
    """Tests for _setup_deployment_pipeline in the deploy flow."""

    def _make_pipeline_config(self):
        """Return a deployment_pipeline config dict."""
        return {
            "pipeline_name": "my-pipeline",
            "stages": {
                "development": {"workspace_name": "ws-dev"},
                "test": {
                    "workspace_name": "ws-test",
                    "capacity_id": "cap-test",
                },
                "production": {
                    "workspace_name": "ws-prod",
                    "capacity_id": "cap-prod",
                },
            },
        }

    def test_setup_creates_pipeline_and_assigns_stages(self):
        """Pipeline created, workspaces created/found, all assigned."""
        config = _make_config(deployment_pipeline=self._make_pipeline_config())
        deployer = _build_deployer(config=config)
        deployer.workspace_id = "ws-dev-id"

        # Pipeline does not exist yet → create
        deployer.pipeline_api.get_pipeline_by_name.return_value = None
        deployer.pipeline_api.create_pipeline.return_value = {
            "success": True,
            "pipeline": {"id": "pipe-123"},
        }

        # Return 3 stages
        deployer.pipeline_api.get_pipeline_stages.return_value = {
            "success": True,
            "stages": [
                {"displayName": "development", "id": "stage-dev"},
                {"displayName": "test", "id": "stage-test"},
                {"displayName": "production", "id": "stage-prod"},
            ],
        }

        # Test + Prod workspaces created
        deployer.fabric.create_workspace.return_value = {
            "success": True,
            "workspace_id": "ws-new-id",
        }
        deployer.pipeline_api.assign_workspace_to_stage.return_value = {
            "success": True,
        }

        deployer._setup_deployment_pipeline("ws-dev")

        deployer.pipeline_api.create_pipeline.assert_called_once()
        # Dev uses existing ws_id, Test + Prod use create_workspace
        assert deployer.fabric.create_workspace.call_count == 2
        assert deployer.pipeline_api.assign_workspace_to_stage.call_count == 3

    def test_setup_reuses_existing_pipeline(self):
        """Pipeline already exists — skips creation."""
        config = _make_config(deployment_pipeline=self._make_pipeline_config())
        deployer = _build_deployer(config=config)
        deployer.workspace_id = "ws-dev-id"

        deployer.pipeline_api.get_pipeline_by_name.return_value = {
            "id": "pipe-existing"
        }
        deployer.pipeline_api.get_pipeline_stages.return_value = {
            "success": True,
            "stages": [
                {"displayName": "development", "id": "s1"},
                {"displayName": "test", "id": "s2"},
                {"displayName": "production", "id": "s3"},
            ],
        }
        deployer.fabric.create_workspace.return_value = {
            "success": True,
            "workspace_id": "ws-id",
        }
        deployer.pipeline_api.assign_workspace_to_stage.return_value = {
            "success": True,
        }

        deployer._setup_deployment_pipeline("ws-dev")

        deployer.pipeline_api.create_pipeline.assert_not_called()
        deployer.pipeline_api.assign_workspace_to_stage.assert_called()

    def test_setup_skipped_when_no_config(self):
        """No deployment_pipeline config → no API calls."""
        deployer = _build_deployer()
        deployer._setup_deployment_pipeline("ws-dev")

        deployer.pipeline_api.get_pipeline_by_name.assert_not_called()

    def test_setup_skipped_for_feature_branches(self):
        """deploy() with force_branch_workspace=True skips pipeline setup."""
        config = _make_config(deployment_pipeline=self._make_pipeline_config())
        deployer = _build_deployer(config=config)
        deployer.git.get_workspace_name_from_branch.return_value = "ws-feature-x"
        deployer.fabric.create_workspace.return_value = {
            "success": True,
            "workspace_id": "ws-branch",
        }
        deployer.fabric.create_folder.return_value = {"success": True}
        deployer.fabric.create_lakehouse.return_value = {"success": True}
        deployer.fabric.create_notebook.return_value = {"success": True}
        deployer.fabric.add_workspace_principal.return_value = {"success": True}

        result = deployer.deploy(branch="feature/x", force_branch_workspace=True)

        assert result is True
        deployer.pipeline_api.get_pipeline_by_name.assert_not_called()

    def test_deploy_calls_pipeline_setup_when_configured(self):
        """deploy() calls _setup_deployment_pipeline for base deployments."""
        config = _make_config(deployment_pipeline=self._make_pipeline_config())
        deployer = _build_deployer(config=config)
        deployer.fabric.create_workspace.return_value = {
            "success": True,
            "workspace_id": "ws-1",
        }
        deployer.fabric.create_folder.return_value = {"success": True}
        deployer.fabric.create_lakehouse.return_value = {"success": True}
        deployer.fabric.create_notebook.return_value = {"success": True}
        deployer.fabric.add_workspace_principal.return_value = {"success": True}

        # Pipeline setup mocks
        deployer.pipeline_api.get_pipeline_by_name.return_value = {"id": "pipe-1"}
        deployer.pipeline_api.get_pipeline_stages.return_value = {
            "success": True,
            "stages": [
                {"displayName": "development", "id": "s1"},
                {"displayName": "test", "id": "s2"},
                {"displayName": "production", "id": "s3"},
            ],
        }
        deployer.pipeline_api.assign_workspace_to_stage.return_value = {
            "success": True,
        }

        result = deployer.deploy()

        assert result is True
        deployer.pipeline_api.get_pipeline_by_name.assert_called_once_with(
            "my-pipeline"
        )

    def test_setup_handles_already_assigned_workspace(self):
        """Idempotent: already-assigned workspace doesn't fail."""
        config = _make_config(
            deployment_pipeline={
                "pipeline_name": "p1",
                "stages": {
                    "development": {"workspace_name": "ws-dev"},
                },
            }
        )
        deployer = _build_deployer(config=config)
        deployer.workspace_id = "ws-dev-id"

        deployer.pipeline_api.get_pipeline_by_name.return_value = {"id": "pipe-1"}
        deployer.pipeline_api.get_pipeline_stages.return_value = {
            "success": True,
            "stages": [{"displayName": "development", "id": "s1"}],
        }
        deployer.pipeline_api.assign_workspace_to_stage.return_value = {
            "success": False,
            "error": "Workspace already assigned to this stage",
        }

        # Should not raise
        deployer._setup_deployment_pipeline("ws-dev")

    def test_setup_propagates_principals_to_stage_workspaces(self):
        """Principals from config are added to Test/Prod workspaces."""
        principals = [
            {"id": "user-admin-1", "role": "Admin"},
            {"id": "user-contrib-1", "role": "Contributor"},
        ]
        config = _make_config(
            principals=principals,
            deployment_pipeline=self._make_pipeline_config(),
        )
        deployer = _build_deployer(config=config)
        deployer.workspace_id = "ws-dev-id"

        deployer.pipeline_api.get_pipeline_by_name.return_value = {"id": "pipe-1"}
        deployer.pipeline_api.get_pipeline_stages.return_value = {
            "success": True,
            "stages": [
                {"displayName": "development", "id": "s1"},
                {"displayName": "test", "id": "s2"},
                {"displayName": "production", "id": "s3"},
            ],
        }
        deployer.fabric.create_workspace.return_value = {
            "success": True,
            "workspace_id": "ws-new-id",
        }
        deployer.fabric.add_workspace_principal.return_value = {"success": True}
        deployer.pipeline_api.assign_workspace_to_stage.return_value = {
            "success": True,
        }

        deployer._setup_deployment_pipeline("ws-dev")

        # Each principal added to Test AND Prod = 2 principals × 2 stages = 4
        assert deployer.fabric.add_workspace_principal.call_count == 4

        # Verify the workspace names passed include test and prod
        call_args = [
            c[0][0] for c in deployer.fabric.add_workspace_principal.call_args_list
        ]
        assert "ws-test" in call_args
        assert "ws-prod" in call_args

    def test_setup_skips_unresolved_env_var_principals(self):
        """Principals with unresolved ${VAR} ids are skipped for stages."""
        principals = [
            {"id": "${AZURE_CLIENT_ID}", "role": "Contributor"},
            {"id": "real-user-id", "role": "Admin"},
        ]
        config = _make_config(
            principals=principals,
            deployment_pipeline={
                "pipeline_name": "p1",
                "stages": {
                    "development": {"workspace_name": "ws-dev"},
                    "test": {"workspace_name": "ws-test", "capacity_id": "c1"},
                },
            },
        )
        deployer = _build_deployer(config=config)
        deployer.workspace_id = "ws-dev-id"

        deployer.pipeline_api.get_pipeline_by_name.return_value = {"id": "pipe-1"}
        deployer.pipeline_api.get_pipeline_stages.return_value = {
            "success": True,
            "stages": [
                {"displayName": "development", "id": "s1"},
                {"displayName": "test", "id": "s2"},
            ],
        }
        deployer.fabric.create_workspace.return_value = {
            "success": True,
            "workspace_id": "ws-test-id",
        }
        deployer.fabric.add_workspace_principal.return_value = {"success": True}
        deployer.pipeline_api.assign_workspace_to_stage.return_value = {
            "success": True,
        }

        deployer._setup_deployment_pipeline("ws-dev")

        # Only "real-user-id" should be added (${AZURE_CLIENT_ID} skipped)
        assert deployer.fabric.add_workspace_principal.call_count == 1
        deployer.fabric.add_workspace_principal.assert_called_with(
            "ws-test", "real-user-id", "Admin"
        )
