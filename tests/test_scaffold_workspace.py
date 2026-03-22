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
    _infer_pipeline_name,
    _replace_stage_marker,
    _strip_any_stage_marker,
    _strip_dev_marker,
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
        rules, _suggested = _build_folder_rules(sample_items, folders=sample_folders)
        rules_dict = {r["type"]: r["folder"] for r in rules}

        assert rules_dict["DataPipeline"] == "Pipelines"
        assert rules_dict["Notebook"] == "Notebooks"
        assert rules_dict["Lakehouse"] == "Data"
        assert rules_dict["Report"] == "Reports"

    def test_without_folders_uses_hardcoded_fallback(self, items_without_folders):
        """When folders=None, should fall back to ITEM_TYPE_TO_FOLDER mapping."""
        rules, _suggested = _build_folder_rules(items_without_folders, folders=None)
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
        rules, _suggested = _build_folder_rules(items, folders=sample_folders)
        rules_dict = {r["type"]: r["folder"] for r in rules}

        # 2 in Notebooks vs 1 in Pipelines → Notebooks wins
        assert rules_dict["Notebook"] == "Notebooks"

    def test_mixed_items_some_with_folders_some_without(self, sample_folders):
        """Items with folderId use actual names; items without use hardcoded."""
        items = [
            {"type": "DataPipeline", "displayName": "p1", "folderId": "folder-001"},
            {"type": "Lakehouse", "displayName": "lh1"},  # No folderId
        ]
        rules, _suggested = _build_folder_rules(items, folders=sample_folders)
        rules_dict = {r["type"]: r["folder"] for r in rules}

        assert rules_dict["DataPipeline"] == "Pipelines"  # From actual placement
        assert rules_dict["Lakehouse"] == "200 Store"  # From hardcoded fallback

    def test_empty_items_returns_empty_rules(self):
        """No items → no rules."""
        rules, _suggested = _build_folder_rules([], folders=None)
        assert rules == []

    def test_empty_items_with_folders_returns_empty_rules(self, sample_folders):
        """No items even with folders → no rules."""
        rules, _suggested = _build_folder_rules([], folders=sample_folders)
        assert rules == []

    def test_items_with_empty_type_are_skipped(self):
        """Items with empty or missing type should not generate rules."""
        items = [
            {"type": "", "displayName": "no_type"},
            {"displayName": "missing_type_key"},
        ]
        rules, _suggested = _build_folder_rules(items, folders=None)
        assert rules == []

    def test_unknown_item_type_without_folder_excluded(self):
        """Item types not in ITEM_TYPE_TO_FOLDER and without folder → no rule."""
        items = [
            {"type": "CustomWidgetThing", "displayName": "w1"},
        ]
        rules, _suggested = _build_folder_rules(items, folders=None)
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
        rules, _suggested = _build_folder_rules(items, folders=sample_folders)
        rules_dict = {r["type"]: r["folder"] for r in rules}

        assert rules_dict["CustomWidgetThing"] == "Reports"

    def test_rules_are_sorted_by_type(self, items_without_folders):
        """Rules should be sorted alphabetically by item type."""
        rules, _suggested = _build_folder_rules(items_without_folders)
        types = [r["type"] for r in rules]
        assert types == sorted(types)

    def test_suggested_rules_for_undiscovered_types(self):
        """Workspace with only Lakehouse/SQLEndpoint gets suggested rules for common types."""
        items = [
            {"type": "Lakehouse", "displayName": "lh1"},
            {"type": "SQLEndpoint", "displayName": "lh1"},
        ]
        rules, suggested = _build_folder_rules(items, folders=None)
        active_types = {r["type"] for r in rules}
        suggested_types = {r["type"] for r in suggested}

        # Lakehouse and SQLEndpoint are active, not suggested
        assert "Lakehouse" in active_types
        assert "SQLEndpoint" in active_types
        assert "Lakehouse" not in suggested_types
        assert "SQLEndpoint" not in suggested_types

        # Common undiscovered types should be suggested
        assert "SemanticModel" in suggested_types
        assert "Report" in suggested_types
        assert "Notebook" in suggested_types

    def test_suggested_rules_empty_when_all_common_types_present(
        self, items_without_folders
    ):
        """When workspace has all common types, no suggestions are needed."""
        _rules, suggested = _build_folder_rules(items_without_folders)
        suggested_types = {r["type"] for r in suggested}
        # items_without_folders includes DataPipeline, Notebook, Lakehouse,
        # Report, SemanticModel — most common types are covered
        assert "SemanticModel" not in suggested_types
        assert "Notebook" not in suggested_types
        assert "Report" not in suggested_types

    def test_empty_items_still_returns_suggested(self):
        """Even with no items, common types are suggested."""
        rules, suggested = _build_folder_rules([], folders=None)
        assert rules == []
        assert len(suggested) > 0
        suggested_types = {r["type"] for r in suggested}
        assert "SemanticModel" in suggested_types


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
        rules, _suggested = _build_folder_rules(items, folders=folders)
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
        rules, _suggested = _build_folder_rules(items, folders=folders)
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

    def test_non_templatise_has_governance_principals(self):
        """Non-templatised output should have all 3 governance principals."""
        yaml = self._gen()
        assert "${AZURE_CLIENT_ID}" in yaml
        assert "${ADDITIONAL_ADMIN_PRINCIPAL_ID}" in yaml
        assert "${ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID}" in yaml

    def test_non_templatise_has_active_project_principals(self):
        """Non-templatised output should have active project-specific principals."""
        yaml = self._gen()
        assert "${SALES_ANALYTICS_ADMIN_ID}" in yaml
        assert "${SALES_ANALYTICS_MEMBERS_ID}" in yaml
        # Should NOT be commented out
        for line in yaml.splitlines():
            if "SALES_ANALYTICS_ADMIN_ID" in line and "- id:" in line:
                assert not line.strip().startswith("#")

    def test_non_templatise_no_hardcoded_uuids(self):
        """Non-templatised output should NOT contain hardcoded principal UUIDs."""
        principals = [
            {
                "id": "aaaa-bbbb-cccc-dddd",
                "type": "Group",
                "role": "Admin",
                "description": "Data Team Admins",
            },
        ]
        yaml = self._gen(discovered_principals=principals)
        # UUID should only appear in comments, not as active principals
        for line in yaml.splitlines():
            if "aaaa-bbbb-cccc-dddd" in line:
                assert line.strip().startswith(
                    "#"
                ), "Discovered principal UUID should be a comment, not active"

    def test_non_templatise_discovered_principals_as_comments(self):
        """Discovered principals should appear as reference comments."""
        principals = [
            {
                "id": "f21d0f2e-f041-4ccc-8a13-c05abfaa886c",
                "type": "Group",
                "role": "Admin",
                "description": "IT Admins",
            },
        ]
        yaml = self._gen(discovered_principals=principals)
        assert "Discovered principals from source workspace" in yaml
        assert "IT Admins" in yaml

    def test_non_templatise_no_todo_comment(self):
        """Non-templatised output should NOT have TODO comments for principals."""
        yaml = self._gen()
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
        """Templatised principals should use CHANGEME prefix."""
        yaml = _generate_feature_yaml(
            workspace_name="HR Analytics [DEV]",
            folders=self.FOLDERS,
            templatise=True,
        )
        assert "${CHANGEME_ADMIN_ID}" in yaml
        assert "${CHANGEME_MEMBERS_ID}" in yaml
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

    def test_display_style_name_uses_base_name(self):
        """Display-style names (with spaces) should use the base display name
        instead of ${PROJECT_PREFIX} so feature workspaces get readable names
        like [F] Sales Audience [FEATURE-my-branch]."""
        yaml = _generate_feature_yaml(
            workspace_name="SC30GLD-DM30 - Opco Data Mart [DEV]",
            folders=["30_lakehouses"],
        )
        assert '  name: "SC30GLD-DM30 - Opco Data Mart"' in yaml
        assert '  display_name: "SC30GLD-DM30 - Opco Data Mart"' in yaml
        assert "${PROJECT_PREFIX}" not in yaml

    def test_slug_style_name_uses_project_prefix(self):
        """Slug-style names (no spaces) should still use ${PROJECT_PREFIX}."""
        yaml = _generate_feature_yaml(
            workspace_name="edp-test-v17 [DEV]",
            folders=["200 Store"],
        )
        assert "  name: ${PROJECT_PREFIX}" in yaml
        assert "  display_name: ${PROJECT_PREFIX}" in yaml

    def test_templatise_always_uses_project_prefix(self):
        """Templates always use ${PROJECT_PREFIX} regardless of name style."""
        yaml = _generate_feature_yaml(
            workspace_name="SC30GLD-DM30 - Opco Data Mart [DEV]",
            folders=["30_lakehouses"],
            templatise=True,
        )
        assert "  name: ${PROJECT_PREFIX}" in yaml


