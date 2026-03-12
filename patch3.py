import sys

file_path = "/home/sanmi/Documents/J'TOYE_DIGITAL/LEIT_TEKSYSTEMS/1_Project_Rhico/usf_fabric_cli_cicd/src/usf_fabric_cli/scripts/admin/utilities/scaffold_workspace.py"

with open(file_path, "r") as f:
    text = f.read()

scaffold_old = """    # -- 6. Generate base_workspace.yaml --
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
    )"""

if scaffold_old in text:
    text = text.replace(scaffold_old, scaffold_new)
    with open(file_path, "w") as f:
        f.write(text)
    print("Injected scaffolding!")
else:
    print("Could not find scaffold_old.")
