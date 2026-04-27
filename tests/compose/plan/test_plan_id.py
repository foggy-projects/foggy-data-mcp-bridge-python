"""G10 PR1 · ``PlanId`` identity contract (Python mirror of Java
``PlanIdTest``).

Verifies the strict equality contract spelled out in G10 spec v2 §4.3:
``__eq__`` compares by referent identity, ``__hash__`` returns the
captured ``identity_hash``, and ``resolve()`` surfaces GC.
"""

from __future__ import annotations

import gc
import time

import pytest

from foggy.dataset_model.engine.compose.plan.plan import BaseModelPlan
from foggy.dataset_model.engine.compose.plan.plan_id import PlanId


def stub_plan() -> BaseModelPlan:
    """Tiny stub plan — only need an identity-hashable, non-singleton object."""
    return BaseModelPlan(model=f"Model_{time.time_ns()}", columns=("id",))


# ---------------------------------------------------------------------------
# equals: 严格按 referent identity
# ---------------------------------------------------------------------------


class TestEquality:
    def test_same_plan_referent(self):
        plan = stub_plan()
        id1 = PlanId.of(plan)
        id2 = PlanId.of(plan)
        assert id1 == id2, "PlanId of the same plan referent must equal"
        assert hash(id1) == hash(id2), "Same referent must produce same identity_hash"

    def test_different_plan_referents(self):
        id1 = PlanId.of(stub_plan())
        id2 = PlanId.of(stub_plan())
        assert id1 != id2, "Two PlanId backed by distinct plan instances must not equal"

    def test_same_model_different_instances_not_equal(self):
        # G10 spec §5.1: 等价判定按对象身份，不按 model 名称。
        a1 = BaseModelPlan(model="X", columns=("id",))
        a2 = BaseModelPlan(model="X", columns=("id",))
        assert a1 is not a2
        assert PlanId.of(a1) != PlanId.of(a2), \
            "Same model name in different instances must yield distinct PlanIds"

    def test_reflexive_and_symmetric(self):
        plan = stub_plan()
        id1 = PlanId.of(plan)
        id2 = PlanId.of(plan)
        # 自反
        assert id1 == id1
        # 对称
        assert id1 == id2
        assert id2 == id1

    def test_not_equal_to_none_or_unrelated(self):
        plan_id = PlanId.of(stub_plan())
        assert plan_id != None  # noqa: E711
        assert plan_id != "not a PlanId"
        assert "not a PlanId" != plan_id

    def test_of_none_raises(self):
        with pytest.raises(TypeError):
            PlanId.of(None)


# ---------------------------------------------------------------------------
# hash: 仅用 identity_hash，不依赖 referent 状态
# ---------------------------------------------------------------------------


class TestHashContract:
    def test_hash_stable(self):
        plan = stub_plan()
        plan_id = PlanId.of(plan)
        assert hash(plan_id) == hash(plan_id), "hash must be stable across calls"
        assert hash(plan_id) == id(plan), \
            "hash should be the cached id() of the referent"

    def test_works_as_set_key(self):
        p1 = stub_plan()
        p2 = stub_plan()
        s = {PlanId.of(p1), PlanId.of(p2)}
        assert len(s) == 2, "Distinct plans must remain distinct in a set"
        assert PlanId.of(p1) in s
        assert PlanId.of(p2) in s

    def test_works_as_dict_key(self):
        p1 = stub_plan()
        p2 = stub_plan()
        m = {PlanId.of(p1): "first", PlanId.of(p2): "second"}
        assert m[PlanId.of(p1)] == "first"
        assert m[PlanId.of(p2)] == "second"
        assert m.get(PlanId.of(stub_plan())) is None, \
            "An unrelated plan must miss the map"


# ---------------------------------------------------------------------------
# resolve: GC 后返回 None（or strongly-referenced fallback)
# ---------------------------------------------------------------------------


class TestGcBehavior:
    def test_resolve_returns_living_referent(self):
        plan = stub_plan()
        plan_id = PlanId.of(plan)
        assert plan_id.resolve() is plan, \
            "resolve() must return the same plan object while alive"

    def test_strong_reference_does_not_prematurely_expire(self):
        plan = stub_plan()
        plan_id = PlanId.of(plan)
        gc.collect()
        assert plan_id.resolve() is plan, \
            "strongly-referenced plan must not be collected"

    def test_repr_shape(self):
        plan_id = PlanId.of(stub_plan())
        s = repr(plan_id)
        assert s.startswith("PlanId(hash="), f"repr prefix: {s}"
        assert "referent=" in s, f"repr includes referent: {s}"


# ---------------------------------------------------------------------------
# Transient semantics doc
# ---------------------------------------------------------------------------


class TestTransientSemantics:
    def test_uses_slots(self):
        # Forces tightness — no random attribute drift.
        plan_id = PlanId.of(stub_plan())
        with pytest.raises(AttributeError):
            plan_id.something_else = 42  # type: ignore[attr-defined]

    def test_no_serialization_roundtrip_attempted(self):
        # PlanId is transient — pickle would lose the weakref. We don't
        # explicitly forbid it, but the contract is "do not persist".
        # This test just documents the intent.
        plan_id = PlanId.of(stub_plan())
        assert plan_id.identity_hash == hash(plan_id)
