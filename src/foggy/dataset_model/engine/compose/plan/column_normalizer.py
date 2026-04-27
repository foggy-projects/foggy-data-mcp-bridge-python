"""G5 Phase 1 (F4) — Column object normalizer (Python side).

Mirrors the Java :class:`ColumnObjectNormalizer` (see
``foggy-dataset-model/.../engine/compose/plan/ColumnObjectNormalizer.java``).
Normalizes ``dsl({columns: [...]})`` entries from the F4 object form
(e.g. ``{field: "amount", agg: "sum", as: "totalSales"}``) to the
canonical string form (e.g. ``"SUM(amount) AS totalSales"``). Downstream
compilation / validation is unchanged.

Supported forms
---------------

* **F1-F3 string** (passthrough): ``"name"`` / ``"name AS alias"`` /
  ``"SUM(amount) AS total"`` / ``"YEAR(orderDate) AS year"``
* **F4 object**: ``{field, agg?, as?}`` — required ``field``, optional
  ``agg`` (whitelist below) and ``as`` (string alias)
* **F5 object** (``{plan, field, ...}``): currently fail-loud with
  ``COLUMN_PLAN_NOT_VISIBLE``; F5 is Phase 2 and blocked on G10

Aggregation whitelist
---------------------

``sum``, ``avg``, ``count``, ``max``, ``min``, ``count_distinct``.
The last is lowered to ``COUNT_DISTINCT(field)`` which the SQL engine
(``inline_expression`` + ``field_validator``) automatically translates to
``COUNT(DISTINCT field)``.

Error codes
-----------

Errors are raised as ``ValueError`` with messages prefixed by the error
code (e.g. ``"COLUMN_FIELD_REQUIRED: ..."``). This matches the Java side
where errors propagate as ``IllegalArgumentException`` with the same
prefixes — keeps double-end parity at the message-string level.

* ``COLUMN_FIELD_REQUIRED`` — F4 object missing ``field`` or null/blank
* ``COLUMN_AGG_NOT_SUPPORTED`` — ``agg`` not in whitelist
* ``COLUMN_AS_TYPE_INVALID`` — ``as`` is not a string
* ``COLUMN_FIELD_INVALID_KEY`` — F4 object contains an unknown key
* ``COLUMN_PLAN_NOT_VISIBLE`` — F5 placeholder; F5 is Phase 2 (blocked on G10)

See also
--------

G5 spec v2-patch: ``docs/8.3.0.beta/P0-SemanticDSL-列项对象语法-后置消歧设计.md``
"""

from __future__ import annotations

from typing import Any, List, Optional

# Aggregation function whitelist (case-insensitive). Lowercase canonical form
# is used internally; output is uppercased for SQL emission.
ALLOWED_AGG = frozenset({"sum", "avg", "count", "max", "min", "count_distinct"})

# Allowed keys in F4 object form. Other keys (e.g. `plan` for F5) trigger
# a fail-loud error in the current Phase 1.
ALLOWED_F4_KEYS = frozenset({"field", "agg", "as"})


def normalize(item: Any, index: int) -> Any:
    """Normalize a single column entry.

    Returns
    -------
    str
        For F1-F3 strings (passthrough) and F4 objects (converted to
        canonical string form).
    Any
        For other types (programmatic ``PlanColumnRef``, etc.) — passthrough
        unchanged for downstream handling.
    None
        If ``item`` is ``None`` (matches Java behavior where null entries
        are passed through and skipped by callers as appropriate).

    Raises
    ------
    ValueError
        On F4 validation failure with a ``COLUMN_*:`` prefix.
    """
    if item is None:
        return None
    if isinstance(item, str):
        # F1-F3: passthrough
        return item
    if isinstance(item, dict):
        return _normalize_map(item, index)
    # Other types — passthrough (programmatic plan-expression objects, etc.)
    return item


