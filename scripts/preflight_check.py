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


def run_preflight(auto_install: bool, skip_env: bool) -> int:
    _ensure_env_loaded()

    cli_path = shutil.which("fabric")
    if not cli_path:
        if auto_install:
            print("Fabric CLI not found. Attempting automatic installation via pip...")
            _install_fabric_cli()
            cli_path = shutil.which("fabric")
        if not cli_path:
            print("❌ Fabric CLI binary is not available on PATH. See https://github.com/microsoft/fabric-cli for manual steps.")
            return 1

    print(f"✅ Fabric CLI detected at {cli_path}")
    version = subprocess.check_output(["fabric", "--version"], text=True).strip()
    print(f"   Version: {version}")

    if skip_env:
        print("ℹ️  Skipping environment variable validation per flag")
    else:
        missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
        if missing:
            print("⚠️  Missing required environment variables:", ", ".join(missing))
            print("    Create or update your .env file and rerun. Example entries are available in .env.template.")
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

    exit_code = run_preflight(auto_install=args.auto_install, skip_env=args.skip_env_check)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
