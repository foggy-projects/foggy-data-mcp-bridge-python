"""Order definition for semantic layer."""

from enum import Enum
from typing import Optional
from pydantic import Field

from foggy.dataset_model.definitions.base import AiDef


class OrderDirection(str, Enum):
    """Order direction enumeration."""

    ASC = "asc"
    DESC = "desc"


class NullSortOrder(str, Enum):
    """Null sort order enumeration."""

    FIRST = "first"
    LAST = "last"


class OrderDef(AiDef):
    """Order/sort definition for query results.

    Defines how query results should be sorted.
    """

    # Order target
    column: str = Field(..., description="Column name to order by")
    table: Optional[str] = Field(default=None, description="Table name (for disambiguation)")

    # Direction
    direction: OrderDirection = Field(default=OrderDirection.ASC, description="Sort direction")

    # Null handling
    nulls: NullSortOrder = Field(default=NullSortOrder.LAST, description="Null sort position")

    # Priority
    priority: int = Field(default=0, description="Sort priority (lower = higher priority)")

    def to_sql(self, alias: Optional[str] = None) -> str:
        """Convert to SQL ORDER BY clause.

        Args:
            alias: Optional column alias

        Returns:
            SQL ORDER BY expression
        """
        col = alias or self.column
        nulls_sql = ""
        if self.nulls == NullSortOrder.FIRST:
            nulls_sql = " NULLS FIRST"
        else:
            nulls_sql = " NULLS LAST"

        return f"{col} {self.direction.value.upper()}{nulls_sql}"

    def validate_definition(self) -> list:
        """Validate the order definition."""
        errors = super().validate_definition()

        if not self.column:
            errors.append("column is required")

        return errors