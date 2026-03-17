#!/usr/bin/env python3
"""
Discover folders from a live Fabric workspace and update YAML config.

Scans the workspace for folders and item placements, then updates the
project's base_workspace.yaml with any new folders and folder_rules
that aren't already present. Designed to run in CI before PR merge
so that folder changes made in feature workspaces are captured in
version-controlled config.

Usage:
    # Discover from feature workspace and update config
    fabric-cicd discover-folders \\
        config/projects/edp/base_workspace.yaml \\
        --workspace "EDP Feature-my-feature"

    # Dry-run -- show what would change without writing
    fabric-cicd discover-folders \\
        config/projects/edp/base_workspace.yaml \\
        --workspace "EDP Feature-my-feature" \\
        --dry-run

    # Auto-derive workspace name from config + branch
    fabric-cicd discover-folders \\
        config/projects/edp/base_workspace.yaml \\
        --branch feature/edp/new-reports
"""

import argparse
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)


def _load_yaml_preserving_comments(path: Path) -> Tuple[Dict[str, Any], str]:
    """Load YAML config and return both parsed dict and raw text.

    Returns the parsed config and the original file content so we can
    do targeted text-level updates that preserve comments and formatting.
    """
    raw = path.read_text(encoding="utf-8")
    config = yaml.safe_load(raw)
    return config, raw


def _get_workspace_folders_and_items(
    workspace_name: str,
) -> Tuple[List[str], List[Dict[str, str]]]:
    """Connect to Fabric and retrieve folders + item-to-folder mappings.

    Returns:
        (folder_paths, folder_rules) where folder_rules is a list of
        dicts with keys: type, folder (and optionally name).
    """
    from usf_fabric_cli.scripts.admin.utilities.scaffold_workspace import (
        _build_folder_paths,
        _build_folder_rules,
        _get_workspace_folders,
    )
    from usf_fabric_cli.services.fabric_wrapper import FabricCLIWrapper
    from usf_fabric_cli.utils.config import get_environment_variables

    env_vars = get_environment_variables(validate_vars=False)
    token = env_vars.get("FABRIC_TOKEN", "") or os.getenv("FABRIC_TOKEN", "")
    if not token:
        raise ValueError(
            "Authentication failed. Set FABRIC_TOKEN or SP credentials "
            "(AZURE_CLIENT_ID + AZURE_CLIENT_SECRET + AZURE_TENANT_ID)."
        )

    fabric = FabricCLIWrapper(token)

    # Verify workspace exists
    workspace_id = fabric.get_workspace_id(workspace_name)
    if not workspace_id:
        raise ValueError(
            f"Workspace '{workspace_name}' not found. "
            "Check the name and your access permissions."
        )

    # Get folders
    raw_folders = _get_workspace_folders(fabric, workspace_name)
    folder_paths = _build_folder_paths(raw_folders) if raw_folders else []

    # Get items and infer folder rules from actual placement
    items = fabric.list_workspace_items_api(workspace_name)
    folder_rules, _suggested = _build_folder_rules(items, folders=raw_folders)

    return folder_paths, folder_rules


def _compute_diff(
    config: Dict[str, Any],
    live_folders: List[str],
    live_rules: List[Dict[str, str]],
) -> Tuple[List[str], List[Dict[str, str]]]:
    """Compute new folders and rules not already in the config.

    Returns:
        (new_folders, new_rules) -- items to add to the YAML.
    """
    existing_folders = set(config.get("folders") or [])
    existing_rules = config.get("folder_rules") or []

    # Build a set of (type, folder) tuples for existing rules
    existing_rule_keys = set()
    for rule in existing_rules:
        key = (rule.get("type", "").lower(), rule.get("folder", "").lower())
        existing_rule_keys.add(key)

    new_folders = [f for f in live_folders if f not in existing_folders]
    new_rules = []
    for rule in live_rules:
        key = (rule.get("type", "").lower(), rule.get("folder", "").lower())
        if key not in existing_rule_keys:
            new_rules.append(rule)

    return new_folders, new_rules


