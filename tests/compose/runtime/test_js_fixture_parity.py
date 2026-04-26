"""Cross-engine parity tests: the same JS fixtures used by the Java
``ScriptRuntimeTest`` are evaluated through the Python FSScript engine
and the resulting :class:`QueryPlan` AST + ``{ plans, metadata }``
envelope are asserted to match Java's expected shape.

The fixtures live at ``tests/compose/runtime/fixtures/`` and are
byte-for-byte identical to the Java test resources at
``foggy-dataset-model/src/test/resources/scripts/``. Whenever the Java
fixtures change, copy them here verbatim — that is the parity contract.

Three scenarios are covered:

* ``union_scenario.js`` — two ``Query.from(...)`` aggregations unioned
  together (``UNION ALL``).
* ``join_scenario.js`` — A-grade customers ``innerJoin`` pending sales
  orders, with a final projection.
* ``derived_query_scenario.js`` — group-by aggregation followed by a
  derived ``where`` filter on the alias-projected output.

What we assert
--------------
1. **Parse + evaluate succeeds** through Python FSScript with the same
   OO chained syntax (``Query.from`` / ``.where`` / ``.select`` /
   ``.groupBy`` / ``.innerJoin`` / ``.on`` / ``.union`` / ``.as``).
2. **The envelope structure** matches the Java contract:
   ``{ "plans": <named map>, "metadata": <dict> }`` with the right keys.
3. **The plan AST shape** is structurally equivalent — model names,
   columns, slice, group_by, join_type, on conditions, union_all flag.
4. **Plans interception** correctly transforms each plan inside
   ``plans`` (dict / list / single forms) when ``run_script`` is invoked
   with ``preview_mode=True`` — every plan becomes a sentinel
   :class:`ComposedSql` produced by a monkeypatched compiler.
5. **The ``metadata`` field passes through unchanged**.

.. versionadded:: 8.2.0.beta (Phase B parity)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from foggy.dataset_model.engine.compose import ComposedSql
from foggy.dataset_model.engine.compose.context.compose_query_context import (
    ComposeQueryContext,
)
from foggy.dataset_model.engine.compose.context.principal import Principal
from foggy.dataset_model.engine.compose.plan import (
    BaseModelPlan,
    DerivedQueryPlan,
    JoinPlan,
    UnionPlan,
)
from foggy.dataset_model.engine.compose.runtime import (
    ComposeRuntimeBundle,
    run_script,
    set_bundle,
)
from foggy.dataset_model.engine.compose.runtime.script_runtime import (
    _compose_runtime,
    _from_dsl,
)
from foggy.dataset_model.engine.compose.plan.query_factory import (
    INSTANCE as _query_factory,
)
from foggy.dataset_model.engine.compose.security import (
    AuthorityResolution,
    ModelBinding,
)
from foggy.dataset_model.engine.compose.sandbox import scan_script_source
from foggy.fsscript.evaluator import ExpressionEvaluator
from foggy.fsscript.expressions.control_flow import ReturnException
from foggy.fsscript.parser import COMPOSE_QUERY_DIALECT, FsscriptParser


# ---------------------------------------------------------------------------
# Fixture loader — single source of truth for the JS files.
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    """Read a JS fixture by file name (relative to ``fixtures/``)."""
    return (_FIXTURES_DIR / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _StubResolver:
    """Authority resolver that grants every requested model an empty
    :class:`ModelBinding` — i.e., no governance restrictions, no denied
    columns. Sufficient for AST-shape parity tests."""

    def resolve(self, request):
        bindings = {
            mq.model: ModelBinding(
                field_access=None, denied_columns=[], system_slice=[],
            )
            for mq in request.models
        }
        return AuthorityResolution(bindings=bindings)


class _StubSemanticService:
    """Minimum surface for ``run_script`` + ``execute_sql`` round trips.

    The compile path is intercepted at the ``compile_plan_to_sql`` call
    via ``monkeypatch`` in the preview-mode test — this stub is only
    consulted by the bundle and (in execute mode) by the M6 / M7
    plumbing that we don't exercise here.
    """

    def __init__(self):
        self.execute_calls: List[tuple] = []

    def execute_sql(self, sql, params, *, route_model=None):
        self.execute_calls.append((sql, list(params), route_model))
        return [{"sentinel": "row"}]


def _make_ctx() -> ComposeQueryContext:
    return ComposeQueryContext(
        principal=Principal(user_id="u1"),
        namespace="default",
        authority_resolver=_StubResolver(),
    )


# ---------------------------------------------------------------------------
# Direct-evaluation helper — bypasses ``intercept_plans`` so AST tests
# can introspect the raw envelope returned by the script.
# ---------------------------------------------------------------------------


def _evaluate_raw(script: str) -> Any:
    """Parse + evaluate ``script`` and return the raw envelope value
    WITHOUT plans interception.

    The bundle is still active during evaluation (``QueryPlan.execute`` /
    ``.to_sql`` calls inside the script — none in our fixtures —
    would still find host infra). But the post-script
    :func:`intercept_plans` step is skipped, so we get the literal
    ``{ plans, metadata }`` dict the script returned, with each plan
    still as a :class:`QueryPlan` instance.
    """
    svc = _StubSemanticService()
    ctx = _make_ctx()
    bundle = ComposeRuntimeBundle(ctx=ctx, semantic_service=svc)
    token = set_bundle(bundle)
    try:
        scan_script_source(script)
        parser = FsscriptParser(script, dialect=COMPOSE_QUERY_DIALECT)
        program = parser.parse_program()
        evaluator = ExpressionEvaluator(
            context={}, module_loader=None, bean_registry=None,
        )
        evaluator.context["from"] = _from_dsl
        evaluator.context["dsl"] = _from_dsl
        evaluator.context["Query"] = _query_factory
        evaluator.context["params"] = {}
        try:
            return evaluator.evaluate(program)
        except ReturnException as ret:
            return getattr(ret, "value", None)
    finally:
        _compose_runtime.reset(token)


# ===========================================================================
# Scenario 1: union_scenario.js
# ===========================================================================


class TestUnionScenario:
    """Parity for ``union_scenario.js``:
    two ``groupBy`` aggregations unioned via ``UNION ALL``."""

    def test_envelope_structure(self):
        result = _evaluate_raw(_load("union_scenario.js"))
        assert isinstance(result, dict)
        assert set(result.keys()) == {"plans", "metadata"}

    def test_plans_is_named_map_with_one_key(self):
        result = _evaluate_raw(_load("union_scenario.js"))
        plans = result["plans"]
        assert isinstance(plans, dict)
        assert list(plans.keys()) == ["cashflow_overview"]

    def test_metadata_passes_through_unchanged(self):
        result = _evaluate_raw(_load("union_scenario.js"))
        assert result["metadata"] == {"title": "本月销售与采购现金流对比"}

    def test_top_level_plan_is_union_all(self):
        result = _evaluate_raw(_load("union_scenario.js"))
        plan = result["plans"]["cashflow_overview"]
        assert isinstance(plan, UnionPlan)
        assert plan.all is True  # `union(other, { all: true })`

    def test_union_branches_are_derived_aggregations(self):
        """Both branches are ``DerivedQueryPlan`` (the re-projection
        ``.select(sales.date, sales.sales_amount.as("amount"))`` /
        ``.select(purchases.date, purchases.purchase_amount.as("amount"))``
        wrapped around the underlying group-by chain)."""
        result = _evaluate_raw(_load("union_scenario.js"))
        plan = result["plans"]["cashflow_overview"]
        assert isinstance(plan.left, DerivedQueryPlan)
        assert isinstance(plan.right, DerivedQueryPlan)

    def test_union_branches_reach_correct_base_models(self):
        """``base_model_plans`` returns left-preorder leaves — sales then
        purchases per the script order."""
        result = _evaluate_raw(_load("union_scenario.js"))
        plan = result["plans"]["cashflow_overview"]
        bases = plan.base_model_plans()
        models = [b.model for b in bases]
        assert models == ["OdooSaleOrderModel", "OdooPurchaseOrderModel"]

    def test_union_branch_columns_aligned_to_amount_alias(self):
        """The script re-projects each branch to ``(date, amount)`` so
        the union has parallel column counts."""
        result = _evaluate_raw(_load("union_scenario.js"))
        plan = result["plans"]["cashflow_overview"]
        assert len(plan.left.columns) == 2
        assert len(plan.right.columns) == 2
        # Left branch: sales_amount aliased to amount
        assert any("amount" in c for c in plan.left.columns)
        assert any("amount" in c for c in plan.right.columns)


# ===========================================================================
# Scenario 2: join_scenario.js
# ===========================================================================


class TestJoinScenario:
    """Parity for ``join_scenario.js``:
    A-grade customers ``innerJoin`` pending sales orders + projection."""

    def test_envelope_structure(self):
        result = _evaluate_raw(_load("join_scenario.js"))
        assert isinstance(result, dict)
        assert set(result.keys()) == {"plans", "metadata"}

    def test_plans_named_anomaly_list(self):
        result = _evaluate_raw(_load("join_scenario.js"))
        assert list(result["plans"].keys()) == ["anomaly_list"]

    def test_metadata_title(self):
        result = _evaluate_raw(_load("join_scenario.js"))
        assert result["metadata"]["title"] == "A级客户逾期未发货清单"

    def test_top_level_is_derived_select_over_inner_join(self):
        """The script ends with ``joined.select(...)`` — i.e. a
        :class:`DerivedQueryPlan` whose ``source`` is the
        :class:`JoinPlan`."""
        result = _evaluate_raw(_load("join_scenario.js"))
        plan = result["plans"]["anomaly_list"]
        assert isinstance(plan, DerivedQueryPlan)
        assert isinstance(plan.source, JoinPlan)

    def test_inner_join_type(self):
        result = _evaluate_raw(_load("join_scenario.js"))
        plan = result["plans"]["anomaly_list"]
        join = plan.source
        assert join.type == "inner"

    def test_join_on_condition_uses_partner_id(self):
        """``premiumCustomers.id`` joined to ``pendingOrders.partnerId``."""
        result = _evaluate_raw(_load("join_scenario.js"))
        plan = result["plans"]["anomaly_list"]
        join = plan.source
        assert len(join.on) == 1
        cond = join.on[0]
        assert cond.left == "id"
        assert cond.op == "="
        assert cond.right == "partnerId"

    def test_join_left_branch_filters_a_grade_customers(self):
        """Left side derives from ``OdooResPartnerModel`` and applies a
        ``contains`` filter on ``category_id$caption``."""
        result = _evaluate_raw(_load("join_scenario.js"))
        plan = result["plans"]["anomaly_list"]
        join = plan.source
        # Walk through the left side: select(...) wraps where(...) wraps base
        left = join.left
        assert isinstance(left, DerivedQueryPlan)
        # Underlying base
        bases = left.base_model_plans()
        assert [b.model for b in bases] == ["OdooResPartnerModel"]
        # Slice was carried by the intermediate where() stage
        slice_repr = str(left)
        assert "category_id$caption" in slice_repr
        assert "A级" in slice_repr

    def test_join_right_branch_filters_pending_status(self):
        """Right side: ``OdooSaleOrderModel`` filtered by
        ``deliveryStatus = pending``."""
        result = _evaluate_raw(_load("join_scenario.js"))
        plan = result["plans"]["anomaly_list"]
        join = plan.source
        right = join.right
        assert isinstance(right, DerivedQueryPlan)
        bases = right.base_model_plans()
        assert [b.model for b in bases] == ["OdooSaleOrderModel"]
        slice_repr = str(right)
        assert "deliveryStatus" in slice_repr
        assert "pending" in slice_repr

    def test_final_projection_has_three_aliased_columns(self):
        """``customer_name`` / ``order_number`` / ``order_amount``."""
        result = _evaluate_raw(_load("join_scenario.js"))
        plan = result["plans"]["anomaly_list"]
        # Each select arg becomes a column expression "<base> AS <alias>"
        cols = list(plan.columns)
        assert len(cols) == 3
        joined = " ".join(cols)
        assert "AS customer_name" in joined
        assert "AS order_number" in joined
        assert "AS order_amount" in joined


# ===========================================================================
# Scenario 3: derived_query_scenario.js
# ===========================================================================


class TestDerivedQueryScenario:
    """Parity for ``derived_query_scenario.js``:
    group-by aggregation, then a derived ``where`` on the aggregate's
    alias-projected output."""

    def test_envelope_structure(self):
        result = _evaluate_raw(_load("derived_query_scenario.js"))
        assert isinstance(result, dict)
        assert set(result.keys()) == {"plans", "metadata"}

    def test_plans_named_high_value_departments(self):
        result = _evaluate_raw(_load("derived_query_scenario.js"))
        assert list(result["plans"].keys()) == ["high_value_departments"]

    def test_metadata_title(self):
        result = _evaluate_raw(_load("derived_query_scenario.js"))
        assert result["metadata"]["title"] == "高销量部门筛选"

    def test_top_level_is_derived_select(self):
        result = _evaluate_raw(_load("derived_query_scenario.js"))
        plan = result["plans"]["high_value_departments"]
        assert isinstance(plan, DerivedQueryPlan)

    def test_derived_chain_traces_back_to_sale_order(self):
        result = _evaluate_raw(_load("derived_query_scenario.js"))
        plan = result["plans"]["high_value_departments"]
        bases = plan.base_model_plans()
        assert [b.model for b in bases] == ["OdooSaleOrderModel"]

    def test_total_sales_filter_carried_in_slice_stage(self):
        """``where([{ field: "total_sales", op: ">", value: 50000 }])``
        becomes a slice on an intermediate stage."""
        result = _evaluate_raw(_load("derived_query_scenario.js"))
        plan = result["plans"]["high_value_departments"]
        stringified = str(plan)
        assert "total_sales" in stringified
        assert "50000" in stringified

    def test_projection_includes_alias_back_references(self):
        """The script projects ``deptSales.teamId$caption /
        total_sales / order_count`` — these are alias-back references
        on the prior stage's output."""
        result = _evaluate_raw(_load("derived_query_scenario.js"))
        plan = result["plans"]["high_value_departments"]
        cols = " ".join(plan.columns)
        assert "teamId$caption" in cols
        assert "total_sales" in cols
        assert "order_count" in cols