# ── _strip_dev_marker tests ─────────────────────────────────────────────


class TestStripDevMarker:
    """Tests for _strip_dev_marker — removes stage indicators from workspace names."""

    def test_bracket_dev(self):
        assert _strip_dev_marker("EDP [DEV]") == "EDP"

    def test_bracket_dev_case_insensitive(self):
        assert _strip_dev_marker("Sales Audience [dev]") == "Sales Audience"

    def test_parenthesised_dev(self):
        assert _strip_dev_marker("HR Analytics (Dev)") == "HR Analytics"

    def test_suffix_development(self):
        assert _strip_dev_marker("MyProject Development") == "MyProject"

    def test_suffix_dev(self):
        assert _strip_dev_marker("MyProject Dev") == "MyProject"

    def test_bracket_test_passthrough(self):
        # _strip_dev_marker only strips DEV markers; TEST/PROD pass through
        assert _strip_dev_marker("EDP [TEST]") == "EDP [TEST]"

    def test_bracket_prod_passthrough(self):
        assert _strip_dev_marker("EDP [PROD]") == "EDP [PROD]"

    def test_no_marker_passthrough(self):
        assert _strip_dev_marker("MyWorkspace") == "MyWorkspace"

    def test_whitespace_trimmed(self):
        assert _strip_dev_marker("  EDP [DEV]  ") == "EDP"

    def test_complex_name(self):
        assert (
            _strip_dev_marker("SC30GLD-DM30 - Opco Data Mart [DEV]")
            == "SC30GLD-DM30 - Opco Data Mart"
        )

    def test_re_active_directory(self):
        assert _strip_dev_marker("RE Active Directory [DEV]") == "RE Active Directory"


