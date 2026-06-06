"""Auxiliary total requery for ordinary Pivot non-additive metrics."""

from __future__ import annotations

from typing import Any

from foggy.dataset_model.definitions.base import AggregationType
from foggy.mcp_spi import SemanticQueryRequest
from foggy.mcp_spi.semantic import PivotRequest

SYS_META_KEY = "_sys_meta"


def apply_auxiliary_totals(
    service: Any,
    model_name: str,
    translated_request: SemanticQueryRequest,
    pivot: PivotRequest,
    items: list[dict[str, Any]],
    key_map: dict[str, str],
    context: Any = None,
) -> list[dict[str, Any]]:
    """Overwrite subtotal/grandTotal cells for non-additive native metrics.

    Ordinary Pivot post-processing can safely sum SUM/COUNT totals in memory,
    but AVG/COUNT_DISTINCT and other non-additive aggregations must be queried
    again at the parent grain. This helper keeps the existing additive path and
    only replaces generated total rows for metrics that need auxiliary requery.
    """
    options = pivot.options
    if not items or not options or not (options.row_subtotals or options.grand_total):
        return items

    non_additive_metrics = _non_additive_native_metrics(service, model_name, pivot)
    if not non_additive_metrics:
        return items

    row_fields = [_field_name(field) for field in pivot.rows]
    col_fields = [_field_name(field) for field in pivot.columns]
    row_keys = [key_map.get(field, field) for field in row_fields]
    col_keys = [key_map.get(field, field) for field in col_fields]
    metric_keys = {
        metric: key_map.get(metric, metric)
        for metric in non_additive_metrics
    }

    result = list(items)

    if options.row_subtotals and len(row_fields) > 1:
        subtotal_group_by = row_fields[:-1] + col_fields
        subtotal_index = _execute_aux_query(
            service,
            model_name,
            translated_request,
            subtotal_group_by,
            non_additive_metrics,
            key_map,
            context,
        )
        subtotal_keys = row_keys[:-1] + col_keys
        _overwrite_rows(
            result,
            subtotal_index,
            subtotal_keys,
            metric_keys,
            "isRowSubtotal",
        )

    if options.grand_total:
        grand_index = _execute_aux_query(
            service,
            model_name,
            translated_request,
            col_fields,
            non_additive_metrics,
            key_map,
            context,
        )
        _overwrite_rows(
            result,
            grand_index,
            col_keys,
            metric_keys,
            "isGrandTotal",
        )

    return result


def _execute_aux_query(
    service: Any,
    model_name: str,
    base_request: SemanticQueryRequest,
    group_by: list[str],
    metrics: list[str],
    key_map: dict[str, str],
    context: Any,
) -> dict[tuple[Any, ...], dict[str, Any]]:
    aux_request = base_request.model_copy(deep=True)
    aux_request.pivot = None
    aux_request.group_by = list(group_by)
    aux_request.columns = list(group_by) + list(metrics)
    aux_request.order_by = []
    aux_request.start = 0
    aux_request.limit = getattr(service, "_max_limit", None)
    aux_request.return_total = False

    response = service.query_model(model_name, aux_request, mode="execute", context=context)
    if response.error:
        raise ValueError(response.error)

    group_keys = [key_map.get(field, field) for field in group_by]
    index: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in response.items or []:
        index[tuple(row.get(key) for key in group_keys)] = row
    return index


def _overwrite_rows(
    items: list[dict[str, Any]],
    aux_index: dict[tuple[Any, ...], dict[str, Any]],
    total_keys: list[str],
    metric_keys: dict[str, str],
    meta_flag: str,
) -> None:
    for row in items:
        meta = row.get(SYS_META_KEY)
        if not isinstance(meta, dict) or not meta.get(meta_flag):
            continue
        key = tuple(row.get(field) for field in total_keys)
        aux_row = aux_index.get(key)
        if aux_row is None:
            raise ValueError(
                "Pivot non-additive auxiliary total query did not return "
                f"a row for {meta_flag} key {key!r}."
            )
        for metric, metric_key in metric_keys.items():
            row[metric_key] = aux_row.get(metric_key)


def _non_additive_native_metrics(
    service: Any,
    model_name: str,
    pivot: PivotRequest,
) -> list[str]:
    table_model = service.get_model(model_name)
    if table_model is None:
        return []

    metrics: list[str] = []
    seen: set[str] = set()
    for item in pivot.metrics:
        if isinstance(item, str):
            metric_name = item
        elif item.type == "native":
            metric_name = item.of
        else:
            continue
        if metric_name in seen:
            continue
        seen.add(metric_name)
        measure = table_model.get_measure(metric_name)
        aggregation = getattr(measure, "aggregation", None) if measure else None
        if _needs_auxiliary_requery(aggregation):
            metrics.append(metric_name)
    return metrics


def _needs_auxiliary_requery(aggregation: Any) -> bool:
    value = getattr(aggregation, "value", aggregation)
    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.lower()
    elif isinstance(value, AggregationType):
        normalized = value.value
    else:
        normalized = str(value).lower()
    return normalized not in {"sum", "count"}


def _field_name(item: Any) -> str:
    if isinstance(item, str):
        return item
    return item.field
