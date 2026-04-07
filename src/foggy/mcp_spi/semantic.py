"""Semantic layer SPI types — aligned with Java.

All externally-facing models use Pydantic aliases to ensure JSON
serialization matches Java field names (camelCase). Python attributes
use snake_case per PEP 8.

Use ``model_dump(by_alias=True, exclude_none=True)`` for Java-compatible output.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from foggy.mcp_spi.enums import AccessMode


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
        start: int = 0,
        limit: Optional[int] = None,
        has_more: Optional[bool] = None,
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

        # Build pagination when limit is provided (aligned with Java)
        pagination = None
        if limit is not None:
            returned = len(data or [])
            effective_total = total or returned
            computed_has_more = has_more if has_more is not None else (start + returned < effective_total)
            end = start + returned
            range_desc = (
                f"第 {start + 1}-{end} 条，共 {effective_total} 条"
                if effective_total > 0 else ""
            )
            pagination = PaginationInfo(
                start=start,
                limit=limit,
                returned=returned,
                total_count=effective_total,
                has_more=computed_has_more,
                range_description=range_desc,
            )

        resp = cls(
            items=data or [],
            schema_info=schema,
            pagination=pagination,
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
# Column Governance DTOs — v1.2
# ============================================================================

class FieldAccessDef(BaseModel):
    """Column governance parameters — computed by Bridge, passed to engine.

    * ``visible``: whitelist of field names the user may see / query.
    * ``masking``: field-name → mask-type mapping for sensitive columns.

    When the Bridge does **not** send this object the engine behaves exactly
    as v1.1 (no governance).
    """
    model_config = ConfigDict(populate_by_name=True)

    visible: List[str] = Field(default_factory=list)
    masking: Dict[str, str] = Field(default_factory=dict)


class SystemSlice(BaseModel):
    """System-injected slice — **not** subject to visible_fields governance.

    Used by the permission bridge (ir.rule) to inject row-level filters that
    may reference blocked columns.  The engine merges these into the WHERE
    clause without column-visibility checks.
    """

    slices: List[Any] = Field(default_factory=list)


# ============================================================================
# SemanticMetadataRequest
# ============================================================================

class SemanticMetadataRequest(BaseModel):
    """Request for metadata."""

    model: Optional[str] = None
    include_columns: bool = True
    include_measures: bool = True
    include_dimensions: bool = True
    visible_fields: Optional[List[str]] = Field(
        None,
        alias="visibleFields",
        description="When set, only these fields appear in the response. "
                    "None means return all fields (v1.1 compat).",
    )


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

    # --- v1.2 column governance ---
    field_access: Optional[FieldAccessDef] = Field(
        None,
        alias="fieldAccess",
        description="Column governance: visible whitelist + masking rules. "
                    "None means no governance (v1.1 compat).",
    )
    system_slice: Optional[List[Any]] = Field(
        None,
        alias="systemSlice",
        description="System-injected slice (ir.rule). Bypasses visible_fields checks.",
    )


# ============================================================================
# Abstract interfaces
# ============================================================================

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
