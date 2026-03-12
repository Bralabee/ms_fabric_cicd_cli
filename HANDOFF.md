# Handoff: Scaffold Workspace Git Fix

## Context
We are working in the `usf_fabric_cli_cicd` repository, specifically maintaining the `scaffold_workspace.py` utility. We previously reverted some aggressive changes and correctly injected "True Git Discovery" via the `FabricGitAPI`.

## Discovered Issues & Status
1. **Test/Prod Workspaces Not Showing / Promote Failing**: Resolved. This is expected behavior when a pipeline name isn't passed. To view them, `make scaffold ...` must be run with the `pipeline="<Name>"` parameter.
2. **Existing Principals Not in Test/Prod**: Resolved. Scaffold correctly outputs these at the ROOT of the `base_workspace.yaml` rather than duplicating them, which is the architecture standard.
3. **Feature Workspace Not Created**: Resolved. `make scaffold ...` must be run with `feature=true` to trigger this.
4. **Git Repo hardcoded to dev.azure.com (Not GitHub compatible)**: **PENDING FIX**. 

## The Pending Bug
Because the Makefile for `scaffold` automatically parses the `--templatise` flag, it generates templates that are meant to be agnostic. However, the newly injected Git Discovery logic incorrectly hardcodes the original source's Git configuration into the template output rather than templatizing it, causing cross-repo interference and disconnect/reconnect failures.

## Next Step for the Agent
1. Open `src/usf_fabric_cli/scripts/admin/utilities/scaffold_workspace.py`.
2. Locate the `_generate_yaml` function.
3. Apply a fix so that when `templatise=True`, `git_repo` evaluates to `"${GIT_REPO_URL}"` and `git_branch` evaluates to `"main"`, regardless of what was discovered by `FabricGitAPI`.
4. Ensure `black` formatting passes.
5. Create a feature branch, commit, and push per the repository guidelines.
