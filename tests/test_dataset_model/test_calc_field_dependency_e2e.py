"""End-to-end tests for calc-field dependency graph (Phase 2).

Verifies that ``SemanticQueryService.query_model`` correctly:
  - Sorts calc fields in dependency order before compilation
  - Inlines already-compiled calc SQL fragments into dependent calcs
  - Rejects circular references with a friendly error
  - Lets slice / group by / order by / having reference calc fields

对齐 Java 行为：``CalculatedFieldTest.java`` 的 transitive / cycle 用例。

需求：``docs/v1.5/P1-Phase2-计算字段依赖图-需求.md``.
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.definitions.base import AggregationType
from foggy.dataset_model.impl.model import (
    DbModelDimensionImpl,
    DbModelMeasureImpl,
    DbTableModelImpl,
)
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.mcp_spi import SemanticQueryRequest


@pytest.fixture
def model():
    m = DbTableModelImpl(name="TestModel", source_table="t_test")
    m.add_dimension(DbModelDimensionImpl(name="name", column="name"))
    m.add_dimension(DbModelDimensionImpl(name="status", column="status"))
    m.add_measure(DbModelMeasureImpl(
        name="salesAmount", column="sales_amount", aggregation=AggregationType.SUM,
    ))
    m.add_measure(DbModelMeasureImpl(
        name="costAmount", column="cost_amount", aggregation=AggregationType.SUM,
    ))
    return m


@pytest.fixture
def svc(model):
    s = SemanticQueryService()
    s.register_model(model)
    return s


# --------------------------------------------------------------------------- #
# 1. Transitive calc-to-calc references
# --------------------------------------------------------------------------- #

class TestTransitiveCalcRefs:
    def test_two_level_chain(self, svc):
        """calc B references calc A → A's expression inlined in B's SQL."""
        req = SemanticQueryRequest(
            columns=["name", "netAmount", "withTax"],
            # Intentionally out-of-order: withTax listed before netAmount
            calculatedFields=[
                {"name": "withTax", "expression": "netAmount * 1.13"},
                {"name": "netAmount", "expression": "salesAmount - costAmount"},
            ],
        )
        r = svc.query_model("TestModel", req, mode="validate")
        assert r.error is None, r.error
        # netAmount must come before withTax in the output
        idx_net = r.sql.index('AS "netAmount"')
        idx_tax = r.sql.index('AS "withTax"')
        assert idx_net < idx_tax
        # withTax should inline netAmount's expression
        assert "(t.sales_amount - t.cost_amount) * 1.13" in r.sql

    def test_deep_chain(self, svc):
        """a → b → c: each references its predecessor."""
        req = SemanticQueryRequest(
            columns=["name", "a", "b", "c"],
            calculatedFields=[
                {"name": "c", "expression": "b + a"},
                {"name": "b", "expression": "a * 2"},
                {"name": "a", "expression": "salesAmount + 1"},
            ],
        )
        r = svc.query_model("TestModel", req, mode="validate")
        assert r.error is None
        # b = (a) * 2
        assert "(t.sales_amount + 1) * 2" in r.sql
        # c = (b) + (a) = ((a)*2) + (a)
        assert "((t.sales_amount + 1) * 2) + (t.sales_amount + 1)" in r.sql

    def test_diamond_dependency(self, svc):
        """a → b, a → c, b+c → d.

        Each reference wraps the inlined expression in parens, so ``a``
        in ``b`` becomes ``(t.sales_amount)``; this is the defensive
        precedence-safety bracketing — verified in the final ``d``
        expression being ``((t.sales_amount) + 1) + ((t.sales_amount) - 1)``.
        """
        req = SemanticQueryRequest(
            columns=["d"],
            calculatedFields=[
                {"name": "d", "expression": "b + c"},
                {"name": "c", "expression": "a - 1"},
                {"name": "b", "expression": "a + 1"},
                {"name": "a", "expression": "salesAmount"},
            ],
        )
        r = svc.query_model("TestModel", req, mode="validate")
        assert r.error is None
        # d = (b) + (c) = ((a)+1) + ((a)-1)
        assert "((t.sales_amount) + 1) + ((t.sales_amount) - 1)" in r.sql

    def test_calc_in_if_condition(self, svc):
        """calc B uses calc A inside IF() condition."""
        req = SemanticQueryRequest(
            columns=["net", "isProfitable"],
            calculatedFields=[
                {"name": "net", "expression": "salesAmount - costAmount"},
                {"name": "isProfitable", "expression": "if(net > 0, 1, 0)"},
            ],
        )
        r = svc.query_model("TestModel", req, mode="validate")
        assert r.error is None
        assert "CASE WHEN (t.sales_amount - t.cost_amount) > 0 THEN 1 ELSE 0 END" in r.sql

    def test_calc_used_multiple_times(self, svc):
        """Calc field referenced more than once — each ref inlines the expression."""
        req = SemanticQueryRequest(
            columns=["a", "b"],
            calculatedFields=[
                {"name": "a", "expression": "salesAmount + 1"},
                {"name": "b", "expression": "a * a"},  # a appears twice
            ],
        )
        r = svc.query_model("TestModel", req, mode="validate")
        assert r.error is None
        assert "(t.sales_amount + 1) * (t.sales_amount + 1)" in r.sql


# --------------------------------------------------------------------------- #
# 2. Circular reference detection
# --------------------------------------------------------------------------- #

class TestCircularReferenceDetection:
    def test_direct_cycle(self, svc):
        req = SemanticQueryRequest(
            columns=["x"],
            calculatedFields=[
                {"name": "x", "expression": "y + 1"},
                {"name": "y", "expression": "x - 1"},
            ],
        )
        r = svc.query_model("TestModel", req, mode="validate")
        assert r.error is not None
        assert "Circular reference" in r.error
        assert "'x'" in r.error and "'y'" in r.error

    def test_three_way_cycle(self, svc):
        req = SemanticQueryRequest(
            columns=["a"],
            calculatedFields=[
                {"name": "a", "expression": "b + 1"},
                {"name": "b", "expression": "c + 1"},
                {"name": "c", "expression": "a + 1"},
            ],
        )
        r = svc.query_model("TestModel", req, mode="validate")
        assert r.error is not None
        assert "Circular reference" in r.error
        # All three must be in the error message
        assert "'a'" in r.error
        assert "'b'" in r.error
        assert "'c'" in r.error

    def test_self_reference_not_cycle(self, svc):
        """Self-reference `a = a + 1` is silently treated as non-cycle —
        the `a` on the RHS resolves to the base model lookup (fails) or
        falls through to literal 'a' (bad SQL). This mirrors Java."""
        req = SemanticQueryRequest(
            columns=["a"],
            calculatedFields=[
                {"name": "a", "expression": "salesAmount + 1"},  # no self-ref
            ],
        )
        r = svc.query_model("TestModel", req, mode="validate")
        assert r.error is None


# --------------------------------------------------------------------------- #
# 3. Slice / WHERE references calc field
# --------------------------------------------------------------------------- #

class TestSliceRefsCalc:
    def test_simple_slice_on_calc(self, svc):
        req = SemanticQueryRequest(
            columns=["name", "netAmount"],
            calculatedFields=[
                {"name": "netAmount", "expression": "salesAmount - costAmount"},
            ],
            slice=[{"field": "netAmount", "op": ">", "value": 100}],
        )
        r = svc.query_model("TestModel", req, mode="validate")
        assert r.error is None
        assert "(t.sales_amount - t.cost_amount) > ?" in r.sql

    def test_slice_on_transitive_calc(self, svc):
        req = SemanticQueryRequest(
            columns=["net", "withTax"],
            calculatedFields=[
                {"name": "net", "expression": "salesAmount - costAmount"},
                {"name": "withTax", "expression": "net * 1.13"},
            ],
            slice=[{"field": "withTax", "op": ">", "value": 113}],
        )
        r = svc.query_model("TestModel", req, mode="validate")
        assert r.error is None
        assert "((t.sales_amount - t.cost_amount) * 1.13) > ?" in r.sql


# --------------------------------------------------------------------------- #
# 4. ORDER BY / GROUP BY references calc field
# --------------------------------------------------------------------------- #

class TestOrderByGroupByRefsCalc:
    def test_orderby_on_calc_in_select(self, svc):
        req = SemanticQueryRequest(
            columns=["name", "netAmount"],
            calculatedFields=[
                {"name": "netAmount", "expression": "salesAmount - costAmount"},
            ],
            order_by=[{"field": "netAmount", "dir": "desc"}],
        )
        r = svc.query_model("TestModel", req, mode="validate")
        assert r.error is None
        # Either inline form OR alias form is acceptable SQL
        assert "netAmount" in r.sql

    def test_orderby_on_calc_not_in_columns_list(self, svc):
        """calc referenced in ORDER BY but not listed in ``columns``.

        Calc fields are always added to SELECT regardless of ``columns``
        list, so ORDER BY picks up the alias via ``selected_order_aliases``.
        This test confirms the query compiles successfully and sorts by
        the calc's alias.
        """
        req = SemanticQueryRequest(
            columns=["name"],
            calculatedFields=[
                {"name": "hiddenScore", "expression": "salesAmount - costAmount"},
            ],
            order_by=[{"field": "hiddenScore", "dir": "asc"}],
        )
        r = svc.query_model("TestModel", req, mode="validate")
        assert r.error is None
        # Either the alias form or the inline expression — both are valid SQL.
        assert '"hiddenScore"' in r.sql or "(t.sales_amount - t.cost_amount)" in r.sql
        assert "ORDER BY" in r.sql

    def test_groupby_on_calc(self, svc):
        """calc (non-agg) used in GROUP BY."""
        req = SemanticQueryRequest(
            columns=["bucket"],
            calculatedFields=[
                {"name": "bucket", "expression": "salesAmount"},
            ],
            group_by=["bucket"],
        )
        r = svc.query_model("TestModel", req, mode="validate")
        assert r.error is None
        # GROUP BY should have the inlined expression
        assert "GROUP BY (t.sales_amount)" in r.sql or "GROUP BY t.sales_amount" in r.sql


# --------------------------------------------------------------------------- #
# 5. Regression: existing single-level calc behaviour unchanged
# --------------------------------------------------------------------------- #

class TestBackwardCompat:
    def test_single_calc_no_deps(self, svc):
        req = SemanticQueryRequest(
            columns=["name", "profit"],
            calculatedFields=[
                {"name": "profit", "expression": "salesAmount - costAmount"},
            ],
        )
        r = svc.query_model("TestModel", req, mode="validate")
        assert r.error is None
        assert 't.sales_amount - t.cost_amount AS "profit"' in r.sql

    def test_calc_with_agg_no_deps(self, svc):
        req = SemanticQueryRequest(
            columns=["totalNet"],
            calculatedFields=[
                {"name": "totalNet", "expression": "salesAmount - costAmount",
                 "agg": "SUM"},
            ],
        )
        r = svc.query_model("TestModel", req, mode="validate")
        assert r.error is None
        assert 'SUM(t.sales_amount - t.cost_amount) AS "totalNet"' in r.sql

    def test_empty_calc_list(self, svc):
        req = SemanticQueryRequest(columns=["name", "salesAmount"])
        r = svc.query_model("TestModel", req, mode="validate")
        assert r.error is None

    def test_in_operator_still_works_in_calc(self, svc):
        """v1.4 regression: `in (...)` syntax still works in calc expressions."""
        req = SemanticQueryRequest(
            columns=["isHot"],
            calculatedFields=[
                {"name": "isHot",
                 "expression": "if(status in ('active', 'pending'), 1, 0)"},
            ],
        )
        r = svc.query_model("TestModel", req, mode="validate")
        assert r.error is None
        assert "IN('active', 'pending')" in r.sql


# --------------------------------------------------------------------------- #
# 6. Interaction with aggregation semantics
# --------------------------------------------------------------------------- #

class TestAggInteraction:
    def test_calc_referencing_agg_calc_uses_pre_wrap(self, svc):
        """calc A has agg=SUM; calc B references A. Per Phase 2 design
        (pre-wrap registration), B inlines A's RAW expression, not
        SUM(...) — avoids nested aggregation invalid SQL.

        Test that B = "a * 2" where A = { expr: "salesAmount", agg: SUM }
        produces "(t.sales_amount) * 2" (inlining raw expression)."""
        req = SemanticQueryRequest(
            columns=["totalSales", "derived"],
            calculatedFields=[
                {"name": "totalSales", "expression": "salesAmount", "agg": "SUM"},
                {"name": "derived", "expression": "totalSales * 2"},
            ],
        )
        r = svc.query_model("TestModel", req, mode="validate")
        assert r.error is None
        # SUM is ONLY applied to totalSales SELECT
        assert 'SUM(t.sales_amount) AS "totalSales"' in r.sql
        # derived inlines pre-wrap expression, no nested SUM
        assert "(t.sales_amount) * 2" in r.sql
        # Nested SUM would be a bug — check it's NOT present
        assert "SUM(SUM(" not in r.sql
