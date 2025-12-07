"""
Unit tests for templating engine
"""

import json
import pytest
from pathlib import Path

from src.core.templating import (
    ArtifactTemplateEngine,
    FabricArtifactTemplater
)


class TestArtifactTemplateEngine:
    """Test template engine core functionality"""
    
    def test_render_simple_string(self):
        """Test rendering simple template string"""
        engine = ArtifactTemplateEngine()
        
        template = "Hello {{ name }}!"
        variables = {"name": "World"}
        
        result = engine.render_string(template, variables)
        assert result == "Hello World!"
    
    def test_render_with_multiple_variables(self):
        """Test rendering with multiple variables"""
        engine = ArtifactTemplateEngine()
        
        template = "Environment: {{ environment }}, Capacity: {{ capacity_id }}"
        variables = {
            "environment": "prod",
            "capacity_id": "F64"
        }
        
        result = engine.render_string(template, variables)
        assert result == "Environment: prod, Capacity: F64"
    
    def test_render_with_filters(self):
        """Test rendering with Jinja2 filters"""
        engine = ArtifactTemplateEngine()
        
        template = "Upper: {{ name | upper }}, Lower: {{ name | lower }}"
        variables = {"name": "Test"}
        
        result = engine.render_string(template, variables)
        assert result == "Upper: TEST, Lower: test"
    
    def test_strict_mode_raises_on_undefined(self):
        """Test that strict mode raises error on undefined variables"""
        engine = ArtifactTemplateEngine(strict_mode=True)
        
        template = "Hello {{ undefined_var }}!"
        variables = {}
        
        with pytest.raises(ValueError, match="Undefined variable"):
            engine.render_string(template, variables)
    
    def test_validate_only_mode(self):
        """Test validation without rendering"""
        engine = ArtifactTemplateEngine()
        
        # Valid template
        valid_template = "Hello {{ name }}!"
        result = engine.render_string(valid_template, {}, validate_only=True)
        assert result is True
        
        # Invalid template
        invalid_template = "Hello {{ name"
        result = engine.render_string(invalid_template, {}, validate_only=True)
        assert result is False
    
    def test_render_json(self):
        """Test rendering JSON templates"""
        engine = ArtifactTemplateEngine()
        
        json_template = {
            "name": "{{ item_name }}",
            "environment": "{{ env }}",
            "config": {
                "capacity": "{{ capacity }}"
            }
        }
        
        variables = {
            "item_name": "MyLakehouse",
            "env": "dev",
            "capacity": "F2"
        }
        
        result = engine.render_json(json_template, variables)
        
        assert result["name"] == "MyLakehouse"
        assert result["environment"] == "dev"
        assert result["config"]["capacity"] == "F2"
    
    def test_prepare_environment_variables(self):
        """Test environment variable preparation"""
        engine = ArtifactTemplateEngine()
        
        base_vars = {
            "project": "MyProject",
            "capacity": "F2"
        }
        
        env_vars = {
            "capacity": "F64",  # Override
            "region": "eastus"  # New
        }
        
        result = engine.prepare_environment_variables("prod", base_vars, env_vars)
        
        assert result["environment"] == "prod"
        assert result["env"] == "prod"
        assert result["project"] == "MyProject"
        assert result["capacity"] == "F64"  # Should be overridden
        assert result["region"] == "eastus"
    
    def test_extract_template_variables(self):
        """Test extracting variable names from templates"""
        template = "Hello {{ name }}, your env is {{ environment }} with capacity {{ capacity_id }}"
        
        variables = ArtifactTemplateEngine.extract_template_variables(template)
        
        assert set(variables) == {"name", "environment", "capacity_id"}
    
    def test_render_file(self, tmp_path):
        """Test rendering template from file"""
        engine = ArtifactTemplateEngine()
        
        # Create template file
        template_file = tmp_path / "template.txt"
        template_file.write_text("Hello {{ name }}!")
        
        # Render
        output_file = tmp_path / "output.txt"
        result = engine.render_file(
            template_file,
            {"name": "World"},
            output_file
        )
        
        assert result == "Hello World!"
        assert output_file.read_text() == "Hello World!"


