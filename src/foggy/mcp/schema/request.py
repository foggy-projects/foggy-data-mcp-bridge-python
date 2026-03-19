"""MCP Request schema definitions."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class McpRequestContext(BaseModel):
    """MCP request context containing user and session information."""

    # User context
    user_id: Optional[str] = Field(default=None, description="User identifier")
    user_name: Optional[str] = Field(default=None, description="User name")
    user_roles: List[str] = Field(default_factory=list, description="User roles")

    # Session context
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    conversation_id: Optional[str] = Field(default=None, description="Conversation identifier")

    # Request metadata
    request_id: Optional[str] = Field(default=None, description="Request ID for tracing")
    client_ip: Optional[str] = Field(default=None, description="Client IP address")
    user_agent: Optional[str] = Field(default=None, description="Client user agent")
    timestamp: datetime = Field(default_factory=datetime.now, description="Request timestamp")

    # Configuration overrides
    locale: str = Field(default="zh-CN", description="Locale for messages")
    timezone: Optional[str] = Field(default=None, description="User timezone")

    # Additional context
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context data")

    model_config = {"extra": "allow"}


class McpRequest(BaseModel):
    """Base MCP request object."""

    # Request identification
    id: Optional[str] = Field(default=None, description="Request ID")
    method: str = Field(..., description="Method name")

    # Request context
    context: McpRequestContext = Field(default_factory=McpRequestContext, description="Request context")

    # Request parameters
    params: Dict[str, Any] = Field(default_factory=dict, description="Request parameters")

    # MCP specific
    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")

    model_config = {"extra": "allow"}

    def get_param(self, name: str, default: Any = None) -> Any:
        """Get a parameter value by name."""
        return self.params.get(name, default)

    def set_param(self, name: str, value: Any) -> None:
        """Set a parameter value."""
        self.params[name] = value


class QueryRequest(BaseModel):
    """Query request for data retrieval."""

    # Query identification
    query_model: str = Field(..., description="Query model name")
    table_model: Optional[str] = Field(default=None, description="Table model name")

    # Selection
    select: List[str] = Field(default_factory=list, description="Columns to select")
    measures: List[str] = Field(default_factory=list, description="Measures to calculate")

    # Filtering
    where: Optional[str] = Field(default=None, description="WHERE clause expression")
    filters: List[Dict[str, Any]] = Field(default_factory=list, description="Filter definitions")

    # Grouping
    group_by: List[str] = Field(default_factory=list, description="Group by columns")
    time_granularity: Optional[str] = Field(default=None, description="Time grouping granularity")

    # Ordering
    order_by: List[Dict[str, str]] = Field(default_factory=list, description="Order by specifications")

    # Pagination
    limit: Optional[int] = Field(default=None, description="Maximum rows to return")
    offset: Optional[int] = Field(default=None, description="Offset for pagination")

    # Options
    distinct: bool = Field(default=False, description="Return distinct rows")
    include_totals: bool = Field(default=False, description="Include total counts")

    model_config = {"extra": "allow"}


class MetadataRequest(BaseModel):
    """Request for model metadata."""

    model_name: str = Field(..., description="Model name to query")
    include_columns: bool = Field(default=True, description="Include column information")
    include_measures: bool = Field(default=True, description="Include measure information")
    include_dimensions: bool = Field(default=True, description="Include dimension information")
    include_examples: bool = Field(default=False, description="Include AI examples")

    model_config = {"extra": "allow"}