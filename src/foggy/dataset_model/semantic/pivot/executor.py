"""Pivot Flat Executor.

Provides validation and translation logic for the S2 Flat Pivot MVP.
"""

from typing import Any, Union, Tuple
from foggy.mcp_spi.semantic import (
    SemanticQueryRequest,
    PivotRequest,
    PivotAxisField,
    PivotMetricItem,
)
from foggy.dataset_model.semantic.pivot.cascade_detector import detect_cascade_and_raise

PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON = "PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON: "

def _extract_field_name(item: Union[str, PivotAxisField]) -> str:
    if isinstance(item, str):
        return item
    return item.field


def validate_and_translate_pivot(request: SemanticQueryRequest) -> Tuple[SemanticQueryRequest, bool]:
    """Validate Pivot support and translate into a standard semantic query request.

    Raises:
        NotImplementedError: If the pivot request uses features not supported.
    """
    pivot: PivotRequest = request.pivot

    if request.columns:
        raise NotImplementedError(f"{PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON}pivot + columns is not supported")
    if request.time_window:
        raise NotImplementedError(f"{PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON}pivot + timeWindow is not supported")

    if pivot.output_format not in ["flat", "grid"]:
        raise NotImplementedError(
            f"{PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON}outputFormat='{pivot.output_format}' "
            f"is not supported. Only 'flat' and 'grid' are supported in S3."
        )

    # columnSubtotals: never supported in any pivot shape.
    if pivot.options.column_subtotals:
        raise NotImplementedError(
            f"{PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON}"
            "columnSubtotals is not supported for any pivot shape. "
            "Remove columnSubtotals from pivot.options and retry."
        )

    # rowSubtotals on ordinary pivot: silently ignored (single-layer rows subtotal is a no-op).
    # grandTotal: supported on ordinary pivot via post-processing in service.py.
    # (cascade pivot with exactly 2-level rows + limit handles these via cascade_staged_sql path)
    want_grand_total = bool(pivot.options and pivot.options.grand_total)

    if pivot.properties:
        raise NotImplementedError(f"{PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON}properties")

    # --- P1 Cascade detection: must run BEFORE generic axis-field checks and
    #     MemoryCubeProcessor path, so that tree+cascade returns the stable
    #     PIVOT_CASCADE_TREE_REJECTED code rather than the generic hierarchyMode error. ---
    detect_cascade_and_raise(pivot)

    # Validate remaining axis field constraints (expandDepth, standalone tree, etc.)
    for axis_item in list(pivot.rows) + list(pivot.columns):
        if isinstance(axis_item, PivotAxisField):
            if axis_item.hierarchy_mode is not None:
                raise NotImplementedError(f"{PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON}axis hierarchyMode")
            if axis_item.expand_depth is not None:
                raise NotImplementedError(f"{PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON}axis expandDepth")

    # Validate metrics
    native_metrics = []
    parent_share_metrics: list = []
    native_metric_set: set = set()
    for metric_item in pivot.metrics:
        if isinstance(metric_item, str):
            native_metrics.append(metric_item)
            native_metric_set.add(metric_item)
        else:
            if metric_item.type == "parentShare":
                parent_share_metrics.append(metric_item)
                # Ensure the 'of' base metric is included in SQL even if
                # not explicitly listed as a standalone metric.
                if metric_item.of not in native_metric_set:
                    native_metrics.append(metric_item.of)
                    native_metric_set.add(metric_item.of)
            elif metric_item.type == "native":
                if metric_item.name != metric_item.of:
                    raise NotImplementedError(f"{PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON}metric aliasing (name != of)")
                native_metrics.append(metric_item.of)
                native_metric_set.add(metric_item.of)
            else:
                raise NotImplementedError(f"{PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON}metric type '{metric_item.type}'")

    # Calculate group_by
    group_by = [_extract_field_name(r) for r in pivot.rows] + [_extract_field_name(c) for c in pivot.columns]

    # Calculate columns
    columns = group_by + native_metrics

    # Create new request
    translated_request = request.model_copy()
    translated_request.pivot = None
    translated_request.group_by = group_by
    translated_request.columns = columns
    # We do NOT touch slice, system_slice, field_access, denied_columns, start, limit etc.
    # They are preserved.

    return translated_request, want_grand_total, parent_share_metrics
