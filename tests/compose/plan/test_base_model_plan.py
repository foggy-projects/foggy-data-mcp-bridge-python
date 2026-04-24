"""M2 BaseModelPlan invariants."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.plan import (
    BaseModelPlan,
    QueryPlan,
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


class TestBaseModelPlanExecuteAndToSqlNeedRuntime:
    """M7 replaces the M2 UnsupportedInM2Error placeholders with a
    RuntimeError when no ambient ``ComposeRuntimeBundle`` is present."""

    def test_execute_without_bundle_raises_runtimeerror(self):
        p = BaseModelPlan(model="X", columns=("id",))
        with pytest.raises(RuntimeError) as exc:
            p.execute()
        assert "ComposeRuntimeBundle" in str(exc.value)

    def test_to_sql_without_bundle_or_ctx_raises_runtimeerror(self):
        p = BaseModelPlan(model="X", columns=("id",))
        with pytest.raises(RuntimeError) as exc:
            p.to_sql()
        assert (
            "explicit context" in str(exc.value)
            or "ComposeRuntimeBundle" in str(exc.value)
        )


class TestIsInstanceQueryPlan:
    def test_base_model_plan_is_a_queryplan(self):
        assert isinstance(
            BaseModelPlan(model="X", columns=("id",)), QueryPlan
        )
