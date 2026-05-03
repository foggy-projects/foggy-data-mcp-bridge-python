"""Real DB oracle parity for stable relation outer queries.

This verifies the v1.12 internal ``CompiledRelation`` outer aggregate/window
runtime against handwritten SQL on SQLite, MySQL8, and PostgreSQL.  It does
not add or exercise a public DSL path.
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from typing import Any, Iterable

import pytest

from foggy.dataset.db.executor import (
    DatabaseExecutor,
    MySQLExecutor,
    PostgreSQLExecutor,
    SQLiteExecutor,
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
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model


MYSQL8_CONFIG = {
    "host": "localhost",
    "port": 13308,
    "database": "foggy_test",
    "user": "foggy",
    "password": "foggy_test_123",
}

POSTGRES_CONFIG = {
    "host": "localhost",
    "port": 15432,
    "database": "foggy_test",
    "user": "foggy",
    "password": "foggy_test_123",
}

RELATION_BODY_SQL = """
    SELECT
        p.category_name AS categoryName,
        d.date_key AS salesDateId,
        SUM(f.sales_amount) AS salesAmount,
        SUM(f.sales_amount) / 100.0 AS salesAmountRatio
    FROM fact_sales f
    LEFT JOIN dim_product p ON f.product_key = p.product_key
    LEFT JOIN dim_date d ON f.date_key = d.date_key
    WHERE f.sales_amount IS NOT NULL
      AND d.date_key IS NOT NULL
    GROUP BY p.category_name, d.date_key
"""

RELATION_BODY_SQL_FROM_BASE = """
    SELECT
        p.category_name AS categoryName,
        d.date_key AS salesDateId,
        SUM(f.sales_amount) AS salesAmount,
        SUM(f.sales_amount) / 100.0 AS salesAmountRatio
    FROM base_sales f
    LEFT JOIN dim_product p ON f.product_key = p.product_key
    LEFT JOIN dim_date d ON f.date_key = d.date_key
    WHERE d.date_key IS NOT NULL
    GROUP BY p.category_name, d.date_key
"""


def _service(executor: DatabaseExecutor) -> SemanticQueryService:
    service = SemanticQueryService(executor=executor, enable_cache=False)
    service.register_model(create_fact_sales_model())
    return service


def _close(service: SemanticQueryService, executor: DatabaseExecutor) -> None:
    service._run_async_in_sync(executor.close())


def _execute(
    service: SemanticQueryService,
    sql: str,
    params: Iterable[Any] | None = None,
) -> list[dict[str, Any]]:
    result = service._run_async_in_sync(service._executor.execute(sql, params=list(params or ())))
    assert result.error is None, result.error
    return result.rows


def _probe_or_skip(service: SemanticQueryService) -> None:
    _execute(service, "SELECT 1 AS ok")
    rows = _execute(service, "SELECT COUNT(*) AS cnt FROM fact_sales")
    if not rows or int(rows[0]["cnt"]) == 0:
        pytest.skip("demo database has no fact_sales seed rows")
    _execute(service, "SELECT COUNT(*) AS cnt FROM dim_product")
    _execute(service, "SELECT COUNT(*) AS cnt FROM dim_date")


@pytest.fixture(params=["sqlite", "mysql8", "postgres"])
def real_db_service(request, tmp_path):
    if request.param == "sqlite":
        db_path = str(tmp_path / "stable_relation_outer.sqlite")
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE dim_product (
                product_key INTEGER PRIMARY KEY,
                category_name TEXT
            );
            CREATE TABLE dim_date (
                date_key INTEGER PRIMARY KEY,
                year INTEGER,
                month INTEGER
            );
            CREATE TABLE fact_sales (
                product_key INTEGER,
                date_key INTEGER,
                sales_amount REAL
            );

            INSERT INTO dim_product VALUES (1, 'Electronics');
            INSERT INTO dim_product VALUES (2, 'Clothing');
            INSERT INTO dim_product VALUES (3, 'Food');

            INSERT INTO dim_date VALUES (20240101, 2024, 1);
            INSERT INTO dim_date VALUES (20240102, 2024, 1);
            INSERT INTO dim_date VALUES (20240201, 2024, 2);
            INSERT INTO dim_date VALUES (20240202, 2024, 2);

            INSERT INTO fact_sales VALUES (1, 20240101, 10.0);
            INSERT INTO fact_sales VALUES (1, 20240102, 20.0);
            INSERT INTO fact_sales VALUES (1, 20240201, 30.0);
            INSERT INTO fact_sales VALUES (2, 20240101, 5.0);
            INSERT INTO fact_sales VALUES (2, 20240201, 15.0);
            INSERT INTO fact_sales VALUES (3, 20240202, 40.0);
        """)
        conn.close()
        executor = SQLiteExecutor(db_path)
    elif request.param == "mysql8":
        executor = MySQLExecutor(**MYSQL8_CONFIG)
    else:
        executor = PostgreSQLExecutor(**POSTGRES_CONFIG)

    service = _service(executor)
    if request.param != "sqlite":
        try:
            _probe_or_skip(service)
        except Exception as exc:
            pytest.skip(f"demo database unavailable: {exc}")

    yield request.param, service
    _close(service, executor)


