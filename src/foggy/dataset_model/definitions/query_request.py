"""Query request definitions for semantic layer queries."""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class FilterType(str, Enum):
    """Filter type enumeration."""

    SIMPLE = "simple"
    RANGE = "range"
    LIST = "list"
    EXPRESSION = "expression"
    HIERARCHY = "hierarchy"


class AggregateFunc(str, Enum):
    """Aggregate function enumeration."""

    SUM = "sum"
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    MEDIAN = "median"
    STDDEV = "stddev"
    VARIANCE = "variance"
    NONE = "none"


class SelectColumnDef(BaseModel):
    """Select column definition for query requests."""

    # Column reference
    name: str = Field(..., description="Column name")
    alias: Optional[str] = Field(default=None, description="Column alias")

    # Aggregation
    aggregate: Optional[AggregateFunc] = Field(default=None, description="Aggregate function")

    # Expression (for calculated columns)
    expression: Optional[str] = Field(default=None, description="Column expression")

    # Format
    format_pattern: Optional[str] = Field(default=None, description="Format pattern")

    model_config = {
        "extra": "allow",
    }

    def get_select_sql(self) -> str:
        """Get the SELECT expression.

        Returns:
            SQL SELECT expression
        """
        if self.expression:
            expr = self.expression
        elif self.aggregate and self.aggregate != AggregateFunc.NONE:
            agg = self.aggregate.value.upper()
            if agg == "COUNT_DISTINCT":
                expr = f"COUNT(DISTINCT {self.name})"
            else:
                expr = f"{agg}({self.name})"
        else:
            expr = self.name

        if self.alias:
            return f"{expr} AS {self.alias}"
        return expr


class CalculatedFieldDef(BaseModel):
    """Calculated field definition for computed columns.

    Supports two modes:
    1. Aggregated calculation: expression + agg → e.g. SUM(salesAmount - discountAmount)
    2. Window function: expression + partitionBy/windowOrderBy/windowFrame
       → e.g. RANK() OVER (PARTITION BY category ORDER BY amount DESC)
    """

    # Identity
    name: str = Field(..., description="Field name")
    alias: Optional[str] = Field(default=None, description="Field alias")

    # Expression
    expression: str = Field(..., description="Calculation expression")

    # Return type
    return_type: str = Field(default="string", description="Return data type")

    # Dependencies
    depends_on: List[str] = Field(default_factory=list, description="Dependent columns")

    # Aggregation (aligned with Java CalculatedFieldDef)
    agg: Optional[str] = Field(default=None, description="Aggregation type: SUM, AVG, COUNT, MAX, MIN, etc.")

    # Window function fields (aligned with Java CalculatedFieldDef)
    partition_by: List[str] = Field(default_factory=list, description="PARTITION BY field list")
    window_order_by: List[Dict[str, str]] = Field(
        default_factory=list,
        description='Window ORDER BY: [{"field": "x", "dir": "desc"}]',
    )
    window_frame: Optional[str] = Field(
        default=None,
        description="Window frame spec, e.g. ROWS BETWEEN 6 PRECEDING AND CURRENT ROW",
    )

    model_config = {
        "extra": "allow",
    }

    def is_window_function(self) -> bool:
        """Check if this calculated field uses window function semantics."""
        return bool(self.partition_by or self.window_order_by)


class CondRequestDef(BaseModel):
    """Condition request for query filtering."""

    # Condition type
    condition_type: FilterType = Field(default=FilterType.SIMPLE, description="Filter type")

    # Simple filter
    column: Optional[str] = Field(default=None, description="Column name")
    operator: str = Field(default="=", description="Comparison operator")
    value: Any = Field(default=None, description="Filter value")

    # Range filter
    from_value: Optional[Any] = Field(default=None, description="Range from value")
    to_value: Optional[Any] = Field(default=None, description="Range to value")

    # List filter
    values: Optional[List[Any]] = Field(default=None, description="List of values")

    # Expression filter
    expression: Optional[str] = Field(default=None, description="Filter expression")

    # Hierarchy filter
    hierarchy_path: Optional[List[str]] = Field(default=None, description="Hierarchy path")
    include_children: bool = Field(default=False, description="Include child nodes")

    model_config = {
        "extra": "allow",
    }

    def to_sql(self) -> str:
        """Convert to SQL WHERE clause.

        Returns:
            SQL filter expression
        """
        if self.condition_type == FilterType.SIMPLE:
            val = f"'{self.value}'" if isinstance(self.value, str) else str(self.value)
            return f"{self.column} {self.operator} {val}"

        elif self.condition_type == FilterType.RANGE:
            from_cond = f"{self.column} >= {self.from_value}"
            to_cond = f"{self.column} <= {self.to_value}"
            return f"{from_cond} AND {to_cond}"

        elif self.condition_type == FilterType.LIST:
            if self.values:
                vals = ", ".join(
                    f"'{v}'" if isinstance(v, str) else str(v) for v in self.values
                )
                return f"{self.column} IN ({vals})"
            return "1=1"

        elif self.condition_type == FilterType.EXPRESSION:
            return self.expression or "1=1"

        return "1=1"


