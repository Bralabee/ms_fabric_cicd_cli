"""
Tests for scaffold_workspace.py — workspace scaffolding and config generation.

Covers:
- _build_folder_rules: actual folder placement, hardcoded fallback, majority vote
- _categorize_items: grouping items by type
- ITEM_TYPE_TO_FOLDER: constant completeness checks
- _generate_yaml / _generate_feature_yaml: templatise=True placeholder generation
- Import smoke tests for top-level functions
"""

import pytest

from usf_fabric_cli.scripts.admin.utilities.scaffold_workspace import (
    DEFAULT_FOLDERS,
    ITEM_TYPE_TO_FOLDER,
    _build_folder_paths,
    _build_folder_rules,
    _categorize_items,
    _generate_feature_yaml,
    _generate_yaml,
)

# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def sample_folders():
    """Workspace folders returned by the Fabric REST API."""
    return [
        {"id": "folder-001", "displayName": "Pipelines"},
        {"id": "folder-002", "displayName": "Notebooks"},
        {"id": "folder-003", "displayName": "Data"},
        {"id": "folder-004", "displayName": "Reports"},
    ]


@pytest.fixture
def sample_items():
    """Workspace items with folderId placement."""
    return [
        {"type": "DataPipeline", "displayName": "ingest_raw", "folderId": "folder-001"},
        {"type": "DataPipeline", "displayName": "ingest_api", "folderId": "folder-001"},
        {"type": "Notebook", "displayName": "transform", "folderId": "folder-002"},
        {"type": "Lakehouse", "displayName": "raw_lake", "folderId": "folder-003"},
        {"type": "Report", "displayName": "dashboard", "folderId": "folder-004"},
    ]


@pytest.fixture
def items_without_folders():
    """Workspace items with no folderId — triggers hardcoded fallback."""
    return [
        {"type": "DataPipeline", "displayName": "pipeline1"},
        {"type": "Notebook", "displayName": "nb1"},
        {"type": "Lakehouse", "displayName": "lh1"},
        {"type": "Report", "displayName": "rpt1"},
        {"type": "SemanticModel", "displayName": "sm1"},
    ]


# ── _build_folder_rules tests ─────────────────────────────────────────────


