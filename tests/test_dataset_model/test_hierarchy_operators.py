"""Unit tests for hierarchy operators, closure table defs, condition builder, and registry."""

import pytest

from foggy.dataset_model.engine.hierarchy import (
    HierarchyDirection,
    HierarchyOperator,
    ChildrenOfOperator,
    DescendantsOfOperator,
    SelfAndDescendantsOfOperator,
    AncestorsOfOperator,
    SelfAndAncestorsOfOperator,
    SiblingsOfOperator,
    LevelOperator,
    ClosureTableDef,
    ParentChildDimensionDef,
    HierarchyConditionBuilder,
    HierarchyOperatorRegistry,
    get_default_hierarchy_registry,
)
from foggy.dataset_model.impl.model import DimensionPropertyDef


# ======================================================================
# ClosureTableDef / ParentChildDimensionDef
# ======================================================================


class TestClosureTableDef:
    """Tests for ClosureTableDef model."""

    def test_create_closure_table_def(self):
        """Basic creation."""
        ct = ClosureTableDef(
            table_name="team_closure",
            parent_column="parent_id",
            child_column="company_id",
        )
        assert ct.table_name == "team_closure"
        assert ct.parent_column == "parent_id"
        assert ct.child_column == "company_id"
        assert ct.distance_column == "distance"
        assert ct.schema_name is None

    def test_closure_table_with_schema(self):
        """Creation with schema_name."""
        ct = ClosureTableDef(
            table_name="team_closure",
            parent_column="parent_id",
            child_column="company_id",
            schema_name="hr",
        )
        assert ct.qualified_table() == "hr.team_closure"

    def test_closure_table_no_schema(self):
        """qualified_table without schema."""
        ct = ClosureTableDef(
            table_name="org_closure",
            parent_column="ancestor_id",
            child_column="descendant_id",
        )
        assert ct.qualified_table() == "org_closure"

    def test_closure_custom_distance(self):
        """Custom distance column."""
        ct = ClosureTableDef(
            table_name="org_closure",
            parent_column="ancestor_id",
            child_column="descendant_id",
            distance_column="depth",
        )
        assert ct.distance_column == "depth"


class TestParentChildDimensionDef:
    """Tests for ParentChildDimensionDef model."""

    def test_create_parent_child_dimension_def(self):
        """Basic creation with closure."""
        closure = ClosureTableDef(
            table_name="team_closure",
            parent_column="parent_id",
            child_column="child_id",
        )
        pc = ParentChildDimensionDef(
            name="team",
            table_name="dim_team",
            foreign_key="team_key",
            primary_key="team_id",
            closure=closure,
        )
        assert pc.name == "team"
        assert pc.table_name == "dim_team"
        assert pc.closure.table_name == "team_closure"
        assert pc.properties == []
        assert pc.caption_column is None

    def test_parent_child_with_properties(self):
        """Creation with properties."""
        closure = ClosureTableDef(
            table_name="org_closure",
            parent_column="parent_id",
            child_column="child_id",
        )
        pc = ParentChildDimensionDef(
            name="org",
            table_name="dim_org",
            foreign_key="org_key",
            primary_key="org_id",
            caption_column="org_name",
            caption="Organization",
            closure=closure,
            properties=[
                DimensionPropertyDef(column="org_type", caption="Type"),
                DimensionPropertyDef(column="region", caption="Region"),
            ],
        )
        assert len(pc.properties) == 2
        assert pc.caption == "Organization"
        assert pc.caption_column == "org_name"


# ======================================================================
# Operator distance conditions
# ======================================================================


