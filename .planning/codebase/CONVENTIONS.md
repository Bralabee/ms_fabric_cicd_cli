# Coding Conventions

**Analysis Date:** 2026-02-26

## Naming Patterns

**Files:**
- Snake case with descriptive names: `config.py`, `fabric_wrapper.py`, `deployment_state.py`
- Exception files: `exceptions.py` (singular, contains multiple exception classes)
- Utility modules grouped by function: `utils/retry.py`, `utils/audit.py`, `utils/telemetry.py`
- Script files follow purpose: `scripts/admin/bulk_destroy.py`, `scripts/dev/generate_project.py`

**Functions:**
- Snake case throughout: `load_config()`, `is_retryable_error()`, `calculate_backoff()`
- Helper functions prefixed with underscore: `_substitute_env_vars()`, `_load_schema()`, `_merge_configs()`
- Boolean check functions: `is_*()` pattern for predicates (`is_retryable_exception()`, `is_retryable_http_status()`)
- Callback/handler functions: `on_retry()` pattern

**Variables:**
- Snake case for all local and instance variables: `config_path`, `error_message`, `max_retries`
- Constants: UPPER_SNAKE_CASE: `DEFAULT_MAX_RETRIES`, `DEFAULT_BASE_DELAY`, `RETRYABLE_ERROR_PATTERNS`
- Private/internal variables: Leading underscore: `_token_manager`, `_effective_workspace_name`, `_git_browse_url`
- Temporary variables with clear purpose: `call_count`, `retry_log`, `mock_sleep`

**Types:**
- Type hints used throughout (from `__future__ import annotations` for forward references)
- Generic types: `T = TypeVar("T")` for decorator generics
- Optional/Union types: `Optional[str]`, `Dict[str, Any]`, `List[Dict[str, Any]]`
- Dataclasses: `WorkspaceConfig` uses `@dataclass` decorator with type annotations

## Code Style

**Formatting:**
- Tool: Black (configured in `pyproject.toml`)
- Line length: 88 characters
- Target version: Python 3.11
- Format enforced via pre-commit hooks and CI pipeline

**Linting:**
- Tool: Flake8 with plugins (flake8-bugbear, flake8-comprehensions)
- Max line length: 88 (matches Black)
- Ignored rules: E203 (whitespace before colon), W503 (line break before binary operator), B008 (function calls in defaults, allowed for Typer)
- Scope: `src/` directory only

**Import Sorting:**
- Tool: isort with Black-compatible profile
- Line length: 88
- Configured in `pyproject.toml`

## Import Organization

**Order:**
1. Future imports: `from __future__ import annotations`
2. Standard library: `import os`, `from pathlib import Path`, `import json`
3. Third-party: `import yaml`, `from rich.console import Console`, `import requests`
4. Local application: `from usf_fabric_cli.utils.config import ConfigManager`

**Path Aliases:**
- No path aliases defined; absolute imports from package root used consistently
- Imports reference full package path: `from usf_fabric_cli.services.deployer import FabricDeployer`
- Lazy imports used in `__init__.py` to avoid circular dependencies and improve load time

**Example from `src/usf_fabric_cli/__init__.py`:**
```python
def __getattr__(name):
    """Lazy import main components."""
    if name == "app":
        from usf_fabric_cli.cli import app
        return app
```

## Error Handling

**Patterns:**

1. **Custom Exception Classes:** All in `src/usf_fabric_cli/exceptions.py`
   - `FabricCLIError`: Base exception for CLI failures with command, exit_code, stderr, stdout
   - `FabricCLINotFoundError`: Raised when Fabric CLI binary not on PATH (exit code 127)
   - `FabricTelemetryError`: Raised when telemetry logging itself fails
   - Custom exceptions inherit from appropriate base class (RuntimeError for CLI errors)

2. **Try-Except Blocks:** Used for expected failures:
   ```python
   try:
       self.secrets = FabricSecrets.load_with_fallback()
       is_valid, error_msg = self.secrets.validate_fabric_auth()
       if not is_valid:
           raise ValueError(error_msg)
   except ImportError:
       env_vars = get_environment_variables()
       self.secrets = None
   ```

3. **Validation Pattern:** Check first, fail early:
   ```python
   if not self.config_path.exists():
       raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
   ```

4. **Error Message Format:** Include context and action items:
   ```python
   message = (
       f"Fabric CLI command failed (exit {exit_code}): {' '.join(command)}\n"
       f"stderr: {self.stderr or 'n/a'}"
   )
   ```

