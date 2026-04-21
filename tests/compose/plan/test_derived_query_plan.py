"""M2 DerivedQueryPlan invariants."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.plan import (
    BaseModelPlan,
    DerivedQueryPlan,
    QueryPlan,
    UnsupportedInM2Error,
)


def _base() -> BaseModelPlan:
    return BaseModelPlan(model="SaleOrderQM", columns=("id", "name"))


class TestDerivedQueryPlanConstruction:
    def test_minimal_valid_construction(self):
        src = _base()
        d = DerivedQueryPlan(source=src, columns=("id",))
        assert d.source is src
        assert d.columns == ("id",)

    def test_source_required_to_be_a_plan(self):
        with pytest.raises(TypeError):
            DerivedQueryPlan(source="not a plan", columns=("id",))  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            DerivedQueryPlan(source=None, columns=("id",))  # type: ignore[arg-type]

    def test_columns_required_non_empty(self):
        with pytest.raises(ValueError):
            DerivedQueryPlan(source=_base(), columns=())

    def test_pagination_validated(self):
        with pytest.raises(ValueError):
            DerivedQueryPlan(source=_base(), columns=("id",), limit=-1)


class TestDerivedQueryPlanImmutability:
    def test_frozen(self):
        d = DerivedQueryPlan(source=_base(), columns=("id",))
        with pytest.raises(Exception):
            d.columns = ("x",)  # type: ignore[misc]


class TestDerivedQueryPlanTreeWalk:
    def test_base_model_plans_proxies_to_source(self):
        """Derived plans inherit their source's base-model set."""
        base = _base()
        d = DerivedQueryPlan(source=base, columns=("id",))
        assert d.base_model_plans() == (base,)


class TestChainQuerySugar:
    def test_plan_query_returns_derived(self):
        """``plan.query(...)`` is sugar for ``from_(source=plan, ...)``."""
        base = _base()
        d = base.query(columns=["id"])
        assert isinstance(d, DerivedQueryPlan)
        assert d.source is base
        assert d.columns == ("id",)

    def test_plan_query_propagates_optional_fields(self):
        base = _base()
        d = base.query(
            columns=["id", "name"],
            slice=[{"field": "id", "op": "=", "value": 1}],
            group_by=["id"],
            order_by=["id"],
            limit=10,
            start=0,
            distinct=True,
        )
        assert d.columns == ("id", "name")
        assert d.slice_ == ({"field": "id", "op": "=", "value": 1},)
        assert d.group_by == ("id",)
        assert d.order_by == ("id",)
        assert d.limit == 10
        assert d.start == 0
        assert d.distinct is True


class TestDerivedExecuteToSqlDeferred:
    def test_execute_raises(self):
        d = DerivedQueryPlan(source=_base(), columns=("id",))
        with pytest.raises(UnsupportedInM2Error):
            d.execute()

    def test_to_sql_raises(self):
        d = DerivedQueryPlan(source=_base(), columns=("id",))
        with pytest.raises(UnsupportedInM2Error):
            d.to_sql()


class TestIsInstance:
    def test_derived_is_queryplan(self):
        assert isinstance(
            DerivedQueryPlan(source=_base(), columns=("id",)), QueryPlan
        )
