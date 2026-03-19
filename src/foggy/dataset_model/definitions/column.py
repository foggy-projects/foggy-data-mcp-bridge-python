"""Column group definition for semantic layer."""

from typing import List, Optional
from pydantic import Field

from foggy.dataset_model.definitions.base import AiDef


class DbColumnGroupDef(AiDef):
    """Column group definition for logical grouping of columns.

    Used to organize columns into logical groups for better
    organization and UI presentation in semantic models.
    """

    # Column references
    columns: List[str] = Field(default_factory=list, description="Column names in this group")

    # Display settings
    display_order: int = Field(default=0, description="Display order for UI")
    collapsed: bool = Field(default=False, description="Whether group is collapsed by default")

    # Parent group (for nested groups)
    parent_group: Optional[str] = Field(default=None, description="Parent group name")

    def add_column(self, column_name: str) -> "DbColumnGroupDef":
        """Add a column to this group.

        Args:
            column_name: Name of column to add

        Returns:
            Self for chaining
        """
        if column_name not in self.columns:
            self.columns.append(column_name)
        return self

    def remove_column(self, column_name: str) -> "DbColumnGroupDef":
        """Remove a column from this group.

        Args:
            column_name: Name of column to remove

        Returns:
            Self for chaining
        """
        if column_name in self.columns:
            self.columns.remove(column_name)
        return self

    def has_column(self, column_name: str) -> bool:
        """Check if a column is in this group.

        Args:
            column_name: Name of column to check

        Returns:
            True if column is in group
        """
        return column_name in self.columns

    def validate_definition(self) -> List[str]:
        """Validate the column group definition."""
        errors = super().validate_definition()

        if not self.columns:
            errors.append("columns list cannot be empty")

        return errors