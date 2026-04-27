"""G10 PR3 mirror · ``_CompileState.plan_alias_map`` infrastructure
verification.

Python-side note: unlike Java where ``PlanColumnRef`` survives into
``plan.columns`` and the compile path emits ``<alias>.<col>``, Python's
fluent API flattens ``PlanColumnRef`` to bare strings via
``to_column_expr()`` at the ``select()`` call. So the compiled SQL
shape doesn't change under the G10 flag — but the alias-map
infrastructure still has to be in place for PR5.4's validator to route
columns back to their producing plan.

These tests verify the *plumbing*: when ``feature_flags.g10_enabled()``
is on, every ``BaseModelPlan`` and ``DerivedQueryPlan`` registered via
``next_alias()`` ends up in ``state.plan_alias_map``. When off, the map
stays empty so legacy compile paths zero-cost short-circuit.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from foggy.dataset_model.engine.compose import feature_flags
from foggy.dataset_model.engine.compose.compilation.compose_planner import (
    _CompileState,
    _register_plan_alias,
)
from foggy.dataset_model.engine.compose.plan.plan import BaseModelPlan


# G10 flag override is cleared by the autouse fixture in
# ``tests/compose/conftest.py`` — no per-file teardown needed.


def _state(g10: bool) -> _CompileState:
    return _CompileState(
        bindings={},
        semantic_service=MagicMock(),
        dialect="sqlite",
        g10_enabled=g10,
    )


class TestRegistrationFlagGated:
    def test_flag_off_keeps_map_empty(self):
        feature_flags.override_g10_enabled(False)
        state = _state(g10=False)
        plan = BaseModelPlan(model="X", columns=("id",))
        _register_plan_alias(state, plan, "cte_0")
        assert state.plan_alias_map == {}, \
            "flag=False keeps plan_alias_map empty (zero-cost legacy path)"

    def test_flag_on_registers_plan_id(self):
        feature_flags.override_g10_enabled(True)
        state = _state(g10=True)
        plan = BaseModelPlan(model="X", columns=("id",))
        _register_plan_alias(state, plan, "cte_0")
        assert state.plan_alias_map == {id(plan): "cte_0"}

    def test_two_value_equal_plans_keyed_by_identity(self):
        # Plans are frozen dataclasses with value-equality. Identity-keying
        # via id() ensures structurally-equal plans don't collide.
        feature_flags.override_g10_enabled(True)
        state = _state(g10=True)
        a = BaseModelPlan(model="X", columns=("id",))
        b = BaseModelPlan(model="X", columns=("id",))
        assert a == b, "value-equal by dataclass eq"
        assert a is not b, "but distinct instances"

        _register_plan_alias(state, a, "cte_0")
        _register_plan_alias(state, b, "cte_1")
        assert state.plan_alias_map[id(a)] == "cte_0"
        assert state.plan_alias_map[id(b)] == "cte_1"
        assert state.plan_alias_map[id(a)] != state.plan_alias_map[id(b)]


class TestStateConstruction:
    def test_g10_enabled_snapshot_at_construction(self):
        # The state captures ``g10_enabled`` once; flipping the env / override
        # mid-compile must not change the captured snapshot.
        feature_flags.override_g10_enabled(True)
        state = _CompileState(
            bindings={}, semantic_service=MagicMock(),
            dialect="sqlite", g10_enabled=feature_flags.g10_enabled(),
        )
        assert state.g10_enabled is True

        feature_flags.override_g10_enabled(False)
        # The snapshot is sticky.
        assert state.g10_enabled is True
