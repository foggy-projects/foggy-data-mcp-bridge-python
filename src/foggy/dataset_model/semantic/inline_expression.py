"""Helpers for parsing inline aggregate expressions with nested functions."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List, Optional


SUPPORTED_INLINE_AGG_FUNCS = frozenset({
    "SUM",
    "AVG",
    "COUNT",
    "MIN",
    "MAX",
    "COUNT_DISTINCT",
    "COUNTD",
    "GROUP_CONCAT",
    "STDDEV_POP",
    "STDDEV_SAMP",
    "VAR_POP",
    "VAR_SAMP",
})

_ALIAS_RE = re.compile(r"[A-Za-z_]\w*$")


@dataclass(frozen=True)
class InlineAggregateExpression:
    """Parsed inline aggregate expression."""

    raw: str
    function: str
    inner_expression: str
    alias: str

    @property
    def aggregation(self) -> str:
        """Normalized aggregation function name."""
        if self.function == "COUNTD":
            return "COUNT_DISTINCT"
        return self.function


def skip_string_literal(text: str, start: int) -> int:
    """Given ``text[start]`` is a quote char, return index past the closing quote.

    Treats ``\\`` as an escape so ``'a\\'b'`` is consumed as a single literal.
    If the literal is unterminated, returns ``len(text)``.
    """
    quote = text[start]
    i = start + 1
    escaped = False
    length = len(text)
    while i < length:
        ch = text[i]
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == quote:
            return i + 1
        i += 1
    return i


def find_matching_paren(text: str, open_index: int) -> int:
    """Find the index of the ``)`` that closes ``text[open_index]`` (a ``(``).

    Respects single/double quoted string literals. Returns ``-1`` if unmatched.
    """
    depth = 0
    i = open_index
    length = len(text)
    while i < length:
        ch = text[i]
        if ch in ("'", '"'):
            i = skip_string_literal(text, i)
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def split_top_level_commas(text: str) -> List[str]:
    """Split ``text`` on commas that are outside of strings and parentheses."""
    args: List[str] = []
    depth = 0
    start = 0
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if ch in ("'", '"'):
            i = skip_string_literal(text, i)
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            args.append(text[start:i].strip())
            start = i + 1
        i += 1
    tail = text[start:].strip()
    if tail:
        args.append(tail)
    return args


# Backwards-compatible aliases for historical private imports within this module.
_find_matching_paren = find_matching_paren


def _find_top_level_as(expr: str) -> int:
    depth = 0
    i = 0
    length = len(expr)
    while i < length:
        ch = expr[i]
        if ch in ("'", '"'):
            i = skip_string_literal(expr, i)
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and expr[i:i + 4].lower() == " as ":
            return i
        i += 1
    return -1


def _default_alias(function_name: str, inner_expression: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_$]+", "_", inner_expression).strip("_")
    if not cleaned:
        cleaned = "expr"
    return f"{function_name.lower()}_{cleaned}"


def parse_inline_aggregate(expr: str) -> Optional[InlineAggregateExpression]:
    """Parse ``agg(expr) [as alias]`` while allowing nested parentheses."""
    stripped = expr.strip()
    alias_idx = _find_top_level_as(stripped)
    if alias_idx >= 0:
        body = stripped[:alias_idx].strip()
        alias = stripped[alias_idx + 4:].strip()
        if not alias or not _ALIAS_RE.fullmatch(alias):
            return None
    else:
        body = stripped
        alias = ""

    open_paren = body.find("(")
    if open_paren <= 0:
        return None

    function_name = body[:open_paren].strip().upper()
    if function_name not in SUPPORTED_INLINE_AGG_FUNCS:
        return None

    close_paren = _find_matching_paren(body, open_paren)
    if close_paren != len(body) - 1:
        return None

    inner_expression = body[open_paren + 1:close_paren].strip()
    if not inner_expression:
        return None

    return InlineAggregateExpression(
        raw=expr,
        function=function_name,
        inner_expression=inner_expression,
        alias=alias or _default_alias(function_name, inner_expression),
    )


@dataclass(frozen=True)
class ColumnSpecParts:
    """Result of :func:`parse_column_with_alias`.

    Attributes
    ----------
    base_expr:
        The expression portion (with outer whitespace stripped). Equals
        the original (stripped) input when no alias was found.
    user_alias:
        The user-supplied alias when present (post ``AS``); ``None``
        otherwise.
    """

    base_expr: str
    user_alias: Optional[str]


def parse_column_with_alias(column_spec: str) -> ColumnSpecParts:
    """Split a non-aggregate ``columns[*]`` entry into its expression
    and optional ``AS alias`` parts.

    Parses *only* the trailing ``AS <ident>`` suffix at the **top level**
    (parens-aware via :func:`_find_top_level_as`). The returned
    ``base_expr`` is the input with the trailing alias stripped. If the
    spec has no top-level ``AS`` or the post-``AS`` token is not a legal
    bare identifier, ``user_alias`` is ``None`` and ``base_expr`` is the
    stripped input.

    This helper is the dual of :func:`parse_inline_aggregate`: the
    aggregate path embeds its own alias logic for the
    ``AGG(...) [AS alias]`` shape, while this function handles the
    non-aggregate case (e.g. ``"product$caption AS productName"``).

    Parameters
    ----------
    column_spec:
        A non-empty ``columns[*]`` string. Whitespace-only inputs raise.

    Raises
    ------
    ValueError
        When ``column_spec`` is not a non-empty string after stripping.
    """
    if not isinstance(column_spec, str):
        raise TypeError(
            f"column_spec must be str, got {type(column_spec).__name__}"
        )
    stripped = column_spec.strip()
    if not stripped:
        raise ValueError("column_spec must be a non-empty (non-whitespace) str")

    alias_idx = _find_top_level_as(stripped)
    if alias_idx < 0:
        return ColumnSpecParts(base_expr=stripped, user_alias=None)

    base = stripped[:alias_idx].strip()
    candidate = stripped[alias_idx + 4:].strip()
    if not base or not candidate or not _ALIAS_RE.fullmatch(candidate):
        # Malformed — caller decides whether to treat the whole input
        # as a (likely failing) bare expression. Keep the input intact
        # so error messages can quote it back unchanged.
        return ColumnSpecParts(base_expr=stripped, user_alias=None)

    return ColumnSpecParts(base_expr=base, user_alias=candidate)
