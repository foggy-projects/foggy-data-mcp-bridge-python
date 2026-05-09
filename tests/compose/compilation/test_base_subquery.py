"""Phase 2 · Base-model slice subquery tests.

Validates that ``BaseModelPlan.slice_`` entries with ``QueryPlan`` /
``PlanSubquery`` values are correctly lowered to SQL subqueries in the
base model's WHERE clause (pre-aggregation).
"""
from __future__ import annotations

import re

import pytest

from foggy.dataset_model.engine.compose.compilation import (
    compile_plan_to_sql,
    error_codes,
)
from foggy.dataset_model.engine.compose.compilation.errors import ComposeCompileError
from foggy.dataset_model.engine.compose.plan import (
    BaseModelPlan,
    from_,
    subquery,
)
from foggy.dataset_model.engine.compose.compilation.per_base_subquery import (
    inject_where_fragments,
    inject_where_fragments_with_params,
    partition_subquery_slices,
)
from foggy.dataset_model.engine.compose.plan.plan import PlanSubquery


# ---------------------------------------------------------------------------
# partition_subquery_slices — unit tests
# ---------------------------------------------------------------------------


class TestPartitionSubquerySlices:
    """Test the partition helper that separates scalar slices from subquery slices."""

    def test_empty_slice(self):
        scalar, subquery_list = partition_subquery_slices(())
        assert scalar == ()
        assert subquery_list == []

    def test_scalar_only(self):
        entries = (
            {"field": "x", "op": "=", "value": 1},
            {"field": "y", "op": "in", "value": [1, 2]},
        )
        scalar, subquery_list = partition_subquery_slices(entries)
        assert len(scalar) == 2
        assert subquery_list == []

    def test_subquery_only(self):
        rhs = BaseModelPlan(model="X", columns=("a",))
        entries = (
            {"field": "x", "op": "in", "value": rhs},
        )
        scalar, subquery_list = partition_subquery_slices(entries)
        assert scalar == ()
        assert len(subquery_list) == 1

    def test_mixed(self):
        rhs = BaseModelPlan(model="X", columns=("a",))
        entries = (
            {"field": "x", "op": "=", "value": 1},
            {"field": "y", "op": "not in", "value": rhs},
            {"field": "z", "op": ">", "value": 5},
        )
        scalar, subquery_list = partition_subquery_slices(entries)
        assert len(scalar) == 2
        assert len(subquery_list) == 1

    def test_plan_subquery_value(self):
        rhs = BaseModelPlan(model="X", columns=("a",))
        sub = PlanSubquery(plan=rhs, field="a")
        entries = (
            {"field": "x", "op": "in", "value": sub},
        )
        scalar, subquery_list = partition_subquery_slices(entries)
        assert scalar == ()
        assert len(subquery_list) == 1


# ---------------------------------------------------------------------------
# inject_where_fragments — unit tests
# ---------------------------------------------------------------------------


