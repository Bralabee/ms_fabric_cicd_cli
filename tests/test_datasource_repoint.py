"""Tests for the datasource repointing service and CLI command."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from usf_fabric_cli.services.datasource_repoint import (
    FabricDatasourceRepointAPI,
    RepointResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repoint_api():
    """Create a FabricDatasourceRepointAPI instance with a fake token."""
    return FabricDatasourceRepointAPI(
        access_token="fake-token",
        token_manager=None,
    )


@pytest.fixture
def sample_semantic_models():
    """Sample semantic model list response."""
    return [
        {"id": "model-1-id", "displayName": "Sales Model"},
        {"id": "model-2-id", "displayName": "HR Model"},
    ]


@pytest.fixture
def feature_datasources():
    """Datasources pointing to a feature workspace."""
    return [
        {
            "datasourceType": "Sql",
            "connectionDetails": {
                "server": "feature-edp-my-feature.datawarehouse.fabric.microsoft.com",
                "database": "lakehouse_sales",
            },
            "datasourceId": "ds-1",
            "gatewayId": "gw-1",
        }
    ]


@pytest.fixture
def dev_datasources():
    """Datasources already pointing to the dev workspace."""
    return [
        {
            "datasourceType": "Sql",
            "connectionDetails": {
                "server": "edp-dev.datawarehouse.fabric.microsoft.com",
                "database": "lakehouse_sales",
            },
            "datasourceId": "ds-2",
            "gatewayId": "gw-2",
        }
    ]


# ---------------------------------------------------------------------------
# RepointResult tests
# ---------------------------------------------------------------------------


class TestRepointResult:
    def test_empty_result(self):
        result = RepointResult()
        assert result.summary["repointed"] == 0
        assert result.summary["skipped"] == 0
        assert result.summary["failed"] == 0

    def test_summary_with_data(self):
        result = RepointResult()
        result.repointed.append({"model": "A", "from": "x", "to": "y"})
        result.skipped.append({"model": "B", "reason": "no match"})
        result.failed.append({"model": "C", "reason": "API error"})
        summary = result.summary
        assert summary["repointed"] == 1
        assert summary["skipped"] == 1
        assert summary["failed"] == 1
        assert len(summary["details"]["repointed"]) == 1


# ---------------------------------------------------------------------------
# Pattern matching tests
# ---------------------------------------------------------------------------


class TestMatchesSourcePattern:
    def test_feature_workspace_matches(self, repoint_api):
        server = "feature-edp-my-feature.datawarehouse.fabric.microsoft.com"
        assert repoint_api._matches_source_pattern(server, "feature[-_].*")

    def test_dev_workspace_does_not_match(self, repoint_api):
        server = "edp-dev.datawarehouse.fabric.microsoft.com"
        assert not repoint_api._matches_source_pattern(server, "feature[-_].*")

    def test_non_fabric_host_does_not_match(self, repoint_api):
        server = "myserver.database.windows.net"
        assert not repoint_api._matches_source_pattern(server, "feature[-_].*")

    def test_empty_server_does_not_match(self, repoint_api):
        assert not repoint_api._matches_source_pattern("", "feature[-_].*")

    def test_empty_pattern_does_not_match(self, repoint_api):
        server = "feature-edp.datawarehouse.fabric.microsoft.com"
        assert not repoint_api._matches_source_pattern(server, "")

    def test_case_insensitive_match(self, repoint_api):
        server = "Feature-EDP-Dev.datawarehouse.fabric.microsoft.com"
        assert repoint_api._matches_source_pattern(server, "feature[-_].*")

    def test_invalid_regex_returns_false(self, repoint_api):
        server = "feature-edp.datawarehouse.fabric.microsoft.com"
        assert not repoint_api._matches_source_pattern(server, "[invalid")

    def test_warehouse_host_matches(self, repoint_api):
        server = "feature-hr-test.warehouse.fabric.microsoft.com"
        assert repoint_api._matches_source_pattern(server, "feature[-_].*")

    def test_custom_pattern(self, repoint_api):
        server = "temp-ws-123.datawarehouse.fabric.microsoft.com"
        assert repoint_api._matches_source_pattern(server, "temp[-_]ws.*")

    def test_exact_workspace_name_match(self, repoint_api):
        server = "feature-edp-test-wouter.datawarehouse.fabric.microsoft.com"
        assert repoint_api._matches_source_pattern(server, "feature-edp-test-wouter")


# ---------------------------------------------------------------------------
# Server repoint tests
# ---------------------------------------------------------------------------


class TestBuildRepointedServer:
    def test_basic_repoint(self, repoint_api):
        original = "feature-edp-my-feat.datawarehouse.fabric.microsoft.com"
        result = repoint_api._build_repointed_server(original, "EDP [DEV]")
        assert result == "edp-dev.datawarehouse.fabric.microsoft.com"

    def test_preserves_service_type(self, repoint_api):
        original = "old-ws.warehouse.fabric.microsoft.com"
        result = repoint_api._build_repointed_server(original, "My Workspace")
        assert "warehouse.fabric.microsoft.com" in result

    def test_non_fabric_host_unchanged(self, repoint_api):
        original = "myserver.database.windows.net"
        result = repoint_api._build_repointed_server(original, "Dev WS")
        assert result == original

    def test_slugifies_workspace_name(self, repoint_api):
        original = "old.datawarehouse.fabric.microsoft.com"
        result = repoint_api._build_repointed_server(original, "HR Analytics [DEV]")
        assert result.startswith("hr-analytics-dev.")


# ---------------------------------------------------------------------------
# Build update detail tests
# ---------------------------------------------------------------------------


class TestBuildUpdateDetail:
    def test_builds_update_for_feature_datasource(
        self, repoint_api, feature_datasources
    ):
        detail = repoint_api._build_update_detail(feature_datasources[0], "EDP [DEV]")
        assert detail is not None
        assert detail["datasourceSelector"]["connectionDetails"]["server"] == (
            "feature-edp-my-feature.datawarehouse.fabric.microsoft.com"
        )
        assert "edp-dev." in detail["connectionDetails"]["server"]
        assert detail["connectionDetails"]["database"] == "lakehouse_sales"

    def test_returns_none_for_matching_workspace(self, repoint_api, dev_datasources):
        # If we try to repoint to a workspace whose slug already matches,
        # _build_repointed_server returns the same string -> None
        detail = repoint_api._build_update_detail(dev_datasources[0], "edp-dev")
        assert detail is None

    def test_returns_none_for_empty_server(self, repoint_api):
        ds = {
            "datasourceType": "Sql",
            "connectionDetails": {"server": "", "database": "db"},
        }
        assert repoint_api._build_update_detail(ds, "Dev") is None


# ---------------------------------------------------------------------------
# Integration: repoint_workspace_models
# ---------------------------------------------------------------------------


class TestRepointWorkspaceModels:
    @patch.object(FabricDatasourceRepointAPI, "update_datasources")
    @patch.object(FabricDatasourceRepointAPI, "get_datasources")
    @patch.object(FabricDatasourceRepointAPI, "list_semantic_models")
    def test_repoints_matching_models(
        self,
        mock_list,
        mock_get_ds,
        mock_update,
        repoint_api,
        sample_semantic_models,
        feature_datasources,
        dev_datasources,
    ):
        mock_list.return_value = sample_semantic_models
        # First model has feature datasource, second has dev datasource
        mock_get_ds.side_effect = [feature_datasources, dev_datasources]
        mock_update.return_value = True

        result = repoint_api.repoint_workspace_models(
            workspace_id="ws-id",
            target_workspace_name="EDP [DEV]",
            source_pattern="feature[-_].*",
        )

        assert result.summary["repointed"] == 1
        assert result.summary["skipped"] == 1
        mock_update.assert_called_once()

    @patch.object(FabricDatasourceRepointAPI, "get_datasources")
    @patch.object(FabricDatasourceRepointAPI, "list_semantic_models")
    def test_dry_run_does_not_update(
        self,
        mock_list,
        mock_get_ds,
        repoint_api,
        sample_semantic_models,
        feature_datasources,
    ):
        mock_list.return_value = [sample_semantic_models[0]]
        mock_get_ds.return_value = feature_datasources

        result = repoint_api.repoint_workspace_models(
            workspace_id="ws-id",
            target_workspace_name="EDP [DEV]",
            source_pattern="feature[-_].*",
            dry_run=True,
        )

        assert result.summary["repointed"] == 1
        assert result.repointed[0]["dry_run"] == "true"

    @patch.object(FabricDatasourceRepointAPI, "list_semantic_models")
    def test_no_models_returns_empty(self, mock_list, repoint_api):
        mock_list.return_value = []
        result = repoint_api.repoint_workspace_models(
            workspace_id="ws-id",
            target_workspace_name="EDP [DEV]",
            source_pattern="feature[-_].*",
        )
        assert result.summary["repointed"] == 0
        assert result.summary["skipped"] == 0

    @patch.object(FabricDatasourceRepointAPI, "update_datasources")
    @patch.object(FabricDatasourceRepointAPI, "get_datasources")
    @patch.object(FabricDatasourceRepointAPI, "list_semantic_models")
    def test_failed_update_tracked(
        self,
        mock_list,
        mock_get_ds,
        mock_update,
        repoint_api,
        feature_datasources,
    ):
        mock_list.return_value = [{"id": "m1", "displayName": "Model A"}]
        mock_get_ds.return_value = feature_datasources
        mock_update.return_value = False  # Simulate API failure

        result = repoint_api.repoint_workspace_models(
            workspace_id="ws-id",
            target_workspace_name="EDP [DEV]",
            source_pattern="feature[-_].*",
        )

        assert result.summary["failed"] == 1
        assert result.summary["repointed"] == 0

    @patch.object(FabricDatasourceRepointAPI, "get_datasources")
    @patch.object(FabricDatasourceRepointAPI, "list_semantic_models")
    def test_model_with_no_datasources_skipped(
        self, mock_list, mock_get_ds, repoint_api
    ):
        mock_list.return_value = [{"id": "m1", "displayName": "Empty Model"}]
        mock_get_ds.return_value = []

        result = repoint_api.repoint_workspace_models(
            workspace_id="ws-id",
            target_workspace_name="EDP [DEV]",
            source_pattern="feature[-_].*",
        )

        assert result.summary["skipped"] == 1
        assert result.skipped[0]["reason"] == "no datasources found"


# ---------------------------------------------------------------------------
# CLI command tests
# ---------------------------------------------------------------------------


class TestRepointConnectionsCLI:
    @patch("usf_fabric_cli.cli.FabricCLIWrapper")
    @patch("usf_fabric_cli.cli.get_environment_variables")
    @patch("usf_fabric_cli.cli.ConfigManager")
    def test_help_flag(self, mock_config, mock_env, mock_wrapper):
        from typer.testing import CliRunner
        from usf_fabric_cli.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["repoint-connections", "--help"])
        assert result.exit_code == 0
        assert "Repoint semantic model connections" in result.output

    @patch(
        "usf_fabric_cli.cli.FabricDatasourceRepointAPI",
        create=True,
    )
    @patch("usf_fabric_cli.cli.FabricCLIWrapper")
    @patch("usf_fabric_cli.cli.get_environment_variables")
    @patch("usf_fabric_cli.cli.ConfigManager")
    def test_dry_run_output(
        self, mock_config_cls, mock_env, mock_wrapper_cls, mock_repoint_cls
    ):
        """Test that dry run produces expected output."""
        from typer.testing import CliRunner
        from usf_fabric_cli.cli import app

        # Setup mocks
        mock_env.return_value = {"FABRIC_TOKEN": "fake-token"}

        mock_cfg = MagicMock()
        mock_cfg.name = "EDP [DEV]"
        mock_config_cls.return_value.load_config.return_value = mock_cfg

        mock_wrapper = MagicMock()
        mock_wrapper.get_workspace_id.return_value = "ws-guid"
        mock_wrapper._token_manager = None
        mock_wrapper_cls.return_value = mock_wrapper

        # Mock the repoint API to return a result with one repointed model
        mock_result = RepointResult()
        mock_result.repointed.append(
            {
                "model": "Sales Model",
                "from": "feature-edp.datawarehouse.fabric.microsoft.com",
                "to": "edp--dev-.datawarehouse.fabric.microsoft.com",
                "dry_run": "true",
            }
        )
        mock_repoint = MagicMock()
        mock_repoint.repoint_workspace_models.return_value = mock_result
        mock_repoint_cls.return_value = mock_repoint

        runner = CliRunner()
        # Note: the import inside the command function needs special handling
        # We patch at the module level where it's imported
        with patch(
            "usf_fabric_cli.services.datasource_repoint.FabricDatasourceRepointAPI",
            mock_repoint_cls,
        ):
            result = runner.invoke(
                app,
                [
                    "repoint-connections",
                    "config/test.yaml",
                    "--dry-run",
                ],
            )

        # The command should succeed (exit 0)
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# PBI token fallback tests
# ---------------------------------------------------------------------------


class TestPBITokenFallback:
    def test_falls_back_to_fabric_token_without_token_manager(self):
        api = FabricDatasourceRepointAPI(access_token="fabric-token")
        headers = api._get_pbi_headers()
        assert headers["Authorization"] == "Bearer fabric-token"

    def test_acquires_pbi_token_from_credential(self):
        mock_tm = MagicMock()
        mock_tm._credential.get_token.return_value = Mock(token="pbi-token")

        api = FabricDatasourceRepointAPI(
            access_token="fabric-token",
            token_manager=mock_tm,
        )
        headers = api._get_pbi_headers()
        assert headers["Authorization"] == "Bearer pbi-token"

    def test_falls_back_on_credential_error(self):
        mock_tm = MagicMock()
        mock_tm._credential.get_token.side_effect = RuntimeError("fail")

        api = FabricDatasourceRepointAPI(
            access_token="fabric-token",
            token_manager=mock_tm,
        )
        headers = api._get_pbi_headers()
        assert headers["Authorization"] == "Bearer fabric-token"
