"""BaselineRatio calculator aligned with Java Pivot V9 semantics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from foggy.mcp_spi.semantic import PivotAxisField, PivotMetricItem, PivotRequest

_SYS_META_KEY = "_sys_meta"


@dataclass(frozen=True)
class ResolvedBaselineRatio:
    axis: str
    baseline: str
    of_metric: str


def _extract_field_name(item: str | PivotAxisField) -> str:
    if isinstance(item, str):
        return item
    return item.field


def _is_subtotal_row(row: dict[str, Any]) -> bool:
    meta = row.get(_SYS_META_KEY)
    if isinstance(meta, dict):
        return (
            meta.get("isRowSubtotal") is True
            or meta.get("isColSubtotal") is True
            or meta.get("isGrandTotal") is True
        )
    return False


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    return None


def _tuple_key(row: dict[str, Any], fields: list[str]) -> tuple[Any, ...]:
    return tuple(row.get(field) for field in fields)


def _sort_key(values: tuple[Any, ...]) -> tuple[tuple[int, Any], ...]:
    out = []
    for value in values:
        if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
            out.append((0, float(value)))
        elif value is None:
            out.append((2, ""))
        else:
            out.append((1, str(value)))
    return tuple(out)


def resolve(metric: PivotMetricItem) -> ResolvedBaselineRatio:
    if metric.axis != "columns":
        raise ValueError(
            f"baselineRatio '{metric.name}': only axis='columns' is supported."
        )
    if metric.baseline not in {"first", "last"}:
        raise ValueError(
            f"baselineRatio '{metric.name}': baseline must be 'first' or 'last'."
        )
    return ResolvedBaselineRatio(
        axis=metric.axis,
        baseline=metric.baseline,
        of_metric=metric.of,
    )


def apply(
    items: list[dict[str, Any]],
    pivot: PivotRequest,
    row_fields: list[str],
    col_fields: list[str],
    key_map: dict[str, str],
) -> list[dict[str, Any]]:
    baseline_ratio_metrics = _collect_baseline_ratio_metrics(pivot)
    if not baseline_ratio_metrics:
        return items
    if not col_fields:
        raise ValueError("baselineRatio requires at least one columns axis field.")

    display_row_fields = [key_map.get(field, field) for field in row_fields]
    display_col_fields = [key_map.get(field, field) for field in col_fields]

    column_domain = sorted(
        {
            _tuple_key(row, display_col_fields)
            for row in items
            if not _is_subtotal_row(row)
            and all(row.get(field) is not None for field in display_col_fields)
        },
        key=_sort_key,
    )

    row_col_index = {
        (_tuple_key(row, display_row_fields), _tuple_key(row, display_col_fields)): row
        for row in items
        if not _is_subtotal_row(row)
    }

    for metric in baseline_ratio_metrics:
        resolved = resolve(metric)
        of_key = key_map.get(resolved.of_metric, resolved.of_metric)
        out_key = metric.name
        baseline_col_key = (
            column_domain[0]
            if resolved.baseline == "first" and column_domain
            else column_domain[-1]
            if column_domain
            else None
        )

        for row in items:
            if _is_subtotal_row(row) or baseline_col_key is None:
                row[out_key] = None
                continue

            current = _to_float(row.get(of_key))
            if current is None:
                row[out_key] = None
                continue

            row_key = _tuple_key(row, display_row_fields)
            baseline_row = row_col_index.get((row_key, baseline_col_key))
            baseline = _to_float(baseline_row.get(of_key)) if baseline_row else None
            if baseline is None or baseline == 0.0:
                row[out_key] = None
            else:
                row[out_key] = current / baseline

    return items


def _collect_baseline_ratio_metrics(pivot: PivotRequest) -> list[PivotMetricItem]:
    result = []
    for metric in pivot.metrics:
        if isinstance(metric, PivotMetricItem) and metric.type == "baselineRatio":
            result.append(metric)
    return result
