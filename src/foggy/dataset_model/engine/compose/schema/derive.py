"""Walk a ``QueryPlan`` tree and derive each node's declared output schema.

The rules encoded here come directly from
``docs/8.2.0.beta/P0-ComposeQuery-QueryPlan派生查询与关系复用规范-需求.md``
§核心语义 and §union/§join 规范:

* Derived query may only reference names present in source's output.
* Union aligns columns positionally; left side defines the output shape,
  right side must match on count.
* Join preserves both sides' columns; any output-name collision must be
  resolved by explicit alias in a subsequent ``.query()`` step.
* Duplicate output names inside a single plan's ``columns`` list is
  rejected (usually the user aliased two entries to the same name).

What the rules do NOT yet do (deferred)
---------------------------------------
* Type-compatibility check on union branches (needs M6 type inference).
* ``fieldAccess``/``deniedColumns`` subtraction from BaseModel output
  (M5 applies authority binding).
* Resolving dimension-path references like ``customer$province`` in
  derived plans — M4 treats dimension paths as opaque identifiers.
  Once the column is projected (aliased or not) it becomes a reference
  target; if a derived plan asks for ``customer$province`` but the
  source only projected ``customer$id``, this derivation raises
  :class:`~.errors.ComposeSchemaError` with ``derived-query/unknown-field``.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Set

from ..plan import (
    BaseModelPlan,
    DerivedQueryPlan,
    JoinPlan,
    QueryPlan,
    UnionPlan,
)
from . import error_codes
from .alias import ColumnAliasParts, extract_column_alias
from .errors import ComposeSchemaError
from .output_schema import ColumnSpec, OutputSchema


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def derive_schema(plan: QueryPlan) -> OutputSchema:
    """Return ``plan``'s declared output schema.

    Does NOT cache on the plan object — plans are frozen dataclasses and
    equal values produce equal schemas, so callers that need repeated
    access are free to memoise externally. Derivation is fast (linear in
    the total column count across the tree); the compiler in M6 will
    handle subtree de-duplication via a dedicated plan-hash cache.
    """
    if not isinstance(plan, QueryPlan):
        raise TypeError(
            f"derive_schema expects a QueryPlan instance, got "
            f"{type(plan).__name__}"
        )
    return _derive(plan, path="")


# ---------------------------------------------------------------------------
# Internal dispatch
# ---------------------------------------------------------------------------


def _derive(plan: QueryPlan, *, path: str) -> OutputSchema:
    if isinstance(plan, BaseModelPlan):
        return _derive_base_model(plan, path=path)
    if isinstance(plan, DerivedQueryPlan):
        return _derive_derived(plan, path=path)
    if isinstance(plan, UnionPlan):
        return _derive_union(plan, path=path)
    if isinstance(plan, JoinPlan):
        return _derive_join(plan, path=path)
    # No concrete subclass matched — this should never happen given
    # QueryPlan is sealed in practice via the four subclasses above;
    # surface as a developer-facing error rather than silently returning.
    raise TypeError(
        f"derive_schema: unknown QueryPlan subclass {type(plan).__name__!r}"
    )


# ---------------------------------------------------------------------------
# Per-plan derivations
# ---------------------------------------------------------------------------


def _derive_base_model(plan: BaseModelPlan, *, path: str) -> OutputSchema:
    """BaseModelPlan: output columns come verbatim from ``plan.columns``
    after alias resolution. ``group_by`` / ``order_by`` reference the
    current plan's output names (i.e. post-alias), not the raw QM
    fields behind the scenes — this matches the spec example shape
    ``groupBy: ['customerId']`` where ``customerId`` is an alias."""
    current_path = f"{path}BaseModelPlan[{plan.model}]"
    specs = _columns_to_specs(
        plan.columns, source_model=plan.model, plan_path=current_path,
    )
    output_schema = OutputSchema.of(specs)
    _validate_group_and_order_by(
        plan.group_by, plan.order_by, output_schema, plan_path=current_path,
    )
    return output_schema


def _derive_derived(plan: DerivedQueryPlan, *, path: str) -> OutputSchema:
    """DerivedQueryPlan: validate every ``columns[*]`` reference resolves
    in ``source.output_schema``; produce a new schema from the (possibly
    re-aliased) columns."""
    source_path = f"{path}DerivedQueryPlan/source/"
    source_schema = _derive(plan.source, path=source_path)
    source_names = source_schema.name_set()

    current_path = f"{path}DerivedQueryPlan"
    parts_list = [
        _parse_alias_or_raise(c, plan_path=current_path) for c in plan.columns
    ]

    # Every *expression* must reference only names in source_names.
    # We can't fully parse SQL-ish expressions at M4 (that's M6's job),
    # but we can catch the common "bare identifier" miss — the single
    # most frequent class of mistake when writing derived plans.
    for parts in parts_list:
        referenced = _extract_bare_identifiers(parts.expression)
        for ident in referenced:
            if _is_reserved_token(ident):
                continue
            if ident not in source_names:
                raise ComposeSchemaError(
                    code=error_codes.DERIVED_QUERY_UNKNOWN_FIELD,
                    message=(
                        f"derived query references unknown field "
                        f"{ident!r} not present in source's output schema "
                        f"(available: {sorted(source_names)!r})"
                    ),
                    phase=error_codes.PHASE_SCHEMA_DERIVE,
                    plan_path=current_path,
                    offending_field=ident,
                )

    specs = _parts_to_specs(
        parts_list, source_model=None, plan_path=current_path
    )
    output_schema = OutputSchema.of(specs)

    # ``group_by`` / ``order_by`` reference the CURRENT plan's output
    # names, not the source's. This matches the spec:
    # `groupBy: ['arOverdue']` where ``arOverdue`` is an alias defined
    # by this plan's own ``columns``.
    _validate_group_and_order_by(
        plan.group_by, plan.order_by, output_schema, plan_path=current_path,
    )
    return output_schema


def _derive_union(plan: UnionPlan, *, path: str) -> OutputSchema:
    """UnionPlan: left defines the output shape; right must match count.
    Column names are taken from the left side's alias-resolved columns;
    right-side names are ignored for output purposes (but validated for
    count)."""
    left_path = f"{path}UnionPlan/left/"
    right_path = f"{path}UnionPlan/right/"
    left_schema = _derive(plan.left, path=left_path)
    right_schema = _derive(plan.right, path=right_path)

    if len(left_schema) != len(right_schema):
        raise ComposeSchemaError(
            code=error_codes.UNION_COLUMN_COUNT_MISMATCH,
            message=(
                f"union column count mismatch: left has "
                f"{len(left_schema)} columns "
                f"({left_schema.names()!r}), right has "
                f"{len(right_schema)} columns "
                f"({right_schema.names()!r})"
            ),
            phase=error_codes.PHASE_SCHEMA_DERIVE,
            plan_path=f"{path}UnionPlan",
        )

    # Output schema takes left's names/expressions verbatim; drop any
    # source_model attribution since union erases per-source identity.
    merged: List[ColumnSpec] = [
        ColumnSpec(
            name=c.name,
            expression=c.expression,
            source_model=None,
            has_explicit_alias=c.has_explicit_alias,
        )
        for c in left_schema.columns
    ]
    return OutputSchema.of(merged)


def _derive_join(plan: JoinPlan, *, path: str) -> OutputSchema:
    """JoinPlan: validate ``on[*]`` refers to both sides' visible fields;
    merge outputs preserving order (left first, then right); reject any
    output-name collision that the user hasn't disambiguated."""
    left_path = f"{path}JoinPlan/left/"
    right_path = f"{path}JoinPlan/right/"
    left_schema = _derive(plan.left, path=left_path)
    right_schema = _derive(plan.right, path=right_path)
    current_path = f"{path}JoinPlan"

    left_names = left_schema.name_set()
    right_names = right_schema.name_set()

    for i, j in enumerate(plan.on):
        if j.left not in left_names:
            raise ComposeSchemaError(
                code=error_codes.JOIN_ON_LEFT_UNKNOWN_FIELD,
                message=(
                    f"JoinPlan.on[{i}].left={j.left!r} not in left side's "
                    f"output schema {sorted(left_names)!r}"
                ),
                phase=error_codes.PHASE_SCHEMA_DERIVE,
                plan_path=current_path,
                offending_field=j.left,
            )
        if j.right not in right_names:
            raise ComposeSchemaError(
                code=error_codes.JOIN_ON_RIGHT_UNKNOWN_FIELD,
                message=(
                    f"JoinPlan.on[{i}].right={j.right!r} not in right "
                    f"side's output schema {sorted(right_names)!r}"
                ),
                phase=error_codes.PHASE_SCHEMA_DERIVE,
                plan_path=current_path,
                offending_field=j.right,
            )

    # Merge outputs. Any name collision = user mistake; force them to
    # disambiguate via a following ``.query()`` with explicit aliases.
    overlap = left_names & right_names
    if overlap:
        raise ComposeSchemaError(
            code=error_codes.JOIN_OUTPUT_COLUMN_CONFLICT,
            message=(
                f"JoinPlan output has name collisions {sorted(overlap)!r}; "
                "resolve via an explicit alias in a subsequent .query(...) "
                "step (e.g. `a.partnerName AS salesPartnerName`)"
            ),
            phase=error_codes.PHASE_SCHEMA_DERIVE,
            plan_path=current_path,
            offending_field=next(iter(sorted(overlap))),
        )

    merged: List[ColumnSpec] = list(left_schema.columns) + list(
        right_schema.columns
    )
    # Strip source_model on merged output — once joined, which side the
    # column came from is not a reliable attribute downstream.
    merged = [
        ColumnSpec(
            name=c.name,
            expression=c.expression,
            source_model=None,
            has_explicit_alias=c.has_explicit_alias,
        )
        for c in merged
    ]
    return OutputSchema.of(merged)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _columns_to_specs(
    columns: Iterable[str], *, source_model: Optional[str], plan_path: str
) -> List[ColumnSpec]:
    parts_list = [
        _parse_alias_or_raise(c, plan_path=plan_path) for c in columns
    ]
    return _parts_to_specs(
        parts_list, source_model=source_model, plan_path=plan_path
    )


