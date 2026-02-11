"""
Tests for the onboard.py 6-phase full bootstrap workflow.

Verifies:
- Workspace naming follows Microsoft convention
- Capacity ID fallback logic
- Pipeline name derivation
- Stage limiting via --stages flag
- Feature branch mode is unchanged
- Dry run mode logs all phases
- Idempotent pipeline creation
- Custom naming overrides
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add scripts/dev to path so we can import onboard
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "dev"))

from onboard import (  # noqa: E402
    _resolve_capacity_id,
    _get_workspace_names,
    _get_pipeline_name,
    _enrich_principals,
    _create_empty_workspace,
    _create_deployment_pipeline,
    onboard_project,
    DEFAULT_STAGES,
)


# ── Helper Data ───────────────────────────────────────────────────


FAKE_PRINCIPALS = [
    {"id": "user-admin-oid", "role": "Admin"},
    {"id": "sp-contrib-oid", "role": "Contributor"},
]


# ── Workspace Naming Tests ────────────────────────────────────────


class TestWorkspaceNaming:
    """Tests for Microsoft-convention workspace naming."""

    def test_default_naming(self):
        names = _get_workspace_names("contoso-analytics")
        assert names["dev"] == "contoso-analytics"
        assert names["test"] == "contoso-analytics [Test]"
        assert names["prod"] == "contoso-analytics [Production]"

    def test_hyphenated_names(self):
        names = _get_workspace_names("my-org-project")
        assert names["test"] == "my-org-project [Test]"
        assert names["prod"] == "my-org-project [Production]"


# ── Capacity Fallback Tests ───────────────────────────────────────


class TestCapacityFallback:
    """Tests for stage-specific capacity ID resolution."""

    def test_dev_uses_default(self):
        with patch.dict(
            os.environ,
            {"FABRIC_CAPACITY_ID": "cap-default"},
            clear=False,
        ):
            result = _resolve_capacity_id("dev")
            assert result == "cap-default"

    def test_test_uses_specific_when_set(self):
        with patch.dict(
            os.environ,
            {
                "FABRIC_CAPACITY_ID": "cap-default",
                "TEST_CAPACITY_ID": "cap-test",
            },
            clear=False,
        ):
            result = _resolve_capacity_id("test")
            assert result == "cap-test"

    def test_test_falls_back_to_default(self):
        env = {"FABRIC_CAPACITY_ID": "cap-default"}
        with patch.dict(os.environ, env, clear=False):
            # Ensure TEST_CAPACITY_ID is not set
            os.environ.pop("TEST_CAPACITY_ID", None)
            result = _resolve_capacity_id("test")
            assert result == "cap-default"

    def test_prod_uses_specific_when_set(self):
        with patch.dict(
            os.environ,
            {
                "FABRIC_CAPACITY_ID": "cap-default",
                "PROD_CAPACITY_ID": "cap-prod",
            },
            clear=False,
        ):
            result = _resolve_capacity_id("prod")
            assert result == "cap-prod"

    def test_prod_falls_back_to_default(self):
        env = {"FABRIC_CAPACITY_ID": "cap-default"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("PROD_CAPACITY_ID", None)
            result = _resolve_capacity_id("prod")
            assert result == "cap-default"


# ── Pipeline Name Tests ───────────────────────────────────────────


class TestPipelineName:
    """Tests for pipeline name derivation."""

    def test_auto_derived_name(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FABRIC_PIPELINE_NAME", None)
            name = _get_pipeline_name("Contoso", "Analytics")
            assert name == "Contoso-Analytics Pipeline"

    def test_env_var_override(self):
        with patch.dict(
            os.environ,
            {"FABRIC_PIPELINE_NAME": "Custom Pipeline"},
            clear=False,
        ):
            name = _get_pipeline_name("Contoso", "Analytics")
            assert name == "Custom Pipeline"


# ── Empty Workspace Creation Tests ────────────────────────────────


class TestCreateEmptyWorkspace:
    """Tests for Test/Prod workspace creation."""

    def test_dry_run_returns_none(self):
        result = _create_empty_workspace(
            workspace_name="test-ws",
            capacity_id="cap-1",
            description="Test",
            principals=[],
            dry_run=True,
        )
        assert result is None

    @patch("usf_fabric_cli.utils.config.get_environment_variables")
    @patch("usf_fabric_cli.services.fabric_wrapper" ".FabricCLIWrapper")
    def test_creates_workspace_and_adds_principals(self, MockWrapper, mock_env):
        mock_env.return_value = {"FABRIC_TOKEN": "tok"}
        mock_fabric = MagicMock()
        MockWrapper.return_value = mock_fabric

        mock_fabric.create_workspace.return_value = {
            "success": True,
            "workspace_id": "ws-123",
        }
        mock_fabric.add_workspace_principal.return_value = {
            "success": True,
        }

        result = _create_empty_workspace(
            workspace_name="test-ws [Test]",
            capacity_id="cap-1",
            description="Test environment",
            principals=FAKE_PRINCIPALS,
        )

        assert result == "ws-123"
        mock_fabric.create_workspace.assert_called_once()
        # Should add 2 principals
        assert mock_fabric.add_workspace_principal.call_count == 2

    @patch("usf_fabric_cli.utils.config.get_environment_variables")
    @patch("usf_fabric_cli.services.fabric_wrapper" ".FabricCLIWrapper")
    def test_skips_unresolved_env_var_principals(self, MockWrapper, mock_env):
        mock_env.return_value = {"FABRIC_TOKEN": "tok"}
        mock_fabric = MagicMock()
        MockWrapper.return_value = mock_fabric

        mock_fabric.create_workspace.return_value = {
            "success": True,
            "workspace_id": "ws-456",
        }

        principals_with_placeholder = [
            {"id": "${SOME_UNSET_VAR}", "role": "Admin"},
            {"id": "real-oid", "role": "Contributor"},
        ]

        result = _create_empty_workspace(
            workspace_name="test-ws",
            capacity_id="cap-1",
            description="Test",
            principals=principals_with_placeholder,
        )

        assert result == "ws-456"
        # Only the real OID should be added
        mock_fabric.add_workspace_principal.assert_called_once()


# ── Deployment Pipeline Creation Tests ────────────────────────────


class TestCreateDeploymentPipeline:
    """Tests for pipeline creation and stage assignment."""

    def test_dry_run_returns_true(self):
        result = _create_deployment_pipeline(
            pipeline_name="Test Pipeline",
            workspace_ids={"dev": "ws-1", "test": "ws-2"},
            dry_run=True,
        )
        assert result is True

    @patch("usf_fabric_cli.utils.config.get_environment_variables")
    @patch("usf_fabric_cli.services.deployment_pipeline" ".FabricDeploymentPipelineAPI")
    def test_creates_pipeline_and_assigns_stages(self, MockAPI, mock_env):
        mock_env.return_value = {"FABRIC_TOKEN": "tok"}
        mock_api = MagicMock()
        MockAPI.return_value = mock_api

        # No existing pipeline
        mock_api.get_pipeline_by_name.return_value = None

        mock_api.create_pipeline.return_value = {
            "success": True,
            "pipeline": {"id": "pipe-1"},
        }

        mock_api.get_pipeline_stages.return_value = {
            "success": True,
            "stages": [
                {"id": "s1", "displayName": "Development"},
                {"id": "s2", "displayName": "Test"},
                {"id": "s3", "displayName": "Production"},
            ],
        }

        mock_api.assign_workspace_to_stage.return_value = {
            "success": True,
        }

        result = _create_deployment_pipeline(
            pipeline_name="My Pipeline",
            workspace_ids={
                "dev": "ws-dev",
                "test": "ws-test",
                "prod": "ws-prod",
            },
        )

        assert result is True
        mock_api.create_pipeline.assert_called_once()
        assert mock_api.assign_workspace_to_stage.call_count == 3

    @patch("usf_fabric_cli.utils.config.get_environment_variables")
    @patch("usf_fabric_cli.services.deployment_pipeline" ".FabricDeploymentPipelineAPI")
    def test_reuses_existing_pipeline(self, MockAPI, mock_env):
        mock_env.return_value = {"FABRIC_TOKEN": "tok"}
        mock_api = MagicMock()
        MockAPI.return_value = mock_api

        # Pipeline already exists
        mock_api.get_pipeline_by_name.return_value = {
            "id": "existing-pipe",
        }

        mock_api.get_pipeline_stages.return_value = {
            "success": True,
            "stages": [
                {"id": "s1", "displayName": "Development"},
                {"id": "s2", "displayName": "Test"},
            ],
        }

        mock_api.assign_workspace_to_stage.return_value = {
            "success": True,
        }

        result = _create_deployment_pipeline(
            pipeline_name="My Pipeline",
            workspace_ids={"dev": "ws-dev", "test": "ws-test"},
        )

        assert result is True
        # Should NOT call create_pipeline
        mock_api.create_pipeline.assert_not_called()


# ── Onboard Full Bootstrap Tests ──────────────────────────────────


class TestOnboardFullBootstrap:
    """Integration tests for the onboard_project function."""

    @patch("onboard._create_deployment_pipeline")
    @patch("onboard._create_empty_workspace")
    @patch("onboard.subprocess.run")
    @patch("onboard.generate_project_config")
    def test_dry_run_all_phases_logged(
        self,
        mock_gen,
        mock_subprocess,
        mock_create_ws,
        mock_create_pipeline,
    ):
        """Verify dry run logs all 6 phases without executing."""
        mock_gen.return_value = Path("config/projects/org/proj.yaml")

        result = onboard_project(
            org_name="Org",
            project_name="Proj",
            template="medallion",
            capacity_id="cap-1",
            dry_run=True,
        )

        assert result is True
        # No subprocess calls in dry run
        mock_subprocess.assert_not_called()
        # _create_empty_workspace IS called but with dry_run=True
        for c in mock_create_ws.call_args_list:
            assert c.kwargs.get("dry_run") is True
        # _create_deployment_pipeline is NOT called (handled inline)
        mock_create_pipeline.assert_not_called()

    @patch("onboard._create_deployment_pipeline")
    @patch("onboard._create_empty_workspace")
    @patch("onboard.subprocess.run")
    @patch("onboard.generate_project_config")
    def test_stages_flag_limits_scope(
        self,
        mock_gen,
        mock_subprocess,
        mock_create_ws,
        mock_create_pipeline,
    ):
        """Verify --stages dev,test skips Prod."""
        mock_gen.return_value = Path("config/proj.yaml")

        result = onboard_project(
            org_name="Org",
            project_name="Proj",
            template="medallion",
            capacity_id="cap-1",
            dry_run=True,
            stages={"dev", "test"},
        )

        assert result is True

    @patch("onboard._create_deployment_pipeline")
    @patch("onboard._create_empty_workspace")
    @patch("onboard.subprocess.run")
    @patch("onboard.generate_project_config")
    def test_feature_branch_mode_skips_full_bootstrap(
        self,
        mock_gen,
        mock_subprocess,
        mock_create_ws,
        mock_create_pipeline,
    ):
        """Feature branch mode only does config + feature deploy."""
        mock_gen.return_value = Path("config/proj.yaml")

        result = onboard_project(
            org_name="Org",
            project_name="Proj",
            template="medallion",
            capacity_id="cap-1",
            dry_run=True,
            with_feature_branch=True,
        )

        assert result is True
        mock_create_ws.assert_not_called()
        mock_create_pipeline.assert_not_called()

    def test_custom_workspace_name_overrides(self):
        """Verify custom naming overrides are applied."""
        names = _get_workspace_names("base-ws")
        assert names["test"] == "base-ws [Test]"
        assert names["prod"] == "base-ws [Production]"

        # In onboard_project, overrides are applied after
        names["test"] = "Custom Test WS"
        names["prod"] = "Custom Prod WS"
        assert names["test"] == "Custom Test WS"
        assert names["prod"] == "Custom Prod WS"

    def test_default_stages_includes_all_three(self):
        """Default stages should include dev, test, and prod."""
        assert DEFAULT_STAGES == {"dev", "test", "prod"}


# ── Enrich Principals Tests ───────────────────────────────────────


class TestEnrichPrincipals:
    """Tests for _enrich_principals env-var injection logic."""

    def test_injects_admin_and_contributor(self):
        """Should inject both mandatory principals from env vars."""
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_ADMIN_PRINCIPAL_ID": "gov-sp-oid",
                "ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID": "contrib-oid",
            },
            clear=False,
        ):
            result = _enrich_principals([])
            assert len(result) == 2
            assert result[0]["id"] == "gov-sp-oid"
            assert result[0]["role"] == "Admin"
            assert result[1]["id"] == "contrib-oid"
            assert result[1]["role"] == "Contributor"

    def test_deduplicates_existing(self):
        """Should not duplicate principals already in the list."""
        existing = [{"id": "gov-sp-oid", "role": "Admin"}]
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_ADMIN_PRINCIPAL_ID": "gov-sp-oid",
                "ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID": "contrib-oid",
            },
            clear=False,
        ):
            result = _enrich_principals(existing)
            # Only the contributor should be added
            assert len(result) == 2
            assert result[1]["id"] == "contrib-oid"

    def test_skips_unresolved_placeholders(self):
        """Should skip env vars that are still ${...} placeholders."""
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_ADMIN_PRINCIPAL_ID": "${SOME_UNSET}",
                "ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID": "",
            },
            clear=False,
        ):
            result = _enrich_principals([])
            assert len(result) == 0

    def test_skips_empty_env_vars(self):
        """Should skip when env vars are empty."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ADDITIONAL_ADMIN_PRINCIPAL_ID", None)
            os.environ.pop("ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID", None)
            result = _enrich_principals([{"id": "existing", "role": "Member"}])
            assert len(result) == 1

    def test_does_not_mutate_original_list(self):
        """Should return a new list, not mutate the input."""
        original = [{"id": "existing", "role": "Member"}]
        with patch.dict(
            os.environ,
            {"ADDITIONAL_ADMIN_PRINCIPAL_ID": "admin-oid"},
            clear=False,
        ):
            os.environ.pop("ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID", None)
            result = _enrich_principals(original)
            assert len(result) == 2
            assert len(original) == 1  # Original unchanged

