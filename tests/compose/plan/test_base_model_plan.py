"""M2 BaseModelPlan invariants."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.plan import (
    BaseModelPlan,
    QueryPlan,
    UnsupportedInM2Error,
)


class TestBaseModelPlanConstruction:
    def test_minimal_valid_construction(self):
        p = BaseModelPlan(model="SaleOrderQM", columns=("id", "name"))
        assert p.model == "SaleOrderQM"
        assert p.columns == ("id", "name")
        assert p.slice_ == ()
        assert p.group_by == ()
        assert p.order_by == ()
        assert p.limit is None
        assert p.start is None
        assert p.distinct is False

    def test_model_required_non_empty(self):
        with pytest.raises(ValueError):
            BaseModelPlan(model="", columns=("id",))
        with pytest.raises(ValueError):
            BaseModelPlan(model=None, columns=("id",))  # type: ignore[arg-type]

    def test_columns_required_non_empty(self):
        with pytest.raises(ValueError):
            BaseModelPlan(model="X", columns=())

    def test_columns_entries_must_be_non_empty_str(self):
        with pytest.raises(ValueError):
            BaseModelPlan(model="X", columns=("",))
        with pytest.raises(ValueError):
            BaseModelPlan(model="X", columns=(123,))  # type: ignore[arg-type]

    def test_limit_must_be_non_negative_int_or_none(self):
        with pytest.raises(ValueError):
            BaseModelPlan(model="X", columns=("id",), limit=-1)
        with pytest.raises(ValueError):
            BaseModelPlan(model="X", columns=("id",), limit=True)  # bool rejected

        # None and 0 both legal
        assert BaseModelPlan(model="X", columns=("id",), limit=None).limit is None
        assert BaseModelPlan(model="X", columns=("id",), limit=0).limit == 0

    def test_start_must_be_non_negative_int_or_none(self):
        with pytest.raises(ValueError):
            BaseModelPlan(model="X", columns=("id",), start=-1)
        assert BaseModelPlan(model="X", columns=("id",), start=0).start == 0


class TestBaseModelPlanImmutability:
    def test_frozen_rejects_attribute_mutation(self):
        p = BaseModelPlan(model="X", columns=("id",))
        with pytest.raises(Exception):  # FrozenInstanceError
            p.model = "Y"  # type: ignore[misc]

    def test_value_equality(self):
        a = BaseModelPlan(model="X", columns=("id", "name"))
        b = BaseModelPlan(model="X", columns=("id", "name"))
        assert a == b
        assert hash(a) == hash(b)

    def test_hashable(self):
        """Hashability matters for M6 subtree de-duplication."""
        a = BaseModelPlan(model="X", columns=("id",))
        b = BaseModelPlan(model="X", columns=("id",))
        assert len({a, b}) == 1  # same value ⇒ one entry in the set


class TestBaseModelPlanTreeWalk:
    def test_base_model_plans_returns_self_only(self):
        p = BaseModelPlan(model="X", columns=("id",))
        assert p.base_model_plans() == (p,)


class TestBaseModelPlanExecuteAndToSqlDeferred:
    """M2 delivers object model only — execute / to_sql land in M6/M7."""

    def test_execute_raises_unsupported(self):
        p = BaseModelPlan(model="X", columns=("id",))
        with pytest.raises(UnsupportedInM2Error):
            p.execute()

    def test_to_sql_raises_unsupported(self):
        p = BaseModelPlan(model="X", columns=("id",))
        with pytest.raises(UnsupportedInM2Error):
            p.to_sql()

    def test_unsupported_is_subclass_of_not_implemented(self):
        """Catch-alls using ``pytest.raises(NotImplementedError)`` work."""
        p = BaseModelPlan(model="X", columns=("id",))
        with pytest.raises(NotImplementedError):
            p.execute()


class TestIsInstanceQueryPlan:
    def test_base_model_plan_is_a_queryplan(self):
        assert isinstance(
            BaseModelPlan(model="X", columns=("id",)), QueryPlan
        )
