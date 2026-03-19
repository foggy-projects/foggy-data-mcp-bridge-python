"""FastAPI application factory and server launcher."""

from typing import Any, Dict, Optional
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from foggy.mcp.config.properties import McpProperties, AuthProperties
from foggy.mcp.config.datasource import DataSourceManager
from foggy.mcp.services.query_service import QueryService
from foggy.mcp.services.mcp_service import LocalDatasetAccessor
from foggy.mcp.tools.base import ToolRegistry
from foggy.mcp.routers.admin import create_admin_router
from foggy.mcp.routers.analyst import create_analyst_router
from foggy.mcp.routers.health import create_health_router
from foggy.mcp.audit.service import ToolAuditService


logger = logging.getLogger(__name__)


class AppState:
    """Application state container."""

    def __init__(self):
        """Initialize state containers."""
        self.properties: Optional[McpProperties] = None
        self.auth_properties: Optional[AuthProperties] = None
        self.data_source_manager: Optional[DataSourceManager] = None
        self.query_service: Optional[QueryService] = None
        self.tool_registry: Optional[ToolRegistry] = None
        self.audit_service: Optional[ToolAuditService] = None


def create_app(
    properties: Optional[McpProperties] = None,
    auth_properties: Optional[AuthProperties] = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        properties: MCP server configuration
        auth_properties: Authentication configuration

    Returns:
        Configured FastAPI application
    """
    # Use default properties if not provided
    properties = properties or McpProperties()
    auth_properties = auth_properties or AuthProperties()

    # Create state
    state = AppState()
    state.properties = properties
    state.auth_properties = auth_properties

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan manager."""
        # Startup
        logger.info(f"Starting {properties.server_name} v{properties.server_version}")

        # Initialize services
        state.data_source_manager = DataSourceManager()
        state.tool_registry = ToolRegistry()
        state.audit_service = ToolAuditService(
            max_logs=10000,
            retention_hours=168
        )

        # Create local accessor and query service
        accessor = LocalDatasetAccessor()
        await accessor.initialize()
        state.query_service = QueryService(
            accessor=accessor,
            data_source_manager=state.data_source_manager,
            max_rows=properties.max_query_rows
        )

        # Store in app state
        app.state.foggy = state

        logger.info("Server initialized successfully")

        yield

        # Shutdown
        logger.info("Shutting down server")
        if state.query_service:
            # Cleanup if needed
            pass
        logger.info("Server shutdown complete")

    # Create FastAPI app
    app = FastAPI(
        title=properties.server_name,
        version=properties.server_version,
        description="Foggy Data MCP Bridge - Semantic Layer Query Server",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(create_health_router())
    app.include_router(create_admin_router(
        data_source_manager=state.data_source_manager,
        tool_registry=state.tool_registry,
    ))
    app.include_router(create_analyst_router(
        query_service=state.query_service,
    ))

    # Exception handlers
    from fastapi.responses import JSONResponse
    from fastapi import Request

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler."""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": str(exc),
                "path": str(request.url),
            }
        )

    return app


def run_server(
    host: str = "0.0.0.0",
    port: int = 8080,
    reload: bool = False,
    properties: Optional[McpProperties] = None,
) -> None:
    """Run the MCP server.

    Args:
        host: Server host
        port: Server port
        reload: Enable auto-reload for development
        properties: Server configuration
    """
    import uvicorn

    properties = properties or McpProperties(
        host=host,
        port=port
    )

    uvicorn.run(
        "foggy.mcp.launcher.app:create_app",
        host=properties.host,
        port=properties.port,
        reload=reload,
        factory=True,
    )


def main() -> None:
    """Main entry point for the MCP server."""
    import argparse
    import logging

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Parse arguments
    parser = argparse.ArgumentParser(description="Foggy MCP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Server host")
    parser.add_argument("--port", type=int, default=8080, help="Server port")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create properties
    properties = McpProperties(
        host=args.host,
        port=args.port,
    )

    # Run server
    run_server(
        host=args.host,
        port=args.port,
        reload=args.reload,
        properties=properties
    )


if __name__ == "__main__":
    main()