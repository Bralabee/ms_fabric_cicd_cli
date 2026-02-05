"""
Unit tests for TokenManager - Azure AD token lifecycle management.

Tests verify:
- Token refresh triggers when within buffer period
- Token not refreshed when plenty of time remaining
- Fabric CLI re-authentication called after token refresh
- Factory function creates manager from environment
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, Mock
import pytest


class TestTokenInfo:
    """Tests for TokenInfo dataclass."""

    def test_token_info_creation(self):
        """Test TokenInfo stores token metadata correctly."""
        from usf_fabric_cli.services.token_manager import TokenInfo

        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=1)

        info = TokenInfo(
            token="test-token-123",
            expires_on=expires,
            acquired_at=now,
        )

        assert info.token == "test-token-123"
        assert info.expires_on == expires
        assert info.acquired_at == now


class TestTokenManager:
    """Tests for TokenManager class."""

    @pytest.fixture
    def mock_credential(self):
        """Create mock ClientSecretCredential."""
        with patch(
            "usf_fabric_cli.services.token_manager.ClientSecretCredential"
        ) as mock:
            credential_instance = MagicMock()
            mock.return_value = credential_instance
            yield credential_instance

    @pytest.fixture
    def mock_access_token(self):
        """Create mock AccessToken."""
        token = MagicMock()
        token.token = "mock-access-token-abc123"
        # Expires 1 hour from now
        token.expires_on = (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
        return token

    @pytest.fixture
    def manager(self, mock_credential, mock_access_token):
        """Create TokenManager with mocked azure-identity."""
        mock_credential.get_token.return_value = mock_access_token

        from usf_fabric_cli.services.token_manager import TokenManager

        return TokenManager(
            client_id="test-client-id",
            client_secret="test-client-secret",
            tenant_id="test-tenant-id",
            refresh_buffer_seconds=60,
        )

    def test_init_creates_credential(self, mock_credential):
        """Test TokenManager initializes with ClientSecretCredential."""
        from usf_fabric_cli.services.token_manager import TokenManager

        manager = TokenManager(
            client_id="client-123",
            client_secret="secret-456",
            tenant_id="tenant-789",
        )

        # Verify credential created with correct params
        from usf_fabric_cli.services.token_manager import ClientSecretCredential

        ClientSecretCredential.assert_called_once_with(
            tenant_id="tenant-789",
            client_id="client-123",
            client_secret="secret-456",
        )

    def test_get_token_acquires_on_first_call(self, manager, mock_credential):
        """Test first get_token() acquires new token."""
        token = manager.get_token()

        assert token == "mock-access-token-abc123"
        mock_credential.get_token.assert_called_once()

    def test_get_token_reuses_valid_token(
        self, manager, mock_credential, mock_access_token
    ):
        """Test get_token() doesn't refresh when token is still valid."""
        # First call
        manager.get_token()
        # Second call
        manager.get_token()

        # Should only acquire once
        assert mock_credential.get_token.call_count == 1

    def test_get_token_refreshes_when_near_expiry(
        self, manager, mock_credential, mock_access_token
    ):
        """Test token refreshes when within buffer period."""
        # First call - acquire initial token
        manager.get_token()

        # Manually set token to expire soon (within 60s buffer)
        from usf_fabric_cli.services.token_manager import TokenInfo

        manager._token_info = TokenInfo(
            token="old-token",
            expires_on=datetime.now(timezone.utc) + timedelta(seconds=30),
            acquired_at=datetime.now(timezone.utc) - timedelta(minutes=55),
        )

        # Second call - should refresh
        token = manager.get_token()

        assert mock_credential.get_token.call_count == 2

    def test_token_age_seconds_returns_correct_age(self, manager, mock_credential):
        """Test token_age_seconds property."""
        manager.get_token()

        age = manager.token_age_seconds

        # Should be very small (just acquired)
        assert age is not None
        assert age < 1.0

    def test_seconds_until_expiry_returns_correct_value(self, manager, mock_credential):
        """Test seconds_until_expiry property."""
        manager.get_token()

        seconds_left = manager.seconds_until_expiry

        # Should be around 1 hour (3600 seconds) minus a small margin
        assert seconds_left is not None
        assert 3500 < seconds_left <= 3600

    def test_callback_invoked_on_refresh(self, mock_credential, mock_access_token):
        """Test on_token_refresh callback is invoked."""
        mock_credential.get_token.return_value = mock_access_token

        callback = MagicMock()

        from usf_fabric_cli.services.token_manager import TokenManager

        manager = TokenManager(
            client_id="test-client",
            client_secret="test-secret",
            tenant_id="test-tenant",
            on_token_refresh=callback,
        )

        manager.get_token()

        callback.assert_called_once_with("mock-access-token-abc123")


