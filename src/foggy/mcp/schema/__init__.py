"""MCP Schema module for request/response objects."""

from foggy.mcp.schema.request import McpRequest, McpRequestContext
from foggy.mcp.schema.response import McpResponse, McpError
from foggy.mcp.schema.query import DatasetNLQueryRequest, DatasetNLQueryResponse
from foggy.mcp.schema.tool import ToolCallRequest, ToolCallResult

__all__ = [
    "McpRequest",
    "McpRequestContext",
    "McpResponse",
    "McpError",
    "DatasetNLQueryRequest",
    "DatasetNLQueryResponse",
    "ToolCallRequest",
    "ToolCallResult",
]