class TestInjectWhereFragments:
    """Test the SQL string injection helper."""

    def test_inject_with_existing_where(self):
        sql = "SELECT x FROM t WHERE t.a = ?\nGROUP BY x"
        result = inject_where_fragments(sql, ["t.b IN (SELECT ...)"])
        assert "t.a = ? AND t.b IN (SELECT ...)" in result
        assert "GROUP BY x" in result

    def test_inject_without_existing_where(self):
        sql = "SELECT x FROM t\nGROUP BY x"
        result = inject_where_fragments(sql, ["t.b NOT IN (SELECT ...)"])
        assert "WHERE t.b NOT IN (SELECT ...)" in result
        assert "GROUP BY x" in result

    def test_inject_without_where_or_groupby(self):
        sql = "SELECT x FROM t"
        result = inject_where_fragments(sql, ["t.b IN (SELECT ...)"])
        assert "WHERE t.b IN (SELECT ...)" in result

    def test_inject_multiple_fragments(self):
        sql = "SELECT x FROM t WHERE t.a = ?\nGROUP BY x"
        result = inject_where_fragments(sql, [
            "t.b IN (SELECT ...)",
            "t.c NOT IN (SELECT ...)",
        ])
        assert "t.b IN (SELECT ...) AND t.c NOT IN (SELECT ...)" in result

    def test_no_fragments_returns_original(self):
        sql = "SELECT x FROM t WHERE t.a = ?"
        result = inject_where_fragments(sql, [])
        assert result == sql

    def test_param_merge_with_existing_where_before_group_by_params(self):
        sql = "SELECT x FROM t WHERE t.a = ?\nGROUP BY ROUND(t.b, ?)"
        result_sql, result_params = inject_where_fragments_with_params(
            sql,
            ["where-param", "group-param"],
            ["t.c IN (SELECT y FROM u WHERE u.z = ?)"],
            ["subquery-param"],
        )
        assert "t.a = ? AND t.c IN" in result_sql
        assert result_params == [
            "where-param",
            "subquery-param",
            "group-param",
        ]

    def test_param_merge_without_where_before_group_by_params(self):
        sql = "SELECT ROUND(t.x, ?) FROM t\nGROUP BY ROUND(t.y, ?)"
        result_sql, result_params = inject_where_fragments_with_params(
            sql,
            ["select-param", "group-param"],
            ["t.c NOT IN (SELECT y FROM u WHERE u.z = ?)"],
            ["subquery-param"],
        )
        assert "\nWHERE t.c NOT IN" in result_sql
        assert result_params == [
            "select-param",
            "subquery-param",
            "group-param",
        ]

    def test_param_merge_at_end_appends_fragment_params(self):
        sql = "SELECT x FROM t WHERE t.a = ?"
        _, result_params = inject_where_fragments_with_params(
            sql,
            ["where-param"],
            ["t.c IN (SELECT y FROM u WHERE u.z = ?)"],
            ["subquery-param"],
        )
        assert result_params == ["where-param", "subquery-param"]


# ---------------------------------------------------------------------------
# End-to-end compile tests
# ---------------------------------------------------------------------------


