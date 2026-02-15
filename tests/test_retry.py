"""
Unit tests for retry utilities (utils/retry.py).

Tests verify:
- Retryable error pattern detection
- HTTP status code classification
- Exception retryability
- Exponential backoff calculation
- Retry decorator behavior
- Retry request convenience function
"""

import random
from unittest.mock import MagicMock, patch

import pytest
import requests

from usf_fabric_cli.utils.retry import (
    calculate_backoff,
    is_retryable_error,
    is_retryable_exception,
    is_retryable_http_status,
    retry_request,
    retry_with_backoff,
)


class TestIsRetryableError:
    """Tests for error message pattern matching."""

    @pytest.mark.parametrize(
        "error_msg",
        [
            "Rate limit exceeded",
            "Error 429: Too Many Requests",
            "503 Service Unavailable",
            "Service temporarily unavailable",
            "Connection reset by peer",
            "Connection refused",
            "Request timed out",
            "Operation timed out after 30s",
            "API throttled, retry later",
            "too many requests sent",
            "Server busy, please wait",
        ],
    )
    def test_retryable_patterns(self, error_msg):
        """All known retryable error patterns should be detected."""
        assert is_retryable_error(error_msg) is True

    @pytest.mark.parametrize(
        "error_msg",
        [
            "Invalid credentials",
            "Permission denied",
            "Resource not found",
            "400 Bad Request",
            "401 Unauthorized",
            "403 Forbidden",
            "Malformed JSON payload",
            "",
        ],
    )
    def test_non_retryable_errors(self, error_msg):
        """Non-transient errors should NOT be classified as retryable."""
        assert is_retryable_error(error_msg) is False

    def test_case_insensitive(self):
        """Pattern matching should be case-insensitive."""
        assert is_retryable_error("RATE LIMIT") is True
        assert is_retryable_error("Timeout") is True


class TestIsRetryableHttpStatus:
    """Tests for HTTP status code classification."""

    @pytest.mark.parametrize("code", [401, 429, 502, 503, 504])
    def test_retryable_status_codes(self, code):
        """401 (token refresh), 429, 502, 503, 504 should be retryable."""
        assert is_retryable_http_status(code) is True

    @pytest.mark.parametrize("code", [200, 201, 400, 403, 404, 500])
    def test_non_retryable_status_codes(self, code):
        """Other status codes should NOT be retryable."""
        assert is_retryable_http_status(code) is False


class TestIsRetryableException:
    """Tests for exception retryability classification."""

    def test_http_error_429(self):
        """HTTPError with 429 should be retryable."""
        response = MagicMock()
        response.status_code = 429
        exc = requests.exceptions.HTTPError(response=response)
        assert is_retryable_exception(exc) is True

    def test_http_error_401(self):
        """HTTPError with 401 should be retryable (token refresh)."""
        response = MagicMock()
        response.status_code = 401
        exc = requests.exceptions.HTTPError(response=response)
        assert is_retryable_exception(exc) is True

    def test_connection_error(self):
        """ConnectionError should be retryable."""
        exc = requests.exceptions.ConnectionError("Connection refused")
        assert is_retryable_exception(exc) is True

    def test_timeout_error(self):
        """Timeout should be retryable."""
        exc = requests.exceptions.Timeout("Read timed out")
        assert is_retryable_exception(exc) is True

    def test_generic_exception_with_retryable_message(self):
        """Generic exception with retryable message should be retryable."""
        exc = Exception("503 Service Unavailable")
        assert is_retryable_exception(exc) is True

    def test_generic_exception_non_retryable(self):
        """Generic exception without retryable pattern should NOT be retryable."""
        exc = Exception("Invalid configuration")
        assert is_retryable_exception(exc) is False


class TestCalculateBackoff:
    """Tests for exponential backoff calculation."""

    def test_first_attempt_base_delay(self):
        """First attempt should be approximately base_delay."""
        random.seed(42)
        delay = calculate_backoff(0, base_delay=1.0, max_delay=30.0)
        assert 0.75 <= delay <= 1.25  # 1.0 ± 25% jitter

    def test_exponential_growth(self):
        """Delay should grow exponentially with attempt number."""
        delay0 = calculate_backoff(0, base_delay=1.0, max_delay=100.0, jitter=False)
        delay1 = calculate_backoff(1, base_delay=1.0, max_delay=100.0, jitter=False)
        delay2 = calculate_backoff(2, base_delay=1.0, max_delay=100.0, jitter=False)

        assert delay0 == 1.0
        assert delay1 == 2.0
        assert delay2 == 4.0

    def test_max_delay_cap(self):
        """Delay should never exceed max_delay (plus jitter)."""
        delay = calculate_backoff(20, base_delay=1.0, max_delay=30.0, jitter=False)
        assert delay == 30.0

    def test_max_delay_cap_with_jitter(self):
        """Delay with jitter should stay within max_delay * 1.25."""
        random.seed(42)
        delay = calculate_backoff(20, base_delay=1.0, max_delay=30.0, jitter=True)
        assert delay <= 30.0 * 1.25

    def test_no_jitter(self):
        """Without jitter, delay should be exactly base_delay * 2^attempt."""
        delay = calculate_backoff(3, base_delay=2.0, max_delay=100.0, jitter=False)
        assert delay == 16.0  # 2.0 * 2^3

    def test_non_negative(self):
        """Delay should never be negative."""
        for attempt in range(10):
            delay = calculate_backoff(attempt)
            assert delay >= 0


