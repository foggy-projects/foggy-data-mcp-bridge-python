"""G5 Phase 1 (F4) + Phase 2 (F5) — Column object normalizer (Python side).

Mirrors the Java :class:`ColumnObjectNormalizer` (see
``foggy-dataset-model/.../engine/compose/plan/ColumnObjectNormalizer.java``).
Normalizes ``dsl({columns: [...]})`` entries from the F4/F5 object forms
to the canonical string form. Downstream compilation / validation is
unchanged.

Supported forms
---------------

* **F1-F3 string** (passthrough): ``"name"`` / ``"name AS alias"`` /
  ``"SUM(amount) AS total"`` / ``"YEAR(orderDate) AS year"``
* **F4 object**: ``{field, agg?, as?}`` — required ``field``, optional
  ``agg`` (whitelist below) and ``as`` (string alias)
* **F5 object**: ``{plan, field, agg?, as?}`` — adds required ``plan``
  (a :class:`QueryPlan` reference). The Python side intentionally
  flattens F5 to the same string form as F4 (``"<AGG>(field) AS alias"``)
  — see "Architectural divergence from Java" below. The ``plan``
  reference is validated at parse time (must be a ``QueryPlan`` instance)
  but discarded after.

Aggregation whitelist
---------------------

``sum``, ``avg``, ``count``, ``max``, ``min``, ``count_distinct``.
The last is lowered to ``COUNT_DISTINCT(field)`` which the SQL engine
(``inline_expression`` + ``field_validator``) automatically translates to
``COUNT(DISTINCT field)``.

Architectural divergence from Java
-----------------------------------

Java's :class:`BaseModelPlan` / :class:`DerivedQueryPlan` columns field
is ``List<Object>`` so F5 ``PlanColumnRef`` / ``AggregateColumn`` /
``ProjectedColumn`` compounds flow through. Python's plan IR is strictly
``Tuple[str, ...]`` (see ``plan.py``), so the F5 Map shape **must
flatten to a string at parse time** — same shape as F4. The ``plan``
reference is validated and then discarded. This matches the
documented Python behaviour at ``tests/compose/compilation/test_plan_alias_map.py``
docstring: "Python's fluent API flattens PlanColumnRef to bare strings
via to_column_expr() at the select() call. So the compiled SQL shape
doesn't change under the G10 flag — but the alias-map infrastructure
still has to be in place for PR5.4's validator to route columns back
to their producing plan."

The Java-side plan-qualified SQL emission (e.g. ``cte_0.salesAmount``
prefix from G10 PR3) is therefore not produced by the Python engine
under G10 ON; the Python validator (PR5.4) routes by ``planProvenance``
in the OutputSchema, not by carrying ``PlanColumnRef`` through compile.

Error codes
-----------

Errors are raised as ``ValueError`` with messages prefixed by the error
code (e.g. ``"COLUMN_FIELD_REQUIRED: ..."``). This matches the Java side
where errors propagate as ``IllegalArgumentException`` with the same
prefixes — keeps double-end parity at the message-string level.

* ``COLUMN_FIELD_REQUIRED`` — F4/F5 object missing ``field`` or null/blank
* ``COLUMN_AGG_NOT_SUPPORTED`` — ``agg`` not in whitelist
* ``COLUMN_AS_TYPE_INVALID`` — ``as`` is not a string
* ``COLUMN_FIELD_INVALID_KEY`` — F4/F5 object contains an unknown key
* ``COLUMN_PLAN_TYPE_INVALID`` — F5 ``plan`` value is not a ``QueryPlan``

See also
--------

G5 spec v2-patch: ``docs/8.3.0.beta/P0-SemanticDSL-列项对象语法-后置消歧设计.md``
"""

from __future__ import annotations

from typing import Any, List, Optional

# Aggregation function whitelist (case-insensitive). Lowercase canonical form
# is used internally; output is uppercased for SQL emission.
ALLOWED_AGG = frozenset({"sum", "avg", "count", "max", "min", "count_distinct"})

