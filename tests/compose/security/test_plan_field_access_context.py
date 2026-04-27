"""G10 PR4 · ``PlanFieldAccessContext`` contract (Python mirror of
Java ``PlanFieldAccessContextTest``)."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.plan.plan import BaseModelPlan
from foggy.dataset_model.engine.compose.security.models import ModelBinding
from foggy.dataset_model.engine.compose.security.plan_field_access_context import (
    PlanFieldAccessContext,
)


def _stub_plan(model: str) -> BaseModelPlan:
    return BaseModelPlan(model=model, columns=("id",))


class TestRegistryBehaviour:
    def test_empty_context_returns_none_for_any_plan(self):
        ctx = PlanFieldAccessContext.empty()
        p = _stub_plan("X")
        assert ctx.contains_plan(p) is False
        assert ctx.resolve_field_access(p) is None
        assert ctx.binding_of(p) is None
        assert len(ctx) == 0
        assert bool(ctx) is False

    def test_planned_field_access_returned(self):
        p = _stub_plan("X")
        binding = ModelBinding(field_access=["orderId", "customerId", "amount"])
        ctx = PlanFieldAccessContext().bind(p, binding)

        assert ctx.contains_plan(p)
        fa = ctx.resolve_field_access(p)
        assert fa == frozenset({"orderId", "customerId", "amount"})
        assert ctx.binding_of(p) is binding

    def test_planned_without_field_access_returns_none(self):
        p = _stub_plan("X")
        binding = ModelBinding()
        ctx = PlanFieldAccessContext().bind(p, binding)

        assert ctx.contains_plan(p), \
            "contains_plan distinguishes 'unregistered' from 'registered without fieldAccess'"
        assert ctx.resolve_field_access(p) is None, \
            "no fieldAccess list → resolve_field_access returns None (caller treats as unrestricted)"
        assert ctx.binding_of(p) is binding

    def test_identity_keyed_not_equality_keyed(self):
        p1 = _stub_plan("OrderQM")
        p2 = _stub_plan("OrderQM")
        # Frozen dataclass with value-equality
        assert p1 == p2
        assert p1 is not p2

        b1 = ModelBinding(field_access=["a"])
        b2 = ModelBinding(field_access=["b"])
        ctx = PlanFieldAccessContext().bind(p1, b1).bind(p2, b2)

        assert len(ctx) == 2
        assert ctx.resolve_field_access(p1) == frozenset({"a"})
        assert ctx.resolve_field_access(p2) == frozenset({"b"})

    def test_none_plan_lookup_returns_none(self):
        ctx = PlanFieldAccessContext.empty()
        assert ctx.resolve_field_access(None) is None
        assert ctx.contains_plan(None) is False
        assert ctx.binding_of(None) is None

    def test_bind_none_rejected(self):
        ctx = PlanFieldAccessContext()
        with pytest.raises(TypeError):
            ctx.bind(None, ModelBinding())  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            ctx.bind(_stub_plan("X"), None)  # type: ignore[arg-type]

    def test_resolved_set_is_immutable(self):
        p = _stub_plan("X")
        binding = ModelBinding(field_access=["a", "b"])
        ctx = PlanFieldAccessContext().bind(p, binding)

        fa = ctx.resolve_field_access(p)
        # frozenset is immutable
        with pytest.raises(AttributeError):
            fa.add("c")  # type: ignore[attr-defined]
