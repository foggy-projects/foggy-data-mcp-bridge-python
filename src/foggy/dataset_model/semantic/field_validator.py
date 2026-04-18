"""Column governance — field validator (v1.3).

Extracts raw field references from DSL expressions and validates them
against the ``visible`` whitelist (:class:`FieldAccessDef`) **and/or**
the ``denied_qm_fields`` blacklist (resolved from physical
``denied_columns`` via :class:`PhysicalColumnMapping`).

Design rules:

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
* When both whitelist and blacklist are active, any mechanism rejecting
  a field causes the query to fail (conservative merge).
* Blacklist checks use both the full QM field name **and** the stripped
  dimension base name (e.g. ``customer`` from ``customer$type``), aligned
  with Java ``FieldAccessPermissionStep``.
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


@dataclass
class InvalidQueryFieldDetail:
    """Recoverable invalid-field error detail for user/LLM repair."""
    error_code: str
    message: str
    model: str
    invalid_field: str
    suggestions: List[str] = field(default_factory=list)

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "errorCode": self.error_code,
            "message": self.message,
            "model": self.model,
            "invalidField": self.invalid_field,
            "suggestions": list(self.suggestions),
        }


def _strip_dimension_suffix(field_name: str) -> str:
    """Strip ``$suffix`` from a dimension field name.

    ``"customer$type"`` → ``"customer"``
    ``"salesAmount"``   → ``"salesAmount"``

    Aligned with Java ``FieldAccessPermissionStep.stripDimensionSuffix()``.
    """
    idx = field_name.find("$")
    return field_name[:idx] if idx > 0 else field_name


def _is_field_denied(field_name: str, denied_qm_fields: Set[str]) -> bool:
    """Check if a field is denied by the blacklist.

    Checks **both** the full field name and the stripped base dimension
    name, aligned with Java ``FieldAccessPermissionStep.checkField()``.
    """
    if field_name in denied_qm_fields:
        return True
    base = _strip_dimension_suffix(field_name)
    if base != field_name and base in denied_qm_fields:
        return True
    return False


def validate_field_access(
    *,
    columns: List[str],
    slice_items: List[Any],
    order_by: List[Any],
    calculated_fields: Optional[List[Dict[str, Any]]] = None,
    field_access: Optional[FieldAccessDef] = None,
    denied_qm_fields: Optional[Set[str]] = None,
) -> FieldValidationResult:
    """Validate user-referenced fields against whitelist **and** blacklist.

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
        Column governance whitelist. ``None`` means no whitelist (v1.1 compat).
    denied_qm_fields
        QM field names denied by physical column blacklist (already resolved
        via :class:`PhysicalColumnMapping`).  ``None`` / empty means no
        blacklist.

    Returns
    -------
    FieldValidationResult
        ``.valid`` is ``True`` when all fields pass; otherwise ``.blocked_fields``
        lists the offending field names.

    Combination semantics (conservative merge):
    - Whitelist active + field not in whitelist → blocked.
    - Blacklist active + field in blacklist → blocked.
    - Both active → **either** mechanism blocking causes rejection.
    """
    has_whitelist = field_access is not None and bool(field_access.visible)
    has_blacklist = bool(denied_qm_fields)

    if not has_whitelist and not has_blacklist:
        # No governance — everything passes
        return FieldValidationResult()

    visible_set = set(field_access.visible) if has_whitelist else None
    denied_set = denied_qm_fields or set()
    blocked: List[str] = []

    def _check_field(f: str) -> None:
        """Check a single field against both whitelist and blacklist."""
        if visible_set is not None and f not in visible_set:
            blocked.append(f)
            return
        if has_blacklist and _is_field_denied(f, denied_set):
            blocked.append(f)

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
                _check_field(dep)
        else:
            # Opaque expression with no extractable fields: fail-closed
            _check_field(parsed.source_field)

    # 2. Validate user slice
    slice_fields = _extract_fields_from_slice(slice_items)
    for f in slice_fields:
        _check_field(f)

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
                _check_field(dep)
        else:
            _check_field(field_ref)

    # 4. Validate calculatedFields
    if calculated_fields:
        calc_fields = _extract_fields_from_calculated(calculated_fields)
        for f in calc_fields:
            _check_field(f)

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


def validate_query_fields(model: Any, request: Any) -> Optional[InvalidQueryFieldDetail]:
    """Surface recoverable invalid-field errors before SQL build, so upstream callers
    (users / LLMs) get a repair hint instead of a raw database error."""
    schema_fields = _collect_model_schema_fields(model)
    if not schema_fields:
        return None

    # Single pass over calculated_fields feeds three downstream consumers:
    #   - schema_fields (calc names are valid references)
    #   - dynamic_fields (skip validation for calc-defined names)
    #   - calc_exprs (dependency validation for order_by + calc expressions)
    dynamic_fields: Set[str] = set()
    calc_exprs: List[tuple[str, str]] = []
    for cf in request.calculated_fields or []:
        name = cf.get("name") if isinstance(cf, dict) else getattr(cf, "name", None)
        if not name:
            continue
        schema_fields.add(name)
        dynamic_fields.add(name)
        expr = cf.get("expression") if isinstance(cf, dict) else getattr(cf, "expression", None)
        if expr:
            calc_exprs.append((name, expr))
    calc_map = dict(calc_exprs)

    for col_expr in request.columns or []:
        parsed = _parse_column_expr(col_expr)
        if parsed.alias:
            dynamic_fields.add(parsed.alias)
        if parsed.source_fields:
            for dep in parsed.source_fields:
                detail = _check_query_field(model, dep, schema_fields, dynamic_fields)
                if detail:
                    return detail
        elif parsed.source_field:
            detail = _check_query_field(model, parsed.source_field, schema_fields, dynamic_fields)
            if detail:
                return detail

    for item in request.group_by or []:
        field_name = getattr(item, "field", None) if not isinstance(item, dict) else item.get("field")
        detail = _check_query_field(model, field_name, schema_fields, dynamic_fields)
        if detail:
            return detail

    for item in request.slice or []:
        detail = _validate_slice_item(model, item, schema_fields, dynamic_fields)
        if detail:
            return detail

    for item in request.order_by or []:
        field_name = item.get("field") if isinstance(item, dict) else getattr(item, "field", None)
        if not field_name:
            continue
        if field_name in dynamic_fields:
            continue
        expr = calc_map.get(field_name)
        if expr:
            for dep in _extract_field_dependencies(expr):
                detail = _check_query_field(model, dep, schema_fields, dynamic_fields)
                if detail:
                    return detail
            continue
        detail = _check_query_field(model, field_name, schema_fields, dynamic_fields)
        if detail:
            return detail

    for _, expr in calc_exprs:
        for dep in _extract_field_dependencies(expr):
            detail = _check_query_field(model, dep, schema_fields, dynamic_fields)
            if detail:
                return detail

    return None


def _collect_model_schema_fields(model: Any) -> Set[str]:
    fields: Set[str] = set()

    for name in getattr(model, "measures", {}) or {}:
        fields.add(name)
    for name in getattr(model, "dimensions", {}) or {}:
        fields.add(name)
    for name in getattr(model, "columns", {}) or {}:
        fields.add(name)

    dimension_joins = getattr(model, "dimension_joins", None) or {}
    if isinstance(dimension_joins, dict):
        iterable = dimension_joins.items()
    else:
        iterable = []
        for join_def in dimension_joins:
            dim_name = getattr(join_def, "name", None)
            if dim_name:
                iterable.append((dim_name, join_def))

    for dim_name, join_def in iterable:
        fields.add(f"{dim_name}$id")
        fields.add(f"{dim_name}$caption")
        for prop in getattr(join_def, "properties", []) or []:
            prop_name = prop.get_name() if hasattr(prop, "get_name") else getattr(prop, "name", None)
            if prop_name:
                fields.add(f"{dim_name}${prop_name}")

    return fields


def _validate_slice_item(
    model: Any,
    item: Any,
    schema_fields: Set[str],
    dynamic_fields: Set[str],
) -> Optional[InvalidQueryFieldDetail]:
    if item is None:
        return None

    field_name = item.get("field") if isinstance(item, dict) else getattr(item, "field", None)
    detail = _check_query_field(model, field_name, schema_fields, dynamic_fields)
    if detail:
        return detail

    for key in ("conditions", "children", "filters", "$or", "$and", "or", "and"):
        nested = item.get(key) if isinstance(item, dict) else getattr(item, key, None)
        if isinstance(nested, list):
            for child in nested:
                detail = _validate_slice_item(model, child, schema_fields, dynamic_fields)
                if detail:
                    return detail
    return None


def _check_query_field(
    model: Any,
    field_name: Optional[str],
    schema_fields: Set[str],
    dynamic_fields: Set[str],
) -> Optional[InvalidQueryFieldDetail]:
    if not field_name:
        return None
    if field_name in dynamic_fields or field_name in schema_fields:
        return None
    if hasattr(model, "resolve_field") and model.resolve_field(field_name) is not None:
        return None

    suggestions = _suggest_fields(field_name, schema_fields)
    message = f"Field '{field_name}' not found in model '{model.name}'."
    if suggestions:
        message += f" Did you mean '{suggestions[0]}'?"
    return InvalidQueryFieldDetail(
        error_code="INVALID_QUERY_FIELD",
        message=message,
        model=model.name,
        invalid_field=field_name,
        suggestions=suggestions,
    )


def _suggest_fields(invalid_field: str, schema_fields: Set[str]) -> List[str]:
    scored: List[tuple[int, str]] = []
    for candidate in schema_fields:
        score = _field_similarity_score(invalid_field, candidate)
        if score > 0:
            scored.append((score, candidate))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [candidate for _, candidate in scored[:3]]


def _field_similarity_score(invalid_field: str, candidate: str) -> int:
    invalid_norm = _normalize_field_name(invalid_field)
    candidate_norm = _normalize_field_name(candidate)
    invalid_tail = _tail_field_name(invalid_field)
    candidate_tail = _tail_field_name(candidate)

    if invalid_norm == candidate_norm:
        return 1000

    score = 0
    if invalid_tail.lower() == candidate_tail.lower():
        score += 800
    if candidate_norm.endswith(invalid_tail.lower()):
        score += 500
    if invalid_tail.lower() in candidate_tail.lower() or candidate_tail.lower() in invalid_tail.lower():
        score += 200

    distance = _levenshtein_distance(invalid_norm, candidate_norm)
    max_len = max(len(invalid_norm), len(candidate_norm))
    score += max(0, 200 - distance * 40)
    if max_len > 0:
        ratio = 1.0 - (distance / max_len)
        if ratio >= 0.55:
            score += round(ratio * 100)

    return score if score >= 220 else 0


def _normalize_field_name(field_name: str) -> str:
    return re.sub(r"[$_\-\s]", "", field_name).lower()


def _tail_field_name(field_name: str) -> str:
    if "$" not in field_name:
        return field_name
    return field_name.rsplit("$", 1)[1]


def _levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    prev = list(range(len(right) + 1))
    for i, left_ch in enumerate(left, start=1):
        curr = [i]
        for j, right_ch in enumerate(right, start=1):
            cost = 0 if left_ch == right_ch else 1
            curr.append(min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + cost,
            ))
        prev = curr
    return prev[-1]
