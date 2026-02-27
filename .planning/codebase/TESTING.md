# Testing Patterns

**Analysis Date:** 2026-02-26

## Test Framework

**Runner:**
- pytest (configured in `pytest.ini`)
- Config: `pytest.ini` at project root
- Python path: `src/` directory for importing source modules

**Assertion Library:**
- pytest built-in assertions: `assert value == expected`
- `pytest.raises()` for exception testing: `with pytest.raises(Exception, match="pattern"):`

**Run Commands:**
```bash
make test                           # Run unit tests (excludes integration)
make test-integration              # Run integration tests (slow, requires Fabric CLI)
make coverage                       # Generate coverage report
pytest tests/                       # Run all tests
pytest tests/ -m "not integration"  # Exclude integration tests
pytest tests/test_config.py         # Run single file
pytest tests/test_config.py::test_load_basic_config  # Run single test
```

## Test File Organization

**Location:**
- Co-located in `tests/` directory (parallel to `src/`)
- Subdirectories: `tests/integration/` for integration tests, `tests/` for unit tests
- Structure mirrors `src/` loosely (not strict requirement)

**Naming:**
- Test files: `test_*.py` (e.g., `test_config.py`, `test_retry.py`)
- Test functions: `test_*()` (e.g., `test_load_basic_config()`)
- Test classes: `Test*` (e.g., `TestIsRetryableError()`)
- Fixtures/helpers: Functions in `conftest.py` or test module

**Structure:**
```
tests/
├── conftest.py                      # Shared fixtures, path setup
├── test_config.py                   # Tests for src/usf_fabric_cli/utils/config.py
├── test_retry.py                    # Tests for src/usf_fabric_cli/utils/retry.py
├── test_deployer.py                 # Tests for src/usf_fabric_cli/services/deployer.py
├── integration/
│   ├── __init__.py
│   ├── test_promote_e2e.py         # End-to-end promotion tests
│   └── test_diagnostics.py         # Integration diagnostics
└── ... (other test files)
```

## Test Structure

**Suite Organization:**

Test files use class-based organization for grouped related tests:

```python
class TestIsRetryableError:
    """Tests for error message pattern matching."""

    @pytest.mark.parametrize(
        "error_msg",
        [
            "Rate limit exceeded",
            "Error 429: Too Many Requests",
            # ... more error patterns
        ],
    )
    def test_retryable_patterns(self, error_msg):
        """All known retryable error patterns should be detected."""
        assert is_retryable_error(error_msg) is True
```

**Patterns:**

1. **Setup:**
   - Module-level fixtures in `conftest.py` (path setup)
   - Per-test temporary directories: `tmp_path` (pytest built-in)
   - Mock setup in test function using `@patch()` decorator
   - Helper functions for complex object construction (e.g., `_make_config()`)

   Example from `tests/test_deployer.py`:
   ```python
   def _make_config(**overrides):
       """Return a minimal config SimpleNamespace mirroring ConfigManager output."""
       defaults = {
           "name": "test-workspace",
           "display_name": "Test Workspace",
           # ... more defaults
       }
       defaults.update(overrides)
       return SimpleNamespace(**defaults)
   ```

2. **Teardown:**
   - Automatic via `tmp_path` fixture (cleaned up after test)
   - Manual cleanup in finally blocks when needed:
     ```python
     try:
         # ... test code
     finally:
         Path(config_path).unlink()
     ```

3. **Assertion Pattern:**
   - Direct equality assertions: `assert workspace_config.name == "test-workspace"`
   - Collection checks: `assert "Bronze" in workspace_config.folders`
   - Length checks: `assert len(lines) == 1`
   - Exception matching: `with pytest.raises(Exception, match="pattern"):`
   - Boolean equality: `assert is_retryable_error(error_msg) is True`

## Mocking

**Framework:** `unittest.mock` (Python standard library)

**Patterns:**

1. **Function Mocking with @patch():**
   ```python
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
   ```

2. **Object Creation with MagicMock():**
   ```python
   response = MagicMock()
   response.status_code = 429
   exc = requests.exceptions.HTTPError(response=response)
   assert is_retryable_exception(exc) is True
   ```

3. **Side Effects for Sequence Control:**
   ```python
   def side_effect(*args, **kwargs):
       nonlocal call_count
       call_count += 1
       if call_count < 2:
           raise error_exc
       return success_response

   mock_request.side_effect = side_effect
   ```

4. **Multiple Nested Patches:**
   ```python
   with patch("module1.func1") as mock1:
       with patch("module2.func2") as mock2:
           # test code
   ```
   (Used in `tests/test_deployer.py` for complex dependency chains)

**What to Mock:**
- External dependencies: HTTP requests, file system access, subprocess calls
- Side effects: time.sleep (for faster tests), system time
- APIs: Azure, Microsoft Fabric, Git operations
- Heavy I/O: Database calls, network requests

**What NOT to Mock:**
- Core business logic under test
- Standard library utilities (os.path, json parsing)
- Pure functions (avoid mocking unless necessary for performance)
- Exception types (raise real exceptions)