class FilterRequestDef(BaseModel):
    """Filter request for complex filtering conditions."""

    # Logic
    logic: str = Field(default="and", description="Logic operator (and/or)")

    # Conditions
    conditions: List[Union[CondRequestDef, "FilterRequestDef"]] = Field(
        default_factory=list, description="Filter conditions"
    )

    model_config = {
        "extra": "allow",
    }

    def to_sql(self) -> str:
        """Convert to SQL WHERE clause.

        Returns:
            SQL filter expression
        """
        if not self.conditions:
            return "1=1"

        parts = []
        for cond in self.conditions:
            if isinstance(cond, FilterRequestDef):
                parts.append(f"({cond.to_sql()})")
            else:
                parts.append(cond.to_sql())

        logic_op = " AND " if self.logic == "and" else " OR "
        return logic_op.join(parts)


class GroupRequestDef(BaseModel):
    """Group by request for query aggregation."""

    # Column reference
    column: str = Field(..., description="Column name to group by")
    alias: Optional[str] = Field(default=None, description="Group alias")

    # Time-based grouping
    time_granularity: Optional[str] = Field(default=None, description="Time granularity (day, week, month, year)")

    # Bucket grouping
    bucket_size: Optional[float] = Field(default=None, description="Bucket size for numeric grouping")

    model_config = {
        "extra": "allow",
    }

    def get_group_sql(self) -> str:
        """Get the GROUP BY expression.

        Returns:
            SQL GROUP BY expression
        """
        if self.time_granularity:
            # Time-based grouping
            granularity = self.time_granularity.lower()
            if granularity == "year":
                return f"YEAR({self.column})"
            elif granularity == "month":
                return f"DATE_FORMAT({self.column}, '%Y-%m')"
            elif granularity == "week":
                return f"DATE_FORMAT({self.column}, '%Y-%u')"
            elif granularity == "day":
                return f"DATE({self.column})"
            elif granularity == "hour":
                return f"DATE_FORMAT({self.column}, '%Y-%m-%d %H:00')"

        if self.bucket_size:
            return f"FLOOR({self.column} / {self.bucket_size}) * {self.bucket_size}"

        return self.column


class OrderRequestDef(BaseModel):
    """Order by request for query sorting."""

    # Column reference
    column: str = Field(..., description="Column name to order by")
    alias: Optional[str] = Field(default=None, description="Column alias")

    # Direction
    direction: str = Field(default="asc", description="Sort direction (asc/desc)")

    # Null handling
    nulls: str = Field(default="last", description="Null position (first/last)")

    # Priority
    priority: int = Field(default=0, description="Sort priority")

    model_config = {
        "extra": "allow",
    }

    def to_sql(self) -> str:
        """Convert to SQL ORDER BY clause.

        Returns:
            SQL ORDER BY expression
        """
        nulls_sql = " NULLS FIRST" if self.nulls == "first" else " NULLS LAST"
        return f"{self.alias or self.column} {self.direction}{nulls_sql}"


class SliceRequestDef(BaseModel):
    """Slice/dice request for multi-dimensional analysis."""

    # Dimensions to slice by
    dimensions: List[str] = Field(default_factory=list, description="Dimensions for slicing")

    # Page slice (for pagination)
    page: int = Field(default=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, description="Page size")

    # Top/Bottom N
    top_n: Optional[int] = Field(default=None, description="Top N results")
    bottom_n: Optional[int] = Field(default=None, description="Bottom N results")

    # Sort by measure for top/bottom
    sort_measure: Optional[str] = Field(default=None, description="Measure for top/bottom sorting")
    sort_direction: str = Field(default="desc", description="Sort direction for top/bottom")

    model_config = {
        "extra": "allow",
    }

    def get_offset(self) -> int:
        """Calculate the row offset for pagination.

        Returns:
            Row offset
        """
        return (self.page - 1) * self.page_size


class WindowOrderDef(BaseModel):
    """Window function order definition."""

    # Order columns
    columns: List[OrderRequestDef] = Field(default_factory=list, description="Order columns")

    # Frame specification
    frame_type: Optional[str] = Field(default=None, description="Frame type (ROWS/RANGE)")
    frame_start: Optional[str] = Field(default=None, description="Frame start")
    frame_end: Optional[str] = Field(default=None, description="Frame end")

    model_config = {
        "extra": "allow",
    }

    def to_sql(self) -> str:
        """Convert to SQL window ORDER BY clause.

        Returns:
            SQL ORDER BY expression
        """
        if not self.columns:
            return ""

        order_parts = [col.to_sql() for col in self.columns]
        order_clause = ", ".join(order_parts)

        if self.frame_type:
            frame_clause = f"{self.frame_type} BETWEEN {self.frame_start} AND {self.frame_end}"
            return f"ORDER BY {order_clause} {frame_clause}"

        return f"ORDER BY {order_clause}"


# Enable forward references
FilterRequestDef.model_rebuild()