"""
Semantic Model Datasource Repointing Service.

After Git Sync copies item definitions from a feature branch into the Dev
workspace, semantic model connection strings may still reference the feature
workspace's lakehouses or warehouses.  This service detects those stale
connections and repoints them to the target (Dev) workspace using the
Power BI REST API (UpdateDatasources).

Supported connection types:
- Lakehouse SQL endpoint connections (datasourceType: Sql)
- Warehouse connections (datasourceType: Sql)

Not yet supported:
- Direct Lake models — these use a different binding mechanism
  (Fabric REST API: Bind Semantic Model Connection) that is not
  implemented here.  Direct Lake models will be reported as
  "skipped: no datasources found" since their bindings are not
  surfaced by the Power BI GetDatasources API.

API limitations (per Microsoft docs):
- The caller must be the semantic model OWNER (not just workspace admin).
- Datasets modified via the XMLA endpoint are not supported.
- Datasets with incremental refresh may result in partial updates.
- Only these datasource types are updatable: SQL Server, Azure SQL,
  Azure Analysis Services, Azure Synapse, OData, SharePoint, Teradata,
  SAP HANA.  Fabric Lakehouse/Warehouse SQL endpoints present as "Sql"
  type and are therefore supported.

References:
- https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/
  get-datasources-in-group
- https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/
  update-datasources-in-group
- https://learn.microsoft.com/en-us/rest/api/fabric/semanticmodel/
  items/bind-semantic-model-connection  (Direct Lake — future)
"""

import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import requests

from usf_fabric_cli.services.fabric_api_base import FabricAPIBase
from usf_fabric_cli.utils.retry import (
    DEFAULT_BASE_DELAY,
    DEFAULT_MAX_DELAY,
    DEFAULT_MAX_RETRIES,
)

if TYPE_CHECKING:
    from usf_fabric_cli.services.token_manager import TokenManager

logger = logging.getLogger(__name__)

# -- Power BI API constants ------------------------------------------------
PBI_API_BASE_URL = "https://api.powerbi.com/v1.0/myorg"
PBI_TOKEN_SCOPE = "https://analysis.windows.net/powerbi/api/.default"  # nosec B105


class RepointResult:
    """Tracks repoint operation results."""

    def __init__(self) -> None:
        self.repointed: List[Dict[str, str]] = []
        self.skipped: List[Dict[str, str]] = []
        self.failed: List[Dict[str, str]] = []

    @property
    def summary(self) -> Dict[str, Any]:
        return {
            "repointed": len(self.repointed),
            "skipped": len(self.skipped),
            "failed": len(self.failed),
            "details": {
                "repointed": self.repointed,
                "skipped": self.skipped,
                "failed": self.failed,
            },
        }


