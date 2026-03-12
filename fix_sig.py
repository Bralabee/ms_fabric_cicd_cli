import sys
import re

file_path = "/home/sanmi/Documents/J'TOYE_DIGITAL/LEIT_TEKSYSTEMS/1_Project_Rhico/usf_fabric_cli_cicd/src/usf_fabric_cli/scripts/admin/utilities/scaffold_workspace.py"

with open(file_path, "r") as f:
    text = f.read()

bad_sig = """    test_workspace_name: Optional[str] = None,
    prod_workspace_name: Optional[str] = None,
    templatise: bool = False,
    git_branch: str = "main",
    git_directory: Optional[str] = None,
    git_repo_fallback: str = "${GIT_REPO_URL}",
) -> Dict[str, str]:
    \"\"\"Scaffold YAML config(s) from a live Fabric workspace."""

good_sig = """    test_workspace_name: Optional[str] = None,
    prod_workspace_name: Optional[str] = None,
    templatise: bool = False,
) -> Dict[str, str]:
    \"\"\"Scaffold YAML config(s) from a live Fabric workspace."""

if bad_sig in text:
    text = text.replace(bad_sig, good_sig)
    with open(file_path, "w") as f:
        f.write(text)
    print("Fixed bad sig")
else:
    print("Not found")