# Allowed keys in F4 object form. Object containing other keys (e.g. `plan`
# for F5) triggers a fail-loud error.
ALLOWED_F4_KEYS = frozenset({"field", "agg", "as"})

# Allowed keys in F5 object form. Adds `plan` on top of F4 keys.
# Detected by the presence of the `plan` key in the input dict.
ALLOWED_F5_KEYS = frozenset({"plan", "field", "agg", "as"})


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

    F1-F3 strings pass through; F4/F5 dicts are normalized to canonical
    string form; chained-API plan-expression objects (``PlanColumnRef`` /
    ``AggregateColumn`` / ``ProjectedColumn``) are **rejected fail-loud**
    with ``COLUMN_PLAN_TYPE_INVALID`` (G5 spec §10.3 item 5). Silent
    ``str()`` fallback would emit a literal repr like
    ``"PlanColumnRef(plan=..., name=...)"`` into SQL — a syntactically-
    legal but semantically-wrong query.

    None entries are skipped.

    Raises
    ------
    ValueError
        With ``COLUMN_PLAN_TYPE_INVALID`` prefix when an unflattened
        plan-expression object is encountered.
    """
    if raw_columns is None:
        return []
    result: List[str] = []
    for i, item in enumerate(raw_columns):
        normalized = normalize(item, i)
        if normalized is None:
            continue
        if isinstance(normalized, str):
            result.append(normalized)
            continue
        # Anything that survived `normalize` and is not a string must be
        # a chained-API plan-expression object. Legacy string-only
        # consumers cannot carry these — fail-loud.
        raise ValueError(
            f"COLUMN_PLAN_TYPE_INVALID: columns[{i}] is a plan-qualified "
            f"column reference ({type(normalized).__name__}) which the "
            "legacy string-only request path cannot carry. Either use the "
            "F4/F5 dict form `{field, agg?, as?}` or `{plan, field, ...}` "
            "(Python flattens F5 to a string at parse time), or route "
            "through a path that supports List[Any] columns."
        )
    return result


# ---------------------------------------------------------------------------
# Internal: normalize one dict (F4 / F5)
# ---------------------------------------------------------------------------


def _normalize_map(raw: dict, index: int) -> str:
    # F5 detection: presence of `plan` key triggers the plan-qualified path.
    is_f5 = "plan" in raw
    allowed_keys = ALLOWED_F5_KEYS if is_f5 else ALLOWED_F4_KEYS

    # Validate keys
    for key in raw.keys():
        if not isinstance(key, str) or key not in allowed_keys:
            raise ValueError(
                f"COLUMN_FIELD_INVALID_KEY: columns[{index}] contains unknown "
                f"key {key!r}. Allowed keys: {sorted(allowed_keys)}"
            )

    if is_f5:
        # F5: validate the plan reference type. The `plan` value must be
        # a QueryPlan instance — any other type fails fast at parse stage
        # with COLUMN_PLAN_TYPE_INVALID, before any flatten attempt.
        # Import is local to avoid a circular import at module load
        # (plan.py imports from this module via its `validate_columns`
        # path).
        from .plan import QueryPlan as _QueryPlan
        plan_obj = raw.get("plan")
        if not isinstance(plan_obj, _QueryPlan):
            raise ValueError(
                f"COLUMN_PLAN_TYPE_INVALID: columns[{index}] 'plan' must be a "
                f"QueryPlan reference (e.g. a `dsl({{...}})` handle), got "
                f"{type(plan_obj).__name__ if plan_obj is not None else 'None'}"
            )
        # Plan reference is validated; the flatten path below produces
        # the same string shape as F4. The plan reference is discarded
        # at this stage (Python plan IR is `Tuple[str, ...]`); the
        # plan-routed validator (PR5.4) routes columns back to their
        # producing plan via OutputSchema's planProvenance, not via
        # carrying PlanColumnRef through compile. See module docstring
        # "Architectural divergence from Java" for full rationale.

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
