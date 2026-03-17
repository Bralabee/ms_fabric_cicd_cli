#!/usr/bin/env python3
"""
Scaffold Workspace Configuration.

Connects to a live Microsoft Fabric workspace, introspects its items,
folders, and structure, then generates a YAML config file compatible
with the usf_fabric_cli_cicd deployer.

This eliminates the need to manually write YAML -- especially useful
for onboarding existing workspaces into CI/CD.

Usage:
    python -m usf_fabric_cli.scripts.admin.utilities.scaffold_workspace \\
        "My Workspace Name"

    # With custom output path:
    python -m usf_fabric_cli.scripts.admin.utilities.scaffold_workspace \\
        "My Workspace Name" \\
        --output config/projects/_templates/myproject/base_workspace.yaml

    # Generate feature workspace template too:
    python -m usf_fabric_cli.scripts.admin.utilities.scaffold_workspace \\
        "My Workspace Name" --include-feature-template

    # Include deployment pipeline stages:
    python -m usf_fabric_cli.scripts.admin.utilities.scaffold_workspace \\
        "My Workspace Name" --pipeline-name "My Pipeline"
"""

import argparse
import json
import logging
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from usf_fabric_cli.services.fabric_git_api import FabricGitAPI
from usf_fabric_cli.services.fabric_wrapper import FabricCLIWrapper
from usf_fabric_cli.utils.config import get_environment_variables

logger = logging.getLogger(__name__)


# -- Fabric item type -> recommended folder mapping --------------------------
# These mirror the standard medallion folder rules used across projects.
ITEM_TYPE_TO_FOLDER: Dict[str, str] = {
    "DataPipeline": "000 Orchestrate",
    "DataflowGen2": "000 Orchestrate",
    "Eventstream": "100 Ingest",
    "MirroredWarehouse": "100 Ingest",
    "MirroredDatabase": "100 Ingest",
    "Lakehouse": "200 Store",
    "SQLEndpoint": "200 Store",
    "Notebook": "300 Prepare",
    "SparkJobDefinition": "300 Prepare",
    "MLModel": "300 Prepare",
    "MLExperiment": "300 Prepare",
    "Warehouse": "400 Model",
    "SemanticModel": "400 Model",
    "KQLDatabase": "400 Model",
    "KQLQueryset": "400 Model",
    "Report": "500 Visualize",
    "Dashboard": "500 Visualize",
    "PaginatedReport": "500 Visualize",
    "Reflex": "000 Orchestrate",
    "Environment": "999 Libraries",
}

# Default folder structure (8-folder medallion)
DEFAULT_FOLDERS = [
    "000 Orchestrate",
    "100 Ingest",
    "200 Store",
    "300 Prepare",
    "400 Model",
    "500 Visualize",
    "999 Libraries",
    "Archive",
]


def _get_workspace_folders(
    fabric: FabricCLIWrapper, workspace_name: str
) -> List[Dict[str, str]]:
    """Retrieve folders from workspace via REST API.

    Returns list of dicts with 'id' and 'displayName'.
    """
    workspace_id = fabric.get_workspace_id(workspace_name)
    if not workspace_id:
        return []

    command = ["api", f"workspaces/{workspace_id}/folders"]
    result = fabric._execute_command(command)

    if not result.get("success"):
        logger.warning(
            "Folder API call failed for workspace '%s' (ID: %s): %s. "
            "Falling back to default folder structure.",
            workspace_name,
            workspace_id,
            result.get("error", "unknown error"),
        )
        return []

    data = result.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return []

    # Handle nested "text" field from fab api wrapper
    if isinstance(data, dict) and "text" in data and isinstance(data["text"], dict):
        data = data["text"]

    if isinstance(data, dict) and "value" in data:
        folders = []
        for f in data["value"]:
            entry: Dict[str, str] = {
                "id": f.get("id", ""),
                "displayName": f.get("displayName", ""),
            }
            if f.get("parentFolderId"):
                entry["parentFolderId"] = f["parentFolderId"]
            folders.append(entry)
        return folders

    return []


def _build_folder_paths(raw_folders: List[Dict[str, str]]) -> List[str]:
    """Convert a flat list of folder dicts into sorted path strings.

    Walks ``parentFolderId`` chains to reconstruct full paths using ``/``
    as separator.  Root folders produce their ``displayName`` as-is.

    Returns paths sorted by depth (shallowest first), then alphabetically.
    """
    id_to_folder: Dict[str, Dict[str, str]] = {
        f["id"]: f for f in raw_folders if f.get("id")
    }
    path_cache: Dict[str, str] = {}

    def _resolve(folder_id: str) -> str:
        if folder_id in path_cache:
            return path_cache[folder_id]
        folder = id_to_folder.get(folder_id)
        if not folder:
            return ""
        parent_id = folder.get("parentFolderId", "")
        if parent_id and parent_id in id_to_folder:
            parent_path = _resolve(parent_id)
            path = f"{parent_path}/{folder['displayName']}"
        else:
            path = folder["displayName"]
        path_cache[folder_id] = path
        return path

    paths = []
    for f in raw_folders:
        fid = f.get("id", "")
        if fid:
            p = _resolve(fid)
            if p:
                paths.append(p)

    # Sort: shallowest first, then alphabetically within same depth
    paths.sort(key=lambda p: (p.count("/"), p))
    return paths


