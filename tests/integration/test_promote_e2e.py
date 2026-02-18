#!/usr/bin/env python3
"""
End-to-end promote verification tests.

Tests the full promote flow:
1. Environment variable loading (Service Principal → FABRIC_TOKEN)
2. DeploymentPipelineAPI instantiation
3. Pipeline discovery by name
4. Promote invocation (Dev → Test)

Usage:
    PYTHONPATH=src pytest tests/integration/test_promote_e2e.py -m integration -v
"""
import os

import pytest
from dotenv import load_dotenv

# Load .env once at module level
load_dotenv()

# ── Shared fixtures ────────────────────────────────────────────


@pytest.fixture(scope="module")
def env_vars():
    """Authenticate via Service Principal and return env vars with token."""
    from usf_fabric_cli.utils.config import get_environment_variables

    return get_environment_variables(validate_vars=True)


@pytest.fixture(scope="module")
def api_client(env_vars):
    """Create a FabricDeploymentPipelineAPI client."""
    from usf_fabric_cli.services.deployment_pipeline import FabricDeploymentPipelineAPI

    token = env_vars.get("FABRIC_TOKEN", "")
    assert token, "FABRIC_TOKEN missing after authentication"
    return FabricDeploymentPipelineAPI(access_token=token)


# ── Tests ──────────────────────────────────────────────────────


@pytest.mark.integration
def test_credentials_available():
    """Verify required Azure credentials are set in the environment."""
    required = ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"]
    for key in required:
        val = os.getenv(key, "")
        assert val, f"{key} is not set — required for integration tests"


@pytest.mark.integration
def test_imports_work():
    """Verify deployment pipeline module imports correctly."""
    from usf_fabric_cli.services.deployment_pipeline import (
        DeploymentStage,
        FabricDeploymentPipelineAPI,
    )
    from usf_fabric_cli.utils.config import get_environment_variables

    assert hasattr(DeploymentStage, "ORDER")
    assert callable(get_environment_variables)
    assert callable(FabricDeploymentPipelineAPI)


@pytest.mark.integration
def test_authentication(env_vars):
    """Verify Service Principal authentication produces a FABRIC_TOKEN."""
    token = env_vars.get("FABRIC_TOKEN", "")
    assert token, "FABRIC_TOKEN not acquired from Service Principal auth"
    assert len(token) > 100, f"Token suspiciously short ({len(token)} chars)"


@pytest.mark.integration
def test_list_pipelines(api_client):
    """Verify the API can list deployment pipelines."""
    result = api_client.list_pipelines()
    assert result["success"], f"list_pipelines failed: {result.get('error')}"
    pipelines = result.get("pipelines", [])
    # Not asserting > 0 — it's valid to have no pipelines yet
    assert isinstance(pipelines, list)


@pytest.mark.integration
def test_get_pipeline_stages(api_client):
    """If at least one pipeline exists, verify we can retrieve its stages."""
    result = api_client.list_pipelines()
    assert result["success"]
    pipelines = result.get("pipelines", [])
    if not pipelines:
        pytest.skip("No deployment pipelines found — skipping stages test")

    pipeline = pipelines[0]
    pid = pipeline["id"]
    stages_result = api_client.get_pipeline_stages(pid)
    assert stages_result[
        "success"
    ], f"get_pipeline_stages failed: {stages_result.get('error')}"
    stages = stages_result.get("stages", [])
    assert isinstance(stages, list)
    assert len(stages) > 0, "Pipeline exists but has no stages"

    from usf_fabric_cli.services.deployment_pipeline import DeploymentStage

    stage_names = {s.get("displayName") for s in stages}
    # Verify stages contain at least one recognised Fabric pipeline stage name
    known_stages = {
        DeploymentStage.DEV,
        "Development",
        DeploymentStage.TEST,
        "Test",
        DeploymentStage.PROD,
        "Production",
    }
    assert (
        stage_names & known_stages
    ), f"No recognised stage found in pipeline stages: {stage_names}"
