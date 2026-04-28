"""6.3 · JoinPlan compilation tests.

Uses ``CteComposer.compose(units, join_specs)`` underneath. Each
``JoinOn`` becomes part of a single ``on_condition`` string joined by
``AND`` when multiple ON predicates exist.

SQLite carve-out: ``type='full'`` on SQLite dialect is rejected with
``UNSUPPORTED_PLAN_SHAPE``.
"""
from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.compilation import (
    ComposeCompileError,
    compile_plan_to_sql,
    error_codes,
)
from foggy.dataset_model.engine.compose.plan import from_
from foggy.dataset_model.engine.compose.plan.plan import JoinOn


# ===========================================================================
# Basic join shapes
# ===========================================================================


class TestJoinBasic:
    def test_inner_join_emits_inner_keyword(
        self, svc, ctx, base_sales, base_orders
    ):
        on = [JoinOn(left="orderStatus", op="=", right="orderStatus")]
        j = base_sales.join(base_orders, type="inner", on=on)
        composed = compile_plan_to_sql(
            j, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "INNER JOIN" in composed.sql

    def test_left_join_emits_left_keyword(
        self, svc, ctx, base_sales, base_orders
    ):
        on = [JoinOn(left="orderStatus", op="=", right="orderStatus")]
        j = base_sales.join(base_orders, type="left", on=on)
        composed = compile_plan_to_sql(
            j, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "LEFT JOIN" in composed.sql

    def test_right_join_emits_right_keyword(
        self, svc, ctx, base_sales, base_orders
    ):
        on = [JoinOn(left="orderStatus", op="=", right="orderStatus")]
        j = base_sales.join(base_orders, type="right", on=on)
        composed = compile_plan_to_sql(
            j, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "RIGHT JOIN" in composed.sql

    def test_full_outer_join_emits_full_outer_keyword(
        self, svc, ctx, base_sales, base_orders
    ):
        on = [JoinOn(left="orderStatus", op="=", right="orderStatus")]
        j = base_sales.join(base_orders, type="full", on=on)
        composed = compile_plan_to_sql(
            j, ctx, semantic_service=svc, dialect="postgres"
        )
        assert "FULL OUTER JOIN" in composed.sql

    def test_join_on_condition_contains_alias_reference(
        self, svc, ctx, base_sales, base_orders
    ):
        on = [JoinOn(left="orderStatus", op="=", right="orderStatus")]
        j = base_sales.join(base_orders, type="inner", on=on)
        composed = compile_plan_to_sql(
            j, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "ON" in composed.sql
        # cte aliases reference each side's QM alias
        assert "cte_0.orderStatus" in composed.sql
        assert "cte_1.orderStatus" in composed.sql


# ===========================================================================
# Multiple ON conditions
# ===========================================================================


class TestJoinMultipleOn:
    def test_two_on_conditions_joined_by_and(
        self, svc, ctx, base_sales, base_orders
    ):
        on = [
            JoinOn(left="orderStatus", op="=", right="orderStatus"),
            JoinOn(left="orderStatus", op="!=", right="orderStatus"),
        ]
        j = base_sales.join(base_orders, type="inner", on=on)
        composed = compile_plan_to_sql(
            j, ctx, semantic_service=svc, dialect="mysql8"
        )
        # AND joining the two predicates
        assert " AND " in composed.sql
        assert composed.sql.count("orderStatus") >= 4  # 2 left + 2 right refs

    def test_three_on_conditions_joined_by_and(
        self, svc, ctx, base_sales, base_orders
    ):
        on = [
            JoinOn(left="orderStatus", op="=", right="orderStatus"),
            JoinOn(left="orderStatus", op="<=", right="orderStatus"),
            JoinOn(left="orderStatus", op=">=", right="orderStatus"),
        ]
        j = base_sales.join(base_orders, type="inner", on=on)
        composed = compile_plan_to_sql(
            j, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert composed.sql.count(" AND ") >= 2


# ===========================================================================
# Mixed with derived on one side
# ===========================================================================


class TestJoinWithDerived:
    def test_derived_left_side(
        self, svc, ctx, base_sales, base_orders
    ):
        left = base_sales.query(columns=["orderStatus$caption"])
        on = [JoinOn(left="orderStatus", op="=", right="orderStatus")]
        j = left.join(base_orders, type="inner", on=on)
        composed = compile_plan_to_sql(
            j, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "INNER JOIN" in composed.sql
        # Derived subquery wrapping visible somewhere
        assert "FROM (" in composed.sql or "WITH" in composed.sql

    def test_derived_right_side(
        self, svc, ctx, base_sales, base_orders
    ):
        right = base_orders.query(columns=["orderStatus$caption"])
        on = [JoinOn(left="orderStatus", op="=", right="orderStatus")]
        j = base_sales.join(right, type="inner", on=on)
        composed = compile_plan_to_sql(
            j, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "INNER JOIN" in composed.sql

    def test_query_after_join(
        self, svc, ctx, base_sales, base_orders
    ):
        """Can you query over a join? Yes — derived wrapping is allowed."""
        on = [JoinOn(left="orderStatus", op="=", right="orderStatus")]
        j = base_sales.join(base_orders, type="left", on=on)
        d = j.query(columns=["orderStatus$caption"])
        composed = compile_plan_to_sql(
            d, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "LEFT JOIN" in composed.sql
        assert "FROM (" in composed.sql


# ===========================================================================
# SQLite carve-out: full outer join rejected
# ===========================================================================


class TestJoinSQLiteFullOuterRejected:
    def test_full_outer_join_sqlite_raises_unsupported(
        self, svc, ctx, base_sales, base_orders
    ):
        on = [JoinOn(left="orderStatus", op="=", right="orderStatus")]
        j = base_sales.join(base_orders, type="full", on=on)
        with pytest.raises(ComposeCompileError) as exc_info:
            compile_plan_to_sql(
                j, ctx, semantic_service=svc, dialect="sqlite"
            )
        assert exc_info.value.code == error_codes.UNSUPPORTED_PLAN_SHAPE
        assert exc_info.value.phase == "plan-lower"
        assert "full" in exc_info.value.message.lower()
        assert "sqlite" in exc_info.value.message.lower()

    def test_full_outer_join_postgres_ok(
        self, svc, ctx, base_sales, base_orders
    ):
        """Postgres supports FULL OUTER JOIN, so no rejection."""
        on = [JoinOn(left="orderStatus", op="=", right="orderStatus")]
        j = base_sales.join(base_orders, type="full", on=on)
        composed = compile_plan_to_sql(
            j, ctx, semantic_service=svc, dialect="postgres"
        )
        assert "FULL OUTER JOIN" in composed.sql