def _build_folder_rules(
    items: List[Dict[str, Any]],
    folders: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, str]]:
    """Infer folder_rules from discovered item types and actual folder placement.

    When folder information is available (from the workspace API), uses each
    item's real ``folderId`` to determine which folder it lives in.  Falls
    back to the hardcoded ``ITEM_TYPE_TO_FOLDER`` mapping only for item types
    whose items have no ``folderId`` or when *folders* is not provided.

    This ensures scaffolded configs accurately reflect non-standard folder
    structures (e.g. workspaces that don't follow the medallion convention).
    """
    # Build folder-ID -> path lookup from discovered folders
    folder_id_to_path: Dict[str, str] = {}
    if folders:
        # Reuse _build_folder_paths logic to get full path per folder ID
        id_to_folder = {f["id"]: f for f in folders if f.get("id")}
        path_cache: Dict[str, str] = {}

        def _resolve_path(folder_id: str) -> str:
            if folder_id in path_cache:
                return path_cache[folder_id]
            folder = id_to_folder.get(folder_id)
            if not folder:
                return ""
            parent_id = folder.get("parentFolderId", "")
            if parent_id and parent_id in id_to_folder:
                parent_path = _resolve_path(parent_id)
                path = f"{parent_path}/{folder['displayName']}"
            else:
                path = folder["displayName"]
            path_cache[folder_id] = path
            return path

        folder_id_to_path = {
            f["id"]: _resolve_path(f["id"])
            for f in folders
            if f.get("id") and _resolve_path(f["id"])
        }

    # Determine the most common folder per item type based on actual placement
    type_to_folder: Dict[str, str] = {}
    if folder_id_to_path:
        # Count how many items of each type live in each folder
        type_folder_counts: Dict[str, Counter] = defaultdict(Counter)
        for item in items:
            item_type = item.get("type", "")
            folder_id = item.get("folderId") or item.get("parentFolderId")
            if item_type and folder_id and folder_id in folder_id_to_path:
                type_folder_counts[item_type][folder_id_to_path[folder_id]] += 1

        # Pick the most common folder for each type (majority vote)
        for item_type, counter in type_folder_counts.items():
            most_common_folder, _ = counter.most_common(1)[0]
            type_to_folder[item_type] = most_common_folder

    # Build final rules -- prefer actual placement, fall back to hardcoded map
    discovered_types = {item.get("type", "") for item in items}
    rules = []
    seen_types: set = set()

    for item_type in sorted(discovered_types):
        if item_type in seen_types or not item_type:
            continue
        folder_name = type_to_folder.get(item_type) or ITEM_TYPE_TO_FOLDER.get(
            item_type
        )
        if folder_name:
            rules.append({"type": item_type, "folder": folder_name})
            seen_types.add(item_type)

    return rules


