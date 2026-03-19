"""MCP Server properties and configuration."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class McpProperties(BaseModel):
    """MCP server configuration properties."""

    # Server settings
    server_name: str = Field(default="foggy-mcp", description="MCP server name")
    server_version: str = Field(default="1.0.0", description="Server version")
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8080, description="Server port")

    # Feature toggles
    enable_query_tools: bool = Field(default=True, description="Enable query tools")
    enable_metadata_tools: bool = Field(default=True, description="Enable metadata tools")
    enable_chart_tools: bool = Field(default=False, description="Enable chart tools")
    enable_export_tools: bool = Field(default=False, description="Enable export tools")

    # Query settings
    max_query_rows: int = Field(default=10000, description="Maximum rows per query")
    query_timeout_seconds: int = Field(default=30, description="Query timeout in seconds")

    # Tool settings
    tool_timeout_seconds: int = Field(default=60, description="Tool execution timeout")
    enable_tool_audit: bool = Field(default=True, description="Enable tool audit logging")

    # Model settings
    model_directories: List[str] = Field(
        default_factory=lambda: ["./models"],
        description="Directories to load TM/QM models from"
    )
    auto_reload_models: bool = Field(default=False, description="Auto reload models on file change")

    model_config = {"extra": "allow"}


class AuthProperties(BaseModel):
    """Authentication configuration properties."""

    # Auth settings
    enabled: bool = Field(default=False, description="Enable authentication")
    auth_type: str = Field(default="none", description="Authentication type: none, api_key, jwt, oauth2")

    # API Key auth
    api_key_header: str = Field(default="X-API-Key", description="API key header name")
    api_keys: List[str] = Field(default_factory=list, description="Valid API keys")

    # JWT auth
    jwt_secret: Optional[str] = Field(default=None, description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_issuer: Optional[str] = Field(default=None, description="JWT issuer")
    jwt_audience: Optional[str] = Field(default=None, description="JWT audience")

    # OAuth2 auth
    oauth2_authorization_url: Optional[str] = Field(default=None, description="OAuth2 authorization URL")
    oauth2_token_url: Optional[str] = Field(default=None, description="OAuth2 token URL")
    oauth2_client_id: Optional[str] = Field(default=None, description="OAuth2 client ID")
    oauth2_client_secret: Optional[str] = Field(default=None, description="OAuth2 client secret")

    # Role mapping
    admin_roles: List[str] = Field(default_factory=lambda: ["admin"], description="Admin roles")
    analyst_roles: List[str] = Field(default_factory=lambda: ["analyst"], description="Analyst roles")
    business_roles: List[str] = Field(default_factory=lambda: ["business"], description="Business roles")

    model_config = {"extra": "allow"}


class PerformanceInfo(BaseModel):
    """Performance tracking information."""

    start_time: float = Field(default=0.0, description="Start timestamp")
    end_time: Optional[float] = Field(default=None, description="End timestamp")
    duration_ms: Optional[float] = Field(default=None, description="Duration in milliseconds")
    query_count: int = Field(default=0, description="Number of queries executed")
    total_rows: int = Field(default=0, description="Total rows processed")

    def start(self) -> None:
        """Mark start time."""
        import time
        self.start_time = time.time()

    def end(self) -> None:
        """Mark end time and calculate duration."""
        import time
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000


class FieldInfo(BaseModel):
    """Field metadata information."""

    name: str = Field(..., description="Field name")
    field_type: str = Field(..., description="Field data type")
    nullable: bool = Field(default=True, description="Whether field can be null")
    description: Optional[str] = Field(default=None, description="Field description")
    default_value: Optional[Any] = Field(default=None, description="Default value")


class ParameterInfo(BaseModel):
    """Tool parameter information."""

    name: str = Field(..., description="Parameter name")
    param_type: str = Field(default="string", description="Parameter type")
    required: bool = Field(default=True, description="Whether parameter is required")
    description: Optional[str] = Field(default=None, description="Parameter description")
    default_value: Optional[Any] = Field(default=None, description="Default value")
    enum_values: Optional[List[str]] = Field(default=None, description="Allowed enum values")


class ReturnInfo(BaseModel):
    """Return value information."""

    return_type: str = Field(..., description="Return type")
    description: Optional[str] = Field(default=None, description="Return value description")
    fields: List[FieldInfo] = Field(default_factory=list, description="Return fields for object types")