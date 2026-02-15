#!/usr/bin/env python3
"""
Quick project generator - creates customized configuration for your organization
"""

import argparse
from importlib.resources import files
from pathlib import Path

import yaml


def generate_project_config(
    org_name: str,
    project_name: str,
    template: str,
    capacity_id: str,
    git_repo: str = None,
):
    """Generate customized project configuration"""

    # Load base template
    template_path = files("usf_fabric_cli.templates.blueprints") / f"{template}.yaml"
    if not template_path.is_file():
        raise ValueError(f"Template {template} not found")

    with template_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Customize for organization
    org_slug = org_name.lower().replace(" ", "_")
    project_slug = project_name.lower().replace(" ", "_")
    workspace_name = f"{org_slug}-{project_slug}".replace("_", "-")

    config["workspace"]["name"] = workspace_name
    config["workspace"]["display_name"] = f"{org_name} {project_name}"
    config["workspace"]["capacity_id"] = capacity_id

    if git_repo:
        config["workspace"]["git_repo"] = git_repo

    # Add deployment pipeline configuration (Microsoft convention naming)
    config["deployment_pipeline"] = {
        "pipeline_name": f"{org_name}-{project_name} Pipeline",
        "stages": {
            "development": {
                "workspace_name": workspace_name,
            },
            "test": {
                "workspace_name": f"{workspace_name} [Test]",
                "capacity_id": "${TEST_CAPACITY_ID:-${FABRIC_CAPACITY_ID}}",
            },
            "production": {
                "workspace_name": f"{workspace_name} [Production]",
                "capacity_id": "${PROD_CAPACITY_ID:-${FABRIC_CAPACITY_ID}}",
            },
        },
    }

    # Update principals with organization domain
    if "principals" in config:
        org_domain = f"{org_name.lower().replace(' ', '')}.com"
        for i, principal in enumerate(config["principals"]):
            if "@yourorg.com" in principal["id"]:
                config["principals"][i]["id"] = principal["id"].replace(
                    "yourorg.com", org_domain
                )

    # Save customized config
    # Create organization directory
    output_dir = Path(f"config/projects/{org_slug}")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{project_slug}.yaml"
    with open(output_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, indent=2)

    print(f"✅ Generated configuration: {output_path}")
    print("📝 Next steps:")
    print(f"   1. Review and edit {output_path}")
    print(f"   2. Validate: make validate config={output_path}")
    print(f"   3. Deploy: make deploy config={output_path} env=dev")

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
