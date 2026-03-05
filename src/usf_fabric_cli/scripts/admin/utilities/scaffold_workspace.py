#!/usr/bin/env python3
"""
Scaffold Workspace Configuration.

Connects to a live Microsoft Fabric workspace, introspects its items,
folders, and structure, then generates a YAML config file compatible
with the usf_fabric_cli_cicd deployer.

This eliminates the need to manually write YAML — especially useful
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

from usf_fabric_cli.services.fabric_wrapper import FabricCLIWrapper
from usf_fabric_cli.utils.config import get_environment_variables

logger = logging.getLogger(__name__)


# ── Fabric item type → recommended folder mapping ──────────────────────────
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
        return [
            {"id": f.get("id", ""), "displayName": f.get("displayName", "")}
            for f in data["value"]
        ]

    return []


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
    # Build folder-ID → display-name lookup from discovered folders
    folder_id_to_name: Dict[str, str] = {}
    if folders:
        folder_id_to_name = {
            f["id"]: f["displayName"]
            for f in folders
            if f.get("id") and f.get("displayName")
        }

    # Determine the most common folder per item type based on actual placement
    type_to_folder: Dict[str, str] = {}
    if folder_id_to_name:
        # Count how many items of each type live in each folder
        type_folder_counts: Dict[str, Counter] = defaultdict(Counter)
        for item in items:
            item_type = item.get("type", "")
            folder_id = item.get("folderId") or item.get("parentFolderId")
            if item_type and folder_id and folder_id in folder_id_to_name:
                type_folder_counts[item_type][folder_id_to_name[folder_id]] += 1

        # Pick the most common folder for each type (majority vote)
        for item_type, counter in type_folder_counts.items():
            most_common_folder, _ = counter.most_common(1)[0]
            type_to_folder[item_type] = most_common_folder

    # Build final rules — prefer actual placement, fall back to hardcoded map
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
            "Could not retrieve role assignments for '%s' — "
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
    # Always search from config/projects/ — walk up past _templates/ if needed
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
        # Skip templates — they are not live project configs
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


# ── Dev/Test/Prod stage name patterns ──────────────────────────────────────
# Recognises [DEV], (DEV), -DEV, _DEV, Dev, Development — case-insensitive
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
      ``EDP [DEV]``       →  ``EDP [TEST]``          (bracket replacement)
      ``Sales - Dev``     →  ``Sales [TEST]``         (separator replacement)
      ``HR Development``  →  ``HR [TEST]``            (word replacement)
      ``MyWorkspace``     →  ``MyWorkspace [TEST]``   (append as fallback)
    """
    for pattern, template in _STAGE_PATTERNS:
        if pattern.search(workspace_name):
            replacement = template.format(stage=target_stage)
            return pattern.sub(replacement, workspace_name).strip()

    # Fallback: no recognisable dev marker — append [STAGE]
    return f"{workspace_name} [{target_stage}]"


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
) -> str:
    """Generate base_workspace.yaml content."""
    slug = project_slug or _slugify(workspace_name)
    upper_slug = slug.upper()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = []
    separator = "# " + "─" * 77
    lines.append(separator)
    lines.append(f"# {workspace_name} — Base Workspace Configuration")
    lines.append("#")
    lines.append("# Auto-generated by: scaffold_workspace.py")
    lines.append(f"# Generated at: {timestamp}")
    lines.append(f"# Source workspace: {workspace_name}")
    lines.append("#")
    lines.append("# REVIEW THIS FILE before deploying. Replace " "placeholder values")
    lines.append("# (${...}) with your actual GitHub Secrets / env vars.")
    lines.append(separator)
    lines.append("")

    # ── workspace section ──
    lines.append("workspace:")
    lines.append(f'  name: "{workspace_name}"')
    lines.append(f'  display_name: "{workspace_name}"')
    lines.append(f'  description: "{workspace_name} workspace — managed by CI/CD"')
    lines.append("  capacity_id: ${FABRIC_CAPACITY_ID}")
    lines.append("  domain: ${FABRIC_DOMAIN_NAME}")
    lines.append("  git_repo: ${GIT_REPO_URL}")
    lines.append("  git_branch: main")
    lines.append(f"  git_directory: /{slug}")
    lines.append("")

    # ── environments section ──
    lines.append("environments:")
    lines.append("  dev:")
    lines.append("    workspace:")
    lines.append(f'      name: "{workspace_name}"')
    lines.append("      capacity_id: ${FABRIC_CAPACITY_ID}")
    lines.append("")

    # ── folders section ──
    lines.append("# Folder structure (discovered from workspace)")
    lines.append("folders:")
    for folder in folders:
        lines.append(f'  - "{folder}"')
    lines.append("")

    # ── folder_rules section ──
    if folder_rules:
        lines.append("# Folder rules — auto-organize items after Git Sync")
        lines.append("folder_rules:")
        for rule in folder_rules:
            lines.append(f'  - type: {rule["type"]}')
            lines.append(f'    folder: "{rule["folder"]}"')
        lines.append("")

    # ── items inventory (as comments, for reference) ──
    lines.append(
        "# ── Discovered Items (for reference) ────────────────────────────────────────"
    )
    total_count = sum(len(v) for v in items_by_type.values())
    lines.append(f"# Total items found: {total_count}")
    for item_type, items_list in sorted(items_by_type.items()):
        lines.append(f"#   {item_type}: {len(items_list)}")
        for item in items_list:
            name = item.get("displayName", "N/A")
            lines.append(f"#     - {name}")
    lines.append("")

    # ── items section (empty — Git Sync manages content) ──
    lines.append("# No Fabric items — content is managed through Fabric Git Sync")
    lines.append("lakehouses: []")
    lines.append("notebooks: []")
    lines.append("resources: []")
    lines.append("")

    # ── principals section ──
    lines.append("# Access control")
    lines.append("principals:")

    if discovered_principals:
        # Emit real principals discovered from the live workspace
        for i, p in enumerate(discovered_principals, 1):
            lines.append(f"  # {i}. {p.get('description', 'Discovered principal')}")
            lines.append(f'  - id: "{p["id"]}"')
            lines.append(f"    type: {p['type']}")
            lines.append(f"    role: {p['role']}")
            lines.append(f'    description: "{p.get("description", "")}"')
            lines.append("")
        lines.append(
            "  # NOTE: Principals above were discovered from the live workspace."
        )
        lines.append(
            "  # Consider replacing literal IDs with env var " "references (${...})"
        )
        lines.append("  # for portability across environments.")
    else:
        # Fallback: placeholder principals when discovery fails
        lines.append("  # 1. Automation Service Principal (runs deployments)")
        lines.append('  - id: "${AZURE_CLIENT_ID}"')
        lines.append("    type: ServicePrincipal")
        lines.append("    role: Admin")
        lines.append("    description: Automation SP — required for CI/CD deployments")
        lines.append("")
        lines.append("  # 2. Admin security group (governance)")
        lines.append('  - id: "${ADDITIONAL_ADMIN_PRINCIPAL_ID}"')
        lines.append("    type: Group")
        lines.append("    role: Admin")
        lines.append("    description: Mandatory governance admin group")
        lines.append("")
        lines.append("  # 3. Contributor security group (support team)")
        lines.append('  - id: "${ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID}"')
        lines.append("    type: Group")
        lines.append("    role: Contributor")
        lines.append("    description: Mandatory governance contributor group")
    lines.append("")
    lines.append(
        f"  # TODO: Add project-specific principals (e.g. ${{{upper_slug}_ADMIN_ID}})"
    )
    lines.append(f'  # - id: "${{{upper_slug}_ADMIN_ID}}"')
    lines.append("  #   type: Group")
    lines.append("  #   role: Admin")
    lines.append(f'  #   description: "{workspace_name} project admins"')
    lines.append("")

    # ── deployment pipeline section ──
    if pipeline_name:
        lines.append("# ── Deployment Pipeline " + "─" * 53)
        lines.append("deployment_pipeline:")
        lines.append(f'  pipeline_name: "{pipeline_name}"')
        lines.append("  stages:")
        lines.append("    development:")
        lines.append(f'      workspace_name: "{workspace_name}"')
        lines.append("      capacity_id: ${FABRIC_CAPACITY_ID}")
        lines.append("    test:")

        # Use explicit overrides if provided, otherwise infer from dev name
        if test_workspace_name:
            test_name = test_workspace_name
        elif prod_workspace_name:
            # Only prod was given — still need to infer test
            test_name = _infer_stage_name(workspace_name, "TEST")
        else:
            test_name = _infer_stage_name(workspace_name, "TEST")

        if prod_workspace_name:
            prod_name = prod_workspace_name
        else:
            prod_name = _infer_stage_name(workspace_name, "PROD")

        lines.append(f'      workspace_name: "{test_name}"')
        lines.append("      capacity_id: ${FABRIC_CAPACITY_ID}")
        lines.append("    production:")
        lines.append(f'      workspace_name: "{prod_name}"')
        lines.append("      capacity_id: ${FABRIC_CAPACITY_ID}")
        lines.append("")

    return "\n".join(lines) + "\n"