def _categorize_items(
    items: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Group workspace items by type."""
    by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in items:
        item_type = item.get("type", "Unknown")
        by_type[item_type].append(item)
    return dict(by_type)


def _discover_principals(
    fabric: FabricCLIWrapper, workspace_name: str
) -> List[Dict[str, str]]:
    """Discover existing role assignments from the live workspace.

    Calls ``GET workspaces/{id}/roleAssignments`` and returns a list of
    principal dicts with keys: id, type, role, description.

    Falls back gracefully to an empty list on any failure, so the caller
    can still emit the default placeholder principals.
    """
    workspace_id = fabric.get_workspace_id(workspace_name)
    if not workspace_id:
        return []

    command = ["api", f"workspaces/{workspace_id}/roleAssignments"]
    result = fabric._execute_command(command)

    if not result.get("success"):
        logger.info(
            "Could not retrieve role assignments for '%s' -- "
            "will use placeholder principals instead.",
            workspace_name,
        )
        return []

    data = result.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return []

    # Handle nested "text" field from fab api wrapper
    if isinstance(data, dict) and "text" in data and isinstance(data["text"], dict):
        data = data["text"]

    if not isinstance(data, dict) or "value" not in data:
        return []

    # Map Fabric API role assignment fields to our YAML schema
    # Fabric API returns: { principal: { id, type, displayName }, role }
    principals = []
    for assignment in data.get("value", []):
        principal = assignment.get("principal", {})
        p_id = principal.get("id", "")
        p_type = principal.get("type", "")
        p_display = principal.get("displayName", "")
        role = assignment.get("role", "")

        if not p_id or not role:
            continue

        # Normalize type names to match our YAML convention
        type_map = {
            "User": "User",
            "Group": "Group",
            "ServicePrincipal": "ServicePrincipal",
            "ServicePrincipalProfile": "ServicePrincipal",
            "App": "ServicePrincipal",
        }
        normalized_type = type_map.get(p_type, p_type or "Unknown")

        principals.append(
            {
                "id": p_id,
                "type": normalized_type,
                "role": role,
                "description": p_display or f"Discovered {normalized_type}",
            }
        )

    return principals


def _slugify(name: str) -> str:
    """Convert workspace name to a filesystem-safe slug."""
    slug = name.lower().strip()
    # Remove bracketed suffixes like [DEV], [TEST], [PROD]
    slug = re.sub(r"\s*\[.*?\]\s*", "", slug)
    # Replace non-alphanumeric with underscore
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    # Clean up leading/trailing underscores
    slug = slug.strip("_")
    return slug


def _check_git_directory_conflicts(
    slug: str, output_dir: Optional[Path] = None
) -> Optional[str]:
    """Check if another project already uses the same git_directory.

    Scans ``config/projects/*/base_workspace.yaml`` for ``git_directory: /<slug>``
    collisions.  Skips the ``_templates/`` directory (templates are not live
    projects).  Returns the conflicting file path, or None if no conflict.
    """
    # Always search from config/projects/ -- walk up past _templates/ if needed
    if output_dir:
        search_root = output_dir.parent.parent
        # If we're inside _templates/, go one more level up to config/projects/
        if search_root.name == "_templates":
            search_root = search_root.parent
    else:
        search_root = Path("config/projects")

    if not search_root.exists():
        return None

    target_dir = f"/{slug}"
    for yaml_file in search_root.glob("*/base_workspace.yaml"):
        # Skip templates -- they are not live project configs
        if "_templates" in yaml_file.parts:
            continue
        try:
            content = yaml_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("git_directory:"):
                    value = stripped.split(":", 1)[1].strip().strip("\"'")
                    if value == target_dir:
                        return str(yaml_file)
        except OSError:
            continue
    return None


# -- Dev/Test/Prod stage name patterns --------------------------------------
# Recognises [DEV], (DEV), -DEV, _DEV, Dev, Development -- case-insensitive
_STAGE_PATTERNS: List[tuple] = [
    # Bracketed: [DEV], [Dev], [dev]
    (re.compile(r"\[DEV(?:ELOPMENT)?\]", re.IGNORECASE), "[{stage}]"),
    # Parenthesised: (DEV)
    (re.compile(r"\(DEV(?:ELOPMENT)?\)", re.IGNORECASE), "({stage})"),
    # Suffix with separator: -DEV, _DEV, - DEV, _ Dev
    (re.compile(r"[\s]*[-_][\s]*DEV(?:ELOPMENT)?$", re.IGNORECASE), " [{stage}]"),
    # Bare suffix: "... Dev", "... Development" (whole-word, end-of-string)
    (re.compile(r"\bDev(?:elopment)?$", re.IGNORECASE), "[{stage}]"),
]


def _infer_stage_name(workspace_name: str, target_stage: str) -> str:
    """Infer a Test/Prod workspace name from the Dev workspace name.

    Handles common naming conventions:
      ``EDP [DEV]``       ->  ``EDP [TEST]``          (bracket replacement)
      ``Sales - Dev``     ->  ``Sales [TEST]``         (separator replacement)
      ``HR Development``  ->  ``HR [TEST]``            (word replacement)
      ``MyWorkspace``     ->  ``MyWorkspace [TEST]``   (append as fallback)
    """
    for pattern, template in _STAGE_PATTERNS:
        if pattern.search(workspace_name):
            replacement = template.format(stage=target_stage)
            return pattern.sub(replacement, workspace_name).strip()

    # Fallback: no recognisable dev marker -- append [STAGE]
    return f"{workspace_name} [{target_stage}]"


def _strip_dev_marker(workspace_name: str) -> str:
    """Remove the dev/development marker from a workspace name.

    Returns the base project name without stage indicators.
    """
    for pattern, _template in _STAGE_PATTERNS:
        if pattern.search(workspace_name):
            return pattern.sub("", workspace_name).strip()
    return workspace_name.strip()


def _infer_pipeline_name(workspace_name: str) -> str:
    """Infer a deployment pipeline name from the workspace name.

    Follows the established convention: ``<base_name> - Pipeline``.

    Examples:
      ``EDP [DEV]``                   ->  ``EDP - Pipeline``
      ``Sales Audience [DEV]``        ->  ``Sales Audience - Pipeline``
      ``HR Development``              ->  ``HR - Pipeline``
      ``MyWorkspace``                 ->  ``MyWorkspace - Pipeline``
    """
    base_name = _strip_dev_marker(workspace_name)
    return f"{base_name} - Pipeline"


def _generate_yaml(
    workspace_name: str,
    folders: List[str],
    items_by_type: Dict[str, List[Dict[str, Any]]],
    folder_rules: List[Dict[str, str]],
    pipeline_name: Optional[str] = None,
    project_slug: Optional[str] = None,
    discovered_principals: Optional[List[Dict[str, str]]] = None,
    test_workspace_name: Optional[str] = None,
    prod_workspace_name: Optional[str] = None,
    templatise: bool = False,
    git_branch: str = "main",
    git_directory: Optional[str] = None,
    git_repo_fallback: str = "${GIT_REPO_URL}",
    brownfield: bool = False,
) -> str:
    """Generate base_workspace.yaml content."""
    slug = project_slug or _slugify(workspace_name)
    upper_slug = slug.upper()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = []
    separator = "# " + "-" * 77

    if templatise:
        lines.append(separator)
        lines.append("# CHANGE-ME [DEV] -- Base Workspace Configuration (Template)")
        lines.append("#")
        lines.append("# Auto-generated by: scaffold_workspace.py")
        lines.append(f"# Generated at: {timestamp}")
        lines.append(f"# Scaffolded from: {workspace_name}")
        lines.append("#")
        lines.append(
            "# TEMPLATE -- Copy this folder to config/projects/<your_project>/ and"
        )
        lines.append("# replace values marked CHANGE-ME using:")
        lines.append(
            "#   make new-project project=<slug> " f'display="<Name>" template={slug}'
        )
        lines.append("#")
        lines.append(
            "# Principals are fully runtime-configurable via env vars"
            " / GitHub Secrets."
        )
        lines.append("# No hardcoded GUIDs in this template.")
        lines.append(separator)
    else:
        lines.append(separator)
        lines.append(f"# {workspace_name} -- Base Workspace Configuration")
        lines.append("#")
        lines.append("# Auto-generated by: scaffold_workspace.py")
        lines.append(f"# Generated at: {timestamp}")
        lines.append(f"# Source workspace: {workspace_name}")
        lines.append("#")
        lines.append(
            "# REVIEW THIS FILE before deploying. Replace" " placeholder values"
        )
        lines.append("# (${...}) with your actual GitHub Secrets / env vars.")
        lines.append(separator)
    lines.append("")

    # -- Resolve display names for workspace/pipeline/stages --
    if templatise:
        ws_name = "CHANGE-ME [DEV]"
        ws_desc = "Standard data product workspace"
        git_dir = git_directory or "/CHANGE-ME"
        git_repo = '"${GIT_REPO_URL}"'
        git_branch_out = '"main"'
    else:
        ws_name = workspace_name
        ws_desc = f"{workspace_name} workspace -- managed by CI/CD"
        git_dir = git_directory or f"/{slug}"
        git_repo = f'"{git_repo_fallback}"'
        git_branch_out = f'"{git_branch}"'

    # -- workspace section --
    lines.append("workspace:")
    lines.append(f'  name: "{ws_name}"')
    lines.append(f'  display_name: "{ws_name}"')
    lines.append(f'  description: "{ws_desc}"')
    lines.append("  capacity_id: ${FABRIC_CAPACITY_ID}")
    lines.append("  domain: ${FABRIC_DOMAIN_NAME}")
    lines.append(f"  git_repo: {git_repo}")
    lines.append(f"  git_branch: {git_branch_out}")
    lines.append(f"  git_directory: {git_dir}")
    lines.append("")

    # -- environments section --
    lines.append("environments:")
    lines.append("  dev:")
    lines.append("    workspace:")
    lines.append(f'      name: "{ws_name}"')
    lines.append("      capacity_id: ${FABRIC_CAPACITY_ID}")
    lines.append("")

    # -- folders section --
    lines.append("# Folder structure (discovered from workspace)")
    lines.append("folders:")
    for folder in folders:
        lines.append(f'  - "{folder}"')
    lines.append("")

    # -- folder_rules section --
    if folder_rules:
        lines.append("# Folder rules -- auto-organize items after Git Sync")
        lines.append("folder_rules:")
        for rule in folder_rules:
            lines.append(f'  - type: {rule["type"]}')
            lines.append(f'    folder: "{rule["folder"]}"')
        lines.append("")

    # -- items inventory (as comments, for reference) --
    lines.append(
        "# -- Discovered Items (for reference) ----------------------------------------"
    )
    total_count = sum(len(v) for v in items_by_type.values())
    lines.append(f"# Total items found: {total_count}")
    for item_type, items_list in sorted(items_by_type.items()):
        lines.append(f"#   {item_type}: {len(items_list)}")
        for item in items_list:
            name = item.get("displayName", "N/A")
            lines.append(f"#     - {name}")
    lines.append("")

    # -- items section (empty -- Git Sync manages content) --
    lines.append("# No Fabric items -- content is managed through Fabric Git Sync")
    lines.append("lakehouses: []")
    lines.append("notebooks: []")
    lines.append("resources: []")
    lines.append("")

    # -- principals section --
    lines.append("# Access control")
    lines.append("principals:")

    if templatise:
        # Templatised: always emit standard governance + CHANGEME_ project principals
        # matching the standard_data_product template structure exactly
        lines.append(
            "  # -- Mandatory governance principals" " (every workspace gets these) --"
        )
        lines.append('  - id: "${AZURE_CLIENT_ID}"')
        lines.append("    type: ServicePrincipal")
        lines.append("    role: Admin")
        lines.append(
            "    description: Automation Service Principal"
            " -- required for CI/CD deployments"
        )
        lines.append("")
        lines.append('  - id: "${ADDITIONAL_ADMIN_PRINCIPAL_ID}"')
        lines.append("    type: Group")
        lines.append("    role: Admin")
        lines.append("    description: Mandatory IT governance admin group")
        lines.append("")
        lines.append('  - id: "${ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID}"')
        lines.append("    type: Group")
        lines.append("    role: Contributor")
        lines.append("    description: Mandatory governance contributor group")
        lines.append("")
        lines.append("  # -- Project-specific principals (runtime-configurable) --")
        lines.append('  - id: "${CHANGEME_ADMIN_ID}"')
        lines.append("    type: Group")
        lines.append("    role: Admin")
        lines.append(
            '    description: "Project admins -- set via <PROJECT>_ADMIN_ID secret"'
        )
        lines.append("")
        lines.append('  - id: "${CHANGEME_MEMBERS_ID}"')
        lines.append("    type: Group")
        lines.append("    role: Member")
        lines.append(
            '    description: "Project team members'
            ' -- set via <PROJECT>_MEMBERS_ID secret"'
        )
        # Include discovered principals as reference comments if available
        if discovered_principals:
            lines.append("")
            lines.append(
                "  # -- Discovered principals from source workspace (for reference) --"
            )
            for p in discovered_principals:
                desc = p.get("description", p["id"][:12] + "...")
                lines.append(f"  #   {p['type']} ({p['role']}): {desc}")
    elif brownfield and discovered_principals:
        # Brownfield: workspace already exists with its own principals.
        # Emit mandatory governance env-var principals plus ALL discovered
        # principals as active entries with their actual GUIDs.  This ensures
        # they propagate to Test, Prod, and Feature workspaces.
        lines.append(
            "  # -- Mandatory governance principals" " (resolved via GitHub Secrets) --"
        )
        lines.append('  - id: "${AZURE_CLIENT_ID}"')
        lines.append("    type: ServicePrincipal")
        lines.append("    role: Admin")
        lines.append("    description: Automation SP -- required for CI/CD deployments")
        lines.append("")
        lines.append('  - id: "${ADDITIONAL_ADMIN_PRINCIPAL_ID}"')
        lines.append("    type: Group")
        lines.append("    role: Admin")
        lines.append("    description: Mandatory governance admin group")
        lines.append("")
        lines.append('  - id: "${ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID}"')
        lines.append("    type: Group")
        lines.append("    role: Contributor")
        lines.append("    description: Mandatory governance contributor group")
        lines.append("")
        lines.append("  # -- Discovered principals from live workspace (active) --")
        for p in discovered_principals:
            desc = p.get("description", f"Discovered {p['type']}")
            lines.append(f'  - id: "{p["id"]}"')
            lines.append(f"    type: {p['type']}")
            lines.append(f"    role: {p['role']}")
            lines.append(f'    description: "{desc}"')
            lines.append("")
    else:
        # Greenfield: emit governance + project-specific placeholder principals
        # using env var refs that must be set as GitHub Secrets before deploying.
        lines.append(
            "  # -- Mandatory governance principals" " (every workspace gets these) --"
        )
        lines.append('  - id: "${AZURE_CLIENT_ID}"')
        lines.append("    type: ServicePrincipal")
        lines.append("    role: Admin")
        lines.append("    description: Automation SP -- required for CI/CD deployments")
        lines.append("")
        lines.append('  - id: "${ADDITIONAL_ADMIN_PRINCIPAL_ID}"')
        lines.append("    type: Group")
        lines.append("    role: Admin")
        lines.append("    description: Mandatory governance admin group")
        lines.append("")
        lines.append('  - id: "${ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID}"')
        lines.append("    type: Group")
        lines.append("    role: Contributor")
        lines.append("    description: Mandatory governance contributor group")
        lines.append("")
        lines.append("  # -- Project-specific principals (runtime-configurable) --")
        lines.append(f'  - id: "${{{upper_slug}_ADMIN_ID}}"')
        lines.append("    type: Group")
        lines.append("    role: Admin")
        lines.append(
            f'    description: "{workspace_name} project admins'
            f' -- set via {upper_slug}_ADMIN_ID secret"'
        )
        lines.append("")
        lines.append(f'  - id: "${{{upper_slug}_MEMBERS_ID}}"')
        lines.append("    type: Group")
        lines.append("    role: Member")
        lines.append(
            f'    description: "{workspace_name} team members'
            f' -- set via {upper_slug}_MEMBERS_ID secret"'
        )

        if discovered_principals:
            lines.append("")
            lines.append(
                "  # -- Discovered principals from source workspace (for reference) --"
            )
            for p in discovered_principals:
                desc = p.get("description", p["id"][:12] + "...")
                lines.append(
                    f"  #   {p['id'][:8]}... {p['type']} ({p['role']}): {desc}"
                )
    lines.append("")

    # -- deployment pipeline section --
    if pipeline_name:
        # Resolve real stage names first (needed for both modes)
        if test_workspace_name:
            test_name = test_workspace_name
        elif prod_workspace_name:
            test_name = _infer_stage_name(workspace_name, "TEST")
        else:
            test_name = _infer_stage_name(workspace_name, "TEST")

        if prod_workspace_name:
            prod_name = prod_workspace_name
        else:
            prod_name = _infer_stage_name(workspace_name, "PROD")

        if templatise:
            pipe_display = "CHANGE-ME - Pipeline"
            dev_display = "CHANGE-ME [DEV]"
            test_display = "CHANGE-ME [TEST]"
            prod_display = "CHANGE-ME [PROD]"
            test_cap = "${FABRIC_CAPACITY_ID_TEST:-FABRIC_CAPACITY_ID}"
            prod_cap = "${FABRIC_CAPACITY_ID_PROD:-FABRIC_CAPACITY_ID}"
        else:
            pipe_display = pipeline_name
            dev_display = workspace_name
            test_display = test_name
            prod_display = prod_name
            test_cap = "${FABRIC_CAPACITY_ID_TEST:-FABRIC_CAPACITY_ID}"
            prod_cap = "${FABRIC_CAPACITY_ID_PROD:-FABRIC_CAPACITY_ID}"

        lines.append("# -- Deployment Pipeline " + "-" * 53)
        if templatise:
            lines.append(f"# Scaffolded from pipeline: {pipeline_name}")
            lines.append(
                f"# Inferred stages: {workspace_name} / {test_name} / {prod_name}"
            )
        lines.append("deployment_pipeline:")
        lines.append(f'  pipeline_name: "{pipe_display}"')
        lines.append("  stages:")
        lines.append("    development:")
        lines.append(f'      workspace_name: "{dev_display}"')
        lines.append("      capacity_id: ${FABRIC_CAPACITY_ID}")
        lines.append("    test:")
        lines.append(f'      workspace_name: "{test_display}"')
        lines.append(f"      capacity_id: {test_cap}")
        lines.append("    production:")
        lines.append(f'      workspace_name: "{prod_display}"')
        lines.append(f"      capacity_id: {prod_cap}")
        lines.append("")

    return "\n".join(lines) + "\n"


def _generate_feature_yaml(
    workspace_name: str,
    folders: List[str],
    project_slug: Optional[str] = None,
    templatise: bool = False,
    brownfield: bool = False,
    discovered_principals: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Generate feature_workspace.yaml content."""
    slug = project_slug or _slugify(workspace_name)
    upper_slug = slug.upper()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # When templatised, use /CHANGE-ME so new-project's sed can replace it
    git_dir = "/CHANGE-ME" if templatise else f"/{slug}"
    # Principal prefix: CHANGEME when templatised, actual UPPER_SLUG otherwise
    principal_prefix = "CHANGEME" if templatise else upper_slug

    # Derive the feature workspace base name from the workspace name.
    # Display-style names (with spaces, e.g., "Sales Audience [DEV]") should
    # use the display name (stripped of [DEV]) so that get_workspace_name_from_branch()
    # produces readable Fabric portal names like:
    #   [F] Sales Audience [FEATURE-my-branch]
    # Slug-style names (no spaces) use ${PROJECT_PREFIX} for backward compat.
    base_display_name = _strip_dev_marker(workspace_name)
    has_spaces = " " in base_display_name
    if templatise:
        ws_name_value = "${PROJECT_PREFIX}"
    elif has_spaces:
        ws_name_value = f'"{base_display_name}"'
    else:
        ws_name_value = "${PROJECT_PREFIX}"

    separator = "# " + "-" * 77
    lines = []
    if templatise:
        lines.append(separator)
        lines.append("# CHANGE-ME -- Feature Workspace Configuration (Template)")
        lines.append("#")
        lines.append("# Auto-generated by: scaffold_workspace.py")
        lines.append(f"# Generated at: {timestamp}")
        lines.append(f"# Scaffolded from: {workspace_name}")
        lines.append("#")
        lines.append(
            "# Feature workspaces are ephemeral -- created per feature branch,"
        )
        lines.append("# destroyed after PR merge. Items come from Fabric Git Sync.")
        lines.append(separator)
    else:
        lines.append(separator)
        lines.append(f"# {workspace_name} -- Feature Workspace Configuration")
        lines.append("#")
        lines.append("# Auto-generated by: scaffold_workspace.py")
        lines.append(f"# Generated at: {timestamp}")
        lines.append("#")
        lines.append(
            "# Feature workspaces are ephemeral -- created per feature branch,"
        )
        lines.append("# destroyed after PR merge. Items come from Fabric Git Sync.")
        lines.append(separator)
    lines.append("")

    lines.append("workspace:")
    lines.append(f"  name: {ws_name_value}")
    lines.append(f"  display_name: {ws_name_value}")
    lines.append(f'  description: "{base_display_name} feature branch workspace"')
    lines.append("  capacity_id: ${FABRIC_CAPACITY_ID}")
    lines.append("  domain: ${FABRIC_DOMAIN_NAME}")
    lines.append("  git_repo: ${GIT_REPO_URL}")
    lines.append("  git_branch: main")
    lines.append(f"  git_directory: {git_dir}")
    lines.append("")

    lines.append("environments:")
    lines.append("  dev:")
    lines.append("    workspace:")
    lines.append(f"      name: {ws_name_value}")
    lines.append("      capacity_id: ${FABRIC_CAPACITY_ID}")
    lines.append("")

    lines.append("# Folder structure -- same as base workspace")
    lines.append("folders:")
    for folder in folders:
        lines.append(f'  - "{folder}"')
    lines.append("")

    lines.append("# No Fabric items -- content is managed through Fabric Git Sync")
    lines.append("lakehouses: []")
    lines.append("notebooks: []")
    lines.append("resources: []")
    lines.append("")

    lines.append(
        "# Principals -- same as base workspace" " for full access on feature branches"
    )
    lines.append("principals:")
    lines.append('  - id: "${AZURE_CLIENT_ID}"')
    lines.append("    type: ServicePrincipal")
    lines.append("    role: Admin")
    lines.append("    description: Automation SP -- required for CI/CD deployments")
    lines.append("")
    lines.append('  - id: "${ADDITIONAL_ADMIN_PRINCIPAL_ID}"')
    lines.append("    type: Group")
    lines.append("    role: Admin")
    lines.append("    description: Mandatory governance admin group")
    lines.append("")
    lines.append('  - id: "${ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID}"')
    lines.append("    type: Group")
    lines.append("    role: Contributor")
    lines.append("    description: Mandatory governance contributor group")

    if brownfield and discovered_principals:
        # Brownfield: emit discovered principals as active entries
        lines.append("")
        lines.append("  # -- Discovered principals from live workspace --")
        for p in discovered_principals:
            desc = p.get("description", f"Discovered {p['type']}")
            lines.append(f'  - id: "{p["id"]}"')
            lines.append(f"    type: {p['type']}")
            lines.append(f"    role: {p['role']}")
            lines.append(f'    description: "{desc}"')
            lines.append("")
    else:
        # Greenfield: emit placeholder env-var principals
        lines.append("")
        lines.append("  # -- Project-specific principals (runtime-configurable) --")
        lines.append(f'  - id: "${{{principal_prefix}_ADMIN_ID}}"')
        lines.append("    type: Group")
        lines.append("    role: Admin")
        lines.append(
            f'    description: "{base_display_name} project admins'
            f' -- set via {principal_prefix}_ADMIN_ID secret"'
        )
        lines.append("")
        lines.append(f'  - id: "${{{principal_prefix}_MEMBERS_ID}}"')
        lines.append("    type: Group")
        lines.append("    role: Member")
        lines.append(
            f'    description: "{base_display_name} team members'
            f' -- set via {principal_prefix}_MEMBERS_ID secret"'
        )
    lines.append("")

    return "\n".join(lines) + "\n"


def scaffold_workspace(
    workspace_name: str,
    output_path: Optional[str] = None,
    include_feature_template: bool = False,
    pipeline_name: Optional[str] = None,
    project_slug: Optional[str] = None,
    test_workspace_name: Optional[str] = None,
    prod_workspace_name: Optional[str] = None,
    templatise: bool = False,
    skip_pipeline: bool = False,
    skip_feature_template: bool = False,
    brownfield: bool = False,
) -> Dict[str, str]:
    """Scaffold YAML config(s) from a live Fabric workspace.

    By default, generates both ``base_workspace.yaml`` (with deployment
    pipeline) and ``feature_workspace.yaml``.  Use ``skip_pipeline`` or
    ``skip_feature_template`` to opt out of either.

    Args:
        workspace_name: Name of the existing Fabric workspace to scan.
        output_path: Path for the base_workspace.yaml file.
            Defaults to ``config/projects/_templates/<slug>/base_workspace.yaml``.
        include_feature_template: Legacy flag — feature template is now
            generated by default.  Kept for backward compatibility.
        pipeline_name: Override the auto-inferred deployment pipeline name.
            If omitted, inferred from ``workspace_name`` using the
            ``<base_name> - Pipeline`` convention.
        project_slug: Override the auto-generated slug for filenames/paths.
        test_workspace_name: Explicit name for the Test stage workspace.
            If omitted, inferred from ``workspace_name``.
        prod_workspace_name: Explicit name for the Production stage workspace.
            If omitted, inferred from ``workspace_name``.
        templatise: Replace real workspace/pipeline names with CHANGE-ME
            placeholders, making the output compatible with
            ``make new-project`` placeholder replacement.
        skip_pipeline: Do not include the deployment_pipeline section.
        skip_feature_template: Do not generate feature_workspace.yaml.
        brownfield: Emit discovered principals as active YAML entries
            with their actual GUIDs instead of placeholder env vars.
            Use for workspaces that already exist with their own
            principals that need to propagate to Test/Prod/Feature.

    Returns:
        Dict mapping output file paths -> "ok" or error message.
    """
    results: Dict[str, str] = {}

    # -- 1. Initialize wrapper --
    # get_environment_variables() handles the full auth waterfall:
    #   1. FABRIC_TOKEN from env  ->  use directly
    #   2. SP creds (AZURE_CLIENT_ID / SECRET / TENANT_ID)  ->  auto-generates token
    #   3. .env file in config/  ->  loaded automatically
    # This matches the deployer's auth path -- no separate FABRIC_TOKEN requirement.
    env_vars = get_environment_variables(validate_vars=False)
    token = env_vars.get("FABRIC_TOKEN", "") or os.getenv("FABRIC_TOKEN", "")
    if not token:
        raise ValueError(
            "Authentication failed. One of the following is required:\n"
            "  - FABRIC_TOKEN environment variable, OR\n"
            "  - Service Principal credentials: AZURE_CLIENT_ID + "
            "AZURE_CLIENT_SECRET + AZURE_TENANT_ID\n"
            "Set them in .env or export as environment variables."
        )

    fabric = FabricCLIWrapper(token)
    slug = project_slug or _slugify(workspace_name)

    # -- Auto-infer pipeline name unless explicitly skipped --
    if not skip_pipeline and not pipeline_name:
        pipeline_name = _infer_pipeline_name(workspace_name)
        print(f"   Auto-inferred pipeline name: {pipeline_name}")
    elif skip_pipeline:
        pipeline_name = None

    # -- 2. Verify workspace exists --
    print(f"\nScanning workspace '{workspace_name}'...")
    workspace_id = fabric.get_workspace_id(workspace_name)
    if not workspace_id:
        raise ValueError(
            f"Workspace '{workspace_name}' not found. "
            "Check the name and your Service Principal access permissions."
        )
    print(f"   Workspace ID: {workspace_id}")

    # -- 3. List folders --
    print("   Discovering folders...")
    raw_folders = _get_workspace_folders(fabric, workspace_name)
    folder_names = _build_folder_paths(raw_folders) if raw_folders else []
    if folder_names:
        print(f"   Found {len(folder_names)} folders: {', '.join(folder_names)}")
    else:
        print("   No folders found -- will use default medallion structure.")
        folder_names = DEFAULT_FOLDERS.copy()

    # -- 4. List items --
    print("   Discovering items...")
    items = fabric.list_workspace_items_api(workspace_name)
    items_by_type = _categorize_items(items)
    total_items = len(items)
    print(f"   Found {total_items} items across {len(items_by_type)} types:")
    for item_type, type_items in sorted(items_by_type.items()):
        print(f"     {item_type}: {len(type_items)}")

    # -- 5. Infer folder rules from discovered types --
    folder_rules = _build_folder_rules(items, folders=raw_folders)

    # -- 5b. Discover principals (role assignments) --
    print("   Discovering principals...")
    discovered_principals = _discover_principals(fabric, workspace_name)
    if discovered_principals:
        print(f"   Found {len(discovered_principals)} role assignments:")
        for p in discovered_principals:
            print(
                f"     {p['type']} ({p['role']}): "
                f"{p.get('description', p['id'][:8] + '...')}"
            )
    else:
        print("   No role assignments discovered -- using placeholder principals.")

    # -- 5c. Check git_directory conflicts --
    if output_path:
        check_path = Path(output_path)
    else:
        check_path = Path(f"config/projects/_templates/{slug}/base_workspace.yaml")
    conflict = _check_git_directory_conflicts(slug, check_path)
    if conflict:
        print(f"\n[!] WARNING: git_directory '/{slug}' is already used in: {conflict}")
        print(
            "   Consider using --project-slug to set a unique slug, "
            "or update the existing config."
        )

    # -- 5d. Discover Git connection details --
    print("   Discovering Git connection details...")
    git_api = FabricGitAPI(token)
    git_branch = "main"
    git_directory = None
    git_repo_url = "${GIT_REPO_URL}"
    try:
        git_conn = git_api.get_git_connection(workspace_id)
        if git_conn and git_conn.get("gitProviderDetails"):
            details = git_conn["gitProviderDetails"]
            git_branch = details.get("branchName", "main")
            raw_dir = details.get("directoryName", "")
            if raw_dir:
                git_directory = raw_dir if raw_dir.startswith("/") else f"/{raw_dir}"
            repo_name = details.get("repositoryName")
            org_name = details.get("organizationName")
            project_name = details.get("projectName")
            owner_name = details.get("ownerName")

            if org_name and project_name and repo_name:
                git_repo_url = (
                    f"https://dev.azure.com/{org_name}/{project_name}/_git/{repo_name}"
                )
            elif owner_name and repo_name:
                git_repo_url = f"https://github.com/{owner_name}/{repo_name}"

            print(
                f"   Found Git connection: branch='{git_branch}', "
                f"directory='{git_directory}'"
            )
        else:
            print("   No Git connection found on workspace.")
    except Exception as e:
        print(f"   Could not discover Git connection: {e}")

    # -- 6. Generate base_workspace.yaml --
    base_yaml = _generate_yaml(
        workspace_name=workspace_name,
        folders=folder_names,
        items_by_type=items_by_type,
        folder_rules=folder_rules,
        pipeline_name=pipeline_name,
        project_slug=slug,
        discovered_principals=discovered_principals,
        test_workspace_name=test_workspace_name,
        prod_workspace_name=prod_workspace_name,
        templatise=templatise,
        git_branch=git_branch,
        git_directory=git_directory,
        git_repo_fallback=git_repo_url,
        brownfield=brownfield,
    )

    if output_path:
        base_path = Path(output_path).resolve()
    else:
        base_path = Path(
            f"config/projects/_templates/{slug}/base_workspace.yaml"
        ).resolve()

    # Validate output path -- guard against writing outside the project tree
    cwd = Path.cwd().resolve()
    if not str(base_path).startswith(str(cwd)):
        raise SystemExit(
            f"Error: output path '{base_path}' is outside the project "
            f"directory '{cwd}'. Use a relative path or one within the "
            f"project tree."
        )

    base_path.parent.mkdir(parents=True, exist_ok=True)
    base_path.write_text(base_yaml, encoding="utf-8")
    print(f"\n[OK] Generated: {base_path}")
    results[str(base_path)] = "ok"

    # -- 7. Generate feature_workspace.yaml (default / auto-update) --
    # Generated by default to ensure scaffold output is all-encompassing.
    # Use skip_feature_template=True to opt out.
    feature_path = base_path.parent / "feature_workspace.yaml"
    should_generate_feature = not skip_feature_template
    if should_generate_feature:
        feature_yaml = _generate_feature_yaml(
            workspace_name=workspace_name,
            folders=folder_names,
            project_slug=slug,
            templatise=templatise,
            brownfield=brownfield,
            discovered_principals=discovered_principals,
        )
        feature_path.write_text(feature_yaml, encoding="utf-8")
        print(f"[OK] Generated: {feature_path}")
        results[str(feature_path)] = "ok"

    # -- 8. Summary --
    print("\nScaffold Summary:")
    print(f"   Workspace:    {workspace_name}")
    print(f"   Workspace ID: {workspace_id}")
    print(f"   Folders:      {len(folder_names)}")
    print(f"   Items:        {total_items}")
    print(f"   Folder rules: {len(folder_rules)}")
    principals_label = (
        f"{len(discovered_principals)} discovered"
        if discovered_principals
        else "3 placeholders"
    )
    print(f"   Principals:   {principals_label}")
    if conflict:
        print(f"   [!] git_directory conflict: {conflict}")
    print(f"   Output:       {base_path.parent}/")
    print()
    # -- Next steps (context-aware) --
    # A project is fully onboarded when BOTH exist:
    #   1. config/projects/<slug>/  (config directory)
    #   2. slug appears in a workflow dropdown (e.g., setup-base-workspaces.yml)
    # If only the directory exists (manual copy), we still need make new-project
    # to wire up workflow dropdowns and env vars.
    project_dir = Path(f"config/projects/{slug}")
    project_dir_exists = project_dir.is_dir()

    # Check if slug appears in any workflow dropdown
    in_workflow = False
    workflows_dir = Path(".github/workflows")
    if workflows_dir.is_dir():
        for wf in workflows_dir.glob("*.yml"):
            try:
                content = wf.read_text(encoding="utf-8")
                if f"- {slug}" in content:
                    in_workflow = True
                    break
            except OSError:
                pass

    project_exists = project_dir_exists and in_workflow

    print("Next steps:")
    step = 1

    print(f"   {step}. Review the generated configs")
    step += 1

    if brownfield:
        if not project_exists:
            display = _strip_dev_marker(workspace_name)
            print(
                f"   {step}. Create a concrete project from the template:\n"
                f"      make new-project project={slug} "
                f'display="{display}" template={slug}'
            )
            step += 1
        else:
            print(
                f"   -- Project '{slug}' already exists "
                f"-- no need for 'make new-project'"
            )
        print(
            f"   {step}. Verify mandatory governance secrets exist in GitHub:\n"
            "      AZURE_CLIENT_ID, ADDITIONAL_ADMIN_PRINCIPAL_ID, "
            "ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID"
        )
        step += 1
    elif templatise:
        print(
            f"   {step}. Create a project from this template:\n"
            f"      make new-project project=<slug> "
            f'display="<Name>" template={slug}'
        )
        step += 1
        print(
            f"   {step}. Add required secrets to GitHub "
            f"(run: make show-secrets project=<slug>)"
        )
        step += 1
    else:
        if discovered_principals:
            print(
                f"   {step}. Replace literal principal IDs with env var "
                "references (${...}) for portability"
            )
            step += 1
        if not project_exists:
            display = _strip_dev_marker(workspace_name)
            print(
                f"   {step}. Create a concrete project from the template:\n"
                f"      make new-project project={slug} "
                f'display="{display}" template={slug}'
            )
            step += 1
        else:
            print(
                f"   -- Project '{slug}' already exists "
                f"-- no need for 'make new-project'"
            )
        print(
            f"   {step}. Add required secrets to GitHub "
            f"(run: make show-secrets project={slug})"
        )
        step += 1

    print(
        f"   {step}. Run the 'Setup Base Workspaces' "
        f"GitHub Actions workflow for this project"
    )
    print()

    return results


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Scaffold a YAML config from an existing Fabric workspace. "
            "Scans the workspace's folders and items, then generates "
            "a deployer-compatible config file."
        ),
    )
    parser.add_argument(
        "workspace_name",
        help="Name of the existing Fabric workspace to scan",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help=(
            "Output path for base_workspace.yaml "
            "(default: config/projects/_templates/<slug>/base_workspace.yaml)"
        ),
    )
    parser.add_argument(
        "--include-feature-template",
        "-f",
        action="store_true",
        help="Legacy flag — feature template is now generated by default",
    )
    parser.add_argument(
        "--pipeline-name",
        "-p",
        default=None,
        help="Override the auto-inferred deployment pipeline name",
    )
    parser.add_argument(
        "--skip-pipeline",
        action="store_true",
        help="Do not include the deployment_pipeline section",
    )
    parser.add_argument(
        "--skip-feature-template",
        action="store_true",
        help="Do not generate feature_workspace.yaml",
    )
    parser.add_argument(
        "--project-slug",
        "-s",
        default=None,
        help="Override the auto-generated project slug",
    )
    parser.add_argument(
        "--test-workspace-name",
        default=None,
        help="Explicit Test stage workspace name (overrides auto-inference)",
    )
    parser.add_argument(
        "--prod-workspace-name",
        default=None,
        help="Explicit Production stage workspace name (overrides auto-inference)",
    )
    parser.add_argument(
        "--templatise",
        action="store_true",
        default=False,
        help=(
            "Replace real workspace/pipeline names with CHANGE-ME placeholders, "
            "making the output a reusable template for 'make new-project'"
        ),
    )
    parser.add_argument(
        "--brownfield",
        action="store_true",
        default=False,
        help=(
            "Emit discovered principals as active YAML entries with actual GUIDs "
            "instead of placeholder env vars. Use for existing workspaces that "
            "already have principals which need to propagate to Test/Prod/Feature."
        ),
    )

    args = parser.parse_args()

    try:
        scaffold_workspace(
            workspace_name=args.workspace_name,
            output_path=args.output,
            include_feature_template=args.include_feature_template,
            pipeline_name=args.pipeline_name,
            project_slug=args.project_slug,
            test_workspace_name=args.test_workspace_name,
            prod_workspace_name=args.prod_workspace_name,
            templatise=args.templatise,
            skip_pipeline=args.skip_pipeline,
            skip_feature_template=args.skip_feature_template,
            brownfield=args.brownfield,
        )
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
