"""6.1 · per-base BaseModelPlan compilation via v1.3 ``_build_query``.

Focuses on the ``compile_plan_to_sql`` one-shot path for a single
``BaseModelPlan`` — structural SQL shape, binding injection, error
propagation. Derived-chain tests live in ``test_derived.py``.
"""
from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.compilation import (
    ComposeCompileError,
    compile_plan_to_sql,
    error_codes,
)
from foggy.dataset_model.engine.compose.plan import from_


# ===========================================================================
# Single BaseModelPlan — happy path
# ===========================================================================


class TestBaseModelPlanBasic:
    def test_single_base_returns_composed_sql(self, svc, ctx, base_sales):
        composed = compile_plan_to_sql(
            base_sales,
            ctx,
            semantic_service=svc,
            dialect="mysql8",
        )
        assert composed.sql
        assert isinstance(composed.params, list)

    def test_select_columns_appear_in_sql(self, svc, ctx, base_sales):
        composed = compile_plan_to_sql(
            base_sales, ctx, semantic_service=svc, dialect="mysql8"
        )
        # The CteComposer wraps the inner SELECT and re-projects with
        # ``SELECT *`` by default, but the inner SQL must contain the
        # requested columns' physical mapping.
        assert "order_status" in composed.sql
        assert "sales_amount" in composed.sql

    def test_qm_shape_wrapped_with_cte_keyword(self, svc, ctx, base_sales):
        composed = compile_plan_to_sql(
            base_sales, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert composed.sql.upper().startswith("WITH ")
        assert "cte_0" in composed.sql

    def test_qm_shape_wrapped_as_subquery_on_mysql57(self, svc, ctx, base_sales):
        """r2 §6.5: dialect='mysql' is conservative 5.7-compat → no CTE."""
        composed = compile_plan_to_sql(
            base_sales, ctx, semantic_service=svc, dialect="mysql"
        )
        assert not composed.sql.upper().startswith("WITH ")
        # Subquery mode uses ``FROM (...) AS t0``
        assert "t0" in composed.sql


class TestBaseModelPlanShapeFields:
    def test_group_by_field_is_honored(self, svc, ctx):
        plan = from_(
            model="FactSalesModel",
            columns=["orderStatus$caption", "salesAmount"],
            group_by=["orderStatus$caption"],
        )
        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "GROUP BY" in composed.sql
        assert "order_status" in composed.sql

    def test_order_by_field_is_honored(self, svc, ctx):
        plan = from_(
            model="FactSalesModel",
            columns=["orderStatus$caption", "salesAmount"],
            order_by=["orderStatus$caption"],
        )
        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "ORDER BY" in composed.sql

    def test_limit_is_honored(self, svc, ctx):
        plan = from_(
            model="FactSalesModel",
            columns=["orderStatus$caption", "salesAmount"],
            limit=100,
        )
        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "LIMIT 100" in composed.sql

    def test_start_offset_combined_with_limit(self, svc, ctx):
        plan = from_(
            model="FactSalesModel",
            columns=["orderStatus$caption", "salesAmount"],
            limit=50,
            start=10,
        )
        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "LIMIT 50" in composed.sql
        assert "OFFSET 10" in composed.sql

    def test_empty_slice_produces_no_where(self, svc, ctx, base_sales):
        composed = compile_plan_to_sql(
            base_sales, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "WHERE" not in composed.sql

    def test_empty_group_by_produces_auto_group_by_when_aggregated(
        self, svc, ctx, base_sales
    ):
        """v1.3 auto-groupby still activates through M6 — we're delegating
        to the same engine, so this is a transparency check."""
        composed = compile_plan_to_sql(
            base_sales, ctx, semantic_service=svc, dialect="mysql8"
        )
        # ``salesAmount`` is a SUM measure → auto GROUP BY kicks in on
        # ``orderStatus``
        assert "GROUP BY" in composed.sql


class TestBaseModelPlanDistinct:
    def test_distinct_flag_does_not_crash(self, svc, ctx):
        """``distinct=True`` flows into ``SemanticQueryRequest``; actual SQL
        emission (``DISTINCT`` vs auto-``GROUP BY``) is v1.3 engine
        policy — M6 only verifies the plan shape travels without panic."""
        plan = from_(
            model="FactSalesModel",
            columns=["orderStatus$caption"],
            distinct=True,
        )
        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="mysql8"
        )
        # The physical column must appear in the generated SQL regardless
        # of whether v1.3 used DISTINCT or GROUP BY for deduplication.
        assert "order_status" in composed.sql


# ===========================================================================
# Error paths
# ===========================================================================


class TestMissingBinding:
    def test_unknown_qm_raises_missing_binding(self, svc, ctx):
        """If the QM isn't registered with the service AND no binding exists,
        ``MISSING_BINDING`` fires at plan-lower."""
        plan = from_(model="NonExistentQM", columns=["id"])
        bindings = {}  # explicit empty so we hit MISSING_BINDING at top level
        with pytest.raises(ComposeCompileError) as exc_info:
            compile_plan_to_sql(
                plan,
                ctx,
                semantic_service=svc,
                bindings=bindings,
                dialect="mysql8",
            )
        assert exc_info.value.code == error_codes.MISSING_BINDING
        assert exc_info.value.phase == "plan-lower"
        assert "NonExistentQM" in exc_info.value.message

    def test_qm_not_registered_with_service_raises_missing_binding(
        self, svc, ctx, make_fixed_resolver
    ):
        """QM has a binding (upstream M5 resolver returned one) but
        ``svc.get_model`` returns None → MISSING_BINDING via per_base path."""
        from foggy.dataset_model.engine.compose.context import ComposeQueryContext
        from foggy.dataset_model.engine.compose.security import ModelBinding

        resolver = make_fixed_resolver({"GhostQM": ModelBinding()})
        custom_ctx = ComposeQueryContext(
            principal=ctx.principal,
            namespace=ctx.namespace,
            authority_resolver=resolver,
        )
        plan = from_(model="GhostQM", columns=["x"])

        with pytest.raises(ComposeCompileError) as exc_info:
            compile_plan_to_sql(
                plan,
                custom_ctx,
                semantic_service=svc,
                dialect="mysql8",
            )
        assert exc_info.value.code == error_codes.MISSING_BINDING
        assert "GhostQM" in exc_info.value.message


class TestPerBaseCompileFailedCauseChain:
    def test_engine_exception_wrapped_with_cause(self, svc, ctx, monkeypatch):
        """★ D1: ``_build_query`` original exception must survive as
        ``ComposeCompileError.__cause__``."""

        original_build = svc._build_query
        sentinel = RuntimeError("deep v1.3 engine panic")

        def boom(table_model, request):
            raise sentinel

        monkeypatch.setattr(svc, "_build_query", boom)

        plan = from_(model="FactSalesModel", columns=["orderStatus$caption"])

        with pytest.raises(ComposeCompileError) as exc_info:
            compile_plan_to_sql(
                plan,
                ctx,
                semantic_service=svc,
                dialect="mysql8",
            )
        assert exc_info.value.code == error_codes.PER_BASE_COMPILE_FAILED
        assert exc_info.value.phase == "compile"
        # The original exception must be kept on __cause__
        assert exc_info.value.__cause__ is sentinel

    def test_error_message_includes_model_name(self, svc, ctx, monkeypatch):
        def boom(table_model, request):
            raise ValueError("resolver down")

        monkeypatch.setattr(svc, "_build_query", boom)

        plan = from_(model="FactSalesModel", columns=["orderStatus$caption"])

        with pytest.raises(ComposeCompileError) as exc_info:
            compile_plan_to_sql(
                plan,
                ctx,
                semantic_service=svc,
                dialect="mysql8",
            )
        assert "FactSalesModel" in exc_info.value.message