class TestBuildFolderRules:
    """Tests for _build_folder_rules with and without folder data."""

    def test_with_folders_uses_actual_placement(self, sample_items, sample_folders):
        """Items with folderId should map to their actual folder names."""
        rules = _build_folder_rules(sample_items, folders=sample_folders)
        rules_dict = {r["type"]: r["folder"] for r in rules}

        assert rules_dict["DataPipeline"] == "Pipelines"
        assert rules_dict["Notebook"] == "Notebooks"
        assert rules_dict["Lakehouse"] == "Data"
        assert rules_dict["Report"] == "Reports"

    def test_without_folders_uses_hardcoded_fallback(self, items_without_folders):
        """When folders=None, should fall back to ITEM_TYPE_TO_FOLDER mapping."""
        rules = _build_folder_rules(items_without_folders, folders=None)
        rules_dict = {r["type"]: r["folder"] for r in rules}

        assert rules_dict["DataPipeline"] == "000 Orchestrate"
        assert rules_dict["Notebook"] == "300 Prepare"
        assert rules_dict["Lakehouse"] == "200 Store"
        assert rules_dict["Report"] == "500 Visualize"
        assert rules_dict["SemanticModel"] == "400 Model"

    def test_majority_vote_picks_most_common_folder(self, sample_folders):
        """When items of the same type span multiple folders, majority wins."""
        items = [
            {"type": "Notebook", "displayName": "nb1", "folderId": "folder-002"},
            {"type": "Notebook", "displayName": "nb2", "folderId": "folder-002"},
            {"type": "Notebook", "displayName": "nb3", "folderId": "folder-001"},
        ]
        rules = _build_folder_rules(items, folders=sample_folders)
        rules_dict = {r["type"]: r["folder"] for r in rules}

        # 2 in Notebooks vs 1 in Pipelines → Notebooks wins
        assert rules_dict["Notebook"] == "Notebooks"

    def test_mixed_items_some_with_folders_some_without(self, sample_folders):
        """Items with folderId use actual names; items without use hardcoded."""
        items = [
            {"type": "DataPipeline", "displayName": "p1", "folderId": "folder-001"},
            {"type": "Lakehouse", "displayName": "lh1"},  # No folderId
        ]
        rules = _build_folder_rules(items, folders=sample_folders)
        rules_dict = {r["type"]: r["folder"] for r in rules}

        assert rules_dict["DataPipeline"] == "Pipelines"  # From actual placement
        assert rules_dict["Lakehouse"] == "200 Store"  # From hardcoded fallback

    def test_empty_items_returns_empty_rules(self):
        """No items → no rules."""
        rules = _build_folder_rules([], folders=None)
        assert rules == []

    def test_empty_items_with_folders_returns_empty_rules(self, sample_folders):
        """No items even with folders → no rules."""
        rules = _build_folder_rules([], folders=sample_folders)
        assert rules == []

    def test_items_with_empty_type_are_skipped(self):
        """Items with empty or missing type should not generate rules."""
        items = [
            {"type": "", "displayName": "no_type"},
            {"displayName": "missing_type_key"},
        ]
        rules = _build_folder_rules(items, folders=None)
        assert rules == []

    def test_unknown_item_type_without_folder_excluded(self):
        """Item types not in ITEM_TYPE_TO_FOLDER and without folder → no rule."""
        items = [
            {"type": "CustomWidgetThing", "displayName": "w1"},
        ]
        rules = _build_folder_rules(items, folders=None)
        assert rules == []

    def test_unknown_item_type_with_folder_included(self, sample_folders):
        """Unknown item types get a rule if they have an actual folder."""
        items = [
            {
                "type": "CustomWidgetThing",
                "displayName": "w1",
                "folderId": "folder-004",
            },
        ]
        rules = _build_folder_rules(items, folders=sample_folders)
        rules_dict = {r["type"]: r["folder"] for r in rules}

        assert rules_dict["CustomWidgetThing"] == "Reports"

    def test_rules_are_sorted_by_type(self, items_without_folders):
        """Rules should be sorted alphabetically by item type."""
        rules = _build_folder_rules(items_without_folders)
        types = [r["type"] for r in rules]
        assert types == sorted(types)


# ── _categorize_items tests ────────────────────────────────────────────────


class TestCategorizeItems:
    """Tests for _categorize_items grouping."""

    def test_groups_by_type(self):
        """Items should be grouped into lists keyed by type."""
        items = [
            {"type": "Notebook", "displayName": "nb1"},
            {"type": "Notebook", "displayName": "nb2"},
            {"type": "Lakehouse", "displayName": "lh1"},
        ]
        result = _categorize_items(items)

        assert len(result["Notebook"]) == 2
        assert len(result["Lakehouse"]) == 1

    def test_missing_type_defaults_to_unknown(self):
        """Items without a 'type' key are grouped under 'Unknown'."""
        items = [{"displayName": "mystery_item"}]
        result = _categorize_items(items)

        assert "Unknown" in result
        assert len(result["Unknown"]) == 1

    def test_empty_items_returns_empty_dict(self):
        """No items → empty dict."""
        result = _categorize_items([])
        assert result == {}


# ── Constants validation ──────────────────────────────────────────────────


class TestConstants:
    """Validate the hardcoded constants are complete and consistent."""

    def test_item_type_to_folder_uses_default_folders(self):
        """All folder names in ITEM_TYPE_TO_FOLDER should exist in DEFAULT_FOLDERS."""
        for item_type, folder in ITEM_TYPE_TO_FOLDER.items():
            assert folder in DEFAULT_FOLDERS, (
                f"ITEM_TYPE_TO_FOLDER['{item_type}'] = '{folder}' "
                f"is not in DEFAULT_FOLDERS"
            )

    def test_default_folders_not_empty(self):
        """DEFAULT_FOLDERS should contain at least the medallion structure."""
        assert len(DEFAULT_FOLDERS) >= 7

    def test_common_fabric_types_covered(self):
        """Key Fabric item types should have a folder mapping."""
        expected_types = [
            "DataPipeline",
            "Notebook",
            "Lakehouse",
            "Report",
            "SemanticModel",
            "Warehouse",
        ]
        for t in expected_types:
            assert t in ITEM_TYPE_TO_FOLDER, f"Missing mapping for {t}"