def _parts_to_specs(
    parts_list: List[ColumnAliasParts],
    *,
    source_model: Optional[str],
    plan_path: str,
) -> List[ColumnSpec]:
    seen: Set[str] = set()
    specs: List[ColumnSpec] = []
    for parts in parts_list:
        if parts.output_name in seen:
            raise ComposeSchemaError(
                code=error_codes.DUPLICATE_OUTPUT_COLUMN,
                message=(
                    f"duplicate output column {parts.output_name!r}; "
                    "the plan projects the same output name twice. "
                    "Use explicit aliases to disambiguate."
                ),
                phase=error_codes.PHASE_SCHEMA_DERIVE,
                plan_path=plan_path,
                offending_field=parts.output_name,
            )
        seen.add(parts.output_name)
        specs.append(
            ColumnSpec(
                name=parts.output_name,
                expression=parts.expression,
                source_model=source_model,
                has_explicit_alias=parts.has_alias,
            )
        )
    return specs


def _parse_alias_or_raise(column_spec: str, *, plan_path: str) -> ColumnAliasParts:
    try:
        return extract_column_alias(column_spec)
    except ValueError as e:
        raise ComposeSchemaError(
            code=error_codes.COLUMN_SPEC_MALFORMED,
            message=f"malformed column spec: {e}",
            phase=error_codes.PHASE_PLAN_BUILD,
            plan_path=plan_path,
            cause=e,
        ) from e