5. **Retryable Error Detection:** Centralized in `src/usf_fabric_cli/utils/retry.py`
   - `is_retryable_exception()`: Checks exception type + message patterns
   - `is_retryable_http_status()`: Specific status codes (401, 429, 502, 503, 504)
   - `is_retryable_error()`: Pattern matching on error messages (case-insensitive)

## Logging

**Framework:** Python's standard `logging` module

**Setup Pattern:**
```python
import logging
logger = logging.getLogger(__name__)
```

**When to Log:**
- Entry/exit of major operations: `logger.info("Loading configuration...")`
- Configuration resolution: `logger.info("Applying inline environment override: %s", environment)`
- Warnings for fallbacks: `logger.warning("Unresolved variable in %s: %s", path, obj)`
- Debug for detailed tracing (not commonly used, but `logger.debug()` available)
- Error conditions: `logger.error()` before raising exceptions (optional, not enforced)

**Log Levels Used:**
- `logger.info()`: Normal operation flow, config decisions
- `logger.warning()`: Unexpected but recoverable situations (unresolved vars, fallbacks)
- `logger.debug()`: Detailed diagnostic info (used sparingly)

**Example from `src/usf_fabric_cli/utils/config.py`:**
```python
logger.info("Applying inline environment override: %s", environment)
logger.warning(
    "Unresolved variable in %s%s: %s — "
    "check that the env var is set in .env or CI/CD secrets",
    f"{context} " if context else "",
    path,
    obj,
)
```

## Comments

**When to Comment:**
- Non-obvious logic or complex algorithms
- Workarounds for quirks: `# Fallback syntax: ${VAR:-FALLBACK_VAR}`
- Important constraints: `# Limit depth` when walking directory tree
- Design decisions: `# Let validation catch it or leave as is`

**JSDoc/Docstring Pattern:**
- Module docstring: Describes module purpose, ~2-3 sentences
- Class docstring: One-liner or short description
- Function docstring: One-liner for simple functions, full signature + description for complex ones
- Docstring format: Triple quotes with optional Args/Returns sections for complex functions

**Examples:**

Module docstring (`src/usf_fabric_cli/utils/retry.py`):
```python
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
```

Function docstring:
```python
def is_retryable_error(error_message: str) -> bool:
    """
    Check if an error message indicates a transient, retryable failure.

    Args:
        error_message: Error message to analyze

    Returns:
        True if error appears retryable
    """
```

Class docstring:
```python
class ConfigManager:
    """Manages configuration loading and validation"""
```

## Function Design

**Size:** Functions typically 20-50 lines; longer functions broken into helper methods
- `ConfigManager.load_config()`: 43 lines, handles multi-step process
- `_substitute_env_vars()`: 45 lines for complex regex substitution
- Helper functions kept under 30 lines

**Parameters:**
- Prefer explicit parameters over *args/**kwargs (except for decorators)
- Optional parameters use type hints: `Optional[str] = None`
- No more than 5 positional parameters; use configuration objects for many options
- Callbacks as optional functions: `on_retry: Optional[Callable] = None`

**Return Values:**
- Always return explicit types (not implicit None unless Optional)
- Multiple return values as tuples or dataclasses: `(is_valid, error_msg)` or `WorkspaceConfig`
- Avoid returning None implicitly; if method can return None, mark as `Optional`

## Module Design

**Exports:**
- Explicit `__all__` in modules that serve as interfaces:
```python
__all__ = [
    "app",
    "FabricDeployer",
    "FabricCLIError",
    "FabricCLINotFoundError",
    "__version__",
]
```

**Barrel Files (Package Init Files):**
- `src/usf_fabric_cli/__init__.py`: Lazy-loads main components, provides version
- `src/usf_fabric_cli/utils/__init__.py`: Empty (modules imported directly)
- `src/usf_fabric_cli/services/__init__.py`: Empty (modules imported directly)
- Pattern: Lazy imports in main `__init__.py` to avoid circular dependencies, direct imports elsewhere

**Private Modules:**
- Underscore prefix for private implementation details
- Internal helper modules: `_migrate_v1_to_v2.py` pattern (not used; example only)

**Dependency Direction:**
- Utils depend on nothing (no dependencies on services or CLI)
- Services depend on utils and exceptions
- CLI depends on services
- No circular imports

---

*Convention analysis: 2026-02-26*
