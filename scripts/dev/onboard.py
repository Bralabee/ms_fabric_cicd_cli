#!/usr/bin/env python3
"""
Unified Onboarding Automation for Fabric Data Products.

Orchestrates:
1. Config Generation (via generate_project.py)
2. Git Feature Branch Creation
3. Fabric Workspace Deployment
"""

import argparse
import subprocess
import sys
import logging
from pathlib import Path

# Add src to path for imports if needed
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "src"))

try:
    from generate_project import generate_project_config
except ImportError:
    # Handle import if running from different cwd
    sys.path.append(str(Path(__file__).resolve().parent))
    from generate_project import generate_project_config

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("onboard")


def run_command(command, cwd=None, check=True):
    """Run shell command with logging"""
    cmd_str = " ".join(command)
    logger.info(f"▶ Running: {cmd_str}")
    try:
        result = subprocess.run(
            command, cwd=cwd, check=check, text=True, capture_output=True
        )
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Command failed: {e.stderr}")
        raise


def onboard_project(
    org_name: str,
    project_name: str,
    template: str,
    capacity_id: str,
    git_repo: str = None,
    dry_run: bool = False,
):
    """Execute end-to-end onboarding workflow"""

    logger.info(f"🚀 Starting onboarding for {org_name} / {project_name}")
    logger.info(f"📋 Template: {template}")

    # 1. Generate Configuration
    logger.info("\n[1/3] Generating Configuration...")
    try:
        if dry_run:
            logger.info("  (Dry Run) calling generate_project_config...")
            # Simulate path
            org_slug = org_name.lower().replace(" ", "_")
            project_slug = project_name.lower().replace(" ", "_")
            config_path = Path(f"config/projects/{org_slug}/{project_slug}.yaml")
        else:
            config_path = generate_project_config(
                org_name, project_name, template, capacity_id, git_repo
            )
    except Exception as e:
        logger.error(f"Failed to generate config: {e}")
        return False

    # 2. Create Feature Branch
    logger.info("\n[2/3] Initializing Git Feature Branch...")
    branch_name = f"feature/{project_name.lower().replace(' ', '-')}"

    if dry_run:
        logger.info(f"  (Dry Run) Would execute: git checkout -b {branch_name}")
    else:
        try:
            # Check if branch exists
            result = run_command(["git", "branch", "--list", branch_name], check=False)
            if branch_name in result.stdout:
                logger.warning(
                    f"  Branch {branch_name} already exists. Checking out..."
                )
                run_command(["git", "checkout", branch_name])
            else:
                run_command(["git", "checkout", "-b", branch_name])

            logger.info(f"  ✅ On branch: {branch_name}")

            # Push branch to remote (Required for Fabric to see it)
            logger.info("  ☁️  Pushing branch to remote...")
            run_command(["git", "push", "-u", "origin", branch_name])
            logger.info("  ✅ Branch pushed to origin")

        except Exception as e:
            logger.error(f"Failed to manage git branch: {e}")
            return False

    # 3. Deploy Workspace
    logger.info("\n[3/3] Deploying Fabric Workspace...")
    deploy_cmd = [
        "python3",
        "-m",
        "usf_fabric_cli.cli",
        "deploy",
        str(config_path),
        "--env",
        "dev",
        "--branch",
        branch_name,
        "--force-branch-workspace",
    ]

    if dry_run:
        logger.info(f"  (Dry Run) Would execute: {' '.join(deploy_cmd)}")
        return True

    try:
        # Set PYTHONPATH to include src
        env = {"PYTHONPATH": str(Path(__file__).resolve().parent.parent.parent / "src")}
        # Also include current env vars
        import os

        env.update(os.environ)

        # Run deploy interactively to show progress
        subprocess.run(deploy_cmd, env=env, check=True)

        logger.info("\n✨ Onboarding Complete! ✨")
        logger.info(f"Resource: {config_path}")
        logger.info(f"Branch:   {branch_name}")
        return True

    except subprocess.CalledProcessError:
        logger.error("❌ Deployment failed.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Onboard a new Fabric Data Product")
    parser.add_argument("--org", required=True, help="Organization Name")
    parser.add_argument("--project", required=True, help="Project Name")
    parser.add_argument(
        "--template",
        default="medallion",
        help="Blueprint template (default: medallion)",
    )
    parser.add_argument(
        "--capacity-id", default="${FABRIC_CAPACITY_ID}", help="Capacity ID placeholder"
    )
    parser.add_argument(
        "--repo", default="${GIT_REPO_URL}", help="Git Repo URL placeholder"
    )
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions")

    args = parser.parse_args()

    success = onboard_project(
        args.org,
        args.project,
        args.template,
        args.capacity_id,
        args.repo,
        args.dry_run,
    )

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
