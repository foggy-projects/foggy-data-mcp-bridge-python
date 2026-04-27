"""``PlanId`` — transient identity key for a ``QueryPlan`` referent.

Cross-language mirror of Java's
``foggy-dataset-model/src/main/java/com/foggyframework/dataset/db/model/engine/compose/plan/PlanId.java``
(G10 PR1).

Why a separate identity key
---------------------------
Plans are immutable frozen dataclasses; structurally-equal plans should
*not* be treated as identical for plan-aware routing (G10 §4.3). The
producing-plan handle that ``ColumnSpec.plan_provenance`` carries needs
identity-not-equality semantics so two ``BaseModelPlan(model='X')``
instances that happen to be value-equal still map to distinct CTE
aliases, distinct bindings, etc.

Python's ``id()`` returns a CPython-specific integer that may be reused
once an object is garbage-collected — so we hold a ``weakref`` to the
referent (mirroring Java's ``WeakReference<QueryPlan>``) plus the cached
``id()`` for hash bucket placement only.

Contract
--------
* ``__eq__`` compares by referent identity (``self.resolve() is other.resolve()``)
  — never by ``identity_hash`` alone, so the rare hash collision can't
  silently merge two distinct plans.
* ``__hash__`` returns the cached ``identity_hash`` for hash-table bucket
  placement; equality still resolves the referent.
* ``resolve()`` returns the referent or ``None`` when GC has reclaimed
  it; downstream consumers must fail-closed.
* Transient — not serialisable, not safe across processes / requests.
  Lives only inside one compile session.

Note
----
Plans are frozen dataclasses; CPython's default ``weakref`` slot is
disabled for ``__slots__``-d frozen dataclasses unless we add a
``__weakref__`` slot. Some plan classes don't allow weakrefs, so we
fall back to a strong reference when ``weakref.ref(plan)`` raises
``TypeError``. The strong-ref fallback keeps the plan alive for the
PlanId's lifetime; since PlanId itself is short-lived (one compile
session), this is acceptable.
"""

from __future__ import annotations

import weakref
from typing import Any, Optional


class PlanId:
    """Identity-keyed handle to a ``QueryPlan`` referent."""

    __slots__ = ("_identity_hash", "_ref", "_strong_ref")

    def __init__(self, plan: Any) -> None:
        if plan is None:
            raise TypeError("PlanId.of: plan must not be None")
        self._identity_hash = id(plan)
        try:
            self._ref = weakref.ref(plan)
            self._strong_ref = None
        except TypeError:
            # Frozen dataclass with __slots__ may reject weakref; fall
            # back to a strong reference. Acceptable because PlanId is
            # transient (single compile session lifetime).
            self._ref = None
            self._strong_ref = plan

    @classmethod
    def of(cls, plan: Any) -> "PlanId":
        return cls(plan)

    def resolve(self) -> Optional[Any]:
        """Return the referent, or ``None`` when GC has reclaimed it."""
        if self._strong_ref is not None:
            return self._strong_ref
        return self._ref() if self._ref is not None else None

    @property
    def identity_hash(self) -> int:
        """Cached ``id()`` of the referent. Use for hash bucket only."""
        return self._identity_hash

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, PlanId):
            return False
        a = self.resolve()
        b = other.resolve()
        return a is not None and a is b

    def __hash__(self) -> int:
        return self._identity_hash

    def __repr__(self) -> str:
        ref = self.resolve()
        ref_part = f"{type(ref).__name__}@{self._identity_hash:x}" if ref is not None else "<gc>"
        return f"PlanId(hash={self._identity_hash:#x}, referent={ref_part})"