# ── Import smoke tests ────────────────────────────────────────────────────


class TestImportSmoke:
    """Verify top-level functions are importable."""

    def test_scaffold_workspace_importable(self):
        """scaffold_workspace function should be importable."""
        from usf_fabric_cli.scripts.admin.utilities.scaffold_workspace import (
            scaffold_workspace,
        )

        assert callable(scaffold_workspace)

    def test_build_folder_rules_signature(self):
        """_build_folder_rules should accept items and optional folders."""
        import inspect

        sig = inspect.signature(_build_folder_rules)
        params = list(sig.parameters.keys())
        assert "items" in params
        assert "folders" in params
        assert sig.parameters["folders"].default is None


# ── _build_folder_paths tests ────────────────────────────────────────────


class TestBuildFolderPaths:
    """Tests for _build_folder_paths — nested folder path reconstruction."""

    def test_flat_folders_unchanged(self):
        """Root-only folders produce their displayName as-is."""
        raw = [
            {"id": "a", "displayName": "000 Orchestrate"},
            {"id": "b", "displayName": "200 Store"},
        ]
        paths = _build_folder_paths(raw)
        assert paths == ["000 Orchestrate", "200 Store"]

    def test_nested_parent_child(self):
        """Child folders produce 'Parent/Child' path strings."""
        raw = [
            {"id": "a", "displayName": "200 Store"},
            {"id": "b", "displayName": "Raw", "parentFolderId": "a"},
            {"id": "c", "displayName": "Curated", "parentFolderId": "a"},
        ]
        paths = _build_folder_paths(raw)
        assert "200 Store" in paths
        assert "200 Store/Raw" in paths
        assert "200 Store/Curated" in paths
        # Parents come before children in sorted output
        assert paths.index("200 Store") < paths.index("200 Store/Raw")

    def test_multi_level_hierarchy(self):
        """Three-level deep hierarchy reconstructed correctly."""
        raw = [
            {"id": "a", "displayName": "200 Store"},
            {"id": "b", "displayName": "Raw", "parentFolderId": "a"},
            {"id": "c", "displayName": "Delta", "parentFolderId": "b"},
        ]
        paths = _build_folder_paths(raw)
        assert paths == ["200 Store", "200 Store/Raw", "200 Store/Raw/Delta"]

    def test_no_parent_id_field_treated_as_root(self):
        """Folders without parentFolderId are treated as root-level."""
        raw = [
            {"id": "a", "displayName": "Folder A"},
            {"id": "b", "displayName": "Folder B"},
        ]
        paths = _build_folder_paths(raw)
        assert paths == ["Folder A", "Folder B"]

    def test_empty_input_returns_empty(self):
        """No folders → no paths."""
        assert _build_folder_paths([]) == []

    def test_sorted_by_depth_then_alphabetically(self):
        """Paths sorted: shallowest first, then alphabetical within same depth."""
        raw = [
            {"id": "a", "displayName": "Zebra"},
            {"id": "b", "displayName": "Alpha"},
            {"id": "c", "displayName": "Sub", "parentFolderId": "a"},
            {"id": "d", "displayName": "Sub", "parentFolderId": "b"},
        ]
        paths = _build_folder_paths(raw)
        assert paths == ["Alpha", "Zebra", "Alpha/Sub", "Zebra/Sub"]

    def test_orphan_parent_id_treated_as_root(self):
        """Folder with parentFolderId pointing to unknown ID → treat as root."""
        raw = [
            {"id": "a", "displayName": "200 Store"},
            {"id": "b", "displayName": "Orphan", "parentFolderId": "nonexistent"},
        ]
        paths = _build_folder_paths(raw)
        assert "200 Store" in paths
        assert "Orphan" in paths  # treated as root, not nested


# ── _build_folder_rules with nested folders ──────────────────────────────


