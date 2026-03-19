"""Authentication interceptor for MCP server."""

from typing import Any, Callable, Dict, List, Optional
from abc import ABC, abstractmethod

from foggy.mcp.auth.context import AuthContext, UserRole
from foggy.mcp.config.properties import AuthProperties


class AuthInterceptor(ABC):
    """Abstract authentication interceptor."""

    @abstractmethod
    async def authenticate(self, request: Dict[str, Any]) -> AuthContext:
        """Authenticate a request and return the auth context."""
        pass

    @abstractmethod
    async def authorize(self, context: AuthContext, resource: str, action: str) -> bool:
        """Check if the context has permission for the action on resource."""
        pass


class NoAuthInterceptor(AuthInterceptor):
    """No-op authentication interceptor (authentication disabled)."""

    async def authenticate(self, request: Dict[str, Any]) -> AuthContext:
        """Return anonymous context."""
        return AuthContext.anonymous()

    async def authorize(self, context: AuthContext, resource: str, action: str) -> bool:
        """Always authorize."""
        return True


class ApiKeyInterceptor(AuthInterceptor):
    """API Key based authentication interceptor."""

    def __init__(
        self,
        valid_keys: Optional[Dict[str, AuthContext]] = None,
        header_name: str = "X-API-Key"
    ):
        """Initialize with valid API keys and their contexts."""
        self._header_name = header_name
        self._valid_keys = valid_keys or {}

    def add_key(self, api_key: str, context: AuthContext) -> None:
        """Add an API key with associated context."""
        self._valid_keys[api_key] = context

    def remove_key(self, api_key: str) -> bool:
        """Remove an API key."""
        if api_key in self._valid_keys:
            del self._valid_keys[api_key]
            return True
        return False

    async def authenticate(self, request: Dict[str, Any]) -> AuthContext:
        """Authenticate using API key from header."""
        headers = request.get("headers", {})
        api_key = headers.get(self._header_name) or headers.get(self._header_name.lower())

        if not api_key:
            return AuthContext.anonymous()

        context = self._valid_keys.get(api_key)
        if context:
            # Return a copy with auth info
            return AuthContext(
                user_id=context.user_id,
                user_name=context.user_name,
                roles=context.roles,
                permissions=context.permissions,
                authenticated=True,
                auth_type="api_key",
                client_ip=request.get("client_ip"),
                user_agent=request.get("user_agent"),
            )

        return AuthContext.anonymous()

    async def authorize(self, context: AuthContext, resource: str, action: str) -> bool:
        """Check authorization based on roles."""
        # Basic role-based authorization
        # In a real implementation, this would check resource-specific permissions
        return context.authenticated


class JwtInterceptor(AuthInterceptor):
    """JWT-based authentication interceptor."""

    def __init__(
        self,
        secret: str,
        algorithm: str = "HS256",
        issuer: Optional[str] = None,
        audience: Optional[str] = None
    ):
        """Initialize with JWT configuration."""
        self._secret = secret
        self._algorithm = algorithm
        self._issuer = issuer
        self._audience = audience

    async def authenticate(self, request: Dict[str, Any]) -> AuthContext:
        """Authenticate using JWT token from Authorization header."""
        import base64
        import json

        headers = request.get("headers", {})
        auth_header = headers.get("Authorization") or headers.get("authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return AuthContext.anonymous()

        token = auth_header[7:]  # Remove "Bearer " prefix

        try:
            # Simplified JWT decoding (in production, use a proper JWT library)
            # This is a placeholder implementation
            parts = token.split(".")
            if len(parts) != 3:
                return AuthContext.anonymous()

            # Decode payload (middle part)
            payload_b64 = parts[1]
            # Add padding if needed
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            payload_json = base64.urlsafe_b64decode(payload_b64)
            payload = json.loads(payload_json)

            # Extract user info
            return AuthContext(
                user_id=payload.get("sub"),
                user_name=payload.get("name") or payload.get("preferred_username"),
                user_email=payload.get("email"),
                roles=payload.get("roles", []),
                permissions=payload.get("permissions", []),
                authenticated=True,
                auth_type="jwt",
                session_id=payload.get("sid"),
                client_ip=request.get("client_ip"),
                user_agent=request.get("user_agent"),
            )

        except Exception:
            return AuthContext.anonymous()

    async def authorize(self, context: AuthContext, resource: str, action: str) -> bool:
        """Check authorization based on JWT claims."""
        return context.authenticated


class RoleBasedAuthorizer:
    """Role-based authorization checker."""

    # Default role permissions
    DEFAULT_PERMISSIONS = {
        UserRole.ADMIN: ["*"],  # Full access
        UserRole.ANALYST: ["query:read", "metadata:read", "chart:read", "chart:write"],
        UserRole.BUSINESS: ["query:read", "metadata:read", "chart:read"],
        UserRole.DEVELOPER: ["query:read", "query:write", "metadata:read", "metadata:write"],
        UserRole.VIEWER: ["query:read", "metadata:read"],
    }

    def __init__(self, role_permissions: Optional[Dict[str, List[str]]] = None):
        """Initialize with optional custom permissions."""
        self._permissions = role_permissions or self.DEFAULT_PERMISSIONS

    def check_permission(self, context: AuthContext, permission: str) -> bool:
        """Check if context has a specific permission."""
        if not context.authenticated:
            return False

        for role in context.roles:
            role_perms = self._permissions.get(role, [])
            if "*" in role_perms or permission in role_perms:
                return True

        return False

    def check_resource_action(self, context: AuthContext, resource: str, action: str) -> bool:
        """Check permission for resource:action."""
        permission = f"{resource}:{action}"
        return self.check_permission(context, permission)


def create_auth_interceptor(properties: AuthProperties) -> AuthInterceptor:
    """Factory function to create an auth interceptor based on properties."""
    if not properties.enabled:
        return NoAuthInterceptor()

    if properties.auth_type == "api_key":
        return ApiKeyInterceptor(
            valid_keys={},  # Keys would be loaded from configuration
            header_name=properties.api_key_header
        )

    if properties.auth_type == "jwt":
        if not properties.jwt_secret:
            raise ValueError("JWT secret is required for JWT authentication")
        return JwtInterceptor(
            secret=properties.jwt_secret,
            algorithm=properties.jwt_algorithm,
            issuer=properties.jwt_issuer,
            audience=properties.jwt_audience
        )

    # Default to no auth
    return NoAuthInterceptor()