"""
Unit tests for Fabric CLI wrapper
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json

from src.core.fabric_wrapper import FabricCLIWrapper, FabricDiagnostics


class TestFabricCLIWrapper:
    
    def setup_method(self):
        """Setup test fixtures"""
        telemetry = MagicMock()
        telemetry.emit = MagicMock()
        self.fabric = FabricCLIWrapper("fake-token", telemetry_client=telemetry)
    
    @patch('subprocess.run')
    def test_create_workspace_success(self, mock_run):
        """Test successful workspace creation"""
        
        # Mock successful fabric command
        mock_run.return_value = Mock(
            stdout='{"id": "workspace-123", "name": "test-workspace"}',
            stderr='',
            returncode=0
        )
        
        result = self.fabric.create_workspace("test-workspace", "F64", "Test description")
        
        assert result["success"] is True
        assert "workspace-123" in str(result.get("data", ""))
        
        # Verify command was called correctly
        mock_run.assert_called()
        commands = [call.args[0] for call in mock_run.call_args_list]
        create_cmd = next((cmd for cmd in commands if cmd[:3] == ["fabric", "workspace", "create"]), None)
        assert create_cmd is not None
    
    @patch('subprocess.run')
    def test_create_workspace_already_exists(self, mock_run):
        """Test workspace creation when workspace already exists (idempotency)"""
        
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(
            returncode=1,
            cmd=['fabric', 'workspace', 'create'],
            stderr='Workspace already exists'
        )

        result = self.fabric.create_workspace("test-workspace", "F64")

        assert result["success"] is True
        assert result.get("reused") is True
    
    @patch('subprocess.run')
    def test_create_lakehouse_with_folder(self, mock_run):
        """Test lakehouse creation in specific folder"""
        
        mock_run.return_value = Mock(
            stdout='{"id": "lakehouse-123", "name": "test-lakehouse"}',
            stderr='',
            returncode=0
        )
        
        result = self.fabric.create_lakehouse(
            "workspace-123", 
            "test-lakehouse", 
            "folder-456",
            "Test lakehouse"
        )
        
        assert result["success"] is True
        
        # Verify folder-id was included in command
        call_args = mock_run.call_args[0][0]
        assert "--folder-id" in call_args
        assert "folder-456" in call_args
    
    @patch('subprocess.run')
    def test_diagnostic_fabric_cli_installed(self, mock_run):
        """Test Fabric CLI installation check"""
        
        mock_run.return_value = Mock(
            stdout='fabric-cli v1.0.0',
            stderr='',
            returncode=0
        )
        
        diagnostics = FabricDiagnostics(self.fabric)
        result = diagnostics.validate_fabric_cli_installation()
        
        assert result["success"] is True
        assert "v1.0.0" in result["version"]
    
    @patch('subprocess.run')
    def test_diagnostic_fabric_cli_not_installed(self, mock_run):
        """Test Fabric CLI not installed"""
        
        mock_run.side_effect = FileNotFoundError("fabric command not found")
        
        diagnostics = FabricDiagnostics(self.fabric)
        result = diagnostics.validate_fabric_cli_installation()
        
        assert result["success"] is False
        assert "not found" in result["error"]
        assert "remediation" in result


if __name__ == "__main__":
    pytest.main([__file__])