# ── _infer_pipeline_name tests ───────────────────────────────────────────


class TestInferPipelineName:
    """Tests for _infer_pipeline_name — derives pipeline name from workspace name."""

    def test_standard_dev_workspace(self):
        assert _infer_pipeline_name("EDP [DEV]") == "EDP - Pipeline"

    def test_complex_workspace_name(self):
        assert (
            _infer_pipeline_name("Sales Audience [DEV]") == "Sales Audience - Pipeline"
        )

    def test_no_dev_marker(self):
        assert _infer_pipeline_name("MyWorkspace") == "MyWorkspace - Pipeline"

    def test_development_suffix(self):
        assert _infer_pipeline_name("HR Development") == "HR - Pipeline"

    def test_hyphenated_workspace(self):
        assert (
            _infer_pipeline_name("SC30GLD-DM30 - Opco Data Mart [DEV]")
            == "SC30GLD-DM30 - Opco Data Mart - Pipeline"
        )


# ── Capacity ID fallback tests ───────────────────────────────────────────


class TestCapacityIdFallback:
    """Tests for non-templatised capacity ID fallback syntax in _generate_yaml."""

    def test_non_templatise_test_capacity_has_fallback(self):
        """Non-templatised YAML should use env-var fallback for test capacity."""
        yaml = _generate_yaml(
            workspace_name="Test WS [DEV]",
            folders=["Data"],
            folder_rules=[],
            items_by_type={},
            pipeline_name="Test WS - Pipeline",
        )
        assert "${FABRIC_CAPACITY_ID_TEST:-FABRIC_CAPACITY_ID}" in yaml

    def test_non_templatise_prod_capacity_has_fallback(self):
        """Non-templatised YAML should use env-var fallback for prod capacity."""
        yaml = _generate_yaml(
            workspace_name="Test WS [DEV]",
            folders=["Data"],
            folder_rules=[],
            items_by_type={},
            pipeline_name="Test WS - Pipeline",
        )
        assert "${FABRIC_CAPACITY_ID_PROD:-FABRIC_CAPACITY_ID}" in yaml

    def test_templatise_test_capacity_has_fallback(self):
        """Templatised YAML should also use env-var fallback for test capacity."""
        yaml = _generate_yaml(
            workspace_name="Test WS [DEV]",
            folders=["Data"],
            folder_rules=[],
            items_by_type={},
            pipeline_name="Test WS - Pipeline",
            templatise=True,
        )
        assert "${FABRIC_CAPACITY_ID_TEST:-FABRIC_CAPACITY_ID}" in yaml
        # Templatised mode uses CHANGEME placeholders, not project-specific vars
        assert "${CHANGEME_MEMBERS_ID}" in yaml
        assert "CHANGE-ME" in yaml

    def test_non_templatise_principals_are_active(self):
        """Non-templatised feature yaml should have active project principals."""
        yaml = _generate_feature_yaml(
            workspace_name="HR Analytics [DEV]",
            folders=["Bronze", "Silver", "Gold"],
        )
        # Project principals should be active (not commented out)
        for line in yaml.splitlines():
            if "HR_ANALYTICS_ADMIN_ID" in line:
                assert not line.strip().startswith(
                    "#"
                ), "Project principal should be active, not a comment"

    def test_templatise_with_explicit_slug(self):
        """Custom project_slug should still use CHANGE-ME placeholders."""
        yaml = _generate_feature_yaml(
            workspace_name="HR Analytics [DEV]",
            folders=["Bronze", "Silver", "Gold"],
            project_slug="hr_custom",
            templatise=True,
        )
        assert "git_directory: /CHANGE-ME" in yaml
        assert "${CHANGEME_ADMIN_ID}" in yaml


