"""
Token Manager for Azure AD Authentication.

Provides proactive token refresh to prevent mid-deployment authentication failures.
Tokens are refreshed 60 seconds before expiry to maintain continuous authentication
during long-running Fabric deployments.

Key Features:
- Proactive refresh (60s buffer before expiry)
- Azure AD Service Principal support via ClientSecretCredential
- Thread-safe token access
- Fabric CLI re-authentication on refresh
"""

import logging
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

try:
    from azure.identity import ClientSecretCredential
    from azure.core.credentials import AccessToken

    AZURE_IDENTITY_AVAILABLE = True
except ImportError:
    AZURE_IDENTITY_AVAILABLE = False
    ClientSecretCredential = None
    AccessToken = None

logger = logging.getLogger(__name__)

# Token refresh buffer - refresh this many seconds before actual expiry
DEFAULT_REFRESH_BUFFER_SECONDS = 60

# Fabric API scope for token acquisition
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"


@dataclass
class TokenInfo:
    """Token metadata for tracking refresh timing."""

    token: str
    expires_on: datetime
    acquired_at: datetime


class TokenManager:
    """
    Manages Azure AD token lifecycle with proactive refresh.

    Prevents authentication failures during long deployments by refreshing
    tokens before they expire. Uses Azure Identity SDK for token acquisition
    and tracks token age for proactive refresh.

    Example:
        >>> manager = TokenManager(client_id, client_secret, tenant_id)
        >>> token = manager.get_token()  # Gets valid token, refreshes if needed
        >>> manager.refresh_fabric_cli_auth()  # Re-authenticates fab CLI
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        refresh_buffer_seconds: int = DEFAULT_REFRESH_BUFFER_SECONDS,
        on_token_refresh: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize TokenManager with Service Principal credentials.

        Args:
            client_id: Azure AD application (client) ID
            client_secret: Service Principal secret
            tenant_id: Azure AD tenant ID
            refresh_buffer_seconds: Seconds before expiry to trigger refresh
            on_token_refresh: Optional callback when token is refreshed
        """
        if not AZURE_IDENTITY_AVAILABLE:
            raise ImportError(
                "azure-identity package required for TokenManager. "
                "Install with: pip install azure-identity"
            )

        self._client_id = client_id
        self._client_secret = client_secret
        self._tenant_id = tenant_id
        self._refresh_buffer_seconds = refresh_buffer_seconds
        self._on_token_refresh = on_token_refresh

        self._credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        self._token_info: Optional[TokenInfo] = None
        self._last_cli_auth: Optional[datetime] = None

        logger.info(
            "TokenManager initialized with %ds refresh buffer", refresh_buffer_seconds
        )

    @property
    def token(self) -> str:
        """Get current valid token, refreshing if necessary."""
        return self.get_token()

    @property
    def token_age_seconds(self) -> Optional[float]:
        """Get age of current token in seconds, or None if no token."""
        if not self._token_info:
            return None
        now = datetime.now(timezone.utc)
        return (now - self._token_info.acquired_at).total_seconds()

    @property
    def seconds_until_expiry(self) -> Optional[float]:
        """Get seconds until token expires, or None if no token."""
        if not self._token_info:
            return None
        now = datetime.now(timezone.utc)
        return (self._token_info.expires_on - now).total_seconds()

    def _should_refresh(self) -> bool:
        """Check if token should be refreshed."""
        if not self._token_info:
            return True

        seconds_left = self.seconds_until_expiry
        if seconds_left is None:
            return True

        should_refresh = seconds_left <= self._refresh_buffer_seconds
        if should_refresh:
            logger.debug(
                "Token refresh needed: %.1fs until expiry (buffer: %ds)",
                seconds_left,
                self._refresh_buffer_seconds,
            )
        return should_refresh

    def _acquire_token(self) -> TokenInfo:
        """Acquire new token from Azure AD."""
        logger.info("Acquiring new Azure AD token for Fabric API...")
        start_time = time.time()

        try:
            access_token: AccessToken = self._credential.get_token(FABRIC_SCOPE)

            # Convert expires_on (Unix timestamp) to datetime
            expires_on = datetime.fromtimestamp(
                access_token.expires_on, tz=timezone.utc
            )
            acquired_at = datetime.now(timezone.utc)

            duration = time.time() - start_time
            logger.info(
                "Token acquired in %.2fs, expires at %s",
                duration,
                expires_on.isoformat(),
            )

            return TokenInfo(
                token=access_token.token,
                expires_on=expires_on,
                acquired_at=acquired_at,
            )
        except Exception as e:
            logger.error("Failed to acquire token: %s", e)
            raise

    def get_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.

        Returns:
            Valid access token string

        Raises:
            Exception: If token acquisition fails
        """
        if self._should_refresh():
            self._token_info = self._acquire_token()

            # Notify callback if registered
            if self._on_token_refresh:
                try:
                    self._on_token_refresh(self._token_info.token)
                except Exception as e:
                    logger.warning("Token refresh callback failed: %s", e)

        return self._token_info.token

    def refresh_fabric_cli_auth(self) -> bool:
        """
        Re-authenticate the Fabric CLI with fresh credentials.

        This should be called when the token has been refreshed to ensure
        the fab CLI's cached authentication is updated.

        Returns:
            True if re-authentication succeeded, False otherwise
        """
        logger.info("Re-authenticating Fabric CLI with Service Principal...")

        try:
            # Logout first to clear stale state
            subprocess.run(
                ["fab", "auth", "logout"],
                capture_output=True,
                check=False,
                timeout=10,
            )

            # Login with Service Principal credentials
            cmd = [
                "fab",
                "auth",
                "login",
                "--username",
                self._client_id,
                "--password",
                self._client_secret,
                "--tenant",
                self._tenant_id,
            ]

            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )

            self._last_cli_auth = datetime.now(timezone.utc)
            logger.info("Fabric CLI re-authenticated successfully")
            return True

        except subprocess.TimeoutExpired:
            logger.error("Fabric CLI authentication timed out")
            return False
        except subprocess.CalledProcessError as e:
            logger.error("Fabric CLI authentication failed: %s", e.stderr)
            return False
        except FileNotFoundError:
            logger.error("Fabric CLI ('fab') not found")
            return False

    def ensure_fresh_auth(self, max_age_seconds: float = 300) -> bool:
        """
        Ensure token and CLI auth are fresh.

        Refreshes token if needed and re-authenticates CLI if token was updated
        or CLI auth is older than max_age_seconds.

        Args:
            max_age_seconds: Max age of CLI auth before refresh (default: 5 min)

        Returns:
            True if auth is fresh, False if refresh failed
        """
        # Get/refresh token
        old_token = self._token_info.token if self._token_info else None
        current_token = self.get_token()

        # Check if CLI auth needs refresh
        token_changed = old_token != current_token
        cli_auth_age = None
        if self._last_cli_auth:
            cli_auth_age = (
                datetime.now(timezone.utc) - self._last_cli_auth
            ).total_seconds()

        needs_cli_refresh = (
            token_changed or cli_auth_age is None or cli_auth_age > max_age_seconds
        )

        if needs_cli_refresh:
            logger.info(
                "CLI auth refresh needed (token_changed=%s, cli_auth_age=%s)",
                token_changed,
                cli_auth_age,
            )
            return self.refresh_fabric_cli_auth()

        return True


def create_token_manager_from_env() -> Optional[TokenManager]:
    """
    Create TokenManager from environment variables.

    Looks for:
    - AZURE_CLIENT_ID
    - AZURE_CLIENT_SECRET
    - TENANT_ID or AZURE_TENANT_ID

    Returns:
        TokenManager instance or None if credentials not available
    """
    import os

    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    tenant_id = os.getenv("TENANT_ID") or os.getenv("AZURE_TENANT_ID")

    # Sanitize credentials (handle inline comments from .env files)
    if client_id:
        client_id = client_id.split(" #")[0].strip()
    if client_secret:
        client_secret = client_secret.split(" #")[0].strip()
    if tenant_id:
        tenant_id = tenant_id.split(" #")[0].strip()

    if not client_id or not client_secret or not tenant_id:
        logger.debug("Service Principal credentials not fully configured")
        return None

    try:
        return TokenManager(client_id, client_secret, tenant_id)
    except ImportError:
        logger.warning("azure-identity not available, TokenManager disabled")
        return None
    except Exception as e:
        logger.warning("Failed to create TokenManager: %s", e)
        return None
