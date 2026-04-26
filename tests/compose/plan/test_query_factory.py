"""Tests for QueryFactory — the ``Query`` global in the fsscript sandbox."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.plan.plan import BaseModelPlan, PlanColumnRef
from foggy.dataset_model.engine.compose.plan.query_factory import INSTANCE as Query, QueryFactory


class TestQueryFactory:
    def test_from_creates_base_model_plan(self):
        """Query.from("ModelName") creates a BaseModelPlan with empty columns."""
        # Simulate FSScript: getattr(Query, "from") → _from_impl
        from_method = getattr(Query, "from")
        plan = from_method("SaleOrderQM")
        assert isinstance(plan, BaseModelPlan)
        assert plan.model == "SaleOrderQM"
        assert plan.columns == ()

    def test_from_rejects_empty_model(self):
        from_method = getattr(Query, "from")
        with pytest.raises(ValueError):
            from_method("")

    def test_from_rejects_none(self):
        from_method = getattr(Query, "from")
        with pytest.raises(ValueError):
            from_method(None)

    def test_unknown_attribute_raises(self):
        with pytest.raises(AttributeError):
            Query.execute  # noqa

    def test_repr(self):
        assert repr(Query) == "Query"

    def test_instance_is_query_factory(self):
        assert isinstance(Query, QueryFactory)

    def test_field_access_after_from(self):
        """Query.from("M").partnerId should return PlanColumnRef."""
        from_method = getattr(Query, "from")
        plan = from_method("SaleOrderQM")
        ref = plan.partnerId
        assert isinstance(ref, PlanColumnRef)
        assert ref.name == "partnerId"

    def test_full_chain_via_query_factory(self):
        """Full OO chain: Query.from → groupBy → select → orderBy.
        
        NOTE: .limit() cannot be chained after .select() because the
        DerivedQueryPlan dataclass field 'limit' shadows the method.
        Use .query(limit=n) for the final stage.
        """
        from_method = getattr(Query, "from")
        sales = from_method("SaleOrderQM")
        
        # Chain step by step so we can verify each stage
        grouped = sales.groupBy(sales.partnerId)
        selected = grouped.select(sales.partnerId, sales.amountTotal.sum().as_("total"))
        ordered = selected.orderBy("-total")
        
        assert grouped.group_by == ("partnerId",)
        assert selected.columns == ("partnerId", "SUM(amountTotal) AS total")
        assert ordered.order_by == ("-total",)
