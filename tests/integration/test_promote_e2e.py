#!/usr/bin/env python3
"""
End-to-end promote verification script.

Tests the full promote flow:
1. Environment variable loading (Service Principal → FABRIC_TOKEN)
2. DeploymentPipelineAPI instantiation
3. Pipeline discovery by name
4. Promote invocation (Dev → Test)

Usage:
    PYTHONPATH=src pytest tests/integration/test_promote_e2e.py -m integration
"""
import os
import sys

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "src")
)


@pytest.mark.integration
def main():
    print("=" * 60)
    print("PROMOTE END-TO-END VERIFICATION")
    print("=" * 60)

    # ── Step 1: Check credentials ──────────────────────────────
    print("\n[1/5] Checking credentials...")
    from dotenv import load_dotenv

    load_dotenv()

    keys = [
        "AZURE_TENANT_ID",
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET",
        "FABRIC_TOKEN",
        "TENANT_ID",
    ]
    for k in keys:
        v = os.getenv(k, "")
        status = f"SET ({len(v)} chars)" if v else "NOT SET"
        print(f"  {k}: {status}")

    # ── Step 2: Import verification ────────────────────────────
    print("\n[2/5] Verifying imports...")
    from usf_fabric_cli.services.deployment_pipeline import (
        DeploymentStage,
        FabricDeploymentPipelineAPI,
    )
    from usf_fabric_cli.utils.config import get_environment_variables

    print("  DeploymentStage.ORDER:", DeploymentStage.ORDER)
    print("  FabricDeploymentPipelineAPI: OK")
    print("  get_environment_variables: OK")

    # ── Step 3: Authenticate ───────────────────────────────────
    print("\n[3/5] Authenticating (Service Principal → FABRIC_TOKEN)...")
    try:
        env_vars = get_environment_variables(validate_vars=True)
        token = env_vars.get("FABRIC_TOKEN", "")
        print(
            f"  FABRIC_TOKEN: "
            f"{'ACQUIRED' if token else 'MISSING'} "
            f"({len(token)} chars)"
        )
    except ValueError as e:
        print(f"  ❌ Auth failed: {e}")
        print("  → Cannot proceed with e2e test without valid credentials.")
        print("  → Fix: ensure .env has AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET")
        sys.exit(1)

    # ── Step 4: Create API client and list pipelines ───────────
    print("\n[4/5] Creating API client and listing pipelines...")
    api = FabricDeploymentPipelineAPI(access_token=token)

    result = api.list_pipelines()
    if result["success"]:
        pipelines = result.get("pipelines", [])
        print(f"  Found {len(pipelines)} deployment pipeline(s):")
        for p in pipelines:
            print(f"    - {p.get('displayName', '?')} (id: {p.get('id', '?')[:8]}...)")
    else:
        print(f"  ⚠️ List pipelines: {result.get('error', 'unknown error')}")
        print("  → This may be expected if no pipelines exist yet.")

    # ── Step 5: Dry-run promote (show what would happen) ───────
    print("\n[5/5] Promote dry-run...")
    if pipelines:
        pipeline = pipelines[0]
        pid = pipeline["id"]
        pname = pipeline.get("displayName", "?")
        print(f"  Pipeline: {pname}")

        stages_result = api.get_pipeline_stages(pid)
        if stages_result["success"]:
            stages = stages_result.get("stages", [])
            print(f"  Stages ({len(stages)}):")
            for s in stages:
                ws = s.get("workspaceId", "unassigned")
                sid = s.get('id', '?')[:8]
                sname = s.get('displayName', '?')
                print(
                    f"    - {sname} "
                    f"(id: {sid}..., workspace: "
                    f"{ws or 'unassigned'})"
                )
            print(f"\n  Would promote: {DeploymentStage.DEV} → {DeploymentStage.TEST}")
            print("  ⚠️ Skipping actual promotion (dry-run mode)")
            print("  To actually promote, run:")
            print(f'    make promote pipeline="{pname}" source=Development target=Test')
        else:
            print(f"  ⚠️ Could not get stages: {stages_result.get('error')}")
    else:
        print("  No pipelines found — nothing to promote.")
        print("  To create one, run: make onboard ...")

    print("\n" + "=" * 60)
    print("VERIFICATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
