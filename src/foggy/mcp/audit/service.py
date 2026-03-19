"""Tool audit service for logging tool executions."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import json


class AuditLogLevel(str, Enum):
    """Audit log level."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class AuditEventType(str, Enum):
    """Audit event types."""

    TOOL_CALL = "tool_call"
    TOOL_SUCCESS = "tool_success"
    TOOL_FAILURE = "tool_failure"
    QUERY_EXECUTE = "query_execute"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    ACCESS_DENIED = "access_denied"


class ToolAuditLog(BaseModel):
    """Audit log entry for tool execution."""

    # Identification
    log_id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex, description="Unique log ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="Log timestamp")

    # Event info
    event_type: AuditEventType = Field(..., description="Event type")
    level: AuditLogLevel = Field(default=AuditLogLevel.INFO, description="Log level")

    # Tool info
    tool_name: str = Field(..., description="Tool name")
    tool_version: Optional[str] = Field(default=None, description="Tool version")
    tool_category: Optional[str] = Field(default=None, description="Tool category")

    # User context
    user_id: Optional[str] = Field(default=None, description="User ID")
    user_name: Optional[str] = Field(default=None, description="User name")
    user_roles: List[str] = Field(default_factory=list, description="User roles")
    session_id: Optional[str] = Field(default=None, description="Session ID")

    # Request info
    request_id: Optional[str] = Field(default=None, description="Request ID")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments (sanitized)")
    client_ip: Optional[str] = Field(default=None, description="Client IP")

    # Result info
    success: bool = Field(default=False, description="Whether execution succeeded")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    error_code: Optional[int] = Field(default=None, description="Error code if failed")

    # Performance
    duration_ms: Optional[float] = Field(default=None, description="Execution duration in ms")

    # Additional data
    result_summary: Optional[str] = Field(default=None, description="Summary of result")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = {"extra": "allow"}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "log_id": self.log_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "level": self.level.value,
            "tool_name": self.tool_name,
            "user_id": self.user_id,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class ToolAuditService:
    """Service for recording and managing tool audit logs."""

    def __init__(
        self,
        max_logs: int = 10000,
        retention_hours: int = 168,  # 7 days
        sanitize_fields: Optional[List[str]] = None
    ):
        """Initialize the audit service."""
        self._logs: List[ToolAuditLog] = []
        self._max_logs = max_logs
        self._retention_hours = retention_hours
        self._sanitize_fields = sanitize_fields or [
            "password", "secret", "token", "api_key", "credential"
        ]
        self._handlers: List[Any] = []

    def add_handler(self, handler: Any) -> None:
        """Add a log handler (e.g., file logger, external system)."""
        self._handlers.append(handler)

    def remove_handler(self, handler: Any) -> None:
        """Remove a log handler."""
        if handler in self._handlers:
            self._handlers.remove(handler)

    def _sanitize_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize sensitive fields from arguments."""
        sanitized = {}
        for key, value in arguments.items():
            # Check if key contains sensitive field names
            key_lower = key.lower()
            if any(field in key_lower for field in self._sanitize_fields):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_arguments(value)
            else:
                sanitized[key] = value
        return sanitized

    def log_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_roles: Optional[List[str]] = None,
    ) -> str:
        """Log a tool call start and return the log ID."""
        log = ToolAuditLog(
            event_type=AuditEventType.TOOL_CALL,
            level=AuditLogLevel.INFO,
            tool_name=tool_name,
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            client_ip=client_ip,
            user_roles=user_roles or [],
            arguments=self._sanitize_arguments(arguments),
            success=False,  # Will be updated on completion
        )

        self._add_log(log)
        self._notify_handlers(log)

        return log.log_id

    def log_tool_success(
        self,
        log_id: str,
        duration_ms: float,
        result_summary: Optional[str] = None,
    ) -> None:
        """Log successful tool execution."""
        log = self._find_log(log_id)
        if log:
            log.event_type = AuditEventType.TOOL_SUCCESS
            log.success = True
            log.duration_ms = duration_ms
            log.result_summary = result_summary
            self._notify_handlers(log)

    def log_tool_failure(
        self,
        log_id: str,
        error_message: str,
        error_code: Optional[int] = None,
        duration_ms: Optional[float] = None,
    ) -> None:
        """Log failed tool execution."""
        log = self._find_log(log_id)
        if log:
            log.event_type = AuditEventType.TOOL_FAILURE
            log.level = AuditLogLevel.ERROR
            log.success = False
            log.error_message = error_message
            log.error_code = error_code
            log.duration_ms = duration_ms
            self._notify_handlers(log)

    def _add_log(self, log: ToolAuditLog) -> None:
        """Add a log entry, managing max size."""
        self._logs.append(log)

        # Trim if over limit
        if len(self._logs) > self._max_logs:
            self._logs = self._logs[-self._max_logs:]

        # Clean old logs based on retention
        self._clean_old_logs()

    def _find_log(self, log_id: str) -> Optional[ToolAuditLog]:
        """Find a log by ID."""
        for log in self._logs:
            if log.log_id == log_id:
                return log
        return None

    def _clean_old_logs(self) -> None:
        """Remove logs older than retention period."""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=self._retention_hours)
        self._logs = [log for log in self._logs if log.timestamp >= cutoff]

    def _notify_handlers(self, log: ToolAuditLog) -> None:
        """Notify all handlers of a new log."""
        for handler in self._handlers:
            try:
                if hasattr(handler, "handle"):
                    handler.handle(log)
            except Exception:
                pass  # Don't fail on handler errors

    def get_logs(
        self,
        tool_name: Optional[str] = None,
        user_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        success: Optional[bool] = None,
        limit: int = 100,
    ) -> List[ToolAuditLog]:
        """Query audit logs with optional filters."""
        logs = self._logs

        if tool_name:
            logs = [l for l in logs if l.tool_name == tool_name]
        if user_id:
            logs = [l for l in logs if l.user_id == user_id]
        if event_type:
            logs = [l for l in logs if l.event_type == event_type]
        if success is not None:
            logs = [l for l in logs if l.success == success]

        # Sort by timestamp descending
        logs = sorted(logs, key=lambda l: l.timestamp, reverse=True)

        return logs[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get audit statistics."""
        total = len(self._logs)
        successful = sum(1 for l in self._logs if l.success)
        failed = total - successful

        # Group by tool
        tools: Dict[str, int] = {}
        for log in self._logs:
            tools[log.tool_name] = tools.get(log.tool_name, 0) + 1

        return {
            "total_calls": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 0,
            "tools": tools,
        }


class FileAuditHandler:
    """Handler for writing audit logs to a file."""

    def __init__(self, file_path: str):
        """Initialize with file path."""
        self._file_path = file_path

    def handle(self, log: ToolAuditLog) -> None:
        """Write log to file."""
        import os
        from datetime import datetime

        # Ensure directory exists
        os.makedirs(os.path.dirname(self._file_path), exist_ok=True)

        # Append log to file
        with open(self._file_path, "a", encoding="utf-8") as f:
            f.write(log.to_json() + "\n")