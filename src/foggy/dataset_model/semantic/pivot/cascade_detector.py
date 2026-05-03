"""Pivot Cascade Detector — Python v1.9 P1 Fail-Closed.

Identifies cascade semantics (multi-level TopN/having chains) and rejects them
before they can enter the in-memory MemoryCubeProcessor path.

Java 9.1 C2 staged SQL cascade is NOT implemented in Python P1.
All cascade shapes must be rejected with a stable error code prefix.

Allowed (S3 preserved):
  - flat/grid baseline
  - single-level TopN (limit + orderBy on exactly one axis field)
  - single-level having (having on exactly one axis field)
  - crossjoin grid shaping

Rejected (P1 fail-closed):
  - Two or more axis fields on the SAME axis each carrying limit or having
  - limit without explicit orderBy on any cascade level
  - columns-axis cascade
  - rows cascade + columns TopN/having mixed
  - three or more cascade levels
  - hierarchyMode=tree + any cascade
  - derived metrics (parentShare / baselineRatio) + any cascade
  - non-additive metric participation when detectable from request metadata
"""

from __future__ import annotations

from typing import Any, List, Optional, Union

from foggy.mcp_spi.semantic import (
    PivotAxisField,
    PivotMetricItem,
    PivotRequest,
)

# Stable error-code prefixes used in rejection messages.
# These are consumed by tests, MCP clients, and LLMs for routing.
PIVOT_CASCADE_SQL_REQUIRED = "PIVOT_CASCADE_SQL_REQUIRED"
PIVOT_CASCADE_ORDER_BY_REQUIRED = "PIVOT_CASCADE_ORDER_BY_REQUIRED"
PIVOT_CASCADE_TREE_REJECTED = "PIVOT_CASCADE_TREE_REJECTED"
PIVOT_CASCADE_CROSS_AXIS_REJECTED = "PIVOT_CASCADE_CROSS_AXIS_REJECTED"
PIVOT_CASCADE_NON_ADDITIVE_REJECTED = "PIVOT_CASCADE_NON_ADDITIVE_REJECTED"
PIVOT_CASCADE_SCOPE_UNSUPPORTED = "PIVOT_CASCADE_SCOPE_UNSUPPORTED"


def _is_constrained(item: Union[str, PivotAxisField]) -> bool:
    """Return True if this axis item carries a TopN limit OR a having filter."""
    if isinstance(item, str):
        return False
    has_limit = item.limit is not None and item.limit > 0
    has_having = item.having is not None
    return has_limit or has_having


def _has_limit(item: Union[str, PivotAxisField]) -> bool:
    if isinstance(item, str):
        return False
    return item.limit is not None and item.limit > 0


def _has_having(item: Union[str, PivotAxisField]) -> bool:
    if isinstance(item, str):
        return False
    return item.having is not None


def _has_tree(item: Union[str, PivotAxisField]) -> bool:
    if isinstance(item, str):
        return False
    return item.hierarchy_mode == "tree"


def _has_order_by(item: Union[str, PivotAxisField]) -> bool:
    if isinstance(item, str):
        return False
    return bool(item.order_by)


def _count_constrained(axis: List[Any]) -> int:
    """Count how many items on an axis carry limit or having."""
    return sum(1 for item in axis if _is_constrained(item))


def _has_derived_metrics(pivot: PivotRequest) -> bool:
    """Return True if any metric is parentShare or baselineRatio."""
    for m in pivot.metrics:
        if isinstance(m, PivotMetricItem):
            if m.type in ("parentShare", "baselineRatio"):
                return True
    return False


def detect_cascade_and_raise(pivot: PivotRequest) -> None:
    """Inspect a PivotRequest and raise NotImplementedError for cascade shapes.

    Call this BEFORE routing to MemoryCubeProcessor.

    Raises
    ------
    NotImplementedError
        When a cascade shape is detected.  The message starts with a stable
        error-code prefix from this module's constants.
    """
    rows: List[Any] = list(pivot.rows)
    columns: List[Any] = list(pivot.columns)

    rows_constrained = _count_constrained(rows)
    cols_constrained = _count_constrained(columns)

    # ─── Rule 1: any tree field combined with any constrained field on either axis ───
    # This also covers a single field that simultaneously carries tree + limit/having.
    any_tree = any(_has_tree(item) for item in rows + columns)
    if any_tree and (rows_constrained > 0 or cols_constrained > 0):
        raise NotImplementedError(
            f"{PIVOT_CASCADE_TREE_REJECTED}: "
            "hierarchyMode=tree cannot be combined with limit/having cascade. "
            "Use the Java engine for tree cascade."
        )
    # Also reject a single field that has tree but no limit/having co-occurring elsewhere —
    # that case is handled by the generic hierarchyMode guard in executor.py.

    # ─── Rule 2: columns-axis cascade ───
    if cols_constrained > 0:
        raise NotImplementedError(
            f"{PIVOT_CASCADE_CROSS_AXIS_REJECTED}: "
            "Columns-axis limit/having is not supported in Python P1. "
            "Only rows-axis single-level TopN/having is supported."
        )

    # ─── Rule 3: mixed cross-axis cascade (rows constrained + columns constrained) ───
    # Already covered by Rule 2 above (cols_constrained > 0 rejects).

    # ─── Rule 4: rows cascade (two or more constrained levels) ───
    if rows_constrained >= 2:
        raise NotImplementedError(
            f"{PIVOT_CASCADE_SQL_REQUIRED}: "
            f"Detected {rows_constrained} axis levels with limit/having on the rows axis. "
            "Multi-level cascade requires staged SQL (Java 9.1 C2) which is not "
            "implemented in Python P1.  Use the Java engine."
        )

    # ─── Rule 5: limit without orderBy on the single constrained level ───
    for item in rows:
        if _has_limit(item) and not _has_order_by(item):
            field = item.field if isinstance(item, PivotAxisField) else item
            raise NotImplementedError(
                f"{PIVOT_CASCADE_ORDER_BY_REQUIRED}: "
                f"Field '{field}' has a limit but no explicit orderBy. "
                "An explicit orderBy is required for deterministic TopN ranking."
            )

    # ─── Rule 6: derived metrics combined with any constrained level ───
    if rows_constrained > 0 and _has_derived_metrics(pivot):
        raise NotImplementedError(
            f"{PIVOT_CASCADE_NON_ADDITIVE_REJECTED}: "
            "parentShare / baselineRatio metrics cannot be combined with "
            "limit/having axis operations in Python P1."
        )
