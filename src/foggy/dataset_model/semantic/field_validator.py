"""Column governance — field validator (v1.3).

Extracts raw field references from DSL expressions and validates them
against the ``visible`` whitelist provided by :class:`FieldAccessDef`.

Design rules (from the execution plan):

* ``sum(amountTotal) as total`` → extracts ``amountTotal``; alias ``total``
  is **not** validated.
* ``partner$caption`` → extracts ``partner$caption`` as-is (dimension
  accessor syntax).
* ``orderBy`` referencing an alias must be **back-tracked** to the
  ``columns`` expression that defined it, and the *source* fields of that
  expression are validated.
* ``system_slice`` fields are **never** validated.
* Inline expressions like ``a + b as c`` are parsed into dependency
  fields ``{a, b}`` — each dependency is validated individually.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from foggy.mcp_spi.semantic import FieldAccessDef


# ---------------------------------------------------------------------------
# Expression parsing helpers
# ---------------------------------------------------------------------------

# Matches common aggregation functions: sum(field), count(field), avg(field), etc.
_AGG_RE = re.compile(
    r"^(?:sum|count|avg|min|max|count_distinct|countDistinct)\s*\(\s*"
    r"([A-Za-z_]\w*(?:\$\w+)?)"  # captured group: the bare field
    r"\s*\)\s*(?:as\s+\w+)?$",
    re.IGNORECASE,
)

# Matches "expr as alias" — we use this to extract the alias name.
_ALIAS_RE = re.compile(r"\s+as\s+(\w+)\s*$", re.IGNORECASE)

# Matches a bare field (possibly with $suffix): name, partner$caption, etc.
_BARE_FIELD_RE = re.compile(r"^[A-Za-z_]\w*(?:\$\w+)?$")

# Strips string literals before tokenization to avoid false positives.
_STRING_LITERAL_RE = re.compile(r"'[^']*'|\"[^\"]*\"")

# Extracts word-like tokens (field candidates) from expressions.
_TOKEN_RE = re.compile(r'[A-Za-z_]\w*(?:\$\w+)?')

# SQL / DSL keywords that should NOT be treated as field references.
_EXPR_KEYWORDS: frozenset[str] = frozenset({
    # Aggregation functions (all lowercase — compared via .lower())
    "sum", "count", "avg", "min", "max", "abs", "round",
    "count_distinct", "countdistinct", "distinct", "group_concat",
    # Control flow
    "case", "when", "then", "else", "end", "and", "or", "not",
    "null", "true", "false", "as", "if", "in", "is", "between", "like",
    # Window function names
    "over", "partition", "by", "order", "asc", "desc",
    "rows", "range", "current", "row", "preceding", "following", "unbounded",
    "rank", "row_number", "dense_rank", "ntile", "lag", "lead",
    "first_value", "last_value",
    # Common scalar functions
    "coalesce", "ifnull", "nvl", "nullif", "cast", "convert",
    "concat", "substring", "left", "right",
    "floor", "ceil", "ceiling", "mod", "power", "sqrt",
})


def _extract_field_dependencies(expr: str) -> Set[str]:
    """Extract the set of field names an expression depends on.

    Strips string literals, tokenizes, and removes known SQL keywords.
    This is the **single source of truth** for dependency extraction.

    Examples::

        "a + b"                → {"a", "b"}
        "sum(a + b)"           → {"a", "b"}
        "case when s = 'x' then amount else 0 end" → {"s", "amount"}
        "round(a / b, 2)"      → {"a", "b"}
        "1 + 2"                → set()
        ""                     → set()
    """
    if not expr:
        return set()
    cleaned = _STRING_LITERAL_RE.sub("", expr)
    tokens = _TOKEN_RE.findall(cleaned)
    return {t for t in tokens if t.lower() not in _EXPR_KEYWORDS}


@dataclass
class _ColumnExpr:
    """Parsed column expression."""
    raw: str
    source_field: str          # expression part (for alias map / error messages)
    alias: Optional[str]       # alias name if any
    source_fields: Set[str] = field(default_factory=set)  # dependency fields


def _parse_column_expr(expr: str) -> _ColumnExpr:
    """Parse a single column expression and extract source field(s) + alias.

    Examples::

        "name"                      → source="name",     alias=None, deps={"name"}
        "partner$caption"           → source="partner$caption", alias=None
        "sum(amountTotal) as total" → source="amountTotal", alias="total", deps={"amountTotal"}
        "count(name) as cnt"        → source="name",     alias="cnt", deps={"name"}
        "amountTotal as amt"        → source="amountTotal", alias="amt"
        "a + b as c"                → source="a + b",    alias="c", deps={"a", "b"}
        "sum(a + b) as total"       → source="sum(a + b)", alias="total", deps={"a", "b"}
    """
    expr = expr.strip()

    # Try agg function pattern first (matches only simple agg(bare_field))
    m = _AGG_RE.match(expr)
    if m:
        source = m.group(1)
        alias_m = _ALIAS_RE.search(expr)
        alias = alias_m.group(1) if alias_m else None
        return _ColumnExpr(raw=expr, source_field=source, alias=alias,
                           source_fields={source})

    # Check for "field as alias" (no aggregation)
    alias_m = _ALIAS_RE.search(expr)
    if alias_m:
        alias = alias_m.group(1)
        # Everything before " as alias" is the source
        source_part = expr[:alias_m.start()].strip()
        if _BARE_FIELD_RE.match(source_part):
            return _ColumnExpr(raw=expr, source_field=source_part, alias=alias,
                               source_fields={source_part})
        # Non-bare expression: extract dependency fields
        deps = _extract_field_dependencies(source_part)
        return _ColumnExpr(raw=expr, source_field=source_part, alias=alias,
                           source_fields=deps)

    # Bare field
    if _BARE_FIELD_RE.match(expr):
        return _ColumnExpr(raw=expr, source_field=expr, alias=None,
                           source_fields={expr})

    # Unrecognized expression — extract dependencies, fail-closed if empty
    deps = _extract_field_dependencies(expr)
    return _ColumnExpr(raw=expr, source_field=expr, alias=None,
                       source_fields=deps)


def extract_field_dependencies(expr: str) -> Set[str]:
    """Public helper: extract all dependency fields from a column expression."""
    return _parse_column_expr(expr).source_fields


# ---------------------------------------------------------------------------
# Slice field extraction
# ---------------------------------------------------------------------------

def _extract_fields_from_slice(slice_items: List[Any]) -> Set[str]:
    """Extract field names referenced in a slice (filter) array.

    Each slice item is typically a dict with a ``field`` key, or it can be
    a nested ``FilterRequestDef`` style object.
    """
    fields: Set[str] = set()
    if not slice_items:
        return fields
    for item in slice_items:
        if isinstance(item, dict):
            f = item.get("field") or item.get("fieldName")
            if f and isinstance(f, str):
                fields.add(f)
            # Recurse into nested conditions
            for key in ("conditions", "children", "filters"):
                nested = item.get(key)
                if isinstance(nested, list):
                    fields.update(_extract_fields_from_slice(nested))
    return fields


# ---------------------------------------------------------------------------
# calculatedFields field extraction
# ---------------------------------------------------------------------------

def _extract_fields_from_calculated(calc_fields: List[Dict[str, Any]]) -> Set[str]:
    """Extract source field references from calculatedFields definitions."""
    fields: Set[str] = set()
    if not calc_fields:
        return fields
    for cf in calc_fields:
        expr = cf.get("expression") or cf.get("formula") or ""
        if isinstance(expr, str):
            fields.update(_extract_field_dependencies(expr))
        # Also check explicit source fields
        for key in ("sourceField", "source_field", "field", "fields"):
            val = cf.get(key)
            if isinstance(val, str):
                fields.add(val)
            elif isinstance(val, list):
                for v in val:
                    if isinstance(v, str):
                        fields.add(v)
    return fields


# ---------------------------------------------------------------------------
# Main validation
# ---------------------------------------------------------------------------

@dataclass
class FieldValidationResult:
    """Result of field-access validation."""
    valid: bool = True
    blocked_fields: List[str] = field(default_factory=list)
    error_message: Optional[str] = None


def validate_field_access(
    *,
    columns: List[str],
    slice_items: List[Any],
    order_by: List[Any],
    calculated_fields: Optional[List[Dict[str, Any]]] = None,
    field_access: Optional[FieldAccessDef] = None,
) -> FieldValidationResult:
    """Validate that all user-referenced fields are in the visible whitelist.

    Parameters
    ----------
    columns
        Column expressions from the query request.
    slice_items
        User-provided slice (filters) — **not** system_slice.
    order_by
        Order-by specifications from the query request.
    calculated_fields
        Optional calculated field definitions.
    field_access
        Column governance definition. ``None`` means no governance (v1.1 compat).

    Returns
    -------
    FieldValidationResult
        ``.valid`` is ``True`` when all fields pass; otherwise ``.blocked_fields``
        lists the offending field names.
    """
    if field_access is None or not field_access.visible:
        # No governance — everything passes
        return FieldValidationResult()

    visible_set = set(field_access.visible)
    blocked: List[str] = []

    # 1. Validate columns (with dependency-aware field extraction)
    alias_deps: Dict[str, Set[str]] = {}   # alias → dependency fields
    for col_expr in columns:
        parsed = _parse_column_expr(col_expr)
        deps = parsed.source_fields
        if parsed.alias:
            # Fallback to raw expression text as sentinel — ensures
            # fail-closed: the text won't match any visible field.
            alias_deps[parsed.alias] = deps or {parsed.source_field}
        if deps:
            for dep in deps:
                if dep not in visible_set:
                    blocked.append(dep)
        else:
            # Opaque expression with no extractable fields: fail-closed
            if parsed.source_field not in visible_set:
                blocked.append(parsed.source_field)

    # 2. Validate user slice
    slice_fields = _extract_fields_from_slice(slice_items)
    for f in slice_fields:
        if f not in visible_set:
            blocked.append(f)

    # 3. Validate orderBy (with alias back-tracking to dependency fields)
    for ob in order_by:
        if isinstance(ob, dict):
            field_ref = ob.get("field") or ob.get("fieldName") or ob.get("column", "")
        elif isinstance(ob, str):
            field_ref = ob
        else:
            continue
        if not field_ref:
            continue
        # Back-track alias to dependency fields
        if field_ref in alias_deps:
            for dep in alias_deps[field_ref]:
                if dep not in visible_set:
                    blocked.append(dep)
        elif field_ref not in visible_set:
            blocked.append(field_ref)

    # 4. Validate calculatedFields
    if calculated_fields:
        calc_fields = _extract_fields_from_calculated(calculated_fields)
        for f in calc_fields:
            if f not in visible_set:
                blocked.append(f)

    # Deduplicate while preserving order
    seen: Set[str] = set()
    unique_blocked: List[str] = []
    for f in blocked:
        if f not in seen:
            seen.add(f)
            unique_blocked.append(f)

    if unique_blocked:
        return FieldValidationResult(
            valid=False,
            blocked_fields=unique_blocked,
            error_message=(
                f"Column governance: the following fields are not accessible: "
                f"{', '.join(unique_blocked)}"
            ),
        )

    return FieldValidationResult()


def filter_response_columns(
    items: List[Dict[str, Any]],
    field_access: Optional[FieldAccessDef],
    display_to_qm: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Remove blocked columns from query result rows.

    Parameters
    ----------
    items
        Result rows from the query engine.  Keys are **display names**
        (SQL aliases like ``"Email"``), not QM field names.
    field_access
        Column governance definition.  ``visible`` contains QM field names.
    display_to_qm
        Mapping from display-name key → QM field name, built from
        ``build_result.columns``.  When provided, each row key is first
        translated to its QM name before checking the visible set.  When
        ``None``, keys are matched directly (unit-test / legacy compat).

    If ``field_access`` is ``None`` or ``visible`` is empty, rows are
    returned unchanged (v1.1 compat).
    """
    if not field_access or not field_access.visible:
        return items
    if not items:
        return items

    visible_set = set(field_access.visible)
    _map = display_to_qm or {}

    return [
        {k: v for k, v in row.items() if _map.get(k, k) in visible_set}
        for row in items
    ]
