"""M2 JoinPlan + JoinOn invariants."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.plan import (
    BaseModelPlan,
    JoinPlan,
    QueryPlan,
)
from foggy.dataset_model.engine.compose.plan.plan import JoinOn


def _base(name: str) -> BaseModelPlan:
    return BaseModelPlan(model=name, columns=("id", "partnerId"))


class TestJoinOn:
    def test_minimal_valid_construction(self):
        j = JoinOn(left="partnerId", op="=", right="partnerId")
        assert j.left == "partnerId"
        assert j.op == "=" and j.right == "partnerId"

    def test_left_right_required_non_empty(self):
        with pytest.raises(ValueError):
            JoinOn(left="", op="=", right="x")
        with pytest.raises(ValueError):
            JoinOn(left="x", op="=", right="")

    def test_op_whitelist(self):
        for op in ("=", "!=", "<", ">", "<=", ">="):
            assert JoinOn(left="a", op=op, right="b").op == op
        for bad in ("in", "IN", "between", "like", "is null", ""):
            with pytest.raises(ValueError):
                JoinOn(left="a", op=bad, right="b")

    def test_frozen(self):
        j = JoinOn(left="a", op="=", right="b")
        with pytest.raises(Exception):
            j.op = "!="  # type: ignore[misc]


class TestJoinPlanConstruction:
    def test_minimal_valid_construction(self):
        a, b = _base("A"), _base("B")
        jp = JoinPlan(
            left=a,
            right=b,
            type="left",
            on=(JoinOn(left="partnerId", op="=", right="partnerId"),),
        )
        assert jp.left is a and jp.right is b
        assert jp.type == "left"
        assert len(jp.on) == 1

    def test_type_whitelist(self):
        a, b = _base("A"), _base("B")
        on = (JoinOn(left="id", op="=", right="id"),)
        for t in ("inner", "left", "right", "full"):
            assert (
                JoinPlan(left=a, right=b, type=t, on=on).type == t
            )
        with pytest.raises(ValueError):
            JoinPlan(left=a, right=b, type="cross", on=on)

    def test_on_must_be_non_empty(self):
        a, b = _base("A"), _base("B")
        with pytest.raises(ValueError):
            JoinPlan(left=a, right=b, type="left", on=())

    def test_on_entries_must_be_join_on(self):
        a, b = _base("A"), _base("B")
        with pytest.raises(TypeError):
            JoinPlan(
                left=a, right=b, type="left",
                on=({"left": "x", "op": "=", "right": "y"},),  # dict raw — direct construction rejects
            )


class TestJoinChainSugar:
    def test_plan_join_accepts_join_on_list(self):
        a, b = _base("A"), _base("B")
        jp = a.join(
            b,
            type="left",
            on=[JoinOn(left="partnerId", op="=", right="partnerId")],
        )
        assert isinstance(jp, JoinPlan)
        assert jp.type == "left"

    def test_plan_join_coerces_dict_conditions(self):
        """Script-side callers pass plain dicts; chain sugar coerces to JoinOn."""
        a, b = _base("A"), _base("B")
        jp = a.join(
            b,
            type="inner",
            on=[{"left": "partnerId", "op": "=", "right": "partnerId"}],
        )
        assert jp.on[0] == JoinOn(left="partnerId", op="=", right="partnerId")

    def test_plan_join_case_insensitive_type(self):
        a, b = _base("A"), _base("B")
        jp = a.join(b, type="LEFT", on=[JoinOn("id", "=", "id")])
        assert jp.type == "left"

    def test_plan_join_rejects_empty_on(self):
        a, b = _base("A"), _base("B")
        with pytest.raises(ValueError):
            a.join(b, type="left", on=[])

    def test_plan_join_rejects_non_plan_right(self):
        a = _base("A")
        with pytest.raises(TypeError):
            a.join(None, type="left", on=[JoinOn("id", "=", "id")])  # type: ignore[arg-type]

    def test_plan_join_rejects_bad_dict_missing_key(self):
        a, b = _base("A"), _base("B")
        with pytest.raises(ValueError):
            a.join(b, type="left", on=[{"left": "id", "op": "="}])  # missing 'right'


class TestJoinTreeWalk:
    def test_base_model_plans_left_then_right(self):
        a, b = _base("A"), _base("B")
        jp = a.join(b, type="left", on=[JoinOn("id", "=", "id")])
        assert jp.base_model_plans() == (a, b)


class TestIsInstance:
    def test_join_is_queryplan(self):
        a, b = _base("A"), _base("B")
        jp = a.join(b, type="left", on=[JoinOn("id", "=", "id")])
        assert isinstance(jp, QueryPlan)
