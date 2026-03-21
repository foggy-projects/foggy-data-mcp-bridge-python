"""Tests for JoinGraph (engine/join/).

20+ tests aligned with Java JoinGraphTest covering edge creation,
BFS path finding, caching, cycle detection, and topological ordering.
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.join import JoinEdge, JoinGraph, JoinType


# ===================================================================
# TestJoinEdge
# ===================================================================

class TestJoinEdge:
    def test_edge_key(self):
        edge = JoinEdge(
            from_table="t",
            to_table="dp",
            to_table_name="dim_product",
            foreign_key="product_id",
            primary_key="id",
        )
        assert edge.edge_key == "t->dp"

    def test_default_join_type_is_left(self):
        edge = JoinEdge(
            from_table="t",
            to_table="dp",
            to_table_name="dim_product",
            foreign_key="product_id",
            primary_key="id",
        )
        assert edge.join_type == JoinType.LEFT

    def test_inner_join_type(self):
        edge = JoinEdge(
            from_table="t",
            to_table="dp",
            to_table_name="dim_product",
            foreign_key="product_id",
            primary_key="id",
            join_type=JoinType.INNER,
        )
        assert edge.join_type == JoinType.INNER

    def test_custom_on_condition(self):
        edge = JoinEdge(
            from_table="t",
            to_table="dp",
            to_table_name="dim_product",
            foreign_key="product_id",
            primary_key="id",
            on_condition="t.product_id = dp.id AND dp.active = 1",
        )
        assert edge.on_condition == "t.product_id = dp.id AND dp.active = 1"

    def test_edge_is_frozen(self):
        edge = JoinEdge(
            from_table="t",
            to_table="dp",
            to_table_name="dim_product",
            foreign_key="product_id",
            primary_key="id",
        )
        with pytest.raises(AttributeError):
            edge.from_table = "other"  # type: ignore[misc]

    def test_join_type_values(self):
        assert JoinType.LEFT.value == "LEFT JOIN"
        assert JoinType.INNER.value == "INNER JOIN"
        assert JoinType.RIGHT.value == "RIGHT JOIN"
        assert JoinType.FULL.value == "FULL JOIN"


# ===================================================================
# TestJoinGraph
# ===================================================================

class TestJoinGraph:

    # -- basic structure ---------------------------------------------------

    def test_empty_graph(self):
        g = JoinGraph("t")
        assert g.root == "t"
        assert g.node_count == 1
        assert g.edge_count == 0

    def test_single_edge(self):
        g = JoinGraph("t")
        g.add_edge("t", "dp", "dim_product", "product_id", "id")
        assert g.node_count == 2
        assert g.edge_count == 1

    def test_multiple_edges(self):
        g = JoinGraph("t")
        g.add_edge("t", "dp", "dim_product", "product_id", "id")
        g.add_edge("t", "dc", "dim_customer", "customer_id", "id")
        g.add_edge("dp", "cat", "dim_category", "category_id", "id")
        assert g.node_count == 4
        assert g.edge_count == 3

    def test_duplicate_edge_ignored(self):
        g = JoinGraph("t")
        g.add_edge("t", "dp", "dim_product", "product_id", "id")
        g.add_edge("t", "dp", "dim_product", "product_id", "id")
        assert g.edge_count == 1

    def test_add_edge_is_chainable(self):
        g = (
            JoinGraph("t")
            .add_edge("t", "dp", "dim_product", "product_id", "id")
            .add_edge("t", "dc", "dim_customer", "customer_id", "id")
        )
        assert g.edge_count == 2

    # -- path finding ------------------------------------------------------

    def test_find_direct_path(self):
        g = JoinGraph("t")
        g.add_edge("t", "dp", "dim_product", "product_id", "id")
        g.add_edge("t", "dc", "dim_customer", "customer_id", "id")

        path = g.get_path({"dp"})
        assert len(path) == 1
        assert path[0].to_table == "dp"
        assert path[0].from_table == "t"

    def test_find_nested_path(self):
        g = JoinGraph("t")
        g.add_edge("t", "dp", "dim_product", "product_id", "id")
        g.add_edge("dp", "cat", "dim_category", "category_id", "id")

        path = g.get_path({"cat"})
        assert len(path) == 2
        tables = [(e.from_table, e.to_table) for e in path]
        assert ("t", "dp") in tables
        assert ("dp", "cat") in tables
        # Topological order: t->dp before dp->cat
        idx_dp = next(i for i, e in enumerate(path) if e.to_table == "dp")
        idx_cat = next(i for i, e in enumerate(path) if e.to_table == "cat")
        assert idx_dp < idx_cat

    def test_find_multi_target(self):
        g = JoinGraph("t")
        g.add_edge("t", "dp", "dim_product", "product_id", "id")
        g.add_edge("t", "dc", "dim_customer", "customer_id", "id")
        g.add_edge("dp", "cat", "dim_category", "category_id", "id")

        path = g.get_path({"dp", "cat", "dc"})
        assert len(path) == 3
        to_tables = {e.to_table for e in path}
        assert to_tables == {"dp", "dc", "cat"}

    def test_root_returns_empty(self):
        g = JoinGraph("t")
        g.add_edge("t", "dp", "dim_product", "product_id", "id")
        path = g.get_path({"t"})
        assert path == []

    def test_empty_targets_returns_empty(self):
        g = JoinGraph("t")
        g.add_edge("t", "dp", "dim_product", "product_id", "id")
        path = g.get_path(set())
        assert path == []

    def test_unreachable_raises(self):
        g = JoinGraph("t")
        g.add_edge("t", "dp", "dim_product", "product_id", "id")
        with pytest.raises(ValueError, match="Unreachable"):
            g.get_path({"unknown"})

    # -- caching -----------------------------------------------------------

    def test_path_cached(self):
        g = JoinGraph("t")
        g.add_edge("t", "dp", "dim_product", "product_id", "id")
        path1 = g.get_path({"dp"})
        path2 = g.get_path({"dp"})
        assert path1 is path2  # exact same object

    def test_cache_cleared_on_add(self):
        g = JoinGraph("t")
        g.add_edge("t", "dp", "dim_product", "product_id", "id")
        path1 = g.get_path({"dp"})
        g.add_edge("t", "dc", "dim_customer", "customer_id", "id")
        path2 = g.get_path({"dp"})
        assert path1 is not path2  # cache invalidated

    # -- cycle detection ---------------------------------------------------

    def test_cycle_detection(self):
        g = JoinGraph("t")
        g.add_edge("t", "dp", "dim_product", "product_id", "id")
        g.add_edge("dp", "cat", "dim_category", "category_id", "id")
        g.add_edge("cat", "t", "fact_sales", "fact_id", "id")
        with pytest.raises(ValueError, match="Cycle detected"):
            g.validate()

    def test_no_cycle_passes_validation(self):
        g = JoinGraph("t")
        g.add_edge("t", "dp", "dim_product", "product_id", "id")
        g.add_edge("t", "dc", "dim_customer", "customer_id", "id")
        g.add_edge("dp", "cat", "dim_category", "category_id", "id")
        g.validate()  # should not raise

    # -- topological order -------------------------------------------------

    def test_topological_order(self):
        """Edges are sorted so that a table appears as to_table only after
        its from_table has already appeared."""
        g = JoinGraph("t")
        g.add_edge("t", "dp", "dim_product", "product_id", "id")
        g.add_edge("dp", "cat", "dim_category", "category_id", "id")
        g.add_edge("t", "dc", "dim_customer", "customer_id", "id")
        g.add_edge("cat", "sub", "dim_subcategory", "sub_id", "id")

        path = g.get_path({"dp", "cat", "dc", "sub"})
        seen: set[str] = {"t"}  # root is always available
        for edge in path:
            assert edge.from_table in seen, (
                f"from_table '{edge.from_table}' not yet seen when processing "
                f"edge {edge.edge_key}"
            )
            seen.add(edge.to_table)

    def test_star_schema(self):
        """Classic star schema: single fact table joined to multiple dims."""
        g = JoinGraph("fact")
        g.add_edge("fact", "product", "dim_product", "product_id", "id")
        g.add_edge("fact", "customer", "dim_customer", "customer_id", "id")
        g.add_edge("fact", "date", "dim_date", "date_id", "id")
        g.add_edge("fact", "store", "dim_store", "store_id", "id")

        path = g.get_path({"product", "customer", "date", "store"})
        assert len(path) == 4
        # All edges come directly from fact
        assert all(e.from_table == "fact" for e in path)

    def test_snowflake_schema(self):
        """Snowflake: fact -> product -> category -> department."""
        g = JoinGraph("fact")
        g.add_edge("fact", "product", "dim_product", "product_id", "id")
        g.add_edge("product", "category", "dim_category", "category_id", "id")
        g.add_edge("category", "dept", "dim_department", "dept_id", "id")

        path = g.get_path({"dept"})
        assert len(path) == 3
        # Verify topological order
        to_order = [e.to_table for e in path]
        assert to_order.index("product") < to_order.index("category")
        assert to_order.index("category") < to_order.index("dept")
