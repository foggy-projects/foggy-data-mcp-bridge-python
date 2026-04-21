"""M2 from_() entry point — model/source mutual exclusion + shape validation."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.plan import (
    BaseModelPlan,
    DerivedQueryPlan,
    from_,
)


class TestFromModelSourceMutualExclusion:
    def test_model_only_builds_base_model_plan(self):
        p = from_(model="SaleOrderQM", columns=["id", "name"])
        assert isinstance(p, BaseModelPlan)
        assert p.model == "SaleOrderQM"
        assert p.columns == ("id", "name")

    def test_source_only_builds_derived_query_plan(self):
        base = from_(model="X", columns=["id"])
        derived = from_(source=base, columns=["id"])
        assert isinstance(derived, DerivedQueryPlan)
        assert derived.source is base

    def test_both_model_and_source_rejected(self):
        base = from_(model="X", columns=["id"])
        with pytest.raises(ValueError):
            from_(model="Y", source=base, columns=["id"])

    def test_neither_rejected(self):
        with pytest.raises(ValueError):
            from_(columns=["id"])


class TestFromValidation:
    def test_positional_arguments_rejected(self):
        """from_ is keyword-only to mirror JS `from({...})` shape."""
        with pytest.raises(TypeError):
            from_("X", ["id"])  # type: ignore[misc]

    def test_columns_required(self):
        with pytest.raises(TypeError):
            # missing columns kwarg
            from_(model="X")  # type: ignore[call-arg]

    def test_columns_must_not_be_none(self):
        with pytest.raises(ValueError):
            from_(model="X", columns=None)  # type: ignore[arg-type]

    def test_columns_must_be_non_empty(self):
        with pytest.raises(ValueError):
            from_(model="X", columns=[])

    def test_model_must_be_non_empty_string(self):
        with pytest.raises(ValueError):
            from_(model="", columns=["id"])
        with pytest.raises(ValueError):
            from_(model="   ".strip(), columns=["id"])  # empty after strip

    def test_source_must_be_a_queryplan(self):
        with pytest.raises(TypeError):
            from_(source="not a plan", columns=["id"])  # type: ignore[arg-type]

    def test_pagination_negative_rejected(self):
        with pytest.raises(ValueError):
            from_(model="X", columns=["id"], limit=-1)
        with pytest.raises(ValueError):
            from_(model="X", columns=["id"], start=-1)


class TestFromOptionalFieldsPropagation:
    def test_slice_group_by_order_by_propagated(self):
        p = from_(
            model="SaleOrderQM",
            columns=["id", "amount"],
            slice=[{"field": "state", "op": "=", "value": "paid"}],
            group_by=["id"],
            order_by=["-amount"],
            limit=50,
            start=0,
            distinct=True,
        )
        assert p.slice_ == ({"field": "state", "op": "=", "value": "paid"},)
        assert p.group_by == ("id",)
        assert p.order_by == ("-amount",)
        assert p.limit == 50
        assert p.start == 0
        assert p.distinct is True

    def test_defaults_when_optional_omitted(self):
        p = from_(model="X", columns=["id"])
        assert p.slice_ == ()
        assert p.group_by == ()
        assert p.order_by == ()
        assert p.limit is None
        assert p.start is None
        assert p.distinct is False


class TestFromKernelEquivalence:
    """``from_(source=p, ...)`` ≡ ``p.query(...)``."""

    def test_from_source_equals_plan_query(self):
        base = from_(model="X", columns=["id", "name"])
        via_from = from_(source=base, columns=["id"], limit=5)
        via_query = base.query(columns=["id"], limit=5)
        assert via_from == via_query
