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

import pytest

from foggy.dataset_model.engine.compose import ComposedSql
from foggy.dataset_model.engine.compose.plan import (
    BaseModelPlan,
    DerivedQueryPlan,
    JoinPlan,
    UnionPlan,
)
from foggy.dataset_model.engine.compose.runtime import run_script
from foggy.dataset_model.engine.compose.runtime.script_runtime import (
    _run_script_no_intercept,
)


# ---------------------------------------------------------------------------
# Fixture loader — module-level cache so the three .js files are read
# exactly once per test process (each is ~1 KB).
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_FIXTURE_NAMES = (
    "union_scenario.js",
    "join_scenario.js",
    "derived_query_scenario.js",
)
_FIXTURES: dict[str, str] = {
    name: (_FIXTURES_DIR / name).read_text(encoding="utf-8")
    for name in _FIXTURE_NAMES
}


def _load(name: str) -> str:
    return _FIXTURES[name]


# ===========================================================================
# Scenario 1: union_scenario.js
# ===========================================================================


class TestUnionScenario:
    """Parity for ``union_scenario.js``:
    two ``groupBy`` aggregations unioned via ``UNION ALL``."""

    @pytest.fixture
    def envelope(self, compose_context, stub_semantic_service):
        return _run_script_no_intercept(
            _load("union_scenario.js"), compose_context,
            semantic_service=stub_semantic_service,
        )

    def test_envelope_structure(self, envelope):
        assert isinstance(envelope, dict)
        assert set(envelope.keys()) == {"plans", "metadata"}

    def test_plans_is_named_map_with_one_key(self, envelope):
        plans = envelope["plans"]
        assert isinstance(plans, dict)
        assert list(plans.keys()) == ["cashflow_overview"]

    def test_metadata_passes_through_unchanged(self, envelope):
        assert envelope["metadata"] == {"title": "本月销售与采购现金流对比"}

    def test_top_level_plan_is_union_all(self, envelope):
        plan = envelope["plans"]["cashflow_overview"]
        assert isinstance(plan, UnionPlan)
        assert plan.all is True  # `union(other, { all: true })`

    def test_union_branches_are_derived_aggregations(self, envelope):
        """Both branches are ``DerivedQueryPlan`` (the re-projection
        ``.select(sales.date, sales.sales_amount.as("amount"))`` /
        ``.select(purchases.date, purchases.purchase_amount.as("amount"))``
        wrapped around the underlying group-by chain)."""
        plan = envelope["plans"]["cashflow_overview"]
        assert isinstance(plan.left, DerivedQueryPlan)
        assert isinstance(plan.right, DerivedQueryPlan)

    def test_union_branches_reach_correct_base_models(self, envelope):
        """``base_model_plans`` returns left-preorder leaves — sales then
        purchases per the script order."""
        plan = envelope["plans"]["cashflow_overview"]
        bases = plan.base_model_plans()
        models = [b.model for b in bases]
        assert models == ["OdooSaleOrderModel", "OdooPurchaseOrderModel"]

    def test_union_branch_columns_aligned_to_amount_alias(self, envelope):
        """The script re-projects each branch to ``(date, amount)`` so
        the union has parallel column counts."""
        plan = envelope["plans"]["cashflow_overview"]
        assert len(plan.left.columns) == 2
        assert len(plan.right.columns) == 2
        assert any("amount" in c for c in plan.left.columns)
        assert any("amount" in c for c in plan.right.columns)


# ===========================================================================
# Scenario 2: join_scenario.js
# ===========================================================================


