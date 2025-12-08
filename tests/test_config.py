"""
Unit tests for configuration management
"""

import pytest
import tempfile
import yaml
from pathlib import Path

from src.core.config import ConfigManager, WorkspaceConfig


def test_load_basic_config():
    """Test loading basic configuration"""

    config_data = {
        "workspace": {"name": "test-workspace", "capacity_id": "F64"},
        "folders": ["Bronze", "Silver", "Gold"],
        "lakehouses": [{"name": "test-lakehouse", "folder": "Bronze"}],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        config_manager = ConfigManager(config_path)
        workspace_config = config_manager.load_config()

        assert workspace_config.name == "test-workspace"
        assert workspace_config.capacity_id == "F64"
        assert "Bronze" in workspace_config.folders
        assert len(workspace_config.lakehouses) == 1
        assert workspace_config.lakehouses[0]["name"] == "test-lakehouse"

    finally:
        Path(config_path).unlink()


def test_environment_override():
    """Test environment-specific configuration overrides"""

    base_config = {"workspace": {"name": "base-workspace", "capacity_id": "F2"}}

    env_config = {"workspace": {"capacity_id": "F64"}}  # Override capacity

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create base config
        base_config_path = temp_path / "base.yaml"
        with open(base_config_path, "w") as f:
            yaml.dump(base_config, f)

        # Create environment config
        env_dir = temp_path / "environments"
        env_dir.mkdir()
        env_config_path = env_dir / "prod.yaml"
        with open(env_config_path, "w") as f:
            yaml.dump(env_config, f)

        # Test override
        config_manager = ConfigManager(str(base_config_path))
        workspace_config = config_manager.load_config("prod")

        assert workspace_config.name == "base-workspace"  # From base
        assert workspace_config.capacity_id == "F64"  # From override


def test_config_validation():
    """Test configuration validation"""

    # Invalid config (missing required fields)
    invalid_config = {
        "workspace": {
            "name": "test-workspace"
            # Missing capacity_id
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(invalid_config, f)
        config_path = f.name

    try:
        config_manager = ConfigManager(config_path)
        with pytest.raises(Exception):  # Should raise validation error
            config_manager.load_config()
    finally:
        Path(config_path).unlink()


if __name__ == "__main__":
    pytest.main([__file__])