# ── Brownfield tests ──────────────────────────────────────────────────


class TestBrownfieldScaffold:
    """Tests for --brownfield flag: discovered principals emitted as active entries."""

    DISCOVERED = [
        {
            "id": "aaa-111",
            "type": "Group",
            "role": "Admin",
            "description": "IT Admin Group",
        },
        {"id": "bbb-222", "type": "User", "role": "Admin", "description": "Jane Doe"},
        {
            "id": "ccc-333",
            "type": "ServicePrincipal",
            "role": "Admin",
            "description": "Data Pipeline SP",
        },
    ]

    def test_base_yaml_brownfield_emits_active_principals(self):
        """Brownfield base_workspace.yaml should have discovered principals as active entries."""
        yaml = _generate_yaml(
            workspace_name="SC30GLD [DEV]",
            folders=["Data"],
            folder_rules=[],
            items_by_type={},
            discovered_principals=self.DISCOVERED,
            brownfield=True,
        )
        # Active entries (not comments)
        assert '  - id: "aaa-111"' in yaml
        assert '  - id: "bbb-222"' in yaml
        assert '  - id: "ccc-333"' in yaml
        assert "IT Admin Group" in yaml
        # Should NOT have placeholder env vars
        assert "SC30GLD_ADMIN_ID" not in yaml
        assert "SC30GLD_MEMBERS_ID" not in yaml

    def test_base_yaml_brownfield_still_has_mandatory_governance(self):
        """Brownfield should still include mandatory governance env-var principals."""
        yaml = _generate_yaml(
            workspace_name="SC30GLD [DEV]",
            folders=["Data"],
            folder_rules=[],
            items_by_type={},
            discovered_principals=self.DISCOVERED,
            brownfield=True,
        )
        assert "${AZURE_CLIENT_ID}" in yaml
        assert "${ADDITIONAL_ADMIN_PRINCIPAL_ID}" in yaml
        assert "${ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID}" in yaml

    def test_feature_yaml_brownfield_emits_active_principals(self):
        """Brownfield feature_workspace.yaml should have discovered principals."""
        yaml = _generate_feature_yaml(
            workspace_name="SC30GLD [DEV]",
            folders=["Data"],
            brownfield=True,
            discovered_principals=self.DISCOVERED,
        )
        assert '  - id: "aaa-111"' in yaml
        assert '  - id: "bbb-222"' in yaml
        assert "SC30GLD_ADMIN_ID" not in yaml

    def test_greenfield_default_uses_placeholder_env_vars(self):
        """Without --brownfield, discovered principals stay as comments."""
        yaml = _generate_yaml(
            workspace_name="SC30GLD [DEV]",
            folders=["Data"],
            folder_rules=[],
            items_by_type={},
            discovered_principals=self.DISCOVERED,
            brownfield=False,
        )
        assert "${SC30GLD_ADMIN_ID}" in yaml
        assert "#   aaa-111" in yaml.replace("...", "")  # commented

    def test_brownfield_without_discovered_falls_back_to_greenfield(self):
        """Brownfield with no discovered principals should use placeholder env vars."""
        yaml = _generate_yaml(
            workspace_name="SC30GLD [DEV]",
            folders=["Data"],
            folder_rules=[],
            items_by_type={},
            discovered_principals=None,
            brownfield=True,
        )
        # Falls through to greenfield path since no discovered principals
        assert "${SC30GLD_ADMIN_ID}" in yaml


