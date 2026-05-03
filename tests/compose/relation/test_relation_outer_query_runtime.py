"""Runtime tests for S7e/S7f outer queries over ``CompiledRelation``."""

from __future__ import annotations

import sqlite3

import pytest

from foggy.dataset_model.engine.compose.compilation import error_codes
from foggy.dataset_model.engine.compose.compilation.errors import (
    ComposeCompileError,
)
from foggy.dataset_model.engine.compose.relation import (
    CompiledRelation,
    CteItem,
    OrderSpec,
    OuterAggregateSpec,
    OuterWindowSpec,
    RelationCapabilities,
    RelationSql,
    compile_outer_aggregate,
    compile_outer_window,
)
from foggy.dataset_model.engine.compose.relation.constants import (
    ReferencePolicy,
    RelationPermissionState,
    SemanticKind,
)
from foggy.dataset_model.engine.compose.schema.output_schema import (
    ColumnSpec,
    OutputSchema,
)


def _schema() -> OutputSchema:
    return OutputSchema.of([
        ColumnSpec(
            name="storeName",
            expression="storeName",
            semantic_kind=SemanticKind.BASE_FIELD,
            reference_policy=ReferencePolicy.DIMENSION_DEFAULT,
        ),
        ColumnSpec(
            name="salesDate",
            expression="salesDate",
            semantic_kind=SemanticKind.BASE_FIELD,
            reference_policy=ReferencePolicy.DIMENSION_DEFAULT,
        ),
        ColumnSpec(
            name="salesAmount",
            expression="salesAmount",
            semantic_kind=SemanticKind.AGGREGATE_MEASURE,
            lineage=frozenset({"salesAmount"}),
            reference_policy=ReferencePolicy.MEASURE_DEFAULT,
        ),
        ColumnSpec(
            name="salesAmount__ratio",
            expression="salesAmount__ratio",
            semantic_kind=SemanticKind.TIME_WINDOW_DERIVED,
            lineage=frozenset({"salesAmount"}),
            reference_policy=ReferencePolicy.TIME_WINDOW_DERIVED_DEFAULT,
        ),
    ])


def _relation(
    dialect: str = "sqlite",
    *,
    with_items: tuple[CteItem, ...] = (),
    body_sql: str | None = None,
    body_params: tuple[object, ...] = (),
) -> CompiledRelation:
    if body_sql is None:
        body_sql = (
            "SELECT store_name AS storeName, sales_date AS salesDate, "
            "sales_amount AS salesAmount, ratio AS salesAmount__ratio "
            "FROM sales WHERE region = ?"
        )
        body_params = ("north",)
    return CompiledRelation(
        alias="rel_0",
        relation_sql=RelationSql(
            body_sql=body_sql,
            preferred_alias="rel_0",
            with_items=with_items,
            body_params=body_params,
        ),
        output_schema=_schema(),
        dialect=dialect,
        capabilities=RelationCapabilities.for_dialect(dialect, bool(with_items)),
        permission_state=RelationPermissionState.AUTHORIZED,
    )


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE sales ("
        "store_name TEXT, sales_date TEXT, sales_amount REAL, ratio REAL, region TEXT)"
    )
    conn.executemany(
        "INSERT INTO sales VALUES (?, ?, ?, ?, ?)",
        [
            ("A", "2024-01-01", 10.0, 0.10, "north"),
            ("A", "2024-01-02", 20.0, 0.20, "north"),
            ("B", "2024-01-01", 5.0, 0.50, "north"),
            ("B", "2024-01-02", 7.0, 0.70, "north"),
            ("C", "2024-01-01", 100.0, 0.90, "south"),
        ],
    )
    return conn


def _rows(conn: sqlite3.Connection, sql: str, params: tuple[object, ...]):
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _err_code(exc: pytest.ExceptionInfo[ComposeCompileError]) -> str:
    return exc.value.code


def test_outer_aggregate_executes_sqlite_oracle():
    compiled = compile_outer_aggregate(
        _relation(),
        group_by=["storeName"],
        aggregates=[OuterAggregateSpec(source="salesAmount", func="SUM", alias="totalSales")],
    )

    rows = _rows(_conn(), compiled.sql, compiled.params)
    oracle = [
        {"storeName": "A", "totalSales": 30.0},
        {"storeName": "B", "totalSales": 12.0},
    ]

    assert rows == oracle
    assert compiled.params == ("north",)
    by_name = {c.name: c for c in compiled.output_schema}
    assert by_name["totalSales"].semantic_kind == SemanticKind.AGGREGATE_MEASURE
    assert ReferencePolicy.AGGREGATABLE in by_name["totalSales"].reference_policy


def test_outer_aggregate_hoists_cte_and_preserves_param_order():
    relation = _relation(
        with_items=(
            CteItem(
                name="base_sales",
                sql="SELECT * FROM sales WHERE region = ?",
                params=("north",),
            ),
        ),
        body_sql=(
            "SELECT store_name AS storeName, sales_date AS salesDate, "
            "sales_amount AS salesAmount, ratio AS salesAmount__ratio "
            "FROM base_sales WHERE store_name != ?"
        ),
        body_params=("B",),
    )

    compiled = compile_outer_aggregate(
        relation,
        group_by=["storeName"],
        aggregates=[OuterAggregateSpec(source="salesAmount", func="SUM", alias="totalSales")],
    )

    assert compiled.sql.startswith("WITH base_sales AS")
    assert "rel_0 AS (" in compiled.sql
    assert "FROM (WITH" not in compiled.sql.upper()
    assert compiled.params == ("north", "B")
    assert _rows(_conn(), compiled.sql, compiled.params) == [
        {"storeName": "A", "totalSales": 30.0},
    ]


