
import os
import sys
import json
# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from core.fabric_wrapper import FabricCLIWrapper
from core.config import get_environment_variables

def list_items():
    try:
        env_vars = get_environment_variables()
        token = env_vars.get('FABRIC_TOKEN') or "dummy"
        wrapper = FabricCLIWrapper(token)
        
        workspace_name = "fabric-monitoring-analytics"
        print(f"Listing items in {workspace_name}...")
        result = wrapper.list_workspace_items(workspace_name)
        
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
    list_items()
