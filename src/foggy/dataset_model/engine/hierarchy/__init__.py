"""Hierarchy operators for closure table support.

This module implements hierarchy traversal operators commonly used
with closure tables for hierarchical dimension queries.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field


class HierarchyDirection(str, Enum):
    """Hierarchy traversal direction."""

    UP = "up"  # Towards root
    DOWN = "down"  # Towards leaves


class HierarchyOperator(ABC, BaseModel):
    """Base class for hierarchy operators.

    Hierarchy operators are used to traverse hierarchical
    dimensions like organization charts, product categories, etc.
    """

    # Target dimension/column
    dimension: str = Field(..., description="Dimension/column to operate on")

    # Target member
    member_value: Any = Field(..., description="Starting member value")

    @abstractmethod
    def get_member_condition(self, column: str) -> str:
        """Get the SQL condition for selecting members.

        Args:
            column: Column name

        Returns:
            SQL condition expression
        """
        pass

    @abstractmethod
    def get_descendants(self, closure_table: str, depth_column: str = "depth") -> str:
        """Get SQL for descendant lookup in closure table.

        Args:
            closure_table: Closure table name
            depth_column: Depth column name

        Returns:
            SQL subquery for descendants
        """
        pass


class ChildrenOfOperator(HierarchyOperator):
    """Operator to get direct children of a hierarchy member.

    Returns only the immediate children (depth = 1) of the
    specified member in the hierarchy.
    """

    def get_member_condition(self, column: str) -> str:
        """Get condition for direct children.

        Args:
            column: Column name

        Returns:
            SQL condition for children
        """
        # For closure table: child_id WHERE parent_id = member_value AND depth = 1
        return f"{column} = {self._format_value(self.member_value)}"

    def get_descendants(self, closure_table: str, depth_column: str = "depth") -> str:
        """Get SQL for children lookup.

        Args:
            closure_table: Closure table name
            depth_column: Depth column name

        Returns:
            SQL subquery for children
        """
        return f"""
            SELECT child_id FROM {closure_table}
            WHERE parent_id = {self._format_value(self.member_value)}
            AND {depth_column} = 1
        """

    def _format_value(self, value: Any) -> str:
        """Format value for SQL.

        Args:
            value: Value to format

        Returns:
            SQL-formatted value
        """
        if value is None:
            return "NULL"
        elif isinstance(value, str):
            escaped = value.replace("'", "''")
            return f"'{escaped}'"
        else:
            return str(value)


class DescendantsOfOperator(HierarchyOperator):
    """Operator to get all descendants of a hierarchy member.

    Returns all descendants (children, grandchildren, etc.)
    of the specified member, but NOT the member itself.
    """

    # Maximum depth (None = unlimited)
    max_depth: Optional[int] = Field(default=None, description="Maximum depth to traverse")

    def get_member_condition(self, column: str) -> str:
        """Get condition for descendants.

        Args:
            column: Column name

        Returns:
            SQL condition for descendants
        """
        # For closure table: child_id WHERE parent_id = member_value AND depth > 0
        return f"{column} IN (SELECT child_id FROM ... WHERE parent_id = {self._format_value(self.member_value)} AND depth > 0)"

    def get_descendants(self, closure_table: str, depth_column: str = "depth") -> str:
        """Get SQL for descendants lookup.

        Args:
            closure_table: Closure table name
            depth_column: Depth column name

        Returns:
            SQL subquery for all descendants
        """
        depth_condition = ""
        if self.max_depth is not None:
            depth_condition = f" AND {depth_column} <= {self.max_depth}"

        return f"""
            SELECT child_id FROM {closure_table}
            WHERE parent_id = {self._format_value(self.member_value)}
            AND {depth_column} > 0
            {depth_condition}
        """

    def _format_value(self, value: Any) -> str:
        """Format value for SQL."""
        if value is None:
            return "NULL"
        elif isinstance(value, str):
            escaped = value.replace("'", "''")
            return f"'{escaped}'"
        else:
            return str(value)


class SelfAndDescendantsOfOperator(HierarchyOperator):
    """Operator to get a member and all its descendants.

    Returns the member itself plus all descendants
    (children, grandchildren, etc.).
    """

    # Maximum depth (None = unlimited)
    max_depth: Optional[int] = Field(default=None, description="Maximum depth to traverse")

    def get_member_condition(self, column: str) -> str:
        """Get condition for self and descendants.

        Args:
            column: Column name

        Returns:
            SQL condition for self and descendants
        """
        # For closure table: includes self (depth = 0) and all descendants (depth > 0)
        return f"{column} IN (SELECT child_id FROM ... WHERE parent_id = {self._format_value(self.member_value)})"

    def get_descendants(self, closure_table: str, depth_column: str = "depth") -> str:
        """Get SQL for self and descendants lookup.

        Args:
            closure_table: Closure table name
            depth_column: Depth column name

        Returns:
            SQL subquery for self and all descendants
        """
        depth_condition = ""
        if self.max_depth is not None:
            depth_condition = f" AND {depth_column} <= {self.max_depth}"

        return f"""
            SELECT child_id FROM {closure_table}
            WHERE parent_id = {self._format_value(self.member_value)}
            {depth_condition}
        """

    def _format_value(self, value: Any) -> str:
        """Format value for SQL."""
        if value is None:
            return "NULL"
        elif isinstance(value, str):
            escaped = value.replace("'", "''")
            return f"'{escaped}'"
        else:
            return str(value)


class AncestorsOfOperator(HierarchyOperator):
    """Operator to get all ancestors of a hierarchy member.

    Returns all ancestors (parent, grandparent, etc.)
    of the specified member, but NOT the member itself.
    """

    # Maximum depth (None = unlimited)
    max_depth: Optional[int] = Field(default=None, description="Maximum depth to traverse")

    def get_member_condition(self, column: str) -> str:
        """Get condition for ancestors.

        Args:
            column: Column name

        Returns:
            SQL condition for ancestors
        """
        return f"{column} IN (SELECT parent_id FROM ... WHERE child_id = {self._format_value(self.member_value)} AND depth > 0)"

    def get_ancestors(self, closure_table: str, depth_column: str = "depth") -> str:
        """Get SQL for ancestors lookup.

        Args:
            closure_table: Closure table name
            depth_column: Depth column name

        Returns:
            SQL subquery for all ancestors
        """
        depth_condition = ""
        if self.max_depth is not None:
            depth_condition = f" AND {depth_column} <= {self.max_depth}"

        return f"""
            SELECT parent_id FROM {closure_table}
            WHERE child_id = {self._format_value(self.member_value)}
            AND {depth_column} > 0
            {depth_condition}
        """

    def get_descendants(self, closure_table: str, depth_column: str = "depth") -> str:
        """Not applicable for ancestors operator."""
        raise NotImplementedError("Use get_ancestors() for AncestorsOfOperator")

    def _format_value(self, value: Any) -> str:
        """Format value for SQL."""
        if value is None:
            return "NULL"
        elif isinstance(value, str):
            escaped = value.replace("'", "''")
            return f"'{escaped}'"
        else:
            return str(value)


class SelfAndAncestorsOfOperator(HierarchyOperator):
    """Operator to get a member and all its ancestors.

    Returns the member itself plus all ancestors
    (parent, grandparent, etc.) up to the root.
    """

    # Maximum depth (None = unlimited)
    max_depth: Optional[int] = Field(default=None, description="Maximum depth to traverse")

    def get_member_condition(self, column: str) -> str:
        """Get condition for self and ancestors."""
        return f"{column} IN (SELECT parent_id FROM ... WHERE child_id = {self._format_value(self.member_value)})"

    def get_ancestors(self, closure_table: str, depth_column: str = "depth") -> str:
        """Get SQL for self and ancestors lookup."""
        depth_condition = ""
        if self.max_depth is not None:
            depth_condition = f" AND {depth_column} <= {self.max_depth}"

        return f"""
            SELECT parent_id FROM {closure_table}
            WHERE child_id = {self._format_value(self.member_value)}
            {depth_condition}
        """

    def get_descendants(self, closure_table: str, depth_column: str = "depth") -> str:
        """Not applicable for ancestors operator."""
        raise NotImplementedError("Use get_ancestors() for SelfAndAncestorsOfOperator")

    def _format_value(self, value: Any) -> str:
        """Format value for SQL."""
        if value is None:
            return "NULL"
        elif isinstance(value, str):
            escaped = value.replace("'", "''")
            return f"'{escaped}'"
        else:
            return str(value)


class SiblingsOfOperator(HierarchyOperator):
    """Operator to get siblings of a hierarchy member.

    Returns members with the same parent as the specified member.
    Optionally includes the member itself.
    """

    # Include the member in results
    include_self: bool = Field(default=False, description="Include self in results")

    def get_member_condition(self, column: str) -> str:
        """Get condition for siblings."""
        return f"{column} IN (SELECT child_id FROM ... WHERE parent_id = (SELECT parent_id FROM ... WHERE child_id = {self._format_value(self.member_value)} AND depth = 1))"

    def get_siblings(self, closure_table: str, depth_column: str = "depth") -> str:
        """Get SQL for siblings lookup.

        Args:
            closure_table: Closure table name
            depth_column: Depth column name

        Returns:
            SQL subquery for siblings
        """
        exclude_self = ""
        if not self.include_self:
            exclude_self = f" AND child_id <> {self._format_value(self.member_value)}"

        return f"""
            SELECT child_id FROM {closure_table}
            WHERE parent_id = (
                SELECT parent_id FROM {closure_table}
                WHERE child_id = {self._format_value(self.member_value)}
                AND {depth_column} = 1
            )
            AND {depth_column} = 1
            {exclude_self}
        """

    def get_descendants(self, closure_table: str, depth_column: str = "depth") -> str:
        """Not applicable for siblings operator."""
        raise NotImplementedError("Use get_siblings() for SiblingsOfOperator")

    def _format_value(self, value: Any) -> str:
        """Format value for SQL."""
        if value is None:
            return "NULL"
        elif isinstance(value, str):
            escaped = value.replace("'", "''")
            return f"'{escaped}'"
        else:
            return str(value)


class LevelOperator(HierarchyOperator):
    """Operator to get all members at a specific level.

    Returns all members at a specified hierarchy level
    (e.g., all root nodes, all leaf nodes).
    """

    # Target level (0 = root, 1 = first level, etc.)
    level: int = Field(default=0, description="Target hierarchy level")

    def get_member_condition(self, column: str) -> str:
        """Get condition for level members."""
        return f"{column} IN (SELECT id FROM ... WHERE level = {self.level})"

    def get_level_members(self, hierarchy_table: str, level_column: str = "level") -> str:
        """Get SQL for level members lookup.

        Args:
            hierarchy_table: Hierarchy table name
            level_column: Level column name

        Returns:
            SQL subquery for level members
        """
        return f"""
            SELECT id FROM {hierarchy_table}
            WHERE {level_column} = {self.level}
        """

    def get_descendants(self, closure_table: str, depth_column: str = "depth") -> str:
        """Not applicable for level operator."""
        raise NotImplementedError("Use get_level_members() for LevelOperator")