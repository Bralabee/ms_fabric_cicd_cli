import sys
import re

file_path = "/home/sanmi/Documents/J'TOYE_DIGITAL/LEIT_TEKSYSTEMS/1_Project_Rhico/usf_fabric_cli_cicd/src/usf_fabric_cli/scripts/admin/utilities/scaffold_workspace.py"

with open(file_path, "r") as f:
    content = f.read()

# 1. Add imports
import_target = "from usf_fabric_cli.services.fabric_wrapper import FabricCLIWrapper"
import_addition = "from usf_fabric_cli.services.fabric_git_api import FabricGitAPI\nfrom usf_fabric_cli.services.fabric_wrapper import FabricCLIWrapper"
content = content.replace(import_target, import_addition)

# 2. Add git parameters to _generate_yaml
gen_yaml_def_old = """    test_workspace_name: Optional[str] = None,
    prod_workspace_name: Optional[str] = None,
    templatise: bool = False,"""

gen_yaml_def_new = """    test_workspace_name: Optional[str] = None,
    prod_workspace_name: Optional[str] = None,
    templatise: bool = False,
    git_branch: str = "main",
    git_directory: Optional[str] = None,
    git_repo_fallback: str = "${GIT_REPO_URL}","""

content = content.replace(gen_yaml_def_old, gen_yaml_def_new)

# 3. Use git parameters in _generate_yaml body
git_old = """    if templatise:
        ws_name = "CHANGE-ME [DEV]"
        ws_desc = "Standard data product workspace"
        git_dir = "/CHANGE-ME"
    else:
        ws_name = workspace_name
        ws_desc = f"{workspace_name} workspace -- managed by CI/CD"
        git_dir = f"/{slug}"

    # -- workspace section --
    lines.append("workspace:")
    lines.append(f'  name: "{ws_name}"')
    lines.append(f'  display_name: "{ws_name}"')
    lines.append(f'  description: "{ws_desc}"')
    lines.append("  capacity_id: ${FABRIC_CAPACITY_ID}")
    lines.append("  domain: ${FABRIC_DOMAIN_NAME}")
    lines.append("  git_repo: ${GIT_REPO_URL}")
    lines.append("  git_branch: main")
    lines.append(f"  git_directory: {git_dir}")"""

git_new = """    if templatise:
        ws_name = "CHANGE-ME [DEV]"
        ws_desc = "Standard data product workspace"
        git_dir = git_directory or "/CHANGE-ME"
    else:
        ws_name = workspace_name
        ws_desc = f"{workspace_name} workspace -- managed by CI/CD"
        git_dir = git_directory or f"/{slug}"

    # -- workspace section --
    lines.append("workspace:")
    lines.append(f'  name: "{ws_name}"')
    lines.append(f'  display_name: "{ws_name}"')
    lines.append(f'  description: "{ws_desc}"')
    lines.append("  capacity_id: ${FABRIC_CAPACITY_ID}")
    lines.append("  domain: ${FABRIC_DOMAIN_NAME}")
    lines.append(f"  git_repo: {git_repo_fallback}")
    lines.append(f"  git_branch: {git_branch}")
    lines.append(f"  git_directory: {git_dir}")"""

content = content.replace(git_old, git_new)

# 4. Integrate Git discovery into scaffold_workspace logic
scaffold_old = """    # -- 6. Generate base_workspace.yaml --
    base_yaml = _generate_yaml(
        workspace_name=workspace_name,
        folders=folders,
        items_by_type=workspace_items,
        folder_rules=folder_rules,
        pipeline_name=pipeline_name,
        project_slug=project_slug,
        discovered_principals=principals,
        test_workspace_name=test_workspace_name,
        prod_workspace_name=prod_workspace_name,
        templatise=templatise,
    )"""

scaffold_new = """    # -- 5d. Discover Git connection details --
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
                git_repo_url = f"https://dev.azure.com/{org_name}/{project_name}/_git/{repo_name}"
            elif owner_name and repo_name:
                git_repo_url = f"https://github.com/{owner_name}/{repo_name}"

            print(
                f"   Found Git connection: branch='{git_branch}', directory='{git_directory}'"
            )
        else:
            print("   No Git connection found on workspace.")
    except Exception as e:
        print(f"   Could not discover Git connection: {e}")

    # -- 6. Generate base_workspace.yaml --
    base_yaml = _generate_yaml(
        workspace_name=workspace_name,
        folders=folders,
        items_by_type=workspace_items,
        folder_rules=folder_rules,
        pipeline_name=pipeline_name,
        project_slug=project_slug,
        discovered_principals=principals,
        test_workspace_name=test_workspace_name,
        prod_workspace_name=prod_workspace_name,
        templatise=templatise,
        git_branch=git_branch,
        git_directory=git_directory,
        git_repo_fallback=git_repo_url,
    )"""

content = content.replace(scaffold_old, scaffold_new)

with open(file_path, "w") as f:
    f.write(content)

print(f"Patched successfully: {file_path}")