class TestBuildFolderRulesNested:
    """Tests for _build_folder_rules when folders have parentFolderId."""

    def test_items_in_nested_folder_get_path_rules(self):
        """Items in a child folder should get path-based folder rules."""
        folders = [
            {"id": "a", "displayName": "200 Store"},
            {"id": "b", "displayName": "Raw", "parentFolderId": "a"},
        ]
        items = [
            {"type": "Lakehouse", "displayName": "lh1", "folderId": "b"},
        ]
        rules = _build_folder_rules(items, folders=folders)
        rules_dict = {r["type"]: r["folder"] for r in rules}
        assert rules_dict["Lakehouse"] == "200 Store/Raw"

    def test_items_in_root_folder_still_flat(self):
        """Items in root folder still get flat names (backward compat)."""
        folders = [
            {"id": "a", "displayName": "200 Store"},
            {"id": "b", "displayName": "Raw", "parentFolderId": "a"},
        ]
        items = [
            {"type": "Lakehouse", "displayName": "lh1", "folderId": "a"},
        ]
        rules = _build_folder_rules(items, folders=folders)
        rules_dict = {r["type"]: r["folder"] for r in rules}
        assert rules_dict["Lakehouse"] == "200 Store"


# ── _generate_yaml templatise tests ──────────────────────────────────────


class TestGenerateYamlTemplatise:
    """Tests for _generate_yaml with templatise=True."""

    FOLDERS = ["000 Orchestrate", "200 Store", "300 Prepare"]
    ITEMS_BY_TYPE = {
        "DataPipeline": [{"displayName": "ingest"}],
        "Lakehouse": [{"displayName": "raw"}],
    }
    FOLDER_RULES = [
        {"type": "DataPipeline", "folder": "000 Orchestrate"},
        {"type": "Lakehouse", "folder": "200 Store"},
    ]

    def _gen(self, **overrides):
        """Helper to call _generate_yaml with sensible defaults."""
        kwargs = dict(
            workspace_name="Sales Analytics [DEV]",
            folders=self.FOLDERS,
            items_by_type=self.ITEMS_BY_TYPE,
            folder_rules=self.FOLDER_RULES,
        )
        kwargs.update(overrides)
        return _generate_yaml(**kwargs)

    def test_templatise_replaces_workspace_name_with_change_me(self):
        """Workspace name/display_name should be CHANGE-ME [DEV]."""
        yaml = self._gen(templatise=True)
        assert 'name: "CHANGE-ME [DEV]"' in yaml
        assert 'display_name: "CHANGE-ME [DEV]"' in yaml
        # Real name should NOT appear in workspace section
        assert 'name: "Sales Analytics [DEV]"' not in yaml

    def test_templatise_replaces_git_directory_with_change_me(self):
        """git_directory should be /CHANGE-ME, not the real slug."""
        yaml = self._gen(templatise=True)
        assert "git_directory: /CHANGE-ME" in yaml
        assert "git_directory: /sales_analytics" not in yaml

    def test_templatise_header_says_template(self):
        """Header comment should say 'Template' and reference scaffolded source."""
        yaml = self._gen(templatise=True)
        assert "(Template)" in yaml
        assert "Scaffolded from: Sales Analytics [DEV]" in yaml

    def test_templatise_principals_use_changeme_prefix(self):
        """Project-specific principals should use CHANGEME_ prefix."""
        yaml = self._gen(templatise=True)
        assert "${CHANGEME_ADMIN_ID}" in yaml
        assert "${CHANGEME_MEMBERS_ID}" in yaml
        # Should NOT contain the real slug-based principal names
        assert "SALES_ANALYTICS_ADMIN_ID" not in yaml

    def test_templatise_discovered_principals_as_comments(self):
        """Discovered principals should appear as reference comments."""
        principals = [
            {
                "id": "aaaa-bbbb-cccc",
                "type": "Group",
                "role": "Admin",
                "description": "Data Team Admins",
            },
        ]
        yaml = self._gen(
            discovered_principals=principals,
            templatise=True,
        )
        # Should appear as a comment, not as a live principal
        assert "Discovered principals from source workspace" in yaml
        assert "Group (Admin): Data Team Admins" in yaml
        # The comment line should start with #
        for line in yaml.splitlines():
            if "Data Team Admins" in line:
                assert line.strip().startswith("#")

    def test_templatise_pipeline_uses_change_me_names(self):
        """Pipeline section should use CHANGE-ME placeholders."""
        yaml = self._gen(
            pipeline_name="Sales Analytics - Pipeline",
            templatise=True,
        )
        assert 'pipeline_name: "CHANGE-ME - Pipeline"' in yaml
        assert 'workspace_name: "CHANGE-ME [DEV]"' in yaml
        assert 'workspace_name: "CHANGE-ME [TEST]"' in yaml
        assert 'workspace_name: "CHANGE-ME [PROD]"' in yaml
        # Real pipeline/stage names should NOT appear in values
        assert 'pipeline_name: "Sales Analytics - Pipeline"' not in yaml

    def test_templatise_pipeline_has_scaffolded_from_comment(self):
        """Pipeline section should include a comment with real names."""
        yaml = self._gen(
            pipeline_name="Sales Analytics - Pipeline",
            templatise=True,
        )
        assert "Scaffolded from pipeline: Sales Analytics - Pipeline" in yaml

    def test_templatise_pipeline_capacity_ids_use_fallback(self):
        """Test and Prod capacity IDs should use fallback syntax."""
        yaml = self._gen(
            pipeline_name="Sales Analytics - Pipeline",
            templatise=True,
        )
        assert "${FABRIC_CAPACITY_ID_TEST:-FABRIC_CAPACITY_ID}" in yaml
        assert "${FABRIC_CAPACITY_ID_PROD:-FABRIC_CAPACITY_ID}" in yaml

    def test_non_templatise_preserves_real_names(self):
        """Default (templatise=False) should use real workspace names."""
        yaml = self._gen(pipeline_name="Sales Analytics - Pipeline")
        assert 'name: "Sales Analytics [DEV]"' in yaml
        assert "git_directory: /sales_analytics" in yaml
        assert 'pipeline_name: "Sales Analytics - Pipeline"' in yaml
        assert "CHANGE-ME" not in yaml

    def test_templatise_no_todo_comment_for_principals(self):
        """templatise=True should NOT emit the TODO comment for principals."""
        yaml = self._gen(templatise=True)
        assert "TODO: Add project-specific principals" not in yaml


