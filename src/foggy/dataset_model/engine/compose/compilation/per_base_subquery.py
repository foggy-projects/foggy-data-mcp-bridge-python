"""Phase 2 · Base-model subquery slice helpers.

Provides utilities to partition, render, and inject subquery-based
WHERE clause fragments into base-model SQL produced by the v1.3
``SemanticQueryService``.

Design rationale:  the v1.3 ``_add_filter`` / ``SqlFormulaRegistry``
layer treats ``slice.value`` as scalar bind parameters.  Rather than
modifying that contract, we:

1. **Partition** the base plan's ``slice_`` into scalar slices (handled
   by v1.3) and subquery slices (handled here).
2. **Render** each subquery slice into a raw SQL WHERE fragment plus
   its own ordered bind params.
3. **Inject** those fragments into the SQL string returned by
   ``build_query_with_governance``, appending ``AND <fragment>`` at
   the correct position (after existing WHERE, before GROUP BY).

This keeps ``per_base.py`` and ``service.py`` clean, isolating all
compose-subquery awareness here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Callable, List, Optional, Tuple, TYPE_CHECKING

from foggy.dataset_model.engine.compose.plan.plan import (
    BaseModelPlan,
    PlanSubquery,
    QueryPlan,
)

if TYPE_CHECKING:
    from foggy.dataset_model.engine.compose.compilation.compose_planner import (
        _CompileState,
    )


@dataclass(frozen=True)
class WhereInjection:
    """SQL text plus the character offset where fragments were inserted."""

    sql: str
    insert_pos: int


# ---------------------------------------------------------------------------
# 1. Partition — separate subquery slices from scalar slices
# ---------------------------------------------------------------------------


def partition_subquery_slices(
    slice_: Tuple[Any, ...],
) -> Tuple[Tuple[Any, ...], List[Any]]:
    """Split ``slice_`` into ``(scalar_slices, subquery_slices)``.

    A slice entry is classified as a subquery slice if its ``value``
    is a ``QueryPlan`` or ``PlanSubquery``.  Compound ``$and``/``$or``
    entries containing *any* subquery leaf are moved wholesale to the
    subquery bucket — mixing scalar and subquery within a single
    compound is not supported in Phase 2.

    Returns
    -------
    tuple
        ``(scalar_slices_tuple, subquery_slices_list)``
    """
    scalar: list[Any] = []
    subquery: list[Any] = []
    for entry in slice_:
        if _entry_contains_subquery(entry):
            subquery.append(entry)
        else:
            scalar.append(entry)
    return tuple(scalar), subquery


def _entry_contains_subquery(entry: Any) -> bool:
    """True if this slice entry (or any nested child) references a
    ``QueryPlan`` or ``PlanSubquery`` as its value."""
    if not isinstance(entry, dict):
        return False
    # Single-key compound: {$and: [...]}, {$or: [...]}, {$not: ...}
    if len(entry) == 1:
        key, val = next(iter(entry.items()))
        if key in {"$and", "$or"}:
            if isinstance(val, (list, tuple)):
                return any(_entry_contains_subquery(sub) for sub in val)
            return False
        if key == "$not":
            nested = val if isinstance(val, (list, tuple)) else [val]
            return any(_entry_contains_subquery(sub) for sub in nested)
        # Shorthand: {"fieldName": value}
        if key != "value" and "field" not in entry:
            return isinstance(val, (QueryPlan, PlanSubquery))
    # Standard: {"field": ..., "op": ..., "value": ...}
    val = entry.get("value")
    return isinstance(val, (QueryPlan, PlanSubquery))


def strip_subquery_slices(plan: BaseModelPlan) -> BaseModelPlan:
    """Return a copy of *plan* with subquery slice entries removed.

    Uses ``dataclasses.replace`` on the frozen plan.
    """
    scalar, _ = partition_subquery_slices(plan.slice_)
    if len(scalar) == len(plan.slice_):
        return plan  # no change
    return replace(plan, slice_=scalar)


# ---------------------------------------------------------------------------
# 2. Render — compile each subquery slice to a SQL WHERE fragment
# ---------------------------------------------------------------------------


def render_subquery_where_fragments(
    subquery_slices: List[Any],
    *,
    plan: BaseModelPlan,
    state: Any,  # _CompileState
    dialect: str,
) -> Tuple[List[str], List[Any]]:
    """Render subquery slice entries into SQL WHERE fragments + params.

    Each subquery slice is expected to be a simple ``{field, op, value}``
    dict where ``value`` is a ``QueryPlan`` or ``PlanSubquery``.

    Returns
    -------
    tuple
        ``(sql_fragments, all_params)`` where each ``sql_fragment``
        is a standalone condition like
        ``t.partner_id NOT IN (SELECT ...)``.
    """
    from foggy.dataset_model.engine.compose.compilation.errors import (
        ComposeCompileError,
    )
    from foggy.dataset_model.engine.compose.compilation import error_codes

    fragments: list[str] = []
    all_params: list[Any] = []

    for entry in subquery_slices:
        if _is_compound_entry(entry):
            raise ComposeCompileError(
                code=error_codes.UNSUPPORTED_PLAN_SHAPE,
                phase="plan-lower",
                message=(
                    "COMPOSE_SUBQUERY_VALUE_UNSUPPORTED: base model "
                    "subquery slices must be top-level simple "
                    "{field, op, value} entries in Phase 2. Split "
                    "compound $and/$or/$not filters into separate "
                    "top-level slice entries."
                ),
            )
        field, op, value = _extract_slice_parts(entry)
        op_upper = op.strip().upper()

        if op_upper not in {"IN", "NOT IN"}:
            raise ComposeCompileError(
                code=error_codes.UNSUPPORTED_PLAN_SHAPE,
                phase="plan-lower",
                message=(
                    "COMPOSE_SUBQUERY_VALUE_UNSUPPORTED: base model slice "
                    f"subquery is only supported for IN / NOT IN, got {op!r}."
                ),
            )

        rhs_plan, rhs_field = _coerce_plan_subquery_parts(value)
        subquery_sql, subquery_params = _render_plan_subquery_sql(
            rhs_plan,
            rhs_field,
            state=state,
            dialect=dialect,
        )

        # Resolve the LHS field to its physical SQL expression.
        # The base model's field resolution is done by the v1.3 engine
        # at compile time; here we need the physical column for the
        # WHERE injection.  We delegate to the semantic service's
        # model field resolution.
        col_expr = _resolve_base_field_expr(field, plan, state)

        fragments.append(f"{col_expr} {op_upper} {subquery_sql}")
        all_params.extend(subquery_params)

    return fragments, all_params


def _is_compound_entry(entry: Any) -> bool:
    if not isinstance(entry, dict) or len(entry) != 1:
        return False
    key = next(iter(entry.keys()))
    return key in {"$and", "$or", "$not"}


def _extract_slice_parts(entry: dict) -> Tuple[str, str, Any]:
    """Extract ``(field, op, value)`` from a slice entry dict."""
    field = entry.get("field") or entry.get("column")
    op = entry.get("op") or entry.get("operator") or "="
    value = entry.get("value")
    if field is None:
        raise ValueError(
            f"Cannot extract field from subquery slice entry: {entry!r}"
        )
    return field, op, value


def _resolve_base_field_expr(
    field: str,
    plan: BaseModelPlan,
    state: Any,
) -> str:
    """Resolve a QM field name to its physical SQL expression."""
    from foggy.dataset_model.engine.compose.compilation.errors import (
        ComposeCompileError,
    )
    from foggy.dataset_model.engine.compose.compilation import error_codes

    svc = state.semantic_service
    model = svc.get_model(plan.model)
    if model is None:
        raise ComposeCompileError(
            code=error_codes.UNSUPPORTED_PLAN_SHAPE,
            phase="plan-lower",
            message=(
                "COMPOSE_SUBQUERY_FIELD_NOT_FOUND: cannot resolve base "
                f"model {plan.model!r} while lowering subquery slice field "
                f"{field!r}."
            ),
        )

    dialect_name = None
    if hasattr(svc, "_field_formula_dialect_name"):
        dialect_name = svc._field_formula_dialect_name()

    resolved = model.resolve_field(field, dialect_name=dialect_name)
    if resolved and resolved.get("sql_expr"):
        return resolved["sql_expr"]

    dim = model.get_dimension(field) if hasattr(model, "get_dimension") else None
    if dim:
        alias = model.get_table_alias_for_model(model.get_field_model_name(field))
        return f"{alias}.{dim.column}"

    measure = model.get_measure(field) if hasattr(model, "get_measure") else None
    if measure:
        alias = model.get_table_alias_for_model(model.get_field_model_name(field))
        return f"{alias}.{measure.column or measure.name}"

    raise ComposeCompileError(
        code=error_codes.UNSUPPORTED_PLAN_SHAPE,
        phase="plan-lower",
        message=(
            "COMPOSE_SUBQUERY_FIELD_NOT_FOUND: base model subquery slice "
            f"field {field!r} cannot be resolved on model {plan.model!r}."
        ),
    )


def _coerce_plan_subquery_parts(value: Any) -> Tuple[QueryPlan, Optional[str]]:
    """Extract ``(plan, field)`` from a ``PlanSubquery`` or ``QueryPlan``.

    Raises ``ComposeCompileError`` if the value is neither.
    """
    from foggy.dataset_model.engine.compose.compilation.errors import (
        ComposeCompileError,
    )
    from foggy.dataset_model.engine.compose.compilation import error_codes

    if isinstance(value, PlanSubquery):
        return value.plan, value.field
    if isinstance(value, QueryPlan):
        return value, None
    raise ComposeCompileError(
        code=error_codes.UNSUPPORTED_PLAN_SHAPE,
        phase="plan-lower",
        message=(
            "COMPOSE_SUBQUERY_VALUE_UNSUPPORTED: expected QueryPlan "
            f"or PlanSubquery value, got {type(value).__name__}."
        ),
    )


def _render_plan_subquery_sql(
    plan: QueryPlan,
    field: Optional[str],
    *,
    state: Any,
    dialect: str,
) -> Tuple[str, List[Any]]:
    """Compile a subquery plan into ``(sql_fragment, params)`` for WHERE injection.

    The subquery plan is compiled via ``_compile_any``, then wrapped in a
    ``(SELECT <field> FROM (<sql>) AS <alias> WHERE <field> IS NOT NULL)``
    envelope to provide NULL safety for NOT IN semantics.
    """
    from foggy.dataset_model.engine.compose.compilation.compose_planner import (
        _compile_any,
        _render_qualified_ref,
    )
    from foggy.dataset_model.engine.compose.compilation.errors import (
        ComposeCompileError,
    )
    from foggy.dataset_model.engine.compose.compilation import error_codes
    from foggy.dataset_model.engine.compose import ComposedSql
    from foggy.dataset_model.engine.compose.compilation.per_base import CteUnit
    from foggy.dataset_model.engine.compose.schema.derive import derive_schema

    schema = derive_schema(plan)
    names = schema.names()
    if field is None:
        if len(names) != 1:
            raise ComposeCompileError(
                code=error_codes.UNSUPPORTED_PLAN_SHAPE,
                phase="plan-lower",
                message=(
                    "COMPOSE_SUBQUERY_FIELD_AMBIGUOUS: implicit QueryPlan "
                    "slice.value requires the subquery plan to project "
                    f"exactly one column; projected columns: {names!r}. "
                    "Use subquery(plan, '<field>') to select one column."
                ),
            )
        field = names[0]
    if field not in schema.name_set():
        raise ComposeCompileError(
            code=error_codes.UNSUPPORTED_PLAN_SHAPE,
            phase="plan-lower",
            message=(
                "COMPOSE_SUBQUERY_FIELD_NOT_FOUND: subquery(plan, field) "
                f"references {field!r}, but the plan projects {names!r}."
            ),
        )

    compiled = _compile_any(plan, state)
    if isinstance(compiled, CteUnit):
        rhs_sql = compiled.sql
        rhs_params = list(compiled.params or [])
    elif isinstance(compiled, ComposedSql):
        rhs_sql = compiled.sql
        rhs_params = list(compiled.params or [])
    else:
        raise ComposeCompileError(
            code=error_codes.UNSUPPORTED_PLAN_SHAPE,
            phase="plan-lower",
            message=(
                "COMPOSE_SUBQUERY_VALUE_UNSUPPORTED: subquery plan "
                f"compiled to unsupported shape {type(compiled).__name__}."
            ),
        )

    alias = state.next_alias()
    field_ref = _render_qualified_ref(alias, field, dialect)
    sql = (
        f"(SELECT {field_ref}\n"
        f"FROM ({rhs_sql}) AS {alias}\n"
        f"WHERE {field_ref} IS NOT NULL)"
    )
    return sql, rhs_params

# Regex to find the boundary between WHERE and GROUP BY / ORDER BY /
# HAVING / LIMIT / end-of-string.  The v1.3 engine produces SQL in a
# predictable clause order: SELECT … FROM … [JOIN …] [WHERE …]
# [GROUP BY …] [HAVING …] [ORDER BY …] [LIMIT …]
_CLAUSE_BOUNDARY = re.compile(
    r"(\bGROUP\s+BY\b|\bHAVING\b|\bORDER\s+BY\b|\bLIMIT\b)",
    re.IGNORECASE,
)


def inject_where_fragments(
    base_sql: str,
    fragments: List[str],
) -> str:
    """Append ``AND <fragment>`` to the base SQL's WHERE clause.

    If the base SQL has no WHERE clause, insert ``WHERE <fragments>``.
    The injection point is before the first GROUP BY / HAVING / ORDER BY
    / LIMIT clause, or at the end of the SQL if none is present.

    Parameters
    ----------
    base_sql : str
        SQL produced by ``build_query_with_governance``.
    fragments : list[str]
        SQL condition strings (e.g. ``"t.partner_id NOT IN (SELECT ...)"``).

    Returns
    -------
    str
        Modified SQL with subquery conditions injected.
    """
    return inject_where_fragments_at_position(base_sql, fragments).sql


def inject_where_fragments_with_params(
    base_sql: str,
    base_params: List[Any],
    fragments: List[str],
    fragment_params: List[Any],
) -> Tuple[str, List[Any]]:
    """Inject WHERE fragments and merge params by SQL placeholder order."""
    injection = inject_where_fragments_at_position(base_sql, fragments)
    if not fragments:
        return injection.sql, list(base_params or [])

    # Internal SQL emitted by the compose engine uses '?' only for bind
    # placeholders, so counting placeholders before the insertion point
    # gives the correct splice index for positional params.
    insert_param_index = base_sql[:injection.insert_pos].count("?")
    params = list(base_params or [])
    merged_params = (
        params[:insert_param_index]
        + list(fragment_params or [])
        + params[insert_param_index:]
    )
    return injection.sql, merged_params


def inject_where_fragments_at_position(
    base_sql: str,
    fragments: List[str],
) -> WhereInjection:
    """Inject WHERE fragments and report the insertion offset in *base_sql*."""
    if not fragments:
        return WhereInjection(sql=base_sql, insert_pos=len(base_sql))

    # Combined condition to inject
    extra_condition = " AND ".join(fragments)

    # Find WHERE position
    where_match = re.search(r"\bWHERE\b", base_sql, re.IGNORECASE)

    if where_match is not None:
        # WHERE exists — find the boundary after WHERE
        after_where = where_match.end()
        boundary = _CLAUSE_BOUNDARY.search(base_sql, after_where)
        if boundary is not None:
            insert_pos = boundary.start()
            # Insert before the boundary clause
            return WhereInjection(
                sql=(
                    base_sql[:insert_pos].rstrip()
                    + " AND "
                    + extra_condition
                    + "\n"
                    + base_sql[insert_pos:]
                ),
                insert_pos=insert_pos,
            )
        else:
            # No boundary — append at end
            insert_pos = len(base_sql)
            return WhereInjection(
                sql=base_sql.rstrip() + " AND " + extra_condition,
                insert_pos=insert_pos,
            )
    else:
        # No WHERE — insert before first boundary
        boundary = _CLAUSE_BOUNDARY.search(base_sql)
        if boundary is not None:
            insert_pos = boundary.start()
            return WhereInjection(
                sql=(
                    base_sql[:insert_pos].rstrip()
                    + "\nWHERE "
                    + extra_condition
                    + "\n"
                    + base_sql[insert_pos:]
                ),
                insert_pos=insert_pos,
            )
        else:
            # No WHERE, no GROUP BY, etc. — append at end
            insert_pos = len(base_sql)
            return WhereInjection(
                sql=base_sql.rstrip() + "\nWHERE " + extra_condition,
                insert_pos=insert_pos,
            )
