"""M2 UnionPlan invariants."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.plan import (
    BaseModelPlan,
    QueryPlan,
    UnionPlan,
)


def _base(name: str) -> BaseModelPlan:
    return BaseModelPlan(model=name, columns=("id", "val"))


class TestUnionPlanConstruction:
    def test_minimal_valid_construction(self):
        a, b = _base("A"), _base("B")
        u = UnionPlan(left=a, right=b)
        assert u.left is a
        assert u.right is b
        assert u.all is False

    def test_all_flag_defaults_to_false(self):
        """Default ``UNION`` (distinct); ``all=True`` ⇒ ``UNION ALL``."""
        u = UnionPlan(left=_base("A"), right=_base("B"))
        assert u.all is False

        u2 = UnionPlan(left=_base("A"), right=_base("B"), all=True)
        assert u2.all is True

    def test_left_must_be_a_plan(self):
        with pytest.raises(TypeError):
            UnionPlan(left="not a plan", right=_base("B"))  # type: ignore[arg-type]

    def test_right_must_be_a_plan(self):
        with pytest.raises(TypeError):
            UnionPlan(left=_base("A"), right=None)  # type: ignore[arg-type]


class TestUnionChainSugar:
    def test_plan_union_returns_union_plan(self):
        a, b = _base("A"), _base("B")
        u = a.union(b)
        assert isinstance(u, UnionPlan)
        assert u.left is a and u.right is b
        assert u.all is False

    def test_plan_union_all_true(self):
        a, b = _base("A"), _base("B")
        u = a.union(b, all=True)
        assert u.all is True

    def test_plan_union_rejects_non_plan_right(self):
        a = _base("A")
        with pytest.raises(TypeError):
            a.union({"model": "not a plan"})  # type: ignore[arg-type]


class TestUnionTreeWalk:
    def test_base_model_plans_preorder_left_then_right(self):
        a, b = _base("A"), _base("B")
        u = a.union(b)
        assert u.base_model_plans() == (a, b)

    def test_base_model_plans_three_level_chain(self):
        """UnionPlan can recurse; base-model collection preserves order."""
        a, b, c = _base("A"), _base("B"), _base("C")
        u = a.union(b).union(c)
        assert u.base_model_plans() == (a, b, c)


class TestUnionImmutability:
    def test_frozen(self):
        u = UnionPlan(left=_base("A"), right=_base("B"))
        with pytest.raises(Exception):
            u.all = True  # type: ignore[misc]


class TestIsInstance:
    def test_union_is_queryplan(self):
        assert isinstance(UnionPlan(left=_base("A"), right=_base("B")), QueryPlan)