def _validate_group_and_order_by(
    group_by: Iterable[str],
    order_by: Iterable[str],
    output_schema: OutputSchema,
    *,
    plan_path: str,
) -> None:
    """Validate both ``group_by`` and ``order_by`` against this plan's
    own output-schema names. Shared by BaseModelPlan and
    DerivedQueryPlan because the rule is identical — references must be
    output names (i.e. post-alias), not raw QM fields or source names.
    """
    output_names = output_schema.name_set()
    for field_name in group_by:
        _assert_reference_visible(
            field_name,
            output_names,
            source_label="this plan's output columns",
            plan_path=plan_path,
            slot="group_by",
        )
    for ob in order_by:
        # strip leading '-' for desc sort
        stripped = ob[1:] if ob.startswith("-") else ob
        _assert_reference_visible(
            stripped,
            output_names,
            source_label="this plan's output columns",
            plan_path=plan_path,
            slot="order_by",
        )


def _assert_reference_visible(
    field_name: str,
    visible: frozenset,
    *,
    source_label: str,
    plan_path: str,
    slot: str,
) -> None:
    if field_name not in visible:
        raise ComposeSchemaError(
            code=error_codes.DERIVED_QUERY_UNKNOWN_FIELD,
            message=(
                f"{slot} references unknown field {field_name!r} not in "
                f"{source_label} (available: {sorted(visible)!r})"
            ),
            phase=error_codes.PHASE_SCHEMA_DERIVE,
            plan_path=plan_path,
            offending_field=field_name,
        )