def _generate_feature_yaml(
    workspace_name: str,
    folders: List[str],
    project_slug: Optional[str] = None,
) -> str:
    """Generate feature_workspace.yaml content."""
    slug = project_slug or _slugify(workspace_name)
    upper_slug = slug.upper()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    separator = "# " + "─" * 77
    lines = []
    lines.append(separator)
    lines.append(f"# {workspace_name} — Feature Workspace Configuration")
    lines.append("#")
    lines.append("# Auto-generated by: scaffold_workspace.py")
    lines.append(f"# Generated at: {timestamp}")
    lines.append("#")
    lines.append("# Feature workspaces are ephemeral — created per " "feature branch,")
    lines.append("# destroyed after PR merge. Items come from Fabric " "Git Sync.")
    lines.append(separator)
    lines.append("")

    lines.append("workspace:")
    lines.append("  name: ${PROJECT_PREFIX}")
    lines.append("  display_name: ${PROJECT_PREFIX}")
    lines.append(f'  description: "{workspace_name} feature branch workspace"')
    lines.append("  capacity_id: ${FABRIC_CAPACITY_ID}")
    lines.append("  domain: ${FABRIC_DOMAIN_NAME}")
    lines.append("  git_repo: ${GIT_REPO_URL}")
    lines.append("  git_branch: main")
    lines.append(f"  git_directory: /{slug}")
    lines.append("")

    lines.append("environments:")
    lines.append("  dev:")
    lines.append("    workspace:")
    lines.append("      name: ${PROJECT_PREFIX}")
    lines.append("      capacity_id: ${FABRIC_CAPACITY_ID}")
    lines.append("")

    lines.append("# Folder structure — same as base workspace")
    lines.append("folders:")
    for folder in folders:
        lines.append(f'  - "{folder}"')
    lines.append("")

    lines.append("# No Fabric items — content is managed through Fabric Git Sync")
    lines.append("lakehouses: []")
    lines.append("notebooks: []")
    lines.append("resources: []")
    lines.append("")

    lines.append("# Mandatory governance principals")
    lines.append("principals:")
    lines.append('  - id: "${AZURE_CLIENT_ID}"')
    lines.append("    type: ServicePrincipal")
    lines.append("    role: Admin")
    lines.append("    description: Automation SP — required for CI/CD deployments")
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
    lines.append("  # TODO: Add project-specific principals")
    lines.append(f'  # - id: "${{{upper_slug}_ADMIN_ID}}"')
    lines.append("  #   type: Group")
    lines.append("  #   role: Admin")
    lines.append(f'  #   description: "{workspace_name} project admins"')
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
) -> Dict[str, str]:
    """Scaffold YAML config(s) from a live Fabric workspace.

    Args:
        workspace_name: Name of the existing Fabric workspace to scan.
        output_path: Path for the base_workspace.yaml file.
            Defaults to ``config/projects/_templates/<slug>/base_workspace.yaml``.
        include_feature_template: Also generate feature_workspace.yaml.
        pipeline_name: If provided, include deployment_pipeline section.
        project_slug: Override the auto-generated slug for filenames/paths.
        test_workspace_name: Explicit name for the Test stage workspace.
            If omitted, inferred from ``workspace_name``.
        prod_workspace_name: Explicit name for the Production stage workspace.
            If omitted, inferred from ``workspace_name``.

    Returns:
        Dict mapping output file paths → "ok" or error message.
    """
    results: Dict[str, str] = {}

    # ── 1. Initialize wrapper ──
    # get_environment_variables() handles the full auth waterfall:
    #   1. FABRIC_TOKEN from env  →  use directly
    #   2. SP creds (AZURE_CLIENT_ID / SECRET / TENANT_ID)  →  auto-generates token
    #   3. .env file in config/  →  loaded automatically
    # This matches the deployer's auth path — no separate FABRIC_TOKEN requirement.
    env_vars = get_environment_variables(validate_vars=False)
    token = env_vars.get("FABRIC_TOKEN", "") or os.getenv("FABRIC_TOKEN", "")
    if not token:
        raise ValueError(
            "Authentication failed. One of the following is required:\n"
            "  • FABRIC_TOKEN environment variable, OR\n"
            "  • Service Principal credentials: AZURE_CLIENT_ID + "
            "AZURE_CLIENT_SECRET + AZURE_TENANT_ID\n"
            "Set them in .env or export as environment variables."
        )

    fabric = FabricCLIWrapper(token)
    slug = project_slug or _slugify(workspace_name)

    # ── 2. Verify workspace exists ──
    print(f"\n🔍 Scanning workspace '{workspace_name}'...")
    workspace_id = fabric.get_workspace_id(workspace_name)
    if not workspace_id:
        raise ValueError(
            f"Workspace '{workspace_name}' not found. "
            "Check the name and your Service Principal access permissions."
        )
    print(f"   Workspace ID: {workspace_id}")

    # ── 3. List folders ──
    print("   Discovering folders...")
    raw_folders = _get_workspace_folders(fabric, workspace_name)
    folder_names = [f["displayName"] for f in raw_folders]
    if folder_names:
        print(f"   Found {len(folder_names)} folders: {', '.join(folder_names)}")
    else:
        print("   No folders found — will use default medallion structure.")
        folder_names = DEFAULT_FOLDERS.copy()

    # ── 4. List items ──
    print("   Discovering items...")
    items = fabric.list_workspace_items_api(workspace_name)
    items_by_type = _categorize_items(items)
    total_items = len(items)
    print(f"   Found {total_items} items across {len(items_by_type)} types:")
    for item_type, type_items in sorted(items_by_type.items()):
        print(f"     {item_type}: {len(type_items)}")

    # ── 5. Infer folder rules from discovered types ──
    folder_rules = _build_folder_rules(items, folders=raw_folders)

    # ── 5b. Discover principals (role assignments) ──
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
        print("   No role assignments discovered — using placeholder principals.")

    # ── 5c. Check git_directory conflicts ──
    if output_path:
        check_path = Path(output_path)
    else:
        check_path = Path(f"config/projects/_templates/{slug}/base_workspace.yaml")
    conflict = _check_git_directory_conflicts(slug, check_path)
    if conflict:
        print(f"\n⚠️  WARNING: git_directory '/{slug}' is already used in: {conflict}")
        print(
            "   Consider using --project-slug to set a unique slug, "
            "or update the existing config."
        )

    # ── 6. Generate base_workspace.yaml ──
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
    )

    if output_path:
        base_path = Path(output_path).resolve()
    else:
        base_path = Path(
            f"config/projects/_templates/{slug}/base_workspace.yaml"
        ).resolve()

    # Validate output path — guard against writing outside the project tree
    cwd = Path.cwd().resolve()
    if not str(base_path).startswith(str(cwd)):
        raise SystemExit(
            f"Error: output path '{base_path}' is outside the project "
            f"directory '{cwd}'. Use a relative path or one within the "
            f"project tree."
        )

    base_path.parent.mkdir(parents=True, exist_ok=True)
    base_path.write_text(base_yaml, encoding="utf-8")
    print(f"\n✅ Generated: {base_path}")
    results[str(base_path)] = "ok"

    # ── 7. Generate feature_workspace.yaml (optional) ──
    if include_feature_template:
        feature_yaml = _generate_feature_yaml(
            workspace_name=workspace_name,
            folders=folder_names,
            project_slug=slug,
        )
        feature_path = base_path.parent / "feature_workspace.yaml"
        feature_path.write_text(feature_yaml, encoding="utf-8")
        print(f"✅ Generated: {feature_path}")
        results[str(feature_path)] = "ok"

    # ── 8. Summary ──
    print("\n📋 Scaffold Summary:")
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
        print(f"   ⚠️  git_directory conflict: {conflict}")
    print(f"   Output:       {base_path.parent}/")
    print()
    print("⚠️  Next steps:")
    print("   1. Review the generated YAML template and adjust as needed")
    if discovered_principals:
        print(
            "   2. Replace literal principal IDs with env var "
            "references (${...}) for portability"
        )
        step = 3
    else:
        step = 2
    print(f"   {step}. Copy template to a project config:")
    print(
        f"      cp -r config/projects/_templates/{slug}/ "
        f"config/projects/<project_slug>/"
    )
    print(
        f"      — or use: make new-project project=<slug> "
        f'display="<Name>" template={slug}'
    )
    print(f"   {step + 1}. Add required secrets to GitHub")
    print(
        f"   {step + 2}. "
        "Add project to workflow dropdown (feature-workspace-create.yml)"
    )
    print(f"   {step + 3}. " "Run: fabric-cicd deploy <config>.yaml --env dev")
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
        help="Also generate a feature_workspace.yaml template",
    )
    parser.add_argument(
        "--pipeline-name",
        "-p",
        default=None,
        help="Include deployment_pipeline section with this pipeline name",
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
        )
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