class TestChildrenOfOperator:
    """Tests for ChildrenOfOperator."""

    def test_children_of_distance(self):
        """Default distance condition is '= 1'."""
        op = ChildrenOfOperator(dimension="org", member_value="dept_001")
        cond = op.build_distance_condition("depth")
        assert cond == "depth = 1"

    def test_children_of_with_max_depth(self):
        """Max depth > 1 yields BETWEEN."""
        op = ChildrenOfOperator(dimension="org", member_value="dept_001", max_depth=3)
        cond = op.build_distance_condition("depth")
        assert cond == "depth BETWEEN 1 AND 3"

    def test_children_of_max_depth_override(self):
        """Explicit max_depth param overrides instance attribute."""
        op = ChildrenOfOperator(dimension="org", member_value="dept_001")
        cond = op.build_distance_condition("dist", max_depth=5)
        assert cond == "dist BETWEEN 1 AND 5"

    def test_children_of_names(self):
        """Canonical and alias names."""
        op = ChildrenOfOperator(dimension="x", member_value=1)
        assert "childrenOf" in op.names
        assert "children_of" in op.names

    def test_children_of_not_ancestor_direction(self):
        """Children is a downward operator."""
        op = ChildrenOfOperator(dimension="x", member_value=1)
        assert op.is_ancestor_direction is False

    def test_children_get_descendants_sql(self):
        """Legacy get_descendants returns depth = 1."""
        op = ChildrenOfOperator(dimension="org", member_value="dept_001")
        sql = op.get_descendants("org_closure")
        assert "depth = 1" in sql
        assert "dept_001" in sql


class TestDescendantsOfOperator:
    """Tests for DescendantsOfOperator."""

    def test_descendants_of_distance(self):
        """Default distance condition is '> 0'."""
        op = DescendantsOfOperator(dimension="org", member_value="dept_001")
        cond = op.build_distance_condition("depth")
        assert cond == "depth > 0"

    def test_descendants_of_with_max_depth(self):
        """Max depth yields BETWEEN 1 AND N."""
        op = DescendantsOfOperator(dimension="org", member_value="dept_001", max_depth=5)
        cond = op.build_distance_condition("depth")
        assert cond == "depth BETWEEN 1 AND 5"

    def test_descendants_of_names(self):
        """Canonical and alias names."""
        op = DescendantsOfOperator(dimension="x", member_value=1)
        assert "descendantsOf" in op.names
        assert "descendants_of" in op.names

    def test_descendants_not_ancestor_direction(self):
        """Descendants is a downward operator."""
        op = DescendantsOfOperator(dimension="x", member_value=1)
        assert op.is_ancestor_direction is False

    def test_descendants_get_descendants_sql(self):
        """Legacy get_descendants SQL."""
        op = DescendantsOfOperator(dimension="org", member_value="dept_001")
        sql = op.get_descendants("org_closure")
        assert "depth > 0" in sql

    def test_descendants_with_max_depth_sql(self):
        """Legacy get_descendants with max_depth."""
        op = DescendantsOfOperator(dimension="org", member_value="dept_001", max_depth=3)
        sql = op.get_descendants("org_closure")
        assert "depth <= 3" in sql


class TestSelfAndDescendantsOfOperator:
    """Tests for SelfAndDescendantsOfOperator."""

    def test_self_and_descendants_distance(self):
        """Default distance condition is '>= 0'."""
        op = SelfAndDescendantsOfOperator(dimension="org", member_value="dept_001")
        cond = op.build_distance_condition("depth")
        assert cond == "depth >= 0"

    def test_self_and_descendants_with_max_depth(self):
        """Max depth yields BETWEEN 0 AND N."""
        op = SelfAndDescendantsOfOperator(
            dimension="org", member_value="dept_001", max_depth=4
        )
        cond = op.build_distance_condition("depth")
        assert cond == "depth BETWEEN 0 AND 4"

    def test_self_and_descendants_names(self):
        """Canonical and alias names."""
        op = SelfAndDescendantsOfOperator(dimension="x", member_value=1)
        assert "selfAndDescendantsOf" in op.names

    def test_self_and_descendants_not_ancestor_direction(self):
        """SelfAndDescendants is a downward operator."""
        op = SelfAndDescendantsOfOperator(dimension="x", member_value=1)
        assert op.is_ancestor_direction is False


