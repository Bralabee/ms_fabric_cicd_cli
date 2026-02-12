"""
Audit Logging - Thin Wrapper Component 4/5
~30 LOC - Compliance-ready audit trail

Key Learning Applied: Compliance Requirements
- JSONL format for easy parsing
- Operation tracking for audit trails
- Minimal overhead, maximum compliance value
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
import os


class AuditLogger:
    """Lightweight audit logging for compliance"""

    def __init__(self, log_directory: str = "audit_logs"):
        self.log_directory = Path(log_directory)
        self.log_directory.mkdir(exist_ok=True)

        # Create audit log file with date
        date_str = datetime.now().strftime("%Y-%m-%d")
        self.log_file = self.log_directory / f"fabric_operations_{date_str}.jsonl"

        # Setup logging
        self.logger = logging.getLogger("fabric_audit")
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_file)
            formatter = logging.Formatter("%(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def log_operation(
        self,
        operation: str,
        workspace_id: Optional[str] = None,
        workspace_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Log a Fabric operation for audit trail"""

        audit_record = {
            "timestamp": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "operation": operation,
            "workspace_id": workspace_id,
            "workspace_name": workspace_name,
            "success": success,
            "user": os.getenv("USER", "unknown"),
            "details": details or {},
        }

        if error:
            audit_record["error"] = error

        # Log as JSONL (one JSON object per line)
        self.logger.info(json.dumps(audit_record))

    def log_workspace_creation(
        self,
        workspace_name: str,
        workspace_id: Optional[str],
        capacity_id: str,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Log workspace creation"""
        self.log_operation(
            operation="workspace_create",
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            details={"capacity_id": capacity_id},
            success=success,
            error=error,
        )

    def log_item_creation(
        self,
        item_type: str,
        item_name: str,
        workspace_id: str,
        workspace_name: str,
        folder_name: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Log item creation (lakehouse, warehouse, notebook, etc.)"""
        details = {"item_type": item_type, "item_name": item_name}
        if folder_name:
            details["folder_name"] = folder_name

        self.log_operation(
            operation="item_create",
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            details=details,
            success=success,
            error=error,
        )

    def log_principal_assignment(
        self,
        principal_id: str,
        role: str,
        workspace_id: str,
        workspace_name: str,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Log principal assignment to workspace"""
        self.log_operation(
            operation="principal_assign",
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            details={"principal_id": principal_id, "role": role},
            success=success,
            error=error,
        )

    def log_git_connection(
        self,
        git_repo: str,
        branch: str,
        workspace_id: str,
        workspace_name: str,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Log Git repository connection"""
        self.log_operation(
            operation="git_connect",
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            details={"git_repo": git_repo, "branch": branch},
            success=success,
            error=error,
        )

    def log_deployment_start(
        self, config_file: str, environment: Optional[str], branch: Optional[str] = None
    ) -> None:
        """Log start of deployment"""
        details = {"config_file": config_file, "environment": environment}
        if branch:
            details["branch"] = branch

        self.log_operation(operation="deployment_start", details=details)

    def log_deployment_complete(
        self,
        workspace_name: str,
        workspace_id: Optional[str],
        items_created: int,
        duration_seconds: float,
    ) -> None:
        """Log completion of deployment"""
        self.log_operation(
            operation="deployment_complete",
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            details={
                "items_created": items_created,
                "duration_seconds": round(duration_seconds, 2),
            },
        )

    def get_audit_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get audit summary by parsing recent JSONL log files."""
        from datetime import timedelta

        summary: Dict[str, Any] = {
            "audit_log_file": str(self.log_file),
            "format": "JSONL - one JSON record per line",
            "retention": f"Logs older than {days} days should be archived",
        }

        cutoff = datetime.now() - timedelta(days=days)
        total_ops = 0
        successes = 0
        failures = 0
        operations: Dict[str, int] = {}

        for log_path in sorted(self.log_directory.glob("fabric_operations_*.jsonl")):
            # Parse date from filename: fabric_operations_YYYY-MM-DD.jsonl
            try:
                date_str = log_path.stem.replace("fabric_operations_", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff:
                    continue
            except ValueError:
                continue

            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                            total_ops += 1
                            op = record.get("operation", "unknown")
                            operations[op] = operations.get(op, 0) + 1
                            if record.get("success", True):
                                successes += 1
                            else:
                                failures += 1
                        except json.JSONDecodeError:
                            continue
            except OSError:
                continue

        summary["total_operations"] = total_ops
        summary["successes"] = successes
        summary["failures"] = failures
        summary["operations_by_type"] = operations
        summary["period_days"] = days

        return summary
