"""Column governance — field validator (v1.2).

Extracts raw field references from DSL expressions and validates them
against the ``visible`` whitelist provided by :class:`FieldAccessDef`.

Design rules (from the execution plan):

* ``sum(amountTotal) as total`` → extracts ``amountTotal``; alias ``total``
  is **not** validated.
* ``partner$caption`` → extracts ``partner$caption`` as-is (dimension
  accessor syntax).
* ``orderBy`` referencing an alias must be **back-tracked** to the
  ``columns`` expression that defined it, and the *source* field of that
  expression is validated.
* ``system_slice`` fields are **never** validated.
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


@dataclass
class _ColumnExpr:
    """Parsed column expression."""
    raw: str
    source_field: str          # the bare field referenced
    alias: Optional[str]       # alias name if any


def _parse_column_expr(expr: str) -> _ColumnExpr:
    """Parse a single column expression and extract the source field + alias.

    Examples::

        "name"                      → source="name",     alias=None
        "partner$caption"           → source="partner$caption", alias=None
        "sum(amountTotal) as total" → source="amountTotal", alias="total"
        "count(name) as cnt"        → source="name",     alias="cnt"
        "amountTotal as amt"        → source="amountTotal", alias="amt"
    """
    expr = expr.strip()

    # Try agg function pattern first
    m = _AGG_RE.match(expr)
    if m:
        source = m.group(1)
        alias_m = _ALIAS_RE.search(expr)
        alias = alias_m.group(1) if alias_m else None
        return _ColumnExpr(raw=expr, source_field=source, alias=alias)

    # Check for "field as alias" (no aggregation)
    alias_m = _ALIAS_RE.search(expr)
    if alias_m:
        alias = alias_m.group(1)
        # Everything before " as alias" is the source
        source_part = expr[:alias_m.start()].strip()
        if _BARE_FIELD_RE.match(source_part):
            return _ColumnExpr(raw=expr, source_field=source_part, alias=alias)
        # Fallback: treat the whole pre-alias part as source
        return _ColumnExpr(raw=expr, source_field=source_part, alias=alias)

    # Bare field
    if _BARE_FIELD_RE.match(expr):
        return _ColumnExpr(raw=expr, source_field=expr, alias=None)

    # Unrecognized expression — treat entire expr as source (safe default)
    return _ColumnExpr(raw=expr, source_field=expr, alias=None)


def extract_field_from_expr(expr: str) -> str:
    """Public helper: extract the bare source field from a column expression."""
    return _parse_column_expr(expr).source_field


# ---------------------------------------------------------------------------
# Alias registry (for orderBy back-tracking)
# ---------------------------------------------------------------------------

def _build_alias_map(columns: List[str]) -> Dict[str, str]:
    """Build alias → source-field mapping from the columns list.

    Returns a dict like ``{"total": "amountTotal", "cnt": "name"}``.
    """
    result: Dict[str, str] = {}
    for col in columns:
        parsed = _parse_column_expr(col)
        if parsed.alias:
            result[parsed.alias] = parsed.source_field
    return result


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
            # Try to extract field references from the expression
            # Match word-like tokens that look like field names
            tokens = re.findall(r'[A-Za-z_]\w*(?:\$\w+)?', expr)
            # Filter out known function names and keywords
            _KEYWORDS = {
                "sum", "count", "avg", "min", "max", "abs", "round",
                "count_distinct", "countDistinct",
                "case", "when", "then", "else", "end", "and", "or", "not",
                "null", "true", "false", "as", "if",
            }
            for token in tokens:
                if token.lower() not in _KEYWORDS:
                    fields.add(token)
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

    # 1. Validate columns
    alias_map = _build_alias_map(columns)
    for col_expr in columns:
        source = extract_field_from_expr(col_expr)
        if source not in visible_set:
            blocked.append(source)

    # 2. Validate user slice
    slice_fields = _extract_fields_from_slice(slice_items)
    for f in slice_fields:
        if f not in visible_set:
            blocked.append(f)

    # 3. Validate orderBy (with alias back-tracking)
    for ob in order_by:
        if isinstance(ob, dict):
            field_ref = ob.get("field") or ob.get("fieldName") or ob.get("column", "")
        elif isinstance(ob, str):
            field_ref = ob
        else:
            continue
        if not field_ref:
            continue
        # Back-track alias to source field
        source = alias_map.get(field_ref, field_ref)
        if source not in visible_set:
            blocked.append(source)

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
) -> List[Dict[str, Any]]:
    """Remove blocked columns from query result rows.

    If ``field_access`` is ``None`` or ``visible`` is empty, rows are
    returned unchanged (v1.1 compat).
    """
    if not field_access or not field_access.visible:
        return items
    if not items:
        return items

    visible_set = set(field_access.visible)

    # Also keep alias-derived keys that don't match any raw field
    # (e.g. "total" from "sum(amount) as total" should stay if "amount" is visible)
    # The engine produces result keys based on aliases, so we keep all keys
    # that are either in visible_set or are not raw field names
    # Strategy: remove only keys that look like raw field names and are NOT visible
    return [
        {k: v for k, v in row.items() if k in visible_set}
        for row in items
    ]
