"""MCP SPI - Service Provider Interfaces for foggy-dataset-mcp.

This module provides the core SPI (Service Provider Interface) for
accessing semantic layer data and services.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel


class AccessMode(str, Enum):
    """Access mode for dataset accessor."""

    LOCAL = "local"
    REMOTE = "remote"


@dataclass
class SemanticRequestContext:
    """Context for semantic layer requests.

    Contains namespace and security information for the request.

    Attributes:
        namespace: Namespace for multi-tenant isolation
        user_id: User identifier
        roles: User roles for authorization
        attributes: Additional security attributes
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


class SemanticMetadataResponse(BaseModel):
    """Response for metadata requests.

    Contains information about available models and their schemas.
    """

    models: List[Dict[str, Any]] = []
    columns: List[Dict[str, Any]] = []
    error: Optional[str] = None
    warnings: List[str] = []


class SemanticQueryResponse(BaseModel):
    """Response for query execution.

    Contains the query results or error information.
    """

    data: List[Dict[str, Any]] = []
    columns: List[Dict[str, Any]] = []
    total: int = 0
    sql: Optional[str] = None
    error: Optional[str] = None
    warnings: List[str] = []
    metrics: Dict[str, Any] = {}


class SemanticMetadataRequest(BaseModel):
    """Request for metadata."""

    model: Optional[str] = None
    include_columns: bool = True
    include_measures: bool = True
    include_dimensions: bool = True


class SemanticQueryRequest(BaseModel):
    """Request for query execution.

    Attributes:
        columns: Columns to select
        filters: Filter conditions
        group_by: Grouping columns
        order_by: Ordering specifications
        limit: Maximum rows to return
        offset: Offset for pagination
        slice: Slice definition for filtering
    """

    columns: List[str] = []
    filters: List[Dict[str, Any]] = []
    group_by: List[str] = []
    order_by: List[Dict[str, Any]] = []
    limit: Optional[int] = None
    offset: Optional[int] = None
    slice: Optional[Dict[str, Any]] = None
    parameters: Dict[str, Any] = {}
    calculated_fields: List[Dict[str, Any]] = []


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
        """Get metadata for all available models.

        Args:
            trace_id: Request tracing ID
            authorization: Authorization header (optional)
            namespace: Namespace for multi-tenant

        Returns:
            SemanticMetadataResponse with model information
        """
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
        """Get detailed description of a specific model.

        Args:
            model: Model name
            format: Output format (json or markdown)
            trace_id: Request tracing ID
            authorization: Authorization header (optional)
            namespace: Namespace for multi-tenant

        Returns:
            SemanticMetadataResponse with model schema
        """
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
            payload: Query parameters (columns, filters, groupBy, etc.)
            mode: Query mode (execute or validate)
            trace_id: Request tracing ID
            authorization: Authorization header (optional)
            namespace: Namespace for multi-tenant

        Returns:
            SemanticQueryResponse with query results
        """
        pass

    @abstractmethod
    def get_access_mode(self) -> str:
        """Get the access mode name.

        Returns:
            'local' or 'remote'
        """
        pass


class SemanticServiceResolver(ABC):
    """Abstract interface for resolving semantic services.

    Provides a unified interface for calling semantic layer services.
    """

    @abstractmethod
    def get_metadata(
        self,
        request: SemanticMetadataRequest,
        format: str = "json",
        context: Optional[SemanticRequestContext] = None,
    ) -> SemanticMetadataResponse:
        """Get metadata.

        Args:
            request: Metadata request
            format: Output format (json or markdown)
            context: Request context

        Returns:
            SemanticMetadataResponse
        """
        pass

    @abstractmethod
    def query_model(
        self,
        model: str,
        request: SemanticQueryRequest,
        mode: str = "execute",
        context: Optional[SemanticRequestContext] = None,
    ) -> SemanticQueryResponse:
        """Execute a query.

        Args:
            model: Model name
            request: Query request
            mode: Execution mode (execute or validate)
            context: Request context

        Returns:
            SemanticQueryResponse
        """
        pass

    @abstractmethod
    def get_all_model_names(self) -> List[str]:
        """Get all available model names.

        Returns:
            List of model names
        """
        pass

    def invalidate_model_cache(self) -> None:
        """Invalidate the model cache.

        Called when QM files change.
        """
        pass


class LocalDatasetAccessor(DatasetAccessor):
    """Local implementation of DatasetAccessor.

    Directly calls SemanticServiceResolver without HTTP layer.
    """

    def __init__(self, resolver: SemanticServiceResolver):
        """Initialize with a semantic service resolver.

        Args:
            resolver: SemanticServiceResolver implementation
        """
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
        """Execute query using the resolver."""
        context = SemanticRequestContext(namespace=namespace)
        request = SemanticQueryRequest(
            columns=payload.get("columns", []),
            filters=payload.get("filters", []),
            group_by=payload.get("groupBy") or payload.get("group_by", []),
            order_by=payload.get("orderBy") or payload.get("order_by", []),
            limit=payload.get("limit"),
            offset=payload.get("offset"),
            slice=payload.get("slice"),
            parameters=payload.get("parameters", {}),
            calculated_fields=payload.get("calculated_fields", payload.get("calculatedFields", [])),
        )
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
        request = SemanticQueryRequest(
            columns=payload.get("columns", []),
            filters=payload.get("filters", []),
            group_by=payload.get("groupBy") or payload.get("group_by", []),
            order_by=payload.get("orderBy") or payload.get("order_by", []),
            limit=payload.get("limit"),
            offset=payload.get("offset"),
            slice=payload.get("slice"),
            parameters=payload.get("parameters", {}),
            calculated_fields=payload.get("calculated_fields", payload.get("calculatedFields", [])),
        )
        # Use async method if resolver supports it
        if hasattr(self._resolver, 'query_model_async'):
            return await self._resolver.query_model_async(model, request, mode, context)
        return self._resolver.query_model(model, request, mode, context)

    def get_access_mode(self) -> str:
        """Return 'local'."""
        return AccessMode.LOCAL


class RemoteDatasetAccessor(DatasetAccessor):
    """Remote implementation of DatasetAccessor.

    Makes HTTP calls to a foggy-dataset-model service.
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """Initialize with remote service configuration.

        Args:
            base_url: Base URL of the remote service
            api_key: API key for authentication
        """
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def get_metadata(
        self,
        trace_id: Optional[str] = None,
        authorization: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> SemanticMetadataResponse:
        """Get metadata via HTTP."""
        # TODO: Implement HTTP call
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
        # TODO: Implement HTTP call
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
        # TODO: Implement HTTP call
        raise NotImplementedError("RemoteDatasetAccessor not yet implemented")

    def get_access_mode(self) -> str:
        """Return 'remote'."""
        return AccessMode.REMOTE


__all__ = [
    "AccessMode",
    "SemanticRequestContext",
    "SemanticMetadataResponse",
    "SemanticQueryResponse",
    "SemanticMetadataRequest",
    "SemanticQueryRequest",
    "DatasetAccessor",
    "SemanticServiceResolver",
    "LocalDatasetAccessor",
    "RemoteDatasetAccessor",
]