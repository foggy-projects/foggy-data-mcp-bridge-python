"""FastAPI routers for MCP server."""

from foggy.mcp.routers.admin import create_admin_router
from foggy.mcp.routers.analyst import create_analyst_router
from foggy.mcp.routers.health import create_health_router

__all__ = [
    "create_admin_router",
    "create_analyst_router",
    "create_health_router",
]