class TestAncestorsOfOperator:
    """Tests for AncestorsOfOperator."""

    def test_ancestors_direction(self):
        """Ancestors is an upward operator."""
        op = AncestorsOfOperator(dimension="org", member_value="dept_005")
        assert op.is_ancestor_direction is True

    def test_ancestors_distance(self):
        """Default distance condition is '> 0'."""
        op = AncestorsOfOperator(dimension="org", member_value="dept_005")
        cond = op.build_distance_condition("depth")
        assert cond == "depth > 0"

    def test_ancestors_with_max_depth(self):
        """Max depth yields BETWEEN 1 AND N."""
        op = AncestorsOfOperator(dimension="org", member_value="dept_005", max_depth=3)
        cond = op.build_distance_condition("depth")
        assert cond == "depth BETWEEN 1 AND 3"

    def test_ancestors_names(self):
        """Canonical and alias names."""
        op = AncestorsOfOperator(dimension="x", member_value=1)
        assert "ancestorsOf" in op.names
        assert "ancestors_of" in op.names

    def test_ancestors_get_ancestors_sql(self):
        """Legacy get_ancestors SQL."""
        op = AncestorsOfOperator(dimension="org", member_value="dept_005")
        sql = op.get_ancestors("org_closure")
        assert "child_id = 'dept_005'" in sql
        assert "depth > 0" in sql

    def test_ancestors_get_descendants_raises(self):
        """get_descendants raises NotImplementedError."""
        op = AncestorsOfOperator(dimension="org", member_value="dept_005")
        with pytest.raises(NotImplementedError):
            op.get_descendants("org_closure")


class TestSelfAndAncestorsOfOperator:
    """Tests for SelfAndAncestorsOfOperator."""

    def test_self_and_ancestors_distance(self):
        """Default distance condition is '>= 0'."""
        op = SelfAndAncestorsOfOperator(dimension="org", member_value="dept_005")
        cond = op.build_distance_condition("depth")
        assert cond == "depth >= 0"

    def test_self_and_ancestors_direction(self):
        """SelfAndAncestors is an upward operator."""
        op = SelfAndAncestorsOfOperator(dimension="org", member_value="dept_005")
        assert op.is_ancestor_direction is True

    def test_self_and_ancestors_with_max_depth(self):
        """Max depth yields BETWEEN 0 AND N."""
        op = SelfAndAncestorsOfOperator(
            dimension="org", member_value="dept_005", max_depth=2
        )
        cond = op.build_distance_condition("depth")
        assert cond == "depth BETWEEN 0 AND 2"

    def test_self_and_ancestors_names(self):
        """Canonical and alias names."""
        op = SelfAndAncestorsOfOperator(dimension="x", member_value=1)
        assert "selfAndAncestorsOf" in op.names
        assert "self_and_ancestors_of" in op.names


# ======================================================================
# HierarchyConditionBuilder
# ======================================================================


