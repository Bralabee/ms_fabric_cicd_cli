"""Integration tests for Fabric diagnostics.

These tests hit the real Fabric CLI binary to ensure the wrapper
and diagnostics layer work end-to-end. They automatically skip when
`fabric` is not available in PATH to keep CI flexible.
"""

from __future__ import annotations

import os
import shutil

import pytest

from src.core.fabric_wrapper import FabricCLIWrapper, FabricDiagnostics


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def diagnostics() -> FabricDiagnostics:
    """Provide diagnostics wired to the real Fabric CLI when available."""
    if shutil.which("fab") is None:
        pytest.skip("Fabric CLI binary not available on PATH")

    # Token isn't needed for version checks, fall back to placeholder.
    token = os.getenv("FABRIC_TOKEN", "integration-test-token")
    wrapper = FabricCLIWrapper(token)
    return FabricDiagnostics(wrapper)


def test_fabric_cli_reports_version(diagnostics: FabricDiagnostics) -> None:
    """Ensure the CLI returns a version string via diagnostics."""
    result = diagnostics.validate_fabric_cli_installation()
    assert result["success"], result
    assert isinstance(result.get("version"), str)
    assert result["version"].strip() != ""


def test_diagnostics_surface_remediation_help(diagnostics: FabricDiagnostics) -> None:
    """Introspect authentication diagnostics for actionable hints."""
    outcome = diagnostics.validate_authentication()
    # Authentication may legitimately fail in CI; assert remediation text exists.
    if not outcome["success"]:
        assert "remediation" in outcome
    else:
        assert outcome["message"].startswith("Authentication")
