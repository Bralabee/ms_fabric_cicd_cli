"""
Deployment State Tracker for Atomic Rollback.

Tracks items created during deployment to enable cleanup on failure.
Items are deleted in reverse order (LIFO) to respect dependencies.

Key Features:
- Track workspace, folders, and items during deployment
- Checkpoint/save state for recovery
- Rollback deletes items in reverse creation order
- Resilient to individual deletion failures
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from usf_fabric_cli.services.fabric_wrapper import FabricCLIWrapper

logger = logging.getLogger(__name__)


class ItemType(str, Enum):
    """Types of Fabric items that can be tracked for rollback."""
    WORKSPACE = "workspace"
    FOLDER = "folder"
    LAKEHOUSE = "lakehouse"
    WAREHOUSE = "warehouse"
    NOTEBOOK = "notebook"
    PIPELINE = "pipeline"
    SEMANTIC_MODEL = "semantic_model"
    REPORT = "report"
    EVENTSTREAM = "eventstream"
    KQL_DATABASE = "kql_database"
    SPARK_JOB_DEFINITION = "spark_job_definition"


@dataclass
class CreatedItem:
    """Record of an item created during deployment."""
    item_type: ItemType
    name: str
    workspace_name: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    item_id: Optional[str] = None
    folder_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "item_type": self.item_type.value if isinstance(self.item_type, ItemType) else self.item_type,
            "name": self.name,
            "workspace_name": self.workspace_name,
            "created_at": self.created_at,
            "item_id": self.item_id,
            "folder_name": self.folder_name,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CreatedItem":
        """Create from dictionary."""
        return cls(
            item_type=ItemType(data["item_type"]),
            name=data["name"],
            workspace_name=data["workspace_name"],
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            item_id=data.get("item_id"),
            folder_name=data.get("folder_name"),
            metadata=data.get("metadata", {}),
        )


class DeploymentState:
    """
    Tracks created items during deployment for rollback capability.
    
    Records all items created during a deployment operation. On failure,
    the rollback() method deletes items in reverse order to clean up
    partial deployments.
    
    Example:
        >>> state = DeploymentState()
        >>> state.record(ItemType.WORKSPACE, "MyWorkspace", "MyWorkspace")
        >>> state.record(ItemType.LAKEHOUSE, "Bronze", "MyWorkspace")
        >>> 
        >>> # On failure:
        >>> state.rollback(fabric_wrapper)  # Deletes Bronze, then MyWorkspace
    """
    
    def __init__(self, checkpoint_path: Optional[Path] = None):
        """
        Initialize deployment state tracker.
        
        Args:
            checkpoint_path: Optional path to save/restore state for recovery
        """
        self._created_items: List[CreatedItem] = []
        self._checkpoint_path = checkpoint_path
        self._deployment_id: Optional[str] = None
        self._started_at: Optional[str] = None
    
    @property
    def items(self) -> List[CreatedItem]:
        """Get list of created items (readonly copy)."""
        return list(self._created_items)
    
    @property
    def item_count(self) -> int:
        """Get count of tracked items."""
        return len(self._created_items)
    
    def start_deployment(self, deployment_id: Optional[str] = None) -> None:
        """
        Mark the start of a new deployment.
        
        Args:
            deployment_id: Optional identifier for this deployment
        """
        self._deployment_id = deployment_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._created_items = []
        logger.info("Deployment started: %s", self._deployment_id)
    
    def record(
        self,
        item_type: ItemType,
        name: str,
        workspace_name: str,
        item_id: Optional[str] = None,
        folder_name: Optional[str] = None,
        **metadata: Any,
    ) -> CreatedItem:
        """
        Record a successfully created item.
        
        Args:
            item_type: Type of item (workspace, lakehouse, etc.)
            name: Display name of the item
            workspace_name: Name of the containing workspace
            item_id: Optional Fabric item ID
            folder_name: Optional folder containing the item
            **metadata: Additional metadata to store
            
        Returns:
            The created item record
        """
        item = CreatedItem(
            item_type=item_type,
            name=name,
            workspace_name=workspace_name,
            item_id=item_id,
            folder_name=folder_name,
            metadata=metadata,
        )
        self._created_items.append(item)
        logger.debug("Recorded: %s '%s' in workspace '%s'", item_type.value, name, workspace_name)
        
        # Auto-checkpoint if path configured
        if self._checkpoint_path:
            self.save_checkpoint()
        
        return item
    
    def save_checkpoint(self, path: Optional[Path] = None) -> Path:
        """
        Save current state to file for recovery.
        
        Args:
            path: Override checkpoint path
            
        Returns:
            Path where checkpoint was saved
        """
        checkpoint_path = path or self._checkpoint_path
        if not checkpoint_path:
            checkpoint_path = Path(f".deployment_state_{self._deployment_id or 'unknown'}.json")
        
        state_data = {
            "deployment_id": self._deployment_id,
            "started_at": self._started_at,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "items": [item.to_dict() for item in self._created_items],
        }
        
        checkpoint_path.write_text(json.dumps(state_data, indent=2))
        logger.debug("Checkpoint saved: %s", checkpoint_path)
        return checkpoint_path
    
    def load_checkpoint(self, path: Optional[Path] = None) -> bool:
        """
        Load state from checkpoint file.
        
        Args:
            path: Override checkpoint path
            
        Returns:
            True if checkpoint loaded successfully
        """
        checkpoint_path = path or self._checkpoint_path
        if not checkpoint_path or not checkpoint_path.exists():
            return False
        
        try:
            state_data = json.loads(checkpoint_path.read_text())
            self._deployment_id = state_data.get("deployment_id")
            self._started_at = state_data.get("started_at")
            self._created_items = [
                CreatedItem.from_dict(item) for item in state_data.get("items", [])
            ]
            logger.info(
                "Checkpoint loaded: %s items from deployment %s",
                len(self._created_items),
                self._deployment_id,
            )
            return True
        except Exception as e:
            logger.error("Failed to load checkpoint: %s", e)
            return False
    
    def rollback(
        self,
        fabric_wrapper: "FabricCLIWrapper",
        stop_on_error: bool = False,
    ) -> Dict[str, Any]:
        """
        Delete created items in reverse order (LIFO).
        
        Attempts to delete all tracked items, starting with the most
        recently created. Continues on individual failures unless
        stop_on_error is True.
        
        Args:
            fabric_wrapper: FabricCLIWrapper instance for deletion
            stop_on_error: If True, stop on first deletion failure
            
        Returns:
            Summary with success/failure counts and errors
        """
        if not self._created_items:
            logger.info("No items to rollback")
            return {"success": True, "deleted": 0, "failed": 0, "errors": []}
        
        logger.warning(
            "Rolling back deployment: deleting %d items in reverse order",
            len(self._created_items),
        )
        
        deleted = 0
        failed = 0
        errors: List[Dict[str, str]] = []
        
        # Delete in reverse order (LIFO)
        for item in reversed(self._created_items):
            try:
                success = self._delete_item(fabric_wrapper, item)
                if success:
                    deleted += 1
                    logger.info(
                        "Deleted: %s '%s' from workspace '%s'",
                        item.item_type.value,
                        item.name,
                        item.workspace_name,
                    )
                else:
                    failed += 1
                    errors.append({
                        "item": f"{item.item_type.value}:{item.name}",
                        "error": "Deletion returned failure",
                    })
            except Exception as e:
                failed += 1
                error_msg = str(e)
                errors.append({
                    "item": f"{item.item_type.value}:{item.name}",
                    "error": error_msg,
                })
                logger.error(
                    "Failed to delete %s '%s': %s",
                    item.item_type.value,
                    item.name,
                    error_msg,
                )
                if stop_on_error:
                    break
        
        # Clear checkpoint after rollback attempt
        if self._checkpoint_path and self._checkpoint_path.exists():
            try:
                self._checkpoint_path.unlink()
                logger.debug("Checkpoint file removed after rollback")
            except Exception:
                pass
        
        result = {
            "success": failed == 0,
            "deleted": deleted,
            "failed": failed,
            "errors": errors,
        }
        
        if failed == 0:
            logger.info("Rollback complete: %d items deleted", deleted)
        else:
            logger.warning(
                "Rollback completed with errors: %d deleted, %d failed",
                deleted,
                failed,
            )
        
        return result
    
    def _delete_item(self, fabric_wrapper: "FabricCLIWrapper", item: CreatedItem) -> bool:
        """
        Delete a single item based on its type.
        
        Args:
            fabric_wrapper: FabricCLIWrapper instance
            item: Item to delete
            
        Returns:
            True if deletion succeeded
        """
        if item.item_type == ItemType.WORKSPACE:
            result = fabric_wrapper.delete_workspace(item.name)
        else:
            # For non-workspace items, we need to construct the path
            # Format: workspace.Workspace/name.Type
            type_suffix = self._get_type_suffix(item.item_type)
            path = f"{item.workspace_name}.Workspace/{item.name}.{type_suffix}"
            
            # Use rm command via _execute_command
            command = ["rm", path, "--force"]
            result = fabric_wrapper._execute_command(command)
        
        return result.get("success", False)
    
    def _get_type_suffix(self, item_type: ItemType) -> str:
        """Get Fabric CLI type suffix for an item type."""
        type_map = {
            ItemType.LAKEHOUSE: "Lakehouse",
            ItemType.WAREHOUSE: "Warehouse",
            ItemType.NOTEBOOK: "Notebook",
            ItemType.PIPELINE: "DataPipeline",
            ItemType.SEMANTIC_MODEL: "SemanticModel",
            ItemType.REPORT: "Report",
            ItemType.FOLDER: "Folder",
            ItemType.EVENTSTREAM: "Eventstream",
            ItemType.KQL_DATABASE: "KQLDatabase",
            ItemType.SPARK_JOB_DEFINITION: "SparkJobDefinition",
        }
        return type_map.get(item_type, item_type.value)
    
    def clear(self) -> None:
        """Clear all tracked items."""
        self._created_items = []
        logger.debug("Deployment state cleared")
