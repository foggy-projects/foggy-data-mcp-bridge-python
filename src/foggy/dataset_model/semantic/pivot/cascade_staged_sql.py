"""Pivot Cascade Staged SQL Planner.

Executes C2 rows exactly two-level cascade via staged CTEs.
Does not permit memory fallback.
"""

from typing import Any, List

from foggy.mcp_spi.semantic import (
    SemanticQueryRequest,
    SemanticQueryResponse,
    PivotRequest,
    PivotAxisField,
)
from foggy.dataset_model.semantic.pivot.cascade_detector import (
    PIVOT_CASCADE_SQL_REQUIRED,
    PIVOT_CASCADE_NON_ADDITIVE_REJECTED,
)
from foggy.dataset_model.semantic.pivot.domain_transport import resolve_renderer


def _get_field_name(item: Any) -> str:
    if isinstance(item, str):
        return item
    return item.field


def execute_cascade_staged_sql(
    service: Any,
    model_name: str,
    request: SemanticQueryRequest,
    context: Any = None,
) -> SemanticQueryResponse:
    """Execute a 2-level rows cascade via staged CTEs."""
    pivot: PivotRequest = request.pivot

    # C2 whitelist: Additive metrics only.
    # Non-additive metrics check. For now, since we only support SUM/COUNT which we translate directly,
    # wait, the prompt says "non-additive metric participation when detectable from request metadata must be rejected".
    # In python, we can look at the table_model to see if the metric is non-additive.
    table_model = service.get_model(model_name)
    if not table_model:
        return SemanticQueryResponse.from_error(f"Model not found: {model_name}")

    # Find the constrained fields (parent and child)
    rows = list(pivot.rows)
    constrained_fields = []
    for item in rows:
        if isinstance(item, PivotAxisField) and (item.limit is not None and item.limit > 0):
            constrained_fields.append(item)
            
    if len(constrained_fields) != 2:
        return SemanticQueryResponse.from_error("Expected exactly two constrained row fields.")
        
    parent_field: PivotAxisField = constrained_fields[0]
    child_field: PivotAxisField = constrained_fields[1]
    
    # We will build the Staged SQL. First check if dialect is supported.
    dialect = service._dialect
    try:
        resolve_renderer(dialect)
    except NotImplementedError:
        return SemanticQueryResponse.from_error(
            f"{PIVOT_CASCADE_SQL_REQUIRED}: Dialect {dialect.name()} is not supported for Cascade Staged SQL."
        )

    # Build base request
    base_request = request.model_copy()
    base_request.pivot = None
    
    # We group by all row and column fields for the base query
    all_axis_fields = [_get_field_name(r) for r in pivot.rows] + [_get_field_name(c) for c in pivot.columns]
    
    # Collect all native metrics
    native_metrics = []
    for m in pivot.metrics:
        if isinstance(m, str):
            metric_name = m
        else:
            if m.type != "native":
                return SemanticQueryResponse.from_error(
                    f"{PIVOT_CASCADE_NON_ADDITIVE_REJECTED}: Non-additive derived metric {m.name} is not supported in cascade."
                )
            metric_name = m.of
            
        # Check table_model for aggregation type
        measure = table_model.get_measure(metric_name)
        if measure:
            agg = getattr(measure, "aggregation", None)
            agg_val = getattr(agg, "value", None) if agg else None
            # Only sum and count are considered additive for safe rollup from [parent, child] grain
            if agg_val not in ("sum", "count"):
                return SemanticQueryResponse.from_error(
                    f"{PIVOT_CASCADE_NON_ADDITIVE_REJECTED}: Non-additive metric {metric_name} with aggregation {agg_val} is not supported in cascade."
                )
                
        native_metrics.append(metric_name)
            
    base_request.group_by = all_axis_fields
    base_request.columns = all_axis_fields + native_metrics
    # Remove any specific order_by/limit for the base query to get the full relevant domain
    base_request.order_by = []
    base_request.limit = service._max_limit
    base_request.start = 0
    
    # Get the base SQL from queryModel
    base_resp = service.query_model(model_name, base_request, mode="validate", context=context)
    if base_resp.error:
        return base_resp
        
    base_sql = base_resp.sql
    params = list(base_resp.params) if base_resp.params else []
    
    # Identify aliases for the fields from schema_info
    alias_map = {}
    if base_resp.schema_info and base_resp.schema_info.columns:
        for i, col_name in enumerate(base_request.columns):
            if i < len(base_resp.schema_info.columns):
                alias_map[col_name] = base_resp.schema_info.columns[i].name
            else:
                alias_map[col_name] = col_name
    else:
        for col_name in base_request.columns:
            alias_map[col_name] = col_name

    def _quote(f: str) -> str:
        # Simple dialect quoting wrapper
        if dialect.name in ("mysql", "mysql8"):
            return f"`{f}`"
        return f'"{f}"'
        
    def _get_sql_alias(f_name: str) -> str:
        return alias_map.get(f_name, f_name)
        
    p_name = _get_field_name(parent_field)
    c_name = _get_field_name(child_field)
    
    p_alias = _get_sql_alias(p_name)
    c_alias = _get_sql_alias(c_name)
    m_aliases = [_get_sql_alias(m) for m in native_metrics]
    
    # Helper to generate ORDER BY clause for a limit
    def _build_order_by(field: PivotAxisField) -> str:
        orders = []
        for ob in (field.order_by or []):
            desc = ob.startswith("-")
            metric = ob[1:] if desc else ob
            metric_alias = _get_sql_alias(metric)
            metric_q = _quote(metric_alias)
            # 1. NULL bucket tie-breaker
            null_bucket = f"CASE WHEN {metric_q} IS NULL THEN 1 ELSE 0 END"
            orders.append(null_bucket)
            # 2. Metric ordering
            dir_str = "DESC" if desc else "ASC"
            orders.append(f"{metric_q} {dir_str}")
        
        # 3. Prefix key tie-breaker (parent, then child if applicable)
        orders.append(f"{_quote(p_alias)} ASC")
        if field == child_field:
            orders.append(f"{_quote(c_alias)} ASC")
            
        return "ORDER BY " + ", ".join(orders)

    # Helper to generate HAVING clause
    def _build_having(field: PivotAxisField) -> str:
        if not field.having:
            return ""
        metric_alias = _get_sql_alias(field.having.metric)
        metric_q = _quote(metric_alias)
        op = field.having.op
        val = field.having.value
        params.append(val)
        return f"HAVING {metric_q} {op} ?"

    def _null_safe_eq(left: str, right: str) -> str:
        if dialect.name in ("mysql", "mysql8"):
            return f"{left} <=> {right}"
        elif dialect.name in ("postgres", "postgresql"):
            return f"{left} IS NOT DISTINCT FROM {right}"
        else:
            return f"{left} IS {right}"

    p_having = _build_having(parent_field)
    p_order = _build_order_by(parent_field)
    p_limit = parent_field.limit
    
    c_having = _build_having(child_field)
    c_order = _build_order_by(child_field)
    c_limit = child_field.limit

    metric_sums = ", ".join(f"SUM({_quote(m)}) AS {_quote(m)}" for m in m_aliases)
    if not metric_sums:
        metric_sums = "1" # dummy

    # Wrap the base query in staged CTEs
    staged_sql = f"""WITH _base_query AS (
    {base_sql}
),
_parent_agg AS (
    SELECT {_quote(p_alias)}, {metric_sums}
    FROM _base_query
    GROUP BY {_quote(p_alias)}
    {p_having}
),
_parent_rank AS (
    SELECT *, ROW_NUMBER() OVER ({p_order}) AS _rn
    FROM _parent_agg
),
_parent_domain AS (
    SELECT {_quote(p_alias)}
    FROM _parent_rank
    WHERE _rn <= {p_limit}
),
_child_agg AS (
    SELECT b.{_quote(p_alias)}, b.{_quote(c_alias)}, {", ".join(f"SUM(b.{_quote(m)}) AS {_quote(m)}" for m in m_aliases)}
    FROM _base_query b
    INNER JOIN _parent_domain p ON {_null_safe_eq(f'b.{_quote(p_alias)}', f'p.{_quote(p_alias)}')}
    GROUP BY b.{_quote(p_alias)}, b.{_quote(c_alias)}
    {c_having}
),
_child_rank AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY b.{_quote(p_alias)} {c_order}) AS _rn
    FROM _child_agg b
),
_child_domain AS (
    SELECT {_quote(p_alias)}, {_quote(c_alias)}
    FROM _child_rank
    WHERE _rn <= {c_limit}
)
SELECT b.*
FROM _base_query b
INNER JOIN _child_domain c ON {_null_safe_eq(f'b.{_quote(p_alias)}', f'c.{_quote(p_alias)}')} AND {_null_safe_eq(f'b.{_quote(c_alias)}', f'c.{_quote(c_alias)}')}
"""
    
    # Execute the final query
    try:
        executor = service._resolve_executor(table_model)
        exec_res = service._run_async_in_sync(executor.execute(staged_sql, params=params))
        if getattr(exec_res, "error", None):
            return SemanticQueryResponse.from_error(f"Cascade execution failed: {exec_res.error}\nSQL:\n{staged_sql}")
        items = getattr(exec_res, "rows", [])
    except Exception as e:
        return SemanticQueryResponse.from_error(f"Cascade execution failed: {str(e)}")

    # Construct the final SemanticQueryResponse
    schema_info = base_resp.schema_info  # inherit schema from base query
    
    from foggy.dataset_model.semantic.pivot.memory_cube import MemoryCubeProcessor
    from foggy.dataset_model.semantic.pivot.grid_shaper import GridShaper
    
    # Clone pivot request to clear limits and havings without mutating the original request
    cloned_pivot = pivot.model_copy(deep=True)
    for item in cloned_pivot.rows:
        if isinstance(item, PivotAxisField):
            item.limit = None
            item.having = None
            
    key_map = alias_map

    try:
        processor = MemoryCubeProcessor(items, cloned_pivot, key_map)
        processed_items = processor.process()
        
        if getattr(cloned_pivot, "output_format", "flat") == "grid":
            shaper = GridShaper(processed_items, cloned_pivot, key_map)
            result = [shaper.shape()]
        else:
            # Reverse map for flat format
            key_reverse_map = {v: k for k, v in key_map.items()}
            result = []
            for item in processed_items:
                mapped_item = {}
                for k, v in item.items():
                    mapped_item[key_reverse_map.get(k, k)] = v
                result.append(mapped_item)
                
    except Exception as e:
        return SemanticQueryResponse.from_error(f"Post-processing cascade failed: {str(e)}")

    return SemanticQueryResponse(
        items=result,
        schema_info=base_resp.schema_info,
    )
