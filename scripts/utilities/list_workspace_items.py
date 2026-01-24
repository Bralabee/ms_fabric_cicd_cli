#!/usr/bin/env python3
"""
List Workspace Items Utility

Lists all items in a specified Fabric workspace.

Usage:
    python scripts/utilities/list_workspace_items.py --workspace "Workspace Name"
"""

import sys
import logging
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

# Add project root and src to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "src"))

from src.core.secrets import FabricSecrets
from src.core.fabric_wrapper import FabricCLIWrapper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
console = Console()

app = typer.Typer(help="List Fabric Workspace Items")


@app.command()
def main(
    workspace: str = typer.Option(..., help="Workspace Name or ID"),
):
    """
    List all items in the specified workspace.
    """
    try:
        # Load secrets
        secrets = FabricSecrets.load_with_fallback()

        # Ensure token is available
        import os

        if not os.getenv("FABRIC_TOKEN"):
            if secrets.fabric_token:
                os.environ["FABRIC_TOKEN"] = secrets.fabric_token
            elif secrets.azure_client_id and secrets.azure_client_secret:
                console.print("[blue]Generating Fabric token from secrets...[/blue]")
                from azure.identity import ClientSecretCredential

                cred = ClientSecretCredential(
                    tenant_id=secrets.get_tenant_id(),
                    client_id=secrets.azure_client_id,
                    client_secret=secrets.azure_client_secret,
                )
                token = cred.get_token(
                    "https://api.fabric.microsoft.com/.default"
                ).token
                os.environ["FABRIC_TOKEN"] = token

        fabric = FabricCLIWrapper(os.environ["FABRIC_TOKEN"])

        console.print(f"[blue]Listing items in workspace '{workspace}'...[/blue]")
        result = fabric.list_workspace_items(workspace)

        if result["success"]:
            data = result["data"]

            if isinstance(data, str):
                console.print("[yellow]Received raw output (not JSON):[/yellow]")
                console.print(data)
                return

            items = data
            # Handle case where data is None or empty
            if not items:
                items = []

            console.print(f"[green]Found {len(items)} items:[/green]")

            table = Table(title=f"Items in {workspace}")
            table.add_column("Name", style="cyan")
            table.add_column("Type", style="magenta")
            table.add_column("Description", style="white")

            for item in items:
                table.add_row(
                    item.get("displayName", "N/A"),
                    item.get("type", "N/A"),
                    item.get("description", ""),
                )

            console.print(table)
        else:
            console.print(f"[red]Failed to list items: {result.get('error')}[/red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