# ===========================================================================
# End-to-end through ``run_script`` + plans interceptor (preview mode)
# ===========================================================================


class TestPreviewModeInterception:
    """When ``run_script(..., preview_mode=True)`` is called against the
    JS fixtures, the plans interceptor MUST replace each plan inside the
    ``plans`` map with the :class:`ComposedSql` returned by the
    compiler."""

    @pytest.fixture
    def fake_compile(self, monkeypatch):
        """Patch ``compile_plan_to_sql`` to return a sentinel
        :class:`ComposedSql` so we don't need the v1.3 SQL build wired
        up. Returns the captured-plans list so tests can assert that
        every plan inside ``plans`` was put through the compiler."""
        captured: List[Any] = []

        def _fake(plan, ctx, *, semantic_service, bindings=None,
                 model_info_provider=None, dialect="mysql"):
            captured.append(plan)
            return ComposedSql(
                sql=f"-- preview for {type(plan).__name__}\nSELECT 1",
                params=[],
            )

        monkeypatch.setattr(
            "foggy.dataset_model.engine.compose.compilation.compiler"
            ".compile_plan_to_sql",
            _fake,
        )
        return captured

    def test_union_scenario_preview_replaces_plan_with_composed_sql(
        self, fake_compile,
    ):
        ctx = _make_ctx()
        svc = _StubSemanticService()
        result = run_script(
            _load("union_scenario.js"), ctx,
            semantic_service=svc, preview_mode=True,
        )
        envelope = result.value
        assert isinstance(envelope, dict)
        assert "plans" in envelope
        assert "metadata" in envelope
        # Plans are now ComposedSql objects (preview), not QueryPlans.
        plans = envelope["plans"]
        assert isinstance(plans, dict)
        assert isinstance(plans["cashflow_overview"], ComposedSql)
        # Metadata passes through.
        assert envelope["metadata"]["title"] == "本月销售与采购现金流对比"
        # The compiler was actually invoked exactly once for the top
        # union plan (compile is per top-level plan, sub-trees flow
        # inside ``compile_plan_to_sql``).
        assert len(fake_compile) == 1

    def test_join_scenario_preview_replaces_plan_with_composed_sql(
        self, fake_compile,
    ):
        ctx = _make_ctx()
        svc = _StubSemanticService()
        result = run_script(
            _load("join_scenario.js"), ctx,
            semantic_service=svc, preview_mode=True,
        )
        envelope = result.value
        assert isinstance(envelope["plans"]["anomaly_list"], ComposedSql)
        assert envelope["metadata"]["title"] == "A级客户逾期未发货清单"

    def test_derived_scenario_preview_replaces_plan_with_composed_sql(
        self, fake_compile,
    ):
        ctx = _make_ctx()
        svc = _StubSemanticService()
        result = run_script(
            _load("derived_query_scenario.js"), ctx,
            semantic_service=svc, preview_mode=True,
        )
        envelope = result.value
        assert isinstance(
            envelope["plans"]["high_value_departments"], ComposedSql,
        )
        assert envelope["metadata"]["title"] == "高销量部门筛选"

    def test_preview_mode_skips_execute_sql(self, fake_compile):
        """Preview mode MUST NOT trigger ``execute_sql`` on the semantic
        service — the whole point is "show me the SQL without hitting
        the database"."""
        ctx = _make_ctx()
        svc = _StubSemanticService()
        run_script(
            _load("union_scenario.js"), ctx,
            semantic_service=svc, preview_mode=True,
        )
        assert svc.execute_calls == []


