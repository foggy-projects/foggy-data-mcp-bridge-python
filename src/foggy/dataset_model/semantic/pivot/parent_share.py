"""ParentShare Calculator — Python port of Java ParentShareCalculator (Phase 2.8).

Computes parent-level share for each child row after SQL execution.

Semantics: ``current child metric value / parent aggregate metric value``

First-version constraints (aligned with Java):
- Only supports same-axis adjacent levels
- Only ``axis="rows"`` (columns rejected at Pydantic validator level)
- Division by zero / missing parent / null child → ``None``
- Subtotal rows → ``None``
- Does NOT participate in having/orderBy/limit/cascade/SQL pushdown
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from foggy.mcp_spi.semantic import PivotMetricItem, PivotRequest, PivotAxisField

_NULL_SENTINEL = "__null__"
_SYS_META_KEY = "_sys_meta"
_GROUP_SEP = "\x1f"


@dataclass
class ResolvedParentShare:
    """Result of resolving a parentShare metric's axis/level/parentLevel."""
    axis: str
    level: str
    parent_level: str
    axis_fields: List[str]
    of_metric: str = ""


def _extract_field_name(item: Union[str, PivotAxisField]) -> str:
    if isinstance(item, str):
        return item
    return item.field


def _is_subtotal_row(row: Dict[str, Any]) -> bool:
    """Check if a row is a subtotal/grandTotal synthetic row."""
    meta = row.get(_SYS_META_KEY)
    if isinstance(meta, dict):
        return (
            meta.get("isRowSubtotal") is True
            or meta.get("isColSubtotal") is True
            or meta.get("isGrandTotal") is True
        )
    return False


