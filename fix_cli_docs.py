import re

filepath = "docs/01_User_Guides/10_Feature_Branch_Workspace_Guide.md"
with open(filepath, 'r') as f:
    content = f.read()

# Update mentions of vars.PROJECT_PREFIX
content = re.sub(
    r"\$\{\{ vars\.PROJECT_PREFIX \|\| [^}]+\}\}",
    "${{ inputs.project }}",
    content
)

content = re.sub(
    r"> `PROJECT_PREFIX` repository variable \(default: `fabric-cicd-demo`\)\. Set this variable in(.*?)\n",
    "> `PROJECT_PREFIX` is dynamically passed via GitHub Action inputs based on the project you are deploying.\n",
    content
)

content = re.sub(
    r"> Set `PROJECT_PREFIX`, `CLI_REPO_URL`",
    "> Set required secrets, `CLI_REPO_URL`",
    content
)

with open(filepath, 'w') as f:
    f.write(content)

print("CLI docs updated.")
