"""``from_()`` — the canonical Compose Query entry point.

Named with a trailing underscore because ``from`` is a hard keyword in
Python. The spec (``P0-ComposeQuery-QueryPlan派生查询与关系复用规范-需求.md``
§"命名约定") explicitly calls this out: JavaScript side uses ``from(...)``
as a global function; Python side exposes ``from_(...)`` with identical
semantics.

Call shapes
-----------

* Base-model (leaf):

    ``from_(model="SaleOrderQM", columns=[...], slice=[...], group_by=[...])``

* Kernel derived (equivalent to ``plan.query(...)``):

    ``from_(source=some_plan, columns=[...], slice=[...])``

``model`` and ``source`` are mutually exclusive — passing both or neither
raises :class:`ValueError`. Every other parameter is shared between the
two shapes.

This is deliberately a plain function, not a class — it is the single
symbol the sandbox pierces into the JavaScript host (see M9 Layer A),
so keeping it stateless makes the sandbox wiring trivial.
"""

from __future__ import annotations

from typing import Any, List, Optional

from .column_normalizer import normalize_columns_to_strings as _normalize_columns_to_strings
from .plan import (
    BaseModelPlan,
    DerivedQueryPlan,
    QueryPlan,
    _freeze_columns,
    _freeze_opt_list,
    _freeze_opt_order_by_list,
    _freeze_opt_str_list,
    _require_plan,
    _validate_columns,
    _validate_pagination,
)
from ..sandbox import validate_slice


def from_(
    *,
    model: Optional[str] = None,
    source: Optional[QueryPlan] = None,
    columns: Optional[List[str]] = None,
    slice: Optional[List[Any]] = None,
    having: Optional[List[Any]] = None,
    group_by: Optional[List[str]] = None,
    order_by: Optional[List[Any]] = None,
    calculated_fields: Optional[List[Any]] = None,
    limit: Optional[int] = None,
    start: Optional[int] = None,
    distinct: bool = False,
) -> QueryPlan:
    """Build a ``BaseModelPlan`` (when ``model=`` is given) or a
    ``DerivedQueryPlan`` (when ``source=`` is given).

    All parameters keyword-only — positional invocation is a TypeError,
    matching the JavaScript ``from({...})`` object-literal convention.

    Validation
    ----------
    * Exactly one of ``model`` or ``source`` must be set.
    * ``limit`` / ``start`` are non-negative ints or ``None``.
    * ``source``, when given, must be a ``QueryPlan`` instance.

    Schema-level validation (does each ``columns[i]`` resolve against the
    source's output schema?) is M4 scope. M2 only checks shape.
    """
    has_model = model is not None
    has_source = source is not None

    if has_model and has_source:
        raise ValueError(
            "from_() accepts either model= (base model) or source= "
            "(derived), not both"
        )
    if not has_model and not has_source:
        raise ValueError(
            "from_() requires exactly one of model= or source="
        )

    # G5 Phase 1 (F4): normalize {field, agg?, as?} dict entries to canonical
    # string form (e.g. "SUM(amount) AS total"). String entries pass through
    # unchanged. count_distinct lowers to "COUNT_DISTINCT(field)" which the
    # SQL engine auto-translates to COUNT(DISTINCT field).
    #
    # `from_()` is the dict-based path; downstream BaseModelPlan / DerivedQueryPlan
    # validation strictly requires strings (see `_validate_columns`), so we
    # normalize to strings here.
    if columns is not None:
        columns = _normalize_columns_to_strings(columns)

    # Run column / pagination validation once, up-front, so the error
    # message is uniform across both shapes.
    if columns is None:
        columns = []
    cols = _freeze_columns(columns)
    # Legacy from_() always requires columns — OO API (Query.from) handles
    # columns via .select() later, but from_() is the dict-based path.
    if not cols:
        raise ValueError("from_().columns must be non-empty")
    _validate_columns(cols, "from_().columns")
    _validate_pagination(limit, start, "from_()")
    validate_slice(slice, "plan-build")
    validate_slice(having, "plan-build")

    slice_tuple = _freeze_opt_list(slice)
    having_tuple = _freeze_opt_list(having)
    group_by_tuple = _freeze_opt_str_list(group_by)
    order_by_tuple = _freeze_opt_order_by_list(order_by)
    calculated_fields_tuple = _freeze_opt_list(calculated_fields)

    if has_model:
        if not isinstance(model, str) or not model:
            raise ValueError("from_(model=...) must be a non-empty str")
        return BaseModelPlan(
            model=model,
            columns=cols,
            slice_=slice_tuple,
            having=having_tuple,
            group_by=group_by_tuple,
            order_by=order_by_tuple,
            calculated_fields=calculated_fields_tuple,
            limit=limit,
            start=start,
            distinct=distinct,
        )

    # has_source branch
    _require_plan(source, "from_(source=...)")
    if having_tuple:
        raise ValueError(
            "from_(source=...) does not accept having; use "
            "source.query(slice=[...]) for derived-plan post-result filters."
        )
    if calculated_fields_tuple:
        raise ValueError(
            "from_(source=...) does not accept calculatedFields; project "
            "derived expressions in columns with AS aliases, then add "
            "another .query(...) stage for post-result filtering or ordering."
        )
    return DerivedQueryPlan(
        source=source,
        columns=cols,
        slice_=slice_tuple,
        group_by=group_by_tuple,
        order_by=order_by_tuple,
        limit=limit,
        start=start,
        distinct=distinct,
    )
