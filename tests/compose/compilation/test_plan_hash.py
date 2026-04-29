"""Tests for ``compilation.plan_hash`` — canonical structural hashing.

6.6 · Full-mode dedup foundation + the critical ``List``-unhashable guard.

Split into three sections:
  A) ``canonical`` — recursive list/dict/tuple normalisation
  B) ``plan_hash`` — structural hash tuples per plan subclass
  C) ``plan_depth`` — recursion depth measurement (used by DOS guard tests)
"""
from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.compilation.plan_hash import (
    MAX_PLAN_DEPTH,
    canonical,
    plan_depth,
    plan_hash,
)
from foggy.dataset_model.engine.compose.plan import from_
from foggy.dataset_model.engine.compose.plan.plan import (
    BaseModelPlan,
    DerivedQueryPlan,
    JoinOn,
    JoinPlan,
    UnionPlan,
)


# ===========================================================================
# A) canonical
# ===========================================================================


class TestCanonicalPrimitives:
    @pytest.mark.parametrize("value", ["hello", 42, 3.14, True, False, None])
    def test_primitives_pass_through(self, value):
        assert canonical(value) == value


class TestCanonicalList:
    def test_empty_list(self):
        assert canonical([]) == ()

    def test_simple_list(self):
        assert canonical([1, 2, 3]) == (1, 2, 3)

    def test_list_of_lists(self):
        assert canonical([[1, 2], [3]]) == ((1, 2), (3,))

    def test_list_preserves_order(self):
        """canonical is order-preserving on lists."""
        assert canonical([3, 1, 2]) == (3, 1, 2)
        assert canonical([1, 2, 3]) != canonical([3, 2, 1])

    def test_list_result_is_hashable(self):
        """Critical guarantee — used as a dict key."""
        hash(canonical([1, [2, [3]], 4]))


class TestCanonicalDict:
    def test_empty_dict(self):
        assert canonical({}) == ()

    def test_simple_dict(self):
        expected = (("a", 1), ("b", 2))
        assert canonical({"a": 1, "b": 2}) == expected

    def test_dict_key_order_normalized(self):
        """Two dicts with same items in different order hash identically."""
        assert canonical({"b": 2, "a": 1}) == canonical({"a": 1, "b": 2})

    def test_nested_dict(self):
        expected = (("a", (("x", 1), ("y", 2))),)
        assert canonical({"a": {"y": 2, "x": 1}}) == expected

    def test_dict_with_list_values(self):
        expected = (("a", (1, 2, 3)),)
        assert canonical({"a": [1, 2, 3]}) == expected


class TestCanonicalTuple:
    def test_tuple_recursed(self):
        assert canonical((1, [2, 3])) == (1, (2, 3))


# ===========================================================================
# B) plan_hash
# ===========================================================================


class TestPlanHashBaseModel:
    def test_single_base(self):
        plan = from_(model="FactSalesModel", columns=["orderStatus", "salesAmount"])
        h = plan_hash(plan)
        assert h[0] == "base"
        assert h[1] == "FactSalesModel"
        assert h[2] == ("orderStatus", "salesAmount")

    def test_two_base_identical_shape_same_hash(self):
        """Critical Full-mode case — two different instances, same shape."""
        a = from_(model="FactSalesModel", columns=["orderStatus", "salesAmount"])
        b = from_(model="FactSalesModel", columns=["orderStatus", "salesAmount"])
        assert a is not b
        assert plan_hash(a) == plan_hash(b)

    def test_different_models_different_hash(self):
        a = from_(model="FactSalesModel", columns=["orderStatus"])
        b = from_(model="FactOrderModel", columns=["orderStatus"])
        assert plan_hash(a) != plan_hash(b)

    def test_different_column_order_different_hash(self):
        """``canonical`` is list-order-preserving; different order != match."""
        a = from_(model="FactSalesModel", columns=["orderStatus", "salesAmount"])
        b = from_(model="FactSalesModel", columns=["salesAmount", "orderStatus"])
        assert plan_hash(a) != plan_hash(b)

    def test_different_limits_different_hash(self):
        a = from_(model="FactSalesModel", columns=["orderStatus"], limit=10)
        b = from_(model="FactSalesModel", columns=["orderStatus"], limit=20)
        assert plan_hash(a) != plan_hash(b)

    def test_calculated_fields_participate_in_hash(self):
        a = from_(
            model="FactSalesModel",
            columns=["orderStatus"],
            calculated_fields=[
                {"name": "grossAmount", "expression": "salesAmount * 1.2"},
            ],
        )
        b = from_(
            model="FactSalesModel",
            columns=["orderStatus"],
            calculated_fields=[
                {"name": "grossAmount", "expression": "salesAmount * 1.3"},
            ],
        )
        assert plan_hash(a) != plan_hash(b)

    def test_base_with_slice_list_of_dict_hashable(self):
        """★ r2 guard: slice entries are dicts (Any), which are NOT hashable
        in vanilla ``hash(plan)``. plan_hash() handles it via canonical."""
        plan = from_(
            model="FactSalesModel",
            columns=["orderStatus"],
            slice=[{"field": "amount", "op": ">", "value": 100}],
        )
        # Must not raise TypeError: unhashable type: 'dict'
        h = plan_hash(plan)
        assert hash(h) is not None  # hashable overall

    def test_plan_hash_result_is_hashable(self):
        plan = from_(model="FactSalesModel", columns=["orderStatus"])
        hash(plan_hash(plan))  # no exception


