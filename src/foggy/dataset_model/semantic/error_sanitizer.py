"""Query error sanitizer — strip physical schema from DB/executor errors.

Background (BUG-007 v1.3)
-------------------------
When a query slips past ``SchemaAwareFieldValidationStep`` / ``validate_query_fields``
and the database rejects the SQL, the raw executor error can include physical
table aliases (``t``, ``j1``, ``dp`` …) and physical column names
(``move_name``, ``account_move_line.move_name`` …).  This breaks the
governance boundary declared by ``fieldAccess`` / ``deniedColumns`` /
``PhysicalColumnMapping``: the blacklist hides columns from results but the
error channel can still disclose them.

This module provides :func:`sanitize_engine_error`, a pure, side-effect-free
helper that rewrites raw error text to QM vocabulary.  It is intentionally
conservative:

- ``<alias>.<qm_token>``  →  ``<qm_token>``           (strip alias, token has ``$``)
- ``<alias>.<phys_col>``  →  ``<qm_field>``           (when mapping is provided)
- ``<alias>.<phys_col>``  →  ``<phys_col>``           (no mapping — still strip alias)
- ``"<alias>.<phys_col>"``  →  ``"<qm_field>"``       (same rules inside double quotes)
- Any ``[table|alias].<col>`` references are rewritten; DB-specific HINT /
  context phrasing is left in place but no longer cites physical identifiers.
- The model name is prepended when provided so upstream audit / LLM routing
  has clean context.

Aligned with Java ``QueryErrorSanitizer`` (see same-named class in
``foggy-data-mcp-bridge``) so MCP error surfaces stay engine-agnostic.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from foggy.dataset_model.semantic.physical_column_mapping import PhysicalColumnMapping


# Matches ``<alias>.<column>`` where ``<alias>`` is a plain identifier and
# ``<column>`` may be either a QM-style token (contains ``$``) or a physical
# column name.  Negative lookarounds prevent splicing across longer tokens.
_ALIAS_COL_RE = re.compile(
    r'(?<![A-Za-z0-9_$])([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_$][A-Za-z0-9_$]*)(?![A-Za-z0-9_$])'
)

# Matches ``"anything-not-double-quote"`` — used to find quoted identifiers
# (PostgreSQL quotes physical names; inside we may find ``alias.col`` or
# plain ``col``).
_DQUOTED_RE = re.compile(r'"([^"]+)"')

# Matches PostgreSQL's full ``HINT: Perhaps you meant to reference the column
# "X".`` line.  We translate this to QM ``Did you mean 'X'?`` phrasing so
# upstream consumers (AI, end users) don't see DB-specific vocabulary and so
# the suggestion remains actionable even after physical->QM translation.
_HINT_COLUMN_RE = re.compile(
    r'(?im)^\s*HINT:\s*Perhaps you meant to reference the column\s+"([^"]+)"\.?\s*$'
)

# Fallback: any remaining standalone ``HINT:`` line is DB-specific noise.
# Strip it so the error surface stays engine-agnostic.
_HINT_ANY_RE = re.compile(r'(?im)^\s*HINT:[^\n]*$')


def _physical_col_to_qm(
    mapping: "PhysicalColumnMapping",
    col: str,
    table_hint: Optional[str] = None,
) -> Optional[str]:
    """Look up a QM field name for a physical column.

    ``table_hint`` narrows the search when available; otherwise we match on
    column name across any table, returning the first QM field found.
    Returns ``None`` when no mapping is known.
    """
    for phys_key, qm_list in mapping.physical_to_qm.items():
        tbl, c = phys_key.rsplit(".", 1)
        if c != col:
            continue
        if table_hint and tbl != table_hint:
            continue
        if qm_list:
            return qm_list[0]
    return None


def _translate_ref(
    alias: str,
    col: str,
    mapping: Optional["PhysicalColumnMapping"],
) -> str:
    """Core translation: rewrite a single ``<alias>.<col>`` reference."""
    # QM-style token (e.g. move$date, partner$caption) — strip alias
    if "$" in col:
        return col
    # Physical column — prefer QM translation
    if mapping is not None:
        qm = _physical_col_to_qm(mapping, col, table_hint=alias)
        if qm is None:
            qm = _physical_col_to_qm(mapping, col)
        if qm is not None:
            return qm
    # No mapping — strip the alias prefix, keep column text as-is
    return col


def sanitize_engine_error(
    raw_message: Optional[str],
    *,
    model_name: Optional[str] = None,
    mapping: Optional["PhysicalColumnMapping"] = None,
) -> str:
    """Return a sanitized copy of a raw DB/executor error message.

    See the module docstring for rules.  Safe to call with ``None`` / empty
    input (returns ``""``).
    """
    if not raw_message:
        return ""

    def _replace_bare(match: re.Match) -> str:
        return _translate_ref(match.group(1), match.group(2), mapping)

    # 1. Translate unquoted <alias>.<col> references first
    msg = _ALIAS_COL_RE.sub(_replace_bare, raw_message)

    # 2. Translate double-quoted identifiers — PostgreSQL's canonical way to
    #    name physical identifiers in error messages.
    def _replace_quoted(match: re.Match) -> str:
        inner = match.group(1)
        # "<alias>.<col>"
        if "." in inner:
            left, right = inner.split(".", 1)
            if left and right and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", left):
                # Let the shared _translate_ref do the work
                return f'"{_translate_ref(left, right, mapping)}"'
        # Bare "<col>"
        if "$" in inner:
            return match.group(0)
        if mapping is not None and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", inner):
            qm = _physical_col_to_qm(mapping, inner)
            if qm is not None:
                return f'"{qm}"'
        return match.group(0)

    msg = _DQUOTED_RE.sub(_replace_quoted, msg)

    # 3. Rewrite ``HINT: Perhaps you meant to reference the column "X".`` to
    #    QM-level ``Did you mean 'X'?`` so the suggestion survives but the
    #    DB-specific phrasing and HINT marker do not leak.  The quoted name
    #    in the HINT has already been translated in step 2, so ``X`` is a QM
    #    field when a mapping was supplied.
    msg = _HINT_COLUMN_RE.sub(lambda m: f"Did you mean '{m.group(1)}'?", msg)

    # 4. Drop any remaining HINT: lines entirely — they are DB-specific
    #    breadcrumbs that are not safe to forward unchanged.
    msg = _HINT_ANY_RE.sub("", msg)

    # Collapse multiple blank lines introduced by HINT removal and trim.
    msg = re.sub(r"\n{2,}", "\n", msg).strip()

    # 5. Prepend model context so upstream callers / LLMs know which model
    #    rejected the query, without needing access to SQL.
    if model_name and model_name not in msg:
        msg = f"[{model_name}] {msg}"

    return msg


__all__ = ["sanitize_engine_error"]