## Fixtures and Factories

**Test Data:**

1. **Parametrized Tests for Multiple Inputs:**
   ```python
   @pytest.mark.parametrize("code", [401, 429, 502, 503, 504])
   def test_retryable_status_codes(self, code):
       """401 (token refresh), 429, 502, 503, 504 should be retryable."""
       assert is_retryable_http_status(code) is True
   ```

2. **Temporary Files/Directories:**
   ```python
   def test_emit_writes_valid_jsonl(self, tmp_path):
       """emit() should write a valid JSONL line."""
       client = TelemetryClient(log_directory=str(tmp_path))
       client.emit(command="deploy", status="success")

       log_file = tmp_path / "fabric_cli_telemetry.jsonl"
       assert log_file.exists()
   ```

3. **Config Builders (Helper Functions):**
   ```python
   def test_load_basic_config():
       config_data = {
           "workspace": {"name": "test-workspace", "capacity_id": "F64"},
           "folders": ["Bronze", "Silver", "Gold"],
       }

       with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
           yaml.dump(config_data, f)
           config_path = f.name
   ```

**Location:**
- Shared fixtures: `tests/conftest.py`
- Test-specific helpers: Defined in test module or test class
- Complex builders: Defined as helper functions in test module with `_` prefix

**From `tests/conftest.py`:**
```python
"""Pytest configuration for locating the src package."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

for path in (PROJECT_ROOT, SRC_PATH):
    str_path = str(path)
    if str_path not in sys.path:
        sys.path.insert(0, str_path)
```

## Coverage

**Requirements:** No enforced minimum, but coverage tracked

**View Coverage:**
```bash
make coverage              # Generate HTML coverage report
coverage report            # Terminal report
coverage html             # Creates htmlcov/index.html
```

**Coverage Configuration:**
- Tracked via `.coverage` file (pytest-cov)
- Integration tests can be excluded from coverage (slow)

## Test Types

**Unit Tests:**
- Scope: Single function/method in isolation
- Mocking: All external dependencies mocked
- Speed: Fast (< 1 second each)
- Location: `tests/test_*.py` (e.g., `tests/test_retry.py`)
- Examples:
  - `test_retryable_patterns()`: Tests error message matching
  - `test_exponential_growth()`: Tests backoff calculation
  - `test_load_basic_config()`: Tests config loading without env vars

**Integration Tests:**
- Scope: Multiple components working together
- Mocking: Minimal; uses real objects where possible (file I/O, config loading)
- Speed: Slower, may require external CLI binaries
- Location: `tests/integration/` (e.g., `tests/integration/test_promote_e2e.py`)
- Marked with `@pytest.mark.integration` to allow selective exclusion:
  ```bash
  pytest tests/ -m "not integration"  # Skip integration tests
  ```
- Configuration in `pytest.ini`:
  ```
  markers =
      integration: marks tests that hit the Fabric CLI binary
  ```

**E2E Tests:**
- Not formalized; integration tests serve this purpose
- Would require full Fabric environment (workspace, capacity, credentials)

## Common Patterns

**Async Testing:**
- Not used (no async code in project)
- Would use `pytest-asyncio` if needed

**Error Testing:**

1. **Exception Type + Message:**
   ```python
   with pytest.raises(Exception, match="503"):
       always_fail()
   ```

2. **Non-Retryable Exceptions Fail Immediately:**
   ```python
   def test_non_retryable_not_retried(self):
       """Non-retryable errors should raise immediately."""
       call_count = 0

       @retry_with_backoff(max_retries=3)
       def permission_denied():
           nonlocal call_count
           call_count += 1
           raise Exception("Permission denied")

       with pytest.raises(Exception, match="Permission denied"):
           permission_denied()
       assert call_count == 1  # No retries
   ```

3. **Custom Retryable Check:**
   ```python
   @retry_with_backoff(
       max_retries=2,
       retryable_check=lambda e: "custom" in str(e),
   )
   def custom_retry():
       raise Exception("custom transient error")
   ```

**Callback Testing:**
```python
def test_on_retry_callback(self, mock_sleep):
    """on_retry callback should be called before each retry."""
    retry_log = []

    def log_retry(exc, attempt, delay):
        retry_log.append((str(exc), attempt))

    @retry_with_backoff(max_retries=2, on_retry=log_retry)
    def flaky():
        # ... implementation

    flaky()
    assert len(retry_log) == 2  # Called twice (not on first failure)
    assert retry_log[0][1] == 0  # First retry attempt index
```

**Callback Resilience:**
```python
def test_on_retry_callback_failure_doesnt_break(self, mock_sleep):
    """A failing on_retry callback should not break the retry loop."""
    call_count = 0

    def bad_callback(exc, attempt, delay):
        raise RuntimeError("callback broke")

    @retry_with_backoff(max_retries=2, on_retry=bad_callback)
    def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise Exception("timeout")
        return "ok"

    assert flaky() == "ok"  # Still succeeds despite bad callback
    assert call_count == 2
```

---

*Testing analysis: 2026-02-26*
