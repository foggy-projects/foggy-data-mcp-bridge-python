"""SQL normalizer for Formula parity (M5 Step 5.1).

Implements the canonical-form rules from ``docs/v1.4/formula-spec-v1/parity.md`` §2
so both Java and Python formula-compiler output can be compared as strings + param
lists.

Python side produces SQL with ``?`` placeholders + a ``bind_params`` tuple; Java
side historically renders inline literals directly. ``to_canonical(...)`` accepts
both and returns a ``(sql, params_tuple)`` pair where:

* excess whitespace is collapsed to single spaces
* SQL keywords are upper-cased consistently
* redundant parenthesis pairs (e.g. ``((a > ?))`` surrounding a flat sub-expression)
  are collapsed to a single pair
* when ``params`` is ``None`` the input is assumed to be in Java inline-literal form
  and literals are extracted back into ``?`` placeholders so Java/Python inputs
  converge on the same canonical shape

The Java side has an equivalent ``SqlNormalizer.java`` that implements the same
rules.  If the two normalizers drift, the parity test surfaces it via an
end-to-end compare.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence, Tuple

# SQL keywords we canonicalize to upper-case.  Applied as whole-word match on
# alpha tokens only, so column names are not touched.
_KEYWORDS: Tuple[str, ...] = (
    "CASE",
    "WHEN",
    "THEN",
    "ELSE",
    "END",
    "AND",
    "OR",
    "NOT",
    "IN",
    "IS",
    "NULL",
    "BETWEEN",
    "COALESCE",
    "ABS",
    "ROUND",
    "CEILING",
    "CEIL",
    "FLOOR",
    "CAST",
    "AS",
    "DATE",
    "INTERVAL",
    "DATEADD",
    "DATEDIFF",
    "DATE_ADD",
    "DATE_SUB",
    "NOW",
    "GETDATE",
    "SUM",
    "COUNT",
    "AVG",
    "MAX",
    "MIN",
    "DISTINCT",
    "DAY",
    "MONTH",
    "YEAR",
    "TRUE",
    "FALSE",
)

_KEYWORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# Matches a flat double-parenthesis pair ``((X))`` where X does not itself
# contain parens.  Applied in a fixed-point loop until stable so nested cases
# like ``((a > ?))`` inside ``CASE WHEN ... THEN`` reduce cleanly.
_DOUBLE_PAREN_FLAT_RE = re.compile(r"\(\s*\(([^()]*)\)\s*\)")

# Single-line inline-literal patterns (Java-side form).  Order matters:
# strings first (so an outer single quote is not misread as part of a number).
_STRING_LITERAL_RE = re.compile(r"'((?:[^']|'')*)'")
_NUMERIC_LITERAL_RE = re.compile(
    r"(?<![A-Za-z_0-9.])(-?\d+(?:\.\d+)?)(?![A-Za-z_0-9.])",
)


def _collapse_whitespace(sql: str) -> str:
    # tab / newline → space, then collapse runs, then trim inside brackets
    sql = re.sub(r"[\t\r\n]+", " ", sql)
    sql = re.sub(r" {2,}", " ", sql)
    sql = re.sub(r"\(\s+", "(", sql)
    sql = re.sub(r"\s+\)", ")", sql)
    return sql.strip()


def _upper_keywords(sql: str) -> str:
    return _KEYWORD_RE.sub(lambda m: m.group(0).upper(), sql)


def _collapse_redundant_parens(sql: str) -> str:
    """Iteratively collapse flat ``((X))`` pairs to ``(X)``."""
    while True:
        new_sql = _DOUBLE_PAREN_FLAT_RE.sub(r"(\1)", sql)
        if new_sql == sql:
            return sql
        sql = new_sql


def _outer_parens_wrap_all(sql: str) -> bool:
    if not (sql.startswith("(") and sql.endswith(")")):
        return False
    depth = 0
    in_string = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == "'":
            in_string = not in_string
        elif not in_string:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i != len(sql) - 1:
                    return False
        i += 1
    return depth == 0


def _strip_outer_parens(sql: str) -> str:
    sql = sql.strip()
    while _outer_parens_wrap_all(sql):
        sql = sql[1:-1].strip()
    return sql


def _canonicalize_case_when(sql: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        condition = _strip_outer_parens(match.group(2))
        return f"{match.group(1)}{condition}{match.group(3)}"

    return re.sub(r"(CASE WHEN )(.*?)( THEN )", _replace, sql)


def _canonicalize_equivalent_shapes(sql: str) -> str:
    sql = re.sub(r"\(-\s+([A-Za-z_][\w$]*|\?)\)", r"(-\1)", sql)
    sql = re.sub(r"\bCEIL\s*\(", "CEILING(", sql)
    sql = re.sub(r"\((NOT\s+\([^()]+\))\)", r"\1", sql)
    sql = re.sub(
        r"\(([A-Za-z_][\w$]*(?:\([^()]*\))?) IS (NOT )?NULL\)",
        r"\1 IS \2NULL",
        sql,
    )
    sql = _canonicalize_case_when(sql)
    return sql


def _extract_inline_literals(sql: str) -> Tuple[str, List[object]]:
    """Convert Java-side inline literals back to ``?`` placeholders.

    Returns ``(sql_with_placeholders, extracted_params_in_order)``.

    Leaves ``NULL`` / ``TRUE`` / ``FALSE`` in-place (those are not bind params
    in either engine's native output).
    """
    params: List[object] = []

    def _str_sub(match: re.Match[str]) -> str:
        raw = match.group(1).replace("''", "'")
        prefix = sql[: match.start()]
        if re.search(r"\bdatetime\s*\($", prefix, re.IGNORECASE) and raw.lower() == "now":
            return "'NOW'"
        params.append(("__STRING__", raw))
        return "\x00p\x00"

    # Step 1: replace string literals first (they may contain digits)
    placeholder_sql = _STRING_LITERAL_RE.sub(_str_sub, sql)

    # Step 2: numeric literals
    def _num_sub(match: re.Match[str]) -> str:
        raw = match.group(1)
        value: object = int(raw) if "." not in raw else float(raw)
        params.append(("__NUMBER__", value))
        return "\x00p\x00"

    placeholder_sql = _NUMERIC_LITERAL_RE.sub(_num_sub, placeholder_sql)

    # Restore to ``?`` — params were recorded in left-to-right order
    final_sql = placeholder_sql.replace("\x00p\x00", "?")
    # Flatten the tagged tuple list back to raw values; the tags are only used
    # internally to avoid mis-classifying a numeric literal inside a string.
    values: List[object] = [val for _tag, val in params]
    return final_sql, values


def to_canonical(
    sql: str,
    params: Optional[Sequence[object]] = None,
) -> Tuple[str, Tuple[object, ...]]:
    """Return ``(canonical_sql, canonical_params)`` for parity compare.

    * ``params is not None``: Python-form input — SQL already uses ``?``
      placeholders; keep params as-is.
    * ``params is None``: Java-form input — extract inline literals into a
      params tuple, substituting ``?`` placeholders so the two sides
      converge.
    """
    if params is None:
        sql, extracted = _extract_inline_literals(sql)
        params = extracted
    sql = _collapse_whitespace(sql)
    sql = _upper_keywords(sql)
    sql = _canonicalize_equivalent_shapes(sql)
    sql = _collapse_redundant_parens(sql)
    sql = _canonicalize_equivalent_shapes(sql)
    # Final whitespace tidy — paren collapse can leave multi-spaces.
    sql = _collapse_whitespace(sql)
    return sql, tuple(params)


def canonicalize_params(params: Iterable[object]) -> Tuple[object, ...]:
    """Standardize param values for parity compare.

    Python booleans are coerced to int (Java's form) so ``True``/``1`` match.
    Floats that equal an int (``2.0``) are coerced to int.
    """
    out: List[object] = []
    for p in params:
        if isinstance(p, bool):
            out.append(int(p))
        elif isinstance(p, float) and p.is_integer():
            out.append(int(p))
        else:
            out.append(p)
    return tuple(out)
