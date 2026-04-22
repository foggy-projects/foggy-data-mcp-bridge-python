"""Column-alias extraction for Compose Query `columns[*]` strings.

Grammar (very small subset, case-insensitive keyword):

    <column_spec>   ::= <expression> (<ws>+ "AS" <ws>+ <identifier>)?
    <identifier>    ::= <letter|underscore> (<letter|digit|underscore|$>)*

Examples:

    "orderId"                         → output = "orderId"           · expr = "orderId"
    "customer$id"                     → output = "customer$id"       · expr = "customer$id"
    "customer$id AS customerId"       → output = "customerId"        · expr = "customer$id"
    "SUM(amount)"                     → output = "SUM(amount)"       · expr = "SUM(amount)"
    "SUM(amount) AS totalAmount"      → output = "totalAmount"       · expr = "SUM(amount)"
    "SUM(IIF(isOverdue==1,x,0)) AS y" → output = "y"                 · expr = "SUM(IIF(...))"
    "  foo   AS   bar  "              → output = "bar"               · expr = "foo"

Design notes
------------

1. ``AS`` matching is *case-insensitive* and requires whitespace on both
   sides — this avoids false-positives inside string literals (e.g.
   ``"some '...AS...' string"``) and inside identifiers (``"ASSETS"``).

2. We match ``AS`` at the **last** occurrence at the top level — this way
   a legal expression like ``"CAST(x AS INT) AS y"`` (currently not a
   supported cast syntax in fsscript but could be in future) still yields
   the outermost alias ``y``. M4 doesn't implement full parser-level
   parenthesis tracking because none of the current allowed functions
   accept ``AS`` in their argument positions. A future M4.5 could upgrade
   this to a paren-aware scanner if CAST support lands.

3. We validate the alias as a simple identifier. Anything weirder (spaces,
   operators, dots) in the alias slot is treated as "not an alias" and
   the whole string becomes the expression. This is the safe failure
   mode: the derivation step will then try to use the full expression
   text as the output column name and surface a more specific error if
   that causes a downstream conflict.
"""

from __future__ import annotations

import re
from typing import NamedTuple


# Case-insensitive ``AS`` surrounded by whitespace, anchored so we scan
# all occurrences; we then pick the LAST match.
_AS_PATTERN = re.compile(r"\s+AS\s+", re.IGNORECASE)

# Alias side must be a plain identifier (letter/digit/underscore/``$``).
# ``$`` allowed so dimension-path aliases like ``customer$id`` survive
# the validation — though in practice most users pick camelCase aliases.
_ALIAS_IDENT = re.compile(r"\A[A-Za-z_][A-Za-z0-9_$]*\Z")


class ColumnAliasParts(NamedTuple):
    """Result of :func:`extract_column_alias`.

    Attributes
    ----------
    expression:
        The expression portion with outer whitespace stripped.
        Equals the original (stripped) input when no alias was found.
    output_name:
        The alias when present; otherwise the stripped expression text.
        This is what downstream plans reference the column by.
    has_alias:
        ``True`` iff the input contained an ``AS <identifier>`` suffix.
    """

    expression: str
    output_name: str
    has_alias: bool


def extract_column_alias(column_spec: str) -> ColumnAliasParts:
    """Split a ``columns[*]`` entry into its expression and output-name parts.

    Parameters
    ----------
    column_spec:
        A non-empty string from ``plan.columns``. Typing-level non-empty
        is enforced upstream in ``from_()``/``plan.query()`` but we still
        guard here for direct callers.

    Returns
    -------
    :class:`ColumnAliasParts`

    Raises
    ------
    ValueError
        When ``column_spec`` is not a non-empty str.
    """
    if not isinstance(column_spec, str):
        raise TypeError(
            f"column_spec must be str, got {type(column_spec).__name__}"
        )
    stripped = column_spec.strip()
    if not stripped:
        raise ValueError("column_spec must be a non-empty (non-whitespace) str")

    # Find all ``AS`` split points; pick the last one to honour the
    # "outermost alias wins" rule sketched in the module docstring.
    matches = list(_AS_PATTERN.finditer(stripped))
    if not matches:
        return ColumnAliasParts(
            expression=stripped, output_name=stripped, has_alias=False
        )

    last = matches[-1]
    candidate_alias = stripped[last.end() :].strip()
    if not _ALIAS_IDENT.match(candidate_alias):
        # Not a legal identifier — treat the entire input as the expression.
        # This preserves safety: a malformed alias never becomes the
        # output name silently.
        return ColumnAliasParts(
            expression=stripped, output_name=stripped, has_alias=False
        )

    expression = stripped[: last.start()].strip()
    if not expression:
        # "AS name" with no preceding expression is not a legal spec;
        # surface this as a structural problem the caller can reject.
        raise ValueError(
            f"column_spec {column_spec!r} has an alias but no expression"
        )

    return ColumnAliasParts(
        expression=expression, output_name=candidate_alias, has_alias=True
    )
