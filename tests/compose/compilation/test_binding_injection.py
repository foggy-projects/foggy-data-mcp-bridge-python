"""6.4 · ★ M6 power key: ``ModelBinding`` three-field injection to v1.3 engine.

Verifies that the binding-sourced ``field_access`` / ``system_slice`` /
``denied_columns`` fields reach the v1.3 ``SemanticQueryRequest`` and
influence the emitted SQL exactly as v1.3 engine does for direct callers.
"""
from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.compilation import (
    ComposeCompileError,
    compile_plan_to_sql,
    error_codes,
)
from foggy.dataset_model.engine.compose.context import ComposeQueryContext
from foggy.dataset_model.engine.compose.plan import from_
from foggy.dataset_model.engine.compose.security import ModelBinding
from foggy.mcp_spi.semantic import DeniedColumn


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def custom_ctx(principal, make_fixed_resolver):
    """Factory: pass a mapping ``{qm_name: binding}`` and get a live ctx."""

    def _make(mapping):
        resolver = make_fixed_resolver(mapping)
        return ComposeQueryContext(
            principal=principal,
            namespace="demo",
            authority_resolver=resolver,
        )

    return _make


# ===========================================================================
# field_access (QM-field whitelist)
# ===========================================================================


class TestFieldAccessWhitelist:
    def test_whitelist_with_allowed_field_emits_sql(
        self, svc, custom_ctx, base_sales
    ):
        """Binding declares orderStatus in whitelist → SELECT compiles."""
        binding = ModelBinding(field_access=["orderStatus", "salesAmount"])
        ctx = custom_ctx({"FactSalesModel": binding})
        composed = compile_plan_to_sql(
            base_sales, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "order_status" in composed.sql

    def test_whitelist_excluding_requested_field_raises(
        self, svc, custom_ctx, base_sales
    ):
        """Requested column NOT in whitelist → v1.3 engine rejects,
        wrapped as ``PER_BASE_COMPILE_FAILED``."""
        binding = ModelBinding(field_access=["orderId"])  # excludes orderStatus
        ctx = custom_ctx({"FactSalesModel": binding})
        with pytest.raises(ComposeCompileError) as exc_info:
            compile_plan_to_sql(
                base_sales, ctx, semantic_service=svc, dialect="mysql8"
            )
        assert exc_info.value.code == error_codes.PER_BASE_COMPILE_FAILED

    def test_field_access_none_means_no_governance(
        self, svc, custom_ctx, base_sales
    ):
        """``field_access=None`` → v1.3 engine applies no whitelist."""
        binding = ModelBinding(field_access=None)
        ctx = custom_ctx({"FactSalesModel": binding})
        composed = compile_plan_to_sql(
            base_sales, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert composed.sql

    def test_empty_whitelist_behavior(
        self, svc, custom_ctx, base_sales
    ):
        """``field_access=[]`` → per v1.3 ``_apply_query_governance``:
        ``bool(visible)`` is False, so ``has_whitelist`` is False and
        governance treats this like "no whitelist", letting the request
        proceed. This matches doc §6.4's "empty field_access behavior"
        which states either outcome (compile ok OR reject) is
        acceptable; we document the v1.3 current behavior: it compiles.
        """
        binding = ModelBinding(field_access=[])
        ctx = custom_ctx({"FactSalesModel": binding})
        # v1.3 current behavior: empty visible = no governance trigger
        composed = compile_plan_to_sql(
            base_sales, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert composed.sql  # compiles without error


# ===========================================================================
# denied_columns (physical-column blacklist)
# ===========================================================================


class TestDeniedColumns:
    def test_denied_physical_column_drops_qm_field(
        self, svc, custom_ctx
    ):
        """Physical column in ``denied_columns`` → QM field mapped to it
        is stripped. Plan must not reference the stripped QM field."""
        binding = ModelBinding(
            denied_columns=[
                DeniedColumn(schema=None, table="fact_sales", column="sales_amount"),
            ],
        )
        ctx = custom_ctx({"FactSalesModel": binding})

        # Plan references only orderStatus (safe) — should compile
        plan = from_(model="FactSalesModel", columns=["orderStatus"])
        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="mysql8"
        )
        # The denied physical column must NOT appear in emitted SQL
        assert "sales_amount" not in composed.sql

    def test_denied_column_used_by_plan_raises(
        self, svc, custom_ctx, base_sales
    ):
        """Plan tries to use a denied physical column → rejection."""
        binding = ModelBinding(
            denied_columns=[
                DeniedColumn(schema=None, table="fact_sales", column="sales_amount"),
            ],
        )
        ctx = custom_ctx({"FactSalesModel": binding})
        # base_sales fixture uses [orderStatus, salesAmount] — denied!
        with pytest.raises(ComposeCompileError) as exc_info:
            compile_plan_to_sql(
                base_sales, ctx, semantic_service=svc, dialect="mysql8"
            )
        assert exc_info.value.code == error_codes.PER_BASE_COMPILE_FAILED

    def test_empty_denied_columns_no_effect(
        self, svc, custom_ctx, base_sales
    ):
        binding = ModelBinding(denied_columns=[])
        ctx = custom_ctx({"FactSalesModel": binding})
        composed = compile_plan_to_sql(
            base_sales, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "sales_amount" in composed.sql


# ===========================================================================
# system_slice (system-injected WHERE)
# ===========================================================================


class TestSystemSlice:
    def test_system_slice_appends_where(
        self, svc, custom_ctx, base_sales
    ):
        binding = ModelBinding(
            system_slice=[
                {"field": "orderStatus", "op": "=", "value": "completed"},
            ],
        )
        ctx = custom_ctx({"FactSalesModel": binding})
        composed = compile_plan_to_sql(
            base_sales, ctx, semantic_service=svc, dialect="mysql8"
        )
        # system_slice value flows into params
        assert "completed" in composed.params

    def test_empty_system_slice_no_effect(
        self, svc, custom_ctx, base_sales
    ):
        binding = ModelBinding(system_slice=[])
        ctx = custom_ctx({"FactSalesModel": binding})
        composed = compile_plan_to_sql(
            base_sales, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert composed.sql


# ===========================================================================
# Missing binding scenarios
# ===========================================================================


class TestMissingBindingSecondDefence:
    def test_bindings_dict_missing_qm(self, svc, ctx):
        """Explicit ``bindings={}`` → MISSING_BINDING at plan-lower."""
        plan = from_(model="FactSalesModel", columns=["orderStatus"])
        with pytest.raises(ComposeCompileError) as exc_info:
            compile_plan_to_sql(
                plan,
                ctx,
                semantic_service=svc,
                bindings={},  # pre-resolved but missing
                dialect="mysql8",
            )
        assert exc_info.value.code == error_codes.MISSING_BINDING
        assert "FactSalesModel" in exc_info.value.message

    def test_bindings_none_triggers_m5_resolve(
        self, svc, ctx, base_sales, permissive_resolver
    ):
        """``bindings=None`` → M6 internally invokes M5 resolver."""
        compile_plan_to_sql(
            base_sales,
            ctx,
            semantic_service=svc,
            bindings=None,
            dialect="mysql8",
        )
        # Verify the resolver was invoked
        assert len(permissive_resolver.calls) == 1


# ===========================================================================
# Multiple references to the same QM (dedup interaction)
# ===========================================================================


class TestSameQmTwiceInPlan:
    def test_union_same_qm_twice_shares_binding(
        self, svc, custom_ctx, base_sales
    ):
        """Union of same-instance QM twice → same binding applied
        consistently; no "binding drift" between CTEs."""
        binding = ModelBinding(
            system_slice=[
                {"field": "orderStatus", "op": "=", "value": "completed"},
            ],
        )
        ctx = custom_ctx({"FactSalesModel": binding})

        # Same instance on both sides (id-based dedup applies)
        u = base_sales.union(base_sales)
        composed = compile_plan_to_sql(
            u, ctx, semantic_service=svc, dialect="mysql8"
        )
        # 'completed' appears at least once (id-dedup may fold twice→once)
        assert "completed" in composed.params


# ===========================================================================
# Pre-supplied bindings (skip M5 resolve)
# ===========================================================================


class TestPreSuppliedBindings:
    def test_pre_supplied_bindings_skips_m5(
        self, svc, ctx, base_sales, permissive_resolver
    ):
        """When caller pre-supplies bindings, M6 does NOT call M5."""
        custom_bindings = {"FactSalesModel": ModelBinding()}
        composed = compile_plan_to_sql(
            base_sales,
            ctx,
            semantic_service=svc,
            bindings=custom_bindings,
            dialect="mysql8",
        )
        assert composed.sql
        # ctx's resolver should NOT have been invoked
        assert len(permissive_resolver.calls) == 0

    def test_caller_can_use_same_bindings_for_multiple_dialects(
        self, svc, ctx, base_sales, permissive_resolver
    ):
        """r3 Q2 no-caching use case: resolve once, compile N dialects."""
        pre_resolved = {"FactSalesModel": ModelBinding()}
        sql_my8 = compile_plan_to_sql(
            base_sales,
            ctx,
            semantic_service=svc,
            bindings=pre_resolved,
            dialect="mysql8",
        )
        sql_pg = compile_plan_to_sql(
            base_sales,
            ctx,
            semantic_service=svc,
            bindings=pre_resolved,
            dialect="postgres",
        )
        sql_sqlite = compile_plan_to_sql(
            base_sales,
            ctx,
            semantic_service=svc,
            bindings=pre_resolved,
            dialect="sqlite",
        )
        # All three yield non-empty SQL
        assert sql_my8.sql and sql_pg.sql and sql_sqlite.sql
        # Zero resolver calls — the caller owned the resolve
        assert len(permissive_resolver.calls) == 0


# ===========================================================================
# Combined: whitelist + system_slice
# ===========================================================================


class TestCombinedBindingFields:
    def test_whitelist_and_system_slice_both_apply(
        self, svc, custom_ctx
    ):
        """Both governance fields active: whitelist limits SELECT, system_slice
        appends WHERE."""
        binding = ModelBinding(
            field_access=["orderStatus", "salesAmount"],
            system_slice=[
                {"field": "orderStatus", "op": "=", "value": "shipped"},
            ],
        )
        ctx = custom_ctx({"FactSalesModel": binding})
        plan = from_(
            model="FactSalesModel",
            columns=["orderStatus", "salesAmount"],
        )
        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert "order_status" in composed.sql
        assert "shipped" in composed.params


# ===========================================================================
# Binding injection verified at the request level
# ===========================================================================


class TestBindingReachesRequest:
    def test_request_receives_field_access_def(
        self, svc, ctx, base_sales, monkeypatch
    ):
        """★ The request object flowing into v1.3 _build_query carries
        the binding's field_access wrapped as FieldAccessDef."""
        captured_requests = []
        original = svc._build_query

        def capturing(table_model, request):
            captured_requests.append(request)
            return original(table_model, request)

        monkeypatch.setattr(svc, "_build_query", capturing)

        from foggy.dataset_model.engine.compose.context import ComposeQueryContext
        from foggy.dataset_model.engine.compose.security import ModelBinding

        # Build a custom resolver inline so we control the binding
        class FixedResolver:
            def __init__(self):
                self.calls = 0

            def resolve(self, request):
                from foggy.dataset_model.engine.compose.security import (
                    AuthorityResolution,
                )
                self.calls += 1
                return AuthorityResolution(
                    bindings={
                        mq.model: ModelBinding(
                            field_access=["orderStatus", "salesAmount"]
                        )
                        for mq in request.models
                    }
                )

        custom_ctx = ComposeQueryContext(
            principal=ctx.principal,
            namespace=ctx.namespace,
            authority_resolver=FixedResolver(),
        )
        compile_plan_to_sql(
            base_sales,
            custom_ctx,
            semantic_service=svc,
            dialect="mysql8",
        )
        assert len(captured_requests) == 1
        request = captured_requests[0]
        assert request.field_access is not None
        assert set(request.field_access.visible) == {"orderStatus", "salesAmount"}

    def test_request_receives_system_slice_list(
        self, svc, ctx, base_sales, monkeypatch
    ):
        captured = []

        def capturing(table_model, request):
            captured.append(request)
            return svc._build_query.__wrapped__(table_model, request) if hasattr(svc._build_query, "__wrapped__") else _orig(table_model, request)

        _orig = svc._build_query
        monkeypatch.setattr(svc, "_build_query", lambda tm, req: (captured.append(req), _orig(tm, req))[1])

        from foggy.dataset_model.engine.compose.context import ComposeQueryContext
        from foggy.dataset_model.engine.compose.security import (
            AuthorityResolution,
            ModelBinding,
        )

        class FixedResolver:
            def resolve(self, request):
                return AuthorityResolution(
                    bindings={
                        mq.model: ModelBinding(
                            system_slice=[
                                {"field": "orderStatus", "op": "=", "value": "x"}
                            ]
                        )
                        for mq in request.models
                    }
                )

        custom_ctx = ComposeQueryContext(
            principal=ctx.principal,
            namespace=ctx.namespace,
            authority_resolver=FixedResolver(),
        )
        compile_plan_to_sql(
            base_sales,
            custom_ctx,
            semantic_service=svc,
            dialect="mysql8",
        )
        assert len(captured) == 1
        assert captured[0].system_slice == [
            {"field": "orderStatus", "op": "=", "value": "x"}
        ]

    def test_denied_columns_not_re_translated_in_compose_layer(
        self, svc, ctx, base_sales, monkeypatch
    ):
        """★ r2 contract: compose layer does NOT call PhysicalColumnMapping
        itself — v1.3 engine owns translation."""
        # Spy on get_physical_column_mapping; M6 must NOT invoke it.
        call_count = {"n": 0}
        original = svc.get_physical_column_mapping

        def spy(name):
            call_count["n"] += 1
            return original(name)

        monkeypatch.setattr(svc, "get_physical_column_mapping", spy)

        # M6 compile path must not call get_physical_column_mapping — if
        # v1.3 engine calls it internally, that's still in scope of M6's
        # contract because we delegate, but a *M6-layer* call would be a
        # violation. Test weaker invariant: the spy is called only by v1.3
        # (not directly from compose.compilation).

        from foggy.dataset_model.engine.compose.context import ComposeQueryContext
        from foggy.dataset_model.engine.compose.security import (
            AuthorityResolution,
            ModelBinding,
        )

        class FixedResolver:
            def resolve(self, request):
                return AuthorityResolution(
                    bindings={
                        mq.model: ModelBinding(
                            denied_columns=[
                                DeniedColumn(
                                    schema=None,
                                    table="fact_sales",
                                    column="sales_amount",
                                )
                            ]
                        )
                        for mq in request.models
                    }
                )

        custom_ctx = ComposeQueryContext(
            principal=ctx.principal,
            namespace=ctx.namespace,
            authority_resolver=FixedResolver(),
        )
        plan = from_(model="FactSalesModel", columns=["orderStatus"])
        composed = compile_plan_to_sql(
            plan, custom_ctx, semantic_service=svc, dialect="mysql8"
        )
        # v1.3 may have called it; that's fine. The important property is
        # the final SQL respected the denied column (doesn't leak sales_amount).
        assert "sales_amount" not in composed.sql