# ── _generate_feature_yaml templatise tests ──────────────────────────────


class TestGenerateFeatureYamlTemplatise:
    """Tests for _generate_feature_yaml with templatise=True."""

    FOLDERS = ["000 Orchestrate", "200 Store"]

    def test_templatise_header_says_template(self):
        """Header should say Template and reference the source workspace."""
        yaml = _generate_feature_yaml(
            workspace_name="HR Analytics [DEV]",
            folders=self.FOLDERS,
            templatise=True,
        )
        assert "(Template)" in yaml
        assert "Scaffolded from: HR Analytics [DEV]" in yaml

    def test_templatise_git_directory_is_change_me(self):
        """git_directory should be /CHANGE-ME."""
        yaml = _generate_feature_yaml(
            workspace_name="HR Analytics [DEV]",
            folders=self.FOLDERS,
            templatise=True,
        )
        assert "git_directory: /CHANGE-ME" in yaml
        assert "git_directory: /hr_analytics" not in yaml

    def test_templatise_principal_prefix_is_changeme(self):
        """TODO principal comment should use CHANGEME prefix."""
        yaml = _generate_feature_yaml(
            workspace_name="HR Analytics [DEV]",
            folders=self.FOLDERS,
            templatise=True,
        )
        assert "${CHANGEME_ADMIN_ID}" in yaml
        # Should NOT use the real slug
        assert "HR_ANALYTICS_ADMIN_ID" not in yaml

    def test_non_templatise_uses_real_slug(self):
        """Default should use the real slug-based values."""
        yaml = _generate_feature_yaml(
            workspace_name="HR Analytics [DEV]",
            folders=self.FOLDERS,
        )
        assert "git_directory: /hr_analytics" in yaml
        assert "${HR_ANALYTICS_ADMIN_ID}" in yaml
        assert "CHANGE-ME" not in yaml

    def test_templatise_with_explicit_slug(self):
        """Custom project_slug should still use CHANGE-ME placeholders."""
        yaml = _generate_feature_yaml(
            workspace_name="HR Analytics [DEV]",
            folders=self.FOLDERS,
            project_slug="hr_custom",
            templatise=True,
        )
        assert "git_directory: /CHANGE-ME" in yaml
        assert "${CHANGEME_ADMIN_ID}" in yaml
