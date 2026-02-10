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
- https://learn.microsoft.com/en-us/fabric/cicd/deployment-pipelines/intro-to-deployment-pipelines
"""

import logging
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import requests

from usf_fabric_cli.utils.retry import (
    is_retryable_exception,
    calculate_backoff,
    DEFAULT_MAX_RETRIES,
    DEFAULT_BASE_DELAY,
    DEFAULT_MAX_DELAY,
)

if TYPE_CHECKING:
    from usf_fabric_cli.services.token_manager import TokenManager

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


class FabricDeploymentPipelineAPI:
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
        self.base_url = base_url
        self._access_token = access_token
        self._token_manager = token_manager
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

    # ── token helpers ──────────────────────────────────────────────

    def _refresh_token_if_needed(self) -> None:
        """Refresh the bearer token via TokenManager when available."""
        if self._token_manager:
            try:
                new_token = self._token_manager.get_token()
                if new_token != self._access_token:
                    self._access_token = new_token
                    self.headers["Authorization"] = f"Bearer {new_token}"
                    logger.debug("Token refreshed for Deployment Pipeline API")
            except Exception as e:
                logger.warning("Token refresh failed: %s", e)

    # ── HTTP helper ────────────────────────────────────────────────

    def _make_request(
        self,
        method: str,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> requests.Response:
        """
        Execute an HTTP request with retry + exponential backoff.

        Follows the same pattern as ``FabricGitAPI._make_request``.
        """
        last_exception: Optional[Exception] = None

        for attempt in range(self._max_retries + 1):
            self._refresh_token_if_needed()

            try:
                response = requests.request(
                    method,
                    url,
                    headers=self.headers,
                    json=json,
                    timeout=timeout,
                )
                response.raise_for_status()
                return response

            except requests.RequestException as e:
                last_exception = e

                if not is_retryable_exception(e) or attempt >= self._max_retries:
                    raise

                delay = calculate_backoff(attempt, self._base_delay, self._max_delay)
                logger.warning(
                    "Deployment Pipeline API request failed (attempt %d/%d): %s. "
                    "Retrying in %.2fs…",
                    attempt + 1,
                    self._max_retries + 1,
                    str(e),
                    delay,
                )
                time.sleep(delay)

        if last_exception:
            raise last_exception
        raise RuntimeError("Retry loop completed without returning or raising")

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
        self, display_name: str, description: str = ""
    ) -> Dict[str, Any]:
        """
        Create a new deployment pipeline.

        Args:
            display_name: Pipeline display name.
            description: Optional pipeline description.

        Returns:
            ``{"success": True, "pipeline": {...}}``
        """
        url = f"{self.base_url}/deploymentPipelines"
        body = {"displayName": display_name, "description": description}

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
            logger.info(
                "Pipeline %s has %d stages", pipeline_id, len(stages)
            )
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
            logger.error("Failed to assign workspace to stage: %s", e)
            return {"success": False, "error": str(e)}

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
