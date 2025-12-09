#!/usr/bin/env python3
"""
Fabric Connection Diagnostic Tool

Diagnoses issues with creating Git connections in Microsoft Fabric.
Attempts to create a connection using the Fabric REST API directly.

Usage:
    python scripts/utilities/debug_connection.py --repo-url <url>
"""

import sys
import logging
import requests
import json
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

app = typer.Typer(help="Diagnose Fabric Git Connection Creation")

@app.command()
def main(
    repo_url: str = typer.Option(..., help="Git Repository URL"),
):
    """
    Attempt to create a Git connection in Fabric to diagnose issues.
    """
    try:
        # Load secrets
        secrets = FabricSecrets.load_with_fallback()
        
        if not secrets.validate_service_principal():
            console.print("[red]Error: Service Principal credentials missing in .env[/red]")
            raise typer.Exit(1)

        console.print(f"Client ID: {secrets.azure_client_id}")
        console.print(f"Tenant ID: {secrets.get_tenant_id()}")

        # Get Fabric Token
        console.print("[blue]Acquiring Fabric access token...[/blue]")
        credential = ClientSecretCredential(
            tenant_id=secrets.get_tenant_id(),
            client_id=secrets.azure_client_id,
            client_secret=secrets.azure_client_secret
        )
        token = credential.get_token("https://api.fabric.microsoft.com/.default").token
        console.print(f"[green]Token acquired: {bool(token)}[/green]")

        url = "https://api.fabric.microsoft.com/v1/connections"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        body = {
            "displayName": "Debug-ADO-Connection-Script",
            "connectivityType": "ShareableCloud",
            "connectionDetails": {
                "type": "AzureDevOpsSourceControl",
                "creationMethod": "AzureDevOpsSourceControl.Contents",
                "parameters": [
                    {
                        "dataType": "Text",
                        "name": "url",
                        "value": repo_url
                    }
                ]
            },
            "credentialDetails": {
                "credentials": {
                    "credentialType": "ServicePrincipal",
                    "tenantId": secrets.get_tenant_id(),
                    "servicePrincipalClientId": secrets.azure_client_id,
                    "servicePrincipalSecret": secrets.azure_client_secret
                }
            }
        }

        console.print("[blue]Sending request to create connection...[/blue]")
        response = requests.post(url, headers=headers, json=body)

        console.print(f"Status Code: {response.status_code}")
        console.print(f"Response: {response.text}")
        
        if response.status_code in [200, 201]:
             console.print("[green]✅ Connection created successfully.[/green]")
        elif response.status_code == 409:
             console.print("[yellow]⚠️  Connection already exists (Conflict). This is expected if you ran this before.[/yellow]")
        else:
             console.print("[red]❌ Failed to create connection.[/red]")

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
