"""Admin MCP router for administrative operations."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from foggy.mcp.config.datasource import DataSourceConfig, DataSourceManager
from foggy.mcp.schema.response import McpResponse, McpError
from foggy.mcp.tools.base import ToolRegistry


class DataSourceCreateRequest(BaseModel):
    """Request to create a data source."""

    name: str
    source_type: str
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    connection_url: Optional[str] = None
    set_default: bool = False


class ToolEnableRequest(BaseModel):
    """Request to enable/disable a tool."""

    tool_name: str
    enabled: bool = True


def create_admin_router(
    data_source_manager: Optional[DataSourceManager] = None,
    tool_registry: Optional[ToolRegistry] = None,
) -> APIRouter:
    """Create the admin router with dependencies."""
    router = APIRouter(prefix="/admin", tags=["admin"])

    # Use provided instances or create defaults
    _data_source_manager = data_source_manager or DataSourceManager()
    _tool_registry = tool_registry or ToolRegistry()

    @router.get("/health", response_model=Dict[str, Any])
    async def health_check() -> Dict[str, Any]:
        """Check server health status."""
        return {
            "status": "healthy",
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "version": "1.0.0",
        }

    @router.get("/datasources", response_model=List[str])
    async def list_data_sources() -> List[str]:
        """List all registered data sources."""
        return _data_source_manager.list_names()

    @router.post("/datasources", response_model=Dict[str, Any])
    async def create_data_source(request: DataSourceCreateRequest) -> Dict[str, Any]:
        """Create a new data source."""
        try:
            config = DataSourceConfig(
                name=request.name,
                source_type=request.source_type,
                host=request.host,
                port=request.port,
                database=request.database,
                username=request.username,
                password=request.password,
                connection_url=request.connection_url,
            )
            _data_source_manager.register(config, set_default=request.set_default)

            return {
                "success": True,
                "name": config.name,
                "type": config.source_type,
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.delete("/datasources/{name}", response_model=Dict[str, Any])
    async def delete_data_source(name: str) -> Dict[str, Any]:
        """Delete a data source."""
        if _data_source_manager.remove(name):
            return {"success": True, "name": name}
        raise HTTPException(status_code=404, detail=f"Data source not found: {name}")

    @router.get("/tools", response_model=List[Dict[str, Any]])
    async def list_tools(
        category: Optional[str] = Query(None, description="Filter by category")
    ) -> List[Dict[str, Any]]:
        """List all registered tools."""
        tools = _tool_registry.list_tools()

        if category:
            from foggy.mcp_spi.tool import ToolCategory
            try:
                cat = ToolCategory(category)
                tools = _tool_registry.list_by_category(cat)
            except ValueError:
                pass

        return [t.get_tool_definition().model_dump() for t in tools]

    @router.get("/tools/{tool_name}", response_model=Dict[str, Any])
    async def get_tool(tool_name: str) -> Dict[str, Any]:
        """Get tool details."""
        tool = _tool_registry.get(tool_name)
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")
        return tool.get_tool_definition().model_dump()

    @router.get("/stats", response_model=Dict[str, Any])
    async def get_stats() -> Dict[str, Any]:
        """Get server statistics."""
        return {
            "datasources": len(_data_source_manager.list_names()),
            "tools": len(_tool_registry.list_tools()),
            "categories": len(_tool_registry.list_by_category),
        }

    @router.post("/reload", response_model=Dict[str, Any])
    async def reload_models() -> Dict[str, Any]:
        """Reload all models (placeholder)."""
        # In a full implementation, this would reload TM/QM models
        return {
            "success": True,
            "message": "Models reloaded",
            "models_loaded": 0,
        }

    return router