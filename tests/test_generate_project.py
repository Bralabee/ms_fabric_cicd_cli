"""Unit tests for generate_project configuration generation."""

from pathlib import Path

import pytest
import yaml

from usf_fabric_cli.scripts.dev.generate_project import generate_project_config


class TestGenerateProjectConfig:
    """Tests for the generate_project_config function."""

    def test_output_is_valid_yaml(self, tmp_path, monkeypatch):
        """Generated config should be valid YAML."""
        monkeypatch.chdir(tmp_path)

        result = generate_project_config(
            org_name="TestOrg",
            project_name="TestProject",
            template="basic_etl",
            capacity_id="test-cap-id",
        )

        assert result is not None
        output = Path(result)
        assert output.exists()
        with output.open() as f:
            parsed = yaml.safe_load(f)
        assert isinstance(parsed, dict)

    def test_deployment_pipeline_section_present(self, tmp_path, monkeypatch):
        """Generated config should include deployment_pipeline."""
        monkeypatch.chdir(tmp_path)

        result = generate_project_config(
            org_name="Org",
            project_name="Proj",
            template="basic_etl",
            capacity_id="test-cap-id",
        )

        output = Path(result)
        with output.open() as f:
            config = yaml.safe_load(f)

        assert "deployment_pipeline" in config
        pipeline = config["deployment_pipeline"]
        assert "stages" in pipeline

    def test_workspace_section_present(self, tmp_path, monkeypatch):
        """Generated config should have a workspace section."""
        monkeypatch.chdir(tmp_path)

        result = generate_project_config(
            org_name="Org",
            project_name="Proj",
            template="basic_etl",
            capacity_id="test-cap-id",
        )

        output = Path(result)
        with output.open() as f:
            config = yaml.safe_load(f)

        assert "workspace" in config
        assert "name" in config["workspace"]

    def test_org_name_in_workspace(self, tmp_path, monkeypatch):
        """Org name should appear in workspace naming."""
        monkeypatch.chdir(tmp_path)

        result = generate_project_config(
            org_name="ACME",
            project_name="DataLake",
            template="basic_etl",
            capacity_id="cap-123",
        )

        output = Path(result)
        with output.open() as f:
            config = yaml.safe_load(f)

        ws_name = config["workspace"]["name"]
        assert "acme" in ws_name.lower()


if __name__ == "__main__":
    pytest.main([__file__])
