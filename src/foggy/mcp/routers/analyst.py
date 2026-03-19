"""Analyst MCP router for query operations."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field

from foggy.mcp.schema.request import QueryRequest
from foggy.mcp.schema.response import QueryResult, McpResponse
from foggy.mcp.schema.query import DatasetNLQueryRequest, DatasetNLQueryResponse
from foggy.mcp.services.query_service import QueryService
from foggy.mcp.tools.query_tool import QueryModelTool
from foggy.mcp.tools.metadata_tool import MetadataTool, ListModelsTool
from foggy.mcp.tools.nl_query_tool import NaturalLanguageQueryTool


class QueryExecuteRequest(BaseModel):
    """Request to execute a query."""

    query_model: str = Field(..., description="Query model name")
    select: List[str] = Field(default_factory=list, description="Columns to select")
    measures: List[str] = Field(default_factory=list, description="Measures to calculate")
    where: Optional[str] = Field(default=None, description="WHERE clause")
    filters: List[Dict[str, Any]] = Field(default_factory=list, description="Filter objects")
    group_by: List[str] = Field(default_factory=list, description="Group by columns")
    order_by: List[Dict[str, str]] = Field(default_factory=list, description="Order by specs")
    limit: Optional[int] = Field(default=100, description="Row limit")
    offset: Optional[int] = Field(default=0, description="Offset for pagination")


def create_analyst_router(
    query_service: Optional[QueryService] = None,
) -> APIRouter:
    """Create the analyst router for query operations."""
    router = APIRouter(prefix="/analyst", tags=["analyst"])

    # Create tools with shared query service
    _query_service = query_service or QueryService()
    query_tool = QueryModelTool(query_service=_query_service)
    metadata_tool = MetadataTool(query_service=_query_service)
    list_models_tool = ListModelsTool(query_service=_query_service)
    nl_query_tool = NaturalLanguageQueryTool(query_service=_query_service)

    @router.get("/models", response_model=Dict[str, Any])
    async def list_models(
        filter: Optional[str] = Query(None, description="Filter pattern")
    ) -> Dict[str, Any]:
        """List available query models."""
        result = await list_models_tool.execute({"filter": filter})
        if result.is_success():
            return result.data
        raise HTTPException(status_code=500, detail=result.error_message)

    @router.get("/models/{model_name}", response_model=Dict[str, Any])
    async def get_model_metadata(
        model_name: str,
        include_columns: bool = Query(True),
        include_measures: bool = Query(True),
        include_dimensions: bool = Query(True),
    ) -> Dict[str, Any]:
        """Get metadata for a specific model."""
        result = await metadata_tool.execute({
            "model_name": model_name,
            "include_columns": include_columns,
            "include_measures": include_measures,
            "include_dimensions": include_dimensions,
        })

        if result.is_success():
            return result.data
        raise HTTPException(status_code=404, detail=result.error_message)

    @router.post("/query", response_model=Dict[str, Any])
    async def execute_query(request: QueryExecuteRequest) -> Dict[str, Any]:
        """Execute a structured query against a query model."""
        result = await query_tool.execute({
            "query_model": request.query_model,
            "select": request.select,
            "measures": request.measures,
            "where": request.where,
            "filters": request.filters,
            "group_by": request.group_by,
            "order_by": request.order_by,
            "limit": request.limit,
            "offset": request.offset,
        })

        if result.is_success():
            return result.data
        raise HTTPException(status_code=400, detail=result.error_message)

    @router.post("/query/nl", response_model=Dict[str, Any])
    async def execute_nl_query(
        query: str = Body(..., description="Natural language query"),
        query_model: Optional[str] = Body(None, description="Target model"),
        max_rows: int = Body(100, description="Max rows"),
    ) -> Dict[str, Any]:
        """Execute a natural language query."""
        result = await nl_query_tool.execute({
            "query": query,
            "query_model": query_model,
            "max_rows": max_rows,
        })

        if result.is_success():
            return result.data
        raise HTTPException(status_code=400, detail=result.error_message)

    @router.post("/validate", response_model=Dict[str, Any])
    async def validate_query(request: QueryExecuteRequest) -> Dict[str, Any]:
        """Validate a query without executing it."""
        errors = await _query_service.validate_query(QueryRequest(
            query_model=request.query_model,
            select=request.select,
            where=request.where,
            group_by=request.group_by,
        ))

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    return router