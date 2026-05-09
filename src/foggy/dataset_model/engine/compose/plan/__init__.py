"""Compose Query ``QueryPlan`` object model (8.2.0.beta M2).

The four concrete plan types form a logical-relation tree that the
Compose Query pipeline builds up during script execution. Tree nodes
carry no execution state — they are pure, immutable descriptors.
Execution (SQL compile in M6, runtime binding in M7) consumes this tree.

Public surface (Layer-C whitelist · see ``M9`` sandbox scaffold):
    - ``from_()``               Build a ``BaseModelPlan`` or ``DerivedQueryPlan``.
    - ``QueryPlan``             Abstract base exposing 5 methods.
    - ``BaseModelPlan``         Leaf node pointing at a physical QM.
    - ``DerivedQueryPlan``      Node derived from another plan.
    - ``UnionPlan``             Set-union of two plans (same datasource).
    - ``JoinPlan``              Relational join of two plans.
    - ``SqlPreview``            Placeholder return type of ``.to_sql()``.
    - ``UnsupportedInM2Error``  Raised when callers reach for M6/M7 surfaces.
"""

from __future__ import annotations

from .dsl import from_
from .plan import (
    BaseModelPlan,
    DerivedQueryPlan,
    JoinPlan,
    PlanSubquery,
    QueryPlan,
    UnionPlan,
    subquery,
)
from .result import SqlPreview, UnsupportedInM2Error

__all__ = [
    "from_",
    "QueryPlan",
    "BaseModelPlan",
    "DerivedQueryPlan",
    "UnionPlan",
    "JoinPlan",
    "PlanSubquery",
    "subquery",
    "SqlPreview",
    "UnsupportedInM2Error",
]
