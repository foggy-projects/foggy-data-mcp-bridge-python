"""Tests for CTE Composer (engine/compose/).

15+ tests covering CteUnit, JoinSpec, and CteComposer in both CTE and
subquery modes.
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose import (
    ComposedSql,
    CteComposer,
    CteUnit,
    JoinSpec,
)


# ===================================================================
# TestCteUnit
# ===================================================================

class TestCteUnit:

    def test_basic_unit(self):
        unit = CteUnit(alias="cte_0", sql="SELECT id, amount FROM orders")
        assert unit.alias == "cte_0"
        assert unit.sql == "SELECT id, amount FROM orders"
        assert unit.params == []
        assert unit.select_columns is None

    def test_unit_with_params(self):
        unit = CteUnit(
            alias="cte_1",
            sql="SELECT * FROM sales WHERE region = %s",
            params=["East"],
        )
        assert unit.params == ["East"]

    def test_unit_with_select_columns(self):
        unit = CteUnit(
            alias="cte_2",
            sql="SELECT * FROM items",
            select_columns=["id", "name"],
        )
        assert unit.select_columns == ["id", "name"]


# ===================================================================
# TestJoinSpec
# ===================================================================

class TestJoinSpec:

    def test_basic_join_spec(self):
        spec = JoinSpec(
            left_alias="cte_0",
            right_alias="cte_1",
            on_condition="cte_0.order_id = cte_1.order_id",
        )
        assert spec.left_alias == "cte_0"
        assert spec.right_alias == "cte_1"
        assert spec.join_type == "LEFT"

    def test_inner_join_type(self):
        spec = JoinSpec(
            left_alias="a",
            right_alias="b",
            on_condition="a.id = b.id",
            join_type="INNER",
        )
        assert spec.join_type == "INNER"


# ===================================================================
# TestCteComposer
# ===================================================================

class TestCteComposer:

    def test_two_unit_cte(self):
        """Compose 2 units into a CTE statement."""
        units = [
            CteUnit(alias="cte_0", sql="SELECT id, amount FROM orders"),
            CteUnit(alias="cte_1", sql="SELECT id, name FROM customers"),
        ]
        joins = [
            JoinSpec(
                left_alias="cte_0",
                right_alias="cte_1",
                on_condition="cte_0.id = cte_1.id",
            ),
        ]
        result = CteComposer.compose(units, joins)
        assert "WITH" in result.sql
        assert "cte_0 AS (SELECT id, amount FROM orders)" in result.sql
        assert "cte_1 AS (SELECT id, name FROM customers)" in result.sql
        assert "LEFT JOIN cte_1 ON cte_0.id = cte_1.id" in result.sql

    def test_two_unit_subquery(self):
        """use_cte=False => FROM (...) AS t0 LEFT JOIN (...) AS t1."""
        units = [
            CteUnit(alias="cte_0", sql="SELECT id, amount FROM orders"),
            CteUnit(alias="cte_1", sql="SELECT id, name FROM customers"),
        ]
        joins = [
            JoinSpec(
                left_alias="cte_0",
                right_alias="cte_1",
                on_condition="cte_0.id = cte_1.id",
            ),
        ]
        result = CteComposer.compose(units, joins, use_cte=False)
        assert "WITH" not in result.sql
        assert "FROM (SELECT id, amount FROM orders) AS t0" in result.sql
        assert "LEFT JOIN (SELECT id, name FROM customers) AS t1" in result.sql
        assert "t0.id = t1.id" in result.sql

    def test_three_unit_chain(self):
        """3 units with 2 join specs."""
        units = [
            CteUnit(alias="cte_0", sql="SELECT * FROM a"),
            CteUnit(alias="cte_1", sql="SELECT * FROM b"),
            CteUnit(alias="cte_2", sql="SELECT * FROM c"),
        ]
        joins = [
            JoinSpec("cte_0", "cte_1", "cte_0.id = cte_1.id"),
            JoinSpec("cte_1", "cte_2", "cte_1.id = cte_2.id"),
        ]
        result = CteComposer.compose(units, joins)
        assert "cte_0 AS" in result.sql
        assert "cte_1 AS" in result.sql
        assert "cte_2 AS" in result.sql
        assert "LEFT JOIN cte_1 ON" in result.sql
        assert "LEFT JOIN cte_2 ON" in result.sql

    def test_params_merged(self):
        """Parameters from all units are merged in order."""
        units = [
            CteUnit(alias="cte_0", sql="SELECT * FROM a WHERE x = %s", params=[1]),
            CteUnit(alias="cte_1", sql="SELECT * FROM b WHERE y = %s", params=[2]),
        ]
        joins = [JoinSpec("cte_0", "cte_1", "cte_0.id = cte_1.id")]
        result = CteComposer.compose(units, joins)
        assert result.params == [1, 2]

    def test_custom_select_columns(self):
        """Select specific columns in the outer query."""
        units = [
            CteUnit(alias="cte_0", sql="SELECT id, amount FROM orders"),
            CteUnit(alias="cte_1", sql="SELECT id, name FROM customers"),
        ]
        joins = [JoinSpec("cte_0", "cte_1", "cte_0.id = cte_1.id")]
        result = CteComposer.compose(
            units, joins, select_columns=["cte_0.id", "cte_0.amount", "cte_1.name"],
        )
        assert "SELECT cte_0.id, cte_0.amount, cte_1.name" in result.sql

    def test_inner_join(self):
        """INNER join type is used in SQL."""
        units = [
            CteUnit(alias="cte_0", sql="SELECT * FROM a"),
            CteUnit(alias="cte_1", sql="SELECT * FROM b"),
        ]
        joins = [
            JoinSpec("cte_0", "cte_1", "cte_0.id = cte_1.id", join_type="INNER"),
        ]
        result = CteComposer.compose(units, joins)
        assert "INNER JOIN cte_1 ON" in result.sql

    def test_single_unit_no_join(self):
        """1 unit, no joins => simple CTE wrap."""
        units = [CteUnit(alias="cte_0", sql="SELECT id, amount FROM orders")]
        result = CteComposer.compose(units, [])
        assert "WITH cte_0 AS (SELECT id, amount FROM orders)" in result.sql
        assert "FROM cte_0" in result.sql
        assert "JOIN" not in result.sql

    def test_empty_params(self):
        """Units with no params produce empty param list."""
        units = [
            CteUnit(alias="cte_0", sql="SELECT 1"),
            CteUnit(alias="cte_1", sql="SELECT 2"),
        ]
        joins = [JoinSpec("cte_0", "cte_1", "1=1")]
        result = CteComposer.compose(units, joins)
        assert result.params == []

    def test_empty_units(self):
        """Empty unit list => degenerate SQL."""
        result = CteComposer.compose([], [])
        assert result.sql == "SELECT 1"

    def test_composed_sql_dataclass(self):
        cs = ComposedSql(sql="SELECT 1", params=[42])
        assert cs.sql == "SELECT 1"
        assert cs.params == [42]

    def test_subquery_params_merged(self):
        """Subquery mode also merges params correctly."""
        units = [
            CteUnit(alias="cte_0", sql="SELECT * FROM a WHERE x = %s", params=["a"]),
            CteUnit(alias="cte_1", sql="SELECT * FROM b WHERE y = %s", params=["b"]),
        ]
        joins = [JoinSpec("cte_0", "cte_1", "cte_0.id = cte_1.id")]
        result = CteComposer.compose(units, joins, use_cte=False)
        assert result.params == ["a", "b"]

    def test_subquery_custom_select_columns(self):
        """Subquery mode rewrites aliases in select columns."""
        units = [
            CteUnit(alias="cte_0", sql="SELECT id, amount FROM orders"),
            CteUnit(alias="cte_1", sql="SELECT id, name FROM customers"),
        ]
        joins = [JoinSpec("cte_0", "cte_1", "cte_0.id = cte_1.id")]
        result = CteComposer.compose(
            units, joins,
            use_cte=False,
            select_columns=["cte_0.amount", "cte_1.name"],
        )
        assert "SELECT t0.amount, t1.name" in result.sql

    def test_three_unit_subquery(self):
        """3 units in subquery mode."""
        units = [
            CteUnit(alias="cte_0", sql="SELECT * FROM a", params=[1]),
            CteUnit(alias="cte_1", sql="SELECT * FROM b", params=[2]),
            CteUnit(alias="cte_2", sql="SELECT * FROM c", params=[3]),
        ]
        joins = [
            JoinSpec("cte_0", "cte_1", "cte_0.id = cte_1.id"),
            JoinSpec("cte_1", "cte_2", "cte_1.id = cte_2.id"),
        ]
        result = CteComposer.compose(units, joins, use_cte=False)
        assert "WITH" not in result.sql
        assert "t0" in result.sql
        assert "t1" in result.sql
        assert "t2" in result.sql
        assert result.params == [1, 2, 3]

    def test_single_unit_subquery_no_join(self):
        """Single unit in subquery mode, no joins."""
        units = [CteUnit(alias="cte_0", sql="SELECT * FROM orders")]
        result = CteComposer.compose(units, [], use_cte=False)
        assert "FROM (SELECT * FROM orders) AS t0" in result.sql
        assert "JOIN" not in result.sql
