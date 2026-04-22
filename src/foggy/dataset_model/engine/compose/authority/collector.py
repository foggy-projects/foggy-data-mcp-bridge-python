"""``collect_base_models`` — walk a ``QueryPlan`` tree and return the
unique ``BaseModelPlan`` nodes by QM model name (first occurrence wins).

Why we collect by model name, not by ``BaseModelPlan`` identity
---------------------------------------------------------------
The same QM (``SaleOrderQM``) referenced twice in a script will
materialise as two distinct ``BaseModelPlan`` instances (different
columns / slice / limit etc. per call site). For authority resolution,
however, ``(principal, namespace, model)`` is the cache key — two
references to the same QM in the same script must produce a single
``AuthorityRequest.models[i]`` entry and a single ``ModelBinding``.

So the dedup rule is:

* Walk the tree in left-to-right preorder (matches ``QueryPlan.base_model_plans``).
* Keep the **first** ``BaseModelPlan`` encountered per ``.model`` string.
* Later duplicates are discarded; they all consume the same binding.

M5 does not care about per-occurrence column/slice differences at
authority level — deniedColumns filter physical tables, not QM call
sites. The column-level filtering happens later (M6) when the SQL
compiler applies the binding to each ``BaseModelPlan`` instance
individually.
"""

from __future__ import annotations

from typing import List

from ..plan import BaseModelPlan, QueryPlan


def collect_base_models(plan: QueryPlan) -> List[BaseModelPlan]:
    """Return the unique ``BaseModelPlan`` nodes in ``plan``, one per
    ``.model`` name, in first-occurrence order.

    Parameters
    ----------
    plan:
        Root of a ``QueryPlan`` tree. Any concrete plan type is valid;
        the function dispatches through ``QueryPlan.base_model_plans()``
        which already knows how to recurse over ``DerivedQueryPlan``,
        ``UnionPlan``, and ``JoinPlan``.

    Returns
    -------
    List[BaseModelPlan]
        Ordered, duplicate-free (by ``.model``) list. Empty input trees
        do not exist in practice — every plan chain bottoms out at a
        ``BaseModelPlan`` — but ``[]`` would be returned without error
        if one somehow did.

    Raises
    ------
    TypeError
        When ``plan`` is not a ``QueryPlan`` instance. Fail-closed: the
        authority pipeline refuses to bind unknown node shapes.
    """
    if not isinstance(plan, QueryPlan):
        raise TypeError(
            f"collect_base_models(plan) requires a QueryPlan instance, "
            f"got {type(plan).__name__}"
        )

    seen_models: set = set()
    unique: List[BaseModelPlan] = []
    for leaf in plan.base_model_plans():
        # base_model_plans() returns BaseModelPlan instances by contract;
        # defensively filter in case a subclass ever violates it.
        if not isinstance(leaf, BaseModelPlan):
            raise TypeError(
                f"QueryPlan.base_model_plans() yielded non-BaseModelPlan "
                f"{type(leaf).__name__}; refusing to proceed"
            )
        if leaf.model in seen_models:
            continue
        seen_models.add(leaf.model)
        unique.append(leaf)
    return unique