class FabricDatasourceRepointAPI(FabricAPIBase):
    """
    Client for repointing semantic model datasource connections.

    Uses the Fabric REST API to list semantic models and the Power BI
    REST API to inspect and update their datasource connections.
    """

    def __init__(
        self,
        access_token: str,
        base_url: str = "https://api.fabric.microsoft.com/v1",
        token_manager: Optional["TokenManager"] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
    ):
        super().__init__(
            access_token=access_token,
            base_url=base_url,
            token_manager=token_manager,
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
        )
        self._pbi_token: Optional[str] = None

    # -- Token helpers -----------------------------------------------------

    def _get_pbi_headers(self) -> Dict[str, str]:
        """
        Get HTTP headers for Power BI REST API calls.

        Acquires a PBI-scoped token from the TokenManager's credential
        (same Service Principal, different resource scope).  Falls back
        to the Fabric token if no TokenManager is available.
        """
        if self._pbi_token is None:
            if (
                self._token_manager
                and hasattr(self._token_manager, "_credential")
                and self._token_manager._credential is not None
            ):
                try:
                    access_token = self._token_manager._credential.get_token(
                        PBI_TOKEN_SCOPE
                    )
                    self._pbi_token = access_token.token
                    logger.debug("Acquired Power BI API token for datasource repoint")
                except (RuntimeError, ValueError) as exc:
                    logger.warning(
                        "Could not acquire PBI token (%s); "
                        "falling back to Fabric token",
                        exc,
                    )
                    self._pbi_token = self._access_token
            else:
                self._pbi_token = self._access_token

        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._pbi_token}",
        }

    # -- Fabric REST API: Semantic Models ----------------------------------

    def list_semantic_models(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        List all semantic models in a workspace via Fabric REST API.

        Args:
            workspace_id: Fabric workspace GUID.

        Returns:
            List of semantic model dicts with id, displayName, etc.
        """
        url = f"{self.base_url}/workspaces/{workspace_id}/semanticModels"
        try:
            response = self._make_request("GET", url)
            data = response.json()
            models = data.get("value", [])
            logger.info(
                "Found %d semantic models in workspace %s",
                len(models),
                workspace_id,
            )
            return models
        except requests.RequestException as e:
            logger.error(
                "Failed to list semantic models in workspace %s: %s",
                workspace_id,
                e,
            )
            return []

    # -- Power BI REST API: Datasources ------------------------------------

    def get_datasources(
        self, workspace_id: str, dataset_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get datasource connections for a semantic model (dataset).

        Uses the Power BI REST API:
        GET /v1.0/myorg/groups/{groupId}/datasets/{datasetId}/datasources

        Args:
            workspace_id: Power BI group (workspace) GUID.
            dataset_id: Dataset (semantic model) GUID.

        Returns:
            List of datasource dicts with connectionDetails, datasourceType, etc.
        """
        url = (
            f"{PBI_API_BASE_URL}/groups/{workspace_id}"
            f"/datasets/{dataset_id}/datasources"
        )
        headers = self._get_pbi_headers()

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("value", [])
        except requests.RequestException as e:
            logger.warning(
                "Failed to get datasources for dataset %s: %s", dataset_id, e
            )
            return []

    def update_datasources(
        self,
        workspace_id: str,
        dataset_id: str,
        update_details: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Update datasource connections for a semantic model.

        Uses the Power BI REST API:
        POST /v1.0/myorg/groups/{groupId}/datasets/{datasetId}/Default.UpdateDatasources

        Args:
            workspace_id: Power BI group (workspace) GUID.
            dataset_id: Dataset (semantic model) GUID.
            update_details: List of datasource update objects, each with
                ``datasourceSelector`` and ``connectionDetails``.

        Returns:
            Dict with "success" (bool) and optional "reason" (str) for failures.
        """
        url = (
            f"{PBI_API_BASE_URL}/groups/{workspace_id}"
            f"/datasets/{dataset_id}/Default.UpdateDatasources"
        )
        headers = self._get_pbi_headers()
        body = {"updateDetails": update_details}

        try:
            response = requests.post(url, headers=headers, json=body, timeout=60)
            response.raise_for_status()
            logger.info(
                "Updated %d datasource(s) for dataset %s",
                len(update_details),
                dataset_id,
            )
            return {"success": True}
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status == 403:
                logger.error(
                    "403 Forbidden updating dataset %s — the service principal "
                    "is likely not the semantic model owner. The Power BI "
                    "UpdateDatasources API requires the caller to be the "
                    "dataset owner, not just a workspace admin.",
                    dataset_id,
                )
                return {
                    "success": False,
                    "reason": (
                        "403 Forbidden — SP is not the semantic model owner. "
                        "Use the TakeOver API or reassign ownership in the "
                        "Fabric portal."
                    ),
                }
            logger.error(
                "HTTP %d updating datasources for dataset %s: %s",
                status,
                dataset_id,
                e,
            )
            return {
                "success": False,
                "reason": f"UpdateDatasources API returned HTTP {status}",
            }
        except requests.RequestException as e:
            logger.error(
                "Failed to update datasources for dataset %s: %s",
                dataset_id,
                e,
            )
            return {
                "success": False,
                "reason": f"UpdateDatasources API call failed: {e}",
            }

    # -- Repoint logic -----------------------------------------------------

    @staticmethod
    def _matches_source_pattern(server: str, source_pattern: str) -> bool:
        """
        Check if a datasource server string matches the source pattern.

        The pattern is matched against the workspace-derived portion of the
        server hostname. Fabric SQL endpoint hostnames follow the format:
            <workspace-derived-name>.<lakehouse-or-warehouse>.fabric.microsoft.com

        Args:
            server: The datasource server string (e.g.,
                "abc-feature-dev.datawarehouse.fabric.microsoft.com").
            source_pattern: Regex pattern to match against the workspace
                portion of the hostname.

        Returns:
            True if the server matches the source pattern.
        """
        if not server or not source_pattern:
            return False

        # Extract workspace-derived portion from Fabric hostnames
        # Format: <workspace-name>.<service>.fabric.microsoft.com
        fabric_suffix = ".fabric.microsoft.com"
        if fabric_suffix not in server.lower():
            return False

        # Get the hostname part before .fabric.microsoft.com
        hostname = server.lower().split(fabric_suffix)[0]
        # The workspace-derived name is the first segment before the service type
        # e.g., "my-ws-dev.datawarehouse" -> "my-ws-dev"
        ws_portion = hostname.split(".")[0] if "." in hostname else hostname

        try:
            return bool(re.search(source_pattern, ws_portion, re.IGNORECASE))
        except re.error:
            logger.warning("Invalid regex pattern: %s", source_pattern)
            return False

    @staticmethod
    def _build_repointed_server(
        original_server: str, target_workspace_name: str
    ) -> str:
        """
        Build a new server string with the target workspace name.

        Replaces the workspace-derived portion of the Fabric hostname
        with the target workspace name (slugified).

        Args:
            original_server: Original server string.
            target_workspace_name: Display name of the target workspace.

        Returns:
            New server string with target workspace name.
        """
        fabric_suffix = ".fabric.microsoft.com"
        if fabric_suffix not in original_server.lower():
            return original_server

        # Split at first dot to isolate workspace portion
        hostname = original_server.split(fabric_suffix)[0]
        parts = hostname.split(".", 1)

        # Slugify workspace name: lowercase, replace spaces/special chars
        slug = re.sub(r"[^a-z0-9]", "-", target_workspace_name.lower())
        slug = re.sub(r"-+", "-", slug).strip("-")

        if len(parts) > 1:
            new_hostname = f"{slug}.{parts[1]}"
        else:
            new_hostname = slug

        return f"{new_hostname}{fabric_suffix}"

    def _build_update_detail(
        self,
        datasource: Dict[str, Any],
        target_workspace_name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Build an UpdateDatasources detail entry for a single datasource.

        Args:
            datasource: A datasource dict from the get_datasources response.
            target_workspace_name: Target workspace display name.

        Returns:
            An update detail dict, or None if the datasource type is
            not supported for repointing.
        """
        connection = datasource.get("connectionDetails", {})
        server = connection.get("server", "")
        database = connection.get("database", "")

        if not server:
            return None

        new_server = self._build_repointed_server(server, target_workspace_name)

        if new_server == server:
            return None

        update = {
            "datasourceSelector": {
                "datasourceType": datasource.get("datasourceType", ""),
                "connectionDetails": {
                    "server": server,
                    "database": database,
                },
            },
            "connectionDetails": {
                "server": new_server,
                "database": database,
            },
        }
        return update

    def repoint_workspace_models(
        self,
        workspace_id: str,
        target_workspace_name: str,
        source_pattern: str,
        dry_run: bool = False,
    ) -> RepointResult:
        """
        Repoint all semantic models in a workspace whose datasource
        connections match the source pattern.

        Args:
            workspace_id: Target workspace GUID (where models live now).
            target_workspace_name: Display name of the target workspace
                (used to derive the correct server hostname).
            source_pattern: Regex pattern matching feature workspace names
                to repoint away from (e.g., ``"feature[-_].*"``).
            dry_run: If True, report what would change without updating.

        Returns:
            RepointResult with details of all actions taken.
        """
        result = RepointResult()

        models = self.list_semantic_models(workspace_id)
        if not models:
            logger.info("No semantic models found -- nothing to repoint")
            return result

        for model in models:
            model_id = model.get("id", "")
            model_name = model.get("displayName", "unknown")

            datasources = self.get_datasources(workspace_id, model_id)
            if not datasources:
                # No SQL-type datasources found. This is expected for Direct
                # Lake models which bind to lakehouses via OneLake, not SQL
                # connections. The Power BI GetDatasources API does not surface
                # Direct Lake bindings.
                reason = (
                    "no SQL datasources found (if this is a Direct Lake model, "
                    "use deployment rules or the Bind Semantic Model Connection "
                    "API to manage its connections)"
                )
                logger.info(
                    "Model '%s' has no datasources — possibly Direct Lake",
                    model_name,
                )
                result.skipped.append({"model": model_name, "reason": reason})
                continue

            updates: List[Dict[str, Any]] = []
            for ds in datasources:
                connection = ds.get("connectionDetails", {})
                server = connection.get("server", "")

                if not self._matches_source_pattern(server, source_pattern):
                    continue

                update = self._build_update_detail(ds, target_workspace_name)
                if update:
                    updates.append(update)

            if not updates:
                result.skipped.append(
                    {
                        "model": model_name,
                        "reason": "no connections match source pattern",
                    }
                )
                continue

            if dry_run:
                for upd in updates:
                    old_server = upd["datasourceSelector"]["connectionDetails"][
                        "server"
                    ]
                    new_server = upd["connectionDetails"]["server"]
                    result.repointed.append(
                        {
                            "model": model_name,
                            "from": old_server,
                            "to": new_server,
                            "dry_run": "true",
                        }
                    )
                continue

            outcome = self.update_datasources(workspace_id, model_id, updates)
            if outcome["success"]:
                for upd in updates:
                    old_server = upd["datasourceSelector"]["connectionDetails"][
                        "server"
                    ]
                    new_server = upd["connectionDetails"]["server"]
                    result.repointed.append(
                        {
                            "model": model_name,
                            "from": old_server,
                            "to": new_server,
                        }
                    )
            else:
                result.failed.append(
                    {
                        "model": model_name,
                        "reason": outcome.get(
                            "reason", "UpdateDatasources API call failed"
                        ),
                    }
                )

        return result
