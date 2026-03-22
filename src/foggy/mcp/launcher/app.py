"""FastAPI application factory and server launcher.

This module creates and configures the FastAPI application for the MCP server,
integrating the semantic query layer with database connectivity.
"""

from typing import Any, Dict, Optional, List
from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from foggy.mcp.config.properties import McpProperties, AuthProperties
from foggy.mcp.config.datasource import DataSourceManager, DataSourceConfig, DataSourceType
from foggy.mcp.tools.base import ToolRegistry
from foggy.mcp.routers.admin import create_admin_router
from foggy.mcp.routers.analyst import create_analyst_router
from foggy.mcp.routers.health import create_health_router
from foggy.mcp.routers.mcp_rpc import create_mcp_router
from foggy.mcp.routers.semantic_v3 import create_semantic_v3_router
from foggy.mcp.audit.service import ToolAuditService
from foggy.mcp_spi import LocalDatasetAccessor, SemanticRequestContext
from foggy.dataset_model.semantic import SemanticQueryService
from foggy.dataset_model.impl.model import DbTableModelImpl
from foggy.dataset.db.executor import create_executor_from_url, ExecutorManager


logger = logging.getLogger(__name__)


class AppState:
    """Application state container."""

    def __init__(self):
        """Initialize state containers."""
        self.properties: Optional[McpProperties] = None
        self.auth_properties: Optional[AuthProperties] = None
        self.data_source_manager: Optional[DataSourceManager] = None
        self.semantic_service: Optional[SemanticQueryService] = None
        self.accessor: Optional[LocalDatasetAccessor] = None
        self.tool_registry: Optional[ToolRegistry] = None
        self.audit_service: Optional[ToolAuditService] = None
        self.executor = None
        self.executor_manager: Optional[ExecutorManager] = None


