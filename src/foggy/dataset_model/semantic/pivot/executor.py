"""Pivot Flat Executor.

Provides validation and translation logic for the S2 Flat Pivot MVP.
"""

from typing import Any, Union
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


def validate_and_translate_pivot(request: SemanticQueryRequest) -> SemanticQueryRequest:
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

    # Crossjoin is allowed in S3
    if pivot.options.row_subtotals or pivot.options.column_subtotals or pivot.options.grand_total:
        raise NotImplementedError(f"{PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON}subtotals")
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
    for metric_item in pivot.metrics:
        if isinstance(metric_item, str):
            native_metrics.append(metric_item)
        else:
            if metric_item.type != "native":
                raise NotImplementedError(f"{PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON}metric type '{metric_item.type}'")
            if metric_item.name != metric_item.of:
                raise NotImplementedError(f"{PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON}metric aliasing (name != of)")
            native_metrics.append(metric_item.of)

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

    return translated_request
