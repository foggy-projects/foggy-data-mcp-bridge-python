"""Hierarchy operators for closure table support.

This module implements hierarchy traversal operators commonly used
with closure tables for hierarchical dimension queries.

Includes:
- HierarchyOperator base class and concrete operators
- ClosureTableDef / ParentChildDimensionDef models
- HierarchyConditionBuilder for SQL generation
- HierarchyOperatorRegistry for name-based lookup
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

from foggy.dataset_model.impl.model import DimensionPropertyDef


# ======================================================================
# Enums
# ======================================================================


class HierarchyDirection(str, Enum):
    """Hierarchy traversal direction."""

    UP = "up"  # Towards root
    DOWN = "down"  # Towards leaves


# ======================================================================
# Closure / Parent-Child definitions (Pydantic models)
# ======================================================================


class ClosureTableDef(BaseModel):
    """Closure table definition for parent-child hierarchies.

    A closure table stores every ancestor-descendant pair together with the
    distance between them, enabling efficient subtree queries.
    """

    table_name: str = Field(..., description="Closure table name, e.g. 'team_closure'")
    parent_column: str = Field(..., description="Ancestor column, e.g. 'parent_id'")
    child_column: str = Field(..., description="Descendant column, e.g. 'company_id'")
    distance_column: str = Field(default="distance", description="Distance/depth column")
    schema_name: Optional[str] = Field(default=None, description="Schema qualifier")

    model_config = {"extra": "allow"}

    def qualified_table(self) -> str:
        """Return optionally schema-qualified table name."""
        if self.schema_name:
            return f"{self.schema_name}.{self.table_name}"
        return self.table_name


class ParentChildDimensionDef(BaseModel):
    """Parent-child dimension definition -- extends DimensionJoinDef with closure table.

    Used for self-referential hierarchies such as organisation charts,
    category trees, or geographic hierarchies.
    """

    name: str = Field(..., description="Dimension name")
    table_name: str = Field(..., description="Dimension table name")
    foreign_key: str = Field(..., description="FK column on fact table")
    primary_key: str = Field(..., description="PK column on dimension table")
    caption_column: Optional[str] = Field(default=None, description="Display column")
    caption: Optional[str] = Field(default=None, description="Dimension display name")
    closure: ClosureTableDef = Field(..., description="Closure table configuration")
    properties: List[DimensionPropertyDef] = Field(default_factory=list, description="Dimension properties")

    model_config = {"extra": "allow"}


# ======================================================================
# HierarchyOperator base + concrete operators
# ======================================================================


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
        """Get the SQL condition for selecting members."""
        pass

    @abstractmethod
    def get_descendants(self, closure_table: str, depth_column: str = "depth") -> str:
        """Get SQL for descendant lookup in closure table."""
        pass

    # ------------------------------------------------------------------
    # New interface for registry-based operators
    # ------------------------------------------------------------------

    @property
    def names(self) -> List[str]:
        """Canonical and alias names for this operator type."""
        return []

    @property
    def is_ancestor_direction(self) -> bool:
        """True for operators that walk UP the hierarchy."""
        return False

    def build_distance_condition(
        self, distance_column: str, max_depth: Optional[int] = None
    ) -> str:
        """Build the distance SQL fragment for this operator."""
        return ""

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _format_value(self, value: Any) -> str:
        """Format value for SQL."""
        if value is None:
            return "NULL"
        elif isinstance(value, str):
            escaped = value.replace("'", "''")
            return f"'{escaped}'"
        else:
            return str(value)


# ------------------------------------------------------------------
# ChildrenOfOperator
# ------------------------------------------------------------------


class ChildrenOfOperator(HierarchyOperator):
    """Operator to get direct children of a hierarchy member.

    Returns only the immediate children (depth = 1) of the
    specified member in the hierarchy.
    """

    max_depth: Optional[int] = Field(default=None, description="Maximum depth (default 1)")

    @property
    def names(self) -> List[str]:
        return ["childrenOf", "children_of"]

    @property
    def is_ancestor_direction(self) -> bool:
        return False

    def build_distance_condition(
        self, distance_column: str, max_depth: Optional[int] = None
    ) -> str:
        effective_max = max_depth if max_depth is not None else self.max_depth
        if effective_max is not None and effective_max > 1:
            return f"{distance_column} BETWEEN 1 AND {effective_max}"
        return f"{distance_column} = 1"

    def get_member_condition(self, column: str) -> str:
        return f"{column} = {self._format_value(self.member_value)}"

    def get_descendants(self, closure_table: str, depth_column: str = "depth") -> str:
        return f"""
            SELECT child_id FROM {closure_table}
            WHERE parent_id = {self._format_value(self.member_value)}
            AND {depth_column} = 1
        """


# ------------------------------------------------------------------
# DescendantsOfOperator
# ------------------------------------------------------------------


class DescendantsOfOperator(HierarchyOperator):
    """Operator to get all descendants of a hierarchy member.

    Returns all descendants (children, grandchildren, etc.)
    of the specified member, but NOT the member itself.
    """

    max_depth: Optional[int] = Field(default=None, description="Maximum depth to traverse")

    @property
    def names(self) -> List[str]:
        return ["descendantsOf", "descendants_of"]

    @property
    def is_ancestor_direction(self) -> bool:
        return False

    def build_distance_condition(
        self, distance_column: str, max_depth: Optional[int] = None
    ) -> str:
        effective_max = max_depth if max_depth is not None else self.max_depth
        if effective_max is not None:
            return f"{distance_column} BETWEEN 1 AND {effective_max}"
        return f"{distance_column} > 0"

    def get_member_condition(self, column: str) -> str:
        return (
            f"{column} IN (SELECT child_id FROM ... "
            f"WHERE parent_id = {self._format_value(self.member_value)} AND depth > 0)"
        )

    def get_descendants(self, closure_table: str, depth_column: str = "depth") -> str:
        depth_condition = ""
        if self.max_depth is not None:
            depth_condition = f" AND {depth_column} <= {self.max_depth}"

        return f"""
            SELECT child_id FROM {closure_table}
            WHERE parent_id = {self._format_value(self.member_value)}
            AND {depth_column} > 0
            {depth_condition}
        """


# ------------------------------------------------------------------
# SelfAndDescendantsOfOperator
# ------------------------------------------------------------------


class SelfAndDescendantsOfOperator(HierarchyOperator):
    """Operator to get a member and all its descendants.

    Returns the member itself plus all descendants
    (children, grandchildren, etc.).
    """

    max_depth: Optional[int] = Field(default=None, description="Maximum depth to traverse")

    @property
    def names(self) -> List[str]:
        return ["selfAndDescendantsOf", "self_and_descendants_of"]

    @property
    def is_ancestor_direction(self) -> bool:
        return False

    def build_distance_condition(
        self, distance_column: str, max_depth: Optional[int] = None
    ) -> str:
        effective_max = max_depth if max_depth is not None else self.max_depth
        if effective_max is not None:
            return f"{distance_column} BETWEEN 0 AND {effective_max}"
        return f"{distance_column} >= 0"

    def get_member_condition(self, column: str) -> str:
        return (
            f"{column} IN (SELECT child_id FROM ... "
            f"WHERE parent_id = {self._format_value(self.member_value)})"
        )

    def get_descendants(self, closure_table: str, depth_column: str = "depth") -> str:
        depth_condition = ""
        if self.max_depth is not None:
            depth_condition = f" AND {depth_column} <= {self.max_depth}"

        return f"""
            SELECT child_id FROM {closure_table}
            WHERE parent_id = {self._format_value(self.member_value)}
            {depth_condition}
        """


# ------------------------------------------------------------------
# AncestorsOfOperator
# ------------------------------------------------------------------


class AncestorsOfOperator(HierarchyOperator):
    """Operator to get all ancestors of a hierarchy member.

    Returns all ancestors (parent, grandparent, etc.)
    of the specified member, but NOT the member itself.
    """

    max_depth: Optional[int] = Field(default=None, description="Maximum depth to traverse")

    @property
    def names(self) -> List[str]:
        return ["ancestorsOf", "ancestors_of"]

    @property
    def is_ancestor_direction(self) -> bool:
        return True

    def build_distance_condition(
        self, distance_column: str, max_depth: Optional[int] = None
    ) -> str:
        effective_max = max_depth if max_depth is not None else self.max_depth
        if effective_max is not None:
            return f"{distance_column} BETWEEN 1 AND {effective_max}"
        return f"{distance_column} > 0"

    def get_member_condition(self, column: str) -> str:
        return (
            f"{column} IN (SELECT parent_id FROM ... "
            f"WHERE child_id = {self._format_value(self.member_value)} AND depth > 0)"
        )

    def get_ancestors(self, closure_table: str, depth_column: str = "depth") -> str:
        """Get SQL for ancestors lookup."""
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


# ------------------------------------------------------------------
# SelfAndAncestorsOfOperator
# ------------------------------------------------------------------


class SelfAndAncestorsOfOperator(HierarchyOperator):
    """Operator to get a member and all its ancestors.

    Returns the member itself plus all ancestors
    (parent, grandparent, etc.) up to the root.
    """

    max_depth: Optional[int] = Field(default=None, description="Maximum depth to traverse")

    @property
    def names(self) -> List[str]:
        return ["selfAndAncestorsOf", "self_and_ancestors_of"]

    @property
    def is_ancestor_direction(self) -> bool:
        return True

    def build_distance_condition(
        self, distance_column: str, max_depth: Optional[int] = None
    ) -> str:
        effective_max = max_depth if max_depth is not None else self.max_depth
        if effective_max is not None:
            return f"{distance_column} BETWEEN 0 AND {effective_max}"
        return f"{distance_column} >= 0"

    def get_member_condition(self, column: str) -> str:
        return (
            f"{column} IN (SELECT parent_id FROM ... "
            f"WHERE child_id = {self._format_value(self.member_value)})"
        )

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


# ------------------------------------------------------------------
# SiblingsOfOperator
# ------------------------------------------------------------------


class SiblingsOfOperator(HierarchyOperator):
    """Operator to get siblings of a hierarchy member.

    Returns members with the same parent as the specified member.
    Optionally includes the member itself.
    """

    include_self: bool = Field(default=False, description="Include self in results")

    @property
    def names(self) -> List[str]:
        return ["siblingsOf", "siblings_of"]

    def get_member_condition(self, column: str) -> str:
        return (
            f"{column} IN (SELECT child_id FROM ... WHERE parent_id = "
            f"(SELECT parent_id FROM ... WHERE child_id = "
            f"{self._format_value(self.member_value)} AND depth = 1))"
        )

    def get_siblings(self, closure_table: str, depth_column: str = "depth") -> str:
        """Get SQL for siblings lookup."""
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


# ------------------------------------------------------------------
# LevelOperator
# ------------------------------------------------------------------


class LevelOperator(HierarchyOperator):
    """Operator to get all members at a specific level.

    Returns all members at a specified hierarchy level
    (e.g., all root nodes, all leaf nodes).
    """

    level: int = Field(default=0, description="Target hierarchy level")

    @property
    def names(self) -> List[str]:
        return ["level", "atLevel"]

    def get_member_condition(self, column: str) -> str:
        return f"{column} IN (SELECT id FROM ... WHERE level = {self.level})"

    def get_level_members(self, hierarchy_table: str, level_column: str = "level") -> str:
        """Get SQL for level members lookup."""
        return f"""
            SELECT id FROM {hierarchy_table}
            WHERE {level_column} = {self.level}
        """

    def get_descendants(self, closure_table: str, depth_column: str = "depth") -> str:
        """Not applicable for level operator."""
        raise NotImplementedError("Use get_level_members() for LevelOperator")


# ======================================================================
# HierarchyConditionBuilder
# ======================================================================


class HierarchyConditionBuilder:
    """Builds SQL conditions for hierarchy operators using closure tables.

    Produces JOIN and WHERE fragments that can be plugged into a larger
    query builder.
    """

    @staticmethod
    def build_descendants_condition(
        closure: ClosureTableDef,
        closure_alias: str,
        fact_fk_column: str,
        fact_alias: str,
        value: Any,
        include_self: bool = True,
        max_depth: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Build JOIN + WHERE for descendant queries.

        The closure table is joined so that the fact table's FK matches the
        closure child column.  The WHERE restricts to a specific parent.

        Args:
            closure: Closure table definition.
            closure_alias: SQL alias for the closure table.
            fact_fk_column: Foreign-key column on the fact table.
            fact_alias: SQL alias for the fact table.
            value: The parent member value.
            include_self: Whether to include the member itself (distance >= 0).
            max_depth: Optional maximum depth.

        Returns:
            Dict with keys: join_table, join_alias, join_condition,
            where_condition, where_params, distance_condition.
        """
        join_condition = (
            f"{fact_alias}.{fact_fk_column} = {closure_alias}.{closure.child_column}"
        )

        where_condition = f"{closure_alias}.{closure.parent_column} = ?"
        where_params: List[Any] = [value]

        # Distance condition
        dc = closure.distance_column
        if max_depth is not None:
            lower = 0 if include_self else 1
            distance_condition = f"{closure_alias}.{dc} BETWEEN {lower} AND {max_depth}"
        else:
            if include_self:
                distance_condition = f"{closure_alias}.{dc} >= 0"
            else:
                distance_condition = f"{closure_alias}.{dc} > 0"

        return {
            "join_table": closure.qualified_table(),
            "join_alias": closure_alias,
            "join_condition": join_condition,
            "where_condition": where_condition,
            "where_params": where_params,
            "distance_condition": distance_condition,
        }

    @staticmethod
    def build_ancestors_condition(
        closure: ClosureTableDef,
        closure_alias: str,
        fact_fk_column: str,
        fact_alias: str,
        value: Any,
        include_self: bool = True,
        max_depth: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Build JOIN + WHERE for ancestor queries (REVERSE direction).

        The closure table is joined so that the fact table's FK matches the
        closure **parent** column (reversed compared to descendants).

        Args:
            closure: Closure table definition.
            closure_alias: SQL alias for the closure table.
            fact_fk_column: Foreign-key column on the fact table.
            fact_alias: SQL alias for the fact table.
            value: The child member value.
            include_self: Whether to include the member itself (distance >= 0).
            max_depth: Optional maximum depth.

        Returns:
            Dict with keys: join_table, join_alias, join_condition,
            where_condition, where_params, distance_condition.
        """
        # REVERSED: fact FK joins to parent_column
        join_condition = (
            f"{fact_alias}.{fact_fk_column} = {closure_alias}.{closure.parent_column}"
        )

        # WHERE on child_column
        where_condition = f"{closure_alias}.{closure.child_column} = ?"
        where_params: List[Any] = [value]

        # Distance condition
        dc = closure.distance_column
        if max_depth is not None:
            lower = 0 if include_self else 1
            distance_condition = f"{closure_alias}.{dc} BETWEEN {lower} AND {max_depth}"
        else:
            if include_self:
                distance_condition = f"{closure_alias}.{dc} >= 0"
            else:
                distance_condition = f"{closure_alias}.{dc} > 0"

        return {
            "join_table": closure.qualified_table(),
            "join_alias": closure_alias,
            "join_condition": join_condition,
            "where_condition": where_condition,
            "where_params": where_params,
            "distance_condition": distance_condition,
        }


# ======================================================================
# HierarchyOperatorRegistry
# ======================================================================


class HierarchyOperatorRegistry:
    """Registry mapping operator names to HierarchyOperator *classes*.

    Stores operator classes (not instances) so callers can look up the
    right class by canonical or alias name.
    """

    def __init__(self) -> None:
        self._operators: Dict[str, type] = {}

    def register(self, op_class: type) -> None:
        """Register an operator class under all its names.

        The class must define a ``names`` property that returns a list of
        name strings.  We instantiate a dummy to read the names, then
        store the class.
        """
        # We need to read the names property.  Since HierarchyOperator
        # requires dimension + member_value, create a minimal instance.
        dummy = op_class.model_construct(dimension="__reg__", member_value=0)
        for name in dummy.names:
            self._operators[name.lower()] = op_class

    def get(self, name: str) -> Optional[type]:
        """Look up an operator class by name (case-insensitive)."""
        return self._operators.get(name.lower())

    def all_names(self) -> Set[str]:
        """Return all registered operator names."""
        return set(self._operators.keys())


def get_default_hierarchy_registry() -> HierarchyOperatorRegistry:
    """Return a registry pre-populated with all built-in operators."""
    registry = HierarchyOperatorRegistry()
    registry.register(ChildrenOfOperator)
    registry.register(DescendantsOfOperator)
    registry.register(SelfAndDescendantsOfOperator)
    registry.register(AncestorsOfOperator)
    registry.register(SelfAndAncestorsOfOperator)
    registry.register(SiblingsOfOperator)
    registry.register(LevelOperator)
    return registry