def create_app(
    properties: Optional[McpProperties] = None,
    auth_properties: Optional[AuthProperties] = None,
    data_source_configs: Optional[List[DataSourceConfig]] = None,
    load_demo_models: bool = True,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        properties: MCP server configuration
        auth_properties: Authentication configuration
        data_source_configs: List of data source configurations
        load_demo_models: Whether to load built-in ecommerce demo models

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

        # Initialize data source manager
        state.data_source_manager = DataSourceManager()

        # Register provided data sources
        if data_source_configs:
            for config in data_source_configs:
                state.data_source_manager.register(config, set_default=True)
                logger.info(f"Registered data source: {config.name} ({config.source_type.value})")

        # Initialize semantic query service
        state.semantic_service = SemanticQueryService(
            default_limit=properties.max_query_rows,
            max_limit=properties.max_query_rows,
            enable_cache=True,
            cache_ttl_seconds=300,
        )

        # Create database executors for all registered data sources
        state.executor_manager = ExecutorManager()
        for ds_name in state.data_source_manager.list_names():
            ds_config = state.data_source_manager.get(ds_name)
            if ds_config:
                try:
                    executor_url = ds_config.get_executor_url()
                    executor = create_executor_from_url(executor_url)
                    is_default = (ds_name == state.data_source_manager.default_source)
                    state.executor_manager.register(ds_name, executor, set_default=is_default)
                    logger.info(f"Executor initialized: {ds_name} -> {ds_config.source_type.value} {ds_config.host}:{ds_config.port}/{ds_config.database}")
                except Exception as e:
                    logger.error(f"Failed to create executor for '{ds_name}': {e}")

        # Set default executor and manager on semantic service (backward compatible)
        state.executor = state.executor_manager.get_default()
        if state.executor:
            state.semantic_service.set_executor(state.executor)
        else:
            logger.warning("No data source configured - queries will return empty results")
        state.semantic_service.set_executor_manager(state.executor_manager)

        # Load demo models
        if load_demo_models:
            try:
                from foggy.demo.models.ecommerce_models import create_all_ecommerce_models
                for name, model in create_all_ecommerce_models().items():
                    state.semantic_service.register_model(model)
                    logger.info(f"Loaded demo model: {name}")
            except Exception as e:
                logger.warning(f"Failed to load demo models: {e}")

        # Load TM/QM models from directories via FSScript evaluator
        from foggy.dataset_model.impl.loader import load_models_from_directory

        # 1. Simple model directories (no namespace)
        for model_dir in properties.model_directories:
            if not os.path.exists(model_dir):
                logger.warning(f"Model directory not found: {model_dir}")
                continue
            try:
                loaded_models = load_models_from_directory(model_dir)
                for m in loaded_models:
                    state.semantic_service.register_model(m)
                logger.info(f"Loaded {len(loaded_models)} models from: {model_dir}")
            except Exception as e:
                logger.warning(f"Failed to load models from {model_dir}: {e}")

        # 2. Namespace-aware model bundles (aligned with Java foggy.bundle.external.bundles)
        for bundle in properties.model_bundles:
            if not os.path.exists(bundle.path):
                logger.warning(f"Bundle directory not found: {bundle.path} (namespace={bundle.namespace})")
                continue
            try:
                loaded_models = load_models_from_directory(bundle.path, namespace=bundle.namespace)
                for m in loaded_models:
                    state.semantic_service.register_model(m)
                ns_label = f" [namespace={bundle.namespace}]" if bundle.namespace else ""
                logger.info(f"Loaded {len(loaded_models)} models from bundle '{bundle.name or bundle.path}'{ns_label}")
            except Exception as e:
                logger.warning(f"Failed to load bundle '{bundle.name or bundle.path}': {e}")

        # Initialize tool registry
        state.tool_registry = ToolRegistry()

        # Initialize audit service
        state.audit_service = ToolAuditService(
            max_logs=10000,
            retention_hours=168
        )

        # Create accessor with semantic service
        state.accessor = LocalDatasetAccessor(state.semantic_service)

        # Store in app state
        app.state.foggy = state

        logger.info(f"Server initialized with {len(state.semantic_service.get_all_model_names())} models: {state.semantic_service.get_all_model_names()}")

        yield

        # Shutdown
        logger.info("Shutting down server")
        if state.executor_manager:
            try:
                await state.executor_manager.close_all()
            except Exception as e:
                logger.warning(f"Error closing executors: {e}")
        elif state.executor:
            try:
                await state.executor.close()
            except Exception as e:
                logger.warning(f"Error closing executor: {e}")
        if state.semantic_service:
            state.semantic_service.invalidate_model_cache()
        logger.info("Server shutdown complete")

    # Create FastAPI app
    app = FastAPI(
        title=properties.server_name,
        version=properties.server_version,
        description="Foggy Data MCP Bridge - Semantic Layer Query Server (Python)",
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
        semantic_service=state.semantic_service,
        accessor=state.accessor,
    ))

    # MCP RPC router (mounted at /mcp/analyst for MCP protocol)
    # Pass state container so the router can lazily resolve service objects
    # after lifespan has initialized them.
    app.include_router(
        create_mcp_router(
            semantic_service=None,
            accessor=None,
            state_getter=lambda: state,
        ),
        prefix="/mcp/analyst",
    )

    # Semantic V3 REST router — aligned with Java SemanticServiceV3TestController
    app.include_router(
        create_semantic_v3_router(state_getter=lambda: state),
        prefix="/semantic/v3",
    )

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

    # Add endpoints for model management
    @app.get("/api/v1/models", tags=["Models"])
    async def list_models():
        """List all available query models."""
        if not state.semantic_service:
            return {"models": []}
        return {"models": state.semantic_service.get_all_model_names()}

    @app.get("/api/v1/models/{model_name}", tags=["Models"])
    async def get_model_metadata(model_name: str):
        """Get metadata for a specific model."""
        if not state.semantic_service:
            return {"error": "Service not initialized"}

        from foggy.mcp_spi import SemanticMetadataRequest
        request = SemanticMetadataRequest(model=model_name)
        response = state.semantic_service.get_metadata(request)
        return response.model_dump(by_alias=True, exclude_none=True)

    def _make_json_response(data: dict) -> JSONResponse:
        """Create JSONResponse that handles Decimal/datetime serialization."""
        import decimal
        from datetime import datetime as dt, date
        import json

        class SafeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, decimal.Decimal):
                    return float(obj)
                if isinstance(obj, (dt, date)):
                    return obj.isoformat()
                return super().default(obj)

        return JSONResponse(
            content=json.loads(json.dumps(data, cls=SafeEncoder))
        )

    @app.post("/api/v1/query/{model_name}", tags=["Query"])
    async def execute_query(model_name: str, payload: Dict[str, Any]):
        """Execute a query against a model.

        Payload uses Java camelCase field names:
        {columns, slice, groupBy, orderBy, start, limit, calculatedFields, ...}
        """
        if not state.accessor:
            return {"error": "Service not initialized"}

        response = await state.accessor.query_model_async(model_name, payload)
        return _make_json_response(response.model_dump(by_alias=True, exclude_none=True))

    @app.post("/api/v1/query/{model_name}/validate", tags=["Query"])
    async def validate_query(model_name: str, payload: Dict[str, Any]):
        """Validate a query without executing it."""
        if not state.accessor:
            return {"error": "Service not initialized"}

        response = await state.accessor.query_model_async(model_name, payload, mode="validate")
        return _make_json_response(response.model_dump(by_alias=True, exclude_none=True))

    return app


