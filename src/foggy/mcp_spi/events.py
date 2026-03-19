"""Progress events for MCP tools."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class ProgressStatus(Enum):
    """Progress status enumeration."""

    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressEvent:
    """Progress event for tool execution tracking.

    Tools can emit progress events to report status during
    long-running operations.
    """

    # Event identification
    event_id: str
    tool_name: str
    request_id: str

    # Progress info
    status: ProgressStatus
    progress: float = 0.0  # 0.0 to 1.0
    message: Optional[str] = None

    # Timing
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Additional data
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    @classmethod
    def started(
        cls,
        tool_name: str,
        request_id: str,
        event_id: Optional[str] = None,
        message: Optional[str] = None,
    ) -> "ProgressEvent":
        """Create started event."""
        import uuid
        return cls(
            event_id=event_id or str(uuid.uuid4()),
            tool_name=tool_name,
            request_id=request_id,
            status=ProgressStatus.STARTED,
            progress=0.0,
            message=message or f"Starting {tool_name}",
        )

    @classmethod
    def progress(
        cls,
        tool_name: str,
        request_id: str,
        progress: float,
        message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> "ProgressEvent":
        """Create in-progress event."""
        import uuid
        return cls(
            event_id=str(uuid.uuid4()),
            tool_name=tool_name,
            request_id=request_id,
            status=ProgressStatus.IN_PROGRESS,
            progress=min(1.0, max(0.0, progress)),
            message=message,
            data=data or {},
        )

    @classmethod
    def completed(
        cls,
        tool_name: str,
        request_id: str,
        event_id: Optional[str] = None,
        message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> "ProgressEvent":
        """Create completed event."""
        import uuid
        return cls(
            event_id=event_id or str(uuid.uuid4()),
            tool_name=tool_name,
            request_id=request_id,
            status=ProgressStatus.COMPLETED,
            progress=1.0,
            message=message or f"Completed {tool_name}",
            data=data or {},
        )

    @classmethod
    def failed(
        cls,
        tool_name: str,
        request_id: str,
        error: str,
        event_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> "ProgressEvent":
        """Create failed event."""
        import uuid
        return cls(
            event_id=event_id or str(uuid.uuid4()),
            tool_name=tool_name,
            request_id=request_id,
            status=ProgressStatus.FAILED,
            progress=1.0,
            message=f"Failed: {error}",
            error=error,
            data=data or {},
        )

    @classmethod
    def cancelled(
        cls,
        tool_name: str,
        request_id: str,
        event_id: Optional[str] = None,
        message: Optional[str] = None,
    ) -> "ProgressEvent":
        """Create cancelled event."""
        import uuid
        return cls(
            event_id=event_id or str(uuid.uuid4()),
            tool_name=tool_name,
            request_id=request_id,
            status=ProgressStatus.CANCELLED,
            progress=1.0,
            message=message or f"Cancelled {tool_name}",
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "eventId": self.event_id,
            "toolName": self.tool_name,
            "requestId": self.request_id,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "error": self.error,
        }