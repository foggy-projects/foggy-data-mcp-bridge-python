"""Query model definition for semantic layer."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from foggy.dataset_model.definitions.base import AiDef


class QueryModelType(str, Enum):
    """Query model type enumeration."""

    TABLE = "table"  # Based on a single table
    SQL = "sql"  # Custom SQL query
    JOIN = "join"  # Multiple tables joined
    NESTED = "nested"  # Nested/inline query model


class QueryConditionDef(BaseModel):
    """Query condition definition for filtering."""

    # Condition type
    condition_type: str = Field(default="simple", description="Condition type: simple, nested, or")

    # Simple condition
    column: Optional[str] = Field(default=None, description="Column name")
    operator: str = Field(default="=", description="Operator (=, !=, >, <, >=, <=, IN, LIKE, etc.)")
    value: Any = Field(default=None, description="Filter value")

    # Nested conditions (for and/or groups)
    conditions: List["QueryConditionDef"] = Field(default_factory=list, description="Nested conditions")
    logic: str = Field(default="and", description="Logic for nested conditions (and/or)")

    model_config = {
        "extra": "allow",
    }

    def to_sql(self, param_style: bool = False) -> str:
        """Convert condition to SQL WHERE clause.

        Args:
            param_style: Use parameter placeholder style

        Returns:
            SQL condition expression
        """
        if self.condition_type == "simple":
            if self.operator.upper() in ("IN", "NOT IN"):
                if isinstance(self.value, list):
                    values = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in self.value)
                    return f"{self.column} {self.operator} ({values})"
            elif self.operator.upper() in ("IS NULL", "IS NOT NULL"):
                return f"{self.column} {self.operator}"
            elif self.operator.upper() in ("LIKE", "NOT LIKE"):
                return f"{self.column} {self.operator} '{self.value}'"
            else:
                val = f"'{self.value}'" if isinstance(self.value, str) else str(self.value)
                return f"{self.column} {self.operator} {val}"

        elif self.condition_type in ("nested", "or"):
            condition_strs = [c.to_sql(param_style) for c in self.conditions]
            logic_op = " AND " if self.logic == "and" else " OR "
            return f"({logic_op.join(condition_strs)})"

        return ""


class JoinDef(BaseModel):
    """Join definition for multi-table query models."""

    # Join type
    join_type: str = Field(default="INNER", description="Join type (INNER, LEFT, RIGHT, FULL)")

    # Source table
    table: str = Field(..., description="Table name to join")
    alias: Optional[str] = Field(default=None, description="Table alias")

    # Join conditions
    on_conditions: List[QueryConditionDef] = Field(
        default_factory=list, description="ON conditions"
    )

    # Join expression (raw SQL)
    on_expression: Optional[str] = Field(default=None, description="Raw ON expression")

    model_config = {
        "extra": "allow",
    }

    def to_sql(self) -> str:
        """Convert to SQL JOIN clause.

        Returns:
            SQL JOIN expression
        """
        alias_part = f" AS {self.alias}" if self.alias else ""
        on_part = self.on_expression or " AND ".join(c.to_sql() for c in self.on_conditions)
        return f"{self.join_type} JOIN {self.table}{alias_part} ON {on_part}"


class DbQueryModelDef(AiDef):
    """Query model definition - the core semantic model.

    A Query Model (QM) is a semantic view that transforms raw data
    into business-meaningful representations with dimensions, measures,
    and pre-defined filters.
    """

    # Model type
    model_type: QueryModelType = Field(default=QueryModelType.TABLE, description="Model type")

    # Source (for table-based models)
    source_table: Optional[str] = Field(default=None, description="Source table name")
    source_schema: Optional[str] = Field(default=None, description="Source schema name")
    source_datasource: Optional[str] = Field(default=None, description="Data source name")

    # SQL (for SQL-based models)
    source_sql: Optional[str] = Field(default=None, description="Custom SQL query")

    # Joins (for join-based models)
    joins: List[JoinDef] = Field(default_factory=list, description="Join definitions")

    # Dimensions
    dimensions: List[str] = Field(default_factory=list, description="Dimension column names")

    # Measures
    measures: List[str] = Field(default_factory=list, description="Measure names")

    # Default conditions
    default_conditions: List[QueryConditionDef] = Field(
        default_factory=list, description="Default filter conditions"
    )

    # Default ordering
    default_orders: List[str] = Field(default_factory=list, description="Default order columns")

    # Row limit
    default_limit: Optional[int] = Field(default=None, description="Default row limit")

    # Cache settings
    cache_enabled: bool = Field(default=False, description="Enable result caching")
    cache_ttl_seconds: int = Field(default=300, description="Cache TTL in seconds")

    # Security
    row_level_security: bool = Field(default=False, description="Enable row-level security")
    access_control: Optional[str] = Field(default=None, description="Access control definition name")

    model_config = {
        "extra": "allow",
    }

    def get_source_expression(self) -> str:
        """Get the source expression (table, SQL, or joins).

        Returns:
            Source SQL expression
        """
        if self.model_type == QueryModelType.TABLE:
            schema_prefix = f"{self.source_schema}." if self.source_schema else ""
            return f"{schema_prefix}{self.source_table}"

        elif self.model_type == QueryModelType.SQL:
            return f"({self.source_sql})"

        elif self.model_type == QueryModelType.JOIN:
            # Start with main table
            parts = [self.source_table or "main_table"]
            # Add joins
            for join in self.joins:
                parts.append(join.to_sql())
            return " ".join(parts)

        return self.source_table or ""

    def get_dimension_list(self) -> List[str]:
        """Get list of dimension column names.

        Returns:
            List of dimension names
        """
        return self.dimensions.copy()

    def get_measure_list(self) -> List[str]:
        """Get list of measure names.

        Returns:
            List of measure names
        """
        return self.measures.copy()

    def validate_definition(self) -> List[str]:
        """Validate the query model definition."""
        errors = super().validate_definition()

        if self.model_type == QueryModelType.TABLE and not self.source_table:
            errors.append("source_table is required for table-based models")

        if self.model_type == QueryModelType.SQL and not self.source_sql:
            errors.append("source_sql is required for SQL-based models")

        if self.model_type == QueryModelType.JOIN and not self.joins:
            errors.append("joins are required for join-based models")

        return errors


# Enable forward references
QueryConditionDef.model_rebuild()