"""
Unit tests for DeploymentState - Atomic rollback tracking.

Tests verify:
- Item recording during deployment
- LIFO rollback order
- Checkpoint save/load
- Resilient error handling during rollback
"""

import json
from unittest.mock import MagicMock
import pytest

from usf_fabric_cli.services.deployment_state import (
    DeploymentState,
    ItemType,
    CreatedItem,
)


class TestCreatedItem:
    """Tests for CreatedItem dataclass."""

    def test_create_item_with_required_fields(self):
        """Test item creation with required fields only."""
        item = CreatedItem(
            item_type=ItemType.LAKEHOUSE,
            name="Bronze",
            workspace_name="DataPlatform",
        )

        assert item.item_type == ItemType.LAKEHOUSE
        assert item.name == "Bronze"
        assert item.workspace_name == "DataPlatform"
        assert item.created_at is not None

    def test_create_item_with_all_fields(self):
        """Test item creation with all fields."""
        item = CreatedItem(
            item_type=ItemType.NOTEBOOK,
            name="ProcessData",
            workspace_name="DataPlatform",
            item_id="abc-123",
            folder_name="Pipelines",
            metadata={"source": "deployment"},
        )

        assert item.item_id == "abc-123"
        assert item.folder_name == "Pipelines"
        assert item.metadata == {"source": "deployment"}

    def test_to_dict_serializes_enum(self):
        """Test to_dict converts enum to string."""
        item = CreatedItem(
            item_type=ItemType.WAREHOUSE,
            name="Gold",
            workspace_name="DataPlatform",
        )

        data = item.to_dict()

        assert data["item_type"] == "warehouse"
        assert isinstance(data["item_type"], str)

    def test_from_dict_deserializes(self):
        """Test from_dict creates item from dictionary."""
        data = {
            "item_type": "lakehouse",
            "name": "Bronze",
            "workspace_name": "DataPlatform",
            "item_id": "123",
            "folder_name": None,
            "metadata": {},
        }

        item = CreatedItem.from_dict(data)

        assert item.item_type == ItemType.LAKEHOUSE
        assert item.name == "Bronze"
        assert item.item_id == "123"


class TestDeploymentState:
    """Tests for DeploymentState tracking."""

    def test_record_adds_item(self):
        """Test recording an item adds it to state."""
        state = DeploymentState()

        item = state.record(ItemType.WORKSPACE, "MyWorkspace", "MyWorkspace")

        assert state.item_count == 1
        assert item.item_type == ItemType.WORKSPACE
        assert item.name == "MyWorkspace"

    def test_record_multiple_items(self):
        """Test recording multiple items maintains order."""
        state = DeploymentState()

        state.record(ItemType.WORKSPACE, "WS", "WS")
        state.record(ItemType.FOLDER, "Folder1", "WS")
        state.record(ItemType.LAKEHOUSE, "Bronze", "WS")

        assert state.item_count == 3
        assert [i.name for i in state.items] == ["WS", "Folder1", "Bronze"]

    def test_record_with_metadata(self):
        """Test recording with extra metadata."""
        state = DeploymentState()

        item = state.record(
            ItemType.NOTEBOOK,
            "Process",
            "WS",
            item_id="abc",
            environment="dev",
            version="1.0",
        )

        assert item.metadata == {"environment": "dev", "version": "1.0"}

    def test_start_deployment_clears_previous(self):
        """Test starting deployment clears previous items."""
        state = DeploymentState()
        state.record(ItemType.WORKSPACE, "OldWS", "OldWS")

        state.start_deployment("new-deploy")

        assert state.item_count == 0

    def test_items_returns_copy(self):
        """Test items property returns a copy."""
        state = DeploymentState()
        state.record(ItemType.WORKSPACE, "WS", "WS")

        items = state.items
        items.append(CreatedItem(ItemType.LAKEHOUSE, "X", "WS"))

        # Original should be unchanged
        assert state.item_count == 1


class TestDeploymentStateCheckpoint:
    """Tests for checkpoint save/load."""

    def test_save_checkpoint(self, tmp_path):
        """Test saving checkpoint to file."""
        checkpoint_file = tmp_path / "checkpoint.json"
        state = DeploymentState(checkpoint_path=checkpoint_file)
        state.start_deployment("test-deploy")
        state.record(ItemType.WORKSPACE, "WS", "WS")
        state.record(ItemType.LAKEHOUSE, "LH", "WS")

        state.save_checkpoint()

        assert checkpoint_file.exists()
        data = json.loads(checkpoint_file.read_text())
        assert data["deployment_id"] == "test-deploy"
        assert len(data["items"]) == 2

    def test_load_checkpoint(self, tmp_path):
        """Test loading checkpoint from file."""
        checkpoint_file = tmp_path / "checkpoint.json"
        checkpoint_data = {
            "deployment_id": "saved-deploy",
            "started_at": "2024-01-01T00:00:00Z",
            "items": [
                {"item_type": "workspace", "name": "WS", "workspace_name": "WS"},
                {"item_type": "lakehouse", "name": "LH", "workspace_name": "WS"},
            ],
        }
        checkpoint_file.write_text(json.dumps(checkpoint_data))

        state = DeploymentState(checkpoint_path=checkpoint_file)
        loaded = state.load_checkpoint()

        assert loaded is True
        assert state.item_count == 2
        assert state._deployment_id == "saved-deploy"

    def test_load_checkpoint_returns_false_if_missing(self, tmp_path):
        """Test loading missing checkpoint returns False."""
        state = DeploymentState(checkpoint_path=tmp_path / "nonexistent.json")

        loaded = state.load_checkpoint()

        assert loaded is False

    def test_auto_checkpoint_on_record(self, tmp_path):
        """Test auto-save checkpoint when recording with checkpoint_path."""
        checkpoint_file = tmp_path / "auto_checkpoint.json"
        state = DeploymentState(checkpoint_path=checkpoint_file)
        state.start_deployment()

        state.record(ItemType.WORKSPACE, "WS", "WS")

        assert checkpoint_file.exists()