def _to_float(value: Any) -> Optional[float]:
    """Return a numeric value for SQL aggregate results."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    return None


def resolve(
    metric: PivotMetricItem,
    row_fields: List[str],
    col_fields: List[str],
) -> ResolvedParentShare:
    """Infer or validate axis/level/parentLevel for a parentShare metric.

    Raises ``ValueError`` when the configuration is invalid.
    """
    axis = metric.axis
    level = metric.level
    parent_level = metric.parent_level

    # --- Explicit level/parentLevel ---
    if level is not None and parent_level is not None:
        if axis is None:
            if level in row_fields and parent_level in row_fields:
                axis = "rows"
            elif level in col_fields and parent_level in col_fields:
                raise ValueError(
                    f"parentShare '{metric.name}': columns-axis parentShare is not "
                    "supported. Only rows axis is supported."
                )
            else:
                raise ValueError(
                    f"parentShare '{metric.name}': level='{level}' and "
                    f"parentLevel='{parent_level}' are not on the same axis."
                )

        axis_fields = row_fields if axis == "rows" else col_fields
        level_idx = axis_fields.index(level) if level in axis_fields else -1
        parent_idx = axis_fields.index(parent_level) if parent_level in axis_fields else -1

        if level_idx < 0 or parent_idx < 0:
            raise ValueError(
                f"parentShare '{metric.name}': level/parentLevel not found "
                f"in {axis} axis fields."
            )
        if level_idx != parent_idx + 1:
            raise ValueError(
                f"parentShare '{metric.name}': level and parentLevel must be "
                f"adjacent. parentLevel at index={parent_idx}, "
                f"level at index={level_idx}."
            )

        return ResolvedParentShare(
            axis=axis, level=level, parent_level=parent_level,
            axis_fields=axis_fields,
        )

    # --- Implicit inference ---
    if axis is None:
        if len(row_fields) >= 2:
            axis = "rows"
        else:
            raise ValueError(
                f"parentShare '{metric.name}': cannot infer parent/child levels — "
                f"rows has fewer than 2 levels. "
                "Specify axis/level/parentLevel explicitly."
            )

    axis_fields = row_fields  # v1: only rows supported
    if len(axis_fields) < 2:
        raise ValueError(
            f"parentShare '{metric.name}': axis='{axis}' has fewer than 2 "
            "levels, cannot infer parent/child relationship."
        )

    # Take last two adjacent levels
    parent_level = axis_fields[-2]
    level = axis_fields[-1]

    return ResolvedParentShare(
        axis=axis, level=level, parent_level=parent_level,
        axis_fields=axis_fields,
    )


def _build_parent_agg_index(
    items: List[Dict[str, Any]],
    resolved: ResolvedParentShare,
    col_fields: List[str],
    of_key: str,
) -> Dict[str, float]:
    """Build parent-level aggregation index.

    Key = parentLevel value (+ ancestor axis values + cross-axis col values).
    Value = SUM of the ``of`` metric across all child rows sharing that parent.
    """
    # Group keys = all axis fields up to and including parentLevel + col fields
    axis_fields = resolved.axis_fields
    parent_idx = axis_fields.index(resolved.parent_level)
    group_keys = list(axis_fields[: parent_idx + 1])
    if resolved.axis == "rows":
        group_keys.extend(col_fields)

    index: Dict[str, float] = {}

    for row in items:
        if _is_subtotal_row(row):
            continue

        key = _GROUP_SEP.join(
            str(row.get(k, _NULL_SENTINEL)) for k in group_keys
        )

        val = _to_float(row.get(of_key))
        if val is not None:
            index[key] = index.get(key, 0.0) + val

    return index


def _build_parent_key(
    row: Dict[str, Any],
    resolved: ResolvedParentShare,
    col_fields: List[str],
) -> str:
    """Build the parent-index lookup key for a single row."""
    axis_fields = resolved.axis_fields
    parent_idx = axis_fields.index(resolved.parent_level)
    group_keys = list(axis_fields[: parent_idx + 1])
    if resolved.axis == "rows":
        group_keys.extend(col_fields)

    return _GROUP_SEP.join(
        str(row.get(k, _NULL_SENTINEL)) for k in group_keys
    )


def apply(
    items: List[Dict[str, Any]],
    pivot: PivotRequest,
    row_fields: List[str],
    col_fields: List[str],
    key_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Compute parentShare for all parentShare metrics and write into items.

    Args:
        items: Result rows (post MemoryCubeProcessor, may include grandTotal rows).
        pivot: Original PivotRequest.
        row_fields: Row axis field names (QM-level, before key_map).
        col_fields: Column axis field names (QM-level, before key_map).
        key_map: QM field name → display column name mapping.

    Returns:
        The same ``items`` list with parentShare values written in.
    """
    parent_share_metrics = _collect_parent_share_metrics(pivot)
    if not parent_share_metrics:
        return items

    # Resolve display-level field names via key_map
    display_row_fields = [key_map.get(f, f) for f in row_fields]
    display_col_fields = [key_map.get(f, f) for f in col_fields]

    for ps_metric in parent_share_metrics:
        # Map metric's level/parentLevel through key_map since resolve()
        # operates on display-level field names (matching items dict keys).
        mapped_metric = ps_metric
        if ps_metric.level is not None or ps_metric.parent_level is not None:
            mapped_metric = ps_metric.model_copy(update={
                "level": key_map.get(ps_metric.level, ps_metric.level) if ps_metric.level else None,
                "parent_level": key_map.get(ps_metric.parent_level, ps_metric.parent_level) if ps_metric.parent_level else None,
            })

        # Resolve using display-level field names (items use display names)
        resolved = resolve(mapped_metric, display_row_fields, display_col_fields)
        of_key = key_map.get(ps_metric.of, ps_metric.of)
        resolved.of_metric = of_key

        # Build parent aggregation index
        parent_index = _build_parent_agg_index(
            items, resolved, display_col_fields, of_key,
        )

        # Output key for the parentShare result
        out_key = ps_metric.name

        # Compute parentShare for each row
        for row in items:
            if _is_subtotal_row(row):
                row[out_key] = None
                continue

            current_val = _to_float(row.get(of_key))
            if current_val is None:
                row[out_key] = None
                continue

            parent_key = _build_parent_key(row, resolved, display_col_fields)
            parent_val = parent_index.get(parent_key)

            if parent_val is None or parent_val == 0.0:
                row[out_key] = None
            else:
                row[out_key] = current_val / parent_val

    return items


def _collect_parent_share_metrics(pivot: PivotRequest) -> List[PivotMetricItem]:
    """Extract parentShare metrics from the PivotRequest."""
    result = []
    for m in pivot.metrics:
        if isinstance(m, PivotMetricItem) and m.type == "parentShare":
            result.append(m)
    return result
