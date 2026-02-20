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


# ──────────────────────────────────────────────────────────────────
# Fallback chain tests for _substitute_env_vars  (TF-005 / TF-006)
# ──────────────────────────────────────────────────────────────────


class TestSubstituteEnvVarsFallback:
    """Tests for ${VAR:-FALLBACK_VAR} syntax in _substitute_env_vars."""

    @staticmethod
    def _make_cm():
        """Create a bare ConfigManager without loading a file."""
        cm = ConfigManager.__new__(ConfigManager)
        cm.schema = {"type": "object", "properties": {"workspace": {"type": "object"}}}
        return cm

    def test_primary_var_set(self):
        """When the primary variable IS set, it should be used (fallback ignored)."""
        import os

        os.environ["CAP_PRIMARY_001"] = "guid-primary"
        os.environ["CAP_FALLBACK_001"] = "guid-fallback"
        try:
            cm = self._make_cm()
            result = cm._substitute_env_vars("${CAP_PRIMARY_001:-CAP_FALLBACK_001}")
            assert result == "guid-primary"
        finally:
            os.environ.pop("CAP_PRIMARY_001", None)
            os.environ.pop("CAP_FALLBACK_001", None)

    def test_fallback_used_when_primary_missing(self):
        """When primary is NOT set but fallback IS, the fallback value is returned."""
        import os

        os.environ.pop("CAP_MISSING_002", None)
        os.environ["CAP_FALLBACK_002"] = "guid-from-fallback"
        try:
            cm = self._make_cm()
            result = cm._substitute_env_vars("${CAP_MISSING_002:-CAP_FALLBACK_002}")
            assert result == "guid-from-fallback"
        finally:
            os.environ.pop("CAP_FALLBACK_002", None)

    def test_neither_set_returns_literal(self):
        """When neither primary nor fallback is set, the literal ${...} is preserved."""
        import os

        os.environ.pop("CAP_NONE_A_003", None)
        os.environ.pop("CAP_NONE_B_003", None)

        cm = self._make_cm()
        result = cm._substitute_env_vars("${CAP_NONE_A_003:-CAP_NONE_B_003}")
        assert result == "${CAP_NONE_A_003:-CAP_NONE_B_003}"

    def test_mixed_standard_and_fallback(self):
        """Standard ${VAR} and fallback ${VAR:-FB} can coexist in the same string."""
        import os

        os.environ["MIX_STD_004"] = "val-std"
        os.environ.pop("MIX_PRI_004", None)
        os.environ["MIX_FB_004"] = "val-fb"
        try:
            cm = self._make_cm()
            content = "name: ${MIX_STD_004}, cap: ${MIX_PRI_004:-MIX_FB_004}"
            result = cm._substitute_env_vars(content)
            assert result == "name: val-std, cap: val-fb"
        finally:
            os.environ.pop("MIX_STD_004", None)
            os.environ.pop("MIX_FB_004", None)

    def test_multiple_fallback_vars_in_same_content(self):
        """Multiple fallback expressions are each resolved independently."""
        import os

        os.environ["MULTI_A_005"] = "resolved-a"
        os.environ.pop("MULTI_B_005", None)
        os.environ["MULTI_B_FB_005"] = "resolved-b-fb"
        try:
            cm = self._make_cm()
            content = (
                "test: ${MULTI_A_005:-UNUSED_005}, prod: ${MULTI_B_005:-MULTI_B_FB_005}"
            )
            result = cm._substitute_env_vars(content)
            assert result == "test: resolved-a, prod: resolved-b-fb"
        finally:
            os.environ.pop("MULTI_A_005", None)
            os.environ.pop("MULTI_B_FB_005", None)

    def test_inline_comment_stripping(self):
        """Env var values with inline comments are sanitized."""
        import os

        os.environ["COMMENTED_006"] = "some-guid  # this is a comment"
        try:
            cm = self._make_cm()
            result = cm._substitute_env_vars("${COMMENTED_006:-UNUSED_006}")
            assert result == "some-guid"
        finally:
            os.environ.pop("COMMENTED_006", None)

    def test_whitespace_in_fallback_expression(self):
        """Whitespace around :- separator is trimmed."""
        import os

        os.environ.pop("WS_PRI_007", None)
        os.environ["WS_FB_007"] = "trimmed-result"
        try:
            cm = self._make_cm()
            result = cm._substitute_env_vars("${WS_PRI_007 :- WS_FB_007}")
            assert result == "trimmed-result"
        finally:
            os.environ.pop("WS_FB_007", None)

    def test_empty_primary_still_uses_primary(self):
        """An empty-string primary is a valid value — fallback is NOT triggered."""
        import os

        os.environ["EMPTY_PRI_008"] = ""
        os.environ["EMPTY_FB_008"] = "should-not-use"
        try:
            cm = self._make_cm()
            result = cm._substitute_env_vars("${EMPTY_PRI_008:-EMPTY_FB_008}")
            # Empty string is a valid env value (not None), so primary wins
            assert result == ""
        finally:
            os.environ.pop("EMPTY_PRI_008", None)
            os.environ.pop("EMPTY_FB_008", None)


