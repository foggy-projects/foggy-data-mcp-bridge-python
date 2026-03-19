"""Authentication context and models."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """User role enumeration."""

    ADMIN = "admin"
    ANALYST = "analyst"
    BUSINESS = "business"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class AuthContext(BaseModel):
    """Authentication context for a request."""

    # User information
    user_id: Optional[str] = Field(default=None, description="User identifier")
    user_name: Optional[str] = Field(default=None, description="User name")
    user_email: Optional[str] = Field(default=None, description="User email")

    # Roles and permissions
    roles: List[str] = Field(default_factory=list, description="User roles")
    permissions: List[str] = Field(default_factory=list, description="User permissions")

    # Authentication details
    auth_type: str = Field(default="none", description="Authentication type")
    authenticated: bool = Field(default=False, description="Whether user is authenticated")
    auth_time: Optional[datetime] = Field(default=None, description="Authentication timestamp")

    # Session information
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    token_id: Optional[str] = Field(default=None, description="Token identifier")

    # Client information
    client_ip: Optional[str] = Field(default=None, description="Client IP address")
    user_agent: Optional[str] = Field(default=None, description="Client user agent")

    # Additional attributes
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Additional attributes")

    model_config = {"extra": "allow"}

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles

    def has_any_role(self, roles: List[str]) -> bool:
        """Check if user has any of the specified roles."""
        return any(r in self.roles for r in roles)

    def has_all_roles(self, roles: List[str]) -> bool:
        """Check if user has all of the specified roles."""
        return all(r in self.roles for r in roles)

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions

    def is_admin(self) -> bool:
        """Check if user is an admin."""
        return self.has_role(UserRole.ADMIN)

    def is_analyst(self) -> bool:
        """Check if user is an analyst."""
        return self.has_role(UserRole.ANALYST)

    @classmethod
    def anonymous(cls) -> "AuthContext":
        """Create an anonymous (unauthenticated) context."""
        return cls(
            user_id="anonymous",
            user_name="Anonymous",
            authenticated=False,
            auth_type="none",
        )

    @classmethod
    def system(cls) -> "AuthContext":
        """Create a system context for internal operations."""
        return cls(
            user_id="system",
            user_name="System",
            roles=[UserRole.ADMIN],
            authenticated=True,
            auth_type="system",
        )