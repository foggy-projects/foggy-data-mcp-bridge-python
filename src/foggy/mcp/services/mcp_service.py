"""MCP Service implementation.

Note: The legacy ``DatasetAccessor``, ``LocalDatasetAccessor``, and
``SemanticServiceResolverImpl`` classes below are part of the OLD MCP
protocol scaffold. They are **NOT** the SPI types used by the semantic
engine — those live in ``foggy.mcp_spi.accessor``.

These legacy classes will be removed once ``query_service.py`` is migrated
to use the SPI ``DatasetAccessor`` directly.
"""

from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod

from foggy.mcp.config.properties import McpProperties
from foggy.mcp.schema.request import McpRequest
from foggy.mcp.schema.response import McpResponse


class McpService(ABC):
    """Abstract base class for MCP services."""

    def __init__(self, properties: Optional[McpProperties] = None):
        """Initialize the service with optional configuration."""
        self.properties = properties or McpProperties()
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the service."""
        self._initialized = True

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the service and release resources."""
        self._initialized = False

    @abstractmethod
    async def handle_request(self, request: McpRequest) -> McpResponse:
        """Handle an incoming request."""
        pass

    def is_initialized(self) -> bool:
        """Check if the service is initialized."""
        return self._initialized


# ============================================================================
# Legacy MCP protocol classes — used by query_service.py internally.
# NOT the SPI types (those are in foggy.mcp_spi.accessor).
# TODO: migrate query_service.py to use foggy.mcp_spi.DatasetAccessor,
#       then delete these classes.
# ============================================================================

class DatasetAccessor(ABC):
    """Legacy async accessor for MCP protocol layer.

    .. deprecated::
        Use ``foggy.mcp_spi.DatasetAccessor`` for new code.
    """

    @abstractmethod
    async def query(self, query_model: str, params: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def get_metadata(self, model_name: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def list_models(self) -> List[str]:
        pass

    @abstractmethod
    async def validate_model(self, model_name: str) -> List[str]:
        pass


class LocalDatasetAccessor(DatasetAccessor):
    """Legacy local accessor stub.

    .. deprecated::
        Use ``foggy.mcp_spi.LocalDatasetAccessor`` for new code.
    """

    def __init__(self, model_registry: Optional[Dict[str, Any]] = None):
        self._models = model_registry or {}
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    async def shutdown(self) -> None:
        self._initialized = False

    async def query(self, query_model: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("Accessor not initialized")
        if query_model not in self._models:
            raise ValueError(f"Model not found: {query_model}")
        return {"columns": [], "rows": [], "total_rows": 0, "query_model": query_model}

    async def get_metadata(self, model_name: str) -> Dict[str, Any]:
        if model_name not in self._models:
            raise ValueError(f"Model not found: {model_name}")
        return {"name": model_name, "columns": [], "measures": [], "dimensions": []}

    async def list_models(self) -> List[str]:
        return list(self._models.keys())

    async def validate_model(self, model_name: str) -> List[str]:
        if model_name not in self._models:
            return [f"Model not found: {model_name}"]
        return []

    def register_model(self, name: str, model: Any) -> None:
        self._models[name] = model


class SemanticServiceResolverImpl:
    """Legacy resolver stub.

    .. deprecated::
        Use ``foggy.mcp_spi.SemanticServiceResolver`` for new code.
    """

    def __init__(self, accessor: Optional[DatasetAccessor] = None):
        self._default_accessor = accessor
        self._accessors: Dict[str, DatasetAccessor] = {}

    def register_accessor(self, name: str, accessor: DatasetAccessor) -> None:
        self._accessors[name] = accessor

    async def resolve(self, model_name: str) -> Optional[DatasetAccessor]:
        return self._default_accessor

    async def get_default_accessor(self) -> Optional[DatasetAccessor]:
        return self._default_accessor