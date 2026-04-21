"""M2 end-to-end composition tests — the spec's typical examples build green."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.plan import (
    BaseModelPlan,
    DerivedQueryPlan,
    JoinPlan,
    QueryPlan,
    UnionPlan,
    UnsupportedInM2Error,
    from_,
)
from foggy.dataset_model.engine.compose.plan.plan import JoinOn


class TestSpecExample1TwoStageAggregation:
    """Mirrors 需求.md §典型示例 1 二段聚合."""

    def test_build_two_stage_aggregation(self):
        overdue_by_customer = from_(
            model="ReceivableLineQM",
            columns=[
                "salespersonId",
                "salespersonName",
                "customer$id AS customerId",
                "SUM(IIF(isOverdue == 1, residualAmount, 0)) AS customerOverdueAmount",
            ],
            slice=[
                {"field": "docType", "op": "=", "value": "AR"},
                {"field": "docState", "op": "=", "value": "posted"},
            ],
            group_by=["salespersonId", "salespersonName", "customerId"],
        )
        assert isinstance(overdue_by_customer, BaseModelPlan)

        salesperson_overdue = overdue_by_customer.query(
            columns=[
                "salespersonId",
                "salespersonName",
                "SUM(customerOverdueAmount) AS arOverdueAmount",
                "COUNT(*) AS arOverdueCustomerCount",
            ],
            group_by=["salespersonId", "salespersonName"],
            order_by=["-arOverdueAmount"],
        )
        assert isinstance(salesperson_overdue, DerivedQueryPlan)
        assert salesperson_overdue.source is overdue_by_customer
        # Both execute() and to_sql() are M6/M7 — just confirm deferred.
        with pytest.raises(UnsupportedInM2Error):
            salesperson_overdue.execute()


class TestSpecExample2UnionThenAggregate:
    """Mirrors 需求.md §典型示例 2 union 后再聚合."""

    def test_build_union_then_aggregate(self):
        current_plan = from_(
            model="CurrentReceivableQM",
            columns=["salespersonId", "amount"],
        )
        archived_plan = from_(
            model="ArchivedReceivableQM",
            columns=["salespersonId", "amount"],
        )

        merged = current_plan.union(archived_plan, all=True)
        final_plan = merged.query(
            columns=["salespersonId", "SUM(amount) AS totalAmount"],
            group_by=["salespersonId"],
        )

        assert isinstance(merged, UnionPlan) and merged.all is True
        assert isinstance(final_plan, DerivedQueryPlan)
        # Both base models are reachable from the root derived plan
        bases = final_plan.base_model_plans()
        assert len(bases) == 2
        assert {b.model for b in bases} == {
            "CurrentReceivableQM",
            "ArchivedReceivableQM",
        }


class TestSpecExample3JoinThenFilter:
    """Mirrors 需求.md §典型示例 3 join 后再筛选."""

    def test_build_join_then_filter(self):
        sales_plan = from_(
            model="SaleOrderQM",
            columns=[
                "partner$id AS partnerId",
                "partner$caption AS partnerName",
                "SUM(amountTotal) AS totalSales",
            ],
            group_by=["partnerId", "partnerName"],
        )
        lead_plan = from_(
            model="CrmLeadQM",
            columns=["partner$id AS partnerId", "COUNT(*) AS leadCount"],
            group_by=["partnerId"],
        )

        joined = sales_plan.join(
            lead_plan,
            type="left",
            on=[{"left": "partnerId", "op": "=", "right": "partnerId"}],
        )
        final_plan = joined.query(
            columns=["partnerName", "totalSales", "leadCount"],
            slice=[{"field": "totalSales", "op": ">", "value": 10000}],
            order_by=["-totalSales"],
        )

        assert isinstance(joined, JoinPlan) and joined.type == "left"
        assert isinstance(final_plan, DerivedQueryPlan)

        bases = final_plan.base_model_plans()
        assert {b.model for b in bases} == {"SaleOrderQM", "CrmLeadQM"}
        # JoinOn coerced from dict
        assert joined.on[0] == JoinOn(
            left="partnerId", op="=", right="partnerId"
        )


class TestMultiLevelDerivation:
    def test_three_level_derivation_chain(self):
        """Each ``plan.query(...)`` produces a new DerivedQueryPlan whose
        ``source`` points at the previous step."""
        level0 = from_(model="X", columns=["id"])
        level1 = level0.query(columns=["id"])
        level2 = level1.query(columns=["id"])
        level3 = level2.query(columns=["id"])

        assert isinstance(level0, BaseModelPlan)
        assert level3.source is level2
        assert level2.source is level1
        assert level1.source is level0
        # Base collection unwinds the whole chain.
        assert level3.base_model_plans() == (level0,)


class TestLayerCPublicSurfaceWhitelist:
    """The five Layer-C methods exist; iteration / raw-sql / memoryFilter DO NOT."""

    _FORBIDDEN = (
        "raw",
        "raw_sql",
        "memory_filter",
        "for_each",
        "forEach",
        "memoryFilter",
        "items",
        "rows",
        "to_array",
        "toArray",
    )

    def test_five_allowed_methods_present(self):
        p = from_(model="X", columns=["id"])
        for name in ("query", "union", "join", "execute", "to_sql"):
            assert hasattr(p, name), (
                f"QueryPlan Layer-C whitelist must expose {name}; "
                "see M9 scaffold §Layer C"
            )

    def test_forbidden_methods_absent(self):
        p = from_(model="X", columns=["id"])
        for name in self._FORBIDDEN:
            assert not hasattr(p, name), (
                f"QueryPlan must NOT expose {name}; violates Layer-C "
                "whitelist (sandbox-violation/C/method-denied)"
            )


class TestBaseModelPlansPreorder:
    def test_mixed_tree_preorder(self):
        """A tree mixing Derived/Union/Join preserves left-to-right
        preorder of base models."""
        a = from_(model="A", columns=["id"])
        b = from_(model="B", columns=["id"])
        c = from_(model="C", columns=["id"])
        d = from_(model="D", columns=["id"])

        # ((A ∪ B) ⋈ C).query(...) ∪ D.query(...)
        left_tree = a.union(b).join(
            c, type="inner", on=[JoinOn("id", "=", "id")]
        ).query(columns=["id"])
        right_tree = d.query(columns=["id"])
        root = left_tree.union(right_tree)

        bases = root.base_model_plans()
        assert [p.model for p in bases] == ["A", "B", "C", "D"]
