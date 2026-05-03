"""Cascade subtotal / grandTotal helpers.

These helpers run only after C2 staged SQL has already selected the surviving
rows domain. They do not rank, filter, or recover unsupported cascade shapes.
"""

from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Tuple

from foggy.mcp_spi.semantic import PivotAxisField, PivotRequest
from foggy.dataset_model.semantic.pivot.cascade_detector import (
    PIVOT_CASCADE_NON_ADDITIVE_REJECTED,
    PIVOT_CASCADE_SCOPE_UNSUPPORTED,
)

TOTAL_MEMBER = "ALL"
SYS_META_KEY = "_sys_meta"


def _field_name(item: Any) -> str:
    if isinstance(item, str):
        return item
    return item.field


def _metric_name(item: Any) -> str:
    if isinstance(item, str):
        return item
    return item.name


def _is_enabled(pivot: PivotRequest) -> bool:
    opts = pivot.options
    return bool(opts and (opts.row_subtotals or opts.column_subtotals or opts.grand_total))


def validate_cascade_totals_supported(service: Any, model_name: str, pivot: PivotRequest) -> None:
    """Reject unsupported cascade total shapes before SQL execution."""
    if not _is_enabled(pivot):
        return

    if pivot.options.column_subtotals:
        raise NotImplementedError(
            f"{PIVOT_CASCADE_SCOPE_UNSUPPORTED}: "
            "columnSubtotals are not supported for Python cascade totals. "
            "Use rowSubtotals and/or grandTotal on rows-axis two-level cascade."
        )

    if len(pivot.rows) != 2:
        raise NotImplementedError(
            f"{PIVOT_CASCADE_SCOPE_UNSUPPORTED}: "
            "Cascade totals require rows-axis exactly two-level cascade."
        )

    if any(isinstance(item, PivotAxisField) and item.hierarchy_mode == "tree"
           for item in list(pivot.rows) + list(pivot.columns)):
        raise NotImplementedError(
            f"{PIVOT_CASCADE_SCOPE_UNSUPPORTED}: "
            "tree + cascade totals are not supported in Python."
        )

    table_model = service.get_model(model_name)
    for metric in pivot.metrics:
        if not isinstance(metric, str) and metric.type != "native":
            raise NotImplementedError(
                f"{PIVOT_CASCADE_NON_ADDITIVE_REJECTED}: "
                "Derived metrics are not supported for cascade totals."
            )

        metric_name = metric if isinstance(metric, str) else metric.of
        measure = table_model.get_measure(metric_name) if table_model else None
        agg = getattr(measure, "aggregation", None) if measure else None
        agg_val = getattr(agg, "value", agg) if agg else None
        if agg_val not in ("sum", "count"):
            raise NotImplementedError(
                f"{PIVOT_CASCADE_NON_ADDITIVE_REJECTED}: "
                f"Non-additive metric {metric_name} with aggregation {agg_val} "
                "is not supported for cascade totals."
            )


def append_cascade_totals(
    items: List[Dict[str, Any]],
    pivot: PivotRequest,
    key_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Append additive subtotal/grandTotal rows over surviving cascade cells."""
    opts = pivot.options
    if not opts or (not opts.row_subtotals and not opts.grand_total):
        return items

    row_fields = [_field_name(item) for item in pivot.rows]
    col_fields = [_field_name(item) for item in pivot.columns]
    metrics = [_metric_name(item) for item in pivot.metrics]

    row_keys = [key_map.get(field, field) for field in row_fields]
    col_keys = [key_map.get(field, field) for field in col_fields]
    metric_keys = [key_map.get(metric, metric) for metric in metrics]

    result = list(items)

    if opts.row_subtotals and len(row_keys) > 1:
        subtotal_rows = _build_row_subtotals(items, row_keys, col_keys, metric_keys)
        result.extend(subtotal_rows)

    if opts.grand_total:
        grand_rows = _build_grand_totals(items, row_keys, col_keys, metric_keys)
        result.extend(grand_rows)

    return result


def _build_row_subtotals(
    items: List[Dict[str, Any]],
    row_keys: List[str],
    col_keys: List[str],
    metric_keys: List[str],
) -> List[Dict[str, Any]]:
    parent_keys = row_keys[:-1]
    leaf_key = row_keys[-1]
    groups: "OrderedDict[Tuple[Any, ...], List[Dict[str, Any]]]" = OrderedDict()

    for row in items:
        key = tuple(row.get(k) for k in parent_keys + col_keys)
        groups.setdefault(key, []).append(row)

    subtotal_rows: List[Dict[str, Any]] = []
    for key, rows in groups.items():
        subtotal: Dict[str, Any] = {}
        parent_values = key[:len(parent_keys)]
        col_values = key[len(parent_keys):]
        for field, value in zip(parent_keys, parent_values):
            subtotal[field] = value
        subtotal[leaf_key] = TOTAL_MEMBER
        for field, value in zip(col_keys, col_values):
            subtotal[field] = value
        for metric in metric_keys:
            subtotal[metric] = _sum_metric(row.get(metric) for row in rows)
        subtotal[SYS_META_KEY] = {"isRowSubtotal": True}
        subtotal_rows.append(subtotal)

    return subtotal_rows


def _build_grand_totals(
    items: List[Dict[str, Any]],
    row_keys: List[str],
    col_keys: List[str],
    metric_keys: List[str],
) -> List[Dict[str, Any]]:
    groups: "OrderedDict[Tuple[Any, ...], List[Dict[str, Any]]]" = OrderedDict()

    if items:
        for row in items:
            key = tuple(row.get(k) for k in col_keys)
            groups.setdefault(key, []).append(row)
    else:
        groups[tuple()] = []

    grand_rows: List[Dict[str, Any]] = []
    for key, rows in groups.items():
        grand: Dict[str, Any] = {}
        for field in row_keys:
            grand[field] = TOTAL_MEMBER
        for field, value in zip(col_keys, key):
            grand[field] = value
        for metric in metric_keys:
            grand[metric] = _sum_metric(row.get(metric) for row in rows)
        grand[SYS_META_KEY] = {"isGrandTotal": True}
        grand_rows.append(grand)

    return grand_rows


def _sum_metric(values: Iterable[Any]) -> Any:
    total: Decimal | None = None
    saw_float = False
    for value in values:
        if value is None:
            continue
        if isinstance(value, float):
            saw_float = True
        try:
            dec = value if isinstance(value, Decimal) else Decimal(str(value))
        except Exception:
            continue
        total = dec if total is None else total + dec

    if total is None:
        return None
    if saw_float:
        return float(total)
    return total