def _update_yaml_file(
    path: Path,
    raw_content: str,
    new_folders: List[str],
    new_rules: List[Dict[str, str]],
) -> str:
    """Update the YAML file content with new folders and rules.

    Does targeted insertions to preserve existing comments and formatting.
    Returns the updated content string.
    """
    updated = raw_content

    # Insert new folders before the last entry in the folders: list
    if new_folders:
        # Find the last folder entry to append after it
        folder_lines = []
        for f in new_folders:
            folder_lines.append(f'  - "{f}"')
        insert_block = "\n".join(folder_lines)

        # Strategy: find the folders: section and append after the last "  - " line
        folders_match = re.search(r"(folders:\s*\n(?:\s+-\s+.*\n)*)", updated)
        if folders_match:
            existing_block = folders_match.group(1)
            updated_block = existing_block.rstrip("\n") + "\n" + insert_block + "\n"
            updated = updated.replace(existing_block, updated_block)
        else:
            # No folders section exists -- add one before folder_rules or principals
            has_rules = "folder_rules:" in updated
            insert_point = "folder_rules:" if has_rules else "principals:"
            if insert_point in updated:
                updated = updated.replace(
                    insert_point,
                    "folders:\n" + insert_block + "\n\n" + insert_point,
                )

    # Insert new folder_rules
    if new_rules:
        rule_lines = []
        for rule in new_rules:
            rule_lines.append(f'  - type: {rule["type"]}')
            rule_lines.append(f'    folder: "{rule["folder"]}"')
        insert_block = "\n".join(rule_lines)

        # Find existing folder_rules section
        rules_match = re.search(
            r"(folder_rules:\s*\n(?:\s+-\s+.*\n(?:\s+\w+:.*\n)*)*)", updated
        )
        if rules_match:
            existing_block = rules_match.group(1)
            updated_block = existing_block.rstrip("\n") + "\n" + insert_block + "\n"
            updated = updated.replace(existing_block, updated_block)
        else:
            # No folder_rules section -- add one after folders section
            folders_end = re.search(r"(folders:\s*\n(?:\s+-\s+.*\n)*)\n", updated)
            if folders_end:
                insert_after = folders_end.group(0)
                updated = updated.replace(
                    insert_after,
                    insert_after + "folder_rules:\n" + insert_block + "\n\n",
                )

    return updated


def _derive_feature_workspace_name(config: Dict[str, Any], branch: str) -> str:
    """Derive feature workspace name from config + branch.

    Delegates to GitFabricIntegration.get_workspace_name_from_branch()
    so that the naming convention matches the deploy --force-branch-workspace
    logic exactly:
      - Display names (spaces): "[F] Base Name [FEATURE-desc]"
      - Slug names (no spaces): "base-name-feature-desc"
    """
    from usf_fabric_cli.services.git_integration import GitFabricIntegration

    ws_name = config.get("workspace", {}).get("name", "")
    # Resolve env vars in name
    ws_name = re.sub(
        r"\$\{(\w+)\}",
        lambda m: os.environ.get(m.group(1), m.group(0)),
        ws_name,
    )

    return GitFabricIntegration.get_workspace_name_from_branch(ws_name, branch)


def discover_folders(
    config_path: str,
    workspace_name: Optional[str] = None,
    branch: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Discover folders from a live workspace and update the YAML config.

    Args:
        config_path: Path to base_workspace.yaml.
        workspace_name: Explicit workspace name to scan.
        branch: Feature branch name (used to derive workspace name if
            workspace_name is not provided).
        dry_run: If True, show changes without writing.

    Returns:
        Dict with new_folders, new_rules counts and details.
    """
    path = Path(config_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    config, raw_content = _load_yaml_preserving_comments(path)

    # Determine workspace to scan
    if not workspace_name:
        if not branch:
            raise ValueError(
                "Either --workspace or --branch must be provided "
                "to identify the workspace to scan."
            )
        workspace_name = _derive_feature_workspace_name(config, branch)

    print(f"Scanning workspace: {workspace_name}")
    print(f"Config file: {path}")

    # Discover live state
    live_folders, live_rules = _get_workspace_folders_and_items(workspace_name)
    print(f"Found {len(live_folders)} folders, {len(live_rules)} folder rules")

    # Compute diff
    new_folders, new_rules = _compute_diff(config, live_folders, live_rules)

    result = {
        "new_folders": len(new_folders),
        "new_rules": len(new_rules),
        "folders": new_folders,
        "rules": new_rules,
        "workspace": workspace_name,
        "config": str(path),
    }

    if not new_folders and not new_rules:
        print("No new folders or rules discovered. Config is up to date.")
        return result

    print(f"\nDiscovered {len(new_folders)} new folder(s):")
    for f in new_folders:
        print(f"  + {f}")

    print(f"\nDiscovered {len(new_rules)} new folder rule(s):")
    for r in new_rules:
        print(f"  + {r['type']} -> {r['folder']}")

    if dry_run:
        print("\n(Dry run -- no changes written)")
        return result

    # Update the YAML file
    updated_content = _update_yaml_file(path, raw_content, new_folders, new_rules)
    path.write_text(updated_content, encoding="utf-8")
    print(f"\nUpdated: {path}")

    return result


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Discover folders from a live Fabric workspace and update "
            "the project's YAML config with new folders and folder_rules."
        ),
    )
    parser.add_argument(
        "config",
        help="Path to base_workspace.yaml",
    )
    parser.add_argument(
        "--workspace",
        "-w",
        default=None,
        help="Name of the live workspace to scan",
    )
    parser.add_argument(
        "--branch",
        "-b",
        default=None,
        help=(
            "Feature branch name (used to derive workspace name "
            "if --workspace is not provided)"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing",
    )

    args = parser.parse_args()

    try:
        result = discover_folders(
            config_path=args.config,
            workspace_name=args.workspace,
            branch=args.branch,
            dry_run=args.dry_run,
        )

        # Exit code 0 = no changes, 1 = error, 2 = changes found (useful for CI)
        if result["new_folders"] or result["new_rules"]:
            if args.dry_run:
                print(
                    "\nCI hint: config needs updating. "
                    "Run without --dry-run to apply changes."
                )
            sys.exit(2)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
