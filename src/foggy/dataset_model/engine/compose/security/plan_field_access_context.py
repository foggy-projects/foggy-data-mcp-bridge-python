"""G10 PR4 · Per-``QueryPlan`` permission view.

Cross-language mirror of Java
``foggy-dataset-model/src/main/java/com/foggyframework/dataset/db/model/engine/compose/security/PlanFieldAccessContext.java``.

Used by :class:`ComposePlanAwarePermissionValidator` to route a column
reference back to the producing plan's ``ModelBinding.field_access``.

Two parallel maps, both identity-keyed by ``id(plan)``:

* :attr:`plan_bindings` — the full :class:`ModelBinding` (covers
  ``field_access`` / ``denied_columns`` / ``system_slice``; PR4 only
  consults ``field_access``, but carrying the binding lets future
  passes evolve without another constructor change).
* :attr:`field_access_sets` — pre-cached ``frozenset`` view of each
  plan's ``field_access`` (or ``None`` when the binding has none).

Identity vs. equality
---------------------
Same rationale as ``_CompileState.plan_alias_map``: two
structurally-equal plan instances should map to distinct bindings
(each represents a separate compile-time entity), and the validator
must resolve via the actual instance the user wrote in the plan tree.

Lifecycle
---------
Constructed once per ``compile_to_composed_sql`` invocation by
walking the plan tree and pairing each :class:`BaseModelPlan` with
its :class:`ModelBinding` via the model name. Discarded after the
SQL is emitted; not persisted.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Optional

from ..plan.plan import QueryPlan
from .models import ModelBinding


class PlanFieldAccessContext:
    """Identity-keyed plan → binding registry (Python side)."""

    __slots__ = ("_plan_bindings", "_field_access_sets")

    def __init__(self) -> None:
        self._plan_bindings: Dict[int, ModelBinding] = {}
        self._field_access_sets: Dict[int, FrozenSet[str]] = {}

    @classmethod
    def empty(cls) -> "PlanFieldAccessContext":
        """Empty context. Validators receiving this must fail closed
        on every ``PlanColumnRef`` since no plan is bound."""
        return cls()

    def bind(self, plan: QueryPlan, binding: ModelBinding) -> "PlanFieldAccessContext":
        """Register a ``plan → binding`` pair. Returns ``self`` for chaining.

        Pre-caches the ``field_access`` whitelist as a ``frozenset`` so
        ``resolve_field_access(plan)`` is O(1).
        """
        if plan is None:
            raise TypeError("plan must not be None")
        if binding is None:
            raise TypeError("binding must not be None")
        plan_id = id(plan)
        self._plan_bindings[plan_id] = binding
        if binding.field_access is not None:
            self._field_access_sets[plan_id] = frozenset(binding.field_access)
        return self

    def contains_plan(self, plan: Optional[QueryPlan]) -> bool:
        """Whether ``plan`` has a registered binding (regardless of
        whether that binding declares a ``field_access`` list)."""
        return plan is not None and id(plan) in self._plan_bindings

    def resolve_field_access(
        self, plan: Optional[QueryPlan]
    ) -> Optional[FrozenSet[str]]:
        """Resolve the ``field_access`` whitelist for ``plan``.

        Returns
        -------
        frozenset or None
            * The plan's whitelist when registered with a non-None
              ``field_access``.
            * ``None`` when either (a) the plan is not registered
              (caller must fail-closed via ``COLUMN_PLAN_NOT_BOUND``)
              or (b) the plan is registered but its binding declares
              no ``field_access`` (no whitelist → unrestricted access
              for that plan; caller treats as "allow"). The two cases
              are distinguished by :meth:`contains_plan`.
        """
        if plan is None:
            return None
        return self._field_access_sets.get(id(plan))

    def binding_of(self, plan: Optional[QueryPlan]) -> Optional[ModelBinding]:
        """Full :class:`ModelBinding` for ``plan``, or ``None`` when
        unregistered. PR4 only reads ``field_access``; future passes
        may consume ``denied_columns`` / ``system_slice``."""
        if plan is None:
            return None
        return self._plan_bindings.get(id(plan))

    def __len__(self) -> int:
        return len(self._plan_bindings)

    def __bool__(self) -> bool:
        return bool(self._plan_bindings)
