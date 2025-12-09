#!/usr/bin/env python3
"""
Azure DevOps Access Diagnostic Tool

Diagnoses Service Principal access to Azure DevOps repositories.
Checks if the SP can list repositories and branches in a project.

Usage:
    python scripts/utilities/debug_ado_access.py --organization <org> --project <proj>
"""

import sys
import logging
import requests
from pathlib import Path
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

app = typer.Typer(help="Diagnose Azure DevOps Access for Service Principal")

@app.command()
def main(
    organization: str = typer.Option(..., help="Azure DevOps Organization name"),
    project: str = typer.Option(..., help="Azure DevOps Project name"),
):
    """
    Check if Service Principal has access to Azure DevOps project.
    """
    try:
        # Load secrets
        secrets = FabricSecrets.load_with_fallback()
        
        if not secrets.validate_service_principal():
            console.print("[red]Error: Service Principal credentials missing in .env[/red]")
            raise typer.Exit(1)

        console.print(f"Checking ADO access for Client ID: {secrets.azure_client_id}")
        console.print(f"Tenant ID: {secrets.get_tenant_id()}")

        # Get token
        console.print("[blue]Acquiring access token for Azure DevOps...[/blue]")
        credential = ClientSecretCredential(
            tenant_id=secrets.get_tenant_id(),
            client_id=secrets.azure_client_id,
            client_secret=secrets.azure_client_secret
        )
        token = credential.get_token("499b84ac-1321-427f-aa17-267ca6975798/.default").token
        console.print("[green]Successfully acquired access token.[/green]")
        
        # Test ADO API
        url = f"https://dev.azure.com/{organization}/{project}/_apis/git/repositories?api-version=7.1"
        
        console.print(f"[blue]Testing access to: {url}[/blue]")
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            console.print("[green]✅ SUCCESS: Service Principal can access Azure DevOps repositories.[/green]")
            repos = response.json().get("value", [])
            console.print(f"Found {len(repos)} repositories:")
            for repo in repos:
                console.print(f" - {repo['name']} (ID: {repo['id']})")
                
                # List branches for this repo
                refs_url = f"https://dev.azure.com/{organization}/{project}/_apis/git/repositories/{repo['id']}/refs?filter=heads/&api-version=7.1"
                console.print(f"   Checking branches: {refs_url}")
                refs_response = requests.get(refs_url, headers=headers)
                if refs_response.status_code == 200:
                    refs = refs_response.json().get("value", [])
                    console.print(f"   Found {len(refs)} branches:")
                    for ref in refs:
                        console.print(f"     - {ref['name']}")
                else:
                    console.print(f"   [red]❌ Failed to list branches: {refs_response.status_code}[/red]")
        else:
            console.print(f"[red]❌ FAILED: Service Principal cannot access Azure DevOps. Status Code: {response.status_code}[/red]")
            console.print(f"Response: {response.text}")
            console.print("\nPossible causes:")
            console.print("1. Service Principal is not added to the Organization.")
            console.print("2. Service Principal access level is 'Stakeholder' instead of 'Basic'.")
            console.print("3. Service Principal is not in the 'Contributors' group of the Project.")
            console.print("4. 'Third-party application access via OAuth' policy is disabled in Organization Settings.")

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
