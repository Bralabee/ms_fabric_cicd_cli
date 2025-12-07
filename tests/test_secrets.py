"""
Unit tests for secrets management module
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core.secrets import FabricSecrets, get_secrets, get_environment_variables


class TestFabricSecrets:
    """Test secrets loading and validation"""
    
    def test_load_from_environment_variables(self, monkeypatch):
        """Test loading secrets from environment variables"""
        monkeypatch.setenv("AZURE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
        monkeypatch.setenv("TENANT_ID", "test-tenant")
        
        secrets = FabricSecrets()
        
        assert secrets.azure_client_id == "test-client-id"
        assert secrets.azure_client_secret == "test-secret"
        assert secrets.tenant_id == "test-tenant"
    
    def test_tenant_id_normalization(self, monkeypatch):
        """Test tenant ID normalization from AZURE_TENANT_ID"""
        monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant-id")
        
        secrets = FabricSecrets()
        
        # Should normalize to tenant_id
        assert secrets.get_tenant_id() == "test-tenant-id"
    
    def test_validate_fabric_auth_with_service_principal(self, monkeypatch):
        """Test validation with Service Principal credentials"""
        monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")
        monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
        monkeypatch.setenv("TENANT_ID", "test-tenant")
        
        secrets = FabricSecrets()
        is_valid, error_msg = secrets.validate_fabric_auth()
        
        assert is_valid is True
        assert error_msg == ""
    
    def test_validate_fabric_auth_with_token(self, monkeypatch):
        """Test validation with direct token"""
        monkeypatch.setenv("FABRIC_TOKEN", "test-token")
        
        secrets = FabricSecrets()
        is_valid, error_msg = secrets.validate_fabric_auth()
        
        assert is_valid is True
        assert error_msg == ""
    
    def test_validate_fabric_auth_missing_credentials(self):
        """Test validation with missing credentials"""
        secrets = FabricSecrets()
        is_valid, error_msg = secrets.validate_fabric_auth()
        
        assert is_valid is False
        assert "Missing Fabric authentication credentials" in error_msg
    
    def test_validate_git_auth_github(self, monkeypatch):
        """Test GitHub authentication validation"""
        monkeypatch.setenv("GITHUB_TOKEN", "test-github-token")
        
        secrets = FabricSecrets()
        is_valid, error_msg = secrets.validate_git_auth("github")
        
        assert is_valid is True
        assert error_msg == ""
    
    def test_validate_git_auth_azure_devops(self, monkeypatch):
        """Test Azure DevOps authentication validation"""
        monkeypatch.setenv("AZURE_DEVOPS_PAT", "test-ado-pat")
        
        secrets = FabricSecrets()
        is_valid, error_msg = secrets.validate_git_auth("azure_devops")
        
        assert is_valid is True
        assert error_msg == ""
    
    def test_validate_git_auth_missing(self):
        """Test Git authentication validation with missing credentials"""
        secrets = FabricSecrets()
        is_valid, error_msg = secrets.validate_git_auth("github")
        
        assert is_valid is False
        assert "Missing GitHub authentication" in error_msg
    
    @patch.dict(os.environ, {"CI": "true"})
    def test_load_with_fallback_ci_environment(self):
        """Test loading in CI environment"""
        secrets = FabricSecrets.load_with_fallback()
        
        # Should detect CI environment
        assert os.getenv("CI") == "true"
    
    def test_get_secrets_raises_on_invalid(self):
        """Test get_secrets raises ValueError on missing credentials"""
        with pytest.raises(ValueError, match="Missing Fabric authentication"):
            get_secrets()
    
    def test_backward_compatibility(self, monkeypatch):
        """Test backward compatibility with get_environment_variables"""
        monkeypatch.setenv("FABRIC_TOKEN", "test-token")
        monkeypatch.setenv("TENANT_ID", "test-tenant")
        monkeypatch.setenv("GITHUB_TOKEN", "test-github")
        
        env_vars = get_environment_variables()
        
        assert env_vars["FABRIC_TOKEN"] == "test-token"
        assert env_vars["TENANT_ID"] == "test-tenant"
        assert env_vars["GITHUB_TOKEN"] == "test-github"


class TestPriorityLoading:
    """Test waterfall priority loading pattern"""
    
    def test_environment_variable_takes_priority(self, tmp_path, monkeypatch):
        """Test that environment variables take priority over .env file"""
        # Create .env file
        env_file = tmp_path / ".env"
        env_file.write_text("AZURE_CLIENT_ID=file-client-id\n")
        
        # Set environment variable (should take priority)
        monkeypatch.setenv("AZURE_CLIENT_ID", "env-client-id")
        
        secrets = FabricSecrets(_env_file=str(env_file))
        
        # Environment variable should win
        assert secrets.azure_client_id == "env-client-id"
    
    def test_fallback_to_env_file(self, tmp_path):
        """Test fallback to .env file when env var not set"""
        # Create .env file
        env_file = tmp_path / ".env"
        env_file.write_text("AZURE_CLIENT_ID=file-client-id\n")
        
        secrets = FabricSecrets(_env_file=str(env_file))
        
        # Should load from file
        assert secrets.azure_client_id == "file-client-id"