class TestRetryWithBackoff:
    """Tests for the retry_with_backoff decorator."""

    def test_success_first_try(self):
        """Function succeeding on first try should not retry."""
        call_count = 0

        @retry_with_backoff(max_retries=3)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        assert succeed() == "ok"
        assert call_count == 1

    @patch("usf_fabric_cli.utils.retry.time.sleep")
    def test_success_after_retries(self, mock_sleep):
        """Function should succeed after transient failures."""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("429 rate limited")
            return "ok"

        assert flaky() == "ok"
        assert call_count == 3

    @patch("usf_fabric_cli.utils.retry.time.sleep")
    def test_exhausts_retries(self, mock_sleep):
        """Should raise after exhausting all retries."""
        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise Exception("503 Service Unavailable")

        with pytest.raises(Exception, match="503"):
            always_fail()
        assert call_count == 3  # 1 initial + 2 retries

    def test_non_retryable_not_retried(self):
        """Non-retryable errors should raise immediately."""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def permission_denied():
            nonlocal call_count
            call_count += 1
            raise Exception("Permission denied")

        with pytest.raises(Exception, match="Permission denied"):
            permission_denied()
        assert call_count == 1

    @patch("usf_fabric_cli.utils.retry.time.sleep")
    def test_custom_retryable_check(self, mock_sleep):
        """Custom retryable check should override default logic."""

        @retry_with_backoff(
            max_retries=2,
            base_delay=0.01,
            retryable_check=lambda e: "custom" in str(e),
        )
        def custom_retry():
            raise Exception("custom transient error")

        with pytest.raises(Exception, match="custom"):
            custom_retry()

    @patch("usf_fabric_cli.utils.retry.time.sleep")
    def test_on_retry_callback(self, mock_sleep):
        """on_retry callback should be called before each retry."""
        retry_log = []

        def log_retry(exc, attempt, delay):
            retry_log.append((str(exc), attempt))

        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.01, on_retry=log_retry)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("429 rate limited")
            return "ok"

        flaky()
        assert len(retry_log) == 2
        assert retry_log[0][1] == 0  # first retry attempt index
        assert retry_log[1][1] == 1  # second retry attempt index

    @patch("usf_fabric_cli.utils.retry.time.sleep")
    def test_on_retry_callback_failure_doesnt_break(self, mock_sleep):
        """A failing on_retry callback should not break the retry loop."""
        call_count = 0

        def bad_callback(exc, attempt, delay):
            raise RuntimeError("callback broke")

        @retry_with_backoff(max_retries=2, base_delay=0.01, on_retry=bad_callback)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("timeout")
            return "ok"

        assert flaky() == "ok"
        assert call_count == 2


class TestRetryRequest:
    """Tests for the retry_request convenience function."""

    @patch("usf_fabric_cli.utils.retry.requests.request")
    def test_success_first_try(self, mock_request):
        """Successful request should return response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        response = retry_request("GET", "https://api.example.com/data")

        assert response == mock_response
        assert mock_request.call_count == 1

    @patch("usf_fabric_cli.utils.retry.time.sleep")
    @patch("usf_fabric_cli.utils.retry.requests.request")
    def test_retries_on_transient_error(self, mock_request, mock_sleep):
        """Should retry on transient HTTP errors."""
        error_response = MagicMock()
        error_response.status_code = 503
        error_exc = requests.exceptions.HTTPError(response=error_response)

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.raise_for_status = MagicMock()

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise error_exc
            return success_response

        mock_request.side_effect = side_effect

        response = retry_request("GET", "https://api.example.com/data", max_retries=3)
        assert response == success_response
        assert call_count == 2

    @patch("usf_fabric_cli.utils.retry.requests.request")
    def test_non_retryable_raises_immediately(self, mock_request):
        """Should raise immediately on non-retryable errors (e.g. 403)."""
        error_response = MagicMock()
        error_response.status_code = 403
        error_exc = requests.exceptions.HTTPError(response=error_response)

        mock_request.side_effect = error_exc

        with pytest.raises(requests.exceptions.HTTPError):
            retry_request("GET", "https://api.example.com/data")
        assert mock_request.call_count == 1


if __name__ == "__main__":
    pytest.main([__file__])
