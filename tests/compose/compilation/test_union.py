"""6.2 · UnionPlan compilation tests.

UnionPlan emits native ``UNION`` / ``UNION ALL`` SQL at the compose
layer — NOT through ``CteComposer`` (which is ON-condition-driven and
for joins). Union is column-aligned; M4 already validated the column
count match, so M6 only emits the SQL.

``CROSS_DATASOURCE_REJECTED`` is tested via the error-code string
assertion and mock path per D5; real cross-datasource detection is
deferred to F-7 follow-up.
"""
from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.compilation import (
    ComposeCompileError,
    compile_plan_to_sql,
    error_codes,
)
from foggy.dataset_model.engine.compose.plan import from_


class TestUnionBasic:
    def test_union_distinct_keyword(self, svc, ctx, base_sales, base_orders):
        """Union with all=False (default) emits plain UNION keyword."""
        u = base_sales.union(base_orders)
        composed = compile_plan_to_sql(
            u, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "UNION" in composed.sql
        # Not UNION ALL — default is distinct union
        assert "UNION ALL" not in composed.sql

    def test_union_all_keyword(self, svc, ctx, base_sales, base_orders):
        """Union with all=True emits UNION ALL keyword."""
        u = base_sales.union(base_orders, all=True)
        composed = compile_plan_to_sql(
            u, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "UNION ALL" in composed.sql

    def test_union_both_sides_appear_in_sql(
        self, svc, ctx, base_sales, base_orders
    ):
        u = base_sales.union(base_orders)
        composed = compile_plan_to_sql(
            u, ctx, semantic_service=svc, dialect="mysql8"
        )
        # Both fact tables must appear
        assert "fact_sales" in composed.sql
        assert "fact_order" in composed.sql

    def test_union_returns_composed_sql(self, svc, ctx, base_sales, base_orders):
        u = base_sales.union(base_orders)
        composed = compile_plan_to_sql(
            u, ctx, semantic_service=svc, dialect="mysql8"
        )
        # ComposedSql type has .sql and .params
        assert hasattr(composed, "sql")
        assert hasattr(composed, "params")


class TestUnionParams:
    def test_union_flows_left_then_right_params(
        self, svc, ctx
    ):
        """Spec parity.md: union emits left sql + params, then right sql + params."""
        a = from_(
            model="FactSalesModel",
            columns=["orderStatus"],
            # slice produces a param the base plan will inline
            slice=[{"field": "orderStatus", "op": "=", "value": "A"}],
        )
        b = from_(
            model="FactOrderModel",
            columns=["orderStatus"],
            slice=[{"field": "orderStatus", "op": "=", "value": "B"}],
        )
        u = a.union(b, all=True)
        composed = compile_plan_to_sql(
            u, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "A" in composed.params
        assert "B" in composed.params
        # Left → right ordering preserved
        assert composed.params.index("A") < composed.params.index("B")


class TestUnionWithDerived:
    def test_derived_side_in_union(self, svc, ctx, base_sales, base_orders):
        """One side is a DerivedQueryPlan — both compile and concatenate."""
        left = base_sales.query(columns=["orderStatus"])
        u = left.union(base_orders)
        composed = compile_plan_to_sql(
            u, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "UNION" in composed.sql
        assert "FROM (" in composed.sql  # derived wrapping

    def test_both_sides_derived(self, svc, ctx, base_sales, base_orders):
        left = base_sales.query(columns=["orderStatus"])
        right = base_orders.query(columns=["orderStatus"])
        u = left.union(right)
        composed = compile_plan_to_sql(
            u, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "UNION" in composed.sql
        # Two derived wrappings visible
        assert composed.sql.count("FROM (") >= 2


class TestUnionMultipleWay:
    def test_three_way_union_left_associative(
        self, svc, ctx, base_sales, base_orders, base_payments
    ):
        """3-way union: (a ∪ b) ∪ c → nested unions compile successfully."""
        u2 = base_sales.union(base_orders)
        u3 = u2.union(base_payments)
        composed = compile_plan_to_sql(
            u3, ctx, semantic_service=svc, dialect="mysql8"
        )
        # 2 UNION tokens in 3-way union
        assert composed.sql.count("UNION") >= 2

    def test_four_way_union(
        self, svc, ctx, base_sales, base_orders, base_payments
    ):
        """4-way union nests deeper but still works."""
        fourth = from_(
            model="FactSalesModel",
            columns=["orderStatus", "salesAmount"],
        )
        u = base_sales.union(base_orders).union(base_payments).union(fourth)
        composed = compile_plan_to_sql(
            u, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert composed.sql.count("UNION") >= 3


class TestUnionCrossDatasourceRejectedContract:
    """D5 decision — CROSS_DATASOURCE_REJECTED defined but not live-detected.

    These tests verify the error contract is constructible and the code
    is a valid namespace member. Real live-detection is deferred to F-7.
    """

    def test_error_code_constructible(self):
        """Hand-roll a ComposeCompileError with this code to prove the
        constant flows through the constructor."""
        err = ComposeCompileError(
            code=error_codes.CROSS_DATASOURCE_REJECTED,
            phase="compile",
            message="mock detection",
        )
        assert err.code == "compose-compile-error/cross-datasource-rejected"
        assert err.phase == "compile"

    def test_code_string_exact(self):
        assert (
            error_codes.CROSS_DATASOURCE_REJECTED
            == "compose-compile-error/cross-datasource-rejected"
        )

    @pytest.mark.xfail(
        reason=(
            "cross-datasource detection deferred to post-M6 · F-7 "
            "(requires ModelBinding.datasource_id or "
            "ModelInfoProvider.get_datasource_id — neither exists yet in "
            "M1/M5 frozen contract)"
        ),
        strict=True,
    )
    def test_cross_datasource_live_detection_via_real_plan(self):
        """Flag xfail: live detection on a real cross-DS plan would
        require a ModelBinding shape we haven't shipped yet."""
        raise AssertionError(
            "placeholder — live detection arrives in F-7"
        )
