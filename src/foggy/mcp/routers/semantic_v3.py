"""Semantic V3 REST API Router — aligned with Java SemanticServiceV3TestController.

Provides REST endpoints that accept and return the same JSON format as Java:
- POST /query/{model}     → SemanticQueryRequest body → SemanticQueryResponse
- POST /validate/{model}  → SemanticQueryRequest body → SemanticQueryResponse
- GET  /metadata/{model}  → SemanticMetadataResponse
- POST /metadata          → batch metadata request

All request/response field names use camelCase, matching Java exactly.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
import json
import logging

from foggy.mcp_spi import (
    LocalDatasetAccessor,
    SemanticQueryRequest,
    SemanticMetadataRequest,
    SemanticQueryResponse,
    MetadataFormat,
)
from foggy.dataset_model.semantic import SemanticQueryService


logger = logging.getLogger(__name__)


def _json_serializable(obj):
    """Convert obj to JSON-serializable form (handle Decimal, datetime, etc.)."""
    import decimal
    from datetime import datetime, date
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_serializable(i) for i in obj]
    return obj


def create_semantic_v3_router(
    semantic_service: Optional[SemanticQueryService] = None,
    accessor: Optional[LocalDatasetAccessor] = None,
    state_getter=None,
) -> APIRouter:
    """Create Semantic V3 router aligned with Java SemanticServiceV3TestController.

    Args:
        semantic_service: Semantic query service
        accessor: Dataset accessor
        state_getter: Callable returning AppState for lazy resolution
    """
    router = APIRouter(tags=["semantic-v3"])

    def _get_service():
        if state_getter:
            s = state_getter()
            return s.semantic_service if s else semantic_service
        return semantic_service

    def _get_accessor():
        if state_getter:
            s = state_getter()
            return s.accessor if s else accessor
        return accessor

    @router.post("/query/{model}")
    async def query_model(
        model: str,
        request: SemanticQueryRequest,
        mode: str = Query("execute", description="Query mode: execute or validate"),
    ):
        """Execute a query against a model.

        Aligned with Java: POST /semantic/v3/test/query/{model}

        Request body is SemanticQueryRequest with camelCase fields:
        {columns, calculatedFields, slice, groupBy, orderBy, start, limit, ...}

        Response is SemanticQueryResponse with camelCase fields:
        {items, schema, pagination, total, totalData, hasNext, ...}
        """
        _acc = _get_accessor()
        if not _acc:
            raise HTTPException(status_code=503, detail="Service not initialized")

        # Convert SemanticQueryRequest to payload dict (Java camelCase)
        payload = request.model_dump(by_alias=True, exclude_none=True)

        if hasattr(_acc, 'query_model_async'):
            response = await _acc.query_model_async(model, payload, mode=mode)
        else:
            response = _acc.query_model(model, payload, mode=mode)

        if response.error:
            raise HTTPException(status_code=400, detail=response.error)

        result = _json_serializable(
            response.model_dump(by_alias=True, exclude_none=True)
        )
        return JSONResponse(content=result)

    @router.post("/validate/{model}")
    async def validate_query(
        model: str,
        request: SemanticQueryRequest,
    ):
        """Validate a query without executing it.

        Aligned with Java: POST /semantic/v3/test/validate/{model}
        """
        _acc = _get_accessor()
        if not _acc:
            raise HTTPException(status_code=503, detail="Service not initialized")

        payload = request.model_dump(by_alias=True, exclude_none=True)

        if hasattr(_acc, 'query_model_async'):
            response = await _acc.query_model_async(model, payload, mode="validate")
        else:
            response = _acc.query_model(model, payload, mode="validate")

        result = _json_serializable(
            response.model_dump(by_alias=True, exclude_none=True)
        )
        return JSONResponse(content=result)

    @router.get("/metadata/{model}")
    async def get_model_metadata(
        model: str,
        format: str = Query("markdown", description="Output format: json or markdown"),
    ):
        """Get metadata for a specific model.

        Aligned with Java: GET /semantic/v3/test/metadata/{model}

        Response is SemanticMetadataResponse: {content, data, format}
        """
        svc = _get_service()
        if not svc:
            raise HTTPException(status_code=503, detail="Service not initialized")

        if format == MetadataFormat.JSON:
            v3_data = svc.get_metadata_v3(model_names=[model])
            return JSONResponse(content={
                "content": json.dumps(v3_data, ensure_ascii=False),
                "data": v3_data,
                "format": MetadataFormat.JSON,
            })
        else:
            md = svc.get_metadata_v3_markdown(model_names=[model])
            return JSONResponse(content={
                "content": md,
                "format": MetadataFormat.MARKDOWN,
            })

    @router.get("/models")
    async def list_models():
        """List all available models.

        Aligned with Java: GET /api/v1/models
        """
        svc = _get_service()
        if not svc:
            raise HTTPException(status_code=503, detail="Service not initialized")

        models = svc.get_all_model_names()
        return {"models": models, "count": len(models)}

    return router