class TestFabricArtifactTemplater:
    """Test Fabric-specific artifact templating"""
    
    def test_render_notebook(self, tmp_path):
        """Test rendering a Fabric notebook"""
        templater = FabricArtifactTemplater()
        
        # Create mock notebook template
        notebook_template = {
            "cells": [
                {
                    "cell_type": "code",
                    "source": "connection_string = '{{ connection_string }}'"
                }
            ],
            "metadata": {
                "lakehouse": "{{ lakehouse_name }}"
            }
        }
        
        template_file = tmp_path / "notebook_template.json"
        with open(template_file, 'w') as f:
            json.dump(notebook_template, f)
        
        # Render
        output_file = tmp_path / "notebook.json"
        variables = {
            "connection_string": "Server=prod-db;Database=mydb",
            "lakehouse_name": "ProdLakehouse"
        }
        
        result = templater.render_notebook(template_file, variables, output_file)
        
        assert result["cells"][0]["source"] == "connection_string = 'Server=prod-db;Database=mydb'"
        assert result["metadata"]["lakehouse"] == "ProdLakehouse"
        assert output_file.exists()
    
    def test_render_lakehouse_definition(self, tmp_path):
        """Test rendering a Lakehouse definition"""
        templater = FabricArtifactTemplater()
        
        # Create mock lakehouse definition
        lakehouse_template = {
            "displayName": "{{ lakehouse_name }}",
            "description": "{{ environment }} lakehouse",
            "properties": {
                "oneLakeFilesPath": "{{ onelake_path }}"
            }
        }
        
        template_file = tmp_path / "lakehouse_template.json"
        with open(template_file, 'w') as f:
            json.dump(lakehouse_template, f)
        
        # Render
        output_file = tmp_path / "lakehouse.json"
        variables = {
            "lakehouse_name": "SalesLakehouse",
            "environment": "Production",
            "onelake_path": "/workspaces/prod/sales"
        }
        
        result = templater.render_lakehouse_definition(template_file, variables, output_file)
        
        assert result["displayName"] == "SalesLakehouse"
        assert result["description"] == "Production lakehouse"
        assert result["properties"]["oneLakeFilesPath"] == "/workspaces/prod/sales"
    
    def test_render_pipeline(self, tmp_path):
        """Test rendering a Data Pipeline"""
        templater = FabricArtifactTemplater()
        
        # Create mock pipeline template
        pipeline_template = {
            "name": "{{ pipeline_name }}",
            "activities": [
                {
                    "name": "Copy{{ environment }}",
                    "source": {
                        "connectionString": "{{ source_connection }}"
                    }
                }
            ]
        }
        
        template_file = tmp_path / "pipeline_template.json"
        with open(template_file, 'w') as f:
            json.dump(pipeline_template, f)
        
        # Render
        output_file = tmp_path / "pipeline.json"
        variables = {
            "pipeline_name": "ETL_Pipeline",
            "environment": "Prod",
            "source_connection": "server=prod-db;database=source"
        }
        
        result = templater.render_pipeline(template_file, variables, output_file)
        
        assert result["name"] == "ETL_Pipeline"
        assert result["activities"][0]["name"] == "CopyProd"
        assert result["activities"][0]["source"]["connectionString"] == "server=prod-db;database=source"
    
    def test_validate_artifact_template(self, tmp_path):
        """Test artifact template validation"""
        templater = FabricArtifactTemplater()
        
        # Create valid template
        template_file = tmp_path / "valid_template.txt"
        template_file.write_text("Hello {{ name }}, env: {{ environment }}")
        
        is_valid, errors = templater.validate_artifact_template(
            template_file,
            required_variables=["name", "environment"]
        )
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_artifact_template_missing_variables(self, tmp_path):
        """Test validation catches missing required variables"""
        templater = FabricArtifactTemplater()
        
        # Create template missing required variable
        template_file = tmp_path / "incomplete_template.txt"
        template_file.write_text("Hello {{ name }}")
        
        is_valid, errors = templater.validate_artifact_template(
            template_file,
            required_variables=["name", "environment"]  # 'environment' is missing
        )
        
        assert is_valid is False
        assert any("Missing required variables" in error for error in errors)
    
    def test_validate_artifact_template_syntax_error(self, tmp_path):
        """Test validation catches syntax errors"""
        templater = FabricArtifactTemplater()
        
        # Create template with syntax error
        template_file = tmp_path / "bad_template.txt"
        template_file.write_text("Hello {{ name")  # Missing closing braces
        
        is_valid, errors = templater.validate_artifact_template(template_file)
        
        assert is_valid is False
        assert any("Template syntax error" in error for error in errors)


class TestComplexScenarios:
    """Test complex real-world scenarios"""
    
    def test_environment_specific_connection_strings(self):
        """Test changing connection strings based on environment"""
        engine = ArtifactTemplateEngine()
        
        notebook_source = """
# Connect to database
connection_string = "{{ db_server }};Database={{ db_name }}"

# Use lakehouse
lakehouse = "{{ lakehouse_name }}"
"""
        
        # Dev environment
        dev_vars = {
            "db_server": "dev-server.database.windows.net",
            "db_name": "dev_db",
            "lakehouse_name": "DevLakehouse"
        }
        
        dev_result = engine.render_string(notebook_source, dev_vars)
        assert "dev-server.database.windows.net" in dev_result
        assert "dev_db" in dev_result
        
        # Prod environment
        prod_vars = {
            "db_server": "prod-server.database.windows.net",
            "db_name": "prod_db",
            "lakehouse_name": "ProdLakehouse"
        }
        
        prod_result = engine.render_string(notebook_source, prod_vars)
        assert "prod-server.database.windows.net" in prod_result
        assert "prod_db" in prod_result