def main() -> None:
    """Main entry point for the MCP server."""
    import argparse
    import uvicorn

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Parse arguments
    parser = argparse.ArgumentParser(description="Foggy MCP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Server host")
    parser.add_argument("--port", type=int, default=8066, help="Server port (default: 8066)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    # Database connection (URL or individual params)
    parser.add_argument("--db-url", default=None, help="Database connection URL (e.g., mysql://user:pass@host:port/db)")
    parser.add_argument("--db-host", default=None, help="Database host")
    parser.add_argument("--db-port", type=int, default=None, help="Database port")
    parser.add_argument("--db-user", default=None, help="Database username")
    parser.add_argument("--db-password", default=None, help="Database password")
    parser.add_argument("--db-name", default=None, help="Database name")
    parser.add_argument("--db-type", default="mysql", choices=["mysql", "postgresql", "sqlite"], help="Database type")

    parser.add_argument("--models-dir", default=None, help="Models directory")
    parser.add_argument("--no-demo-models", action="store_true", help="Skip loading demo models")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create properties
    properties = McpProperties(
        host=args.host,
        port=args.port,
        model_directories=[args.models_dir] if args.models_dir else [],
    )

    # Build data source config
    data_source_configs = None

    if args.db_url:
        # URL-based config
        url = args.db_url.lower()
        if "mysql" in url:
            source_type = DataSourceType.MYSQL
        elif "postgres" in url:
            source_type = DataSourceType.POSTGRESQL
        elif "sqlite" in url:
            source_type = DataSourceType.SQLITE
        else:
            source_type = DataSourceType.MYSQL

        data_source_configs = [
            DataSourceConfig(
                name="default",
                source_type=source_type,
                connection_url=args.db_url,
            )
        ]

    elif args.db_host:
        # Individual parameter config
        type_map = {
            "mysql": DataSourceType.MYSQL,
            "postgresql": DataSourceType.POSTGRESQL,
            "sqlite": DataSourceType.SQLITE,
        }
        source_type = type_map.get(args.db_type, DataSourceType.MYSQL)

        default_ports = {
            DataSourceType.MYSQL: 3306,
            DataSourceType.POSTGRESQL: 5432,
        }

        data_source_configs = [
            DataSourceConfig(
                name="default",
                source_type=source_type,
                host=args.db_host,
                port=args.db_port or default_ports.get(source_type, 3306),
                database=args.db_name or "foggy_test",
                username=args.db_user or "foggy",
                password=args.db_password or "",
            )
        ]

    # Store configs in a module-level variable for the factory function
    _app_config["properties"] = properties
    _app_config["data_source_configs"] = data_source_configs
    _app_config["load_demo_models"] = not args.no_demo_models

    # Run server using uvicorn with factory
    uvicorn.run(
        "foggy.mcp.launcher.app:_create_app_from_config",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
    )


# Module-level config for factory pattern (uvicorn requires importable factory)
_app_config: Dict[str, Any] = {}


def _create_app_from_config() -> FastAPI:
    """Factory function called by uvicorn to create the app."""
    return create_app(
        properties=_app_config.get("properties"),
        data_source_configs=_app_config.get("data_source_configs"),
        load_demo_models=_app_config.get("load_demo_models", True),
    )


if __name__ == "__main__":
    main()
