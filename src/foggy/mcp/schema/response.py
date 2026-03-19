"""MCP Response schema definitions."""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class ResponseStatus(str, Enum):
    """Response status enumeration."""

    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


class McpError(BaseModel):
    """MCP error object."""

    code: int = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Additional error data")

    # Standard JSON-RPC error codes
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # Custom error codes
    QUERY_ERROR = -32001
    AUTHENTICATION_ERROR = -32002
    AUTHORIZATION_ERROR = -32003
    RESOURCE_NOT_FOUND = -32004
    VALIDATION_ERROR = -32005
    TIMEOUT_ERROR = -32006

    @classmethod
    def parse_error(cls, message: str = "Parse error") -> "McpError":
        """Create a parse error."""
        return cls(code=cls.PARSE_ERROR, message=message)

    @classmethod
    def invalid_request(cls, message: str = "Invalid request") -> "McpError":
        """Create an invalid request error."""
        return cls(code=cls.INVALID_REQUEST, message=message)

    @classmethod
    def method_not_found(cls, method: str) -> "McpError":
        """Create a method not found error."""
        return cls(code=cls.METHOD_NOT_FOUND, message=f"Method not found: {method}")

    @classmethod
    def invalid_params(cls, message: str) -> "McpError":
        """Create an invalid params error."""
        return cls(code=cls.INVALID_PARAMS, message=message)

    @classmethod
    def internal_error(cls, message: str = "Internal error") -> "McpError":
        """Create an internal error."""
        return cls(code=cls.INTERNAL_ERROR, message=message)

    @classmethod
    def query_error(cls, message: str, data: Optional[Dict[str, Any]] = None) -> "McpError":
        """Create a query error."""
        return cls(code=cls.QUERY_ERROR, message=message, data=data)

    @classmethod
    def authentication_error(cls, message: str = "Authentication failed") -> "McpError":
        """Create an authentication error."""
        return cls(code=cls.AUTHENTICATION_ERROR, message=message)

    @classmethod
    def authorization_error(cls, message: str = "Access denied") -> "McpError":
        """Create an authorization error."""
        return cls(code=cls.AUTHORIZATION_ERROR, message=message)

    @classmethod
    def validation_error(cls, message: str, errors: Optional[List[str]] = None) -> "McpError":
        """Create a validation error."""
        return cls(code=cls.VALIDATION_ERROR, message=message, data={"errors": errors} if errors else None)


class McpResponse(BaseModel):
    """MCP response object following JSON-RPC 2.0 specification."""

    # Response identification
    id: Optional[str] = Field(default=None, description="Request ID this response corresponds to")
    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")

    # Response content (one of result or error)
    result: Optional[Any] = Field(default=None, description="Result data on success")
    error: Optional[McpError] = Field(default=None, description="Error object on failure")

    # Response metadata
    status: ResponseStatus = Field(default=ResponseStatus.SUCCESS, description="Response status")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    duration_ms: Optional[float] = Field(default=None, description="Request duration in milliseconds")

    model_config = {"extra": "allow"}

    @classmethod
    def success(cls, result: Any, request_id: Optional[str] = None) -> "McpResponse":
        """Create a successful response."""
        return cls(
            id=request_id,
            result=result,
            status=ResponseStatus.SUCCESS,
            error=None
        )

    @classmethod
    def failure(cls, error: McpError, request_id: Optional[str] = None) -> "McpResponse":
        """Create a failure response."""
        return cls(
            id=request_id,
            result=None,
            status=ResponseStatus.ERROR,
            error=error
        )

    def is_success(self) -> bool:
        """Check if response is successful."""
        return self.error is None


class QueryResult(BaseModel):
    """Query result data."""

    # Result data
    columns: List[str] = Field(default_factory=list, description="Column names")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="Result rows")
    total_rows: int = Field(default=0, description="Total row count")

    # Pagination
    has_more: bool = Field(default=False, description="Whether more rows exist")
    page: Optional[int] = Field(default=None, description="Current page")
    page_size: Optional[int] = Field(default=None, description="Page size")

    # Metadata
    query_time_ms: Optional[float] = Field(default=None, description="Query execution time")
    from_cache: bool = Field(default=False, description="Whether result is from cache")

    # Totals (when requested)
    totals: Optional[Dict[str, Any]] = Field(default=None, description="Aggregate totals")

    model_config = {"extra": "allow"}


class MetadataResult(BaseModel):
    """Model metadata result."""

    # Basic info
    name: str = Field(..., description="Model name")
    alias: Optional[str] = Field(default=None, description="Display name")
    description: Optional[str] = Field(default=None, description="Model description")
    model_type: str = Field(default="query_model", description="Model type")

    # Schema info
    columns: List[Dict[str, Any]] = Field(default_factory=list, description="Column definitions")
    measures: List[Dict[str, Any]] = Field(default_factory=list, description="Measure definitions")
    dimensions: List[Dict[str, Any]] = Field(default_factory=list, description="Dimension definitions")

    # AI info
    ai_description: Optional[str] = Field(default=None, description="AI-friendly description")
    ai_examples: List[str] = Field(default_factory=list, description="Example queries")

    # Access info
    access_type: str = Field(default="read", description="Access type")
    supported_operations: List[str] = Field(default_factory=list, description="Supported operations")

    model_config = {"extra": "allow"}