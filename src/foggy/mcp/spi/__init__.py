"""MCP SPI - Service Provider Interfaces for foggy-dataset-mcp.

This module provides the core SPI (Service Provider Interface) for
accessing semantic layer data and services.

All externally-facing models use Pydantic aliases to ensure JSON
serialization matches Java field names (camelCase). Python attributes
use snake_case per PEP 8.

Use ``model_dump(by_alias=True, exclude_none=True)`` for Java-compatible output.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr


# ============================================================================
# Enums
# ============================================================================

class AccessMode(str, Enum):
    """Access mode for dataset accessor."""

    LOCAL = "local"
    REMOTE = "remote"


# ============================================================================
# Request Context (dataclass — internal only)
# ============================================================================

@dataclass
class SemanticRequestContext:
    """Context for semantic layer requests.

    Contains namespace and security information for the request.
    """

    namespace: Optional[str] = None
    user_id: Optional[str] = None
    roles: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "SemanticRequestContext":
        """Create a default context."""
        return cls()

    @classmethod
    def for_user(cls, user_id: str, roles: Optional[List[str]] = None) -> "SemanticRequestContext":
        """Create a context for a specific user."""
        return cls(user_id=user_id, roles=roles or [])


# ============================================================================
# Response nested models — aligned with Java SemanticQueryResponse
# ============================================================================

class ColumnDef(BaseModel):
    """Column definition in schema — aligned with Java SchemaInfo.ColumnDef."""
    model_config = ConfigDict(populate_by_name=True)

    name: str
    data_type: Optional[str] = Field(None, alias="dataType")
    title: Optional[str] = None


class SchemaInfo(BaseModel):
    """Schema info — aligned with Java SemanticQueryResponse.SchemaInfo."""

    columns: List[ColumnDef] = []
    summary: Optional[str] = None


class PaginationInfo(BaseModel):
    """Pagination info — aligned with Java SemanticQueryResponse.PaginationInfo."""
    model_config = ConfigDict(populate_by_name=True)

    start: int = 0
    limit: int = 20
    returned: int = 0
    total_count: Optional[int] = Field(None, alias="totalCount")
    has_more: bool = Field(False, alias="hasMore")
    range_description: str = Field("", alias="rangeDescription")


class NormalizedRequest(BaseModel):
    """Normalized request in debug — aligned with Java DebugInfo.NormalizedRequest."""
    model_config = ConfigDict(populate_by_name=True)

    slice: Optional[List[Dict[str, Any]]] = None
    group_by: Optional[List[Dict[str, Any]]] = Field(None, alias="groupBy")
    order_by: Optional[List[Dict[str, Any]]] = Field(None, alias="orderBy")


class DebugInfo(BaseModel):
    """Debug info — aligned with Java SemanticQueryResponse.DebugInfo."""
    model_config = ConfigDict(populate_by_name=True)

    normalized: Optional[NormalizedRequest] = None
    duration_ms: Optional[float] = Field(None, alias="durationMs")
    extra: Optional[Dict[str, Any]] = None


# ============================================================================
# SemanticQueryResponse — aligned with Java
# ============================================================================

class SemanticQueryResponse(BaseModel):
    """Response for query execution — aligned with Java SemanticQueryResponse.

    JSON output (via ``model_dump(by_alias=True, exclude_none=True)``)
    matches Java exactly::

        {
            "items": [...],
            "schema": {"columns": [...], "summary": "..."},
            "pagination": {"start": 0, "limit": 100, ...},
            "total": 200,
            "totalData": {...},
            "hasNext": true,
            "cursor": "...",
            "warnings": [...],
            "debug": {...},
            "truncationInfo": {...}
        }
    """
    model_config = ConfigDict(populate_by_name=True)

    items: List[Dict[str, Any]] = []
    schema_info: Optional[SchemaInfo] = Field(None, alias="schema")
    pagination: Optional[PaginationInfo] = None
    total: Optional[int] = None
    total_data: Optional[Any] = Field(None, alias="totalData")
    has_next: Optional[bool] = Field(None, alias="hasNext")
    cursor: Optional[str] = None
    warnings: Optional[List[str]] = None
    debug: Optional[DebugInfo] = None
    truncation_info: Optional[Dict[str, Any]] = Field(None, alias="truncationInfo")

    # Internal-only error field — excluded from JSON serialization
    _error: Optional[str] = PrivateAttr(default=None)

    @property
    def error(self) -> Optional[str]:
        """Get internal error (not serialized to JSON)."""
        return self._error

    @error.setter
    def error(self, value: Optional[str]) -> None:
        self._error = value

    @property
    def data(self) -> List[Dict[str, Any]]:
        """Backward compat: access result rows via .data."""
        return self.items

    @property
    def sql(self) -> Optional[str]:
        """Backward compat: extract SQL from debug.extra."""
        if self.debug and self.debug.extra:
            return self.debug.extra.get("sql")
        return None

    @property
    def columns(self) -> List[Dict[str, Any]]:
        """Backward compat: extract column defs from schema_info."""
        if self.schema_info and self.schema_info.columns:
            return [c.model_dump(by_alias=True, exclude_none=True) for c in self.schema_info.columns]
        return []

    @property
    def metrics(self) -> Dict[str, Any]:
        """Backward compat: build metrics dict from debug."""
        result: Dict[str, Any] = {}
        if self.debug:
            if self.debug.duration_ms is not None:
                result["duration_ms"] = self.debug.duration_ms
            if self.debug.extra:
                result.update(self.debug.extra)
        return result

    @classmethod
    def from_error(cls, error_msg: str, warnings: Optional[List[str]] = None) -> "SemanticQueryResponse":
        """Create an error response (internal use)."""
        resp = cls(warnings=warnings)
        resp._error = error_msg
        return resp

    @classmethod
    def from_legacy(
        cls,
        data: List[Dict[str, Any]],
        columns_info: List[Dict[str, Any]] = None,
        total: int = 0,
        sql: Optional[str] = None,
        error: Optional[str] = None,
        warnings: Optional[List[str]] = None,
        duration_ms: Optional[float] = None,
    ) -> "SemanticQueryResponse":
        """Create from legacy (Python-internal) field names — migration helper."""
        schema = None
        if columns_info:
            col_defs = [
                ColumnDef(
                    name=c.get("name", ""),
                    data_type=c.get("dataType") or c.get("data_type"),
                    title=c.get("title") or c.get("alias"),
                )
                for c in columns_info
            ]
            schema = SchemaInfo(columns=col_defs)

        extra = {"sql": sql} if sql else None
        debug = DebugInfo(duration_ms=duration_ms, extra=extra) if (duration_ms or sql) else None

        resp = cls(
            items=data or [],
            schema_info=schema,
            total=total or len(data or []),
            warnings=warnings if warnings else None,
            debug=debug,
        )
        if error:
            resp._error = error
        return resp


# ============================================================================
# SemanticMetadataResponse — aligned with Java
# ============================================================================

class SemanticMetadataResponse(BaseModel):
    """Response for metadata requests — aligned with Java SemanticMetadataResponse.

    Java output::

        {"content": "...", "data": {...}, "format": "json|markdown"}

    Python internal fields (models, columns, error, warnings) are excluded from
    JSON serialization but available for internal use.
    """

    content: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    format: Optional[str] = None

    # Python internal extensions — excluded from external JSON
    models: List[Dict[str, Any]] = Field(default_factory=list, exclude=True)
    _columns_internal: List[Dict[str, Any]] = PrivateAttr(default_factory=list)
    _error: Optional[str] = PrivateAttr(default=None)
    _warnings: List[str] = PrivateAttr(default_factory=list)

    @property
    def columns(self) -> List[Dict[str, Any]]:
        """Internal column info."""
        return self._columns_internal

    @columns.setter
    def columns(self, value: List[Dict[str, Any]]) -> None:
        self._columns_internal = value

    @property
    def error(self) -> Optional[str]:
        return self._error

    @error.setter
    def error(self, value: Optional[str]) -> None:
        self._error = value

    @property
    def warnings(self) -> List[str]:
        return self._warnings

    @warnings.setter
    def warnings(self, value: List[str]) -> None:
        self._warnings = value


# ============================================================================
# SemanticMetadataRequest
# ============================================================================

class SemanticMetadataRequest(BaseModel):
    """Request for metadata."""

    model: Optional[str] = None
    include_columns: bool = True
    include_measures: bool = True
    include_dimensions: bool = True


# ============================================================================
# SemanticQueryRequest — aligned with Java
# ============================================================================

class SemanticQueryRequest(BaseModel):
    """Request for query execution — aligned with Java SemanticQueryRequest.

    All DSL field names match Java exactly when serialized with aliases::

        {
            "columns": [...],
            "calculatedFields": [...],
            "slice": [...],
            "groupBy": [...],
            "orderBy": [...],
            "start": 0,
            "limit": 100,
            "returnTotal": false,
            "distinct": false,
            "withSubtotals": false,
            "captionMatchMode": "EXACT",
            "mismatchHandleStrategy": "ABORT"
        }
    """
    model_config = ConfigDict(populate_by_name=True)

    columns: List[str] = []
    calculated_fields: List[Dict[str, Any]] = Field(default_factory=list, alias="calculatedFields")
    slice: List[Any] = []
    group_by: List[Any] = Field(default_factory=list, alias="groupBy")
    order_by: List[Any] = Field(default_factory=list, alias="orderBy")
    start: int = 0
    limit: Optional[int] = None
    cursor: Optional[str] = None
    hints: Optional[Dict[str, Any]] = None
    stream: Optional[bool] = None
    caption_match_mode: str = Field("EXACT", alias="captionMatchMode")
    mismatch_handle_strategy: str = Field("ABORT", alias="mismatchHandleStrategy")
    return_total: bool = Field(False, alias="returnTotal")
    distinct: bool = False
    with_subtotals: bool = Field(False, alias="withSubtotals")


# ============================================================================
# Abstract interfaces
# ============================================================================

class DatasetAccessor(ABC):
    """Abstract interface for accessing dataset services.

    This is the main SPI for the MCP layer. Implementations can be:
    - LocalDatasetAccessor: Direct calls to SemanticService
    - RemoteDatasetAccessor: HTTP calls to remote foggy-dataset-model service
    """

    @abstractmethod
    def get_metadata(
        self,
        trace_id: Optional[str] = None,
        authorization: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> SemanticMetadataResponse:
        """Get metadata for all available models."""
        pass

    @abstractmethod
    def describe_model(
        self,
        model: str,
        format: str = "json",
        trace_id: Optional[str] = None,
        authorization: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> SemanticMetadataResponse:
        """Get detailed description of a specific model."""
        pass

    @abstractmethod
    def query_model(
        self,
        model: str,
        payload: Dict[str, Any],
        mode: str = "execute",
        trace_id: Optional[str] = None,
        authorization: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> SemanticQueryResponse:
        """Execute a query against a model.

        Args:
            model: Model name
            payload: Query parameters in Java camelCase format
                     (columns, slice, groupBy, orderBy, start, limit, etc.)
            mode: Query mode (execute or validate)
        """
        pass

    @abstractmethod
    def get_access_mode(self) -> str:
        """Get the access mode name. Returns 'local' or 'remote'."""
        pass


class SemanticServiceResolver(ABC):
    """Abstract interface for resolving semantic services."""

    @abstractmethod
    def get_metadata(
        self,
        request: SemanticMetadataRequest,
        format: str = "json",
        context: Optional[SemanticRequestContext] = None,
    ) -> SemanticMetadataResponse:
        """Get metadata."""
        pass

    @abstractmethod
    def query_model(
        self,
        model: str,
        request: SemanticQueryRequest,
        mode: str = "execute",
        context: Optional[SemanticRequestContext] = None,
    ) -> SemanticQueryResponse:
        """Execute a query."""
        pass

    @abstractmethod
    def get_all_model_names(self) -> List[str]:
        """Get all available model names."""
        pass

    def invalidate_model_cache(self) -> None:
        """Invalidate the model cache."""
        pass


# ============================================================================
# Helper: build SemanticQueryRequest from Java-format payload dict
# ============================================================================

def _build_query_request(payload: Dict[str, Any]) -> SemanticQueryRequest:
    """Build a SemanticQueryRequest from a Java-format payload dict.

    Payload keys must use Java camelCase names:
    columns, slice, groupBy, orderBy, start, limit, calculatedFields, etc.
    """
    return SemanticQueryRequest(
        columns=payload.get("columns", []),
        slice=payload.get("slice", []),
        group_by=payload.get("groupBy", []),
        order_by=payload.get("orderBy", []),
        start=payload.get("start", 0),
        limit=payload.get("limit"),
        calculated_fields=payload.get("calculatedFields", []),
        return_total=payload.get("returnTotal", False),
        distinct=payload.get("distinct", False),
        with_subtotals=payload.get("withSubtotals", False),
        hints=payload.get("hints"),
        cursor=payload.get("cursor"),
        stream=payload.get("stream"),
        caption_match_mode=payload.get("captionMatchMode", "EXACT"),
        mismatch_handle_strategy=payload.get("mismatchHandleStrategy", "ABORT"),
    )


# ============================================================================
# LocalDatasetAccessor
# ============================================================================

class LocalDatasetAccessor(DatasetAccessor):
    """Local implementation of DatasetAccessor.

    Directly calls SemanticServiceResolver without HTTP layer.
    """

    def __init__(self, resolver: SemanticServiceResolver):
        self._resolver = resolver

    def get_metadata(
        self,
        trace_id: Optional[str] = None,
        authorization: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> SemanticMetadataResponse:
        """Get metadata using the resolver."""
        context = SemanticRequestContext(namespace=namespace)
        request = SemanticMetadataRequest()
        return self._resolver.get_metadata(request, "json", context)

    def describe_model(
        self,
        model: str,
        format: str = "json",
        trace_id: Optional[str] = None,
        authorization: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> SemanticMetadataResponse:
        """Describe model using the resolver."""
        context = SemanticRequestContext(namespace=namespace)
        request = SemanticMetadataRequest(model=model)
        return self._resolver.get_metadata(request, format, context)

    def query_model(
        self,
        model: str,
        payload: Dict[str, Any],
        mode: str = "execute",
        trace_id: Optional[str] = None,
        authorization: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> SemanticQueryResponse:
        """Execute query using the resolver.

        Payload keys are Java camelCase (slice, groupBy, orderBy, start, etc.)
        and are passed through without renaming.
        """
        context = SemanticRequestContext(namespace=namespace)
        request = _build_query_request(payload)
        return self._resolver.query_model(model, request, mode, context)

    async def query_model_async(
        self,
        model: str,
        payload: Dict[str, Any],
        mode: str = "execute",
        trace_id: Optional[str] = None,
        authorization: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> SemanticQueryResponse:
        """Async version of query_model — safe to call from FastAPI handlers."""
        context = SemanticRequestContext(namespace=namespace)
        request = _build_query_request(payload)
        # Use async method if resolver supports it
        if hasattr(self._resolver, 'query_model_async'):
            return await self._resolver.query_model_async(model, request, mode, context)
        return self._resolver.query_model(model, request, mode, context)

    def get_access_mode(self) -> str:
        """Return 'local'."""
        return AccessMode.LOCAL


# ============================================================================
# RemoteDatasetAccessor
# ============================================================================

class RemoteDatasetAccessor(DatasetAccessor):
    """Remote implementation of DatasetAccessor.

    Makes HTTP calls to a foggy-dataset-model service.
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def get_metadata(
        self,
        trace_id: Optional[str] = None,
        authorization: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> SemanticMetadataResponse:
        """Get metadata via HTTP."""
        raise NotImplementedError("RemoteDatasetAccessor not yet implemented")

    def describe_model(
        self,
        model: str,
        format: str = "json",
        trace_id: Optional[str] = None,
        authorization: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> SemanticMetadataResponse:
        """Describe model via HTTP."""
        raise NotImplementedError("RemoteDatasetAccessor not yet implemented")

    def query_model(
        self,
        model: str,
        payload: Dict[str, Any],
        mode: str = "execute",
        trace_id: Optional[str] = None,
        authorization: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> SemanticQueryResponse:
        """Execute query via HTTP."""
        raise NotImplementedError("RemoteDatasetAccessor not yet implemented")

    def get_access_mode(self) -> str:
        """Return 'remote'."""
        return AccessMode.REMOTE


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "AccessMode",
    "SemanticRequestContext",
    # Response models (Java-aligned)
    "ColumnDef",
    "SchemaInfo",
    "PaginationInfo",
    "NormalizedRequest",
    "DebugInfo",
    "SemanticQueryResponse",
    "SemanticMetadataResponse",
    # Request models
    "SemanticMetadataRequest",
    "SemanticQueryRequest",
    # Interfaces
    "DatasetAccessor",
    "SemanticServiceResolver",
    "LocalDatasetAccessor",
    "RemoteDatasetAccessor",
]