# ── As-Stage Tests ──────────────────────────────────────────────────────────


class TestStripAnyStageMarker:
    """Tests for _strip_any_stage_marker -- removes DEV, TEST, or PROD markers."""

    def test_strip_dev_bracket(self):
        assert _strip_any_stage_marker("EDP [DEV]") == "EDP"

    def test_strip_test_bracket(self):
        assert _strip_any_stage_marker("EDP [TEST]") == "EDP"

    def test_strip_prod_bracket(self):
        assert _strip_any_stage_marker("Finance [PROD]") == "Finance"

    def test_strip_production_bracket(self):
        assert _strip_any_stage_marker("Finance [PRODUCTION]") == "Finance"

    def test_strip_testing_bracket(self):
        assert _strip_any_stage_marker("Sales [TESTING]") == "Sales"

    def test_no_marker_passthrough(self):
        assert _strip_any_stage_marker("MyWorkspace") == "MyWorkspace"

    def test_case_insensitive(self):
        assert _strip_any_stage_marker("HR [prod]") == "HR"


class TestReplaceStageMarker:
    """Tests for _replace_stage_marker -- swaps stage markers."""

    def test_prod_to_dev(self):
        assert _replace_stage_marker("Finance [PROD]", "DEV") == "Finance [DEV]"

    def test_prod_to_test(self):
        assert _replace_stage_marker("Finance [PROD]", "TEST") == "Finance [TEST]"

    def test_test_to_dev(self):
        assert _replace_stage_marker("Sales [TEST]", "DEV") == "Sales [DEV]"

    def test_dev_to_prod(self):
        assert _replace_stage_marker("EDP [DEV]", "PROD") == "EDP [PROD]"

    def test_no_marker_appends(self):
        assert _replace_stage_marker("MyWorkspace", "DEV") == "MyWorkspace [DEV]"

    def test_production_to_dev(self):
        assert _replace_stage_marker("HR Production", "DEV") == "HR [DEV]"


