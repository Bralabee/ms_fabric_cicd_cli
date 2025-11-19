"""Custom exception types for Fabric CLI orchestration."""

from __future__ import annotations

from typing import List


class FabricCLIError(RuntimeError):
    """Base exception for Fabric CLI execution failures."""

    def __init__(self, command: List[str], exit_code: int, stderr: str | None = None, stdout: str | None = None):
        self.command = command
        self.exit_code = exit_code
        self.stderr = (stderr or "").strip()
        self.stdout = (stdout or "").strip()
        message = (
            f"Fabric CLI command failed (exit {exit_code}): {' '.join(command)}\n"
            f"stderr: {self.stderr or 'n/a'}"
        )
        super().__init__(message)


class FabricCLINotFoundError(FabricCLIError):
    """Raised when the Fabric CLI binary cannot be located."""

    def __init__(self, command: List[str]):
        super().__init__(command=command, exit_code=127, stderr="Fabric CLI binary not found on PATH")


class FabricTelemetryError(RuntimeError):
    """Raised when telemetry logging itself fails."""

    def __init__(self, message: str):
        super().__init__(message)
