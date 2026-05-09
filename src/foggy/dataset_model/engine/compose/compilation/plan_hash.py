"""Plan-subtree canonical hashing + MAX_PLAN_DEPTH DOS guard (M6 · 6.6).

Two features in one module because they share the same recursive plan
walker and the tests live together.

``plan_hash(plan)`` returns a **hashable tuple** that identifies a plan
subtree structurally. Two ``BaseModelPlan`` / ``DerivedQueryPlan`` /
``UnionPlan`` / ``JoinPlan`` instances that are semantically equivalent
yield equal hashes even when ``id()`` differs — this is the Full dedup
mode from the 6.6 spec.

The MVP dedup mode (``Dict[int, CteUnit]`` keyed by ``id(plan)``) lives
in :mod:`compose_planner`; it runs **before** ``plan_hash`` and covers
the typical "same instance referenced twice" case for free. Full mode
then catches the "two different instances with identical shape" case.

Why a separate hashing module instead of reusing ``hash(plan)``?

- M2 plans are declared ``@dataclass(frozen=True)`` which auto-generates
  ``__hash__``, but ``BaseModelPlan.slice_`` / ``columns`` / ``group_by``
  / ``order_by`` are stored as ``Tuple[str, ...]`` — already hashable.
- ``slice_`` entries, however, are ``Any`` (typically ``Dict[str, Any]``
  after v1.3-compat deserialisation), and ``Dict`` is NOT hashable.
  Calling ``hash(plan)`` on a real plan with a non-empty slice would
  raise ``TypeError: unhashable type: 'dict'``.
- Rather than touch M2's frozen contract (which would need cross-lang
  signoff), M6 owns the canonicalisation locally.
"""
from __future__ import annotations

from typing import Any, Mapping, Tuple

from foggy.dataset_model.engine.compose.plan.plan import (
    BaseModelPlan,
    DerivedQueryPlan,
    JoinOn,
    JoinPlan,
    PlanSubquery,
    QueryPlan,
    UnionPlan,
)

#: Canonical hashable view of a :class:`QueryPlan` subtree. The first
#: element is a string discriminator (``"base" / "derived" / "union" /
#: "join"``); the remaining elements are canonicalised plan attributes.
#: Equality on this tuple implies structural equivalence.
CanonicalPlanTuple = Tuple[Any, ...]


# ---------------------------------------------------------------------------
# MAX_PLAN_DEPTH guard (r3)
# ---------------------------------------------------------------------------

MAX_PLAN_DEPTH: int = 32
"""Defense-in-depth cap on nested plan recursion.

A real Compose Query rarely exceeds depth 3-5; depths above 32 signal
either script abuse or a generated-plan bug. The cap protects the M7
script runner from pathological DOS inputs without blocking any
real-world query shape.

Enforced inside :mod:`compose_planner._compile_any` via
``_CompileState.enter_depth`` / ``exit_depth`` on the state's
``current_depth`` counter; any recursion level > ``MAX_PLAN_DEPTH``
raises ``ComposeCompileError(UNSUPPORTED_PLAN_SHAPE, phase='plan-lower')``.
"""


# ---------------------------------------------------------------------------
# Canonical tuple (hashable view of arbitrary plan attribute values)
# ---------------------------------------------------------------------------


def canonical(value: Any) -> Any:
    """Recursively convert Lists / Dicts / tuples so the result is a
    hashable, order-preserving primitive.

    Rules:
      - ``list`` → ``tuple(canonical(v) for v in lst)`` — order preserved
      - ``dict`` / ``Mapping`` → ``tuple(sorted((k, canonical(v)) for k, v in items))``
        — key order normalised so ``{"a": 1, "b": 2}`` and ``{"b": 2, "a": 1}``
        yield equal hashes
      - ``tuple`` → re-wrapped with canonical on each element (handles
        nested tuples in pre-frozen plan fields)
      - anything else (``str / int / float / bool / None``) returned
        verbatim, trusting it is already hashable
    """
    if isinstance(value, PlanSubquery):
        return ("subquery", plan_hash(value.plan), value.field)
    if isinstance(value, QueryPlan):
        return ("plan", plan_hash(value))
    if isinstance(value, list):
        return tuple(canonical(v) for v in value)
    if isinstance(value, Mapping):
        # ``dict`` is a ``Mapping`` subclass, so this branch covers both.
        # ``sorted`` on (key, value) — keys must be comparable (typically str)
        return tuple(
            sorted(
                ((k, canonical(v)) for k, v in value.items()),
                key=lambda kv: kv[0],
            )
        )
    if isinstance(value, tuple):
        return tuple(canonical(v) for v in value)
    return value