def normalize_columns(raw_columns: Optional[List[Any]]) -> List[Any]:
    """Normalize a list of column entries.

    Returns a new list with all dict entries converted to strings. Strings
    and other types pass through unchanged. ``None`` entries are preserved
    in the list (caller decides whether to filter them).
    """
    if raw_columns is None:
        return []
    result: List[Any] = []
    for i, item in enumerate(raw_columns):
        result.append(normalize(item, i))
    return result


def normalize_columns_to_strings(raw_columns: Optional[List[Any]]) -> List[str]:
    """Normalize a list to ``List[str]``. Used by paths that strictly require
    strings downstream (e.g. ``BaseModelPlan.columns`` validation).

    Non-None, non-String, non-Map entries fall back to ``str(item)`` — same
    behavior as Java legacy ``DslQueryFunction.toStringList``.

    None entries are skipped.
    """
    if raw_columns is None:
        return []
    result: List[str] = []
    for i, item in enumerate(raw_columns):
        normalized = normalize(item, i)
        if normalized is None:
            continue
        result.append(normalized if isinstance(normalized, str) else str(normalized))
    return result


# ---------------------------------------------------------------------------
# Internal: normalize one dict (F4 / F5)
# ---------------------------------------------------------------------------


def _normalize_map(raw: dict, index: int) -> str:
    # Phase 2 placeholder — F5 plan-qualified form not yet supported (blocked on G10).
    if "plan" in raw:
        raise ValueError(
            f"COLUMN_PLAN_NOT_VISIBLE: columns[{index}] uses plan-qualified "
            "syntax {plan, field, ...} which is Phase 2 of G5 and currently "
            "blocked on G10 engine refactor. As a workaround, rename in "
            'source plans using "name AS alias" and reference the alias instead.'
        )

    # Validate keys
    for key in raw.keys():
        if not isinstance(key, str) or key not in ALLOWED_F4_KEYS:
            raise ValueError(
                f"COLUMN_FIELD_INVALID_KEY: columns[{index}] contains unknown "
                f"key {key!r}. Allowed keys: {sorted(ALLOWED_F4_KEYS)}"
            )

    # field — required
    field_obj = raw.get("field")
    if not isinstance(field_obj, str) or not field_obj.strip():
        raise ValueError(
            f"COLUMN_FIELD_REQUIRED: columns[{index}] missing required 'field' "
            f"(must be a non-empty string, got {type(field_obj).__name__ if field_obj is not None else 'None'})"
        )
    field = field_obj.strip()

    # as — optional
    alias: Optional[str] = None
    if "as" in raw:
        as_obj = raw.get("as")
        if as_obj is not None and not isinstance(as_obj, str):
            raise ValueError(
                f"COLUMN_AS_TYPE_INVALID: columns[{index}] 'as' must be a "
                f"string, got {type(as_obj).__name__}"
            )
        if isinstance(as_obj, str):
            as_str = as_obj.strip()
            if as_str:
                alias = as_str

    # agg — optional
    agg: Optional[str] = None
    if "agg" in raw:
        agg_obj = raw.get("agg")
        if not isinstance(agg_obj, str) or not agg_obj.strip():
            raise ValueError(
                f"COLUMN_AGG_NOT_SUPPORTED: columns[{index}] 'agg' must be a "
                f"non-empty string in {sorted(ALLOWED_AGG)}, got {agg_obj!r}"
            )
        agg_lower = agg_obj.strip().lower()
        if agg_lower not in ALLOWED_AGG:
            raise ValueError(
                f"COLUMN_AGG_NOT_SUPPORTED: columns[{index}] agg {agg_obj!r} "
                f"is not in the whitelist {sorted(ALLOWED_AGG)}. "
                "(Note: 'count_distinct' is supported and lowers to "
                "COUNT(DISTINCT field).)"
            )
        agg = agg_lower

    # Build the canonical string form
    if agg is not None:
        # count_distinct → COUNT_DISTINCT(field) which the SQL engine lowers
        # to COUNT(DISTINCT field) automatically.
        body = f"{agg.upper()}({field})"
    else:
        body = field

    return f"{body} AS {alias}" if alias else body
