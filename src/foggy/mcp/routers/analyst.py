"""Analyst MCP router for query operations."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field

from foggy.mcp_spi import LocalDatasetAccessor, SemanticQueryRequest, SemanticMetadataRequest
from foggy.dataset_model.semantic import SemanticQueryService


class QueryExecuteRequest(BaseModel):
    """Request to execute a query.

    .. deprecated::
        This model uses Python-style field names (filters, group_by, order_by, offset)
        which do NOT match Java. Use ``SemanticQueryRequest`` from ``foggy.mcp.spi``
        instead, which uses Java-aligned names (slice, groupBy, orderBy, start).
        New V3 endpoints are at /semantic/v3/query/{model}.
    """

    query_model: str = Field(..., description="Query model name")
    columns: List[str] = Field(default_factory=list, description="Columns to select")
    filters: List[Dict[str, Any]] = Field(default_factory=list, description="Filter objects")
    group_by: List[str] = Field(default_factory=list, description="Group by columns")
    order_by: List[Dict[str, Any]] = Field(default_factory=list, description="Order by specs")
    limit: Optional[int] = Field(default=100, description="Row limit")
    offset: Optional[int] = Field(default=None, description="Offset for pagination")


def create_analyst_router(
    semantic_service: Optional[SemanticQueryService] = None,
    accessor: Optional[LocalDatasetAccessor] = None,
) -> APIRouter:
    """Create the analyst router for query operations.

    Args:
        semantic_service: Semantic query service for executing queries
        accessor: Dataset accessor for querying models
    """
    router = APIRouter(prefix="/analyst", tags=["analyst"])

    @router.get("/models", response_model=Dict[str, Any])
    async def list_models(
        filter: Optional[str] = Query(None, description="Filter pattern")
    ) -> Dict[str, Any]:
        """List available query models."""
        if not semantic_service:
            raise HTTPException(status_code=503, detail="Service not initialized")

        models = semantic_service.get_all_model_names()
        if filter:
            models = [m for m in models if filter.lower() in m.lower()]

        return {
            "models": models,
            "total": len(models),
        }

    @router.get("/models/{model_name}", response_model=Dict[str, Any])
    async def get_model_metadata(
        model_name: str,
        include_columns: bool = Query(True),
        include_measures: bool = Query(True),
        include_dimensions: bool = Query(True),
    ) -> Dict[str, Any]:
        """Get metadata for a specific model."""
        if not semantic_service:
            raise HTTPException(status_code=503, detail="Service not initialized")

        request = SemanticMetadataRequest(
            model=model_name,
            include_columns=include_columns,
            include_measures=include_measures,
            include_dimensions=include_dimensions,
        )

        response = semantic_service.get_metadata(request)

        if response.error:
            raise HTTPException(status_code=404, detail=response.error)

        return {
            "success": True,
            "data": response.models[0] if response.models else None,
            "warnings": response.warnings,
        }

    @router.post("/query", response_model=Dict[str, Any])
    async def execute_query(request: QueryExecuteRequest) -> Dict[str, Any]:
        """Execute a structured query against a query model."""
        if not accessor:
            raise HTTPException(status_code=503, detail="Service not initialized")

        query_request = SemanticQueryRequest(
            columns=request.columns,
            slice=request.filters,
            group_by=request.group_by,
            order_by=request.order_by,
            limit=request.limit,
            start=request.offset or 0,
        )

        response = accessor.query_model(request.query_model, query_request.model_dump())

        if response.error:
            raise HTTPException(status_code=400, detail=response.error)

        return {
            "success": True,
            "data": response.data,
            "columns": response.columns,
            "total": response.total,
            "sql": response.sql,
            "metrics": response.metrics,
            "warnings": response.warnings,
        }

    @router.post("/query/validate", response_model=Dict[str, Any])
    async def validate_query(request: QueryExecuteRequest) -> Dict[str, Any]:
        """Validate a query without executing it."""
        if not accessor:
            raise HTTPException(status_code=503, detail="Service not initialized")

        query_request = SemanticQueryRequest(
            columns=request.columns,
            slice=request.filters,
            group_by=request.group_by,
            order_by=request.order_by,
            limit=request.limit,
            start=request.offset or 0,
        )

        response = accessor.query_model(
            request.query_model,
            query_request.model_dump(),
            mode="validate"
        )

        return {
            "valid": response.error is None,
            "sql": response.sql,
            "columns": response.columns,
            "errors": [response.error] if response.error else [],
            "warnings": response.warnings,
        }

    @router.post("/query/sql", response_model=Dict[str, Any])
    async def generate_sql(request: QueryExecuteRequest) -> Dict[str, Any]:
        """Generate SQL for a query without executing it."""
        if not semantic_service:
            raise HTTPException(status_code=503, detail="Service not initialized")

        model = semantic_service.get_model(request.query_model)
        if not model:
            raise HTTPException(status_code=404, detail=f"Model not found: {request.query_model}")

        query_request = SemanticQueryRequest(
            columns=request.columns,
            slice=request.filters,
            group_by=request.group_by,
            order_by=request.order_by,
            limit=request.limit,
            start=request.offset or 0,
        )

        # Build query and get SQL
        from foggy.dataset_model.semantic.service import QueryBuildResult

        # Use validate mode to get SQL without execution
        response = accessor.query_model(
            request.query_model,
            query_request.model_dump(),
            mode="validate"
        )

        return {
            "sql": response.sql,
            "columns": response.columns,
            "model": request.query_model,
        }

    return router