class TestBaseSubqueryCompile:
    """End-to-end tests compiling BaseModelPlan with subquery slices."""

    def test_base_in_subquery(self, svc, ctx):
        """IN subquery in base slice → SQL contains IN (SELECT ...)."""
        rhs_plan = from_(
            model="FactSalesModel",
            columns=["orderStatus$caption"],
            slice=[{"field": "salesAmount", "op": ">", "value": 100}],
        )
        plan = BaseModelPlan(
            model="FactSalesModel",
            columns=("orderStatus$caption", "salesAmount"),
            slice_=(
                {"field": "orderStatus$caption", "op": "in", "value": rhs_plan},
            ),
        )

        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="postgres",
        )

        assert " IN (SELECT " in composed.sql
        assert "IS NOT NULL)" in composed.sql
        assert 100 in composed.params

    def test_base_not_in_subquery(self, svc, ctx):
        """NOT IN subquery in base slice → SQL contains NOT IN (SELECT ...)."""
        rhs_plan = from_(
            model="FactSalesModel",
            columns=["orderStatus$caption"],
        )
        plan = BaseModelPlan(
            model="FactSalesModel",
            columns=("orderStatus$caption", "salesAmount"),
            slice_=(
                {"field": "orderStatus$caption", "op": "not in", "value": rhs_plan},
            ),
        )

        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="postgres",
        )

        assert " NOT IN (SELECT " in composed.sql
        assert "IS NOT NULL)" in composed.sql

    def test_pre_aggregation_semantics(self, svc, ctx):
        """Subquery condition is in WHERE (before GROUP BY), not HAVING."""
        rhs_plan = from_(
            model="FactSalesModel",
            columns=["orderStatus$caption"],
        )
        plan = BaseModelPlan(
            model="FactSalesModel",
            columns=("orderStatus$caption", "salesAmount"),
            slice_=(
                {"field": "orderStatus$caption", "op": "not in", "value": rhs_plan},
            ),
        )

        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="postgres",
        )

        sql_upper = composed.sql.upper()
        # The NOT IN should appear in WHERE, before GROUP BY
        where_pos = sql_upper.find("WHERE")
        group_pos = sql_upper.find("GROUP BY")
        not_in_pos = sql_upper.find("NOT IN (SELECT")
        assert where_pos >= 0, "Expected WHERE clause"
        assert not_in_pos >= 0, "Expected NOT IN (SELECT ...)"
        if group_pos >= 0:
            assert not_in_pos < group_pos, (
                "Subquery condition must appear before GROUP BY"
            )

    def test_mixed_scalar_and_subquery_slices(self, svc, ctx):
        """Scalar slice + subquery slice → both in WHERE."""
        rhs_plan = from_(
            model="FactSalesModel",
            columns=["orderStatus$caption"],
        )
        plan = BaseModelPlan(
            model="FactSalesModel",
            columns=("orderStatus$caption", "salesAmount"),
            slice_=(
                {"field": "salesAmount", "op": ">", "value": 50},
                {"field": "orderStatus$caption", "op": "not in", "value": rhs_plan},
            ),
        )

        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="postgres",
        )

        assert " NOT IN (SELECT " in composed.sql
        assert 50 in composed.params

    def test_explicit_subquery_field(self, svc, ctx):
        """Using subquery(plan, field) for multi-column subquery plans."""
        rhs_plan = from_(
            model="FactSalesModel",
            columns=["orderStatus$caption", "salesAmount"],
        )
        plan = BaseModelPlan(
            model="FactSalesModel",
            columns=("orderStatus$caption", "salesAmount"),
            slice_=(
                {
                    "field": "orderStatus$caption",
                    "op": "in",
                    "value": subquery(rhs_plan, "orderStatus$caption"),
                },
            ),
        )

        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="postgres",
        )

        assert " IN (SELECT " in composed.sql
        assert "IS NOT NULL)" in composed.sql

    def test_having_subquery_still_rejected(self, svc, ctx):
        """Phase 2: having subqueries remain rejected (fail-closed)."""
        rhs_plan = from_(
            model="FactSalesModel",
            columns=["orderStatus$caption"],
        )
        plan = BaseModelPlan(
            model="FactSalesModel",
            columns=("orderStatus$caption", "salesAmount"),
            having=(
                {
                    "field": "orderStatus$caption",
                    "op": "in",
                    "value": rhs_plan,
                },
            ),
        )

        with pytest.raises(ValueError) as exc_info:
            compile_plan_to_sql(
                plan, ctx, semantic_service=svc, dialect="postgres",
            )

        assert "COMPOSE_SUBQUERY_VALUE_UNSUPPORTED" in str(exc_info.value)

    def test_null_safe_not_in(self, svc, ctx):
        """NOT IN subquery wraps with IS NOT NULL to handle NULL semantics."""
        rhs_plan = from_(
            model="FactSalesModel",
            columns=["orderStatus$caption"],
        )
        plan = BaseModelPlan(
            model="FactSalesModel",
            columns=("orderStatus$caption", "salesAmount"),
            slice_=(
                {"field": "orderStatus$caption", "op": "not in", "value": rhs_plan},
            ),
        )

        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="postgres",
        )

        # The subquery SQL should have IS NOT NULL filtering
        assert "IS NOT NULL)" in composed.sql

    def test_param_ordering(self, svc, ctx):
        """Subquery params must follow preceding base WHERE params."""
        rhs_plan = from_(
            model="FactSalesModel",
            columns=["orderStatus$caption"],
            slice=[{"field": "salesAmount", "op": ">", "value": 999}],
        )
        plan = BaseModelPlan(
            model="FactSalesModel",
            columns=("orderStatus$caption", "salesAmount"),
            slice_=(
                {"field": "orderStatus$caption", "op": "=", "value": "paid"},
                {"field": "orderStatus$caption", "op": "in", "value": rhs_plan},
            ),
        )

        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="postgres",
        )

        # "paid" comes from the base WHERE; 999 comes from the RHS subquery.
        assert "paid" in composed.params
        assert 999 in composed.params
        idx_paid = composed.params.index("paid")
        idx_999 = composed.params.index(999)
        assert idx_paid < idx_999, (
            f"Scalar param 'paid' (idx={idx_paid}) should precede subquery "
            f"param 999 (idx={idx_999})"
        )

    def test_nested_rhs_derived_plan(self, svc, ctx):
        """RHS plan is a derived plan with its own slices → compiled correctly."""
        inner = from_(
            model="FactSalesModel",
            columns=["orderStatus$caption", "salesAmount"],
        )
        rhs_plan = inner.query(
            columns=["orderStatus$caption"],
            slice=[{"field": "salesAmount", "op": ">", "value": 200}],
        )
        plan = BaseModelPlan(
            model="FactSalesModel",
            columns=("orderStatus$caption", "salesAmount"),
            slice_=(
                {"field": "orderStatus$caption", "op": "not in", "value": rhs_plan},
            ),
        )

        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="postgres",
        )

        assert " NOT IN (SELECT " in composed.sql
        assert 200 in composed.params

    def test_compound_base_subquery_slice_rejected_fail_closed(self, svc, ctx):
        rhs_plan = from_(
            model="FactSalesModel",
            columns=["orderStatus$caption"],
        )
        plan = BaseModelPlan(
            model="FactSalesModel",
            columns=("orderStatus$caption", "salesAmount"),
            slice_=(
                {
                    "$and": [
                        {
                            "field": "orderStatus$caption",
                            "op": "in",
                            "value": rhs_plan,
                        },
                    ]
                },
            ),
        )

        with pytest.raises(ComposeCompileError) as exc_info:
            compile_plan_to_sql(
                plan, ctx, semantic_service=svc, dialect="postgres",
            )

        assert "COMPOSE_SUBQUERY_VALUE_UNSUPPORTED" in str(exc_info.value)

    def test_unresolvable_lhs_field_rejected_fail_closed(self, svc, ctx):
        rhs_plan = from_(
            model="FactSalesModel",
            columns=["orderStatus$caption"],
        )
        plan = BaseModelPlan(
            model="FactSalesModel",
            columns=("orderStatus$caption", "salesAmount"),
            slice_=(
                {
                    "field": "notARealField",
                    "op": "in",
                    "value": rhs_plan,
                },
            ),
        )

        with pytest.raises(ComposeCompileError) as exc_info:
            compile_plan_to_sql(
                plan, ctx, semantic_service=svc, dialect="postgres",
            )

        assert "COMPOSE_SUBQUERY_FIELD_NOT_FOUND" in str(exc_info.value)

    def test_cross_datasource_base_subquery_rejected_fail_closed(
        self, svc, ctx, make_ds_provider
    ):
        provider = make_ds_provider({
            "FactSalesModel": "mysql_main",
            "FactOrderModel": "pg_analytics",
        })
        rhs_plan = from_(
            model="FactOrderModel",
            columns=["orderStatus$caption"],
        )
        plan = BaseModelPlan(
            model="FactSalesModel",
            columns=("orderStatus$caption", "salesAmount"),
            slice_=(
                {
                    "field": "orderStatus$caption",
                    "op": "not in",
                    "value": rhs_plan,
                },
            ),
        )

        with pytest.raises(ComposeCompileError) as exc_info:
            compile_plan_to_sql(
                plan,
                ctx,
                semantic_service=svc,
                model_info_provider=provider,
                dialect="postgres",
            )

        assert exc_info.value.code == error_codes.CROSS_DATASOURCE_REJECTED
        assert exc_info.value.phase == "plan-lower"
        assert "mysql_main" in exc_info.value.message
        assert "pg_analytics" in exc_info.value.message
