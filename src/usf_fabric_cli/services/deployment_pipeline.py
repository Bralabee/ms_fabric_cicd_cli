"""
Fabric Deployment Pipeline API — Dev → Test → Prod promotion service.

Wraps the Microsoft Fabric REST API for Deployment Pipelines, enabling
automated stage promotion through CI/CD pipelines.

Key Features:
- List, create, and manage deployment pipelines
- Deploy (promote) content between stages (Dev → Test → Prod)
- Long-running operation polling for async deployments
- Automatic retry with exponential backoff for transient failures
- Token refresh support via TokenManager

References:
- https://learn.microsoft.com/en-us/rest/api/fabric/core/\
  deployment-pipelines
- https://learn.microsoft.com/en-us/fabric/cicd/\
  deployment-pipelines/intro-to-deployment-pipelines
"""

import logging
import time
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

# ── Power BI API constants ─────────────────────────────────────────
# The Fabric REST API (api.fabric.microsoft.com) does NOT expose a
# /users endpoint for deployment pipelines.  Pipeline user management
# is only available via the Power BI REST API (api.powerbi.com).
# Reference: https://learn.microsoft.com/en-us/rest/api/power-bi/
#            pipelines/update-user-as-admin
PBI_API_BASE_URL = "https://api.powerbi.com/v1.0/myorg"
PBI_TOKEN_SCOPE = "https://analysis.windows.net/powerbi/api/.default"

# The Power BI API uses "App" for Service Principals, not
# "ServicePrincipal" as used elsewhere in Microsoft APIs.
PBI_PRINCIPAL_TYPE_MAP = {
    "ServicePrincipal": "App",
    "serviceprincipal": "App",
    "App": "App",
    "app": "App",
    "User": "User",
    "user": "User",
    "Group": "Group",
    "group": "Group",
}

logger = logging.getLogger(__name__)


class DeploymentStage:
    """Known deployment pipeline stage names, in order."""

    DEV = "Development"
    TEST = "Test"
    PROD = "Production"

    ORDER = [DEV, TEST, PROD]

    @classmethod
    def next_stage(cls, current: str) -> Optional[str]:
        """Return the next stage after *current*, or None for Production."""
        try:
            idx = cls.ORDER.index(current)
            return cls.ORDER[idx + 1] if idx + 1 < len(cls.ORDER) else None
        except ValueError:
            return None