# ---------------------------------------------------------------------------
# Bare-identifier scan
# ---------------------------------------------------------------------------

# Match identifiers in a loose way: letter/underscore start, then
# letter/digit/underscore/``$`` (dimension-path). Crucially excludes
# numbers, string literals (quoted), and punctuation.
#
# We skip over string literals by running a simple state machine before
# the regex; quoted segments (single- or double-quoted) are masked out.
_IDENT_SCAN = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")


# Reserved tokens / functions / keywords that appear inside allowed
# expressions and must NOT be validated as field references.
_RESERVED_TOKENS: frozenset = frozenset(
    {
        # SQL-ish aggregate / scalar / control
        "SUM", "COUNT", "AVG", "MIN", "MAX",
        "IIF", "IF", "CASE", "WHEN", "THEN", "ELSE", "END",
        "COALESCE", "NULLIF",
        "IS_NULL", "IS_NOT_NULL", "BETWEEN", "IN", "NOT",
        "DATE_DIFF", "DATE_ADD", "NOW",
        "AND", "OR",
        # Booleans / null
        "TRUE", "FALSE", "NULL",
        # Wildcard / placeholder
        "DISTINCT",
    }
)


def _is_reserved_token(ident: str) -> bool:
    return ident.upper() in _RESERVED_TOKENS


def _extract_bare_identifiers(expression: str) -> List[str]:
    """Return all top-level identifier-like tokens in ``expression`` that
    could be column references.

    Implementation is intentionally loose: string literals are masked to
    spaces so identifiers inside them are ignored; otherwise every
    identifier-shaped token is returned. The caller then filters
    reserved tokens via :func:`_is_reserved_token`.

    This is a lint-quality heuristic rather than a full parser; M6 SQL
    compile will do precise binding. Accepting some false negatives here
    is preferable to rejecting legal expressions — the M5 authority-bound
    schema will catch deeper issues, and the final SQL build will catch
    the rest.
    """
    masked = _mask_string_literals(expression)
    return list(_IDENT_SCAN.findall(masked))


def _mask_string_literals(text: str) -> str:
    """Replace contents of single- / double-quoted string segments with
    spaces so downstream identifier scanning skips them. Escapes (\\')
    are handled simply: the escape char stays, the following char is
    also masked."""
    out = []
    quote: Optional[str] = None
    escaped = False
    for ch in text:
        if quote is None:
            if ch in ("'", '"'):
                quote = ch
                out.append(" ")
            else:
                out.append(ch)
        else:
            if escaped:
                escaped = False
                out.append(" ")
                continue
            if ch == "\\":
                escaped = True
                out.append(" ")
            elif ch == quote:
                quote = None
                out.append(" ")
            else:
                out.append(" ")
    return "".join(out)
