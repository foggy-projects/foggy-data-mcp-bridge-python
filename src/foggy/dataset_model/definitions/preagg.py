"""Pre-aggregation definitions for query optimization."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from foggy.dataset_model.definitions.base import AiDef


class PreAggStatus(str, Enum):
    """Pre-aggregation status enumeration."""

    PENDING = "pending"
    BUILDING = "building"
    READY = "ready"
    ERROR = "error"
    DISABLED = "disabled"


class PreAggRefreshType(str, Enum):
    """Pre-aggregation refresh type enumeration."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    AUTO = "auto"
    EVENT_BASED = "event_based"


class PreAggRefreshDef(BaseModel):
    """Pre-aggregation refresh strategy definition."""

    # Refresh type
    refresh_type: PreAggRefreshType = Field(
        default=PreAggRefreshType.MANUAL, description="Refresh type"
    )

    # Schedule (for scheduled refresh)
    cron_expression: Optional[str] = Field(default=None, description="Cron expression for schedule")
    timezone: str = Field(default="UTC", description="Timezone for schedule")

    # Auto refresh settings
    auto_refresh_interval_minutes: int = Field(default=60, description="Auto refresh interval")
    auto_refresh_on_data_change: bool = Field(default=False, description="Refresh on data change")

    # Event-based refresh
    event_source: Optional[str] = Field(default=None, description="Event source for event-based refresh")

    # Retry settings
    max_retries: int = Field(default=3, description="Max retry attempts")
    retry_delay_seconds: int = Field(default=60, description="Retry delay")

    model_config = {
        "extra": "allow",
    }


class PreAggFilterDef(BaseModel):
    """Pre-aggregation filter definition."""

    # Filter expression
    column: str = Field(..., description="Column name to filter")
    operator: str = Field(..., description="Filter operator (=, >, <, IN, etc.)")
    value: Any = Field(..., description="Filter value")

    # Filter type
    filter_type: str = Field(default="static", description="Filter type: static, dynamic")

    model_config = {
        "extra": "allow",
    }

    def to_sql(self) -> str:
        """Convert to SQL WHERE clause.

        Returns:
            SQL filter expression
        """
        if self.operator.upper() in ("IN", "NOT IN"):
            if isinstance(self.value, list):
                values = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in self.value)
                return f"{self.column} {self.operator} ({values})"
        elif self.operator.upper() in ("IS NULL", "IS NOT NULL"):
            return f"{self.column} {self.operator}"
        else:
            val = f"'{self.value}'" if isinstance(self.value, str) else str(self.value)
            return f"{self.column} {self.operator} {val}"

        return f"{self.column} {self.operator} {self.value}"


class PreAggMeasureDef(BaseModel):
    """Pre-aggregation measure definition."""

    # Measure reference
    measure_name: str = Field(..., description="Source measure name")
    alias: Optional[str] = Field(default=None, description="Alias in pre-agg table")

    # Aggregation
    aggregation: str = Field(default="sum", description="Aggregation type")

    model_config = {
        "extra": "allow",
    }


class PreAggregationDef(AiDef):
    """Pre-aggregation table definition for query optimization.

    Pre-aggregations are materialized views that pre-compute
    aggregations for faster query performance.
    """

    # Target
    query_model: str = Field(..., description="Target query model name")

    # Dimensions (group by columns)
    dimensions: List[str] = Field(default_factory=list, description="Dimension columns")

    # Measures (aggregations)
    measures: List[PreAggMeasureDef] = Field(default_factory=list, description="Measures to pre-aggregate")

    # Filters (partition data)
    filters: List[PreAggFilterDef] = Field(default_factory=list, description="Filters for pre-agg data")

    # Storage
    target_table: Optional[str] = Field(default=None, description="Target table name (auto-generated if None)")
    target_datasource: Optional[str] = Field(default=None, description="Target data source")

    # Status
    status: PreAggStatus = Field(default=PreAggStatus.PENDING, description="Current status")

    # Refresh strategy
    refresh: PreAggRefreshDef = Field(
        default_factory=PreAggRefreshDef, description="Refresh strategy"
    )

    # Statistics
    row_count: Optional[int] = Field(default=None, description="Number of rows in pre-agg table")
    size_bytes: Optional[int] = Field(default=None, description="Size in bytes")
    last_refresh_time: Optional[datetime] = Field(default=None, description="Last refresh time")
    last_refresh_duration_ms: Optional[int] = Field(default=None, description="Last refresh duration")

    # Match settings
    exact_match_only: bool = Field(default=False, description="Only use for exact dimension matches")
    priority: int = Field(default=0, description="Priority for matching (higher = preferred)")

    model_config = {
        "extra": "allow",
    }

    def get_target_table_name(self) -> str:
        """Get the target table name (generate if not specified).

        Returns:
            Target table name
        """
        if self.target_table:
            return self.target_table

        # Auto-generate table name
        dim_suffix = "_".join(self.dimensions[:3]) if self.dimensions else "all"
        return f"preagg_{self.query_model}_{dim_suffix}"

    def is_refresh_needed(self) -> bool:
        """Check if refresh is needed.

        Returns:
            True if refresh is needed
        """
        if self.status == PreAggStatus.DISABLED:
            return False

        if self.status in (PreAggStatus.PENDING, PreAggStatus.ERROR):
            return True

        if self.refresh.refresh_type == PreAggRefreshType.MANUAL:
            return False

        if self.refresh.refresh_type == PreAggRefreshType.AUTO:
            if self.last_refresh_time:
                elapsed = (datetime.now() - self.last_refresh_time).total_seconds() / 60
                return elapsed >= self.refresh.auto_refresh_interval_minutes

        return False

    def validate_definition(self) -> List[str]:
        """Validate the pre-aggregation definition."""
        errors = super().validate_definition()

        if not self.dimensions:
            errors.append("dimensions cannot be empty")

        if not self.measures:
            errors.append("measures cannot be empty")

        if not self.query_model:
            errors.append("query_model is required")

        return errors