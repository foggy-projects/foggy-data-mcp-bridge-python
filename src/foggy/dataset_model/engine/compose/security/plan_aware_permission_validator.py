"""G10 PR4 · Compose-layer plan-aware permission validation.

Cross-language mirror of Java
``ComposePlanAwarePermissionValidator``.

Independent module, deliberately separate from the global Python
field-access enforcement (``SemanticServiceV3._resolve_effective_visible``
+ legacy step) which assumes a single flat ``field_access`` whitelist.
The Compose pipeline can route a column through multiple plans, so the
routing rule (column → producing plan → that plan's binding's
``field_access``) belongs in its own validator.

Pipeline position
-----------------
Called by ``compile_to_composed_sql`` after schema derivation, before
SQL emission, only when ``feature_flags.g10_enabled()`` is True. The
single-base / pre-G10 path is unchanged.

Validation rules (per G10 spec §6.4)
------------------------------------
1. F5 plan-qualified — currently rejected at the DSL boundary by
   ``column_normalizer._normalize_map`` with ``COLUMN_PLAN_NOT_VISIBLE``.
   The plan-qualified routing branch is in place for parity with Java
   but is dead code in Python until F5 lands.

2. Bare field (string in ``plan.columns``) — resolve via
   :class:`OutputSchema`:
   * Not in schema → ``COLUMN_FIELD_NOT_FOUND``.
   * Ambiguous in schema → ``JOIN_AMBIGUOUS_COLUMN`` (caller must
     disambiguate via F5 once G5 Phase 2 lands).
   * Unique in schema — if the matched ``ColumnSpec`` carries
     ``plan_provenance``, route to that plan's binding; otherwise
     (single-base case) skip and let the caller's existing
     fieldAccess pipeline handle it.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

from ..plan.plan import (
    AggregateColumn,
    BaseModelPlan,
    DerivedQueryPlan,
    JoinPlan,
    PlanColumnRef,
    ProjectedColumn,
    QueryPlan,
    UnionPlan,
    WindowColumn,
)
from ..schema import error_codes
from ..schema.alias import extract_column_alias
from ..schema.errors import ComposeSchemaError
from ..schema.output_schema import ColumnSpec, OutputSchema
from .plan_field_access_context import PlanFieldAccessContext


def validate(
    plan: QueryPlan, schema: OutputSchema, plan_ctx: PlanFieldAccessContext
) -> None:
    """Validate every top-level column reference in ``plan``'s output
    against the per-plan whitelists in ``plan_ctx``.

    Top-level here means the columns the user wrote in the outermost
    plan's ``columns``. Inner-plan columns were already validated when
    their plan was schema-derived; we don't double-walk here.

    Parameters
    ----------
    plan:
        The root plan whose columns to validate.
    schema:
        Plan's already-derived :class:`OutputSchema` (post-PR2:
        ambiguous-column-aware).
    plan_ctx:
        Per-plan binding view; never ``None`` (use
        ``PlanFieldAccessContext.empty()`` when no bindings are
        pre-registered).

    Raises
    ------
    ComposeSchemaError
        With code one of ``FIELD_ACCESS_DENIED``,
        ``COLUMN_PLAN_NOT_BOUND``, ``COLUMN_FIELD_NOT_FOUND``, or
        ``JOIN_AMBIGUOUS_COLUMN`` — and ``phase=permission-validate``.
    """
    if plan is None:
        raise TypeError("validate expects a non-null QueryPlan")
    if schema is None:
        raise TypeError("validate expects a non-null OutputSchema")
    if plan_ctx is None:
        raise TypeError("validate expects a non-null PlanFieldAccessContext")
    for column in _top_level_columns(plan):
        _validate_column(column, schema, plan_ctx)


# ---------------------------------------------------------------------------
# Per-column dispatch
# ---------------------------------------------------------------------------


def _validate_column(
    column: object, schema: OutputSchema, plan_ctx: PlanFieldAccessContext
) -> None:
    # F5 plan-qualified — direct routing. Currently dead path in Python
    # because ``from_()`` rejects ``{plan, field}`` syntax with
    # ``COLUMN_PLAN_NOT_VISIBLE`` (G5 Phase 2 placeholder). Keep the
    # branch for cross-language symmetry with Java.
    ref = _extract_plan_ref(column)
    if ref is not None and ref.plan is not None:
        _validate_plan_qualified(ref, plan_ctx)
        return
    field_name = _extract_field_name(column)
    if field_name is None:
        # Expression-only (e.g. SUM(amount)) — defer to legacy pipeline.
        return
    _validate_bare_field(field_name, schema, plan_ctx)


def _validate_plan_qualified(
    ref: PlanColumnRef, plan_ctx: PlanFieldAccessContext
) -> None:
    plan = ref.plan
    if not plan_ctx.contains_plan(plan):
        raise ComposeSchemaError(
            code=error_codes.COLUMN_PLAN_NOT_BOUND,
            message=(
                f"Plan-qualified column reference {ref.name!r} targets a "
                f"QueryPlan that is not registered in the active "
                f"PlanFieldAccessContext (plan={type(plan).__name__})."
            ),
            phase=error_codes.PHASE_PERMISSION_VALIDATE,
            offending_field=ref.name,
        )
    whitelist = plan_ctx.resolve_field_access(plan)
    if whitelist is None:
        # Plan bound but no fieldAccess — unrestricted by spec.
        return
    base = _strip_dimension_suffix(ref.name)
    if base not in whitelist:
        raise _field_access_denied(
            ref.name,
            f"plan-qualified reference {ref.name!r} denied by plan's "
            f"field_access whitelist (allowed: {len(whitelist)} fields)."
        )


def _validate_bare_field(
    field_name: str, schema: OutputSchema, plan_ctx: PlanFieldAccessContext
) -> None:
    matches = schema.get_all(field_name)
    if not matches:
        raise ComposeSchemaError(
            code=error_codes.COLUMN_FIELD_NOT_FOUND,
            message=(
                f"Bare-field reference {field_name!r} is not in the plan's "
                f"output schema. Available column names: {sorted(schema.name_set())}"
            ),
            phase=error_codes.PHASE_PERMISSION_VALIDATE,
            offending_field=field_name,
        )
    if schema.is_ambiguous(field_name):
        raise ComposeSchemaError(
            code=error_codes.JOIN_AMBIGUOUS_COLUMN,
            message=(
                f"Bare-field reference {field_name!r} is ambiguous: "
                f"{len(matches)} plans in this join produce a column with "
                f"that name. Disambiguate by writing "
                f"{{plan: <handle>, field: {field_name!r}}} (F5 plan-qualified)."
            ),
            phase=error_codes.PHASE_PERMISSION_VALIDATE,
            offending_field=field_name,
        )
    sole = matches[0]
    provenance: Optional[QueryPlan] = (
        sole.plan_provenance.resolve() if sole.plan_provenance is not None else None
    )
    if provenance is None:
        # Single-base / no-provenance case — defer to legacy pipeline.
        return
    if not plan_ctx.contains_plan(provenance):
        raise ComposeSchemaError(
            code=error_codes.COLUMN_PLAN_NOT_BOUND,
            message=(
                f"Bare-field {field_name!r} resolved to plan provenance "
                f"{type(provenance).__name__} but that plan is not registered "
                f"in the active PlanFieldAccessContext."
            ),
            phase=error_codes.PHASE_PERMISSION_VALIDATE,
            offending_field=field_name,
        )
    whitelist = plan_ctx.resolve_field_access(provenance)
    if whitelist is None:
        return
    base = _strip_dimension_suffix(field_name)
    if base not in whitelist:
        raise _field_access_denied(
            field_name,
            f"bare-field {field_name!r} resolved to a plan whose "
            f"field_access whitelist excludes it.",
        )


# ---------------------------------------------------------------------------
# Column-shape extractors
# ---------------------------------------------------------------------------


def _extract_plan_ref(column: object) -> Optional[PlanColumnRef]:
    """Return the ``PlanColumnRef`` wrapped by a column entry, or
    ``None`` when the entry has no plan reference attached."""
    if isinstance(column, PlanColumnRef):
        return column
    if isinstance(column, ProjectedColumn) and isinstance(column.expr, PlanColumnRef):
        return column.expr
    if isinstance(column, AggregateColumn):
        return column.ref
    if isinstance(column, WindowColumn):
        return column.ref
    return None


def _extract_field_name(column: object) -> Optional[str]:
    """Return the bare column name for a column entry without a plan
    ref, or ``None`` when the entry is an expression that doesn't map
    to a single field name. Reuses :func:`extract_column_alias` so the
    ``"expr AS alias"`` parsing matches :class:`OutputSchema`'s
    derivation byte-for-byte."""
    if isinstance(column, str):
        return extract_column_alias(column).output_name
    if isinstance(column, ProjectedColumn):
        return column.alias
    return None


def _strip_dimension_suffix(field_name: Optional[str]) -> Optional[str]:
    """Drop the ``$caption`` / ``$id`` dimension suffix used by the QM
    dimension-attribute syntax so ``"salesDate$id"`` matches the bare
    ``"salesDate"`` entry of a fieldAccess whitelist."""
    if field_name is None:
        return None
    idx = field_name.find("$")
    return field_name[:idx] if idx > 0 else field_name


# ---------------------------------------------------------------------------
# Top-level column extraction
# ---------------------------------------------------------------------------


def _top_level_columns(plan: QueryPlan) -> Iterable[object]:
    """Return the columns to validate for ``plan``. Joins/unions
    surface their merged outputs (validated when the user references
    them in a wrapping derived plan); base / derived plans expose
    their own ``columns``."""
    if isinstance(plan, DerivedQueryPlan):
        return plan.columns
    if isinstance(plan, BaseModelPlan):
        return plan.columns
    return ()


def _field_access_denied(field: str, detail: str) -> ComposeSchemaError:
    return ComposeSchemaError(
        code=error_codes.FIELD_ACCESS_DENIED,
        message=f"Field access denied: {detail}",
        phase=error_codes.PHASE_PERMISSION_VALIDATE,
        offending_field=field,
    )