def test_outer_aggregate_rejects_non_aggregatable_ratio():
    with pytest.raises(ComposeCompileError) as exc:
        compile_outer_aggregate(
            _relation(),
            group_by=["storeName"],
            aggregates=[
                OuterAggregateSpec(
                    source="salesAmount__ratio",
                    func="SUM",
                    alias="badTotal",
                )
            ],
        )
    assert _err_code(exc) == error_codes.RELATION_COLUMN_NOT_AGGREGATABLE


def test_outer_aggregate_rejects_mysql57_cte_relation():
    with pytest.raises(ComposeCompileError) as exc:
        compile_outer_aggregate(
            _relation(
                "mysql",
                with_items=(CteItem(name="base_sales", sql="SELECT * FROM sales"),),
                body_sql="SELECT * FROM base_sales",
            ),
            group_by=["storeName"],
            aggregates=[OuterAggregateSpec(source="salesAmount", func="SUM", alias="totalSales")],
        )
    assert _err_code(exc) == error_codes.RELATION_OUTER_AGGREGATE_NOT_SUPPORTED


def test_outer_window_rank_executes_sqlite_oracle_with_ratio_order_key():
    compiled = compile_outer_window(
        _relation(),
        select=["storeName", "salesAmount__ratio"],
        windows=[
            OuterWindowSpec(
                func="RANK",
                alias="growthRank",
                order_by=(OrderSpec("salesAmount__ratio", "DESC"),),
            )
        ],
    )

    rows = _rows(_conn(), compiled.sql, compiled.params)
    assert rows == [
        {"storeName": "B", "salesAmount__ratio": 0.7, "growthRank": 1},
        {"storeName": "B", "salesAmount__ratio": 0.5, "growthRank": 2},
        {"storeName": "A", "salesAmount__ratio": 0.2, "growthRank": 3},
        {"storeName": "A", "salesAmount__ratio": 0.1, "growthRank": 4},
    ]
    by_name = {c.name: c for c in compiled.output_schema}
    assert by_name["growthRank"].semantic_kind == SemanticKind.WINDOW_CALC
    assert ReferencePolicy.ORDERABLE in by_name["growthRank"].reference_policy


def test_outer_window_moving_avg_executes_sqlite_oracle():
    compiled = compile_outer_window(
        _relation(),
        select=["storeName", "salesDate", "salesAmount"],
        windows=[
            OuterWindowSpec(
                func="AVG",
                input="salesAmount",
                alias="salesMovingAvg",
                partition_by=("storeName",),
                order_by=(OrderSpec("salesDate", "ASC"),),
                frame="ROWS BETWEEN 1 PRECEDING AND CURRENT ROW",
            )
        ],
    )

    rows = _rows(_conn(), compiled.sql, compiled.params)
    assert rows == [
        {
            "storeName": "A",
            "salesDate": "2024-01-01",
            "salesAmount": 10.0,
            "salesMovingAvg": 10.0,
        },
        {
            "storeName": "A",
            "salesDate": "2024-01-02",
            "salesAmount": 20.0,
            "salesMovingAvg": 15.0,
        },
        {
            "storeName": "B",
            "salesDate": "2024-01-01",
            "salesAmount": 5.0,
            "salesMovingAvg": 5.0,
        },
        {
            "storeName": "B",
            "salesDate": "2024-01-02",
            "salesAmount": 7.0,
            "salesMovingAvg": 6.0,
        },
    ]


def test_outer_window_rejects_ratio_as_window_input():
    with pytest.raises(ComposeCompileError) as exc:
        compile_outer_window(
            _relation(),
            select=["storeName"],
            windows=[
                OuterWindowSpec(
                    func="AVG",
                    input="salesAmount__ratio",
                    alias="badAvg",
                    order_by=(OrderSpec("storeName"),),
                )
            ],
        )
    assert _err_code(exc) == error_codes.RELATION_COLUMN_NOT_WINDOWABLE


def test_outer_window_rejects_mysql57_even_without_cte():
    with pytest.raises(ComposeCompileError) as exc:
        compile_outer_window(
            _relation("mysql"),
            select=["storeName"],
            windows=[
                OuterWindowSpec(
                    func="RANK",
                    alias="rankNo",
                    order_by=(OrderSpec("salesAmount", "DESC"),),
                )
            ],
        )
    assert _err_code(exc) == error_codes.RELATION_OUTER_WINDOW_NOT_SUPPORTED


def test_outer_window_sqlserver_hoists_cte_without_from_with_marker():
    relation = _relation(
        "sqlserver",
        with_items=(CteItem(name="base_sales", sql="SELECT * FROM sales WHERE region = ?", params=("north",)),),
        body_sql=(
            "SELECT store_name AS storeName, sales_date AS salesDate, "
            "sales_amount AS salesAmount, ratio AS salesAmount__ratio FROM base_sales"
        ),
    )

    compiled = compile_outer_window(
        relation,
        select=["storeName"],
        windows=[
            OuterWindowSpec(
                func="RANK",
                alias="growthRank",
                order_by=(OrderSpec("salesAmount", "DESC"),),
            )
        ],
    )

    assert compiled.sql.startswith(";WITH")
    assert "FROM (WITH" not in compiled.sql.upper()
    assert compiled.params == ("north",)

