"""
Shared base class for Fabric REST API clients.

Provides common HTTP request logic with:
- Automatic retry + exponential backoff for transient failures
- Proactive token refresh via TokenManager before each attempt

``FabricGitAPI`` and ``FabricDeploymentPipelineAPI`` inherit from this
instead of duplicating the same ~60 lines of init / retry / refresh code.
"""

import logging
import time
from typing import Any, Dict, Optional, TYPE_CHECKING

import requests

from usf_fabric_cli.utils.retry import (
    is_retryable_exception,
    calculate_backoff,
    DEFAULT_MAX_RETRIES,
    DEFAULT_BASE_DELAY,
    DEFAULT_MAX_DELAY,
)

if TYPE_CHECKING:
    from usf_fabric_cli.services.token_manager import TokenManager

logger = logging.getLogger(__name__)


class FabricAPIBase:
    """
    Base class for Fabric REST API clients.

    Subclasses get:
    * ``self.base_url`` / ``self.headers`` ready to use
    * ``_refresh_token_if_needed()`` — proactive bearer-token refresh
    * ``_make_request()`` — HTTP call with retry + backoff + token refresh
    """

    def __init__(
        self,
        access_token: str,
        base_url: str = "https://api.fabric.microsoft.com/v1",
        token_manager: Optional["TokenManager"] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
    ):
        self.base_url = base_url
        self._access_token = access_token
        self._token_manager = token_manager
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self.headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

    # ── Token helpers ──────────────────────────────────────────────

    def _refresh_token_if_needed(self) -> None:
        """Refresh the bearer token via *TokenManager* when available."""
        if self._token_manager:
            try:
                new_token = self._token_manager.get_token()
                if new_token != self._access_token:
                    self._access_token = new_token
                    self.headers["Authorization"] = f"Bearer {new_token}"
                    logger.debug("Token refreshed for %s", self.__class__.__name__)
            except Exception as e:
                logger.warning("Token refresh failed: %s", e)

    # ── HTTP helper ────────────────────────────────────────────────

    def _make_request(
        self,
        method: str,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> requests.Response:
        """
        Execute an HTTP request with retry + exponential backoff.

        Refreshes the bearer token before every attempt so that
        long-running retry sequences don't fail due to token expiry.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE …).
            url: Fully-qualified request URL.
            json: Optional JSON body.
            timeout: Per-request timeout in seconds.

        Returns:
            ``requests.Response`` on success.

        Raises:
            requests.RequestException: When all retries are exhausted.
        """
        last_exception: Optional[Exception] = None

        for attempt in range(self._max_retries + 1):
            self._refresh_token_if_needed()

            try:
                response = requests.request(
                    method,
                    url,
                    headers=self.headers,
                    json=json,
                    timeout=timeout,
                )
                response.raise_for_status()
                return response

            except requests.RequestException as e:
                last_exception = e

                if not is_retryable_exception(e) or attempt >= self._max_retries:
                    raise

                delay = calculate_backoff(attempt, self._base_delay, self._max_delay)
                logger.warning(
                    "%s request failed (attempt %d/%d): %s. " "Retrying in %.2fs…",
                    self.__class__.__name__,
                    attempt + 1,
                    self._max_retries + 1,
                    str(e),
                    delay,
                )
                time.sleep(delay)

        if last_exception:
            raise last_exception
        raise RuntimeError("Retry loop completed without returning or raising")
