"""Semantic V3 REST API Router — aligned with Java SemanticServiceV3TestController.

Provides REST endpoints that accept and return the same JSON format as Java:
- POST /query/{model}     → SemanticQueryRequest body → SemanticQueryResponse
- POST /validate/{model}  → SemanticQueryRequest body → SemanticQueryResponse
- GET  /metadata/{model}  → SemanticMetadataResponse
- POST /metadata          → batch metadata request

All request/response field names use camelCase, matching Java exactly.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Body, HTTPException, Query
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
from foggy.mcp_spi.semantic import DeniedColumn
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


def _normalize_denied_columns(raw_denied_columns: Any) -> Optional[list[dict[str, Any]]]:
    if not isinstance(raw_denied_columns, list):
        return None

    normalized: list[dict[str, Any]] = []
    for item in raw_denied_columns:
        if not isinstance(item, dict):
            continue

        table = item.get("table")
        schema = item.get("schema")
        column = item.get("column")
        if table and column:
            entry = {"table": table, "column": column}
            if schema:
                entry["schema"] = schema
            normalized.append(entry)
            continue

        columns = item.get("columns")
        if not table or not isinstance(columns, list):
            continue
        for col in columns:
            if not col:
                continue
            entry = {"table": table, "column": col}
            if schema:
                entry["schema"] = schema
            normalized.append(entry)

    return normalized


def _build_denied_column_models(raw_denied_columns: Any) -> Optional[list[DeniedColumn]]:
    normalized = _normalize_denied_columns(raw_denied_columns)
    if normalized is None:
        return None
    return [DeniedColumn(**item) for item in normalized]


def _optional_string_list(value: Any) -> Optional[list[str]]:
    if not isinstance(value, list):
        return None
    result = [str(item) for item in value if item is not None and str(item)]
    return result or None


def _optional_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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

    @router.post("/list-models")
    async def list_models_catalog(
        request: Dict[str, Any] = Body(default_factory=dict),
    ):
        """Build a host-facing model catalog.

        This is the programmatic counterpart of the no-parameter MCP
        dataset.list_models tool. Hosts may pass fixed arguments such as
        format=markdown, fieldLimit, modelNames, visibleFields and
        deniedColumns without exposing those knobs to the LLM tool schema.
        """
        svc = _get_service()
        if not svc:
            raise HTTPException(status_code=503, detail="Service not initialized")

        model_names = _optional_string_list(
            request.get("modelNames") or request.get("models")
        )
        visible_fields = _optional_string_list(request.get("visibleFields"))
        denied_columns = _build_denied_column_models(request.get("deniedColumns"))
        llm_hints = request.get("llmHints") if isinstance(request.get("llmHints"), dict) else None
        field_limit = max(0, _optional_int(request.get("fieldLimit"), 10))
        fmt = str(request.get("format", MetadataFormat.JSON.value)).lower()

        if hasattr(svc, "get_model_catalog"):
            catalog = svc.get_model_catalog(
                model_names=model_names,
                visible_fields=visible_fields,
                denied_columns=denied_columns,
                llm_hints=llm_hints,
                field_limit=field_limit,
            )
        else:
            models = svc.get_all_model_names()
            if model_names:
                allowed = set(model_names)
                models = [model for model in models if model in allowed]
            items = []
            for model in models:
                item = {
                    "model": model,
                    "caption": model,
                }
                if field_limit > 0:
                    item["fieldPreview"] = []
                    item["fieldCount"] = 0
                items.append(item)
            catalog = {
                "models": models,
                "count": len(models),
                "recommendedNext": "dataset.describe_model_internal",
                "items": items,
            }

        markdown = (
            svc.render_model_catalog_markdown(catalog)
            if hasattr(svc, "render_model_catalog_markdown")
            else json.dumps(catalog, ensure_ascii=False, indent=2)
        )
        if fmt == MetadataFormat.MARKDOWN:
            return JSONResponse(content={
                "format": fmt,
                "content": markdown,
            })
        if fmt == "all":
            return JSONResponse(content={
                "format": fmt,
                "content": markdown,
                "data": catalog,
            })
        return JSONResponse(content={
            "format": fmt,
            "content": json.dumps(catalog, ensure_ascii=False),
            "data": catalog,
        })

    return router
