#!/usr/bin/env python3
"""
Quick project generator — creates customized configuration for your organization.

Templates use the git-sync-only convention:
  - Fabric items (notebooks, lakehouses, etc.) are managed through Git Sync
  - CLI manages workspace structure, folders, access control, deployment pipelines
  - Principals use environment variable GUIDs (not email addresses)
"""

import argparse
from importlib.resources import files
from pathlib import Path
from typing import Optional

import yaml


def generate_project_config(
    org_name: str,
    project_name: str,
    template: str,
    capacity_id: str,
    git_repo: Optional[str] = None,
):
    """Generate customized project configuration from a blueprint template.

    The template is loaded, workspace names are customized for the organization,
    and the deployment pipeline stages are updated to match. Principals remain
    as environment variable references — configure them in .env or CI/CD secrets.
    """

    # Load base template
    template_path = files("usf_fabric_cli.templates.blueprints") / f"{template}.yaml"
    if not template_path.is_file():
        raise ValueError(f"Template '{template}' not found")

    with template_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Derive workspace name from org + project
    org_slug = org_name.lower().replace(" ", "_")
    project_slug = project_name.lower().replace(" ", "_")
    workspace_name = f"{org_slug}-{project_slug}".replace("_", "-")

    # ── Customize workspace section ──────────────────────────────────────
    config["workspace"]["name"] = workspace_name
    config["workspace"]["display_name"] = f"{org_name} {project_name}"
    config["workspace"]["capacity_id"] = capacity_id

    if git_repo:
        config["workspace"]["git_repo"] = git_repo

    # ── Update environment overrides (if present) ────────────────────────
    if "environments" in config:
        for env_name, env_config in config["environments"].items():
            if "workspace" in env_config:
                if env_name == "dev":
                    env_config["workspace"]["name"] = workspace_name
                if "capacity_id" in env_config["workspace"]:
                    env_config["workspace"]["capacity_id"] = capacity_id

    # ── Customize deployment pipeline (if present in template) ───────────
    if "deployment_pipeline" in config:
        pipeline = config["deployment_pipeline"]
        pipeline["pipeline_name"] = f"{org_name}-{project_name} Pipeline"

        if "stages" in pipeline:
            stages = pipeline["stages"]
            if "development" in stages:
                stages["development"]["workspace_name"] = workspace_name
            if "test" in stages:
                stages["test"]["workspace_name"] = f"{workspace_name} [Test]"
            if "production" in stages:
                stages["production"][
                    "workspace_name"
                ] = f"{workspace_name} [Production]"
    else:
        # Template lacks deployment_pipeline — add default 3-stage pipeline
        config["deployment_pipeline"] = {
            "pipeline_name": f"{org_name}-{project_name} Pipeline",
            "stages": {
                "development": {
                    "workspace_name": workspace_name,
                    "capacity_id": "${FABRIC_CAPACITY_ID}",
                },
                "test": {
                    "workspace_name": f"{workspace_name} [Test]",
                    "capacity_id": "${FABRIC_CAPACITY_ID}",
                },
                "production": {
                    "workspace_name": f"{workspace_name} [Production]",
                    "capacity_id": "${FABRIC_CAPACITY_ID}",
                },
            },
        }

    # ── Save customized config ───────────────────────────────────────────
    output_dir = Path(f"config/projects/{org_slug}")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{project_slug}.yaml"
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, indent=2, sort_keys=False)

    print(f"✅ Generated configuration: {output_path}")
    print("📝 Next steps:")
    print(f"   1. Review and edit: {output_path}")
    print("   2. Set secret env vars in .env (see template ← CHANGE markers)")
    print(f"   3. Validate: make validate config={output_path}")
    print(f"   4. Deploy:   make deploy config={output_path} env=dev")

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate customized project configuration"
    )
    parser.add_argument("org_name", help="Organization name (e.g., 'Contoso Inc')")
    parser.add_argument(
        "project_name", help="Project name (e.g., 'Customer Analytics')"
    )
    parser.add_argument(
        "--template",
        default="basic_etl",
        choices=[
            "basic_etl",
            "advanced_analytics",
            "data_science",
            "extensive_example",
            "medallion",
            "realtime_streaming",
            "minimal_starter",
            "compliance_regulated",
            "data_mesh_domain",
            "migration_hybrid",
            "specialized_timeseries",
        ],
        help="Configuration template to use",
    )
    parser.add_argument(
        "--capacity-id",
        default="${FABRIC_CAPACITY_ID}",
        help="Fabric capacity ID (defaults to ${FABRIC_CAPACITY_ID})",
    )
    parser.add_argument(
        "--git-repo",
        default="${GIT_REPO_URL}",
        help="Git repository URL (defaults to ${GIT_REPO_URL})",
    )

    args = parser.parse_args()

    try:
        generate_project_config(
            args.org_name,
            args.project_name,
            args.template,
            args.capacity_id,
            args.git_repo,
        )
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
