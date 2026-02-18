"""
Unit tests for configuration management
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from usf_fabric_cli.utils.config import ConfigManager


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
        config_manager = ConfigManager(config_path, validate_env=False)
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
        config_manager = ConfigManager(str(base_config_path), validate_env=False)
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
        config_manager = ConfigManager(config_path, validate_env=False)
        with pytest.raises(Exception):  # Should raise validation error
            config_manager.load_config()
    finally:
        Path(config_path).unlink()


def test_env_var_substitution():
    """Test ${VAR_NAME} substitution in config content"""
    import os

    config_data = {
        "workspace": {
            "name": "test-workspace",
            "capacity_id": "${TEST_CAPACITY_ID}",
        }
    }

    os.environ["TEST_CAPACITY_ID"] = "F64-from-env"

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config_manager = ConfigManager(config_path, validate_env=False)
            workspace_config = config_manager.load_config()
            assert workspace_config.capacity_id == "F64-from-env"
        finally:
            Path(config_path).unlink()
    finally:
        del os.environ["TEST_CAPACITY_ID"]


def test_env_var_substitution_missing_var():
    """Test that missing env vars are left as-is (${VAR_NAME} literal)"""
    import os

    # Make sure the variable does NOT exist
    os.environ.pop("NONEXISTENT_VAR_12345", None)

    config_manager = ConfigManager.__new__(ConfigManager)
    config_manager.schema = {
        "type": "object",
        "properties": {"workspace": {"type": "object"}},
    }

    result = config_manager._substitute_env_vars("capacity: ${NONEXISTENT_VAR_12345}")
    assert "${NONEXISTENT_VAR_12345}" in result


def test_merge_configs_deep_merge():
    """Test deep merge of nested dicts"""
    config_manager = ConfigManager.__new__(ConfigManager)

    base = {
        "workspace": {"name": "base-ws", "capacity_id": "F2", "description": "Base"},
        "folders": ["Bronze"],
    }
    override = {"workspace": {"capacity_id": "F64"}}

    merged = config_manager._merge_configs(base, override)

    assert merged["workspace"]["name"] == "base-ws"  # Preserved
    assert merged["workspace"]["capacity_id"] == "F64"  # Overridden
    assert merged["workspace"]["description"] == "Base"  # Preserved
    assert merged["folders"] == ["Bronze"]  # Untouched


def test_merge_configs_list_concatenation():
    """Test that lists are concatenated during merge (e.g., principals)"""
    config_manager = ConfigManager.__new__(ConfigManager)

    base = {"principals": [{"id": "user-1", "role": "Admin"}]}
    override = {"principals": [{"id": "user-2", "role": "Member"}]}

    merged = config_manager._merge_configs(base, override)

    assert len(merged["principals"]) == 2
    ids = [p["id"] for p in merged["principals"]]
    assert "user-1" in ids
    assert "user-2" in ids


def test_to_workspace_config_principal_injection():
    """Test that ADDITIONAL_ADMIN_PRINCIPAL_ID is injected"""
    import os

    config_data = {
        "workspace": {"name": "test-ws", "capacity_id": "F64"},
        "principals": [{"id": "existing-user", "role": "Member"}],
    }

    os.environ["ADDITIONAL_ADMIN_PRINCIPAL_ID"] = "injected-admin-guid"
    os.environ.pop("ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID", None)

    try:
        config_manager = ConfigManager.__new__(ConfigManager)
        wc = config_manager._to_workspace_config(config_data)

        # Should have both the existing principal and the injected admin
        assert len(wc.principals) == 2
        ids = [p["id"] for p in wc.principals]
        assert "existing-user" in ids
        assert "injected-admin-guid" in ids

        # Injected admin should have Admin role
        admin_p = [p for p in wc.principals if p["id"] == "injected-admin-guid"][0]
        assert admin_p["role"] == "Admin"
    finally:
        del os.environ["ADDITIONAL_ADMIN_PRINCIPAL_ID"]


def test_to_workspace_config_principal_deduplication():
    """Test that duplicate principal IDs are deduplicated"""
    import os

    os.environ.pop("ADDITIONAL_ADMIN_PRINCIPAL_ID", None)
    os.environ.pop("ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID", None)

    config_data = {
        "workspace": {"name": "test-ws", "capacity_id": "F64"},
        "principals": [
            {"id": "dup-user", "role": "Admin"},
            {"id": "dup-user", "role": "Member"},
            {"id": "unique-user", "role": "Viewer"},
        ],
    }

    try:
        config_manager = ConfigManager.__new__(ConfigManager)
        wc = config_manager._to_workspace_config(config_data)

        ids = [p["id"] for p in wc.principals]
        assert ids.count("dup-user") == 1  # Deduplicated
        assert "unique-user" in ids
    finally:
        pass


def test_to_workspace_config_defaults():
    """Test default values for optional fields"""
    import os

    os.environ.pop("ADDITIONAL_ADMIN_PRINCIPAL_ID", None)
    os.environ.pop("ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID", None)

    config_data = {
        "workspace": {"name": "minimal-ws", "capacity_id": "F2"},
    }

    config_manager = ConfigManager.__new__(ConfigManager)
    wc = config_manager._to_workspace_config(config_data)

    assert wc.name == "minimal-ws"
    assert wc.display_name == "minimal-ws"  # Defaults to name
    assert wc.description == ""
    assert wc.git_branch == "main"  # Default branch
    assert wc.git_directory == "/"  # Default directory
    assert wc.folders == []  # No default folders (explicit opt-in only)
    assert wc.lakehouses == []
    assert wc.notebooks == []
    assert wc.resources == []


def test_config_import_path():
    """Test that config.py imports secrets from the correct path"""
    # This verifies the P1#6 fix: from usf_fabric_cli.utils.secrets
    from usf_fabric_cli.utils.config import ConfigManager  # noqa: F811

    # If the import path were wrong, this would have already failed
    assert ConfigManager is not None


if __name__ == "__main__":
    pytest.main([__file__])
