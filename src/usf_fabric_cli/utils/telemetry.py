"""Lightweight telemetry writer for Fabric CLI operations."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict

from usf_fabric_cli.exceptions import FabricTelemetryError

MAX_LOG_SIZE_BYTES = (
    int(os.getenv("FABRIC_TELEMETRY_MAX_MB", "50")) * 1024 * 1024
)


class TelemetryClient:
    """Writes Fabric CLI command telemetry to JSONL."""

    def __init__(
        self,
        log_directory: str | Path | None = None,
        enabled: bool | None = None,
    ):
        if enabled is False or os.getenv(
            "DISABLE_FABRIC_TELEMETRY", ""
        ) == "1":
            self._enabled = False
        else:
            self._enabled = True

        if log_directory:
            self._log_dir = Path(log_directory)
        else:
            self._log_dir = Path.home() / ".fabric-cli"

        self._log_file = (
            self._log_dir / "fabric_cli_telemetry.jsonl"
        )

    @property
    def _max_log_size(self) -> int:
        """Maximum log file size before rotation."""
        return MAX_LOG_SIZE_BYTES

    def _rotate_if_needed(self) -> None:
        """Rotate log file if it exceeds size threshold."""
        if (
            self._log_file.exists()
            and self._log_file.stat().st_size
            > self._max_log_size
        ):
            rotated = self._log_file.with_suffix(".jsonl.1")
            if rotated.exists():
                rotated.unlink()
            self._log_file.rename(rotated)

    def emit(self, **kwargs: Any) -> None:
        """Write a telemetry event as a JSONL line."""
        if not self._enabled:
            return

        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            self._rotate_if_needed()

            record: Dict[str, Any] = {
                "timestamp": datetime.now(
                    tz=UTC
                ).isoformat(),
                **kwargs,
            }
            with open(self._log_file, "a") as fh:
                fh.write(json.dumps(record) + "\n")
        except Exception as exc:
            raise FabricTelemetryError(
                f"Failed to write telemetry: {exc}"
            ) from exc
