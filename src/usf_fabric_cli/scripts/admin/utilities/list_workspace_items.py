#!/usr/bin/env python3
"""
List Workspace Items Utility.

Lists all items in a specified Fabric workspace.

Usage:
    python -m usf_fabric_cli.scripts.admin.utilities.list_workspace_items \\
        "Workspace Name"
"""

import os
import sys

from usf_fabric_cli.services.fabric_wrapper import FabricCLIWrapper
from usf_fabric_cli.utils.config import get_environment_variables


def list_workspace_items(workspace_name: str) -> None:
    """List all items in the specified workspace."""
    try:
        env_vars = get_environment_variables()
        token = env_vars.get("FABRIC_TOKEN", "")
        if not token:
            token = os.getenv("FABRIC_TOKEN", "")

        if not token:
            print(
                "Error: FABRIC_TOKEN is not set. Please set it in .env "
                "or export it as an environment variable."
            )
            sys.exit(1)

        fabric = FabricCLIWrapper(token)
        print(f"Listing items in workspace '{workspace_name}'...")

        result = fabric.list_workspace_items(workspace_name)

        if result.get("success"):
            data = result.get("data")

            if isinstance(data, str):
                print("Raw output (not JSON):")
                print(data)
                return

            items = data or []
            print(f"Found {len(items)} items:\n")

            print(f"  {'Name':<40} {'Type':<25} {'Description'}")
            print(f"  {'─' * 40} {'─' * 25} {'─' * 30}")

            for item in items:
                name = item.get("displayName", "N/A")
                item_type = item.get("type", "N/A")
                desc = item.get("description", "")
                print(f"  {name:<40} {item_type:<25} {desc}")
        else:
            print(f"Failed to list items: {result.get('error')}")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python -m usf_fabric_cli"
            ".scripts.admin.utilities"
            ".list_workspace_items <workspace_name>"
        )
        print('   or: make list-items workspace="Name"')
        sys.exit(1)

    list_workspace_items(sys.argv[1])


if __name__ == "__main__":
    main()
