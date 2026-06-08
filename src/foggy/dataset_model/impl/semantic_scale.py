"""Java-aligned semantic scale SQL helpers."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Optional


_SIMPLE_COLUMN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def normalize_semantic_scale_factor(value: Any) -> Optional[Decimal]:
    """Return a validated Decimal scale factor, or ``None`` when unset."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        factor = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"semanticScaleFactor must be numeric: {value!r}") from exc
    if factor <= 0:
        raise ValueError("semanticScaleFactor must be greater than 0")
    return factor


def validate_semantic_scale_column(
    semantic_scale_factor: Any,
    column: Optional[str],
    *,
    has_formula: bool = False,
    field_name: str,
) -> None:
    """Validate the Java semanticScaleFactor column contract."""
    if normalize_semantic_scale_factor(semantic_scale_factor) is None:
        return
    if has_formula and not column:
        return
    if not column or not _SIMPLE_COLUMN_RE.match(str(column)):
        raise ValueError(
            "semanticScaleFactor column must be a physical column name: "
            f"{field_name}"
        )


def semantic_scale_sql_literal(value: Any) -> str:
    """Format a scale factor using the Java SQL literal convention."""
    factor = normalize_semantic_scale_factor(value)
    if factor is None:
        raise ValueError("semanticScaleFactor is not configured")
    literal = format(factor.normalize(), "f")
    if "." not in literal:
        literal = f"{literal}.0"
    return literal


def apply_semantic_scale(sql_expr: str, semantic_scale_factor: Any) -> str:
    """Wrap ``sql_expr`` with semantic unit conversion when configured."""
    if normalize_semantic_scale_factor(semantic_scale_factor) is None:
        return sql_expr
    return f"(({sql_expr}) / {semantic_scale_sql_literal(semantic_scale_factor)})"


def semantic_scale_metadata_value(value: Any) -> Optional[str]:
    """Return metadata string representation for semanticScaleFactor."""
    factor = normalize_semantic_scale_factor(value)
    if factor is None:
        return None
    return format(factor.normalize(), "f")
