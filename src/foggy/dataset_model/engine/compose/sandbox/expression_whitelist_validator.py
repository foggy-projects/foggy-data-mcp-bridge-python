"""Layer B — DSL expression whitelist validator.

Validates column expressions and slice values against a function whitelist
and injection pattern blacklist. Applied at ``BaseModelPlan`` and
``DerivedQueryPlan`` construction time.
"""

from __future__ import annotations

import re
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
    """Validate slice values for injection patterns.

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
        if isinstance(entry, dict):
            value = entry.get("value")
            if isinstance(value, str):
                _check_injection(value, phase)


def _check_injection(value: str, phase: str) -> None:
    for p in INJECTION_PATTERNS:
        if p.search(value):
            raise ComposeSandboxViolationError(
                LAYER_B_INJECTION_SUSPECTED,
                "Expression contains a blocked injection pattern.",
                phase,
            )