class TestHierarchyConditionBuilder:
    """Tests for HierarchyConditionBuilder."""

    def _make_closure(self) -> ClosureTableDef:
        return ClosureTableDef(
            table_name="team_closure",
            parent_column="parent_id",
            child_column="child_id",
            distance_column="distance",
        )

    def test_descendant_condition_builder(self):
        """Builds correct JOIN + WHERE for descendants."""
        closure = self._make_closure()
        result = HierarchyConditionBuilder.build_descendants_condition(
            closure=closure,
            closure_alias="cl",
            fact_fk_column="team_key",
            fact_alias="t",
            value=42,
            include_self=False,
        )
        assert result["join_table"] == "team_closure"
        assert result["join_alias"] == "cl"
        assert "t.team_key = cl.child_id" in result["join_condition"]
        assert "cl.parent_id = ?" in result["where_condition"]
        assert result["where_params"] == [42]
        assert "cl.distance > 0" in result["distance_condition"]

    def test_descendant_with_self(self):
        """include_self=True yields distance >= 0."""
        closure = self._make_closure()
        result = HierarchyConditionBuilder.build_descendants_condition(
            closure=closure,
            closure_alias="cl",
            fact_fk_column="team_key",
            fact_alias="t",
            value=42,
            include_self=True,
        )
        assert ">= 0" in result["distance_condition"]

    def test_descendant_without_self(self):
        """include_self=False yields distance > 0."""
        closure = self._make_closure()
        result = HierarchyConditionBuilder.build_descendants_condition(
            closure=closure,
            closure_alias="cl",
            fact_fk_column="team_key",
            fact_alias="t",
            value=42,
            include_self=False,
        )
        assert "> 0" in result["distance_condition"]

    def test_max_depth_condition_descendants(self):
        """max_depth=2 with include_self yields BETWEEN 0 AND 2."""
        closure = self._make_closure()
        result = HierarchyConditionBuilder.build_descendants_condition(
            closure=closure,
            closure_alias="cl",
            fact_fk_column="team_key",
            fact_alias="t",
            value=42,
            include_self=True,
            max_depth=2,
        )
        assert "BETWEEN 0 AND 2" in result["distance_condition"]

    def test_max_depth_no_self_descendants(self):
        """max_depth=3 without include_self yields BETWEEN 1 AND 3."""
        closure = self._make_closure()
        result = HierarchyConditionBuilder.build_descendants_condition(
            closure=closure,
            closure_alias="cl",
            fact_fk_column="team_key",
            fact_alias="t",
            value=42,
            include_self=False,
            max_depth=3,
        )
        assert "BETWEEN 1 AND 3" in result["distance_condition"]

    def test_ancestor_condition_builder(self):
        """Builds correct JOIN + WHERE for ancestors with REVERSED join."""
        closure = self._make_closure()
        result = HierarchyConditionBuilder.build_ancestors_condition(
            closure=closure,
            closure_alias="cl",
            fact_fk_column="team_key",
            fact_alias="t",
            value=99,
            include_self=False,
        )
        # REVERSED: fact FK joins to parent_column
        assert "t.team_key = cl.parent_id" in result["join_condition"]
        # WHERE on child_column
        assert "cl.child_id = ?" in result["where_condition"]
        assert result["where_params"] == [99]
        assert "> 0" in result["distance_condition"]

    def test_ancestor_with_self(self):
        """Ancestor include_self=True yields distance >= 0."""
        closure = self._make_closure()
        result = HierarchyConditionBuilder.build_ancestors_condition(
            closure=closure,
            closure_alias="cl",
            fact_fk_column="team_key",
            fact_alias="t",
            value=99,
            include_self=True,
        )
        assert ">= 0" in result["distance_condition"]

    def test_ancestor_max_depth(self):
        """Ancestor with max_depth yields BETWEEN."""
        closure = self._make_closure()
        result = HierarchyConditionBuilder.build_ancestors_condition(
            closure=closure,
            closure_alias="cl",
            fact_fk_column="team_key",
            fact_alias="t",
            value=99,
            include_self=False,
            max_depth=2,
        )
        assert "BETWEEN 1 AND 2" in result["distance_condition"]

    def test_closure_with_schema(self):
        """Closure with schema produces qualified table name."""
        closure = ClosureTableDef(
            table_name="team_closure",
            parent_column="parent_id",
            child_column="child_id",
            schema_name="hr",
        )
        result = HierarchyConditionBuilder.build_descendants_condition(
            closure=closure,
            closure_alias="cl",
            fact_fk_column="team_key",
            fact_alias="t",
            value=1,
        )
        assert result["join_table"] == "hr.team_closure"


# ======================================================================
# HierarchyOperatorRegistry
# ======================================================================


