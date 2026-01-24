"""
Retry utilities with exponential backoff.

Provides retry logic for transient errors in API calls and CLI operations.
Extracted from fabric_wrapper.py for shared use across components.

Key Features:
- Exponential backoff with configurable base/max delay
- Jitter to prevent thundering herd
- Customizable retryable error detection
- Decorator for easy application to functions
"""

import logging
import random
import time
from functools import wraps
from typing import Any, Callable, List, Optional, TypeVar

import requests

logger = logging.getLogger(__name__)

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0  # seconds
DEFAULT_MAX_DELAY = 30.0  # seconds

# Error patterns that indicate transient, retryable failures
RETRYABLE_ERROR_PATTERNS = [
    "rate limit",
    "429",
    "503",
    "service unavailable",
    "temporarily unavailable",
    "connection reset",
    "connection refused",
    "timeout",
    "timed out",
    "throttl",
    "too many requests",
    "server busy",
]

T = TypeVar("T")


def is_retryable_error(error_message: str) -> bool:
    """
    Check if an error message indicates a transient, retryable failure.
    
    Args:
        error_message: Error message to analyze
        
    Returns:
        True if error appears retryable
    """
    error_lower = error_message.lower()
    return any(pattern in error_lower for pattern in RETRYABLE_ERROR_PATTERNS)


def is_retryable_http_status(status_code: int) -> bool:
    """
    Check if an HTTP status code indicates a retryable error.
    
    Args:
        status_code: HTTP status code
        
    Returns:
        True if status code is retryable (429, 503, 502, 504)
    """
    return status_code in (429, 502, 503, 504)


def is_retryable_exception(exception: Exception) -> bool:
    """
    Check if an exception is retryable.
    
    Handles both requests exceptions and general exceptions with
    retryable error patterns.
    
    Args:
        exception: Exception to analyze
        
    Returns:
        True if exception appears retryable
    """
    # Check for requests HTTP errors with retryable status codes
    if isinstance(exception, requests.exceptions.HTTPError):
        if hasattr(exception, "response") and exception.response is not None:
            return is_retryable_http_status(exception.response.status_code)
    
    # Check for connection/timeout errors
    if isinstance(exception, (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
    )):
        return True
    
    # Fall back to error message pattern matching
    return is_retryable_error(str(exception))


def calculate_backoff(
    attempt: int,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    jitter: bool = True,
) -> float:
    """
    Calculate exponential backoff delay with optional jitter.
    
    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        jitter: Whether to add random jitter (±25%)
        
    Returns:
        Delay in seconds
    """
    delay = min(base_delay * (2 ** attempt), max_delay)
    
    if jitter:
        # Add jitter (±25%) to prevent thundering herd
        jitter_range = delay * 0.25
        delay = delay + (2 * random.random() - 1) * jitter_range
    
    return max(0, delay)


def retry_with_backoff(
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    retryable_check: Optional[Callable[[Exception], bool]] = None,
    on_retry: Optional[Callable[[Exception, int, float], None]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying functions with exponential backoff.
    
    Retries the decorated function when a retryable exception occurs,
    using exponential backoff between attempts.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay between retries in seconds (default: 1.0)
        max_delay: Maximum delay between retries in seconds (default: 30.0)
        retryable_check: Custom function to determine if exception is retryable
        on_retry: Optional callback(exception, attempt, delay) called before retry
        
    Returns:
        Decorated function with retry logic
        
    Example:
        @retry_with_backoff(max_retries=5, base_delay=2.0)
        def call_api():
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_str = str(e)
                    
                    # Check if error is retryable
                    should_retry = (
                        retryable_check(e) if retryable_check
                        else is_retryable_exception(e)
                    )
                    
                    if not should_retry or attempt >= max_retries:
                        raise
                    
                    delay = calculate_backoff(attempt, base_delay, max_delay)
                    
                    logger.warning(
                        "Retryable error on attempt %d/%d: %s. Retrying in %.2fs...",
                        attempt + 1,
                        max_retries + 1,
                        error_str,
                        delay,
                    )
                    
                    # Call optional retry callback
                    if on_retry:
                        try:
                            on_retry(e, attempt, delay)
                        except Exception:
                            pass  # Don't let callback failures break retry
                    
                    time.sleep(delay)
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry loop completed without returning or raising")
        
        return wrapper
    return decorator


def retry_request(
    method: str,
    url: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    **request_kwargs: Any,
) -> requests.Response:
    """
    Make an HTTP request with automatic retry on transient failures.
    
    Convenience function for one-off retried requests without decorating
    a function.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        url: Request URL
        max_retries: Maximum retry attempts
        base_delay: Initial backoff delay
        max_delay: Maximum backoff delay
        **request_kwargs: Additional arguments passed to requests.request()
        
    Returns:
        Response object
        
    Raises:
        requests.RequestException: If all retries fail
    """
    last_exception: Optional[Exception] = None
    
    for attempt in range(max_retries + 1):
        try:
            response = requests.request(method, url, **request_kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            last_exception = e
            
            if not is_retryable_exception(e) or attempt >= max_retries:
                raise
            
            delay = calculate_backoff(attempt, base_delay, max_delay)
            logger.warning(
                "Request failed (attempt %d/%d): %s. Retrying in %.2fs...",
                attempt + 1,
                max_retries + 1,
                str(e),
                delay,
            )
            time.sleep(delay)
    
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry loop completed without returning or raising")