def _schema() -> OutputSchema:
    return OutputSchema.of([
        ColumnSpec(
            name="categoryName",
            expression="categoryName",
            semantic_kind=SemanticKind.BASE_FIELD,
            reference_policy=ReferencePolicy.DIMENSION_DEFAULT,
        ),
        ColumnSpec(
            name="salesDateId",
            expression="salesDateId",
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
            name="salesAmountRatio",
            expression="salesAmountRatio",
            semantic_kind=SemanticKind.TIME_WINDOW_DERIVED,
            lineage=frozenset({"salesAmount"}),
            reference_policy=ReferencePolicy.TIME_WINDOW_DERIVED_DEFAULT,
        ),
    ])


def _relation(
    dialect: str,
    *,
    with_items: tuple[CteItem, ...] = (),
    body_sql: str = RELATION_BODY_SQL,
    body_params: tuple[object, ...] = (),
) -> CompiledRelation:
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


def _num(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _quant(value: Any) -> Decimal:
    return _num(value).quantize(Decimal("0.000001"))


def _value(row: dict[str, Any], name: str) -> Any:
    if name in row:
        return row[name]
    lower = name.lower()
    for key, value in row.items():
        if str(key).lower() == lower:
            return value
    return None


def _norm_aggregate(rows: Iterable[dict[str, Any]]) -> list[tuple[str | None, Decimal]]:
    result = []
    for row in rows:
        result.append((_value(row, "categoryName"), _quant(_value(row, "totalSales"))))
    return sorted(result, key=lambda item: (item[0] is None, str(item[0])))


def _norm_rank(rows: Iterable[dict[str, Any]]) -> list[tuple[str | None, int, Decimal, int]]:
    result = []
    for row in rows:
        result.append((
            _value(row, "categoryName"),
            int(_value(row, "salesDateId")),
            _quant(_value(row, "salesAmountRatio")),
            int(_value(row, "growthRank")),
        ))
    return sorted(result, key=lambda item: (item[2] * Decimal("-1"), item[0] or "", item[1]))


def _norm_moving_avg(rows: Iterable[dict[str, Any]]) -> list[tuple[str | None, int, Decimal, Decimal]]:
    result = []
    for row in rows:
        result.append((
            _value(row, "categoryName"),
            int(_value(row, "salesDateId")),
            _quant(_value(row, "salesAmount")),
            _quant(_value(row, "salesMovingAvg")),
        ))
    return sorted(result, key=lambda item: (item[0] is None, item[0] or "", item[1]))


def test_outer_aggregate_groupby_oracle(real_db_service):
    dialect, service = real_db_service
    compiled = compile_outer_aggregate(
        _relation(dialect),
        group_by=["categoryName"],
        aggregates=[OuterAggregateSpec(source="salesAmount", func="SUM", alias="totalSales")],
    )

    oracle_sql = """
        SELECT p.category_name AS categoryName, SUM(f.sales_amount) AS totalSales
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        LEFT JOIN dim_date d ON f.date_key = d.date_key
        WHERE f.sales_amount IS NOT NULL
          AND d.date_key IS NOT NULL
        GROUP BY p.category_name
    """

    assert _norm_aggregate(_execute(service, compiled.sql, compiled.params)) == _norm_aggregate(
        _execute(service, oracle_sql)
    )


def test_outer_aggregate_cte_hoist_oracle(real_db_service):
    dialect, service = real_db_service
    relation = _relation(
        dialect,
        with_items=(
            CteItem(
                name="base_sales",
                sql="SELECT * FROM fact_sales WHERE sales_amount >= ?",
                params=(0,),
            ),
        ),
        body_sql=RELATION_BODY_SQL_FROM_BASE,
    )
    compiled = compile_outer_aggregate(
        relation,
        group_by=["categoryName"],
        aggregates=[OuterAggregateSpec(source="salesAmount", func="SUM", alias="totalSales")],
    )

    oracle_sql = """
        WITH base_sales AS (SELECT * FROM fact_sales WHERE sales_amount >= ?)
        SELECT p.category_name AS categoryName, SUM(f.sales_amount) AS totalSales
        FROM base_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        LEFT JOIN dim_date d ON f.date_key = d.date_key
        WHERE f.sales_amount IS NOT NULL
          AND d.date_key IS NOT NULL
        GROUP BY p.category_name
    """

    assert compiled.sql.lstrip().upper().startswith("WITH ")
    assert compiled.params == (0,)
    assert _norm_aggregate(_execute(service, compiled.sql, compiled.params)) == _norm_aggregate(
        _execute(service, oracle_sql, compiled.params)
    )


def test_outer_window_rank_oracle(real_db_service):
    dialect, service = real_db_service
    compiled = compile_outer_window(
        _relation(dialect),
        select=["categoryName", "salesDateId", "salesAmountRatio"],
        windows=[
            OuterWindowSpec(
                func="RANK",
                alias="growthRank",
                order_by=(OrderSpec("salesAmountRatio", "DESC"),),
            )
        ],
    )

    oracle_sql = f"""
        WITH rel_0 AS ({RELATION_BODY_SQL})
        SELECT
            categoryName,
            salesDateId,
            salesAmountRatio,
            RANK() OVER (ORDER BY salesAmountRatio DESC) AS growthRank
        FROM rel_0
    """

    assert _norm_rank(_execute(service, compiled.sql, compiled.params)) == _norm_rank(
        _execute(service, oracle_sql)
    )


def test_outer_window_moving_avg_oracle(real_db_service):
    dialect, service = real_db_service
    compiled = compile_outer_window(
        _relation(dialect),
        select=["categoryName", "salesDateId", "salesAmount"],
        windows=[
            OuterWindowSpec(
                func="AVG",
                input="salesAmount",
                alias="salesMovingAvg",
                partition_by=("categoryName",),
                order_by=(OrderSpec("salesDateId", "ASC"),),
                frame="ROWS BETWEEN 1 PRECEDING AND CURRENT ROW",
            )
        ],
    )

    oracle_sql = f"""
        WITH rel_0 AS ({RELATION_BODY_SQL})
        SELECT
            categoryName,
            salesDateId,
            salesAmount,
            AVG(salesAmount) OVER (
                PARTITION BY categoryName
                ORDER BY salesDateId ASC
                ROWS BETWEEN 1 PRECEDING AND CURRENT ROW
            ) AS salesMovingAvg
        FROM rel_0
    """

    assert _norm_moving_avg(_execute(service, compiled.sql, compiled.params)) == _norm_moving_avg(
        _execute(service, oracle_sql)
    )
