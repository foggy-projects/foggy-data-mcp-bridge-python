"""Tool execution context."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import datetime


@dataclass
class ToolExecutionContext:
    """Context for tool execution.

    Contains all contextual information needed during tool execution,
    including user info, request metadata, and shared state.
    """

    # Request identification
    request_id: str
    session_id: Optional[str] = None

    # User context
    user_id: Optional[str] = None
    user_role: Optional[str] = None
    user_permissions: list[str] = field(default_factory=list)

    # Request context
    namespace: Optional[str] = None
    locale: str = "en"
    timezone: str = "UTC"

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    deadline: Optional[datetime] = None

    # Shared state
    state: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)

    # Parent context (for nested tool calls)
    parent: Optional["ToolExecutionContext"] = None

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get value from shared state."""
        return self.state.get(key, default)

    def set_state(self, key: str, value: Any) -> None:
        """Set value in shared state."""
        self.state[key] = value

    def get_header(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Get header value (case-insensitive)."""
        # Try exact match first
        if name in self.headers:
            return self.headers[name]
        # Try case-insensitive match
        name_lower = name.lower()
        for key, value in self.headers.items():
            if key.lower() == name_lower:
                return value
        return default

    def has_permission(self, permission: str) -> bool:
        """Check if user has permission."""
        if "*" in self.user_permissions:
            return True
        return permission in self.user_permissions

    def is_admin(self) -> bool:
        """Check if user is admin."""
        return self.user_role == "admin" or self.has_permission("admin")

    def is_expired(self) -> bool:
        """Check if context deadline has passed."""
        if self.deadline is None:
            return False
        return datetime.utcnow() > self.deadline

    def create_child(self, request_id: Optional[str] = None) -> "ToolExecutionContext":
        """Create a child context for nested tool calls."""
        return ToolExecutionContext(
            request_id=request_id or f"{self.request_id}_child",
            session_id=self.session_id,
            user_id=self.user_id,
            user_role=self.user_role,
            user_permissions=self.user_permissions.copy(),
            namespace=self.namespace,
            locale=self.locale,
            timezone=self.timezone,
            deadline=self.deadline,
            state={},  # New state for child
            headers=self.headers.copy(),
            parent=self,
        )

    @classmethod
    def create(
        cls,
        request_id: str,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        namespace: Optional[str] = None,
        **kwargs,
    ) -> "ToolExecutionContext":
        """Create a new context with common parameters."""
        return cls(
            request_id=request_id,
            user_id=user_id,
            user_role=user_role,
            namespace=namespace,
            **kwargs,
        )