# ===========================================================================
# End-to-end through ``run_script`` + plans interceptor (execute mode)
# ===========================================================================


class TestExecuteModeInterception:
    """When ``run_script(..., preview_mode=False)`` (the default) is
    called against the JS fixtures, each plan inside ``plans`` MUST be
    replaced by the row list from the stub ``execute_sql``."""

    @pytest.fixture
    def fake_compile(self, monkeypatch):
        """Patch the compiler to return sentinel SQL — same fixture as
        preview mode, but here we expect ``execute_sql`` to be called
        downstream.

        Note we patch in TWO places:

        * ``compilation.compiler.compile_plan_to_sql`` — used by
          ``QueryPlan.to_sql`` (re-imported on every call).
        * ``runtime.plan_execution.compile_plan_to_sql`` —
          ``plan_execution`` does ``from ..compilation.compiler import
          compile_plan_to_sql`` at module import time, so patching the
          source module alone doesn't reach this binding.
        """
        def _fake(plan, ctx, *, semantic_service, bindings=None,
                 model_info_provider=None, dialect="mysql"):
            return ComposedSql(
                sql=f"-- exec for {type(plan).__name__}",
                params=[],
            )

        monkeypatch.setattr(
            "foggy.dataset_model.engine.compose.compilation.compiler"
            ".compile_plan_to_sql",
            _fake,
        )
        monkeypatch.setattr(
            "foggy.dataset_model.engine.compose.runtime.plan_execution"
            ".compile_plan_to_sql",
            _fake,
        )

    def test_execute_mode_replaces_plan_with_rows(self, fake_compile):
        ctx = _make_ctx()
        svc = _StubSemanticService()
        result = run_script(
            _load("union_scenario.js"), ctx,
            semantic_service=svc, preview_mode=False,
        )
        envelope = result.value
        assert envelope["plans"]["cashflow_overview"] == [{"sentinel": "row"}]
        # The execute path was actually invoked.
        assert len(svc.execute_calls) == 1


# ===========================================================================
# Direct fsscript-level checks — confirm the JS-keyword `as(...)` alias
# works for all three fixtures (without invoking compile / execute).
# ===========================================================================


class TestJsKeywordAliasWorksOnAllFixtures:
    """Smoke test: every fixture parses + evaluates without raising
    ``"Unknown method 'as'"`` — i.e. the ``as`` → ``as_`` JS-keyword
    alias added on PlanColumnRef / AggregateColumn / ProjectedColumn /
    WindowColumn covers the cases the JS fixtures actually use."""

    @pytest.mark.parametrize(
        "fixture",
        ["union_scenario.js", "join_scenario.js", "derived_query_scenario.js"],
    )
    def test_fixture_parses_and_evaluates(self, fixture):
        # Just confirm no AttributeError / RuntimeError leaks out of the
        # raw evaluator; deeper assertions live in the per-scenario
        # classes above.
        result = _evaluate_raw(_load(fixture))
        assert isinstance(result, dict)
        assert "plans" in result