class TestRefreshFabricCliAuth:
    """Tests for Fabric CLI re-authentication."""

    @pytest.fixture
    def manager(self):
        """Create TokenManager with mocked dependencies."""
        with patch("usf_fabric_cli.services.token_manager.ClientSecretCredential"):
            from usf_fabric_cli.services.token_manager import TokenManager

            return TokenManager(
                client_id="test-client",
                client_secret="test-secret",
                tenant_id="test-tenant",
            )

    @patch("usf_fabric_cli.services.token_manager.subprocess.run")
    def test_refresh_cli_auth_success(self, mock_run, manager):
        """Test successful CLI re-authentication."""
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.refresh_fabric_cli_auth()

        assert result is True
        # Should call logout then login
        assert mock_run.call_count == 2

    @patch("usf_fabric_cli.services.token_manager.subprocess.run")
    def test_refresh_cli_auth_login_failure(self, mock_run, manager):
        """Test CLI re-authentication failure."""
        # Logout succeeds, login fails
        from subprocess import CalledProcessError

        mock_run.side_effect = [
            MagicMock(returncode=0),  # logout
            CalledProcessError(1, "fab", stderr="auth failed"),  # login
        ]

        result = manager.refresh_fabric_cli_auth()

        assert result is False

    @patch("usf_fabric_cli.services.token_manager.subprocess.run")
    def test_refresh_cli_auth_timeout(self, mock_run, manager):
        """Test CLI re-authentication timeout."""
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired("fab", 30)

        result = manager.refresh_fabric_cli_auth()

        assert result is False


class TestCreateTokenManagerFromEnv:
    """Tests for factory function."""

    @patch.dict(
        "os.environ",
        {
            "AZURE_CLIENT_ID": "env-client-id",
            "AZURE_CLIENT_SECRET": "env-client-secret",
            "TENANT_ID": "env-tenant-id",
        },
    )
    @patch("usf_fabric_cli.services.token_manager.ClientSecretCredential")
    def test_creates_manager_from_env(self, mock_credential):
        """Test factory creates manager from environment."""
        from usf_fabric_cli.services.token_manager import create_token_manager_from_env

        manager = create_token_manager_from_env()

        assert manager is not None
        mock_credential.assert_called_once_with(
            tenant_id="env-tenant-id",
            client_id="env-client-id",
            client_secret="env-client-secret",
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_returns_none_when_credentials_missing(self):
        """Test factory returns None when credentials missing."""
        from usf_fabric_cli.services.token_manager import create_token_manager_from_env

        manager = create_token_manager_from_env()

        assert manager is None

    @patch.dict(
        "os.environ",
        {
            "AZURE_CLIENT_ID": "client-id # some comment",
            "AZURE_CLIENT_SECRET": "secret # inline",
            "AZURE_TENANT_ID": "tenant-id # comment",
            "TENANT_ID": "",  # Clear this to prevent interference
        },
        clear=False,
    )
    @patch("usf_fabric_cli.services.token_manager.ClientSecretCredential")
    def test_sanitizes_inline_comments(self, mock_credential):
        """Test factory sanitizes inline comments from .env files."""
        # Remove TENANT_ID if set to prevent interference
        import os

        os.environ.pop("TENANT_ID", None)

        from usf_fabric_cli.services.token_manager import create_token_manager_from_env

        manager = create_token_manager_from_env()

        assert manager is not None
        mock_credential.assert_called_once_with(
            tenant_id="tenant-id",
            client_id="client-id",
            client_secret="secret",
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