# ---------------------------------------------------------------------------
# plan_hash — structural hash tuple per QueryPlan subclass
# ---------------------------------------------------------------------------


def plan_hash(plan: QueryPlan) -> CanonicalPlanTuple:
    """Canonical hash tuple for a plan subtree — stable across instances.

    The returned tuple is hashable, so callers can use it as
    ``Dict[Tuple, CteUnit]`` key. Two plans producing equal tuples are
    considered structurally interchangeable and can share a compiled
    CTE (Full-mode dedup).

    Parameters
    ----------
    plan:
        Any ``QueryPlan`` instance. Unknown subclasses raise
        ``TypeError`` — fail-closed to avoid silent dedup drift when a
        new plan type is introduced without updating this module.
    """
    if isinstance(plan, BaseModelPlan):
        return (
            "base",
            plan.model,
            canonical(plan.columns),
            canonical(plan.slice_),
            canonical(plan.having),
            canonical(plan.group_by),
            canonical(plan.order_by),
            canonical(plan.calculated_fields),
            plan.limit,
            plan.start,
            bool(plan.distinct),
        )
    if isinstance(plan, DerivedQueryPlan):
        return (
            "derived",
            plan_hash(plan.source),
            canonical(plan.columns),
            canonical(plan.slice_),
            canonical(plan.group_by),
            canonical(plan.order_by),
            plan.limit,
            plan.start,
            bool(plan.distinct),
        )
    if isinstance(plan, UnionPlan):
        return (
            "union",
            bool(plan.all),
            plan_hash(plan.left),
            plan_hash(plan.right),
        )
    if isinstance(plan, JoinPlan):
        return (
            "join",
            plan.type,
            plan_hash(plan.left),
            plan_hash(plan.right),
            tuple(_canonical_join_on(o) for o in plan.on),
        )
    raise TypeError(
        f"plan_hash() received unsupported plan type {type(plan).__name__}; "
        "extend plan_hash if a new QueryPlan subclass was added"
    )


def _canonical_join_on(on: JoinOn) -> Tuple[str, str, str]:
    """Canonical form of one ``JoinOn`` — ``(left, op, right)``."""
    return (on.left, on.op, on.right)


# ---------------------------------------------------------------------------
# Depth measurement helper (used by tests + compose_planner depth guard)
# ---------------------------------------------------------------------------


def plan_depth(plan: QueryPlan) -> int:
    """Return the maximum nesting depth of ``plan``.

    A single ``BaseModelPlan`` has depth 1; ``DerivedQueryPlan(source=base)``
    is depth 2; ``UnionPlan(left=base, right=base)`` is depth 2;
    ``DerivedQueryPlan(source=UnionPlan(...))`` is depth 3; etc.

    Used by tests to verify the MAX_PLAN_DEPTH guard triggers at
    exactly depth ``MAX_PLAN_DEPTH + 1`` and passes at
    ``MAX_PLAN_DEPTH``.
    """
    if isinstance(plan, BaseModelPlan):
        return 1
    if isinstance(plan, DerivedQueryPlan):
        return 1 + plan_depth(plan.source)
    if isinstance(plan, UnionPlan):
        return 1 + max(plan_depth(plan.left), plan_depth(plan.right))
    if isinstance(plan, JoinPlan):
        return 1 + max(plan_depth(plan.left), plan_depth(plan.right))
    raise TypeError(
        f"plan_depth() received unsupported plan type {type(plan).__name__}"
    )
