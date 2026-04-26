"""FSScript sandbox E2E tests — verifies full pipeline:

    script text → parser → evaluator → QueryPlan AST → SQL compiler

These tests exercise the OO fluent API (`Query.from(...)`) through
the actual FSScript parser and evaluator, validating that the sandbox
globals, method dispatch (including dataclass field shadowing fix),
and compiler integration all work end-to-end.

.. versionadded:: 8.2.0.beta
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from foggy.dataset_model.engine.compose import ComposedSql
from foggy.dataset_model.engine.compose.context.compose_query_context import (
    ComposeQueryContext,
)
from foggy.dataset_model.engine.compose.context.principal import Principal
from foggy.dataset_model.engine.compose.plan import BaseModelPlan, DerivedQueryPlan
from foggy.dataset_model.engine.compose.plan.plan import JoinPlan, UnionPlan
from foggy.dataset_model.engine.compose.runtime import run_script
from foggy.dataset_model.engine.compose.security import (
    AuthorityResolution,
    ModelBinding,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _StubResolver:
    def resolve(self, request):
        return AuthorityResolution(
            bindings={mq.model: ModelBinding() for mq in request.models}
        )


class _StubSemanticService:
    def __init__(self, rows=None):
        self.rows = rows if rows is not None else [{"id": 1}]
        self.execute_calls: List = []

    def execute_sql(self, sql, params, *, route_model=None):
        self.execute_calls.append((sql, list(params), route_model))
        return list(self.rows)


def _ctx():
    return ComposeQueryContext(
        principal=Principal(user_id="u1"),
        namespace="default",
        authority_resolver=_StubResolver(),
    )


def _run(script: str):
    """Shorthand: run a script and return the result value."""
    return run_script(
        script, _ctx(), semantic_service=_StubSemanticService()
    )


# ---------------------------------------------------------------------------
# Query.from() entry point
# ---------------------------------------------------------------------------


class TestQueryFromEntryPoint:
    def test_query_from_creates_base_model_plan(self):
        r = _run('Query.from("SaleOrderQM")')
        assert isinstance(r.value, BaseModelPlan)
        assert r.value.model == "SaleOrderQM"
        assert r.value.columns == ()

    def test_query_from_rejects_empty_string(self):
        with pytest.raises(ValueError):
            _run('Query.from("")')


class TestJsKeywordAsAlias:
    """JS scripts (and the Java fluent API) call ``.as("alias")`` —
    Python's ``as`` is a reserved word so we expose the same method
    under ``as_`` and route ``.as`` to it via ``__getattr__``. These
    tests pin that behaviour so future refactors don't drop it.

    .. versionadded:: 8.2.0.beta (Phase B)
    """

    def test_field_ref_as_alias(self):
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales.partnerId.as("pid");
        ''')
        assert r.value.to_column_expr() == "partnerId AS pid"

    def test_aggregate_as_alias(self):
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales.amountTotal.sum().as("total");
        ''')
        assert r.value.to_column_expr() == "SUM(amountTotal) AS total"

    def test_aggregate_as_alias_with_caption(self):
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales.amountTotal.sum().as("total", "总金额");
        ''')
        assert r.value.to_column_expr() == "SUM(amountTotal)$总金额 AS total"

    def test_window_column_as_alias(self):
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales.rowNumber().over({orderBy: ["-date"]}).as("rn");
        ''')
        assert r.value.to_column_expr() == \
            "ROW_NUMBER() OVER (ORDER BY date DESC) AS rn"

    def test_projected_column_re_as_alias(self):
        """Re-aliasing a ``ProjectedColumn`` via ``.as("new_alias")`` is
        used by the ``union_scenario.js`` fixture to align column names
        across union branches."""
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales.amountTotal.sum().as("sales_amount").as("amount");
        ''')
        # The outer .as("amount") replaces the alias; the underlying
        # aggregate expression is preserved.
        assert r.value.to_column_expr() == "SUM(amountTotal) AS amount"


# ---------------------------------------------------------------------------
# Field references + aggregation
# ---------------------------------------------------------------------------


class TestFieldRefAndAggregation:
    def test_field_ref_sum(self):
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            sales.amountTotal.sum().as_("total");
        ''')
        assert r.value.to_column_expr() == "SUM(amountTotal) AS total"

    def test_field_ref_with_caption(self):
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            sales.amountTotal.sum().as_("total", "Total Amount");
        ''')
        assert r.value.to_column_expr() == "SUM(amountTotal)$Total Amount AS total"


# ---------------------------------------------------------------------------
# Full fluent chain: groupBy → select → orderBy → limit
# ---------------------------------------------------------------------------


class TestFluentChain:
    def test_two_stage_aggregation(self):
        """§3.1 canonical example — two-stage aggregation."""
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales
                .groupBy(sales.partnerId)
                .select(
                    sales.partnerId.as_("pid"),
                    sales.amountTotal.sum().as_("total")
                )
                .orderBy("-total")
                .limit(10);
        ''')
        plan = r.value
        assert isinstance(plan, DerivedQueryPlan)
        assert plan.limit == 10

    def test_where_then_select(self):
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales
                .where([{field: "state", op: "=", value: "done"}])
                .select(sales.partnerId, sales.amountTotal.as_("amount"));
        ''')
        plan = r.value
        assert isinstance(plan, DerivedQueryPlan)
        assert plan.columns == ("partnerId", "amountTotal AS amount")
        # where is on the intermediate stage
        assert plan.source.slice_ == ({"field": "state", "op": "=", "value": "done"},)

    def test_limit_and_offset_chaining(self):
        """Verifies the dataclass field shadowing fix works in real FSScript."""
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales
                .select(sales.id, sales.name)
                .orderBy("name")
                .limit(20)
                .offset(10);
        ''')
        plan = r.value
        assert isinstance(plan, DerivedQueryPlan)
        assert plan.start == 10
        # limit is on the parent stage
        assert plan.source.limit == 20


# ---------------------------------------------------------------------------
# JOIN
# ---------------------------------------------------------------------------


class TestFluentJoin:
    def test_left_join_with_compound_on(self):
        r = _run('''
            const customers = Query.from("ResPartnerQM");
            const orders = Query.from("SaleOrderQM");
            return customers
                .leftJoin(orders)
                .on(customers.id, orders.partnerId)
                .and_(customers.companyId, orders.companyId);
        ''')
        plan = r.value
        assert isinstance(plan, JoinPlan)
        assert plan.type == "left"
        assert len(plan.on) == 2
        assert plan.on[0].left == "id"
        assert plan.on[0].right == "partnerId"
        assert plan.on[1].left == "companyId"
        assert plan.on[1].right == "companyId"

    def test_inner_join_then_select(self):
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            const leads = Query.from("CrmLeadQM");
            const joined = sales
                .innerJoin(leads)
                .on(sales.partnerId, leads.partnerId);
            return joined.select(
                sales.partnerId.as_("pid"),
                sales.amountTotal.sum().as_("revenue"),
                leads.id.count().as_("leadCount")
            );
        ''')
        plan = r.value
        assert isinstance(plan, DerivedQueryPlan)
        assert "SUM(amountTotal) AS revenue" in plan.columns
        assert "COUNT(id) AS leadCount" in plan.columns


# ---------------------------------------------------------------------------
# UNION
# ---------------------------------------------------------------------------


class TestFluentUnion:
    def test_union_all(self):
        r = _run('''
            const current = Query.from("CurrentReceivableQM");
            const archived = Query.from("ArchivedReceivableQM");
            return current.union(archived, {all: true});
        ''')
        plan = r.value
        assert isinstance(plan, UnionPlan)
        assert plan.all is True


# ---------------------------------------------------------------------------
# Complex multi-step script
# ---------------------------------------------------------------------------


class TestComplexScript:
    def test_aggregate_first_join_later(self):
        """BI golden rule: aggregate first, join later."""
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            const leads = Query.from("CrmLeadQM");

            const salesAgg = sales
                .groupBy(sales.partnerId)
                .select(
                    sales.partnerId.as_("pid"),
                    sales.amountTotal.sum().as_("totalSales")
                );

            const leadsAgg = leads
                .groupBy(leads.partnerId)
                .select(
                    leads.partnerId.as_("pid"),
                    leads.id.count().as_("leadCount")
                );

            return salesAgg
                .leftJoin(leadsAgg)
                .on(salesAgg.pid, leadsAgg.pid);
        ''')
        plan = r.value
        assert isinstance(plan, JoinPlan)
        assert plan.type == "left"
        # Both sides are derived aggregations
        assert isinstance(plan.left, DerivedQueryPlan)
        assert isinstance(plan.right, DerivedQueryPlan)
        # 4 base models reachable (2 base + 2 derived)
        bases = plan.base_model_plans()
        assert {b.model for b in bases} == {"SaleOrderQM", "CrmLeadQM"}


# ---------------------------------------------------------------------------
# Window Functions (8.3.0.beta)
# ---------------------------------------------------------------------------


class TestWindowFunctions:
    def test_window_row_number(self):
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales.select(
                sales.rowNumber().over({orderBy: ["-date"]}).as_("rn")
            );
        ''')
        plan = r.value
        assert isinstance(plan, DerivedQueryPlan)
        assert plan.columns == ("ROW_NUMBER() OVER (ORDER BY date DESC) AS rn",)

    def test_window_lag_with_partition(self):
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales.select(
                sales.amountTotal.lag(1).over({
                    partitionBy: [sales.partnerId],
                    orderBy: ["date"]
                }).as_("prevAmount")
            );
        ''')
        plan = r.value
        assert plan.columns == ("LAG(amountTotal, 1) OVER (PARTITION BY partnerId ORDER BY date ASC) AS prevAmount",)

    def test_window_lag_default_offset(self):
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales.select(
                sales.amountTotal.lag().over({orderBy: ["date"]}).as_("prev")
            );
        ''')
        plan = r.value
        assert plan.columns == ("LAG(amountTotal, 1) OVER (ORDER BY date ASC) AS prev",)

    def test_window_lead_with_offset(self):
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales.select(
                sales.amountTotal.lead(2).over({orderBy: ["date"]}).as_("nextAmount")
            );
        ''')
        plan = r.value
        assert plan.columns == ("LEAD(amountTotal, 2) OVER (ORDER BY date ASC) AS nextAmount",)

    def test_window_lead_default_offset(self):
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales.select(
                sales.amountTotal.lead().over({orderBy: ["date"]}).as_("next")
            );
        ''')
        plan = r.value
        assert plan.columns == ("LEAD(amountTotal, 1) OVER (ORDER BY date ASC) AS next",)

    def test_window_rank(self):
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales.select(
                sales.rank().over({orderBy: ["-score"]}).as_("rnk")
            );
        ''')
        plan = r.value
        assert plan.columns == ("RANK() OVER (ORDER BY score DESC) AS rnk",)

    def test_window_dense_rank(self):
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales.select(
                sales.denseRank().over({
                    partitionBy: ["category"],
                    orderBy: ["-score"]
                }).as_("drnk")
            );
        ''')
        plan = r.value
        assert plan.columns == ("DENSE_RANK() OVER (PARTITION BY category ORDER BY score DESC) AS drnk",)

    def test_window_aggregate_over(self):
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales.select(
                sales.amountTotal.sum().over({
                    partitionBy: [sales.partnerId]
                }).as_("runningTotal")
            );
        ''')
        plan = r.value
        assert plan.columns == ("SUM(amountTotal) OVER (PARTITION BY partnerId) AS runningTotal",)

    def test_window_avg_over_both_partition_and_order(self):
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales.select(
                sales.price.avg().over({
                    partitionBy: ["category"],
                    orderBy: ["date", "-id"]
                }).as_("movingAvg")
            );
        ''')
        plan = r.value
        assert plan.columns == ("AVG(price) OVER (PARTITION BY category ORDER BY date ASC, id DESC) AS movingAvg",)

    def test_window_with_caption(self):
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales.select(
                sales.amountTotal.sum().over({
                    partitionBy: [sales.partnerId]
                }).as_("runTotal", "累计金额")
            );
        ''')
        plan = r.value
        assert plan.columns == ("SUM(amountTotal) OVER (PARTITION BY partnerId)$累计金额 AS runTotal",)

    def test_window_then_where_stage_cutoff(self):
        """Verifies window column feeds into next stage for filtering (阶段切断)."""
        r = _run('''
            const sales = Query.from("SaleOrderQM");
            return sales
                .select(
                    sales.partnerId.as_("pid"),
                    sales.rowNumber().over({
                        partitionBy: [sales.partnerId],
                        orderBy: ["-date"]
                    }).as_("rn")
                )
                .where([{field: "rn", op: "=", value: 1}]);
        ''')
        plan = r.value
        assert isinstance(plan, DerivedQueryPlan)
        # The where is on the outer stage
        assert plan.slice_ == ({"field": "rn", "op": "=", "value": 1},)
        # The window select is on the inner stage
        inner = plan.source
        assert any("ROW_NUMBER" in col for col in inner.columns)
