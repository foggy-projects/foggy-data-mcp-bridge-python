"""Case-insensitive canonical field name resolution.

Resolves user-supplied field names that differ only by case from the
canonical (schema-defined) field name. Example: ``aroverdueamount``
resolves to canonical ``arOverdueAmount``.

Rules:
* Only case-only variants are resolved.  ``ar_overdue_amount`` is NOT
  treated as equivalent to ``arOverdueAmount`` — that would be
  camelCase/snake_case conversion, which must remain explicit.
* If the schema contains two fields that differ only by case (e.g.
  ``amount`` and ``Amount``), referencing ``AMOUNT`` raises
  ``CaseInsensitiveFieldAmbiguousError`` — fail-closed.
* If no match exists (exact or case-insensitive), the input is returned
  unchanged so downstream unknown-field handling can surface its own
  error.

Feature flag
------------
Enabled by default.  Disable via constructor parameter or environment
variable ``FOGGY_DATASET_CASE_INSENSITIVE_FIELD_RESOLVE=false``.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Set

import re

logger = logging.getLogger(__name__)

_BARE_FIELD_RE = re.compile(r"^[A-Za-z_]\w*(?:\$\w+)?$")
_BARE_ALIAS_RE = re.compile(
    r"^\s*([A-Za-z_]\w*(?:\$\w+)?)\s+as\s+([A-Za-z_]\w*)\s*$",
    re.IGNORECASE,
)


class CaseInsensitiveFieldAmbiguousError(Exception):
    """Raised when a field reference matches multiple canonical names
    that differ only by case."""

    error_code: str = "CASE_INSENSITIVE_FIELD_AMBIGUOUS"

    def __init__(self, field: str, candidates: List[str]) -> None:
        self.field = field
        self.candidates = sorted(candidates)
        super().__init__(
            f"Field '{field}' is ambiguous — matches multiple canonical "
            f"fields that differ only by case: {self.candidates}"
        )


class CaseInsensitiveFieldResolver:
    """Resolve field names using case-insensitive matching against a
    canonical schema.

    Usage::

        resolver = CaseInsensitiveFieldResolver({"arOverdueAmount", "salesAmount"})
        resolver.resolve("aroverdueamount")   # → "arOverdueAmount"
        resolver.resolve("arOverdueAmount")   # → "arOverdueAmount" (exact)
        resolver.resolve("ar_overdue_amount") # → "ar_overdue_amount" (no match)

    Parameters
    ----------
    canonical_fields:
        The set of canonical (schema-defined) field names.
    """

    def __init__(self, canonical_fields: Set[str]) -> None:
        self._canonical: Set[str] = frozenset(canonical_fields)
        # Build lowered → [canonical, …] index
        self._lower_index: Dict[str, List[str]] = {}
        for name in canonical_fields:
            key = name.lower()
            self._lower_index.setdefault(key, []).append(name)

    def resolve(self, field_name: str) -> str:
        """Return the canonical field name for ``field_name``.

        Resolution order:
        1. Exact match → return as-is (short-circuit).
        2. Unique case-insensitive match → return canonical name.
        3. Multiple case-insensitive matches → raise ambiguity error.
        4. No match → return ``field_name`` unchanged (let downstream
           unknown-field handling surface its own error).
        """
        if field_name in self._canonical:
            return field_name
        key = field_name.lower()
        candidates = self._lower_index.get(key)
        if candidates is None:
            return field_name  # no match
        if len(candidates) == 1:
            canonical = candidates[0]
            logger.debug(
                "Case-insensitive field resolve: '%s' → '%s'",
                field_name, canonical,
            )
            return canonical
        raise CaseInsensitiveFieldAmbiguousError(field_name, candidates)

    def resolve_or_none(self, field_name: str) -> Optional[str]:
        """Like :meth:`resolve` but returns ``None`` when no match exists
        (instead of returning the input unchanged)."""
        if field_name in self._canonical:
            return field_name
        key = field_name.lower()
        candidates = self._lower_index.get(key)
        if candidates is None:
            return None
        if len(candidates) == 1:
            return candidates[0]
        raise CaseInsensitiveFieldAmbiguousError(field_name, candidates)


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------

_ENV_VAR = "FOGGY_DATASET_CASE_INSENSITIVE_FIELD_RESOLVE"


def case_insensitive_field_resolve_enabled(
    constructor_value: Optional[bool] = None,
) -> bool:
    """Return whether case-insensitive field resolution is enabled.

    Resolution order:
    1. Explicit constructor value (when not None).
    2. Environment variable ``FOGGY_DATASET_CASE_INSENSITIVE_FIELD_RESOLVE``.
    3. Default ``True``.
    """
    if constructor_value is not None:
        return constructor_value
    env = os.getenv(_ENV_VAR)
    if env is None or env.strip() == "":
        return True
    return env.strip().lower() not in {"0", "false", "no", "off"}


# ---------------------------------------------------------------------------
# Request-level resolution helpers
# ---------------------------------------------------------------------------


def resolve_slice_fields(
    items: Any,
    resolver: CaseInsensitiveFieldResolver,
) -> Any:
    """Recursively resolve field names in a slice/having condition tree.

    Handles both list-of-dicts and nested ``$or``/``$and``/``or``/``and``
    logical groups.  Returns a new structure with resolved field names;
    the original is not mutated.
    """
    if items is None:
        return items
    if isinstance(items, list):
        return [resolve_slice_fields(item, resolver) for item in items]
    if isinstance(items, dict):
        out = dict(items)
        # Resolve top-level field
        for key in ("field", "fieldName", "column"):
            val = out.get(key)
            if isinstance(val, str) and val:
                out[key] = resolver.resolve(val)
        # Recurse into nested groups
        for key in ("conditions", "children", "filters",
                     "$or", "$and", "or", "and"):
            nested = out.get(key)
            if isinstance(nested, list):
                out[key] = resolve_slice_fields(nested, resolver)
        return out
    return items


def resolve_order_by_fields(
    order_by: Any,
    resolver: CaseInsensitiveFieldResolver,
) -> Any:
    """Resolve field names in an order_by list.

    Supports dict entries ``{"field": "…"}`` and string shorthand
    ``"-fieldName"`` / ``"+fieldName"`` / ``"fieldName"``.
    """
    if order_by is None:
        return order_by
    if not isinstance(order_by, list):
        return order_by
    result = []
    for item in order_by:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped.startswith(("-", "+")):
                prefix = stripped[0]
                field = stripped[1:].strip()
                resolved = resolver.resolve(field)
                result.append(f"{prefix}{resolved}")
            elif ":" in stripped:
                field, direction = stripped.split(":", 1)
                resolved = resolver.resolve(field.strip())
                result.append(f"{resolved}:{direction.strip()}")
            else:
                parts = stripped.rsplit(None, 1)
                if len(parts) == 2 and parts[1].lower() in {"asc", "desc"}:
                    resolved = resolver.resolve(parts[0].strip())
                    result.append(f"{resolved} {parts[1].lower()}")
                else:
                    result.append(resolver.resolve(stripped))
        elif isinstance(item, dict):
            out = dict(item)
            for key in ("field", "fieldName", "column"):
                val = out.get(key)
                if isinstance(val, str) and val:
                    prefix = ""
                    field = val.strip()
                    if field.startswith(("-", "+")):
                        prefix = field[0]
                        field = field[1:].strip()
                    if ":" in field:
                        name, direction = field.split(":", 1)
                        out[key] = prefix + resolver.resolve(name.strip()) + f":{direction.strip()}"
                    else:
                        parts = field.rsplit(None, 1)
                        if len(parts) == 2 and parts[1].lower() in {"asc", "desc"}:
                            out[key] = prefix + resolver.resolve(parts[0].strip()) + f" {parts[1].lower()}"
                        else:
                            out[key] = prefix + resolver.resolve(field)
            result.append(out)
        else:
            # Object with attributes
            field = getattr(item, "field", None) or getattr(item, "field_name", None)
            if isinstance(field, str) and field:
                # Can't mutate frozen objects; pass through and let
                # downstream normalization handle it.
                result.append(item)
            else:
                result.append(item)
    return result


def resolve_group_by_fields(
    group_by: Any,
    resolver: CaseInsensitiveFieldResolver,
) -> Any:
    """Resolve field names in a group_by list."""
    if group_by is None:
        return group_by
    if not isinstance(group_by, list):
        return group_by
    result = []
    for item in group_by:
        if isinstance(item, str):
            result.append(resolver.resolve(item))
        elif isinstance(item, dict):
            out = dict(item)
            for key in ("field", "fieldName", "column"):
                val = out.get(key)
                if isinstance(val, str) and val:
                    out[key] = resolver.resolve(val)
            result.append(out)
        else:
            result.append(item)
    return result


def resolve_columns(
    columns: Any,
    resolver: CaseInsensitiveFieldResolver,
) -> Any:
    """Resolve field names in a columns list.

    Bare identifiers and bare aliases (``field AS alias``) are resolved.
    Other expressions like ``SUM(field) AS alias`` are left to the
    downstream expression parser.
    """
    if columns is None:
        return columns
    if not isinstance(columns, list):
        return columns

    result = []
    for col in columns:
        if isinstance(col, str):
            stripped = col.strip()
            if _BARE_FIELD_RE.match(stripped):
                result.append(resolver.resolve(stripped))
            elif match := _BARE_ALIAS_RE.match(stripped):
                result.append(f"{resolver.resolve(match.group(1))} AS {match.group(2)}")
            else:
                result.append(col)
        else:
            result.append(col)
    return result
