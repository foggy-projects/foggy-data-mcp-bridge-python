"""Dataset Accessor SPI — bridge between MCP layer and semantic engine.

The accessor accepts standard JSON dict payloads and converts them
to typed SemanticQueryRequest objects internally.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from foggy.mcp_spi.enums import AccessMode
from foggy.mcp_spi.semantic import (
    DeniedColumn,
    FieldAccessDef,
    SemanticMetadataRequest,
    SemanticMetadataResponse,
    SemanticQueryRequest,
    SemanticQueryResponse,
    SemanticRequestContext,
    SemanticServiceResolver,
)


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


# ============================================================================
# Helper: build SemanticQueryRequest from Java-format payload dict
# ============================================================================

def build_query_request(payload: Dict[str, Any]) -> SemanticQueryRequest:
    """Build a SemanticQueryRequest from a Java-format payload dict.

    Payload keys must use Java camelCase names:
    columns, slice, groupBy, orderBy, start, limit, calculatedFields, etc.
    """
    # --- v1.2 column governance ---
    field_access_raw = payload.get("fieldAccess")
    field_access = FieldAccessDef(**field_access_raw) if isinstance(field_access_raw, dict) else None
    system_slice = payload.get("systemSlice")

    # --- v1.3 physical column blacklist ---
    denied_columns_raw = payload.get("deniedColumns")
    denied_columns = None
    if isinstance(denied_columns_raw, list):
        denied_columns = [
            DeniedColumn(**dc) if isinstance(dc, dict) else dc
            for dc in denied_columns_raw
        ]

    return SemanticQueryRequest(
        columns=payload.get("columns", []),
        slice=payload.get("slice", []),
        having=payload.get("having", []),
        group_by=payload.get("groupBy", []),
        order_by=payload.get("orderBy", []),
        start=payload.get("start", 0),
        limit=payload.get("limit"),
        calculated_fields=payload.get("calculatedFields", []),
        return_total=payload.get("returnTotal", False),
        distinct=payload.get("distinct", False),
        with_subtotals=payload.get("withSubtotals", False),
        time_window=payload.get("timeWindow"),
        pivot=payload.get("pivot"),
        hints=payload.get("hints"),
        cursor=payload.get("cursor"),
        stream=payload.get("stream"),
        caption_match_mode=payload.get("captionMatchMode", "EXACT"),
        mismatch_handle_strategy=payload.get("mismatchHandleStrategy", "ABORT"),
        field_access=field_access,
        system_slice=system_slice,
        denied_columns=denied_columns,
    )


# Keep backward compat alias
_build_query_request = build_query_request


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
        request = build_query_request(payload)
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
        request = build_query_request(payload)
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
