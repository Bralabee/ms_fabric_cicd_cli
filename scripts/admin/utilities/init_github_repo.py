#!/usr/bin/env python3
"""
GitHub Repository Initializer

Creates and initializes a GitHub repository with a default branch
and README for Fabric Git integration.

Mirrors the Azure DevOps equivalent (init_ado_repo.py) so that
both providers offer identical lifecycle management.

Usage:
    python scripts/admin/utilities/init_github_repo.py \
        --owner BralaBee-LEIT --repo finance-analytics

Requires:
    GITHUB_TOKEN environment variable (PAT with ``repo`` scope).
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

import requests
import typer
from rich.console import Console

# Add project root for sibling imports
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(project_root))

# ---------------------------------------------------------------------------
# Logging / UI
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
console = Console()

app = typer.Typer(help="Create & initialize a GitHub repository for Fabric integration")

GITHUB_API = "https://api.github.com"


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_repo(
    owner: str,
    repo_name: str,
    token: str,
) -> Optional[Dict[str, Any]]:
    """Return repo metadata or *None* if it does not exist."""
    url = f"{GITHUB_API}/repos/{owner}/{repo_name}"
    resp = requests.get(url, headers=_headers(token), timeout=30)
    if resp.status_code == 200:
        return resp.json()
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return None  # unreachable, keeps mypy happy


def create_repo(
    owner: str,
    repo_name: str,
    token: str,
    *,
    private: bool = True,
    description: str = "",
    auto_init: bool = True,
) -> Dict[str, Any]:
    """Create a GitHub repository (user or org).

    When *auto_init* is ``True`` (the default) GitHub creates the
    default branch with an initial commit containing a README — this
    is required because Fabric's Git-connect API expects an existing
    branch.

    Returns the full repo JSON from the GitHub API.
    """
    # Detect whether *owner* is the authenticated user or an org
    user_resp = requests.get(
        f"{GITHUB_API}/user",
        headers=_headers(token),
        timeout=30,
    )
    user_resp.raise_for_status()
    authenticated_user = user_resp.json().get("login", "")

    if owner.lower() == authenticated_user.lower():
        url = f"{GITHUB_API}/user/repos"
    else:
        url = f"{GITHUB_API}/orgs/{owner}/repos"

    body: Dict[str, Any] = {
        "name": repo_name,
        "description": description
        or ("Fabric data-product repo – " "provisioned by usf-fabric-cli"),
        "private": private,
        "auto_init": auto_init,
    }

    console.print(f"[blue]Creating GitHub repo " f"'{owner}/{repo_name}' …[/blue]")
    resp = requests.post(
        url,
        headers=_headers(token),
        json=body,
        timeout=30,
    )

    if resp.status_code == 201:
        data = resp.json()
        console.print(f"[green]✅ Created: {data['html_url']}[/green]")
        return data

    if resp.status_code == 422:
        # 422 usually means the repo already exists
        err = resp.json()
        errors = err.get("errors", [])
        if any(
            e.get("message") == "name already exists on " "this account" for e in errors
        ):
            console.print(
                f"[yellow]⚠️  Repo '{owner}/{repo_name}' " f"already exists.[/yellow]"
            )
            existing = get_repo(owner, repo_name, token)
            if existing:
                return existing
        # Re-raise if it's a different 422
        resp.raise_for_status()

    resp.raise_for_status()
    return {}  # unreachable


def ensure_branch(
    owner: str,
    repo_name: str,
    branch: str,
    token: str,
) -> bool:
    """Ensure *branch* exists; create from default branch if not.

    Returns ``True`` if the branch exists (or was created).
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo_name}" f"/branches/{branch}"
    resp = requests.get(
        url,
        headers=_headers(token),
        timeout=30,
    )
    if resp.status_code == 200:
        console.print(f"[green]✓ Branch '{branch}' already exists[/green]")
        return True

    if resp.status_code != 404:
        resp.raise_for_status()

    # Branch doesn't exist — create it from the default branch HEAD
    console.print(f"[blue]Creating branch '{branch}' …[/blue]")
    # Get default-branch SHA
    repo_info = get_repo(owner, repo_name, token)
    if not repo_info:
        console.print("[red]Repo not found[/red]")
        return False

    default_branch = repo_info.get("default_branch", "main")
    ref_url = (
        f"{GITHUB_API}/repos/{owner}/{repo_name}" f"/git/ref/heads/{default_branch}"
    )
    ref_resp = requests.get(
        ref_url,
        headers=_headers(token),
        timeout=30,
    )
    ref_resp.raise_for_status()
    sha = ref_resp.json()["object"]["sha"]

    create_url = f"{GITHUB_API}/repos/{owner}/{repo_name}/git/refs"
    create_body = {
        "ref": f"refs/heads/{branch}",
        "sha": sha,
    }
    create_resp = requests.post(
        create_url,
        headers=_headers(token),
        json=create_body,
        timeout=30,
    )
    if create_resp.status_code in (201, 200):
        console.print(f"[green]✅ Branch '{branch}' created[/green]")
        return True

    create_resp.raise_for_status()
    return False


def get_clone_url(
    owner: str,
    repo_name: str,
    token: str,
) -> Optional[str]:
    """Return the HTTPS clone URL for a repo."""
    repo = get_repo(owner, repo_name, token)
    if repo:
        return repo.get("clone_url")
    return None


# ---------------------------------------------------------------------------
# Public orchestration function (called by onboard.py)
# ---------------------------------------------------------------------------


def init_github_repo(
    owner: str,
    repo_name: str,
    token: str,
    *,
    branch: str = "main",
    private: bool = True,
    description: str = "",
) -> Optional[str]:
    """Create repo, ensure branch exists, return clone URL.

    This is the main entry-point used by ``onboard.py`` when
    ``--create-repo --git-provider github`` is specified.

    Returns:
        HTTPS clone URL on success, ``None`` on failure.
    """
    try:
        create_repo(
            owner,
            repo_name,
            token,
            private=private,
            description=description,
        )
        ensure_branch(owner, repo_name, branch, token)
        clone_url = get_clone_url(owner, repo_name, token)
        return clone_url
    except Exception as exc:
        console.print(f"[red]GitHub repo init failed: {exc}[/red]")
        logger.error("init_github_repo error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@app.command()
def main(
    owner: str = typer.Option(
        ...,
        help="GitHub user or organization name",
    ),
    repo: str = typer.Option(
        ...,
        help="Repository name to create",
    ),
    branch: str = typer.Option(
        "main",
        help="Branch to ensure exists",
    ),
    private: bool = typer.Option(
        True,
        help="Create as private repository",
    ),
):
    """
    Create and initialize a GitHub repository for Fabric
    Git integration.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        console.print("[red]GITHUB_TOKEN environment variable " "is required[/red]")
        raise typer.Exit(1)

    url = init_github_repo(
        owner,
        repo,
        token,
        branch=branch,
        private=private,
    )
    if url:
        console.print(f"\n[bold green]Clone URL:[/bold green] {url}")
    else:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
