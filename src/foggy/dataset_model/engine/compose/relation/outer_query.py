"""Runtime compiler for outer queries over ``CompiledRelation``.

This module closes the Python runtime gap for the Java S7e/S7f stable
relation contract.  It is intentionally internal: callers provide a
pre-authorized ``CompiledRelation`` and receive SQL plus output schema.
No public DSL shape is added here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple

from foggy.dataset_model.engine.compose import ComposedSql
from foggy.dataset_model.engine.compose.compilation import error_codes
from foggy.dataset_model.engine.compose.compilation.errors import (
    ComposeCompileError,
)
from foggy.dataset_model.engine.compose.relation.constants import (
    ReferencePolicy,
    SemanticKind,
)
from foggy.dataset_model.engine.compose.relation.models import (
    CompiledRelation,
)
from foggy.dataset_model.engine.compose.schema.output_schema import (
    ColumnSpec,
    OutputSchema,
)


_SAFE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_AGG_FUNCS = frozenset({"SUM", "AVG", "MIN", "MAX", "COUNT"})
_WINDOW_FUNCS = frozenset({
    "ROW_NUMBER",
    "RANK",
    "DENSE_RANK",
    "AVG",
    "SUM",
    "MIN",
    "MAX",
    "COUNT",
    "LAG",
    "LEAD",
})


@dataclass(frozen=True)
class RelationOuterQuery:
    """Compiled SQL, params and schema for an outer relation query."""

    sql: str
    params: Tuple[Any, ...]
    output_schema: OutputSchema

    def as_composed_sql(self) -> ComposedSql:
        return ComposedSql(sql=self.sql, params=list(self.params))


@dataclass(frozen=True)
class OuterAggregateSpec:
    source: str
    func: str
    alias: str


@dataclass(frozen=True)
class OrderSpec:
    column: str
    direction: str = "ASC"


@dataclass(frozen=True)
class OuterWindowSpec:
    func: str
    alias: str
    input: Optional[str] = None
    partition_by: Tuple[str, ...] = ()
    order_by: Tuple[OrderSpec, ...] = ()
    frame: Optional[str] = None
    offset: Optional[int] = None


def compile_outer_aggregate(
    relation: CompiledRelation,
    *,
    group_by: Sequence[str],
    aggregates: Sequence[OuterAggregateSpec],
) -> RelationOuterQuery:
    """Compile S7e outer aggregate over a stable relation.

    Only columns marked ``groupable`` may appear in ``group_by``.  Only
    columns marked ``aggregatable`` may be aggregate inputs.
    """
    if not relation.capabilities.supports_outer_aggregate:
        _raise(
            error_codes.RELATION_OUTER_AGGREGATE_NOT_SUPPORTED,
            "Relation does not support outer aggregate for this dialect/wrap shape",
        )
    if not aggregates:
        _raise(
            error_codes.UNSUPPORTED_PLAN_SHAPE,
            "Outer aggregate requires at least one aggregate spec",
        )

    source = _render_relation_source(relation)
    select_parts: List[str] = []
    out_cols: List[ColumnSpec] = []

    for name in group_by:
        col = _require_column(relation, name)
        _require_policy(col, ReferencePolicy.GROUPABLE, error_codes.RELATION_COLUMN_NOT_READABLE)
        select_parts.append(_col_sql(name))
        out_cols.append(col)

    for spec in aggregates:
        func = spec.func.upper()
        if func not in _AGG_FUNCS:
            _raise(error_codes.UNSUPPORTED_PLAN_SHAPE, f"Unsupported aggregate function {spec.func!r}")
        col = _require_column(relation, spec.source)
        _require_policy(col, ReferencePolicy.AGGREGATABLE, error_codes.RELATION_COLUMN_NOT_AGGREGATABLE)
        alias = _ident(spec.alias)
        select_parts.append(f"{func}({_col_sql(spec.source)}) AS {alias}")
        out_cols.append(_aggregate_output_column(spec, col))

    parts = _with_prefix(source)
    parts.append("SELECT " + ", ".join(select_parts))
    parts.append(source.from_sql)
    if group_by:
        parts.append("GROUP BY " + ", ".join(_col_sql(name) for name in group_by))
    return RelationOuterQuery(
        sql="\n".join(parts),
        params=source.params,
        output_schema=OutputSchema.of(out_cols),
    )


def compile_outer_window(
    relation: CompiledRelation,
    *,
    select: Sequence[str],
    windows: Sequence[OuterWindowSpec],
) -> RelationOuterQuery:
    """Compile S7f outer window over a stable relation."""
    if not relation.capabilities.supports_outer_window:
        _raise(
            error_codes.RELATION_OUTER_WINDOW_NOT_SUPPORTED,
            "Relation does not support outer window for this dialect/wrap shape",
        )
    if not windows:
        _raise(
            error_codes.UNSUPPORTED_PLAN_SHAPE,
            "Outer window requires at least one window spec",
        )

    source = _render_relation_source(relation)
    select_parts: List[str] = []
    out_cols: List[ColumnSpec] = []

    for name in select:
        col = _require_column(relation, name)
        _require_policy(col, ReferencePolicy.READABLE, error_codes.RELATION_COLUMN_NOT_READABLE)
        select_parts.append(_col_sql(name))
        out_cols.append(col)

    for spec in windows:
        select_parts.append(_window_sql(relation, spec))
        out_cols.append(_window_output_column(relation, spec))

    parts = _with_prefix(source)
    parts.append("SELECT " + ", ".join(select_parts))
    parts.append(source.from_sql)
    return RelationOuterQuery(
        sql="\n".join(parts),
        params=source.params,
        output_schema=OutputSchema.of(out_cols),
    )


@dataclass(frozen=True)
class _RenderedRelationSource:
    with_sql: Optional[str]
    from_sql: str
    params: Tuple[Any, ...]


def _render_relation_source(relation: CompiledRelation) -> _RenderedRelationSource:
    alias = _ident(relation.alias or relation.relation_sql.preferred_alias)
    rsql = relation.relation_sql
    caps = relation.capabilities

    if not rsql.with_items:
        if not caps.can_inline_as_subquery:
            _raise(
                error_codes.RELATION_WRAP_UNSUPPORTED,
                "Relation cannot be inlined as a subquery for this dialect",
            )
        return _RenderedRelationSource(
            with_sql=None,
            from_sql=f"FROM ({rsql.body_sql}) AS {alias}",
            params=tuple(rsql.body_params),
        )

    if not caps.can_hoist_cte:
        _raise(
            error_codes.RELATION_OUTER_AGGREGATE_NOT_SUPPORTED
            if not caps.supports_outer_aggregate
            else error_codes.RELATION_CTE_HOIST_UNSUPPORTED,
            "Relation contains CTE items that cannot be hoisted for this dialect",
        )

    cte_parts = []
    params: List[Any] = []
    for item in rsql.with_items:
        cte_parts.append(f"{_ident(item.name)} AS ({item.sql})")
        params.extend(item.params)
    cte_parts.append(f"{alias} AS ({rsql.body_sql})")
    params.extend(rsql.body_params)
    with_keyword = ";WITH" if caps.requires_top_level_with else "WITH"
    return _RenderedRelationSource(
        with_sql=with_keyword + " " + ",\n".join(cte_parts),
        from_sql=f"FROM {alias}",
        params=tuple(params),
    )


def _with_prefix(source: _RenderedRelationSource) -> List[str]:
    return [source.with_sql] if source.with_sql else []


def _window_sql(relation: CompiledRelation, spec: OuterWindowSpec) -> str:
    func = spec.func.upper()
    if func not in _WINDOW_FUNCS:
        _raise(error_codes.UNSUPPORTED_PLAN_SHAPE, f"Unsupported window function {spec.func!r}")
    alias = _ident(spec.alias)

    args = _window_args(relation, spec, func)
    over_parts: List[str] = []
    if spec.partition_by:
        partition_cols = []
        for name in spec.partition_by:
            col = _require_column(relation, name)
            _require_policy(col, ReferencePolicy.GROUPABLE, error_codes.RELATION_COLUMN_NOT_READABLE)
            partition_cols.append(_col_sql(name))
        over_parts.append("PARTITION BY " + ", ".join(partition_cols))
    if spec.order_by:
        order_cols = []
        for order in spec.order_by:
            col = _require_column(relation, order.column)
            _require_policy(col, ReferencePolicy.ORDERABLE, error_codes.RELATION_COLUMN_NOT_ORDERABLE)
            direction = order.direction.upper()
            if direction not in ("ASC", "DESC"):
                _raise(error_codes.UNSUPPORTED_PLAN_SHAPE, f"Unsupported order direction {order.direction!r}")
            order_cols.append(f"{_col_sql(order.column)} {direction}")
        over_parts.append("ORDER BY " + ", ".join(order_cols))
    if spec.frame:
        # First pass keeps the Java snapshot contract: caller supplies a
        # restricted SQL frame string; this compiler refuses statement breaks.
        if ";" in spec.frame:
            _raise(error_codes.UNSUPPORTED_PLAN_SHAPE, "Window frame must not contain ';'")
        over_parts.append(spec.frame)

    return f"{func}({args}) OVER ({' '.join(over_parts)}) AS {alias}"


def _window_args(relation: CompiledRelation, spec: OuterWindowSpec, func: str) -> str:
    if func in ("ROW_NUMBER", "RANK", "DENSE_RANK"):
        if spec.input is not None:
            _raise(error_codes.UNSUPPORTED_PLAN_SHAPE, f"{func} does not accept input column")
        return ""
    if spec.input is None:
        _raise(error_codes.UNSUPPORTED_PLAN_SHAPE, f"{func} requires input column")
    col = _require_column(relation, spec.input)
    _require_policy(col, ReferencePolicy.WINDOWABLE, error_codes.RELATION_COLUMN_NOT_WINDOWABLE)
    args = [_col_sql(spec.input)]
    if func in ("LAG", "LEAD") and spec.offset is not None:
        if spec.offset < 0:
            _raise(error_codes.UNSUPPORTED_PLAN_SHAPE, "Window offset must be non-negative")
        args.append(str(int(spec.offset)))
    return ", ".join(args)


def _require_column(relation: CompiledRelation, name: str) -> ColumnSpec:
    col = relation.output_schema.get(name)
    if col is None:
        _raise(error_codes.RELATION_COLUMN_NOT_FOUND, f"Relation column {name!r} not found")
    return col


def _require_policy(col: ColumnSpec, policy: str, code: str) -> None:
    policies = col.reference_policy or frozenset()
    if policy not in policies:
        _raise(code, f"Relation column {col.name!r} lacks reference policy {policy!r}")


def _aggregate_output_column(spec: OuterAggregateSpec, source_col: ColumnSpec) -> ColumnSpec:
    lineage = set(source_col.lineage or frozenset())
    lineage.add(spec.source)
    return ColumnSpec(
        name=spec.alias,
        expression=f"{spec.func.upper()}({spec.source}) AS {spec.alias}",
        semantic_kind=SemanticKind.AGGREGATE_MEASURE,
        value_meaning=f"{spec.func.upper()} of {spec.source}",
        lineage=frozenset(lineage),
        reference_policy=ReferencePolicy.MEASURE_DEFAULT,
    )


def _window_output_column(relation: CompiledRelation, spec: OuterWindowSpec) -> ColumnSpec:
    lineage = set()
    if spec.input is not None:
        input_col = _require_column(relation, spec.input)
        lineage.update(input_col.lineage or frozenset())
        lineage.add(spec.input)
    for name in spec.partition_by:
        lineage.add(name)
    for order in spec.order_by:
        lineage.add(order.column)
    return ColumnSpec(
        name=spec.alias,
        expression=f"{spec.func.upper()}(...) OVER (...) AS {spec.alias}",
        semantic_kind=SemanticKind.WINDOW_CALC,
        value_meaning=_window_value_meaning(spec),
        lineage=frozenset(lineage),
        reference_policy=frozenset({ReferencePolicy.READABLE, ReferencePolicy.ORDERABLE}),
    )


def _window_value_meaning(spec: OuterWindowSpec) -> str:
    if spec.order_by:
        order = ", ".join(f"{o.column} {o.direction.upper()}" for o in spec.order_by)
        return f"{spec.func.upper().lower()} ordered by {order}"
    return f"{spec.func.upper().lower()} window calculation"


def _col_sql(name: str) -> str:
    return _ident(name)


def _ident(name: str) -> str:
    if not _SAFE_IDENT.match(name or ""):
        _raise(error_codes.UNSUPPORTED_PLAN_SHAPE, f"Unsafe SQL identifier {name!r}")
    return name


def _raise(code: str, message: str) -> None:
    raise ComposeCompileError(code=code, phase="relation-compile", message=message)
