"""
Unit tests for FabricAPIBase — the shared base class for Fabric REST API clients.

Covers:
- Initialization and header setup
- Token refresh via TokenManager
- HTTP request with retry + exponential backoff
- Non-retryable errors raised immediately
- Token refresh per retry attempt
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from usf_fabric_cli.services.fabric_api_base import FabricAPIBase

# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def base_api():
    """Create a plain FabricAPIBase instance (no token manager)."""
    return FabricAPIBase(access_token="test-token-abc")


@pytest.fixture
def mock_token_manager():
    """Create a mock TokenManager that returns refreshed tokens."""
    manager = MagicMock()
    manager.get_token.return_value = "refreshed-token-xyz"
    return manager


@pytest.fixture
def api_with_token_manager(mock_token_manager):
    """Create a FabricAPIBase with a token manager."""
    return FabricAPIBase(
        access_token="initial-token",
        token_manager=mock_token_manager,
    )


# ── Initialization ─────────────────────────────────────────────────


class TestFabricAPIBaseInit:
    """Tests for FabricAPIBase.__init__."""

    def test_default_base_url(self, base_api):
        assert base_api.base_url == "https://api.fabric.microsoft.com/v1"

    def test_custom_base_url(self):
        api = FabricAPIBase(access_token="tok", base_url="https://custom.api/v2")
        assert api.base_url == "https://custom.api/v2"

    def test_headers_contain_bearer_token(self, base_api):
        assert base_api.headers["Authorization"] == "Bearer test-token-abc"
        assert base_api.headers["Content-Type"] == "application/json"

    def test_no_token_manager_by_default(self, base_api):
        assert base_api._token_manager is None

    def test_token_manager_stored(self, api_with_token_manager, mock_token_manager):
        assert api_with_token_manager._token_manager is mock_token_manager

    def test_custom_retry_params(self):
        api = FabricAPIBase(
            access_token="tok",
            max_retries=5,
            base_delay=2.0,
            max_delay=120.0,
        )
        assert api._max_retries == 5
        assert api._base_delay == 2.0
        assert api._max_delay == 120.0


# ── Token refresh ──────────────────────────────────────────────────


class TestRefreshTokenIfNeeded:
    """Tests for _refresh_token_if_needed."""

    def test_no_manager_does_nothing(self, base_api):
        """Without a TokenManager, refresh is a no-op."""
        original_token = base_api._access_token
        base_api._refresh_token_if_needed()
        assert base_api._access_token == original_token

    def test_token_refreshed_when_changed(self, api_with_token_manager):
        """When the manager returns a new token, headers are updated."""
        assert api_with_token_manager._access_token == "initial-token"
        api_with_token_manager._refresh_token_if_needed()

        assert api_with_token_manager._access_token == "refreshed-token-xyz"
        assert (
            api_with_token_manager.headers["Authorization"]
            == "Bearer refreshed-token-xyz"
        )

    def test_token_not_updated_when_same(self, api_with_token_manager):
        """When the manager returns the same token, no update happens."""
        api_with_token_manager._token_manager.get_token.return_value = "initial-token"
        api_with_token_manager._refresh_token_if_needed()
        assert api_with_token_manager._access_token == "initial-token"
        assert api_with_token_manager.headers["Authorization"] == "Bearer initial-token"

    def test_runtime_error_is_swallowed(self, api_with_token_manager):
        """RuntimeError from token manager is logged but not raised."""
        api_with_token_manager._token_manager.get_token.side_effect = RuntimeError(
            "token expired"
        )
        # Should not raise
        api_with_token_manager._refresh_token_if_needed()
        # Token should remain unchanged
        assert api_with_token_manager._access_token == "initial-token"


# ── HTTP requests (make_request) ───────────────────────────────────


class TestMakeRequest:
    """Tests for _make_request with retry logic."""

    @patch("usf_fabric_cli.services.fabric_api_base.requests.request")
    def test_successful_get(self, mock_request, base_api):
        """Successful GET returns the response."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        result = base_api._make_request("GET", "https://api.example.com/test")

        assert result is mock_response
        mock_request.assert_called_once_with(
            "GET",
            "https://api.example.com/test",
            headers=base_api.headers,
            json=None,
            timeout=30,
        )

    @patch("usf_fabric_cli.services.fabric_api_base.requests.request")
    def test_successful_post_with_json(self, mock_request, base_api):
        """POST with JSON body passes payload correctly."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        body = {"key": "value"}
        result = base_api._make_request(
            "POST", "https://api.example.com/create", json=body
        )

        assert result is mock_response
        mock_request.assert_called_once_with(
            "POST",
            "https://api.example.com/create",
            headers=base_api.headers,
            json=body,
            timeout=30,
        )

    @patch("usf_fabric_cli.services.fabric_api_base.requests.request")
    def test_custom_timeout(self, mock_request, base_api):
        """Custom timeout is forwarded."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        base_api._make_request("GET", "https://api.example.com/slow", timeout=120)
        _, kwargs = mock_request.call_args
        assert kwargs["timeout"] == 120

    @patch("usf_fabric_cli.services.fabric_api_base.requests.request")
    def test_non_retryable_error_raises_immediately(self, mock_request, base_api):
        """A 404 (non-retryable) is raised without retrying."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error
        mock_request.return_value = mock_response

        with pytest.raises(requests.exceptions.HTTPError):
            base_api._make_request("GET", "https://api.example.com/missing")

        # Should only attempt once (no retries for non-retryable)
        assert mock_request.call_count == 1

    @patch("usf_fabric_cli.services.fabric_api_base.time.sleep")
    @patch("usf_fabric_cli.services.fabric_api_base.requests.request")
    def test_retryable_error_retries_then_succeeds(
        self, mock_request, mock_sleep, base_api
    ):
        """A retryable 503 error triggers retry; success on second attempt."""
        # First call: 503 (retryable)
        mock_response_fail = Mock()
        mock_response_fail.ok = False
        mock_response_fail.status_code = 503
        mock_response_fail.text = "Service Unavailable"
        http_error = requests.exceptions.HTTPError(response=mock_response_fail)
        mock_response_fail.raise_for_status.side_effect = http_error

        # Second call: success
        mock_response_ok = Mock()
        mock_response_ok.ok = True
        mock_response_ok.raise_for_status = Mock()

        mock_request.side_effect = [mock_response_fail, mock_response_ok]

        result = base_api._make_request("GET", "https://api.example.com/flaky")

        assert result is mock_response_ok
        assert mock_request.call_count == 2
        mock_sleep.assert_called_once()  # backoff sleep between retries

    @patch("usf_fabric_cli.services.fabric_api_base.time.sleep")
    @patch("usf_fabric_cli.services.fabric_api_base.requests.request")
    def test_retryable_error_exhausts_retries(self, mock_request, mock_sleep):
        """When all retries are exhausted, the last exception is raised."""
        api = FabricAPIBase(access_token="tok", max_retries=2)

        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"
        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error
        mock_request.return_value = mock_response

        with pytest.raises(requests.exceptions.HTTPError):
            api._make_request("GET", "https://api.example.com/throttled")

        # 1 initial + 2 retries = 3 attempts
        assert mock_request.call_count == 3

    @patch("usf_fabric_cli.services.fabric_api_base.time.sleep")
    @patch("usf_fabric_cli.services.fabric_api_base.requests.request")
    def test_connection_error_retries(self, mock_request, mock_sleep, base_api):
        """ConnectionError is retryable."""
        conn_err = requests.exceptions.ConnectionError("Connection refused")

        mock_response_ok = Mock()
        mock_response_ok.ok = True
        mock_response_ok.raise_for_status = Mock()

        mock_request.side_effect = [conn_err, mock_response_ok]

        result = base_api._make_request("GET", "https://api.example.com/conn")
        assert result is mock_response_ok
        assert mock_request.call_count == 2

    @patch("usf_fabric_cli.services.fabric_api_base.requests.request")
    def test_token_refresh_called_per_attempt(
        self, mock_request, api_with_token_manager
    ):
        """Token refresh is called before each request attempt."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        api_with_token_manager._make_request("GET", "https://api.example.com/x")

        # Verify token manager was consulted
        api_with_token_manager._token_manager.get_token.assert_called()

    @patch("usf_fabric_cli.services.fabric_api_base.requests.request")
    def test_non_ok_response_logged_at_debug(self, mock_request, base_api):
        """Non-2xx responses have their body logged."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error
        mock_request.return_value = mock_response

        with pytest.raises(requests.exceptions.HTTPError):
            base_api._make_request("GET", "https://api.example.com/bad")