class TestDeploymentStateRollback:
    """Tests for rollback functionality."""

    @pytest.fixture
    def mock_wrapper(self):
        """Create mock FabricCLIWrapper."""
        wrapper = MagicMock()
        wrapper.delete_workspace.return_value = {"success": True}
        wrapper._execute_command.return_value = {"success": True}
        return wrapper

    def test_rollback_empty_state(self, mock_wrapper):
        """Test rollback with no items."""
        state = DeploymentState()

        result = state.rollback(mock_wrapper)

        assert result["success"] is True
        assert result["deleted"] == 0

    def test_rollback_deletes_in_reverse_order(self, mock_wrapper):
        """Test rollback deletes items in LIFO order."""
        state = DeploymentState()
        state.record(ItemType.WORKSPACE, "WS", "WS")
        state.record(ItemType.LAKEHOUSE, "Bronze", "WS")
        state.record(ItemType.LAKEHOUSE, "Silver", "WS")

        deleted_items = []

        def track_delete(cmd):
            deleted_items.append(cmd[1])  # The path
            return {"success": True}

        mock_wrapper._execute_command.side_effect = track_delete

        result = state.rollback(mock_wrapper)

        assert result["deleted"] == 3
        # Should delete in reverse: Silver, Bronze, then Workspace
        assert "Silver" in deleted_items[0]
        assert "Bronze" in deleted_items[1]

    def test_rollback_continues_on_failure(self, mock_wrapper):
        """Test rollback continues when individual deletion fails."""
        state = DeploymentState()
        state.record(ItemType.LAKEHOUSE, "LH1", "WS")
        state.record(ItemType.LAKEHOUSE, "LH2", "WS")
        state.record(ItemType.LAKEHOUSE, "LH3", "WS")

        # Second deletion fails
        mock_wrapper._execute_command.side_effect = [
            {"success": True},
            {"success": False},
            {"success": True},
        ]

        result = state.rollback(mock_wrapper)

        assert result["deleted"] == 2
        assert result["failed"] == 1

    def test_rollback_stop_on_error(self, mock_wrapper):
        """Test rollback stops on error when flag set."""
        state = DeploymentState()
        state.record(ItemType.LAKEHOUSE, "LH1", "WS")
        state.record(ItemType.LAKEHOUSE, "LH2", "WS")
        state.record(ItemType.LAKEHOUSE, "LH3", "WS")

        # First deletion fails
        mock_wrapper._execute_command.side_effect = Exception("API Error")

        result = state.rollback(mock_wrapper, stop_on_error=True)

        assert result["failed"] == 1
        assert mock_wrapper._execute_command.call_count == 1

    def test_rollback_uses_delete_workspace_for_workspace(self, mock_wrapper):
        """Test rollback calls delete_workspace for workspace items."""
        state = DeploymentState()
        state.record(ItemType.WORKSPACE, "MyWorkspace", "MyWorkspace")

        state.rollback(mock_wrapper)

        mock_wrapper.delete_workspace.assert_called_once_with("MyWorkspace")

    def test_rollback_removes_checkpoint_file(self, mock_wrapper, tmp_path):
        """Test rollback removes checkpoint file after completion."""
        checkpoint_file = tmp_path / "checkpoint.json"
        checkpoint_file.write_text("{}")

        state = DeploymentState(checkpoint_path=checkpoint_file)
        state.record(ItemType.LAKEHOUSE, "LH", "WS")

        state.rollback(mock_wrapper)

        assert not checkpoint_file.exists()


class TestItemType:
    """Tests for ItemType enum."""

    def test_all_item_types_exist(self):
        """Test all expected item types are defined."""
        expected_types = [
            "WORKSPACE",
            "FOLDER",
            "LAKEHOUSE",
            "WAREHOUSE",
            "NOTEBOOK",
            "PIPELINE",
            "SEMANTIC_MODEL",
            "REPORT",
        ]

        for type_name in expected_types:
            assert hasattr(ItemType, type_name)

    def test_item_type_values_are_lowercase(self):
        """Test item type values are lowercase strings."""
        assert ItemType.LAKEHOUSE.value == "lakehouse"
        assert ItemType.SEMANTIC_MODEL.value == "semantic_model"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
