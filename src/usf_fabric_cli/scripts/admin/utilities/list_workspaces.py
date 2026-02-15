#!/usr/bin/env python3
"""
List Workspaces Utility.

Lists all Fabric workspaces accessible with current credentials.

Usage:
    python -m usf_fabric_cli.scripts.admin.utilities.list_workspaces
"""

import json

from usf_fabric_cli.services.fabric_wrapper import FabricCLIWrapper
from usf_fabric_cli.utils.config import get_environment_variables


def list_workspaces() -> None:
    """List all accessible Fabric workspaces."""
    try:
        env_vars = get_environment_variables()
        token = env_vars.get("FABRIC_TOKEN") or "dummy"
        wrapper = FabricCLIWrapper(token)

        print("Listing workspaces...")
        result = wrapper._execute_command(["ls", "--output_format", "json"])

        if result.get("success"):
            data = result.get("data")
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    pass
            print(json.dumps(data, indent=2))
        else:
            print(f"Error: {result.get('error')}")
            if result.get("exception"):
                print(f"Exception: {result.get('exception')}")
    except Exception as e:
        print(f"An error occurred: {e}")


def main() -> None:
    list_workspaces()


if __name__ == "__main__":
    main()
