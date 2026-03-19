"""Configuration package for semantic layer."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class SemanticProperties(BaseModel):
    """Configuration properties for semantic layer.

    Contains settings for model loading, caching, and query execution.
    """

    # Model paths
    model_paths: List[str] = Field(
        default_factory=lambda: ["./models"],
        description="Paths to search for model files"
    )

    # Model file extensions
    model_extensions: List[str] = Field(
        default_factory=lambda: [".tm.json", ".qm.json"],
        description="Model file extensions to scan"
    )

    # Cache settings
    cache_enabled: bool = Field(default=True, description="Enable model caching")
    cache_ttl_seconds: int = Field(default=3600, description="Model cache TTL")

    # Query settings
    query_timeout_seconds: int = Field(default=300, description="Query timeout")
    max_result_rows: int = Field(default=100000, description="Maximum result rows")
    default_page_size: int = Field(default=20, description="Default page size")

    # Validation
    validate_on_startup: bool = Field(default=True, description="Validate models on startup")
    strict_validation: bool = Field(default=False, description="Enable strict validation")

    # Pre-aggregation
    preagg_enabled: bool = Field(default=True, description="Enable pre-aggregation")
    preagg_auto_refresh: bool = Field(default=False, description="Auto-refresh pre-aggs")

    # Debug
    debug_mode: bool = Field(default=False, description="Enable debug mode")
    log_queries: bool = Field(default=False, description="Log generated SQL queries")

    model_config = {
        "extra": "allow",
    }


class QmValidationOnStartup(BaseModel):
    """Startup validation configuration.

    Controls which validations run during application startup.
    """

    # Enable validation
    enabled: bool = Field(default=True, description="Enable startup validation")

    # Validation scope
    validate_table_models: bool = Field(default=True, description="Validate table models")
    validate_query_models: bool = Field(default=True, description="Validate query models")
    validate_datasources: bool = Field(default=True, description="Validate data source connections")
    validate_preaggregations: bool = Field(default=False, description="Validate pre-aggregations")

    # Behavior on error
    fail_on_error: bool = Field(default=False, description="Fail startup on validation error")
    log_errors: bool = Field(default=True, description="Log validation errors")

    model_config = {
        "extra": "allow",
    }