"""Tests for the datasource repointing service and CLI command."""

from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

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
# update_datasources HTTP error handling
# ---------------------------------------------------------------------------


class TestUpdateDatasourcesErrorHandling:
    @patch("usf_fabric_cli.services.datasource_repoint.requests.post")
    def test_403_returns_ownership_reason(self, mock_post, repoint_api):
        """403 response includes a specific ownership failure reason."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            response=mock_response
        )
        mock_post.return_value = mock_response

        result = repoint_api.update_datasources("ws-id", "ds-id", [{}])
        assert result["success"] is False
        assert "403" in result["reason"]
        assert "owner" in result["reason"]

    @patch("usf_fabric_cli.services.datasource_repoint.requests.post")
    def test_500_returns_http_status(self, mock_post, repoint_api):
        """Non-403 HTTP errors include the status code."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            response=mock_response
        )
        mock_post.return_value = mock_response

        result = repoint_api.update_datasources("ws-id", "ds-id", [{}])
        assert result["success"] is False
        assert "HTTP 500" in result["reason"]

    @patch("usf_fabric_cli.services.datasource_repoint.requests.post")
    def test_success_returns_true(self, mock_post, repoint_api):
        """Successful update returns success dict."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = repoint_api.update_datasources("ws-id", "ds-id", [{}])
        assert result["success"] is True

    @patch("usf_fabric_cli.services.datasource_repoint.requests.post")
    def test_connection_error_returns_failure(self, mock_post, repoint_api):
        """Network errors return a failure dict with the exception message."""
        mock_post.side_effect = requests.ConnectionError("Connection refused")

        result = repoint_api.update_datasources("ws-id", "ds-id", [{}])
        assert result["success"] is False
        assert "Connection refused" in result["reason"]


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
        mock_update.return_value = {"success": True}

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
        mock_update.return_value = {
            "success": False,
            "reason": "UpdateDatasources API returned HTTP 500",
        }

        result = repoint_api.repoint_workspace_models(
            workspace_id="ws-id",
            target_workspace_name="EDP [DEV]",
            source_pattern="feature[-_].*",
        )

        assert result.summary["failed"] == 1
        assert result.summary["repointed"] == 0
        assert "HTTP 500" in result.failed[0]["reason"]

    @patch.object(FabricDatasourceRepointAPI, "update_datasources")
    @patch.object(FabricDatasourceRepointAPI, "get_datasources")
    @patch.object(FabricDatasourceRepointAPI, "list_semantic_models")
    def test_403_ownership_failure_tracked(
        self,
        mock_list,
        mock_get_ds,
        mock_update,
        repoint_api,
        feature_datasources,
    ):
        """403 errors surface a specific ownership message in the failure reason."""
        mock_list.return_value = [{"id": "m1", "displayName": "Sales Model"}]
        mock_get_ds.return_value = feature_datasources
        mock_update.return_value = {
            "success": False,
            "reason": "403 Forbidden — SP is not the semantic model owner. "
            "Use the TakeOver API or reassign ownership in the Fabric portal.",
        }

        result = repoint_api.repoint_workspace_models(
            workspace_id="ws-id",
            target_workspace_name="EDP [DEV]",
            source_pattern="feature[-_].*",
        )

        assert result.summary["failed"] == 1
        assert "403" in result.failed[0]["reason"]
        assert "owner" in result.failed[0]["reason"]

    @patch.object(FabricDatasourceRepointAPI, "get_datasources")
    @patch.object(FabricDatasourceRepointAPI, "list_semantic_models")
    def test_model_with_no_datasources_skipped_with_direct_lake_hint(
        self, mock_list, mock_get_ds, repoint_api
    ):
        """Models with no datasources get a Direct Lake hint in the skip reason."""
        mock_list.return_value = [{"id": "m1", "displayName": "Empty Model"}]
        mock_get_ds.return_value = []

        result = repoint_api.repoint_workspace_models(
            workspace_id="ws-id",
            target_workspace_name="EDP [DEV]",
            source_pattern="feature[-_].*",
        )

        assert result.summary["skipped"] == 1
        assert "Direct Lake" in result.skipped[0]["reason"]
        assert "no SQL datasources found" in result.skipped[0]["reason"]


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

        # The command should succeed (exit 0) when connections were repointed
        assert result.exit_code == 0

    @patch(
        "usf_fabric_cli.cli.FabricDatasourceRepointAPI",
        create=True,
    )
    @patch("usf_fabric_cli.cli.FabricCLIWrapper")
    @patch("usf_fabric_cli.cli.get_environment_variables")
    @patch("usf_fabric_cli.cli.ConfigManager")
    def test_nothing_to_repoint_exits_2(
        self, mock_config_cls, mock_env, mock_wrapper_cls, mock_repoint_cls
    ):
        """Exit code 2 when no connections needed repointing (graceful skip)."""
        from typer.testing import CliRunner
        from usf_fabric_cli.cli import app

        mock_env.return_value = {"FABRIC_TOKEN": "fake-token"}

        mock_cfg = MagicMock()
        mock_cfg.name = "EDP [DEV]"
        mock_config_cls.return_value.load_config.return_value = mock_cfg

        mock_wrapper = MagicMock()
        mock_wrapper.get_workspace_id.return_value = "ws-guid"
        mock_wrapper._token_manager = None
        mock_wrapper_cls.return_value = mock_wrapper

        # Return empty result — nothing to repoint
        mock_result = RepointResult()
        mock_repoint = MagicMock()
        mock_repoint.repoint_workspace_models.return_value = mock_result
        mock_repoint_cls.return_value = mock_repoint

        runner = CliRunner()
        with patch(
            "usf_fabric_cli.services.datasource_repoint.FabricDatasourceRepointAPI",
            mock_repoint_cls,
        ):
            result = runner.invoke(
                app,
                [
                    "repoint-connections",
                    "config/test.yaml",
                ],
            )

        # Exit 2 = graceful skip (nothing to do)
        assert result.exit_code == 2
        assert "No connections needed repointing" in result.output


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


# ---------------------------------------------------------------------------
# Direct Lake binding tests
# ---------------------------------------------------------------------------

# Shared fixtures for Direct Lake tests

SOURCE_WS_ID = "source-ws-id"
TARGET_WS_ID = "target-ws-id"

SOURCE_LAKEHOUSES = [
    {"id": "src-lh-1", "displayName": "lh_helicopter", "type": "Lakehouse"},
    {"id": "src-lh-2", "displayName": "lh_scorecard", "type": "Lakehouse"},
]

TARGET_LAKEHOUSES = [
    {"id": "tgt-lh-1", "displayName": "lh_helicopter", "type": "Lakehouse"},
    {"id": "tgt-lh-2", "displayName": "lh_scorecard", "type": "Lakehouse"},
]

SOURCE_LH_DETAIL_1 = {
    "id": "src-lh-1",
    "displayName": "lh_helicopter",
    "properties": {
        "sqlEndpointProperties": {
            "id": "src-sql-ep-1",
            "connectionString": "srchash1.datawarehouse.fabric.microsoft.com",
            "provisioningStatus": "Success",
        }
    },
}

SOURCE_LH_DETAIL_2 = {
    "id": "src-lh-2",
    "displayName": "lh_scorecard",
    "properties": {
        "sqlEndpointProperties": {
            "id": "src-sql-ep-2",
            "connectionString": "srchash2.datawarehouse.fabric.microsoft.com",
            "provisioningStatus": "Success",
        }
    },
}

TARGET_LH_DETAIL_1 = {
    "id": "tgt-lh-1",
    "displayName": "lh_helicopter",
    "properties": {
        "sqlEndpointProperties": {
            "id": "tgt-sql-ep-1",
            "connectionString": "tgthash1.datawarehouse.fabric.microsoft.com",
            "provisioningStatus": "Success",
        }
    },
}

TARGET_LH_DETAIL_2 = {
    "id": "tgt-lh-2",
    "displayName": "lh_scorecard",
    "properties": {
        "sqlEndpointProperties": {
            "id": "tgt-sql-ep-2",
            "connectionString": "tgthash2.datawarehouse.fabric.microsoft.com",
            "provisioningStatus": "Success",
        }
    },
}

MODELS_IN_TARGET = [
    {"id": "model-dl-1", "displayName": "sm_helicopter"},
    {"id": "model-dl-2", "displayName": "Balanced Scorecard Model"},
    {"id": "model-sql-1", "displayName": "SM_Helicopter_PoC"},
]

# Direct Lake model connections (Automatic, path = endpoint;db-id)
DL_CONNECTIONS_MODEL_1 = [
    {
        "connectivityType": "Automatic",
        "connectionDetails": {
            "type": "SQL",
            "path": "srchash1.datawarehouse.fabric.microsoft.com;src-sql-ep-1",
        },
    }
]

DL_CONNECTIONS_MODEL_2 = [
    {
        "connectivityType": "Automatic",
        "connectionDetails": {
            "type": "SQL",
            "path": "srchash2.datawarehouse.fabric.microsoft.com;src-sql-ep-2",
        },
    }
]

# SQL endpoint model — has ShareableCloud, not Automatic
SQL_CONNECTIONS_MODEL = [
    {
        "connectivityType": "ShareableCloud",
        "id": "conn-1",
        "displayName": "SQL Connection",
        "connectionDetails": {
            "type": "SQL",
            "path": "hash.datawarehouse.fabric.microsoft.com;some-db-id",
        },
    }
]


class TestListItemConnections:
    def test_returns_connections(self, repoint_api):
        mock_response = Mock()
        mock_response.json.return_value = {"value": DL_CONNECTIONS_MODEL_1}
        with patch.object(repoint_api, "_make_request", return_value=mock_response):
            result = repoint_api.list_item_connections("ws-1", "item-1")
        assert len(result) == 1
        assert result[0]["connectivityType"] == "Automatic"

    def test_returns_empty_on_error(self, repoint_api):
        with patch.object(
            repoint_api,
            "_make_request",
            side_effect=requests.RequestException("fail"),
        ):
            result = repoint_api.list_item_connections("ws-1", "item-1")
        assert result == []


class TestGetLakehouse:
    def test_returns_lakehouse_detail(self, repoint_api):
        mock_response = Mock()
        mock_response.json.return_value = SOURCE_LH_DETAIL_1
        with patch.object(repoint_api, "_make_request", return_value=mock_response):
            result = repoint_api.get_lakehouse("ws-1", "lh-1")
        assert result is not None
        assert result["displayName"] == "lh_helicopter"
        sql_props = result["properties"]["sqlEndpointProperties"]
        assert sql_props["id"] == "src-sql-ep-1"

    def test_returns_none_on_error(self, repoint_api):
        with patch.object(
            repoint_api,
            "_make_request",
            side_effect=requests.RequestException("fail"),
        ):
            result = repoint_api.get_lakehouse("ws-1", "lh-1")
        assert result is None


class TestBindConnection:
    def test_successful_bind(self, repoint_api):
        mock_response = Mock()
        mock_response.status_code = 200
        with patch.object(repoint_api, "_make_request", return_value=mock_response):
            result = repoint_api.bind_connection(
                "ws-1",
                "model-1",
                {
                    "connectivityType": "Automatic",
                    "connectionDetails": {"type": "SQL", "path": "host;db-id"},
                },
            )
        assert result["success"] is True

    def test_403_returns_ownership_error(self, repoint_api):
        mock_resp = Mock()
        mock_resp.status_code = 403
        mock_resp.text = "Forbidden"
        mock_resp.json.return_value = {"message": "Not the owner"}
        http_error = requests.HTTPError(response=mock_resp)
        with patch.object(repoint_api, "_make_request", side_effect=http_error):
            result = repoint_api.bind_connection(
                "ws-1",
                "model-1",
                {"connectivityType": "Automatic", "connectionDetails": {}},
            )
        assert result["success"] is False
        assert "403" in result["reason"]
        assert "owner" in result["reason"].lower()


class TestRebindDirectLakeModels:
    """Tests for the full rebind_direct_lake_models orchestration."""

    def _setup_api(self, repoint_api):
        """Wire up mocks for a standard two-lakehouse scenario."""

        def mock_list_items(ws_id, item_type=None):
            if ws_id == SOURCE_WS_ID:
                return SOURCE_LAKEHOUSES
            return TARGET_LAKEHOUSES

        def mock_get_lakehouse(ws_id, lh_id):
            mapping = {
                (SOURCE_WS_ID, "src-lh-1"): SOURCE_LH_DETAIL_1,
                (SOURCE_WS_ID, "src-lh-2"): SOURCE_LH_DETAIL_2,
                (TARGET_WS_ID, "tgt-lh-1"): TARGET_LH_DETAIL_1,
                (TARGET_WS_ID, "tgt-lh-2"): TARGET_LH_DETAIL_2,
            }
            return mapping.get((ws_id, lh_id))

        def mock_list_connections(ws_id, model_id):
            mapping = {
                "model-dl-1": DL_CONNECTIONS_MODEL_1,
                "model-dl-2": DL_CONNECTIONS_MODEL_2,
                "model-sql-1": SQL_CONNECTIONS_MODEL,
            }
            return mapping.get(model_id, [])

        repoint_api.list_workspace_items = Mock(side_effect=mock_list_items)
        repoint_api.get_lakehouse = Mock(side_effect=mock_get_lakehouse)
        repoint_api.list_semantic_models = Mock(return_value=MODELS_IN_TARGET)
        repoint_api.list_item_connections = Mock(side_effect=mock_list_connections)
        repoint_api.bind_connection = Mock(return_value={"success": True})

    def test_rebinds_direct_lake_models(self, repoint_api):
        self._setup_api(repoint_api)
        result = repoint_api.rebind_direct_lake_models(
            target_workspace_id=TARGET_WS_ID,
            source_workspace_id=SOURCE_WS_ID,
        )
        assert result.summary["repointed"] == 2
        assert result.summary["skipped"] == 1  # SQL model skipped
        assert result.summary["failed"] == 0

        # Verify bind_connection was called for each Direct Lake model
        assert repoint_api.bind_connection.call_count == 2

        # Check the binding payloads
        calls = repoint_api.bind_connection.call_args_list
        for call in calls:
            binding = (
                call[1]["connection_binding"]
                if "connection_binding" in call[1]
                else call[0][2]
            )
            assert binding["connectivityType"] == "Automatic"
            assert binding["connectionDetails"]["type"] == "SQL"
            # Target path should contain target endpoint info
            assert "tgthash" in binding["connectionDetails"]["path"]

    def test_dry_run_does_not_call_bind(self, repoint_api):
        self._setup_api(repoint_api)
        result = repoint_api.rebind_direct_lake_models(
            target_workspace_id=TARGET_WS_ID,
            source_workspace_id=SOURCE_WS_ID,
            dry_run=True,
        )
        assert result.summary["repointed"] == 2
        assert repoint_api.bind_connection.call_count == 0
        # Verify dry_run flag in details
        for detail in result.summary["details"]["repointed"]:
            assert detail.get("dry_run") == "true"

    def test_skips_models_with_no_connections(self, repoint_api):
        self._setup_api(repoint_api)
        repoint_api.list_item_connections = Mock(return_value=[])
        result = repoint_api.rebind_direct_lake_models(
            target_workspace_id=TARGET_WS_ID,
            source_workspace_id=SOURCE_WS_ID,
        )
        assert result.summary["repointed"] == 0
        assert result.summary["skipped"] == 3

    def test_skips_when_already_pointing_to_target(self, repoint_api):
        """Models already pointing to target lakehouses should be skipped."""
        self._setup_api(repoint_api)
        # Return target connections instead of source
        already_correct = [
            {
                "connectivityType": "Automatic",
                "connectionDetails": {
                    "type": "SQL",
                    "path": "tgthash1.datawarehouse.fabric.microsoft.com;tgt-sql-ep-1",
                },
            }
        ]
        repoint_api.list_item_connections = Mock(return_value=already_correct)
        result = repoint_api.rebind_direct_lake_models(
            target_workspace_id=TARGET_WS_ID,
            source_workspace_id=SOURCE_WS_ID,
        )
        assert result.summary["repointed"] == 0
        assert repoint_api.bind_connection.call_count == 0

    def test_fails_when_target_lakehouse_missing(self, repoint_api):
        """If target workspace lacks a matching lakehouse, report failure."""
        self._setup_api(repoint_api)
        # Remove target lakehouses
        repoint_api.list_workspace_items = Mock(
            side_effect=lambda ws_id, item_type=None: (
                SOURCE_LAKEHOUSES if ws_id == SOURCE_WS_ID else []
            )
        )
        result = repoint_api.rebind_direct_lake_models(
            target_workspace_id=TARGET_WS_ID,
            source_workspace_id=SOURCE_WS_ID,
        )
        # No target lakehouses → early return
        assert result.summary["repointed"] == 0

    def test_reports_bind_api_failure(self, repoint_api):
        self._setup_api(repoint_api)
        repoint_api.bind_connection = Mock(
            return_value={"success": False, "reason": "403 Forbidden"}
        )
        result = repoint_api.rebind_direct_lake_models(
            target_workspace_id=TARGET_WS_ID,
            source_workspace_id=SOURCE_WS_ID,
        )
        assert result.summary["failed"] == 2
        assert result.summary["repointed"] == 0

    def test_handles_no_source_lakehouses(self, repoint_api):
        self._setup_api(repoint_api)
        repoint_api.list_workspace_items = Mock(return_value=[])
        repoint_api.get_lakehouse = Mock(return_value=None)
        result = repoint_api.rebind_direct_lake_models(
            target_workspace_id=TARGET_WS_ID,
            source_workspace_id=SOURCE_WS_ID,
        )
        assert result.summary["repointed"] == 0
