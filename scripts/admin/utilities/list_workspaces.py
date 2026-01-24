import os
import sys
import json

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from usf_fabric_cli.services.fabric_wrapper import FabricCLIWrapper
from usf_fabric_cli.utils.config import get_environment_variables


def list_workspaces():
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
                except:
                    pass
            print(json.dumps(data, indent=2))
        else:
            print(f"Error: {result.get('error')}")
            if result.get("exception"):
                print(f"Exception: {result.get('exception')}")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    list_workspaces()