class TestPlanHashDerivedQueryPlan:
    def test_derived_hash_recurses_into_source(self):
        base = from_(model="FactSalesModel", columns=["orderStatus", "salesAmount"])
        derived = base.query(columns=["orderStatus"])
        h = plan_hash(derived)
        assert h[0] == "derived"
        assert h[1] == plan_hash(base)

    def test_two_equivalent_derived_same_hash(self):
        base1 = from_(model="FactSalesModel", columns=["orderStatus"])
        base2 = from_(model="FactSalesModel", columns=["orderStatus"])
        d1 = base1.query(columns=["orderStatus"])
        d2 = base2.query(columns=["orderStatus"])
        assert plan_hash(d1) == plan_hash(d2)


class TestPlanHashUnionPlan:
    def test_union_all_flag_in_hash(self):
        a = from_(model="FactSalesModel", columns=["orderStatus"])
        b = from_(model="FactSalesModel", columns=["orderStatus"])
        u_all = a.union(b, all=True)
        u_distinct = a.union(b, all=False)
        assert plan_hash(u_all) != plan_hash(u_distinct)

    def test_union_same_sides_same_hash(self):
        a1 = from_(model="FactSalesModel", columns=["orderStatus"])
        a2 = from_(model="FactSalesModel", columns=["orderStatus"])
        u1 = a1.union(a1, all=True)
        u2 = a2.union(a2, all=True)
        assert plan_hash(u1) == plan_hash(u2)


class TestPlanHashJoinPlan:
    def test_join_type_in_hash(self):
        l = from_(model="FactSalesModel", columns=["orderStatus"])
        r = from_(model="FactOrderModel", columns=["orderStatus"])
        on = [JoinOn(left="orderStatus", op="=", right="orderStatus")]
        j_inner = l.join(r, type="inner", on=on)
        j_left = l.join(r, type="left", on=on)
        assert plan_hash(j_inner) != plan_hash(j_left)

    def test_join_on_list_in_hash(self):
        l = from_(model="FactSalesModel", columns=["orderStatus"])
        r = from_(model="FactOrderModel", columns=["orderStatus"])
        on1 = [JoinOn(left="orderStatus", op="=", right="orderStatus")]
        on2 = [
            JoinOn(left="orderStatus", op="=", right="orderStatus"),
            JoinOn(left="orderStatus", op="=", right="orderStatus"),
        ]
        assert plan_hash(l.join(r, on=on1)) != plan_hash(l.join(r, on=on2))


class TestPlanHashUnknownSubclass:
    def test_unknown_type_rejected(self):
        class FakePlan:
            pass

        with pytest.raises(TypeError, match="unsupported plan type"):
            plan_hash(FakePlan())


# ===========================================================================
# C) plan_depth
# ===========================================================================


class TestPlanDepth:
    def test_base_is_depth_1(self):
        plan = from_(model="FactSalesModel", columns=["orderStatus"])
        assert plan_depth(plan) == 1

    def test_derived_adds_depth(self):
        base = from_(model="FactSalesModel", columns=["orderStatus", "salesAmount"])
        d1 = base.query(columns=["orderStatus"])
        d2 = d1.query(columns=["orderStatus"])
        d3 = d2.query(columns=["orderStatus"])
        assert plan_depth(base) == 1
        assert plan_depth(d1) == 2
        assert plan_depth(d2) == 3
        assert plan_depth(d3) == 4

    def test_union_depth_takes_max_side(self):
        a = from_(model="FactSalesModel", columns=["orderStatus"])
        b = from_(model="FactOrderModel", columns=["orderStatus"])
        u = a.union(b)
        assert plan_depth(u) == 2  # 1 (union) + max(1, 1)

    def test_join_depth_takes_max_side(self):
        l = from_(model="FactSalesModel", columns=["orderStatus"])
        r = from_(model="FactOrderModel", columns=["orderStatus"])
        on = [JoinOn(left="orderStatus", op="=", right="orderStatus")]
        j = l.join(r, on=on)
        assert plan_depth(j) == 2

    def test_max_plan_depth_constant(self):
        """Spec-level contract — r3 hard-coded 32 as DOS guard cap."""
        assert MAX_PLAN_DEPTH == 32
