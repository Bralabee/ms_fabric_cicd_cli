"""Lightweight telemetry writer for Fabric CLI operations."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict

from usf_fabric_cli.exceptions import FabricTelemetryError


class TelemetryClient:
    """Writes Fabric CLI command telemetry to JSONL for later analysis."""

    def __init__(
        self, log_directory: str | Path | None = None, enabled: bool | None = None
    ):
        self._log_dir = Path(log_directory or "audit_logs")
        env_override = os.getenv("DISABLE_FABRIC_TELEMETRY")
        self.enabled = (
            enabled if enabled is not None else True
        ) and env_override != "1"
        self._log_file = self._log_dir / "fabric_cli_telemetry.jsonl"
        if self.enabled:
            self._log_dir.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, payload: Dict[str, Any]) -> None:
        if not self.enabled:
            return

        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            **payload,
        }

        try:
            with self._log_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry))
                handle.write("\n")
        except OSError as exc:
            raise FabricTelemetryError(f"Failed to write telemetry: {exc}") from exc
