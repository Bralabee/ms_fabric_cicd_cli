import os
import glob
import re

def update_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # 1. Update text that mentions setting PROJECT_PREFIX
    content = re.sub(
        r"Before running any workflow, set up the 7 required secrets and at least `PROJECT_PREFIX` as a repo variable.",
        "Before running any workflow, set up the required secrets. The workflow will dynamically calculate the project prefix from folder names.",
        content
    )
    
    # 2. Update Variables table containing PROJECT_PREFIX
    content = re.sub(
        r"\| `PROJECT_PREFIX` \| [^|]+ \| [^|]+ \|\n",
        "",
        content
    )
    
    # 3. Update mention of vars.PROJECT_PREFIX
    content = re.sub(
        r"\(it should be — the workflows set it via `vars\.PROJECT_PREFIX`\)",
        "(the workflows dynamically export it based on the project slug)",
        content
    )
    
    # 4. Remove instructions to set PROJECT_PREFIX manually
    content = re.sub(
        r"> \*\*💡 Quick start\*\*: If you only change one thing, set `PROJECT_PREFIX` to something.*?\n(.*?)\n(.*?)\n",
        "",
        content,
        flags=re.MULTILINE
    )
    
    # 5. Remove or replace "The `PROJECT_PREFIX` variable determines workspace naming:"
    content = content.replace(
        "The `PROJECT_PREFIX` variable determines workspace naming:",
        "The project folder's generated slug determines the `PROJECT_PREFIX` for workspace naming:"
    )

    # 6. Re-word config feature workspaces references
    content = content.replace(
        "uses the `PROJECT_PREFIX` repo variable as a naming prefix",
        "uses the dynamic `PROJECT_PREFIX` environment variable based on the project's folder slug"
    )

    with open(filepath, 'w') as f:
        f.write(content)

repo_dir = "/home/sanmi/Documents/J'TOYE_DIGITAL/LEIT_TEKSYSTEMS/1_Project_Rhico/edp_fabric_consumer_repo/EDPFabric"

files_to_check = glob.glob(f"{repo_dir}/**/*.md", recursive=True)
for file in files_to_check:
    update_file(file)

print("EDPFabric docs updated.")
