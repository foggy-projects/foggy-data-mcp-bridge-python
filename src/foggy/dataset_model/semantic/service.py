"""Semantic Query Service Implementation.

This module provides the main service for executing semantic layer queries,
integrating SqlQueryBuilder with table/query models.
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import time
import re
import logging

from pydantic import BaseModel

from foggy.dataset_model.impl.model import DbTableModelImpl, DbModelDimensionImpl, DbModelMeasureImpl
from foggy.dataset_model.engine.query import SqlQueryBuilder
from foggy.dataset_model.engine.formula import get_default_registry, SqlFormulaRegistry
from foggy.dataset_model.engine.join import JoinGraph, JoinEdge, JoinType
from foggy.dataset_model.definitions.query_request import CalculatedFieldDef
from foggy.mcp.spi import (
    SemanticServiceResolver,
    SemanticMetadataResponse,
    SemanticQueryResponse,
    SemanticMetadataRequest,
    SemanticQueryRequest,
    SemanticRequestContext,
)


logger = logging.getLogger(__name__)


class QueryBuildResult(BaseModel):
    """Result of building a query.

    Contains the built SQL, parameters, and any warnings.
    """

    sql: str
    params: List[Any] = []
    warnings: List[str] = []
    columns: List[Dict[str, Any]] = []


class SemanticQueryService(SemanticServiceResolver):
    """Main service for executing semantic layer queries.

    This service:
    1. Manages a registry of table models (TM) and query models (QM)
    2. Builds SQL queries from semantic requests
    3. Executes queries against the database
    4. Returns structured results

    Example:
        >>> service = SemanticQueryService()
        >>> service.register_model(my_table_model)
        >>> response = service.query_model("sales_qm", request)
    """

    def __init__(
        self,
        default_limit: int = 1000,
        max_limit: int = 10000,
        enable_cache: bool = True,
        cache_ttl_seconds: int = 300,
        executor=None,
    ):
        """Initialize the semantic query service.

        Args:
            default_limit: Default row limit for queries
            max_limit: Maximum allowed row limit
            enable_cache: Enable query result caching
            cache_ttl_seconds: Cache TTL in seconds
            executor: Optional database executor for query execution
        """
        self._models: Dict[str, DbTableModelImpl] = {}
        self._default_limit = default_limit
        self._max_limit = max_limit
        self._enable_cache = enable_cache
        self._cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, Tuple[SemanticQueryResponse, float]] = {}
        self._executor = executor
        self._formula_registry: SqlFormulaRegistry = get_default_registry()

    def register_model(self, model: DbTableModelImpl) -> None:
        """Register a table model with the service."""
        self._models[model.name] = model
        logger.info(f"Registered model: {model.name}")

    def unregister_model(self, name: str) -> bool:
        """Unregister a model by name."""
        if name in self._models:
            del self._models[name]
            self.invalidate_model_cache()
            return True
        return False

    def get_model(self, name: str) -> Optional[DbTableModelImpl]:
        """Get a registered model by name."""
        return self._models.get(name)

    def get_all_model_names(self) -> List[str]:
        """Get all registered model names."""
        return list(self._models.keys())

    def invalidate_model_cache(self) -> None:
        """Invalidate all cached query results."""
        self._cache.clear()
        logger.debug("Cache invalidated")

    # ==================== SemanticServiceResolver Implementation ====================

    def get_metadata(
        self,
        request: SemanticMetadataRequest,
        format: str = "json",
        context: Optional[SemanticRequestContext] = None,
    ) -> SemanticMetadataResponse:
        """Get metadata for available models."""
        models = []

        if request.model:
            model = self.get_model(request.model)
            if model:
                models.append(self._build_model_metadata(model, request))
        else:
            for model_name in self.get_all_model_names():
                model = self.get_model(model_name)
                if model:
                    models.append(self._build_model_metadata(model, request))

        return SemanticMetadataResponse(
            models=models,
            columns=[],
            warnings=[],
        )

    def query_model(
        self,
        model: str,
        request: SemanticQueryRequest,
        mode: str = "execute",
        context: Optional[SemanticRequestContext] = None,
    ) -> SemanticQueryResponse:
        """Execute a query against a model."""
        start_time = time.time()

        table_model = self.get_model(model)
        if not table_model:
            return SemanticQueryResponse(
                error=f"Model not found: {model}",
                warnings=[],
            )

        # Build query
        try:
            build_result = self._build_query(table_model, request)
        except Exception as e:
            logger.exception(f"Failed to build query for model {model}")
            return SemanticQueryResponse(
                error=f"Query build failed: {str(e)}",
                warnings=[],
            )

        # Validate mode
        if mode == "validate":
            return SemanticQueryResponse(
                sql=build_result.sql,
                columns=build_result.columns,
                warnings=build_result.warnings,
                metrics={"validation_time_ms": (time.time() - start_time) * 1000},
            )

        # Check cache
        cache_key = self._get_cache_key(model, request)
        if self._enable_cache and cache_key in self._cache:
            cached_response, cached_time = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                logger.debug(f"Cache hit for {model}")
                return cached_response

        # Execute query
        try:
            response = self._execute_query(build_result, table_model)
        except Exception as e:
            logger.exception(f"Failed to execute query for model {model}")
            return SemanticQueryResponse(
                error=f"Query execution failed: {str(e)}",
                sql=build_result.sql,
                warnings=build_result.warnings,
            )

        # Add metrics
        response.metrics = {
            "query_time_ms": (time.time() - start_time) * 1000,
            "total_time_ms": (time.time() - start_time) * 1000,
            "from_cache": False,
        }
        response.sql = build_result.sql
        response.warnings = build_result.warnings

        # Cache result
        if self._enable_cache:
            self._cache[cache_key] = (response, time.time())

        return response

    # ==================== Query Building ====================

    def _build_query(
        self,
        model: DbTableModelImpl,
        request: SemanticQueryRequest,
    ) -> QueryBuildResult:
        """Build a SQL query with auto-JOIN for dimension fields.

        Supports V3 field names:
          - dim$id, dim$caption, dim$property → auto LEFT JOIN dimension table
          - measureName → aggregated fact table column
          - dimName (simple) → fact table FK column
        """
        from foggy.dataset_model.impl.model import DimensionJoinDef

        warnings: List[str] = []
        columns_info: List[Dict[str, Any]] = []

        builder = SqlQueryBuilder()

        # 1. FROM clause
        table_name = model.source_table
        if model.source_schema:
            table_name = f"{model.source_schema}.{model.source_table}"
        builder.from_table(table_name, alias="t")

        # Build JoinGraph from model's dimension_joins (supports multi-hop in future)
        join_graph = JoinGraph(root="t")
        for dj in model.dimension_joins:
            ta = dj.get_alias()
            join_graph.add_edge(
                from_alias="t", to_alias=ta,
                to_table_name=dj.table_name,
                foreign_key=dj.foreign_key,
                primary_key=dj.primary_key,
                join_type=JoinType.LEFT,
            )

        # Track JOINs to add (deduplicated by dimension name)
        joined_dims: Dict[str, DimensionJoinDef] = {}

        def ensure_join(join_def: DimensionJoinDef):
            """Add LEFT JOIN if not already added."""
            if join_def.name not in joined_dims:
                joined_dims[join_def.name] = join_def
                ta = join_def.get_alias()
                on_cond = f"t.{join_def.foreign_key} = {ta}.{join_def.primary_key}"
                builder.left_join(join_def.table_name, alias=ta, on_condition=on_cond)

        # 2. SELECT columns
        has_aggregation = False
        selected_dims: List[str] = []  # SQL expressions for auto GROUP BY

        if not request.columns:
            # No columns → select visible dimensions + measures
            for dim_name, dim in model.dimensions.items():
                if dim.visible:
                    col_expr = f"t.{dim.column}"
                    label = dim.alias or dim.name
                    builder.select(f"{col_expr} AS `{label}`")
                    columns_info.append({"name": label, "fieldName": dim_name, "expression": col_expr, "aggregation": None})
                    selected_dims.append(col_expr)

            for m_name, measure in model.measures.items():
                if measure.visible:
                    info = self._build_measure_select(measure)
                    builder.select(info["select_expr"])
                    columns_info.append(info)
                    has_aggregation = True
        else:
            for col_name in request.columns:
                # Try inline expression: "sum(salesAmount) as totalSales"
                inline = self._parse_inline_expression(col_name, model, ensure_join)
                if inline:
                    builder.select(inline["select_expr"])
                    columns_info.append(inline)
                    has_aggregation = True
                    continue

                resolved = model.resolve_field(col_name)
                if resolved:
                    # Auto-JOIN if needed
                    if resolved["join_def"]:
                        ensure_join(resolved["join_def"])

                    label = resolved["alias_label"]
                    sql_expr = resolved["sql_expr"]

                    if resolved["is_measure"] and resolved["aggregation"]:
                        agg = resolved["aggregation"]
                        if agg == "COUNT_DISTINCT":
                            sel = f"COUNT(DISTINCT {sql_expr}) AS `{label}`"
                        else:
                            sel = f"{agg}({sql_expr}) AS `{label}`"
                        builder.select(sel)
                        columns_info.append({"name": label, "fieldName": col_name, "expression": sql_expr, "aggregation": agg})
                        has_aggregation = True
                    else:
                        builder.select(f"{sql_expr} AS `{label}`")
                        columns_info.append({"name": label, "fieldName": col_name, "expression": sql_expr, "aggregation": None})
                        selected_dims.append(sql_expr)
                else:
                    # Fallback: try as raw fact table column
                    dim = model.get_dimension(col_name)
                    measure = model.get_measure(col_name)
                    if dim:
                        col_expr = f"t.{dim.column}"
                        label = dim.alias or dim.name
                        builder.select(f"{col_expr} AS `{label}`")
                        columns_info.append({"name": label, "fieldName": col_name, "expression": col_expr, "aggregation": None})
                        selected_dims.append(col_expr)
                    elif measure:
                        info = self._build_measure_select(measure)
                        builder.select(info["select_expr"])
                        columns_info.append(info)
                        has_aggregation = True
                    else:
                        warnings.append(f"Column not found: {col_name}")

        # 2.5 Process calculatedFields (aggregated calculations + window functions)
        for cf_dict in request.calculated_fields:
            cf = CalculatedFieldDef(**cf_dict) if isinstance(cf_dict, dict) else cf_dict
            select_sql = self._build_calculated_field_sql(cf, model, ensure_join)
            alias = cf.alias or cf.name
            builder.select(f"{select_sql} AS `{alias}`")
            columns_info.append({
                "name": alias, "fieldName": cf.name,
                "expression": cf.expression, "aggregation": cf.agg,
                "window": cf.is_window_function(),
            })
            if cf.agg or cf.is_window_function():
                has_aggregation = True

        # 3. WHERE clause
        for filter_item in request.filters:
            self._add_filter(builder, model, filter_item, ensure_join)

        # 4. GROUP BY
        if request.group_by:
            for col_name in request.group_by:
                resolved = model.resolve_field(col_name)
                if resolved:
                    if resolved["join_def"]:
                        ensure_join(resolved["join_def"])
                    builder.group_by(resolved["sql_expr"])
                else:
                    dim = model.get_dimension(col_name)
                    builder.group_by(f"t.{dim.column}" if dim else f"t.{col_name}")
        elif has_aggregation and selected_dims:
            for dim_expr in selected_dims:
                builder.group_by(dim_expr)

        # 5. HAVING
        having_filters = request.parameters.get("having", [])
        for hf in having_filters:
            col, op, val = hf.get("column"), hf.get("operator"), hf.get("value")
            if col and op and val is not None:
                builder.having(f"{col} {op} ?", params=[val])

        # 6. ORDER BY
        for order_item in request.order_by:
            column = order_item.get("column") or order_item.get("field")
            direction = (order_item.get("direction") or order_item.get("dir", "asc")).upper()
            if column:
                resolved = model.resolve_field(column)
                if resolved:
                    if resolved["join_def"]:
                        ensure_join(resolved["join_def"])
                    if resolved["is_measure"]:
                        builder.order_by(f"`{resolved['alias_label']}`", direction)
                    else:
                        builder.order_by(resolved["sql_expr"], direction)
                else:
                    builder.order_by(column, direction)

        # 7. LIMIT/OFFSET
        limit = min(request.limit or self._default_limit, self._max_limit)
        builder.limit(limit)
        if request.offset:
            builder.offset(request.offset)

        sql, params = builder.build()

        return QueryBuildResult(
            sql=sql, params=params, warnings=warnings, columns=columns_info,
        )

    def _build_measure_select(self, measure: DbModelMeasureImpl) -> Dict[str, Any]:
        """Build SELECT expression for a measure."""
        col = measure.column or measure.name
        alias = measure.alias or measure.name
        agg = None

        if measure.aggregation:
            agg_name = measure.aggregation.value.upper()
            if agg_name == "COUNT_DISTINCT":
                select_expr = f"COUNT(DISTINCT t.{col}) AS `{alias}`"
            else:
                select_expr = f"{agg_name}(t.{col}) AS `{alias}`"
            agg = agg_name
        else:
            select_expr = f"t.{col} AS `{alias}`"

        return {
            "name": alias,
            "fieldName": measure.name,
            "expression": f"t.{col}",
            "aggregation": agg,
            "select_expr": select_expr,
        }

    # Regex for inline aggregate: "sum(fieldName) as alias" or "count_distinct(field)"
    _INLINE_AGG_RE = re.compile(
        r'^(sum|avg|count|min|max|count_distinct|countd|group_concat|'
        r'stddev_pop|stddev_samp|var_pop|var_samp)\s*\(\s*([^)]+)\s*\)'
        r'(?:\s+as\s+(\w+))?$',
        re.IGNORECASE,
    )

    def _parse_inline_expression(
        self,
        col_name: str,
        model: DbTableModelImpl,
        ensure_join=None,
    ) -> Optional[Dict[str, Any]]:
        """Parse inline aggregate expression like 'sum(salesAmount) as totalSales'.

        Returns column info dict if parsed, None if not an inline expression.
        """
        m = self._INLINE_AGG_RE.match(col_name.strip())
        if not m:
            return None

        func_name = m.group(1).upper()
        field_name = m.group(2).strip()
        alias = m.group(3)

        # Map function names
        AGG_MAP = {
            "COUNTD": "COUNT_DISTINCT",
            "COUNT_DISTINCT": "COUNT_DISTINCT",
        }
        agg = AGG_MAP.get(func_name, func_name)

        # Resolve the inner field
        resolved = model.resolve_field(field_name)
        if resolved:
            sql_col = resolved["sql_expr"]
            if resolved["join_def"] and ensure_join:
                ensure_join(resolved["join_def"])
            default_alias = alias or f"{func_name.lower()}_{field_name}"
        else:
            # Unknown field — use as raw column on fact table
            sql_col = f"t.{field_name}"
            default_alias = alias or f"{func_name.lower()}_{field_name}"

        if agg == "COUNT_DISTINCT":
            select_expr = f"COUNT(DISTINCT {sql_col}) AS `{default_alias}`"
        else:
            select_expr = f"{agg}({sql_col}) AS `{default_alias}`"

        return {
            "name": default_alias,
            "fieldName": col_name,
            "expression": sql_col,
            "aggregation": agg,
            "select_expr": select_expr,
        }

    # ==================== Calculated Fields & Window Functions ====================

    # SQL keywords and function names that should NOT be treated as field references
    _SQL_KEYWORDS = frozenset({
        'AND', 'OR', 'NOT', 'AS', 'BETWEEN', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
        'NULL', 'TRUE', 'FALSE', 'IS', 'IN', 'LIKE', 'OVER', 'PARTITION', 'BY', 'ORDER',
        'ASC', 'DESC', 'ROWS', 'RANGE', 'CURRENT', 'ROW', 'PRECEDING', 'FOLLOWING',
        'UNBOUNDED', 'SUM', 'AVG', 'COUNT', 'MIN', 'MAX', 'LAG', 'LEAD',
        'FIRST_VALUE', 'LAST_VALUE', 'RANK', 'ROW_NUMBER', 'DENSE_RANK', 'NTILE',
        'COALESCE', 'IFNULL', 'NVL', 'NULLIF', 'IF', 'CAST', 'CONVERT',
        'CONCAT', 'CONCAT_WS', 'SUBSTRING', 'LEFT', 'RIGHT', 'LPAD', 'RPAD',
        'REPLACE', 'LOCATE', 'YEAR', 'MONTH', 'DAY', 'DATE_FORMAT', 'STR_TO_DATE',
        'DATE_ADD', 'DATE_SUB', 'DATEDIFF', 'TIMESTAMPDIFF',
        'ABS', 'ROUND', 'FLOOR', 'CEIL', 'CEILING', 'MOD', 'POWER', 'SQRT',
        'DISTINCT', 'GROUP_CONCAT', 'STDDEV_POP', 'STDDEV_SAMP', 'VAR_POP', 'VAR_SAMP',
        'CUME_DIST', 'PERCENT_RANK',
    })

    # Pure window functions with no arguments (or just ())
    _PURE_WINDOW_RE = re.compile(
        r'^(RANK|ROW_NUMBER|DENSE_RANK|NTILE|CUME_DIST|PERCENT_RANK)\s*\(\s*\)$',
        re.IGNORECASE,
    )

    def _resolve_single_field(self, field_name: str, model: DbTableModelImpl, ensure_join=None) -> str:
        """Resolve a semantic field name to SQL column expression.

        Tries model.resolve_field() first, then dimension/measure lookup, then returns as-is.
        """
        resolved = model.resolve_field(field_name)
        if resolved:
            if resolved["join_def"] and ensure_join:
                ensure_join(resolved["join_def"])
            return resolved["sql_expr"]
        dim = model.get_dimension(field_name)
        if dim:
            return f"t.{dim.column}"
        measure = model.get_measure(field_name)
        if measure:
            return f"t.{measure.column or measure.name}"
        return field_name

    def _resolve_expression_fields(self, expression: str, model: DbTableModelImpl, ensure_join=None) -> str:
        """Replace semantic field names in an expression with SQL column references.

        Handles:
        - Pure window functions: RANK(), ROW_NUMBER() → returned as-is
        - Function calls: LAG(salesAmount, 1) → LAG(t.sales_amount, 1)
        - Arithmetic: salesAmount - discountAmount → t.sales_amount - t.discount_amount
        - Dimension refs: product$categoryName → dp.category_name (with auto-JOIN)
        """
        stripped = expression.strip()

        # Pure window functions (no arguments): return as-is
        if self._PURE_WINDOW_RE.match(stripped):
            return stripped

        keywords = self._SQL_KEYWORDS

        def replace_field(match: re.Match) -> str:
            token = match.group(0)
            if token.upper() in keywords:
                return token
            # Try numeric literal (don't resolve)
            if token.isdigit():
                return token
            resolved = model.resolve_field(token)
            if resolved:
                if resolved["join_def"] and ensure_join:
                    ensure_join(resolved["join_def"])
                return resolved["sql_expr"]
            dim = model.get_dimension(token)
            if dim:
                return f"t.{dim.column}"
            measure = model.get_measure(token)
            if measure:
                return f"t.{measure.column or measure.name}"
            return token

        return re.sub(r'\b(\w+\$\w+|\w+)\b', replace_field, expression)

    def _build_calculated_field_sql(
        self,
        cf: CalculatedFieldDef,
        model: DbTableModelImpl,
        ensure_join=None,
    ) -> str:
        """Build SQL expression for a calculated field, including OVER() for window functions.

        Flow:
        1. Resolve semantic field names in expression → SQL column names
        2. If agg specified (non-window): wrap as AGG(expr)
        3. If window function: wrap as expr OVER (PARTITION BY ... ORDER BY ... frame)
        """
        base_sql = self._resolve_expression_fields(cf.expression, model, ensure_join)

        if cf.is_window_function():
            # Window function: optionally wrap with agg, then add OVER()
            if cf.agg:
                agg_upper = cf.agg.upper()
                if agg_upper == "COUNT_DISTINCT":
                    base_sql = f"COUNT(DISTINCT {base_sql})"
                else:
                    base_sql = f"{agg_upper}({base_sql})"

            over_parts: List[str] = []
            if cf.partition_by:
                resolved_parts = [
                    self._resolve_single_field(f, model, ensure_join) for f in cf.partition_by
                ]
                over_parts.append(f"PARTITION BY {', '.join(resolved_parts)}")
            if cf.window_order_by:
                order_clauses = []
                for wo in cf.window_order_by:
                    col_sql = self._resolve_single_field(wo["field"], model, ensure_join)
                    direction = wo.get("dir", "asc").upper()
                    order_clauses.append(f"{col_sql} {direction}")
                over_parts.append(f"ORDER BY {', '.join(order_clauses)}")
            if cf.window_frame:
                over_parts.append(cf.window_frame)

            base_sql = f"{base_sql} OVER ({' '.join(over_parts)})"
        elif cf.agg:
            # Non-window aggregation
            agg_upper = cf.agg.upper()
            if agg_upper == "COUNT_DISTINCT":
                base_sql = f"COUNT(DISTINCT {base_sql})"
            else:
                base_sql = f"{agg_upper}({base_sql})"

        return base_sql

    # ==================== Filtering ====================

    def _add_filter(
        self,
        builder: SqlQueryBuilder,
        model: DbTableModelImpl,
        filter_item: Dict[str, Any],
        ensure_join=None,
    ) -> None:
        """Add a single filter condition with auto-JOIN support."""
        column = filter_item.get("column") or filter_item.get("field")
        operator = filter_item.get("operator") or filter_item.get("op", "=")
        value = filter_item.get("value")

        if not column:
            # Check for shorthand: {"fieldName": value}
            for k, v in filter_item.items():
                if k not in ("column", "operator", "value", "op", "field", "values", "pattern", "from", "to"):
                    resolved = model.resolve_field(k)
                    if resolved:
                        if resolved["join_def"] and ensure_join:
                            ensure_join(resolved["join_def"])
                        builder.where(f"{resolved['sql_expr']} = ?", params=[v])
                    return
            return

        # Resolve column through model field resolver
        resolved = model.resolve_field(column)
        if resolved:
            col_expr = resolved["sql_expr"]
            if resolved["join_def"] and ensure_join:
                ensure_join(resolved["join_def"])
        else:
            # Fallback to fact table
            dim = model.get_dimension(column)
            col_expr = f"t.{dim.column}" if dim else f"t.{column}"

        # Resolve value: support "values" key for IN, or range from filter_item
        effective_value = value
        if operator.upper() in ("IN", "NOT IN", "NIN"):
            effective_value = filter_item.get("values", [value] if value else [])
        elif operator.upper() == "BETWEEN":
            from_val = filter_item.get("from")
            to_val = filter_item.get("to")
            if from_val is not None and to_val is not None:
                effective_value = [from_val, to_val]

        # Use SqlFormulaRegistry for all operators
        params: List[Any] = []
        condition = self._formula_registry.build_condition(
            col_expr, operator, effective_value, params
        )
        if condition:
            builder.where(condition, params=params if params else None)

    # ==================== Query Execution ====================

    def _execute_query(
        self,
        build_result: QueryBuildResult,
        model: DbTableModelImpl,
    ) -> SemanticQueryResponse:
        """Execute the built query (synchronous wrapper).

        When called from an async context (e.g., FastAPI), prefer
        using query_model_async() instead.
        """
        import asyncio

        if self._executor is None:
            logger.warning("No database executor configured - returning empty result")
            return SemanticQueryResponse(
                data=[],
                columns=build_result.columns,
                total=0,
            )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, self._execute_query_async(build_result))
                return future.result(timeout=60)
        else:
            return asyncio.run(self._execute_query_async(build_result))

    async def _execute_query_async(
        self,
        build_result: QueryBuildResult,
    ) -> SemanticQueryResponse:
        """Execute the built query asynchronously."""
        if self._executor is None:
            return SemanticQueryResponse(
                data=[],
                columns=build_result.columns,
                total=0,
                error="No database executor configured",
            )

        result = await self._executor.execute(
            build_result.sql,
            build_result.params,
        )

        if result.error:
            return SemanticQueryResponse(
                error=result.error,
                sql=build_result.sql,
                columns=build_result.columns,
            )

        return SemanticQueryResponse(
            data=result.rows,
            columns=build_result.columns,
            total=result.total,
        )

    def set_executor(self, executor) -> None:
        """Set the database executor."""
        self._executor = executor
        logger.info(f"Database executor set: {type(executor).__name__}")

    # ==================== Async Query ====================

    async def query_model_async(
        self,
        model: str,
        request: SemanticQueryRequest,
        mode: str = "execute",
        context: Optional[SemanticRequestContext] = None,
    ) -> SemanticQueryResponse:
        """Async version of query_model — safe to call from FastAPI handlers."""
        start_time = time.time()

        table_model = self.get_model(model)
        if not table_model:
            return SemanticQueryResponse(error=f"Model not found: {model}", warnings=[])

        try:
            build_result = self._build_query(table_model, request)
        except Exception as e:
            logger.exception(f"Failed to build query for model {model}")
            return SemanticQueryResponse(error=f"Query build failed: {str(e)}", warnings=[])

        if mode == "validate":
            return SemanticQueryResponse(
                sql=build_result.sql,
                columns=build_result.columns,
                warnings=build_result.warnings,
                metrics={"validation_time_ms": (time.time() - start_time) * 1000},
            )

        cache_key = self._get_cache_key(model, request)
        if self._enable_cache and cache_key in self._cache:
            cached_response, cached_time = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_response

        try:
            response = await self._execute_query_async(build_result)
        except Exception as e:
            logger.exception(f"Failed to execute query for model {model}")
            return SemanticQueryResponse(
                error=f"Query execution failed: {str(e)}",
                sql=build_result.sql,
                warnings=build_result.warnings,
            )

        response.metrics = {
            "query_time_ms": (time.time() - start_time) * 1000,
            "from_cache": False,
        }
        response.sql = build_result.sql
        response.warnings = build_result.warnings

        if self._enable_cache:
            self._cache[cache_key] = (response, time.time())

        return response

    # ==================== Metadata Building ====================

    def _build_model_metadata(
        self,
        model: DbTableModelImpl,
        request: SemanticMetadataRequest,
    ) -> Dict[str, Any]:
        """Build metadata dict for a model."""
        metadata: Dict[str, Any] = {
            "name": model.name,
            "alias": model.alias,
            "description": model.description,
            "sourceTable": model.source_table,
            "sourceSchema": model.source_schema,
            "enabled": model.enabled,
            "valid": model.valid,
        }

        if request.include_dimensions:
            metadata["dimensions"] = [
                {
                    "name": dim.name,
                    "alias": dim.alias,
                    "column": dim.column,
                    "type": dim.data_type.value,
                    "visible": dim.visible,
                    "filterable": dim.filterable,
                    "sortable": dim.sortable,
                }
                for dim in model.dimensions.values()
            ]

        if request.include_measures:
            metadata["measures"] = [
                {
                    "name": m.name,
                    "alias": m.alias,
                    "column": m.column,
                    "aggregation": m.aggregation.value if m.aggregation else None,
                    "expression": m.expression,
                    "visible": m.visible,
                }
                for m in model.measures.values()
            ]

        if request.include_columns:
            metadata["columns"] = [
                {
                    "name": col.name,
                    "type": col.type.value if hasattr(col, "type") and col.type else "string",
                    "nullable": col.nullable if hasattr(col, "nullable") else True,
                }
                for col in model.columns.values()
            ]

        return metadata

    def get_metadata_v3(self, model_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """Build V3 metadata package — aligned with Java SemanticServiceV3Impl.

        Returns a combined metadata package with all models and their fields
        in the format expected by AI assistants (same as Java get_metadata).

        Structure:
            {
                "prompt": "usage instructions...",
                "version": "v3",
                "fields": { fieldName -> fieldInfo },
                "models": { modelName -> modelInfo }
            }
        """
        target_models = model_names or list(self._models.keys())

        fields: Dict[str, Any] = {}
        models_info: Dict[str, Any] = {}

        for model_name in target_models:
            model = self._models.get(model_name)
            if not model:
                continue

            # Model info
            models_info[model_name] = {
                "name": model.alias or model.name,
                "factTable": model.source_table,
                "purpose": model.description or "数据查询和分析",
                "scenarios": ["数据查询", "统计分析", "报表生成"],
            }
            ai_desc = getattr(model, 'ai_description', None)
            if ai_desc:
                models_info[model_name]["aiDescription"] = ai_desc

            # Dimension JOIN fields → expand to $id, $caption, and $properties
            for join_def in model.dimension_joins:
                dim_name = join_def.name
                dim_caption = join_def.caption or dim_name

                # dim$id
                id_fn = f"{dim_name}$id"
                if id_fn not in fields:
                    fields[id_fn] = {
                        "name": f"{dim_caption}(ID)",
                        "fieldName": id_fn,
                        "meta": f"维度ID | {join_def.primary_key}",
                        "type": "INTEGER",
                        "filterType": "dimension",
                        "filterable": True,
                        "measure": False,
                        "aggregatable": False,
                        "sourceColumn": join_def.foreign_key,
                        "models": {},
                    }
                fields[id_fn]["models"][model_name] = {
                    "description": f"{dim_caption}(ID)",
                    "usage": "用于精确查询、排序",
                }

                # dim$caption
                cap_fn = f"{dim_name}$caption"
                if cap_fn not in fields:
                    fields[cap_fn] = {
                        "name": f"{dim_caption}(名称)",
                        "fieldName": cap_fn,
                        "meta": "维度名称 | TEXT",
                        "type": "TEXT",
                        "filterType": "dimension",
                        "filterable": True,
                        "measure": False,
                        "aggregatable": False,
                        "models": {},
                    }
                fields[cap_fn]["models"][model_name] = {
                    "description": f"{dim_caption}显示名称",
                    "usage": "用于展示、模糊查询",
                }

                # dim$property fields
                for prop in join_def.properties:
                    prop_name = prop.get_name()
                    prop_fn = f"{dim_name}${prop_name}"
                    if prop_fn not in fields:
                        fields[prop_fn] = {
                            "name": prop.caption or prop_name,
                            "fieldName": prop_fn,
                            "meta": f"维度属性 | {prop.data_type}",
                            "type": prop.data_type.upper(),
                            "filterType": "text",
                            "filterable": True,
                            "measure": False,
                            "aggregatable": False,
                            "models": {},
                        }
                    fields[prop_fn]["models"][model_name] = {
                        "description": prop.description or prop.caption or prop_name,
                    }

            # Fact table own dimensions → expand to $id and $caption
            for dim_name, dim in model.dimensions.items():
                id_fn = f"{dim_name}$id"
                if id_fn not in fields:
                    fields[id_fn] = {
                        "name": f"{dim.alias or dim_name}(ID)",
                        "fieldName": id_fn,
                        "meta": f"属性 | {dim.data_type.value}",
                        "type": dim.data_type.value.upper(),
                        "filterType": "text",
                        "filterable": dim.filterable,
                        "measure": False,
                        "aggregatable": False,
                        "sourceColumn": dim.column,
                        "models": {},
                    }
                fields[id_fn]["models"][model_name] = {
                    "description": dim.description or dim.alias or dim_name,
                }

            # Measure fields
            for measure_name, measure in model.measures.items():
                if measure_name not in fields:
                    agg_name = measure.aggregation.value.upper() if measure.aggregation else "SUM"
                    fields[measure_name] = {
                        "name": measure.alias or measure_name,
                        "fieldName": measure_name,
                        "meta": f"度量 | 数值 | 默认聚合:{agg_name}",
                        "type": "NUMBER",
                        "filterType": "number",
                        "filterable": True,
                        "measure": True,
                        "aggregatable": True,
                        "aggregation": agg_name,
                        "sourceColumn": measure.column,
                        "models": {},
                    }
                fields[measure_name]["models"][model_name] = {
                    "description": f"{measure.alias or measure_name} (聚合方式: {agg_name})",
                }

        return {
            "prompt": (
                "## 使用说明 (V3版本)\n"
                "- 字段名直接使用 fields 中的 fieldName\n"
                "- 维度用 xxx$id(查询/过滤) 或 xxx$caption(展示)\n"
                "- 度量默认带聚合，可用内联表达式如 sum(fieldName)\n"
            ),
            "version": "v3",
            "fields": fields,
            "models": models_info,
        }

    def get_metadata_v3_markdown(self, model_names: Optional[List[str]] = None) -> str:
        """Build V3 metadata as markdown — aligned with Java default format.

        Java's LocalDatasetAccessor hardcodes format="markdown" for get_metadata.
        Markdown is preferred because:
        - ~40-60% fewer tokens than JSON
        - Tables are natural for LLMs to scan
        - Better structure comprehension

        Single model → detailed format with field tables
        Multiple models → compact index format
        """
        target_names = model_names or list(self._models.keys())
        target_models = [(n, self._models[n]) for n in target_names if n in self._models]

        if not target_models:
            return "# 暂无可用数据模型\n"

        if len(target_models) == 1:
            return self._build_single_model_markdown(target_models[0][0], target_models[0][1])
        else:
            return self._build_multi_model_markdown(target_models)

    def _build_single_model_markdown(self, model_name: str, model: 'DbTableModelImpl') -> str:
        """Build detailed markdown for a single model (aligned with Java buildSingleModelMarkdown)."""
        lines: List[str] = []
        alias = model.alias or model_name

        lines.append(f"# {model_name} - {alias}")
        lines.append("")
        lines.append("## 模型信息")
        lines.append(f"- 表名: {model.source_table}")
        if model.description:
            lines.append(f"- 说明: {model.description}")
        lines.append("")

        # Dimension JOIN fields
        if model.dimension_joins:
            lines.append("## 维度字段")
            lines.append("| 字段名 | 名称 | 类型 | 说明 |")
            lines.append("|--------|------|------|------|")
            for jd in model.dimension_joins:
                dc = jd.caption or jd.name
                lines.append(f"| {jd.name}$id | {dc}(ID) | INTEGER | {jd.key_description or jd.description or ''} |")
                lines.append(f"| {jd.name}$caption | {dc}(名称) | TEXT | {dc}显示名称 |")
                for prop in jd.properties:
                    pn = prop.get_name()
                    lines.append(f"| {jd.name}${pn} | {prop.caption or pn} | {prop.data_type} | {prop.description or ''} |")
            lines.append("")

        # Fact table own attributes
        if model.dimensions:
            lines.append("## 属性字段")
            lines.append("| 字段名 | 名称 | 类型 | 说明 |")
            lines.append("|--------|------|------|------|")
            for dim_name, dim in model.dimensions.items():
                lines.append(f"| {dim_name} | {dim.alias or dim_name} | {dim.data_type.value.upper()} | {dim.description or ''} |")
            lines.append("")

        # Measure fields
        if model.measures:
            lines.append("## 度量字段")
            lines.append("| 字段名 | 名称 | 类型 | 聚合 | 说明 |")
            lines.append("|--------|------|------|------|------|")
            for m_name, measure in model.measures.items():
                m_alias = measure.alias or m_name
                agg = measure.aggregation.value.upper() if measure.aggregation else "-"
                m_desc = measure.description or ""
                lines.append(f"| {m_name} | {m_alias} | NUMBER | {agg} | {m_desc} |")
            lines.append("")

        lines.append("## 使用提示")
        lines.append("- 维度用 `xxx$id`(查询/过滤), `xxx$caption`(展示), `xxx$property`(维度属性)")
        lines.append("- 度量支持内联聚合: `sum(salesAmount) as total`")
        lines.append("- 系统自动处理 groupBy，通常无需手动指定")

        return "\n".join(lines)

    def _build_multi_model_markdown(self, models: List[tuple]) -> str:
        """Build compact index markdown for multiple models (aligned with Java buildMultiModelMarkdown)."""
        lines: List[str] = []

        lines.append("# 数据模型语义索引 V3")
        lines.append("")

        # Model index
        lines.append("## 模型索引")
        for model_name, model in models:
            alias = model.alias or model_name
            desc = model.description or ""
            lines.append(f"- **{alias}**({model_name}): {desc}")
        lines.append("")

        # Field index
        lines.append("## 字段索引")
        lines.append("")
        lines.append("> 查询时使用缩进行中的「字段名」，而非标题中的业务名。")
        lines.append("")

        for model_name, model in models:
            alias = model.alias or model_name
            lines.append(f"### {alias}")
            lines.append("")

            # Dimension JOINs
            if model.dimension_joins:
                lines.append("**维度**")
                for jd in model.dimension_joins:
                    dc = jd.caption or jd.name
                    lines.append(f"- {dc}")
                    lines.append(f"    - [field:{jd.name}$id] | ID, 用于查询/过滤")
                    lines.append(f"    - [field:{jd.name}$caption] | 名称, 用于展示")
                    for prop in jd.properties:
                        pn = prop.get_name()
                        lines.append(f"    - [field:{jd.name}${pn}] | {prop.caption or pn}")

            # Fact table attributes
            if model.dimensions:
                lines.append("")
                lines.append("**属性**")
                for dim_name, dim in model.dimensions.items():
                    lines.append(f"- {dim.alias or dim_name}")
                    lines.append(f"    - [field:{dim_name}] | {dim.data_type.value.upper()}")

            # Measures
            if model.measures:
                lines.append("")
                lines.append("**度量**")
                for m_name, measure in model.measures.items():
                    m_alias = measure.alias or m_name
                    agg = measure.aggregation.value.upper() if measure.aggregation else "SUM"
                    lines.append(f"- {m_alias}")
                    lines.append(f"    - [field:{m_name}] | {agg}")

            lines.append("")

        # Usage
        lines.append("## 使用提示")
        lines.append("- 维度用 `xxx$id`(查询/过滤), `xxx$caption`(展示)")
        lines.append("- 度量支持内联聚合: `sum(fieldName) as alias`")
        lines.append("- 系统自动处理 groupBy，通常无需手动指定")

        return "\n".join(lines)

    # ==================== Caching ====================

    def _get_cache_key(self, model: str, request: SemanticQueryRequest) -> str:
        """Generate cache key for a query."""
        import hashlib
        import json

        key_data = {
            "model": model,
            "columns": sorted(request.columns),
            "filters": request.filters,
            "group_by": sorted(request.group_by),
            "order_by": request.order_by,
            "limit": request.limit,
            "offset": request.offset,
        }

        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()


__all__ = [
    "SemanticQueryService",
    "QueryBuildResult",
]