class TestJoinScenario:
    """Parity for ``join_scenario.js``:
    A-grade customers ``innerJoin`` pending sales orders + projection."""

    @pytest.fixture
    def envelope(self, compose_context, stub_semantic_service):
        return _run_script_no_intercept(
            _load("join_scenario.js"), compose_context,
            semantic_service=stub_semantic_service,
        )

    def test_envelope_structure(self, envelope):
        assert isinstance(envelope, dict)
        assert set(envelope.keys()) == {"plans", "metadata"}

    def test_plans_named_anomaly_list(self, envelope):
        assert list(envelope["plans"].keys()) == ["anomaly_list"]

    def test_metadata_title(self, envelope):
        assert envelope["metadata"]["title"] == "A级客户逾期未发货清单"

    def test_top_level_is_derived_select_over_inner_join(self, envelope):
        """The script ends with ``joined.select(...)`` — a
        :class:`DerivedQueryPlan` whose ``source`` is the
        :class:`JoinPlan`."""
        plan = envelope["plans"]["anomaly_list"]
        assert isinstance(plan, DerivedQueryPlan)
        assert isinstance(plan.source, JoinPlan)

    def test_inner_join_type(self, envelope):
        plan = envelope["plans"]["anomaly_list"]
        assert plan.source.type == "inner"

    def test_join_on_condition_uses_partner_id(self, envelope):
        """``premiumCustomers.id`` joined to ``pendingOrders.partnerId``."""
        plan = envelope["plans"]["anomaly_list"]
        join = plan.source
        assert len(join.on) == 1
        cond = join.on[0]
        assert cond.left == "id"
        assert cond.op == "="
        assert cond.right == "partnerId"

    def test_join_left_branch_filters_a_grade_customers(self, envelope):
        """Left side derives from ``OdooResPartnerModel`` and applies a
        ``contains`` filter on ``category_id$caption``."""
        plan = envelope["plans"]["anomaly_list"]
        left = plan.source.left
        assert isinstance(left, DerivedQueryPlan)
        assert [b.model for b in left.base_model_plans()] == ["OdooResPartnerModel"]
        slice_repr = str(left)
        assert "category_id$caption" in slice_repr
        assert "A级" in slice_repr

    def test_join_right_branch_filters_pending_status(self, envelope):
        """Right side: ``OdooSaleOrderModel`` filtered by
        ``deliveryStatus = pending``."""
        plan = envelope["plans"]["anomaly_list"]
        right = plan.source.right
        assert isinstance(right, DerivedQueryPlan)
        assert [b.model for b in right.base_model_plans()] == ["OdooSaleOrderModel"]
        slice_repr = str(right)
        assert "deliveryStatus" in slice_repr
        assert "pending" in slice_repr

    def test_final_projection_has_three_aliased_columns(self, envelope):
        """``customer_name`` / ``order_number`` / ``order_amount``."""
        plan = envelope["plans"]["anomaly_list"]
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

    @pytest.fixture
    def envelope(self, compose_context, stub_semantic_service):
        return _run_script_no_intercept(
            _load("derived_query_scenario.js"), compose_context,
            semantic_service=stub_semantic_service,
        )

    def test_envelope_structure(self, envelope):
        assert isinstance(envelope, dict)
        assert set(envelope.keys()) == {"plans", "metadata"}

    def test_plans_named_high_value_departments(self, envelope):
        assert list(envelope["plans"].keys()) == ["high_value_departments"]

    def test_metadata_title(self, envelope):
        assert envelope["metadata"]["title"] == "高销量部门筛选"

    def test_top_level_is_derived_select(self, envelope):
        plan = envelope["plans"]["high_value_departments"]
        assert isinstance(plan, DerivedQueryPlan)

    def test_derived_chain_traces_back_to_sale_order(self, envelope):
        plan = envelope["plans"]["high_value_departments"]
        assert [b.model for b in plan.base_model_plans()] == ["OdooSaleOrderModel"]

    def test_total_sales_filter_carried_in_slice_stage(self, envelope):
        """``where([{ field: "total_sales", op: ">", value: 50000 }])``
        becomes a slice on an intermediate stage."""
        plan = envelope["plans"]["high_value_departments"]
        stringified = str(plan)
        assert "total_sales" in stringified
        assert "50000" in stringified

    def test_projection_includes_alias_back_references(self, envelope):
        """The script projects ``deptSales.teamId$caption /
        total_sales / order_count`` — alias-back references on the prior
        stage's output."""
        plan = envelope["plans"]["high_value_departments"]
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

    def test_union_scenario_preview_replaces_plan_with_composed_sql(
        self, compose_context, stub_semantic_service, fake_compile_plan,
    ):
        result = run_script(
            _load("union_scenario.js"), compose_context,
            semantic_service=stub_semantic_service, preview_mode=True,
        )
        envelope = result.value
        assert isinstance(envelope, dict)
        assert "plans" in envelope
        assert "metadata" in envelope
        plans = envelope["plans"]
        assert isinstance(plans, dict)
        assert isinstance(plans["cashflow_overview"], ComposedSql)
        assert envelope["metadata"]["title"] == "本月销售与采购现金流对比"
        # Compiler invoked once for the top union plan; sub-trees flow
        # inside ``compile_plan_to_sql``.
        assert len(fake_compile_plan) == 1

    def test_join_scenario_preview_replaces_plan_with_composed_sql(
        self, compose_context, stub_semantic_service, fake_compile_plan,
    ):
        result = run_script(
            _load("join_scenario.js"), compose_context,
            semantic_service=stub_semantic_service, preview_mode=True,
        )
        envelope = result.value
        assert isinstance(envelope["plans"]["anomaly_list"], ComposedSql)
        assert envelope["metadata"]["title"] == "A级客户逾期未发货清单"

    def test_derived_scenario_preview_replaces_plan_with_composed_sql(
        self, compose_context, stub_semantic_service, fake_compile_plan,
    ):
        result = run_script(
            _load("derived_query_scenario.js"), compose_context,
            semantic_service=stub_semantic_service, preview_mode=True,
        )
        envelope = result.value
        assert isinstance(
            envelope["plans"]["high_value_departments"], ComposedSql,
        )
        assert envelope["metadata"]["title"] == "高销量部门筛选"

    def test_preview_mode_skips_execute_sql(
        self, compose_context, stub_semantic_service, fake_compile_plan,
    ):
        """Preview mode MUST NOT trigger ``execute_sql`` — that's the
        point of "show me the SQL without hitting the database"."""
        run_script(
            _load("union_scenario.js"), compose_context,
            semantic_service=stub_semantic_service, preview_mode=True,
        )
        assert stub_semantic_service.execute_calls == []


