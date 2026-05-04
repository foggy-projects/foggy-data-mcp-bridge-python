"""MCP SPI module - Model Context Protocol Service Provider Interface.

This is the single source of truth for all SPI types. Both the MCP layer
(foggy.mcp) and the semantic engine (foggy.dataset_model) import from here.
"""

from foggy.mcp_spi.context import ToolExecutionContext
from foggy.mcp_spi.events import ProgressEvent, ProgressStatus
from foggy.mcp_spi.tool import McpTool, ToolCategory, ToolMetadata, ToolResult
from foggy.mcp_spi.enums import AccessMode, QueryMode, MetadataFormat
from foggy.mcp_spi.semantic import (
    SemanticRequestContext,
    ColumnDef,
    SchemaInfo,
    PaginationInfo,
    NormalizedRequest,
    DebugInfo,
    SemanticInfo,
    SemanticQueryResponse,
    PivotAxisField,
    PivotMetricItem,
    PivotOptions,
    PivotLayout,
    PivotRequest,
    SemanticMetadataResponse,
    SemanticMetadataRequest,
    SemanticQueryRequest,
    SemanticServiceResolver,
)
from foggy.mcp_spi.accessor import (
    DatasetAccessor,
    LocalDatasetAccessor,
    RemoteDatasetAccessor,
    build_query_request,
    _build_query_request,
)

__all__ = [
    # Tool SPI
    "McpTool",
    "ToolCategory",
    "ToolMetadata",
    "ToolResult",
    "ToolExecutionContext",
    "ProgressEvent",
    "ProgressStatus",
    # Enums
    "AccessMode",
    "QueryMode",
    "MetadataFormat",
    # Semantic types (Java-aligned)
    "SemanticRequestContext",
    "ColumnDef",
    "SchemaInfo",
    "PaginationInfo",
    "NormalizedRequest",
    "DebugInfo",
    "SemanticInfo",
    "SemanticQueryResponse",
    "PivotAxisField",
    "PivotMetricItem",
    "PivotOptions",
    "PivotLayout",
    "PivotRequest",
    "SemanticMetadataResponse",
    "SemanticMetadataRequest",
    "SemanticQueryRequest",
    # Interfaces
    "DatasetAccessor",
    "SemanticServiceResolver",
    "LocalDatasetAccessor",
    "RemoteDatasetAccessor",
    "build_query_request",
]
