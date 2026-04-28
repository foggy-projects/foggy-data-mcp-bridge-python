"""6.2 · UnionPlan compilation tests.

UnionPlan emits native ``UNION`` / ``UNION ALL`` SQL at the compose
layer — NOT through ``CteComposer`` (which is ON-condition-driven and
for joins). Union is column-aligned; M4 already validated the column
count match, so M6 only emits the SQL.

``CROSS_DATASOURCE_REJECTED`` is tested via real compile-time detection
using a datasource-aware ``ModelInfoProvider`` (F-7 post-v1.5 Stage 1).
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
            columns=["orderStatus$caption"],
            # slice produces a param the base plan will inline
            slice=[{"field": "orderStatus", "op": "=", "value": "A"}],
        )
        b = from_(
            model="FactOrderModel",
            columns=["orderStatus$caption"],
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
        left = base_sales.query(columns=["orderStatus$caption"])
        u = left.union(base_orders)
        composed = compile_plan_to_sql(
            u, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "UNION" in composed.sql
        assert "FROM (" in composed.sql  # derived wrapping

    def test_both_sides_derived(self, svc, ctx, base_sales, base_orders):
        left = base_sales.query(columns=["orderStatus$caption"])
        right = base_orders.query(columns=["orderStatus$caption"])
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
            columns=["orderStatus$caption", "salesAmount"],
        )
        u = base_sales.union(base_orders).union(base_payments).union(fourth)
        composed = compile_plan_to_sql(
            u, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert composed.sql.count("UNION") >= 3


class TestUnionCrossDatasourceRejectedContract:
    """F-7 — CROSS_DATASOURCE_REJECTED live detection via ModelInfoProvider.

    The error code was defined in M6; real detection was deferred to F-7
    (post-v1.5 Stage 1). These tests verify the compile-time detection
    path using a datasource-aware ``ModelInfoProvider``.
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

    def test_cross_datasource_live_detection_via_real_plan(
        self, svc, ctx, make_ds_provider
    ):
        """F-7: live detection on a real cross-datasource plan raises
        CROSS_DATASOURCE_REJECTED when the provider reports different
        datasource IDs for the two models."""
        provider = make_ds_provider({
            "FactSalesModel": "mysql_main",
            "FactOrderModel": "pg_analytics",
        })
        a = from_(model="FactSalesModel", columns=["orderStatus$caption", "salesAmount"])
        b = from_(model="FactOrderModel", columns=["orderStatus$caption", "totalAmount"])
        u = a.union(b)
        with pytest.raises(ComposeCompileError) as exc_info:
            compile_plan_to_sql(
                u, ctx,
                semantic_service=svc,
                model_info_provider=provider,
                dialect="mysql8",
            )
        assert exc_info.value.code == error_codes.CROSS_DATASOURCE_REJECTED
        assert exc_info.value.phase == "plan-lower"
        assert "mysql_main" in exc_info.value.message
        assert "pg_analytics" in exc_info.value.message

    def test_same_datasource_union_passes(
        self, svc, ctx, make_ds_provider
    ):
        """F-7: union of two models on the SAME datasource compiles normally."""
        provider = make_ds_provider({
            "FactSalesModel": "mysql_main",
            "FactOrderModel": "mysql_main",
        })
        a = from_(model="FactSalesModel", columns=["orderStatus$caption", "salesAmount"])
        b = from_(model="FactOrderModel", columns=["orderStatus$caption", "totalAmount"])
        u = a.union(b)
        composed = compile_plan_to_sql(
            u, ctx,
            semantic_service=svc,
            model_info_provider=provider,
            dialect="mysql8",
        )
        assert "UNION" in composed.sql

    def test_unknown_datasource_permissive(
        self, svc, ctx, make_ds_provider
    ):
        """F-7: when one or both models have None datasource ID (unknown),
        the check is permissive — no rejection."""
        provider = make_ds_provider({
            "FactSalesModel": "mysql_main",
            "FactOrderModel": None,  # unknown
        })
        a = from_(model="FactSalesModel", columns=["orderStatus$caption", "salesAmount"])
        b = from_(model="FactOrderModel", columns=["orderStatus$caption", "totalAmount"])
        u = a.union(b)
        composed = compile_plan_to_sql(
            u, ctx,
            semantic_service=svc,
            model_info_provider=provider,
            dialect="mysql8",
        )
        assert "UNION" in composed.sql

    def test_both_unknown_datasource_permissive(
        self, svc, ctx, make_ds_provider
    ):
        """F-7: when both models have None datasource ID, no rejection."""
        provider = make_ds_provider({
            "FactSalesModel": None,
            "FactOrderModel": None,
        })
        a = from_(model="FactSalesModel", columns=["orderStatus$caption", "salesAmount"])
        b = from_(model="FactOrderModel", columns=["orderStatus$caption", "totalAmount"])
        u = a.union(b)
        composed = compile_plan_to_sql(
            u, ctx,
            semantic_service=svc,
            model_info_provider=provider,
            dialect="mysql8",
        )
        assert "UNION" in composed.sql

    def test_no_provider_no_rejection(self, svc, ctx, base_sales, base_orders):
        """F-7: backward-compatible — when no provider is given, the
        cross-datasource check is skipped entirely."""
        u = base_sales.union(base_orders)
        composed = compile_plan_to_sql(
            u, ctx, semantic_service=svc, dialect="mysql8",
        )
        assert "UNION" in composed.sql

    def test_three_way_cross_datasource_rejected(
        self, svc, ctx, make_ds_provider
    ):
        """F-7: 3-way union with a datasource mismatch in the nested
        union is caught at the outermost union level."""
        provider = make_ds_provider({
            "FactSalesModel": "ds_alpha",
            "FactOrderModel": "ds_alpha",
            "FactPaymentModel": "ds_beta",
        })
        a = from_(model="FactSalesModel", columns=["orderStatus$caption", "salesAmount"])
        b = from_(model="FactOrderModel", columns=["orderStatus$caption", "totalAmount"])
        c = from_(model="FactPaymentModel", columns=["payMethod$caption", "payAmount"])
        u = a.union(b).union(c)
        with pytest.raises(ComposeCompileError) as exc_info:
            compile_plan_to_sql(
                u, ctx,
                semantic_service=svc,
                model_info_provider=provider,
                dialect="mysql8",
            )
        assert exc_info.value.code == error_codes.CROSS_DATASOURCE_REJECTED

    def test_union_all_cross_datasource_rejected(
        self, svc, ctx, make_ds_provider
    ):
        """F-7: UNION ALL also triggers cross-datasource detection."""
        provider = make_ds_provider({
            "FactSalesModel": "ds1",
            "FactOrderModel": "ds2",
        })
        a = from_(model="FactSalesModel", columns=["orderStatus$caption", "salesAmount"])
        b = from_(model="FactOrderModel", columns=["orderStatus$caption", "totalAmount"])
        u = a.union(b, all=True)
        with pytest.raises(ComposeCompileError) as exc_info:
            compile_plan_to_sql(
                u, ctx,
                semantic_service=svc,
                model_info_provider=provider,
                dialect="mysql8",
            )
        assert exc_info.value.code == error_codes.CROSS_DATASOURCE_REJECTED
