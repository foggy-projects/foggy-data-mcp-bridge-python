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

from foggy.dataset_model.impl.model import (
    DbTableModelImpl,
    DbModelDimensionImpl,
    DbModelMeasureImpl,
)
from foggy.dataset_model.engine.query import SqlQueryBuilder
from foggy.dataset_model.engine.formula import get_default_registry, SqlFormulaRegistry
from foggy.dataset_model.engine.hierarchy import (
    ClosureTableDef,
    HierarchyConditionBuilder,
    get_default_hierarchy_registry,
)
from foggy.dataset_model.engine.join import JoinGraph, JoinEdge, JoinType
from foggy.dataset_model.definitions.query_request import CalculatedFieldDef
from foggy.mcp_spi import (
    SemanticServiceResolver,
    SemanticMetadataResponse,
    SemanticQueryResponse,
    SemanticMetadataRequest,
    SemanticQueryRequest,
    SemanticRequestContext,
    DebugInfo,
    QueryMode,
)
from foggy.mcp_spi.semantic import DeniedColumn, FieldAccessDef
from foggy.dataset_model.semantic.field_validator import (
    validate_field_access,
    filter_response_columns,
    validate_query_fields,
)
from foggy.dataset_model.semantic.masking import apply_masking
from foggy.dataset_model.semantic.physical_column_mapping import (
    PhysicalColumnMapping,
    build_physical_column_mapping,
)
from foggy.dataset_model.semantic.error_sanitizer import sanitize_engine_error
from foggy.dataset_model.semantic.inline_expression import (
    find_matching_paren,
    parse_inline_aggregate,
    skip_string_literal,
    split_top_level_commas,
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
        dialect=None,
    ):
        """Initialize the semantic query service.

        Args:
            default_limit: Default row limit for queries
            max_limit: Maximum allowed row limit
            enable_cache: Enable query result caching
            cache_ttl_seconds: Cache TTL in seconds
            executor: Optional database executor for query execution
            dialect: Optional database dialect for identifier quoting.
                     If None, uses ANSI double-quote (compatible with
                     PostgreSQL, SQLite, and most databases).
        """
        self._models: Dict[str, DbTableModelImpl] = {}
        self._default_limit = default_limit
        self._max_limit = max_limit
        self._enable_cache = enable_cache
        self._cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, Tuple[SemanticQueryResponse, float]] = {}
        self._executor = executor
        self._executor_manager = None  # Optional[ExecutorManager] for multi-datasource routing
        self._dialect = dialect
        self._formula_registry: SqlFormulaRegistry = get_default_registry()
        self._hierarchy_registry = get_default_hierarchy_registry()
        # v1.3: physical column mapping cache (model_name → PhysicalColumnMapping)
        self._mapping_cache: Dict[str, PhysicalColumnMapping] = {}

    def _qi(self, identifier: str) -> str:
        """Quote an SQL identifier using the configured dialect.

        Falls back to ANSI double-quote if no dialect is set.
        """
        if self._dialect and hasattr(self._dialect, 'quote_identifier'):
            return self._dialect.quote_identifier(identifier)
        # ANSI SQL standard: double-quote for identifiers
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'

    def get_physical_column_mapping(self, model_name: str) -> Optional[PhysicalColumnMapping]:
        """Get or lazily build the physical column mapping for a model.

        The mapping is cached per model name and invalidated when models
        are registered/unregistered.
        """
        if model_name in self._mapping_cache:
            return self._mapping_cache[model_name]
        model = self.get_model(model_name)
        if model is None:
            return None
        mapping = build_physical_column_mapping(model)
        self._mapping_cache[model_name] = mapping
        return mapping

    def register_model(self, model: DbTableModelImpl, namespace: Optional[str] = None) -> None:
        """Register a table model with the service.

        If model.name already contains a namespace prefix (``ns:Name``),
        it is registered as-is. Otherwise, if ``namespace`` is provided,
        the model is registered under ``namespace:model.name``.

        The model is also accessible by its bare name (without namespace
        prefix) as a fallback, unless another model with the same bare
        name is already registered.

        Aligned with Java's ``namespace:modelName`` composite key pattern.
        """
        key = model.name
        if namespace and ":" not in key:
            key = f"{namespace}:{key}"
            model.name = key

        self._models[key] = model
        # Invalidate mapping cache for this model
        self._mapping_cache.pop(key, None)

        # Also register bare name as fallback (don't overwrite existing)
        bare_name = key.split(":", 1)[1] if ":" in key else key
        if bare_name != key and bare_name not in self._models:
            self._models[bare_name] = model
            self._mapping_cache.pop(bare_name, None)

        logger.info(f"Registered model: {key}")

    def unregister_model(self, name: str) -> bool:
        """Unregister a model by name."""
        if name in self._models:
            del self._models[name]
            self.invalidate_model_cache()
            return True
        return False

    def unregister_by_namespace(self, namespace: str) -> int:
        """Unregister all models belonging to a namespace.

        Aligned with Java ``TableModelLoaderManager.clearByNamespace()``.

        Args:
            namespace: Namespace prefix to clear (e.g., ``"odoo"``)

        Returns:
            Number of models removed
        """
        prefix = f"{namespace}:"
        to_remove = [k for k in self._models if k.startswith(prefix)]
        for k in to_remove:
            del self._models[k]
        if to_remove:
            self.invalidate_model_cache()
            logger.info(f"Unregistered {len(to_remove)} models from namespace '{namespace}'")
        return len(to_remove)

    def get_model(self, name: str) -> Optional[DbTableModelImpl]:
        """Get a registered model by name.

        Supports both namespaced (``"odoo:OdooSaleOrderModel"``) and
        bare (``"OdooSaleOrderModel"``) lookups.
        """
        return self._models.get(name)

    def get_all_model_names(self) -> List[str]:
        """Get all registered model names (including namespace-prefixed)."""
        return list(self._models.keys())

    def invalidate_model_cache(self) -> None:
        """Invalidate all cached query results and physical column mappings."""
        self._cache.clear()
        self._mapping_cache.clear()
        logger.debug("Cache invalidated")

    # ==================== Governance Helpers ====================

    def _apply_query_governance(
        self,
        model_name: str,
        request: SemanticQueryRequest,
    ) -> Tuple[Optional[SemanticQueryResponse], SemanticQueryRequest]:
        """Validate field governance and merge system_slice.

        Returns ``(error_response, updated_request)``.  When ``error_response``
        is not ``None``, the caller should return it immediately.  Otherwise
        the returned ``updated_request`` has ``system_slice`` merged into
        ``slice`` and is ready for query building.
        """
        field_access = request.field_access
        denied_qm_fields = None
        if request.denied_columns:
            mapping = self.get_physical_column_mapping(model_name)
            if mapping:
                denied_qm_fields = mapping.to_denied_qm_fields(request.denied_columns)

        has_whitelist = field_access is not None and bool(field_access.visible)
        has_blacklist = bool(denied_qm_fields)
        if has_whitelist or has_blacklist:
            validation = validate_field_access(
                columns=request.columns,
                slice_items=request.slice,
                order_by=request.order_by,
                calculated_fields=request.calculated_fields,
                field_access=field_access,
                denied_qm_fields=denied_qm_fields,
            )
            if not validation.valid:
                return SemanticQueryResponse.from_error(validation.error_message), request

        if request.system_slice:
            merged_slice = list(request.slice) + list(request.system_slice)
            request = request.model_copy(update={"slice": merged_slice})

        return None, request

    def _sanitize_error(
        self,
        model_name: Optional[str],
        raw_error: Optional[str],
    ) -> Optional[str]:
        """Apply :func:`sanitize_engine_error` with the model's physical
        column mapping when available.

        Safe to call with ``None`` / empty error — returns as-is.  Used to
        make sure any error text reaching callers is in QM vocabulary and
        does not leak physical column or alias names (BUG-007 v1.3).
        """
        if not raw_error:
            return raw_error
        mapping: Optional[PhysicalColumnMapping] = None
        if model_name:
            try:
                mapping = self.get_physical_column_mapping(model_name)
            except Exception:  # pragma: no cover — mapping build is best-effort
                mapping = None
        return sanitize_engine_error(
            raw_error, model_name=model_name, mapping=mapping,
        )

    def _sanitize_response_error(
        self,
        model_name: Optional[str],
        response: SemanticQueryResponse,
    ) -> SemanticQueryResponse:
        """In-place rewrite of ``response.error`` via :meth:`_sanitize_error`.

        Returns the same response (for call-site convenience)."""
        if response is not None and response.error:
            response.error = self._sanitize_error(model_name, response.error)
        return response

    def _resolve_effective_visible(
        self,
        model_names: List[str],
        visible_fields: Optional[List[str]],
        denied_columns: Optional[List['DeniedColumn']],
    ) -> Optional[set]:
        """Merge ``visible_fields`` whitelist with ``denied_columns`` blacklist.

        Returns an effective visible set, or ``None`` when no governance applies.
        Used by both JSON and markdown metadata builders.
        """
        effective: Optional[set] = set(visible_fields) if visible_fields is not None else None

        if not denied_columns:
            return effective

        all_denied_qm: set = set()
        all_qm: set = set()
        for name in model_names:
            mapping = self.get_physical_column_mapping(name)
            if mapping:
                all_denied_qm.update(mapping.to_denied_qm_fields(denied_columns))
                all_qm.update(mapping.get_all_qm_field_names())

        if not all_denied_qm:
            return effective

        if effective is not None:
            effective -= all_denied_qm
        else:
            effective = all_qm - all_denied_qm

        return effective

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

        resp = SemanticMetadataResponse(models=models)
        resp.warnings = []
        return resp

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
            return SemanticQueryResponse.from_error(f"Model not found: {model}")

        # --- v1.2/v1.3: governance check + system_slice merge ---
        governance_error, request = self._apply_query_governance(model, request)
        if governance_error is not None:
            return governance_error

        invalid_field = validate_query_fields(table_model, request)
        if invalid_field is not None:
            return SemanticQueryResponse.from_error(
                invalid_field.message,
                error_detail=invalid_field.to_public_dict(),
            )

        # Build query
        try:
            build_result = self._build_query(table_model, request)
        except Exception as e:
            logger.exception(f"Failed to build query for model {model}")
            return SemanticQueryResponse.from_error(f"Query build failed: {str(e)}")

        # Validate mode
        if mode == QueryMode.VALIDATE:
            return SemanticQueryResponse.from_legacy(
                data=[],
                columns_info=build_result.columns,
                sql=build_result.sql,
                warnings=build_result.warnings,
                duration_ms=(time.time() - start_time) * 1000,
            )

        # Check cache
        cache_key = self._get_cache_key(model, request)
        if self._enable_cache and cache_key in self._cache:
            cached_response, cached_time = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                logger.debug(f"Cache hit for {model}")
                return cached_response

        # Execute query
        effective_limit = min(request.limit or self._default_limit, self._max_limit)
        try:
            response = self._execute_query(
                build_result, table_model,
                start=request.start, limit=effective_limit,
            )
        except Exception as e:
            logger.exception(f"Failed to execute query for model {model}")
            return self._sanitize_response_error(
                model,
                SemanticQueryResponse.from_legacy(
                    data=[],
                    sql=build_result.sql,
                    error=f"Query execution failed: {str(e)}",
                    warnings=build_result.warnings,
                ),
            )

        # Sanitize any executor-surfaced error (e.g. PostgreSQL column
        # not-exist + physical HINT) before the response leaves the engine.
        self._sanitize_response_error(model, response)

        # --- v1.2 column governance: post-execution filtering + masking ---
        field_access = request.field_access
        display_to_qm: Optional[Dict[str, str]] = None
        if field_access is not None and (field_access.visible or field_access.masking):
            display_to_qm = {}
            for col in build_result.columns:
                disp = col.get("name", "")
                qm = col.get("fieldName", "")
                if disp and qm:
                    display_to_qm[disp] = qm

        if field_access is not None and field_access.visible:
            response.items = filter_response_columns(
                response.items, field_access, display_to_qm=display_to_qm,
            )
        if field_access is not None and field_access.masking:
            apply_masking(
                response.items, field_access, display_to_qm=display_to_qm,
            )

        # Add debug info with timing and SQL
        duration_ms = (time.time() - start_time) * 1000
        # DebugInfo already imported at module level from foggy.mcp_spi
        response.debug = DebugInfo(
            duration_ms=duration_ms,
            extra={"sql": build_result.sql, "from_cache": False},
        )
        if build_result.warnings:
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
        table_name = model.get_table_expr_for_model(model.name)
        builder.from_table(table_name, alias=model.get_table_alias_for_model(model.name))

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
        explicit_joins_added: set[tuple[str, str, str]] = set()

        def ensure_join(join_def: DimensionJoinDef):
            """Add LEFT JOIN if not already added."""
            if join_def.name not in joined_dims:
                ensure_explicit_joins_for_field(join_def.name)
                joined_dims[join_def.name] = join_def
                ta = join_def.get_alias()
                root_alias = model.get_table_alias_for_model(model.get_field_model_name(join_def.name))
                on_cond = f"{root_alias}.{join_def.foreign_key} = {ta}.{join_def.primary_key}"
                builder.left_join(join_def.table_name, alias=ta, on_condition=on_cond)

        def ensure_explicit_joins_for_field(field_name: str) -> None:
            field_model_name = model.get_field_model_name(field_name)
            if field_model_name == model.name:
                return
            for explicit_join in model.explicit_joins:
                if explicit_join.right_model != field_model_name:
                    continue
                key = (
                    explicit_join.join_type,
                    explicit_join.left_model,
                    explicit_join.right_model,
                )
                if key in explicit_joins_added:
                    continue
                on_clauses: List[str] = []
                for condition in explicit_join.conditions:
                    left_resolved = model.resolve_field_for_model(
                        condition.left_field,
                        condition.left_model,
                    )
                    right_resolved = model.resolve_field_for_model(
                        condition.right_field,
                        condition.right_model,
                    )
                    if left_resolved is None or right_resolved is None:
                        raise ValueError(
                            f"Failed to resolve explicit join condition "
                            f"{condition.left_field} = {condition.right_field}"
                        )
                    on_clauses.append(
                        f"{left_resolved['sql_expr']} = {right_resolved['sql_expr']}"
                    )
                join_method = {
                    "LEFT": builder.left_join,
                    "INNER": builder.inner_join,
                }.get(explicit_join.join_type.upper())
                if join_method is None:
                    join_method = lambda table_name, alias, on_condition: builder.join(
                        explicit_join.join_type.upper(),
                        table_name,
                        alias=alias,
                        on_condition=on_condition,
                    )
                join_method(
                    explicit_join.get_right_table_expr(),
                    alias=explicit_join.right_alias,
                    on_condition=" AND ".join(on_clauses),
                )
                explicit_joins_added.add(key)

        def ensure_runtime_joins(field_name: str) -> None:
            ensure_explicit_joins_for_field(field_name)
            resolved = model.resolve_field(field_name)
            if resolved and resolved["join_def"]:
                ensure_join(resolved["join_def"])

        # 2. SELECT columns
        has_aggregation = False
        selected_dims: List[str] = []  # SQL expressions for auto GROUP BY

        if not request.columns:
            # No columns → select visible dimensions + measures
            for dim_name, dim in model.dimensions.items():
                if dim.visible:
                    col_expr = f"t.{dim.column}"
                    label = dim.alias or dim.name
                    builder.select(f"{col_expr} AS {self._qi(label)}")
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
                    ensure_runtime_joins(col_name)
                    # Auto-JOIN if needed
                    label = resolved["alias_label"]
                    sql_expr = resolved["sql_expr"]

                    if resolved["is_measure"] and resolved["aggregation"]:
                        agg = resolved["aggregation"]
                        if agg == "COUNT_DISTINCT":
                            sel = f"COUNT(DISTINCT {sql_expr}) AS {self._qi(label)}"
                        else:
                            sel = f"{agg}({sql_expr}) AS {self._qi(label)}"
                        builder.select(sel)
                        columns_info.append({"name": label, "fieldName": col_name, "expression": sql_expr, "aggregation": agg})
                        has_aggregation = True
                    else:
                        builder.select(f"{sql_expr} AS {self._qi(label)}")
                        columns_info.append({"name": label, "fieldName": col_name, "expression": sql_expr, "aggregation": None})
                        selected_dims.append(sql_expr)
                else:
                    # Fallback: try as raw fact table column
                    dim = model.get_dimension(col_name)
                    measure = model.get_measure(col_name)
                    if dim:
                        col_expr = f"t.{dim.column}"
                        label = dim.alias or dim.name
                        builder.select(f"{col_expr} AS {self._qi(label)}")
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
            builder.select(f"{select_sql} AS {self._qi(alias)}")
            columns_info.append({
                "name": alias, "fieldName": cf.name,
                "expression": cf.expression, "aggregation": cf.agg,
                "window": cf.is_window_function(),
            })
            if cf.agg or cf.is_window_function():
                has_aggregation = True

        # 3. WHERE clause
        for filter_item in request.slice:
            self._add_filter(builder, model, filter_item, ensure_join)

        # 4. GROUP BY
        if request.group_by:
            for col_name in request.group_by:
                resolved = model.resolve_field(col_name)
                if resolved:
                    ensure_runtime_joins(col_name)
                    builder.group_by(resolved["sql_expr"])
                else:
                    dim = model.get_dimension(col_name)
                    alias = model.get_table_alias_for_model(model.get_field_model_name(col_name))
                    builder.group_by(f"{alias}.{dim.column}" if dim else f"{alias}.{col_name}")
        elif has_aggregation and selected_dims:
            for dim_expr in selected_dims:
                builder.group_by(dim_expr)

        # 5. HAVING
        having_filters = (request.hints or {}).get("having", [])
        for hf in having_filters:
            col, op, val = hf.get("column"), hf.get("operator"), hf.get("value")
            if col and op and val is not None:
                builder.having(f"{col} {op} ?", params=[val])

        # 6. ORDER BY
        selected_order_aliases = self._build_selected_order_aliases(columns_info)
        for order_item in request.order_by:
            column = order_item.get("column") or order_item.get("field")
            direction = (order_item.get("direction") or order_item.get("dir", "asc")).upper()
            if column:
                selected_alias = selected_order_aliases.get(column)
                if selected_alias:
                    builder.order_by(selected_alias, direction)
                    continue
                resolved = model.resolve_field(column)
                if resolved:
                    ensure_runtime_joins(column)
                    if resolved["is_measure"]:
                        builder.order_by(self._qi(resolved['alias_label']), direction)
                    else:
                        builder.order_by(resolved["sql_expr"], direction)
                else:
                    builder.order_by(column, direction)

        # 7. LIMIT/OFFSET
        limit = min(request.limit or self._default_limit, self._max_limit)
        builder.limit(limit)
        if request.start:
            builder.offset(request.start)

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
                select_expr = f"COUNT(DISTINCT t.{col}) AS {self._qi(alias)}"
            else:
                select_expr = f"{agg_name}(t.{col}) AS {self._qi(alias)}"
            agg = agg_name
        else:
            select_expr = f"t.{col} AS {self._qi(alias)}"

        return {
            "name": alias,
            "fieldName": measure.name,
            "expression": f"t.{col}",
            "aggregation": agg,
            "select_expr": select_expr,
        }

    def _parse_inline_expression(
        self,
        col_name: str,
        model: DbTableModelImpl,
        ensure_join=None,
    ) -> Optional[Dict[str, Any]]:
        """Parse inline aggregate expression like 'sum(salesAmount) as totalSales'.

        Returns column info dict if parsed, None if not an inline expression.
        """
        parsed = parse_inline_aggregate(col_name)
        if not parsed:
            return None

        agg = parsed.aggregation
        sql_col = self._resolve_expression_fields(
            parsed.inner_expression,
            model,
            ensure_join,
        )

        if agg == "COUNT_DISTINCT":
            select_expr = f"COUNT(DISTINCT {sql_col}) AS {self._qi(parsed.alias)}"
        else:
            select_expr = f"{agg}({sql_col}) AS {self._qi(parsed.alias)}"

        return {
            "name": parsed.alias,
            "fieldName": col_name,
            "expression": sql_col,
            "aggregation": agg,
            "select_expr": select_expr,
        }

    def _build_selected_order_aliases(
        self,
        columns_info: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """Map selected column keys to their quoted SQL aliases for ORDER BY."""
        alias_map: Dict[str, str] = {}

        for info in columns_info:
            alias = info.get("name")
            if not alias:
                continue

            quoted_alias = self._qi(alias)
            alias_map[alias] = quoted_alias

            field_name = info.get("fieldName")
            if field_name:
                alias_map[field_name] = quoted_alias

        return alias_map

    # ==================== Calculated Fields & Window Functions ====================

    # Allowed SQL functions whitelist (aligned with Java AllowedFunctions.java).
    # Only these functions are permitted in calculated fields and expressions.
    # Any function call not in this set will be rejected to prevent SQL injection.
    _ALLOWED_FUNCTIONS = frozenset({
        # Aggregate (7)
        'SUM', 'AVG', 'COUNT', 'MIN', 'MAX', 'GROUP_CONCAT',
        'COUNT_DISTINCT',
        # Statistical aggregate (4)
        'STDDEV_POP', 'STDDEV_SAMP', 'VAR_POP', 'VAR_SAMP',
        # Window (10)
        'ROW_NUMBER', 'RANK', 'DENSE_RANK', 'NTILE',
        'LAG', 'LEAD', 'FIRST_VALUE', 'LAST_VALUE',
        'CUME_DIST', 'PERCENT_RANK',
        # String (12)
        'CONCAT', 'CONCAT_WS', 'SUBSTRING', 'SUBSTR', 'LEFT', 'RIGHT',
        'LTRIM', 'RTRIM', 'LPAD', 'RPAD', 'REPLACE', 'LOCATE',
        'CHAR_LENGTH', 'INSTR', 'UPPER', 'LOWER', 'TRIM',
        # Numeric (7)
        'ABS', 'ROUND', 'FLOOR', 'CEIL', 'CEILING', 'MOD', 'POWER', 'SQRT',
        # Date (12)
        'YEAR', 'MONTH', 'DAY', 'HOUR', 'MINUTE', 'SECOND',
        'DATE_FORMAT', 'STR_TO_DATE', 'DATE_ADD', 'DATE_SUB',
        'DATEDIFF', 'TIMESTAMPDIFF', 'EXTRACT',
        'TIME', 'CURRENT_TIME', 'CURRENT_TIMESTAMP',
        # Conditional / type (8)
        'COALESCE', 'IFNULL', 'NVL', 'NULLIF', 'IF', 'CAST', 'CONVERT', 'ISNULL',
        # Misc
        'DISTINCT',
    })

    @classmethod
    def validate_function(cls, func_name: str) -> bool:
        """Check if a function name is in the allowed whitelist.

        Args:
            func_name: Function name (case-insensitive)

        Returns:
            True if allowed, False otherwise
        """
        return func_name.upper() in cls._ALLOWED_FUNCTIONS

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
            alias = model.get_table_alias_for_model(model.get_field_model_name(field_name))
            return f"{alias}.{dim.column}"
        measure = model.get_measure(field_name)
        if measure:
            alias = model.get_table_alias_for_model(model.get_field_model_name(field_name))
            return f"{alias}.{measure.column or measure.name}"
        return field_name

    def _render_expression(self, expression: str, model: DbTableModelImpl, ensure_join=None) -> str:
        """Render an expression to SQL, lowering IF(...) to CASE WHEN recursively."""
        result: List[str] = []
        i = 0
        length = len(expression)
        while i < length:
            ch = expression[i]
            if ch in ("'", '"'):
                end = skip_string_literal(expression, i)
                result.append(expression[i:end])
                i = end
                continue
            if ch == "&" and i + 1 < length and expression[i + 1] == "&":
                result.append(" AND ")
                i += 2
                continue
            if ch == "|" and i + 1 < length and expression[i + 1] == "|":
                result.append(" OR ")
                i += 2
                continue
            if ch == "=" and i + 1 < length and expression[i + 1] == "=":
                result.append(" = ")
                i += 2
                continue
            if ch.isalpha() or ch == "_":
                start = i
                i += 1
                while i < length and (expression[i].isalnum() or expression[i] in ("_", "$")):
                    i += 1
                token = expression[start:i]
                j = i
                while j < length and expression[j].isspace():
                    j += 1
                if j < length and expression[j] == "(":
                    close = find_matching_paren(expression, j)
                    if close < 0:
                        raise ValueError(f"Unclosed function call in expression: {expression}")
                    func_name = token.upper()
                    if func_name not in self._ALLOWED_FUNCTIONS and func_name not in self._SQL_KEYWORDS:
                        raise ValueError(
                            f"Function '{token}' is not in the allowed function whitelist. "
                            f"Allowed functions: {sorted(self._ALLOWED_FUNCTIONS)}"
                        )
                    args = split_top_level_commas(expression[j + 1:close])
                    if func_name == "IF":
                        if len(args) != 3:
                            raise ValueError(f"IF(...) expects 3 arguments, got {len(args)} in: {expression}")
                        cond_sql = self._render_expression(args[0], model, ensure_join).strip()
                        then_sql = self._render_expression(args[1], model, ensure_join).strip()
                        else_sql = self._render_expression(args[2], model, ensure_join).strip()
                        result.append(
                            f"CASE WHEN {cond_sql} THEN {then_sql} ELSE {else_sql} END"
                        )
                    else:
                        rendered_args = [
                            self._render_expression(arg, model, ensure_join).strip()
                            for arg in args
                        ]
                        result.append(f"{func_name}({', '.join(rendered_args)})")
                    i = close + 1
                    continue
                if token.upper() in self._SQL_KEYWORDS:
                    result.append(token)
                else:
                    result.append(self._resolve_single_field(token, model, ensure_join))
                continue
            result.append(ch)
            i += 1
        return "".join(result)

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
        return self._render_expression(expression, model, ensure_join)

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
        root_builder: Optional[SqlQueryBuilder] = None,
    ) -> None:
        """Add a single filter condition with auto-JOIN support.

        Supports compound conditions:
          {"$or": [{...}, {...}]}  → (cond1 OR cond2)
          {"$and": [{...}, {...}]} → cond1 AND cond2
        Nesting is supported: {"$or": [{"$and": [...]}, {...}]}
        """
        if root_builder is None:
            root_builder = builder

        # --- Handle $or compound condition ---
        if "$or" in filter_item:
            or_fragments: list[str] = []
            or_params: list[Any] = []
            for sub_item in filter_item["$or"]:
                sub_builder = SqlQueryBuilder()
                self._add_filter(sub_builder, model, sub_item, ensure_join, root_builder=root_builder)
                if sub_builder._query.where and sub_builder._query.where.conditions:
                    fragment = " AND ".join(sub_builder._query.where.conditions)
                    if len(sub_builder._query.where.conditions) > 1:
                        fragment = f"({fragment})"
                    or_fragments.append(fragment)
                    or_params.extend(sub_builder._query.where.params)
            if or_fragments:
                or_clause = " OR ".join(or_fragments)
                if len(or_fragments) > 1:
                    or_clause = f"({or_clause})"
                builder.where(or_clause, params=or_params if or_params else None)
            return

        # --- Handle $and compound condition ---
        if "$and" in filter_item:
            for sub_item in filter_item["$and"]:
                self._add_filter(builder, model, sub_item, ensure_join, root_builder=root_builder)
            return

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
            alias = model.get_table_alias_for_model(model.get_field_model_name(column))
            col_expr = f"{alias}.{dim.column}" if dim else f"{alias}.{column}"

        # Check for $field value reference: {"value": {"$field": "otherField"}}
        # Generates field-to-field comparison: col_a > col_b (no bind param)
        if isinstance(value, dict) and "$field" in value:
            ref_field = value["$field"]
            ref_resolved = model.resolve_field(ref_field)
            if ref_resolved:
                ref_expr = ref_resolved["sql_expr"]
                if ref_resolved["join_def"] and ensure_join:
                    ensure_join(ref_resolved["join_def"])
            else:
                ref_dim = model.get_dimension(ref_field)
                ref_alias = model.get_table_alias_for_model(model.get_field_model_name(ref_field))
                ref_expr = f"{ref_alias}.{ref_dim.column}" if ref_dim else f"{ref_alias}.{ref_field}"

            # Map operator to SQL
            op_map = {"=": "=", "eq": "=", "!=": "<>", "<>": "<>", "neq": "<>",
                       ">": ">", "gt": ">", ">=": ">=", "gte": ">=",
                       "<": "<", "lt": "<", "<=": "<=", "lte": "<=",
                       "===": "=", "force_eq": "="}
            sql_op = op_map.get(operator, operator)
            builder.where(f"{col_expr} {sql_op} {ref_expr}")
            return

        # Resolve value: support "values" key for IN, or range from filter_item
        effective_value = value
        if operator.upper() in ("IN", "NOT IN", "NIN"):
            raw = filter_item.get("values") or filter_item.get("value")
            effective_value = raw if isinstance(raw, list) else ([raw] if raw is not None else [])
        elif operator.upper() == "BETWEEN":
            from_val = filter_item.get("from")
            to_val = filter_item.get("to")
            if from_val is not None and to_val is not None:
                effective_value = [from_val, to_val]

        hierarchy_condition = self._build_hierarchy_filter(
            root_builder, model, column, operator, effective_value
        )
        if hierarchy_condition:
            builder.where(
                hierarchy_condition["condition"],
                params=hierarchy_condition["params"] if hierarchy_condition["params"] else None,
            )
            return

        # Use SqlFormulaRegistry for all operators
        params: List[Any] = []
        condition = self._formula_registry.build_condition(
            col_expr, operator, effective_value, params
        )
        if condition:
            builder.where(condition, params=params if params else None)

    def _build_hierarchy_filter(
        self,
        builder: SqlQueryBuilder,
        model: DbTableModelImpl,
        field_name: str,
        operator: str,
        value: Any,
    ) -> Optional[Dict[str, Any]]:
        """Build closure-table JOIN + WHERE for hierarchy operators."""
        op_class = self._hierarchy_registry.get(operator)
        if op_class is None or "$" not in field_name:
            return None

        dim_name, suffix = field_name.split("$", 1)
        if suffix != "id":
            return None

        dim = model.get_dimension(dim_name)
        join_def = model.get_dimension_join(dim_name)
        if dim is None or join_def is None or not dim.supports_hierarchy_operators():
            return None

        child_column = dim.level_column or join_def.primary_key
        closure = ClosureTableDef(
            table_name=dim.hierarchy_table,
            parent_column=dim.parent_column or "parent_id",
            child_column=child_column,
        )

        alias_index = 1
        existing_joins = []
        if builder._query.from_clause:
            existing_joins = builder._query.from_clause.joins
        alias_index += len(existing_joins)
        closure_alias = f"h_{dim_name}_{alias_index}"

        op_instance = op_class.model_construct(dimension=dim_name, member_value=value)
        values = value if isinstance(value, list) else [value]
        params: List[Any] = []
        fragments: List[str] = []

        self._ensure_join(
            builder,
            closure.qualified_table(),
            closure_alias,
            (
                f"t.{join_def.foreign_key} = {closure_alias}."
                f"{closure.parent_column if op_instance.is_ancestor_direction else closure.child_column}"
            ),
        )

        for single_value in values:
            if op_instance.is_ancestor_direction:
                built = HierarchyConditionBuilder.build_ancestors_condition(
                    closure=closure,
                    closure_alias=closure_alias,
                    fact_fk_column=join_def.foreign_key,
                    fact_alias="t",
                    value=single_value,
                    include_self=operator.lower() == "selfandancestorsof",
                )
            else:
                built = HierarchyConditionBuilder.build_descendants_condition(
                    closure=closure,
                    closure_alias=closure_alias,
                    fact_fk_column=join_def.foreign_key,
                    fact_alias="t",
                    value=single_value,
                    include_self=operator.lower() == "selfanddescendantsof",
                )

            leaf_parts = [built["where_condition"]]
            if built["distance_condition"]:
                leaf_parts.insert(0, built["distance_condition"])
            fragments.append("(" + " AND ".join(leaf_parts) + ")")
            params.extend(built["where_params"])

        if not fragments:
            return None

        condition = fragments[0] if len(fragments) == 1 else "(" + " OR ".join(fragments) + ")"
        return {"condition": condition, "params": params}

    def _ensure_join(
        self,
        builder: SqlQueryBuilder,
        table_name: str,
        alias: str,
        on_condition: str,
    ) -> None:
        """Add a JOIN if the exact table alias pair is not already present."""
        if not builder._query.from_clause:
            return
        for join in builder._query.from_clause.joins:
            if join.table_name == table_name and join.alias == alias:
                return
        builder.left_join(table_name, alias=alias, on_condition=on_condition)

    # ==================== Query Execution ====================

    def _get_sync_loop(self):
        """Get or create a persistent event loop for synchronous execution.

        Reuses the same loop across calls to avoid closing connection pools
        (e.g., asyncpg) that are bound to a specific event loop.
        """
        import asyncio
        if not hasattr(self, '_sync_loop') or self._sync_loop is None or self._sync_loop.is_closed():
            self._sync_loop = asyncio.new_event_loop()
        return self._sync_loop

    def _execute_query(
        self,
        build_result: QueryBuildResult,
        model: DbTableModelImpl,
        start: int = 0,
        limit: Optional[int] = None,
    ) -> SemanticQueryResponse:
        """Execute the built query (synchronous wrapper).

        When called from an async context (e.g., FastAPI), prefer
        using query_model_async() instead.

        Uses a persistent event loop to avoid closing async connection
        pools between consecutive queries (fixes asyncpg/aiomysql
        "Event loop is closed" errors in embedded scenarios).
        """
        import asyncio

        executor = self._resolve_executor(model)
        if executor is None:
            logger.warning("No database executor configured - returning empty result")
            return SemanticQueryResponse.from_legacy(
                data=[],
                columns_info=build_result.columns,
            )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in an async context (e.g., FastAPI) —
            # run in a thread with its own persistent loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                sync_loop = self._get_sync_loop()
                future = pool.submit(
                    sync_loop.run_until_complete,
                    self._execute_query_async(build_result, executor=executor,
                                              start=start, limit=limit),
                )
                return future.result(timeout=60)
        else:
            # No running loop — use persistent loop directly
            return self._get_sync_loop().run_until_complete(
                self._execute_query_async(build_result, executor=executor,
                                          start=start, limit=limit)
            )

    async def _execute_query_async(
        self,
        build_result: QueryBuildResult,
        executor=None,
        start: int = 0,
        limit: Optional[int] = None,
    ) -> SemanticQueryResponse:
        """Execute the built query asynchronously.

        Args:
            build_result: The built query with SQL and params
            executor: Optional executor override (for multi-datasource routing).
                     Falls back to self._executor if not provided.
            start: Pagination start offset (for response pagination info).
            limit: Pagination limit (for response pagination info).
        """
        executor = executor or self._executor
        if executor is None:
            return SemanticQueryResponse.from_legacy(
                data=[],
                columns_info=build_result.columns,
                error="No database executor configured",
            )

        result = await executor.execute(
            build_result.sql,
            build_result.params,
        )

        if result.error:
            return SemanticQueryResponse.from_legacy(
                data=[],
                columns_info=build_result.columns,
                sql=build_result.sql,
                error=result.error,
            )

        return SemanticQueryResponse.from_legacy(
            data=result.rows,
            columns_info=build_result.columns,
            total=result.total,
            sql=build_result.sql,
            start=start,
            limit=limit,
            has_more=result.has_more,
        )

    def set_executor(self, executor) -> None:
        """Set the database executor."""
        self._executor = executor
        logger.info(f"Database executor set: {type(executor).__name__}")

    def set_executor_manager(self, manager) -> None:
        """Set the executor manager for multi-datasource routing.

        Args:
            manager: ExecutorManager instance managing named executors
        """
        self._executor_manager = manager
        logger.info(f"Executor manager set with {len(manager.list_names())} data sources: {manager.list_names()}")

    def _resolve_executor(self, model: DbTableModelImpl):
        """Resolve the appropriate executor for a model based on its source_datasource.

        Resolution order:
        1. If model has source_datasource and executor_manager has it → use named executor
        2. Fall back to executor_manager default
        3. Fall back to self._executor (backward compatible)

        Args:
            model: The table model being queried

        Returns:
            DatabaseExecutor or None
        """
        ds_name = getattr(model, 'source_datasource', None)
        if ds_name and self._executor_manager:
            executor = self._executor_manager.get(ds_name)
            if executor:
                return executor
            logger.warning(
                f"Named executor '{ds_name}' not found for model '{model.name}', "
                f"falling back to default"
            )
        if self._executor_manager:
            default = self._executor_manager.get_default()
            if default:
                return default
        return self._executor

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
            return SemanticQueryResponse.from_error(f"Model not found: {model}")

        # --- v1.2/v1.3: governance check + system_slice merge ---
        governance_error, request = self._apply_query_governance(model, request)
        if governance_error is not None:
            return governance_error

        try:
            build_result = self._build_query(table_model, request)
        except Exception as e:
            logger.exception(f"Failed to build query for model {model}")
            return SemanticQueryResponse.from_error(f"Query build failed: {str(e)}")

        if mode == QueryMode.VALIDATE:
            return SemanticQueryResponse.from_legacy(
                data=[],
                columns_info=build_result.columns,
                sql=build_result.sql,
                warnings=build_result.warnings,
                duration_ms=(time.time() - start_time) * 1000,
            )

        cache_key = self._get_cache_key(model, request)
        if self._enable_cache and cache_key in self._cache:
            cached_response, cached_time = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_response

        effective_limit = min(request.limit or self._default_limit, self._max_limit)
        try:
            executor = self._resolve_executor(table_model)
            response = await self._execute_query_async(
                build_result, executor=executor,
                start=request.start, limit=effective_limit,
            )
        except Exception as e:
            logger.exception(f"Failed to execute query for model {model}")
            return self._sanitize_response_error(
                model,
                SemanticQueryResponse.from_legacy(
                    data=[],
                    sql=build_result.sql,
                    error=f"Query execution failed: {str(e)}",
                    warnings=build_result.warnings,
                ),
            )

        # Sanitize any executor-surfaced error before returning (BUG-007 v1.3)
        self._sanitize_response_error(model, response)

        # Add debug info
        duration_ms = (time.time() - start_time) * 1000
        response.debug = DebugInfo(
            duration_ms=duration_ms,
            extra={"sql": build_result.sql, "from_cache": False},
        )
        if build_result.warnings:
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

    def get_metadata_v3(
        self,
        model_names: Optional[List[str]] = None,
        visible_fields: Optional[List[str]] = None,
        denied_columns: Optional[List[DeniedColumn]] = None,
    ) -> Dict[str, Any]:
        """Build V3 metadata package — aligned with Java SemanticServiceV3Impl.

        Returns a combined metadata package with all models and their fields
        in the format expected by AI assistants (same as Java get_metadata).

        Parameters
        ----------
        model_names
            Subset of models to include. ``None`` → all.
        visible_fields
            v1.2 column governance: when set, only fields whose ``fieldName``
            is in this list appear in the ``fields`` dict. ``None`` means no
            filtering (v1.1 compat).
        denied_columns
            v1.3 physical column blacklist: when set, denied columns are
            resolved per-model to denied QM fields which are then merged
            with ``visible_fields`` for consistent trimming.

        Structure:
            {
                "prompt": "usage instructions...",
                "version": "v3",
                "fields": { fieldName -> fieldInfo },
                "models": { modelName -> modelInfo },
                "physicalTables": [{"table": "...", "role": "..."}]  // v1.3
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
                "purpose": model.description or "Data querying and analysis",
                "scenarios": ["Data Querying", "Statistical Analysis", "Report Generation"],
            }
            ai_desc = getattr(model, 'ai_description', None)
            if ai_desc:
                models_info[model_name]["aiDescription"] = ai_desc

            # Dimension JOIN fields → expand to $id, $caption, and $properties
            for join_def in model.dimension_joins:
                dim_name = join_def.name
                dim_caption = join_def.caption or dim_name

                # Check hierarchy support from the corresponding dimension object
                dim_obj = model.dimensions.get(dim_name)
                is_hier = dim_obj is not None and dim_obj.supports_hierarchy_operators()

                # dim$id
                id_fn = f"{dim_name}$id"
                if id_fn not in fields:
                    field_info: Dict[str, Any] = {
                        "name": f"{dim_caption}(ID)",
                        "fieldName": id_fn,
                        "meta": f"Dimension ID | {join_def.primary_key}",
                        "type": "INTEGER",
                        "filterType": "dimension",
                        "filterable": True,
                        "measure": False,
                        "aggregatable": False,
                        "sourceColumn": join_def.foreign_key,
                        "models": {},
                    }
                    if is_hier:
                        field_info["hierarchical"] = True
                        field_info["supportedOps"] = ["selfAndDescendantsOf", "selfAndAncestorsOf"]
                    fields[id_fn] = field_info
                fields[id_fn]["models"][model_name] = {
                    "description": f"{dim_caption}(ID)",
                        "usage": "Used for exact filtering and sorting",
                }

                # dim$caption
                cap_fn = f"{dim_name}$caption"
                if cap_fn not in fields:
                    fields[cap_fn] = {
                        "name": f"{dim_caption} (Caption)",
                        "fieldName": cap_fn,
                        "meta": "Dimension Caption | TEXT",
                        "type": "TEXT",
                        "filterType": "dimension",
                        "filterable": True,
                        "measure": False,
                        "aggregatable": False,
                        "models": {},
                    }
                fields[cap_fn]["models"][model_name] = {
                    "description": f"{dim_caption} display name",
                    "usage": "Used for display and fuzzy search",
                }

                # dim$property fields
                for prop in join_def.properties:
                    prop_name = prop.get_name()
                    prop_fn = f"{dim_name}${prop_name}"
                    if prop_fn not in fields:
                        fields[prop_fn] = {
                            "name": prop.caption or prop_name,
                            "fieldName": prop_fn,
                            "meta": f"Dimension Property | {prop.data_type}",
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

            # Collect JOIN dimension names to exclude from fact-table properties
            # JOIN dimensions are already represented by $id/$caption fields above.
            # Including them again as plain fields would create duplicate sourceColumn
            # mappings (e.g. both company$id and company → sourceColumn: company_id),
            # causing downstream reverse-mapping to pick the wrong field name.
            join_dim_names = {jd.name for jd in model.dimension_joins}

            # Fact table own dimensions → use plain field name (no $id suffix)
            # These are simple attributes on the fact table (e.g. orderId, orderStatus),
            # NOT join dimensions, so they should be referenced directly by name.
            for dim_name, dim in model.dimensions.items():
                if dim_name in join_dim_names:
                    continue  # Skip JOIN dimensions — covered by $id/$caption above
                if dim_name not in fields:
                    fields[dim_name] = {
                        "name": dim.alias or dim_name,
                        "fieldName": dim_name,
                        "meta": f"Attribute | {dim.data_type.value}",
                        "type": dim.data_type.value.upper(),
                        "filterType": "text",
                        "filterable": dim.filterable,
                        "measure": False,
                        "aggregatable": False,
                        "sourceColumn": dim.column,
                        "models": {},
                    }
                fields[dim_name]["models"][model_name] = {
                    "description": dim.description or dim.alias or dim_name,
                }

            # Fact table properties (from TM properties section, stored in model.columns)
            # These are explicit properties like id, name, state, partner_share, etc.
            # NOT dimensions, so they appear with their camelCase name directly.
            for col_name, col_def in model.columns.items():
                if col_name not in fields:
                    col_type = col_def.column_type.value if col_def.column_type else "STRING"
                    fields[col_name] = {
                        "name": col_def.alias or col_name,
                        "fieldName": col_name,
                        "meta": f"Attribute | {col_type}",
                        "type": col_type.upper(),
                        "filterType": "text",
                        "filterable": True,
                        "measure": False,
                        "aggregatable": False,
                        "sourceColumn": col_def.name,  # SQL column name (snake_case)
                        "models": {},
                    }
                fields[col_name]["models"][model_name] = {
                    "description": col_def.comment or col_def.alias or col_name,
                }

            # Measure fields
            for measure_name, measure in model.measures.items():
                if measure_name not in fields:
                    agg_name = measure.aggregation.value.upper() if measure.aggregation else "SUM"
                    fields[measure_name] = {
                        "name": measure.alias or measure_name,
                        "fieldName": measure_name,
                        "meta": f"Measure | Number | Default Aggregation: {agg_name}",
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
                    "description": f"{measure.alias or measure_name} (Aggregation: {agg_name})",
                }

        # --- v1.3: collect physical tables (deduplicated, single pass) ---
        physical_tables: List[Dict[str, str]] = []
        pt_seen: set = set()
        for mn in target_models:
            mapping = self.get_physical_column_mapping(mn)
            if mapping:
                for pt in mapping.get_physical_tables():
                    t = pt["table"]
                    if t not in pt_seen:
                        pt_seen.add(t)
                        physical_tables.append(pt)

        # --- v1.2/v1.3: governance trimming ---
        effective_visible = self._resolve_effective_visible(
            target_models, visible_fields, denied_columns,
        )
        if effective_visible is not None:
            fields = {k: v for k, v in fields.items() if k in effective_visible}

        result: Dict[str, Any] = {
            "prompt": (
                "## Usage Notes (V3)\n"
                "- Use the fieldName values from fields directly\n"
                "- Use xxx$id for query/filtering or xxx$caption for display\n"
                "- Measures already carry default aggregation; inline expressions such as sum(fieldName) are supported\n"
                "- Fields marked hierarchical=true support hierarchy operators: "
                "selfAndDescendantsOf(value and all descendants), selfAndAncestorsOf(value and all ancestors)\n"
            ),
            "version": "v3",
            "fields": fields,
            "models": models_info,
        }
        if physical_tables:
            result["physicalTables"] = physical_tables
        return result

    def get_metadata_v3_markdown(
        self,
        model_names: Optional[List[str]] = None,
        visible_fields: Optional[List[str]] = None,
        denied_columns: Optional[List[DeniedColumn]] = None,
    ) -> str:
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
            return "# No data models available\n"

        # --- v1.2/v1.3: governance trimming ---
        target_names_only = [n for n, _ in target_models]
        visible_set = self._resolve_effective_visible(
            target_names_only, visible_fields, denied_columns,
        )

        if len(target_models) == 1:
            return self._build_single_model_markdown(
                target_models[0][0], target_models[0][1], visible_set=visible_set,
            )
        else:
            return self._build_multi_model_markdown(target_models, visible_set=visible_set)

    # ---------- Type description helpers (aligned with Java getDataTypeDescription) ----------

    @staticmethod
    def _get_column_type_description(column_type) -> str:
        """Map ColumnType enum to English description (aligned with Java getDataTypeDescription)."""
        if column_type is None:
            return "Text"
        type_name = column_type.value.upper() if hasattr(column_type, 'value') else str(column_type).upper()
        mapping = {
            "STRING": "Text",
            "TEXT": "Text",
            "INTEGER": "Text",   # Java maps INTEGER properties to Text by default
            "LONG": "Text",
            "FLOAT": "Number",
            "DOUBLE": "Number",
            "DECIMAL": "Number",
            "MONEY": "Currency",
            "NUMBER": "Number",
            "BOOLEAN": "Boolean",
            "BOOL": "Boolean",
            "DATE": "Date (yyyy-MM-dd)",
            "DAY": "Date (yyyy-MM-dd)",
            "DATETIME": "Datetime",
            "TIMESTAMP": "Datetime",
            "TIME": "Text",
            "DICT": "Dictionary",
            "JSON": "Text",
        }
        return mapping.get(type_name, "Text")

    def _build_single_model_markdown(
        self,
        model_name: str,
        model: 'DbTableModelImpl',
        visible_set: Optional[set] = None,
    ) -> str:
        """Build detailed markdown for a single model (aligned with Java buildSingleModelMarkdown).

        Parameters
        ----------
        visible_set
            v1.2 governance: only include fields whose name is in this set.
            ``None`` means no filtering.
        """
        lines: List[str] = []
        alias = model.alias or model_name

        def _visible(field_name: str) -> bool:
            return visible_set is None or field_name in visible_set

        # Collect dimension field names for exclusion from properties section
        dimension_field_names: set = set()

        lines.append(f"# {model_name} - {alias}")
        lines.append("")
        lines.append("## Model Information")
        lines.append(f"- Table: {model.source_table}")
        # Primary key (aligned with Java: jdbcModel.getIdColumn())
        if model.primary_key:
            lines.append(f"- Primary Key: {', '.join(model.primary_key)}")
        if model.description:
            lines.append(f"- Description: {model.description}")
        lines.append("")

        # Dimension JOIN fields
        if model.dimension_joins:
            dim_rows: List[str] = []
            for jd in model.dimension_joins:
                dc = jd.caption or jd.name
                dim_obj = model.dimensions.get(jd.name)
                is_hier = dim_obj is not None and dim_obj.supports_hierarchy_operators()
                hier_label = "✅ selfAndDescendantsOf / selfAndAncestorsOf" if is_hier else "-"
                id_field = f"{jd.name}$id"
                caption_field = f"{jd.name}$caption"
                dimension_field_names.add(id_field)
                dimension_field_names.add(caption_field)
                if _visible(id_field):
                    dim_rows.append(f"| {id_field} | {dc}(ID) | INTEGER | {hier_label} | {jd.key_description or jd.description or ''} |")
                if _visible(caption_field):
                    dim_rows.append(f"| {caption_field} | {dc} (Caption) | TEXT | - | {dc} display name |")
                for prop in jd.properties:
                    pn = prop.get_name()
                    prop_field = f"{jd.name}${pn}"
                    dimension_field_names.add(prop_field)
                    if _visible(prop_field):
                        dim_rows.append(f"| {prop_field} | {prop.caption or pn} | {prop.data_type} | - | {prop.description or ''} |")
            if dim_rows:
                lines.append("## Dimension Fields")
                lines.append("| Field Name | Label | Type | Hierarchy | Description |")
                lines.append("|------------|-------|------|-----------|-------------|")
                lines.extend(dim_rows)
                lines.append("")

        # Fact table own properties (aligned with Java: queryModel.getQueryProperties())
        # Use model.columns (DbColumnDef) — the TM-defined properties, NOT model.dimensions
        if model.columns:
            # Filter out columns already shown in dimension fields + governance
            filtered_columns = {
                name: col for name, col in model.columns.items()
                if name not in dimension_field_names and _visible(name)
            }
            if filtered_columns:
                lines.append("## Attribute Fields")
                lines.append("| Field Name | Label | Type | Description |")
                lines.append("|------------|-------|------|-------------|")
                for col_name, col in filtered_columns.items():
                    col_caption = col.alias or col_name
                    col_type = self._get_column_type_description(col.column_type)
                    col_desc = col.comment or ""
                    lines.append(f"| {col_name} | {col_caption} | {col_type} | {col_desc} |")
                lines.append("")

        # Measure fields
        if model.measures:
            measure_rows: List[str] = []
            for m_name, measure in model.measures.items():
                if not _visible(m_name):
                    continue
                m_alias = measure.alias or m_name
                agg = measure.aggregation.value.upper() if measure.aggregation else "-"
                m_desc = measure.description or ""
                measure_rows.append(f"| {m_name} | {m_alias} | NUMBER | {agg} | {m_desc} |")
            if measure_rows:
                lines.append("## Measure Fields")
                lines.append("| Field Name | Label | Type | Aggregation | Description |")
                lines.append("|------------|-------|------|-------------|-------------|")
                lines.extend(measure_rows)
                lines.append("")

        lines.append("## Usage Tips")
        lines.append("- Use `xxx$id` for query/filtering, `xxx$caption` for display, and `xxx$property` for dimension properties")
        lines.append("- Measures support inline aggregation: `sum(salesAmount) as total`")
        lines.append("- The system handles groupBy automatically in most cases")
        lines.append("- Hierarchical dimensions support `selfAndDescendantsOf` (value and all descendants) and `selfAndAncestorsOf` (value and all ancestors)")

        return "\n".join(lines)

    def _build_multi_model_markdown(
        self,
        models: List[tuple],
        visible_set: Optional[set] = None,
    ) -> str:
        """Build compact index markdown for multiple models (aligned with Java buildMultiModelMarkdown).

        Parameters
        ----------
        visible_set
            v1.2 governance: only include fields whose name is in this set.
            ``None`` means no filtering.
        """
        lines: List[str] = []

        def _visible(field_name: str) -> bool:
            return visible_set is None or field_name in visible_set

        lines.append("# Semantic Model Index V3")
        lines.append("")

        # Model index
        lines.append("## Model Index")
        for model_name, model in models:
            alias = model.alias or model_name
            desc = model.description or ""
            lines.append(f"- **{alias}**({model_name}): {desc}")
        lines.append("")

        # Field index
        lines.append("## Field Index")
        lines.append("")
        lines.append("> Use the indented `fieldName` values in queries, not the business labels in section titles.")
        lines.append("")

        for model_name, model in models:
            alias = model.alias or model_name
            lines.append(f"### {alias}")
            lines.append("")

            # Dimension JOINs
            if model.dimension_joins:
                dim_lines: List[str] = []
                for jd in model.dimension_joins:
                    dc = jd.caption or jd.name
                    dim_obj = model.dimensions.get(jd.name)
                    is_hier = dim_obj is not None and dim_obj.supports_hierarchy_operators()
                    hier_hint = " 🔗 hierarchical" if is_hier else ""
                    sub_lines: List[str] = []
                    id_field = f"{jd.name}$id"
                    if _visible(id_field):
                        id_ops = " *(supports selfAndDescendantsOf / selfAndAncestorsOf)*" if is_hier else ""
                        sub_lines.append(f"    - [field:{id_field}] | ID, used for query/filtering{id_ops}")
                    cap_field = f"{jd.name}$caption"
                    if _visible(cap_field):
                        sub_lines.append(f"    - [field:{cap_field}] | Caption, used for display")
                    for prop in jd.properties:
                        pn = prop.get_name()
                        prop_field = f"{jd.name}${pn}"
                        if _visible(prop_field):
                            sub_lines.append(f"    - [field:{prop_field}] | {prop.caption or pn}")
                    if sub_lines:
                        dim_lines.append(f"- {dc}{hier_hint}")
                        dim_lines.extend(sub_lines)
                if dim_lines:
                    lines.append("**Dimensions**")
                    lines.extend(dim_lines)

            # Fact table properties (use model.columns, NOT model.dimensions)
            if model.columns:
                prop_lines: List[str] = []
                for col_name, col in model.columns.items():
                    if not _visible(col_name):
                        continue
                    col_caption = col.alias or col_name
                    col_type = self._get_column_type_description(col.column_type)
                    prop_lines.append(f"- {col_caption}")
                    prop_lines.append(f"    - [field:{col_name}] | {col_type}")
                if prop_lines:
                    lines.append("")
                    lines.append("**Attributes**")
                    lines.extend(prop_lines)

            # Measures
            if model.measures:
                measure_lines: List[str] = []
                for m_name, measure in model.measures.items():
                    if not _visible(m_name):
                        continue
                    m_alias = measure.alias or m_name
                    agg = measure.aggregation.value.upper() if measure.aggregation else "SUM"
                    measure_lines.append(f"- {m_alias}")
                    measure_lines.append(f"    - [field:{m_name}] | {agg}")
                if measure_lines:
                    lines.append("")
                    lines.append("**Measures**")
                    lines.extend(measure_lines)

            lines.append("")

        # Usage
        lines.append("## Usage Tips")
        lines.append("- Use `xxx$id` for query/filtering and `xxx$caption` for display")
        lines.append("- Measures support inline aggregation: `sum(fieldName) as alias`")
        lines.append("- The system handles groupBy automatically in most cases")

        return "\n".join(lines)

    # ==================== Caching ====================

    def _get_cache_key(self, model: str, request: SemanticQueryRequest) -> str:
        """Generate cache key for a query."""
        import hashlib
        import json

        key_data = {
            "model": model,
            "columns": sorted(request.columns),
            "slice": request.slice,
            "group_by": sorted(request.group_by) if request.group_by else [],
            "order_by": request.order_by,
            "limit": request.limit,
            "start": request.start,
        }

        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()


__all__ = [
    "SemanticQueryService",
    "QueryBuildResult",
]
