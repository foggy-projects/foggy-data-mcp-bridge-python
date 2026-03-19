"""Health check router for MCP server."""

from typing import Any, Dict
from fastapi import APIRouter
from datetime import datetime


def create_health_router() -> APIRouter:
    """Create the health check router."""
    router = APIRouter(tags=["health"])

    @router.get("/health", response_model=Dict[str, Any])
    async def health_check() -> Dict[str, Any]:
        """Basic health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "foggy-mcp",
        }

    @router.get("/health/ready", response_model=Dict[str, Any])
    async def readiness_check() -> Dict[str, Any]:
        """Readiness check for Kubernetes/container orchestration."""
        # In a full implementation, check database connections, model loading, etc.
        return {
            "ready": True,
            "checks": {
                "server": "ok",
                "models": "ok",
                "datasources": "ok",
            },
        }

    @router.get("/health/live", response_model=Dict[str, Any])
    async def liveness_check() -> Dict[str, Any]:
        """Liveness check for Kubernetes/container orchestration."""
        return {
            "alive": True,
            "timestamp": datetime.now().isoformat(),
        }

    @router.get("/", response_model=Dict[str, str])
    async def root() -> Dict[str, str]:
        """Root endpoint with service info."""
        return {
            "service": "Foggy MCP Server",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health",
        }

    return router