# ===========================================================================
# End-to-end through ``run_script`` + plans interceptor (execute mode)
# ===========================================================================


class TestExecuteModeInterception:
    """When ``run_script(..., preview_mode=False)`` (the default) is
    called against the JS fixtures, each plan inside ``plans`` MUST be
    replaced by the row list from the stub ``execute_sql``."""

    def test_execute_mode_replaces_plan_with_rows(
        self, compose_context, stub_semantic_service, fake_compile_plan,
    ):
        result = run_script(
            _load("union_scenario.js"), compose_context,
            semantic_service=stub_semantic_service, preview_mode=False,
        )
        envelope = result.value
        assert envelope["plans"]["cashflow_overview"] == [{"sentinel": "row"}]
        assert len(stub_semantic_service.execute_calls) == 1


# ===========================================================================
# Direct fsscript-level checks — confirm the JS-keyword `as(...)` alias
# works for all three fixtures (without invoking compile / execute).
# ===========================================================================


class TestJsKeywordAliasWorksOnAllFixtures:
    """Smoke test: every fixture parses + evaluates without raising
    ``"Unknown method 'as'"`` — i.e. the ``as`` → ``as_`` JS-keyword
    alias added on PlanColumnRef / AggregateColumn / ProjectedColumn /
    WindowColumn covers the cases the JS fixtures actually use."""

    @pytest.mark.parametrize("fixture", _FIXTURE_NAMES)
    def test_fixture_parses_and_evaluates(
        self, fixture, compose_context, stub_semantic_service,
    ):
        result = _run_script_no_intercept(
            _load(fixture), compose_context,
            semantic_service=stub_semantic_service,
        )
        assert isinstance(result, dict)
        assert "plans" in result
