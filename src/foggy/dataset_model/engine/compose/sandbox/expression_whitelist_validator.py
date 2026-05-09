"""Layer B — DSL expression whitelist validator.

Validates column expressions and slice values against a function whitelist
and injection pattern blacklist. Applied at ``BaseModelPlan`` and
``DerivedQueryPlan`` construction time.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time
from decimal import Decimal
from numbers import Number
from typing import Any

from .error_codes import (
    LAYER_B_DERIVED_FN_DENIED,
    LAYER_B_FUNCTION_DENIED,
    LAYER_B_INJECTION_SUSPECTED,
)
from .exceptions import ComposeSandboxViolationError

# ---------------------------------------------------------------------------
# Allowed SQL functions — keep in sync with v1.4 M5 function list
# ---------------------------------------------------------------------------

ALLOWED_FUNCTIONS: frozenset = frozenset(
    {
        # Aggregation
        "SUM", "COUNT", "AVG", "MIN", "MAX",
        # Conditional
        "IIF", "IF", "CASE", "COALESCE", "NULLIF", "IFNULL", "NVL",
        # Date/Time
        "DATE_DIFF", "DATEDIFF", "DATE_ADD", "DATE_SUB", "DATE_FORMAT",
        "YEAR", "MONTH", "DAY", "HOUR", "MINUTE", "SECOND",
        "NOW", "CURDATE", "CURRENT_DATE", "CURRENT_TIMESTAMP",
        "DATE_TRUNC", "EXTRACT", "TIMESTAMPDIFF",
        # String
        "CONCAT", "UPPER", "LOWER", "TRIM", "LTRIM", "RTRIM",
        "SUBSTR", "SUBSTRING", "LENGTH", "LEN", "REPLACE",
        "LEFT", "RIGHT", "LPAD", "RPAD", "REVERSE",
        # Math
        "ABS", "ROUND", "CEIL", "CEILING", "FLOOR", "MOD",
        "POWER", "SQRT", "LOG", "LOG10", "EXP", "SIGN",
        # Type conversion
        "CAST", "CONVERT", "TO_CHAR", "TO_DATE", "TO_NUMBER",
        # Window (base only, full window validation is M10)
        "ROW_NUMBER", "RANK", "DENSE_RANK", "NTILE",
        "LAG", "LEAD", "FIRST_VALUE", "LAST_VALUE",
        # Misc
        "DISTINCT", "GROUP_CONCAT", "STRING_AGG",
    }
)

# Functions that are explicitly blocked (known dangerous).
BLOCKED_FUNCTIONS: frozenset = frozenset(
    {
        "CHAR", "CHR",
        "SLEEP", "BENCHMARK", "WAITFOR",
        "LOAD_FILE", "INTO_OUTFILE", "INTO_DUMPFILE",
        "EXEC", "EXECUTE", "XP_CMDSHELL",
        "SYSTEM", "DBMS_PIPE",
    }
)

# Pattern to extract function names from SQL expressions: FUNC_NAME(
FUNCTION_CALL_PATTERN = re.compile(r"\b([A-Z_][A-Z0-9_]*)\s*\(", re.IGNORECASE)

# Injection patterns in slice values
INJECTION_PATTERNS = [
    re.compile(r"(?i)\bUNION\s+(ALL\s+)?SELECT\b"),
    re.compile(r"(?i)\bSELECT\s+.*\bFROM\b"),
    re.compile(r"(?i)\bDROP\s+(TABLE|DATABASE)\b"),
    re.compile(r"(?i)\bINSERT\s+INTO\b"),
    re.compile(r"(?i)\bDELETE\s+FROM\b"),
    re.compile(r"(?i)\bUPDATE\s+.*\bSET\b"),
    re.compile(r"(?i)\b(ALTER|CREATE|TRUNCATE)\s+(TABLE|DATABASE)\b"),
    re.compile(r"--\s*$", re.MULTILINE),
    re.compile(r"/\*.*\*/"),
    re.compile(r"(?i)\bOR\s+1\s*=\s*1\b"),
    re.compile(r"(?i)\bOR\s+'[^']*'\s*=\s*'[^']*'"),
]

SLICE_VALUE_UNSUPPORTED_CODE = "COMPOSE_SLICE_VALUE_UNSUPPORTED"
SUBQUERY_VALUE_UNSUPPORTED_CODE = "COMPOSE_SUBQUERY_VALUE_UNSUPPORTED"

_SCALAR_SLICE_VALUE_TYPES = (
    str,
    bytes,
    Number,
    Decimal,
    bool,
    date,
    datetime,
    time,
    type(None),
)


def validate_columns(columns: list[str] | None, phase: str) -> None:
    """Validate column expressions for blocked function usage.

    Parameters
    ----------
    columns : list[str] or None
        The column expression list.
    phase : str
        Pipeline phase for error reporting.

    Raises
    ------
    ComposeSandboxViolationError
        If a blocked function is found.
    """
    if not columns:
        return
    for col in columns:
        if not col:
            continue
        for m in FUNCTION_CALL_PATTERN.finditer(col):
            func_name = m.group(1).upper()
            if func_name in BLOCKED_FUNCTIONS:
                raise ComposeSandboxViolationError(
                    LAYER_B_FUNCTION_DENIED,
                    f"Function '{func_name}' is not in the allowed list.",
                    phase,
                )


def validate_derived_columns(columns: list[str] | None, phase: str) -> None:
    """Validate column expressions for derived plans — stricter checks.
    Blocks RAW_SQL and other functions only allowed in base plans.

    Parameters
    ----------
    columns : list[str] or None
        The column expression list.
    phase : str
        Pipeline phase for error reporting.

    Raises
    ------
    ComposeSandboxViolationError
        If a blocked function is found.
    """
    if not columns:
        return
    for col in columns:
        if not col:
            continue
        for m in FUNCTION_CALL_PATTERN.finditer(col):
            func_name = m.group(1).upper()
            if func_name in BLOCKED_FUNCTIONS:
                raise ComposeSandboxViolationError(
                    LAYER_B_FUNCTION_DENIED,
                    f"Function '{func_name}' is not in the allowed list.",
                    phase,
                )
            if func_name == "RAW_SQL":
                raise ComposeSandboxViolationError(
                    LAYER_B_DERIVED_FN_DENIED,
                    "Function 'RAW_SQL' is not allowed in derived plans.",
                    phase,
                )


def validate_slice(slice_: list[Any] | None, phase: str) -> None:
    """Validate slice values for injection patterns and supported shape.

    Parameters
    ----------
    slice_ : list[Any] or None
        The slice list (each entry is typically a dict with field/op/value).
    phase : str
        Pipeline phase for error reporting.

    Raises
    ------
    ComposeSandboxViolationError
        If an injection pattern is detected.
    """
    if not slice_:
        return
    for entry in slice_:
        _validate_slice_entry(entry, phase)


def _validate_slice_entry(entry: Any, phase: str) -> None:
    if not isinstance(entry, dict):
        return

    if len(entry) == 1:
        key, val = next(iter(entry.items()))
        if key in {"$and", "$or"}:
            if isinstance(val, (list, tuple)):
                for nested in val:
                    _validate_slice_entry(nested, phase)
            return
        if key == "$not":
            nested_items = val if isinstance(val, (list, tuple)) else [val]
            for nested in nested_items:
                _validate_slice_entry(nested, phase)
            return
        if key != "value" and "field" not in entry:
            _validate_slice_value(val, phase, op="=")
            return

    if "value" in entry:
        _validate_slice_value(entry.get("value"), phase, op=entry.get("op", "="))


def _validate_slice_value(value: Any, phase: str, *, op: Any) -> None:
    if isinstance(value, str):
        _check_injection(value, phase)
        return

    op_upper = _normalize_slice_op(op)

    if isinstance(value, dict) and set(value.keys()) == {"$field"}:
        ref = value.get("$field")
        if isinstance(ref, str):
            _check_injection(ref, phase)
        return

    if _is_query_plan(value) or _is_plan_subquery(value):
        if op_upper in {"IN", "NOT IN"}:
            return
        raise ValueError(
            f"{SUBQUERY_VALUE_UNSUPPORTED_CODE}: slice.value can only be a "
            "QueryPlan or subquery(plan, field) for IN / NOT IN operators."
        )

    if isinstance(value, dict) or _is_object_like(value):
        raise ValueError(
            f"{SLICE_VALUE_UNSUPPORTED_CODE}: slice.value must be a scalar "
            "or a list of scalar values; object values are not supported. "
            "Use {'$field': '<output_field>'} only for derived "
            "field-to-field comparisons."
        )

    if isinstance(value, (list, tuple, set)):
        for item in value:
            if isinstance(item, str):
                _check_injection(item, phase)
            if _is_query_plan(item):
                raise ValueError(
                    f"{SLICE_VALUE_UNSUPPORTED_CODE}: slice.value list "
                    "cannot contain QueryPlan values; join/anti-join "
                    "support is not available in this form."
                )
            if _is_plan_subquery(item):
                raise ValueError(
                    f"{SLICE_VALUE_UNSUPPORTED_CODE}: slice.value list "
                    "cannot contain subquery values; pass the subquery as "
                    "the direct IN / NOT IN value instead."
                )
            if isinstance(item, dict) or _is_object_like(item):
                raise ValueError(
                    f"{SLICE_VALUE_UNSUPPORTED_CODE}: slice.value list "
                    "cannot contain object values; use scalar values only."
                )
        return

    if isinstance(value, _SCALAR_SLICE_VALUE_TYPES):
        return

    raise ValueError(
        f"{SLICE_VALUE_UNSUPPORTED_CODE}: slice.value must be a scalar "
        "or a list of scalar values."
    )


def _is_query_plan(value: Any) -> bool:
    try:
        from ..plan.plan import QueryPlan
    except Exception:
        return False
    return isinstance(value, QueryPlan)


def _is_plan_subquery(value: Any) -> bool:
    try:
        from ..plan.plan import PlanSubquery
    except Exception:
        return False
    return isinstance(value, PlanSubquery)


def _is_object_like(value: Any) -> bool:
    if value is None or isinstance(value, _SCALAR_SLICE_VALUE_TYPES):
        return False
    if isinstance(value, (list, tuple, set)):
        return False
    return hasattr(value, "__dict__")


def _normalize_slice_op(op: Any) -> str:
    return " ".join(str(op).strip().upper().split())


def _check_injection(value: str, phase: str) -> None:
    for p in INJECTION_PATTERNS:
        if p.search(value):
            raise ComposeSandboxViolationError(
                LAYER_B_INJECTION_SUSPECTED,
                "Expression contains a blocked injection pattern.",
                phase,
            )
