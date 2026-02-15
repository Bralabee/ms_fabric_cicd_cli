"""
Unit tests for secrets management module
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from usf_fabric_cli.utils.secrets import (
    FabricSecrets,
    get_environment_variables,
    get_secrets,
)


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
        # Ensure TENANT_ID doesn't interfere from .env or env vars
        monkeypatch.delenv("TENANT_ID", raising=False)

        # Pass _env_file=None to ignore .env file
        secrets = FabricSecrets(_env_file=None)

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

    def test_validate_fabric_auth_missing_credentials(self, monkeypatch):
        """Test validation with missing credentials"""
        # Clear potential environment variables
        for var in [
            "AZURE_CLIENT_ID",
            "AZURE_CLIENT_SECRET",
            "TENANT_ID",
            "FABRIC_TOKEN",
        ]:
            monkeypatch.delenv(var, raising=False)

        # Use non-existent env file to avoid reading local .env
        secrets = FabricSecrets(_env_file="non_existent_env_file")
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
        # Ensure no token is present regardless of environment
        with patch.dict(os.environ, {}, clear=True):
            secrets = FabricSecrets(_env_file=None)
            is_valid, error_msg = secrets.validate_git_auth("github")

            assert is_valid is False
            assert "Missing GitHub authentication" in error_msg

    @patch.dict(os.environ, {"CI": "true"})
    def test_load_with_fallback_ci_environment(self):
        """Test loading in CI environment"""
        FabricSecrets.load_with_fallback()

        # Should detect CI environment
        assert os.getenv("CI") == "true"

    def test_get_secrets_raises_on_invalid(self, monkeypatch):
        """Test get_secrets raises ValueError on missing credentials"""
        # Clear potential environment variables
        for var in [
            "AZURE_CLIENT_ID",
            "AZURE_CLIENT_SECRET",
            "TENANT_ID",
            "FABRIC_TOKEN",
        ]:
            monkeypatch.delenv(var, raising=False)

        # Patch FabricSecrets to ignore .env file
        with patch("usf_fabric_cli.utils.secrets.FabricSecrets") as MockSecrets:
            # We want to use the real logic but with empty config
            # So we can't just mock the class entirely easily without side effects.
            # Instead, let's patch the model_config on the class temporarily?
            # Or better, patch the constructor call inside get_secrets?
            # get_secrets calls FabricSecrets()

            # Let's use a side_effect to return a real instance with _env_file=None
            def side_effect(*args, **kwargs):
                return FabricSecrets(_env_file="non_existent_env_file", **kwargs)

            MockSecrets.side_effect = side_effect

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

    def test_fallback_to_env_file(self, tmp_path, monkeypatch):
        """Test fallback to .env file when env var not set"""
        # Clear env var to ensure fallback
        monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)

        # Create .env file
        env_file = tmp_path / ".env"
        env_file.write_text("AZURE_CLIENT_ID=file-client-id\n")

        secrets = FabricSecrets(_env_file=str(env_file))

        # Should load from file
        assert secrets.azure_client_id == "file-client-id"


class TestKeyVaultIntegration:
    """Test Azure Key Vault fallback paths (mocked, no real credentials)."""

    def _make_secrets(self, monkeypatch, **overrides):
        """Helper: create FabricSecrets with clean env + optional overrides."""
        for var in [
            "AZURE_CLIENT_ID",
            "AZURE_CLIENT_SECRET",
            "TENANT_ID",
            "AZURE_TENANT_ID",
            "FABRIC_TOKEN",
            "GITHUB_TOKEN",
            "AZURE_DEVOPS_PAT",
            "AZURE_KEYVAULT_URL",
        ]:
            monkeypatch.delenv(var, raising=False)
        for k, v in overrides.items():
            monkeypatch.setenv(k, v)
        return FabricSecrets(_env_file="non_existent_env_file")

    # ── _get_from_keyvault ─────────────────────────────────────────

    @patch("usf_fabric_cli.utils.secrets.KEYVAULT_AVAILABLE", True)
    @patch("usf_fabric_cli.utils.secrets.SecretClient")
    @patch("usf_fabric_cli.utils.secrets.DefaultAzureCredential")
    def test_get_from_keyvault_success(
        self, mock_cred_cls, mock_client_cls, monkeypatch
    ):
        """_get_from_keyvault returns secret value when KV is reachable."""
        secrets = self._make_secrets(
            monkeypatch, AZURE_KEYVAULT_URL="https://my-vault.vault.azure.net"
        )

        mock_secret = MagicMock()
        mock_secret.value = "kv-secret-value"
        mock_client_cls.return_value.get_secret.return_value = mock_secret

        result = secrets._get_from_keyvault("azure-client-id")
        assert result == "kv-secret-value"
        mock_client_cls.return_value.get_secret.assert_called_once_with(
            "azure-client-id"
        )

    @patch("usf_fabric_cli.utils.secrets.KEYVAULT_AVAILABLE", True)
    @patch("usf_fabric_cli.utils.secrets.SecretClient")
    @patch("usf_fabric_cli.utils.secrets.DefaultAzureCredential")
    def test_get_from_keyvault_failure_returns_none(
        self, mock_cred_cls, mock_client_cls, monkeypatch
    ):
        """_get_from_keyvault returns None when KV call raises."""
        secrets = self._make_secrets(
            monkeypatch, AZURE_KEYVAULT_URL="https://my-vault.vault.azure.net"
        )
        mock_client_cls.return_value.get_secret.side_effect = Exception("403 Forbidden")

        result = secrets._get_from_keyvault("azure-client-id")
        assert result is None

    @patch("usf_fabric_cli.utils.secrets.KEYVAULT_AVAILABLE", False)
    def test_get_from_keyvault_skipped_when_sdk_missing(self, monkeypatch):
        """_get_from_keyvault returns None when azure-keyvault-secrets not installed."""
        secrets = self._make_secrets(
            monkeypatch, AZURE_KEYVAULT_URL="https://my-vault.vault.azure.net"
        )
        # Should be a noop — no SDK to call
        assert secrets._get_from_keyvault("azure-client-id") is None

    def test_get_from_keyvault_skipped_when_no_url(self, monkeypatch):
        """_get_from_keyvault returns None when AZURE_KEYVAULT_URL is not set."""
        secrets = self._make_secrets(monkeypatch)
        assert secrets.azure_keyvault_url is None
        assert secrets._get_from_keyvault("anything") is None

    # ── get_secret KV fallback ─────────────────────────────────────

    @patch("usf_fabric_cli.utils.secrets.KEYVAULT_AVAILABLE", True)
    @patch("usf_fabric_cli.utils.secrets.SecretClient")
    @patch("usf_fabric_cli.utils.secrets.DefaultAzureCredential")
    def test_get_secret_falls_back_to_keyvault(
        self, mock_cred_cls, mock_client_cls, monkeypatch
    ):
        """get_secret tries Key Vault when env var is missing."""
        secrets = self._make_secrets(
            monkeypatch, AZURE_KEYVAULT_URL="https://my-vault.vault.azure.net"
        )

        mock_secret = MagicMock()
        mock_secret.value = "from-kv"
        mock_client_cls.return_value.get_secret.return_value = mock_secret

        result = secrets.get_secret("SOME_SECRET")
        assert result == "from-kv"
        # Default KV name is env var with _ → -
        mock_client_cls.return_value.get_secret.assert_called_once_with("SOME-SECRET")

    @patch("usf_fabric_cli.utils.secrets.KEYVAULT_AVAILABLE", True)
    @patch("usf_fabric_cli.utils.secrets.SecretClient")
    @patch("usf_fabric_cli.utils.secrets.DefaultAzureCredential")
    def test_get_secret_env_var_beats_keyvault(
        self, mock_cred_cls, mock_client_cls, monkeypatch
    ):
        """get_secret prefers env var over Key Vault."""
        monkeypatch.setenv("MY_VAR", "from-env")
        secrets = self._make_secrets(
            monkeypatch,
            AZURE_KEYVAULT_URL="https://my-vault.vault.azure.net",
            MY_VAR="from-env",
        )

        result = secrets.get_secret("MY_VAR")
        assert result == "from-env"
        # Key Vault should NOT be called
        mock_client_cls.return_value.get_secret.assert_not_called()

    # ── load_with_fallback KV population ───────────────────────────

    @patch("usf_fabric_cli.utils.secrets.KEYVAULT_AVAILABLE", True)
    @patch("usf_fabric_cli.utils.secrets.SecretClient")
    @patch("usf_fabric_cli.utils.secrets.DefaultAzureCredential")
    def test_load_with_fallback_populates_from_keyvault(
        self, mock_cred_cls, mock_client_cls, monkeypatch
    ):
        """load_with_fallback fills missing fields from Key Vault."""
        # Map KV secret names → values
        kv_secrets = {
            "azure-client-id": "kv-client",
            "azure-client-secret": "kv-secret",
            "tenant-id": "kv-tenant",
            "fabric-token": "kv-token",
            "github-token": "kv-gh",
            "azure-devops-pat": "kv-pat",
        }
        mock_kv_secret = MagicMock()

        def mock_get_secret(name):
            s = MagicMock()
            s.value = kv_secrets.get(name)
            return s

        mock_client_cls.return_value.get_secret.side_effect = mock_get_secret

        with patch.dict(
            os.environ,
            {"AZURE_KEYVAULT_URL": "https://v.vault.azure.net"},
            clear=True,
        ):
            instance = FabricSecrets.load_with_fallback(
                env_file="non_existent_env_file"
            )

        assert instance.azure_client_id == "kv-client"
        assert instance.azure_client_secret == "kv-secret"
        assert instance.tenant_id == "kv-tenant"
        assert instance.fabric_token == "kv-token"
        assert instance.github_token == "kv-gh"
        assert instance.azure_devops_pat == "kv-pat"

    @patch("usf_fabric_cli.utils.secrets.KEYVAULT_AVAILABLE", False)
    def test_load_with_fallback_skips_kv_when_sdk_missing(self, monkeypatch):
        """load_with_fallback doesn't error when azure SDK unavailable."""

        with patch.dict(
            os.environ,
            {"AZURE_KEYVAULT_URL": "https://v.vault.azure.net"},
            clear=True,
        ):
            instance = FabricSecrets.load_with_fallback(
                env_file="non_existent_env_file"
            )
        # Fields should remain None — no crash
        assert instance.azure_client_id is None
