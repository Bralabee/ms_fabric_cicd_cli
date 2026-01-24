#!/usr/bin/env python3
"""
Azure DevOps Repository Initializer

Initializes an empty Azure DevOps repository with a main branch and README.
This is required because Fabric Git integration requires an existing branch.

Usage:
    python scripts/utilities/init_ado_repo.py --organization <org> --project <proj> --repository <repo>
"""

import sys
import logging
import requests
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from azure.identity import ClientSecretCredential

# Add project root to path to allow imports from src
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.core.secrets import FabricSecrets

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
console = Console()

app = typer.Typer(help="Initialize Azure DevOps Repository for Fabric Integration")


def get_ado_token(secrets: FabricSecrets) -> str:
    """Get Azure DevOps access token using Service Principal."""
    if not secrets.validate_service_principal():
        raise ValueError(
            "Service Principal credentials (CLIENT_ID, CLIENT_SECRET, TENANT_ID) are required."
        )

    console.print("[blue]Acquiring Azure DevOps access token...[/blue]")
    credential = ClientSecretCredential(
        tenant_id=secrets.get_tenant_id(),
        client_id=secrets.azure_client_id,
        client_secret=secrets.azure_client_secret,
    )
    # Scope for Azure DevOps
    return credential.get_token("499b84ac-1321-427f-aa17-267ca6975798/.default").token


def get_repo_id(
    organization: str, project: str, repository_name: str, token: str
) -> Optional[str]:
    """Get Repository ID from name. Returns None if not found."""
    url = f"https://dev.azure.com/{organization}/{project}/_apis/git/repositories/{repository_name}?api-version=7.1"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()["id"]
    elif response.status_code == 404:
        return None
    else:
        raise Exception(f"Failed to get repository details: {response.text}")


def create_repo(
    organization: str, project: str, repository_name: str, token: str
) -> str:
    """Create a new Azure DevOps repository."""
    # Use project-level endpoint, but don't include project in body
    url = f"https://dev.azure.com/{organization}/{project}/_apis/git/repositories?api-version=7.1"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    body = {"name": repository_name}

    console.print(f"[blue]Creating repository '{repository_name}'...[/blue]")
    response = requests.post(url, headers=headers, json=body)

    if response.status_code == 201:
        return response.json()["id"]
    else:
        raise Exception(f"Failed to create repository: {response.text}")


@app.command()
def main(
    organization: str = typer.Option(..., help="Azure DevOps Organization name"),
    project: str = typer.Option(..., help="Azure DevOps Project name"),
    repository: str = typer.Option(..., help="Repository name to initialize"),
    branch: str = typer.Option("main", help="Branch name to initialize"),
):
    """
    Initialize an Azure DevOps repository with a branch.
    """
    try:
        # Load secrets using standard framework
        secrets = FabricSecrets.load_with_fallback()
        token = get_ado_token(secrets)

        # Get Repo ID
        console.print(f"[blue]Resolving repository ID for '{repository}'...[/blue]")
        repo_id = get_repo_id(organization, project, repository, token)

        if not repo_id:
            console.print(
                f"[yellow]Repository '{repository}' not found. Attempting to create it...[/yellow]"
            )
            repo_id = create_repo(organization, project, repository, token)
            console.print(f"[green]Created Repository ID: {repo_id}[/green]")
        else:
            console.print(f"[green]Found Repository ID: {repo_id}[/green]")

        # Initialize Repo/Branch
        url = f"https://dev.azure.com/{organization}/{project}/_apis/git/repositories/{repo_id}/pushes?api-version=7.1"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

        body = {
            "refUpdates": [
                {
                    "name": f"refs/heads/{branch}",
                    "oldObjectId": "0000000000000000000000000000000000000000",
                }
            ],
            "commits": [
                {
                    "comment": f"Initialize {branch} branch",
                    "changes": [
                        {
                            "changeType": "add",
                            "item": {"path": "/README.md"},
                            "newContent": {
                                "content": f"# Fabric Integration Repo\n\nInitialized by Fabric CLI CI/CD for branch {branch}",
                                "contentType": "rawtext",
                            },
                        }
                    ],
                }
            ],
        }

        console.print(f"[blue]Pushing initial commit to '{branch}'...[/blue]")
        response = requests.post(url, headers=headers, json=body)

        if response.status_code == 201:
            console.print(
                f"[green]✅ Successfully initialized branch '{branch}' in repository '{repository}'.[/green]"
            )
        elif response.status_code == 400 and "TF401021" in response.text:
            console.print(
                f"[yellow]⚠️  Branch '{branch}' already exists. Skipping initialization.[/yellow]"
            )
        else:
            console.print(
                f"[red]❌ Failed to initialize branch: {response.status_code}[/red]"
            )
            console.print(response.text)
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