# ──────────────────────────────────────────────────────────────────
# Tests for _warn_unresolved_vars  (TF-005 / TF-006)
# ──────────────────────────────────────────────────────────────────


class TestWarnUnresolvedVars:
    """Tests for the _warn_unresolved_vars static method."""

    def test_warns_on_simple_unresolved(self, caplog):
        """A flat dict with an unresolved ${VAR} should produce a warning."""
        import logging

        with caplog.at_level(logging.WARNING):
            ConfigManager._warn_unresolved_vars(
                {"workspace": {"capacity_id": "${NOT_SET_VAR}"}},
                context="[test.yaml]",
            )
        assert any("NOT_SET_VAR" in r.message for r in caplog.records)

    def test_warns_on_fallback_unresolved(self, caplog):
        """Unresolved fallback syntax ${A:-B} should also trigger a warning."""
        import logging

        with caplog.at_level(logging.WARNING):
            ConfigManager._warn_unresolved_vars(
                {"stages": {"test": {"capacity_id": "${A:-B}"}}},
            )
        assert any("A:-B" in r.message for r in caplog.records)

    def test_no_warning_when_all_resolved(self, caplog):
        """Fully resolved config (no ${...} patterns) → zero warnings."""
        import logging

        with caplog.at_level(logging.WARNING):
            ConfigManager._warn_unresolved_vars(
                {
                    "workspace": {"name": "ws", "capacity_id": "some-guid"},
                    "folders": ["Bronze"],
                },
            )
        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_records) == 0

    def test_warns_on_nested_list_item(self, caplog):
        """Unresolved vars inside list elements should be detected."""
        import logging

        with caplog.at_level(logging.WARNING):
            ConfigManager._warn_unresolved_vars(
                {"resources": [{"name": "ok"}, {"name": "${MISSING_RES}"}]},
            )
        assert any("MISSING_RES" in r.message for r in caplog.records)

    def test_context_appears_in_warning(self, caplog):
        """The context label should appear in the warning message."""
        import logging

        with caplog.at_level(logging.WARNING):
            ConfigManager._warn_unresolved_vars(
                {"key": "${UNSET}"},
                context="[myfile.yaml]",
            )
        assert any("[myfile.yaml]" in r.message for r in caplog.records)


# ──────────────────────────────────────────────────────────────────
# Integration: fallback chain through full config load
# ──────────────────────────────────────────────────────────────────


def test_full_config_load_with_fallback_capacity():
    """End-to-end: a project YAML with fallback capacity resolves correctly
    through ConfigManager.load_config()."""
    import os

    os.environ.pop("E2E_CAP_PROD_009", None)
    os.environ["E2E_CAP_SHARED_009"] = "shared-guid"

    config_data = {
        "workspace": {
            "name": "e2e-test-ws",
            "capacity_id": "${E2E_CAP_PROD_009:-E2E_CAP_SHARED_009}",
        },
    }

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config_manager = ConfigManager(config_path, validate_env=False)
            workspace_config = config_manager.load_config()
            assert workspace_config.capacity_id == "shared-guid"
        finally:
            Path(config_path).unlink()
    finally:
        os.environ.pop("E2E_CAP_SHARED_009", None)


def test_full_config_load_primary_wins_over_fallback():
    """End-to-end: when the primary capacity var IS set, it takes precedence."""
    import os

    os.environ["E2E_CAP_PRI_010"] = "primary-guid"
    os.environ["E2E_CAP_FB_010"] = "fallback-guid"

    config_data = {
        "workspace": {
            "name": "e2e-primary-ws",
            "capacity_id": "${E2E_CAP_PRI_010:-E2E_CAP_FB_010}",
        },
    }

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config_manager = ConfigManager(config_path, validate_env=False)
            workspace_config = config_manager.load_config()
            assert workspace_config.capacity_id == "primary-guid"
        finally:
            Path(config_path).unlink()
    finally:
        os.environ.pop("E2E_CAP_PRI_010", None)
        os.environ.pop("E2E_CAP_FB_010", None)


if __name__ == "__main__":
    pytest.main([__file__])
