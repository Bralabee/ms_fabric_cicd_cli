"""Pre-flight validation for Fabric CLI deployments."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv

REQUIRED_ENV_VARS = ["FABRIC_TOKEN", "TENANT_ID"]


def _install_fabric_cli() -> None:
    cmd: List[str] = [sys.executable, "-m", "pip", "install", "fabric-cli"]
    subprocess.check_call(cmd)


def _ensure_env_loaded() -> None:
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)


def _validate_auth_vars() -> List[str]:
    """Check for valid authentication configuration (Token OR Service Principal)."""
    # Check 1: Direct Token
    if os.getenv("FABRIC_TOKEN"):
        return []

    # Check 2: Service Principal
    sp_vars = ["AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"]
    missing_sp = [var for var in sp_vars if not os.getenv(var)]

    # Tenant ID can be TENANT_ID or AZURE_TENANT_ID
    if not (os.getenv("TENANT_ID") or os.getenv("AZURE_TENANT_ID")):
        missing_sp.append("TENANT_ID (or AZURE_TENANT_ID)")

    if not missing_sp:
        return []

    return ["FABRIC_TOKEN"] + missing_sp


def run_preflight(auto_install: bool, skip_env: bool) -> int:
    _ensure_env_loaded()

    cli_path = shutil.which("fab")
    if not cli_path:
        if auto_install:
            print("Fabric CLI not found. Attempting automatic installation via pip...")
            _install_fabric_cli()
            cli_path = shutil.which("fab")
        if not cli_path:
            print(
                "❌ Fabric CLI binary is not available on PATH. See https://github.com/microsoft/fabric-cli for manual steps."
            )
            return 1

    print(f"✅ Fabric CLI detected at {cli_path}")
    version = subprocess.check_output(["fab", "--version"], text=True).strip()
    print(f"   Version: {version}")

    if skip_env:
        print("ℹ️  Skipping environment variable validation per flag")
    else:
        missing = _validate_auth_vars()
        if missing:
            # If we have missing vars, it means NEITHER method was fully complete.
            # We'll report that we couldn't find a complete set for either method.
            print("⚠️  Missing required environment variables for authentication.")
            print("    You must provide EITHER:")
            print("      1. FABRIC_TOKEN")
            print("    OR")
            print(
                "      2. AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, and TENANT_ID/AZURE_TENANT_ID"
            )
            print(
                "    Create or update your .env file and rerun. Example entries are available in .env.template."
            )
            return 1
        print("✅ Required environment variables detected")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Fabric CLI preflight checks")
    parser.add_argument(
        "--auto-install",
        action="store_true",
        help="Automatically install fabric-cli with pip when missing",
    )
    parser.add_argument(
        "--skip-env-check",
        action="store_true",
        help="Skip validation of required environment variables",
    )
    args = parser.parse_args()

    exit_code = run_preflight(
        auto_install=args.auto_install, skip_env=args.skip_env_check
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