class FabricDeploymentPipelineAPI(FabricAPIBase):
    """
    Client for the Fabric Deployment Pipelines REST API.

    Provides methods to manage deployment pipelines and promote content
    between stages (Dev → Test → Prod).
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
        """
        Initialise the Deployment Pipeline API client.

        Args:
            access_token: Azure AD / Entra ID token with Fabric API scope.
            base_url: Fabric REST API base URL.
            token_manager: Optional TokenManager for proactive refresh.
            max_retries: Maximum retry attempts for transient failures.
            base_delay: Initial backoff delay in seconds.
            max_delay: Maximum backoff delay in seconds.
        """
        super().__init__(
            access_token=access_token,
            base_url=base_url,
            token_manager=token_manager,
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
        )
        # Cache for Power BI API token (lazily acquired)
        self._pbi_token: Optional[str] = None

    # ── Power BI token helpers ─────────────────────────────────────

    def _get_pbi_headers(self) -> Dict[str, str]:
        """
        Get HTTP headers for Power BI REST API calls.

        Acquires a PBI-scoped token from the TokenManager's credential
        (same Service Principal, different resource scope). Falls back
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
                    logger.debug("Acquired Power BI API token for pipeline users")
                except Exception as exc:
                    logger.warning(
                        "Could not acquire PBI token (%s); "
                        "falling back to Fabric token",
                        exc,
                    )
                    self._pbi_token = self._access_token
            else:
                # No credential available — try Fabric token (may work
                # when Fabric and PBI share the same backend auth).
                self._pbi_token = self._access_token

        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._pbi_token}",
        }

    @staticmethod
    def _map_principal_type(principal_type: str) -> str:
        """Map standard principal types to Power BI API equivalents."""
        return PBI_PRINCIPAL_TYPE_MAP.get(principal_type, principal_type)

    # ── Pipeline CRUD ──────────────────────────────────────────────

    def list_pipelines(self) -> Dict[str, Any]:
        """
        List all deployment pipelines accessible to the caller.

        Returns:
            ``{"success": True, "pipelines": [...]}``
        """
        url = f"{self.base_url}/deploymentPipelines"

        try:
            response = self._make_request("GET", url)
            data = response.json()
            pipelines = data.get("value", [])
            logger.info("Found %d deployment pipelines", len(pipelines))
            return {"success": True, "pipelines": pipelines}
        except requests.RequestException as e:
            logger.error("Failed to list deployment pipelines: %s", e)
            return {"success": False, "error": str(e)}

    def get_pipeline(self, pipeline_id: str) -> Dict[str, Any]:
        """
        Get details of a single deployment pipeline.

        Args:
            pipeline_id: Fabric deployment pipeline ID.

        Returns:
            ``{"success": True, "pipeline": {...}}``
        """
        url = f"{self.base_url}/deploymentPipelines/{pipeline_id}"

        try:
            response = self._make_request("GET", url)
            return {"success": True, "pipeline": response.json()}
        except requests.RequestException as e:
            logger.error("Failed to get pipeline %s: %s", pipeline_id, e)
            return {"success": False, "error": str(e)}

    def get_pipeline_by_name(self, display_name: str) -> Optional[Dict[str, Any]]:
        """Look up a pipeline by its display name."""
        result = self.list_pipelines()
        if result["success"]:
            for p in result["pipelines"]:
                if p.get("displayName") == display_name:
                    return p
        return None

    def create_pipeline(
        self,
        display_name: str,
        description: str = "",
        stages: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new deployment pipeline.

        Args:
            display_name: Pipeline display name.
            description: Optional pipeline description.
            stages: Optional list of stage definitions. Each stage is a dict
                with ``displayName`` (required), ``description`` (optional),
                and ``isPublic`` (optional, bool). Defaults to the standard
                three-stage pipeline: Development → Test → Production.

        Returns:
            ``{"success": True, "pipeline": {...}}``
        """
        url = f"{self.base_url}/deploymentPipelines"

        # Default to the standard 3-stage pipeline if no custom stages given
        if stages is None:
            stages = [
                {
                    "displayName": DeploymentStage.DEV,
                    "description": "Development stage",
                },
                {
                    "displayName": DeploymentStage.TEST,
                    "description": "Test / QA stage",
                },
                {
                    "displayName": DeploymentStage.PROD,
                    "description": "Production stage",
                },
            ]

        body: Dict[str, Any] = {
            "displayName": display_name,
            "description": description,
            "stages": stages,
        }

        try:
            response = self._make_request("POST", url, json=body)
            pipeline = response.json()
            logger.info("Created deployment pipeline: %s", pipeline.get("id"))
            return {"success": True, "pipeline": pipeline}
        except requests.RequestException as e:
            logger.error("Failed to create pipeline: %s", e)
            return {"success": False, "error": str(e)}

    def delete_pipeline(self, pipeline_id: str) -> Dict[str, Any]:
        """
        Delete a deployment pipeline.

        Args:
            pipeline_id: Pipeline ID to delete.
        """
        url = f"{self.base_url}/deploymentPipelines/{pipeline_id}"

        try:
            self._make_request("DELETE", url)
            logger.info("Deleted deployment pipeline: %s", pipeline_id)
            return {"success": True}
        except requests.RequestException as e:
            logger.error("Failed to delete pipeline %s: %s", pipeline_id, e)
            return {"success": False, "error": str(e)}

    # ── Pipeline user / access management ──────────────────────────

    def list_pipeline_users(self, pipeline_id: str) -> Dict[str, Any]:
        """
        List users (principals) who have access to a deployment pipeline.

        Uses the **Power BI REST API** (``api.powerbi.com``) because the
        Fabric REST API does not expose a ``/users`` endpoint for
        deployment pipelines.

        Ref: https://learn.microsoft.com/en-us/rest/api/power-bi/
             pipelines/get-pipeline-users

        Args:
            pipeline_id: Deployment pipeline ID.

        Returns:
            ``{"success": True, "users": [...]}``
        """
        url = f"{PBI_API_BASE_URL}/pipelines/{pipeline_id}/users"
        pbi_headers = self._get_pbi_headers()

        try:
            response = requests.get(url, headers=pbi_headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            users = data.get("value", [])
            logger.info("Pipeline %s has %d users", pipeline_id, len(users))
            return {"success": True, "users": users}
        except requests.RequestException as e:
            logger.error("Failed to list pipeline users for %s: %s", pipeline_id, e)
            return {"success": False, "error": str(e)}

    def add_pipeline_user(
        self,
        pipeline_id: str,
        identifier: str,
        principal_type: str = "Group",
        pipeline_role: str = "Admin",
    ) -> Dict[str, Any]:
        """
        Add a user / group / service principal to a deployment pipeline.

        Uses the **Power BI REST API** (``api.powerbi.com``) because the
        Fabric REST API does not expose a ``/users`` endpoint for
        deployment pipelines.

        .. note::

           - ``principalType`` is automatically mapped: ``"ServicePrincipal"``
             becomes ``"App"`` as required by the Power BI API.
           - ``accessRight`` (the PBI field) replaces ``pipelineRole``.
           - Deployment pipelines only support ``"Admin"`` access.

        Ref: https://learn.microsoft.com/en-us/rest/api/power-bi/
             pipelines/update-user-as-admin

        Args:
            pipeline_id: Deployment pipeline ID.
            identifier: Object ID (GUID) of the user, group, or SP.
            principal_type: ``"User"``, ``"Group"``, ``"ServicePrincipal"``,
                or ``"App"``.  SP types are mapped to ``"App"`` automatically.
            pipeline_role: ``"Admin"`` (currently the only supported role).

        Returns:
            ``{"success": True}`` or ``{"success": False, "error": "..."}``
        """
        url = f"{PBI_API_BASE_URL}/pipelines/{pipeline_id}/users"
        pbi_headers = self._get_pbi_headers()

        # Map principal type to PBI equivalent
        pbi_principal_type = self._map_principal_type(principal_type)

        body = {
            "identifier": identifier,
            "principalType": pbi_principal_type,
            "accessRight": pipeline_role,
        }

        try:
            response = requests.post(url, headers=pbi_headers, json=body, timeout=30)
            response.raise_for_status()
            logger.info(
                "Added %s (PBI: %s) %s as %s to pipeline %s",
                principal_type,
                pbi_principal_type,
                identifier[:12],
                pipeline_role,
                pipeline_id,
            )
            return {"success": True}
        except requests.RequestException as e:
            error_detail = ""
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_detail = e.response.text
                except Exception:
                    error_detail = ""

            # Already exists is OK (idempotent)
            combined = f"{e} {error_detail}".lower()
            if "already" in combined or "exists" in combined:
                logger.info(
                    "Principal %s already has access to pipeline %s",
                    identifier[:12],
                    pipeline_id,
                )
                return {"success": True, "reused": True}

            logger.error(
                "Failed to add user %s to pipeline %s: %s (detail: %s)",
                identifier[:12],
                pipeline_id,
                e,
                error_detail,
            )
            return {
                "success": False,
                "error": str(e),
                "error_detail": error_detail,
            }

    # ── Stage management ───────────────────────────────────────────

    def get_pipeline_stages(self, pipeline_id: str) -> Dict[str, Any]:
        """
        List stages for a pipeline.

        Args:
            pipeline_id: Deployment pipeline ID.

        Returns:
            ``{"success": True, "stages": [...]}``
        """
        url = f"{self.base_url}/deploymentPipelines/{pipeline_id}/stages"

        try:
            response = self._make_request("GET", url)
            data = response.json()
            stages = data.get("value", [])
            logger.info("Pipeline %s has %d stages", pipeline_id, len(stages))
            return {"success": True, "stages": stages}
        except requests.RequestException as e:
            logger.error("Pipeline stages fetch failed: %s", e)
            return {"success": False, "error": str(e)}

    def assign_workspace_to_stage(
        self, pipeline_id: str, stage_id: str, workspace_id: str
    ) -> Dict[str, Any]:
        """
        Assign a Fabric workspace to a deployment pipeline stage.

        Args:
            pipeline_id: Pipeline ID.
            stage_id: Stage ID within the pipeline.
            workspace_id: Workspace to assign.

        Returns:
            ``{"success": True}``
        """
        url = (
            f"{self.base_url}/deploymentPipelines/{pipeline_id}"
            f"/stages/{stage_id}/assignWorkspace"
        )
        body = {"workspaceId": workspace_id}

        try:
            self._make_request("POST", url, json=body)
            logger.info(
                "Assigned workspace %s to stage %s in pipeline %s",
                workspace_id,
                stage_id,
                pipeline_id,
            )
            return {"success": True}
        except requests.RequestException as e:
            # Capture the API response body for better error classification
            error_detail = ""
            status_code = None
            if hasattr(e, "response") and e.response is not None:
                status_code = e.response.status_code
                try:
                    error_detail = e.response.text
                except Exception:
                    error_detail = ""

            logger.error(
                "Failed to assign workspace to stage: %s (detail: %s)",
                e,
                error_detail,
            )
            return {
                "success": False,
                "error": str(e),
                "error_detail": error_detail,
                "status_code": status_code,
            }

    def unassign_workspace_from_stage(
        self, pipeline_id: str, stage_id: str
    ) -> Dict[str, Any]:
        """
        Remove the workspace assigned to a pipeline stage.

        Args:
            pipeline_id: Pipeline ID.
            stage_id: Stage ID to unassign.
        """
        url = (
            f"{self.base_url}/deploymentPipelines/{pipeline_id}"
            f"/stages/{stage_id}/unassignWorkspace"
        )

        try:
            self._make_request("POST", url)
            logger.info(
                "Unassigned workspace from stage %s in pipeline %s",
                stage_id,
                pipeline_id,
            )
            return {"success": True}
        except requests.RequestException as e:
            logger.error("Failed to unassign workspace from stage: %s", e)
            return {"success": False, "error": str(e)}

    # ── Deploy (promote) ───────────────────────────────────────────

    def deploy_to_stage(
        self,
        pipeline_id: str,
        source_stage_id: str,
        target_stage_id: str,
        items: Optional[List[Dict[str, str]]] = None,
        note: str = "",
        allow_create_artifact: bool = True,
        allow_overwrite_artifact: bool = True,
    ) -> Dict[str, Any]:
        """
        Promote (deploy) content from one pipeline stage to the next.

        This is a **long-running operation**. Use :py:meth:`poll_operation`
        to wait for completion.

        Args:
            pipeline_id: Pipeline ID.
            source_stage_id: Stage to deploy FROM.
            target_stage_id: Stage to deploy TO.
            items: Optional selective list of items to deploy.
                   Each: ``{"itemId": "...", "type": "..."}``
            note: Deployment note / description.
            allow_create_artifact: Create new items in target if missing.
            allow_overwrite_artifact: Overwrite existing items in target.

        Returns:
            ``{"success": True, "operation_id": "...", "retry_after": N}``
        """
        url = f"{self.base_url}/deploymentPipelines/{pipeline_id}/deploy"

        body: Dict[str, Any] = {
            "sourceStageId": source_stage_id,
            "targetStageId": target_stage_id,
            "note": note,
            "options": {
                "allowCreateArtifact": allow_create_artifact,
                "allowOverwriteArtifact": allow_overwrite_artifact,
            },
        }

        if items:
            body["items"] = items

        try:
            response = self._make_request("POST", url, json=body, timeout=60)

            operation_id = response.headers.get("x-ms-operation-id")
            retry_after = int(response.headers.get("Retry-After", "10"))

            logger.info(
                "Deployment started: %s → %s (operation: %s)",
                source_stage_id,
                target_stage_id,
                operation_id,
            )
            return {
                "success": True,
                "operation_id": operation_id,
                "retry_after": retry_after,
            }
        except requests.RequestException as e:
            logger.error("Deployment failed: %s", e)
            error_detail = ""
            if hasattr(e, "response") and e.response is not None:
                error_detail = e.response.text
            return {"success": False, "error": str(e), "details": error_detail}

    # ── Long-running ops ───────────────────────────────────────────

    def poll_operation(
        self,
        operation_id: str,
        max_attempts: int = 60,
        retry_after: int = 10,
    ) -> Dict[str, Any]:
        """
        Poll a long-running operation until completion.

        Args:
            operation_id: Operation ID from deploy_to_stage.
            max_attempts: Maximum polling attempts.
            retry_after: Seconds between polls.

        Returns:
            ``{"success": True/False, "status": "...", "result": {...}}``
        """
        url = f"{self.base_url}/operations/{operation_id}"

        for attempt in range(max_attempts):
            try:
                response = self._make_request("GET", url)
                result = response.json()
                status = result.get("status", "Unknown")

                logger.debug(
                    "Operation %s status: %s (attempt %d/%d)",
                    operation_id,
                    status,
                    attempt + 1,
                    max_attempts,
                )

                if status in ("Succeeded", "Failed", "Cancelled"):
                    return {
                        "success": status == "Succeeded",
                        "status": status,
                        "result": result,
                    }

                time.sleep(retry_after)

            except requests.RequestException as e:
                logger.error("Failed to poll operation %s: %s", operation_id, e)
                return {"success": False, "error": str(e)}

        logger.error(
            "Operation %s timed out after %d seconds",
            operation_id,
            max_attempts * retry_after,
        )
        return {"success": False, "error": "Operation timed out", "status": "Timeout"}

    # ── Stage items ───────────────────────────────────────────────

    def list_stage_items(
        self,
        pipeline_id: str,
        stage_id: str,
    ) -> Dict[str, Any]:
        """
        List all items in a deployment pipeline stage.

        Args:
            pipeline_id: Pipeline ID.
            stage_id: Stage ID.

        Returns:
            ``{"success": True, "items": [...]}``
        """
        url = (
            f"{self.base_url}/deploymentPipelines/{pipeline_id}"
            f"/stages/{stage_id}/items"
        )

        try:
            response = self._make_request("GET", url)
            data = response.json()
            items = data.get("value", [])
            logger.info("Stage %s has %d items", stage_id, len(items))
            return {"success": True, "items": items}
        except requests.RequestException as e:
            logger.error("Failed to list stage items: %s", e)
            return {"success": False, "error": str(e)}

    # ── Selective deployment ───────────────────────────────────────

    # Item types that cannot be deployed via Service Principal
    UNSUPPORTED_SP_TYPES = {"Warehouse", "SQLEndpoint"}

    def _build_selective_items(
        self,
        source_items: List[Dict],
        target_items: List[Dict],
        exclude_types: Optional[set] = None,
    ) -> Dict[str, Any]:
        """
        Build the selective deploy payload.

        Excludes items whose type is in *exclude_types* and pairs source
        items with target items by display name to avoid
        ``TargetArtifactNameConflict`` errors.

        Returns:
            ``{"deployable": [...], "excluded": [...], "paired": int}``
        """
        if exclude_types is None:
            exclude_types = self.UNSUPPORTED_SP_TYPES

        # Target lookup: (name, type) → target item ID
        target_by_name: Dict = {}
        for t in target_items:
            key = (t.get("itemDisplayName"), t.get("itemType"))
            target_by_name[key] = t.get("itemId")

        deployable: List[Dict] = []
        excluded: List[Dict] = []
        paired = 0

        for item in source_items:
            item_type = item.get("itemType", "")
            item_name = item.get("itemDisplayName", "")

            if item_type in exclude_types:
                excluded.append(item)
                continue

            entry: Dict[str, str] = {
                "sourceItemId": item["itemId"],
                "itemType": item_type,
            }

            # Pair with existing target item to avoid name conflicts
            target_id = target_by_name.get((item_name, item_type))
            if target_id:
                entry["targetItemId"] = target_id
                paired += 1

            deployable.append(entry)

        return {"deployable": deployable, "excluded": excluded, "paired": paired}

    @staticmethod
    def _extract_failing_item_ids(result: Dict) -> set:
        """
        Extract item IDs that caused deployment failure from the
        operation error response.
        """
        failing_ids: set = set()
        error = result.get("result", result).get("error", {})
        for detail in error.get("moreDetails", []):
            resource = detail.get("relatedResource", {})
            resource_id = resource.get("resourceId")
            if resource_id:
                failing_ids.add(resource_id)
        return failing_ids

    def selective_promote(
        self,
        pipeline_id: str,
        source_stage_name: str,
        target_stage_name: Optional[str] = None,
        note: str = "",
        exclude_types: Optional[set] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Promote content selectively, excluding unsupported item types
        and retrying with auto-exclusion of items that fail.

        This replicates the logic of the standalone ``selective_promote.py``
        script inside the CLI so workflows can use a single command.

        Args:
            pipeline_id: Pipeline ID.
            source_stage_name: Source stage display name.
            target_stage_name: Target stage display name (auto-inferred
                               if omitted).
            note: Deployment note.
            exclude_types: Item types to exclude. Defaults to
                           ``UNSUPPORTED_SP_TYPES`` (Warehouse,
                           SQLEndpoint).
            max_retries: Maximum deploy attempts, auto-excluding
                         failing items between retries.

        Returns:
            ``{"success": True/False, ...}``
            A result with ``"no_items": True`` when there is nothing
            deployable (analogous to exit code 2 of the script).
        """
        if target_stage_name is None:
            target_stage_name = DeploymentStage.next_stage(source_stage_name)
            if target_stage_name is None:
                return {
                    "success": False,
                    "error": f"No next stage after '{source_stage_name}'",
                }

        effective_excludes = (
            exclude_types
            if exclude_types is not None
            else set(self.UNSUPPORTED_SP_TYPES)
        )

        # Resolve stage IDs
        stages_result = self.get_pipeline_stages(pipeline_id)
        if not stages_result["success"]:
            return stages_result

        source_id: Optional[str] = None
        target_id: Optional[str] = None
        for stage in stages_result["stages"]:
            if stage.get("displayName") == source_stage_name:
                source_id = stage["id"]
            if stage.get("displayName") == target_stage_name:
                target_id = stage["id"]

        if not source_id:
            return {
                "success": False,
                "error": (f"Source stage '{source_stage_name}' not found"),
            }
        if not target_id:
            return {
                "success": False,
                "error": (f"Target stage '{target_stage_name}' not found"),
            }

        # List items in both stages
        source_result = self.list_stage_items(pipeline_id, source_id)
        if not source_result["success"]:
            return source_result
        source_items = source_result["items"]

        target_result = self.list_stage_items(pipeline_id, target_id)
        if not target_result["success"]:
            return target_result
        target_items = target_result["items"]

        logger.info(
            "Source stage has %d items, target has %d items",
            len(source_items),
            len(target_items),
        )

        if not source_items:
            return {
                "success": True,
                "no_items": True,
                "message": (f"No items in {source_stage_name} stage"),
            }

        # Build selective items
        sel = self._build_selective_items(
            source_items, target_items, effective_excludes
        )
        current_items = sel["deployable"]
        type_excluded = sel["excluded"]

        if type_excluded:
            types_summary: Dict[str, list] = {}
            for item in type_excluded:
                t = item.get("itemType", "Unknown")
                types_summary.setdefault(t, []).append(item.get("itemDisplayName", "?"))
            for item_type, names in types_summary.items():
                logger.warning(
                    "Excluding %d %s item(s) (unsupported for SP " "promotion): %s",
                    len(names),
                    item_type,
                    ", ".join(names),
                )

        if not current_items:
            return {
                "success": True,
                "no_items": True,
                "message": (
                    f"All {len(source_items)} items are excluded "
                    f"types — nothing to promote"
                ),
            }

        logger.info(
            "Deploying %d items (%d excluded, %d paired with target)",
            len(current_items),
            len(type_excluded),
            sel["paired"],
        )

        # Deploy with retry + auto-exclusion of failing items
        auto_excluded: List[Dict] = []

        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                logger.info(
                    "Retry %d/%d: deploying %d items "
                    "(%d auto-excluded due to errors)",
                    attempt,
                    max_retries,
                    len(current_items),
                    len(auto_excluded),
                )

            deploy_result = self.deploy_to_stage(
                pipeline_id=pipeline_id,
                source_stage_id=source_id,
                target_stage_id=target_id,
                items=current_items,
                note=note or f"Promote {source_stage_name} → {target_stage_name}",
            )

            if not deploy_result["success"]:
                return deploy_result

            # Poll completion
            poll_result = self.poll_operation(
                deploy_result["operation_id"],
                retry_after=deploy_result.get("retry_after", 10),
            )

            if poll_result["success"]:
                total_excluded = len(type_excluded) + len(auto_excluded)
                msg = (
                    f"Promotion succeeded: "
                    f"{source_stage_name} → {target_stage_name}"
                )
                if total_excluded:
                    msg += (
                        f" ({len(type_excluded)} type-excluded + "
                        f"{len(auto_excluded)} error-excluded)"
                    )
                return {
                    "success": True,
                    "message": msg,
                    "type_excluded": len(type_excluded),
                    "auto_excluded": len(auto_excluded),
                    "deployed": len(current_items),
                }

            # Deployment failed — try to auto-exclude failing items
            failing_ids = self._extract_failing_item_ids(poll_result)
            if not failing_ids or attempt == max_retries:
                break

            new_items = []
            for item in current_items:
                if item["sourceItemId"] in failing_ids:
                    auto_excluded.append(item)
                    logger.warning(
                        "Auto-excluding failing item: %s (%s)",
                        item.get("itemType", "?"),
                        item["sourceItemId"][:12],
                    )
                else:
                    new_items.append(item)

            if len(new_items) == len(current_items):
                logger.warning("Could not identify specific failing items to exclude")
                break

            if not new_items:
                return {
                    "success": True,
                    "no_items": True,
                    "message": "All remaining items failed",
                }

            current_items = new_items
            # Brief wait before retry
            import time as _time

            _time.sleep(30)

        # All retries exhausted
        return {
            "success": False,
            "error": f"Promotion failed after {max_retries} attempts",
            "result": poll_result.get("result", {}),
        }

    # ── Convenience: full promotion ────────────────────────────────

    def promote(
        self,
        pipeline_id: str,
        source_stage_name: str,
        target_stage_name: Optional[str] = None,
        note: str = "",
        wait: bool = True,
    ) -> Dict[str, Any]:
        """
        High-level: promote content from one named stage to the next.

        If *target_stage_name* is not given, it is inferred as the next
        stage in the standard Dev → Test → Prod sequence.

        Args:
            pipeline_id: Pipeline ID.
            source_stage_name: Display name of the source stage
                               (e.g. "Development").
            target_stage_name: Display name of the target stage
                               (e.g. "Test"). Auto-inferred if omitted.
            note: Deployment note.
            wait: If True, block until the deployment finishes.

        Returns:
            Deployment result.
        """
        if target_stage_name is None:
            target_stage_name = DeploymentStage.next_stage(source_stage_name)
            if target_stage_name is None:
                return {
                    "success": False,
                    "error": f"No next stage after '{source_stage_name}'",
                }

        # Resolve stage IDs
        stages_result = self.get_pipeline_stages(pipeline_id)
        if not stages_result["success"]:
            return stages_result

        source_id: Optional[str] = None
        target_id: Optional[str] = None
        for stage in stages_result["stages"]:
            if stage.get("displayName") == source_stage_name:
                source_id = stage["id"]
            if stage.get("displayName") == target_stage_name:
                target_id = stage["id"]

        if not source_id:
            return {
                "success": False,
                "error": f"Source stage '{source_stage_name}' not found",
            }
        if not target_id:
            return {
                "success": False,
                "error": f"Target stage '{target_stage_name}' not found",
            }

        # Kick off deployment
        deploy_result = self.deploy_to_stage(
            pipeline_id=pipeline_id,
            source_stage_id=source_id,
            target_stage_id=target_id,
            note=note or f"Promote {source_stage_name} → {target_stage_name}",
        )

        if not deploy_result["success"] or not wait:
            return deploy_result

        # Wait for completion
        return self.poll_operation(
            deploy_result["operation_id"],
            retry_after=deploy_result.get("retry_after", 10),
        )