class TestAsStageGeneration:
    """Tests for --as-stage parameter in _generate_yaml."""

    def test_as_stage_production_sets_prod_to_scanned_name(self):
        yaml = _generate_yaml(
            workspace_name="Finance [PROD]",
            folders=["Data"],
            items_by_type={},
            folder_rules=[],
            pipeline_name="Finance - Pipeline",
            as_stage="production",
        )
        # workspace.name should be the dev name
        assert 'name: "Finance [DEV]"' in yaml
        # prod stage should be the original scanned name
        assert 'workspace_name: "Finance [PROD]"' in yaml
        # dev stage should be the inferred dev name
        lines = yaml.split("\n")
        dev_stage_idx = next(
            i for i, l in enumerate(lines) if "development:" in l
        )
        assert 'Finance [DEV]' in lines[dev_stage_idx + 1]
        # test stage should be inferred
        assert 'workspace_name: "Finance [TEST]"' in yaml

    def test_as_stage_test_sets_test_to_scanned_name(self):
        yaml = _generate_yaml(
            workspace_name="Sales [TEST]",
            folders=["Data"],
            items_by_type={},
            folder_rules=[],
            pipeline_name="Sales - Pipeline",
            as_stage="test",
        )
        assert 'name: "Sales [DEV]"' in yaml
        assert 'workspace_name: "Sales [TEST]"' in yaml
        assert 'workspace_name: "Sales [PROD]"' in yaml

    def test_as_stage_development_is_default_behavior(self):
        yaml_default = _generate_yaml(
            workspace_name="EDP [DEV]",
            folders=["Data"],
            items_by_type={},
            folder_rules=[],
            pipeline_name="EDP - Pipeline",
        )
        yaml_explicit = _generate_yaml(
            workspace_name="EDP [DEV]",
            folders=["Data"],
            items_by_type={},
            folder_rules=[],
            pipeline_name="EDP - Pipeline",
            as_stage="development",
        )
        # Both should produce identical pipeline stage assignments
        assert 'workspace_name: "EDP [DEV]"' in yaml_default
        assert 'workspace_name: "EDP [DEV]"' in yaml_explicit

    def test_as_stage_production_no_marker_in_name(self):
        """Workspace name without stage marker -- appends [DEV] for dev."""
        yaml = _generate_yaml(
            workspace_name="Finance Reporting",
            folders=["Data"],
            items_by_type={},
            folder_rules=[],
            pipeline_name="Finance Reporting - Pipeline",
            as_stage="production",
        )
        # Dev should get [DEV] appended
        assert 'name: "Finance Reporting [DEV]"' in yaml
        # Prod should keep the original name
        assert 'workspace_name: "Finance Reporting"' in yaml

    def test_as_stage_with_templatise_uses_changeme(self):
        """With templatise=True, as_stage doesn't affect placeholder output."""
        yaml = _generate_yaml(
            workspace_name="Finance [PROD]",
            folders=["Data"],
            items_by_type={},
            folder_rules=[],
            pipeline_name="Finance - Pipeline",
            as_stage="production",
            templatise=True,
        )
        # Templatise always uses CHANGE-ME regardless of as_stage
        assert 'name: "CHANGE-ME [DEV]"' in yaml
        assert 'workspace_name: "CHANGE-ME [PROD]"' in yaml

    def test_as_stage_production_with_explicit_test_override(self):
        """Explicit test_workspace_name takes precedence over inference."""
        yaml = _generate_yaml(
            workspace_name="Finance [PROD]",
            folders=["Data"],
            items_by_type={},
            folder_rules=[],
            pipeline_name="Finance - Pipeline",
            as_stage="production",
            test_workspace_name="Custom Test WS",
        )
        assert 'workspace_name: "Custom Test WS"' in yaml
        assert 'workspace_name: "Finance [PROD]"' in yaml

    def test_as_stage_adds_comment_about_existing_workspace(self):
        yaml = _generate_yaml(
            workspace_name="Finance [PROD]",
            folders=["Data"],
            items_by_type={},
            folder_rules=[],
            pipeline_name="Finance - Pipeline",
            as_stage="production",
        )
        assert "mapped as production stage" in yaml
