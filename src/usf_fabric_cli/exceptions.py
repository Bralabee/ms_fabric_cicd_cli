"""Custom exception types for Fabric CLI orchestration."""

from __future__ import annotations

from typing import List, NoReturn, Optional

from rich.console import Console

console = Console()


class FabricCLIError(RuntimeError):
    """Base exception for Fabric CLI execution failures."""

    def __init__(
        self,
        command: List[str],
        exit_code: int,
        stderr: str | None = None,
        stdout: str | None = None,
    ):
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
        super().__init__(
            command=command, exit_code=127, stderr="Fabric CLI binary not found on PATH"
        )


class FabricTelemetryError(RuntimeError):
    """Raised when telemetry logging itself fails."""

    def __init__(self, message: str):
        super().__init__(message)


def handle_cli_error(
    operation: str, error: Exception | str, suggestion: Optional[str] = None
) -> NoReturn:
    """
    Standardize CLI error output.
    1. What failed (operation)
    2. Why it failed (from error)
    3. What to do next (suggestion)
    """
    import typer

    console.print(f"[red]❌ Failed to {operation}[/red]")
    console.print(f"   [red]Reason: {error}[/red]")
    if suggestion:
        console.print(f"\n[yellow]💡 Suggested Action: {suggestion}[/yellow]")
    raise typer.Exit(1)