class TestHierarchyOperatorRegistry:
    """Tests for HierarchyOperatorRegistry."""

    def test_hierarchy_registry(self):
        """Lookup by canonical name."""
        reg = get_default_hierarchy_registry()
        cls = reg.get("childrenOf")
        assert cls is ChildrenOfOperator

    def test_hierarchy_registry_alias(self):
        """Lookup by alias name (snake_case)."""
        reg = get_default_hierarchy_registry()
        cls = reg.get("children_of")
        assert cls is ChildrenOfOperator

    def test_registry_case_insensitive(self):
        """Lookup is case-insensitive."""
        reg = get_default_hierarchy_registry()
        cls = reg.get("CHILDRENOF")
        assert cls is ChildrenOfOperator

    def test_registry_descendants(self):
        """Lookup descendants operator."""
        reg = get_default_hierarchy_registry()
        assert reg.get("descendantsOf") is DescendantsOfOperator
        assert reg.get("descendants_of") is DescendantsOfOperator

    def test_registry_ancestors(self):
        """Lookup ancestors operator."""
        reg = get_default_hierarchy_registry()
        assert reg.get("ancestorsOf") is AncestorsOfOperator
        assert reg.get("ancestors_of") is AncestorsOfOperator

    def test_registry_self_and_descendants(self):
        """Lookup self-and-descendants operator."""
        reg = get_default_hierarchy_registry()
        assert reg.get("selfAndDescendantsOf") is SelfAndDescendantsOfOperator

    def test_registry_self_and_ancestors(self):
        """Lookup self-and-ancestors operator."""
        reg = get_default_hierarchy_registry()
        assert reg.get("selfAndAncestorsOf") is SelfAndAncestorsOfOperator

    def test_registry_unknown(self):
        """Unknown name returns None."""
        reg = get_default_hierarchy_registry()
        assert reg.get("nonexistent") is None

    def test_registry_all_names(self):
        """all_names returns a non-empty set."""
        reg = get_default_hierarchy_registry()
        names = reg.all_names()
        assert len(names) >= 10  # At least 2 per 5 main operators
        assert "childrenof" in names  # lowercase

    def test_custom_registry(self):
        """Register and lookup a single operator."""
        reg = HierarchyOperatorRegistry()
        reg.register(ChildrenOfOperator)
        assert reg.get("childrenOf") is ChildrenOfOperator
        assert reg.get("descendants_of") is None


# ======================================================================
# Direction enum
# ======================================================================


class TestHierarchyDirection:
    """Tests for HierarchyDirection enum."""

    def test_direction_values(self):
        """Enum values."""
        assert HierarchyDirection.UP.value == "up"
        assert HierarchyDirection.DOWN.value == "down"


# ======================================================================
# Legacy compatibility (tests that mirror test_definitions.py)
# ======================================================================


class TestLegacyCompatibility:
    """Ensure backward compatibility with existing test_definitions.py tests."""

    def test_children_of_operator(self):
        """Matches TestHierarchyOperators.test_children_of_operator."""
        op = ChildrenOfOperator(dimension="org", member_value="dept_001")
        sql = op.get_descendants("org_closure")
        assert "depth = 1" in sql
        assert "dept_001" in sql

    def test_descendants_of_operator(self):
        """Matches TestHierarchyOperators.test_descendants_of_operator."""
        op = DescendantsOfOperator(dimension="org", member_value="dept_001")
        sql = op.get_descendants("org_closure")
        assert "depth > 0" in sql

    def test_descendants_with_max_depth(self):
        """Matches TestHierarchyOperators.test_descendants_with_max_depth."""
        op = DescendantsOfOperator(
            dimension="org", member_value="dept_001", max_depth=3
        )
        sql = op.get_descendants("org_closure")
        assert "depth <= 3" in sql

    def test_self_and_descendants(self):
        """Matches TestHierarchyOperators.test_self_and_descendants."""
        op = SelfAndDescendantsOfOperator(dimension="org", member_value="dept_001")
        sql = op.get_descendants("org_closure")
        assert "parent_id = 'dept_001'" in sql

    def test_ancestors_of_operator(self):
        """Matches TestHierarchyOperators.test_ancestors_of_operator."""
        op = AncestorsOfOperator(dimension="org", member_value="dept_005")
        sql = op.get_ancestors("org_closure")
        assert "child_id = 'dept_005'" in sql
        assert "depth > 0" in sql

    def test_siblings_of_operator(self):
        """Matches TestHierarchyOperators.test_siblings_of_operator."""
        op = SiblingsOfOperator(
            dimension="org", member_value="dept_002", include_self=False
        )
        sql = op.get_siblings("org_closure")
        assert "depth = 1" in sql
        assert "dept_002" in sql
