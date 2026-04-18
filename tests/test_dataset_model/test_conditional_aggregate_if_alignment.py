"""Java-aligned conditional aggregate IF lowering regression tests.

Validates that Python supports ``sum/avg/count(if(...))`` without exposing
raw CASE WHEN DSL, and lowers to standard SQL with real DB reconciliation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple

import pytest

from foggy.dataset.db.executor import MySQLExecutor, PostgreSQLExecutor, SQLiteExecutor
from foggy.dataset.dialects.mysql import MySqlDialect
from foggy.dataset.dialects.postgres import PostgresDialect
from foggy.dataset.dialects.sqlite import SqliteDialect
from foggy.dataset_model.semantic import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest
from foggy.mcp_spi.semantic import DeniedColumn, FieldAccessDef


MYSQL_CONFIG = {
    "host": "localhost",
    "port": 13306,
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

SQLITE_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "conditional_aggregate_if_alignment.sqlite3"

GROUP_FIELD = "orderStatus"
GROUP_ALIAS = "订单状态"


def _normalize_row(row: Dict[str, object], metric_alias: str) -> Tuple[str, object]:
    return row[GROUP_ALIAS], row[metric_alias]


def _normalize_rows(rows: Iterable[Dict[str, object]], metric_alias: str) -> Dict[str, object]:
    normalized: Dict[str, object] = {}
    for row in rows:
        key, value = _normalize_row(row, metric_alias)
        normalized[key] = value
    return normalized


def _assert_rows_match(actual_rows: Iterable[Dict[str, object]], expected_rows: Iterable[Dict[str, object]], metric_alias: str) -> None:
    actual = _normalize_rows(actual_rows, metric_alias)
    expected = _normalize_rows(expected_rows, metric_alias)
    assert actual == expected


def _build_service(dialect, executor):
    service = SemanticQueryService(dialect=dialect, executor=executor)
    service.register_model(create_fact_sales_model())
    return service


def _build_request(expression: str, alias: str) -> SemanticQueryRequest:
    return SemanticQueryRequest(
        columns=[GROUP_FIELD, f"{expression} as {alias}"],
        order_by=[{"field": GROUP_FIELD, "dir": "asc"}],
    )


def _query_and_sql(service: SemanticQueryService, request: SemanticQueryRequest):
    validate_response = service.query_model("FactSalesModel", request, mode="validate")
    assert validate_response.error is None, validate_response.error
    assert validate_response.sql is not None

    execute_response = service.query_model("FactSalesModel", request, mode="execute")
    assert execute_response.error is None, execute_response.error
    return validate_response.sql, execute_response.items


def _native_sql(metric_sql: str, quote: str) -> str:
    return f"""
SELECT
  t.order_status AS {quote}{GROUP_ALIAS}{quote},
  {metric_sql} AS {quote}metric_value{quote}
FROM fact_sales t
GROUP BY t.order_status
ORDER BY t.order_status ASC
""".strip()


@pytest.fixture(scope="module")
def sqlite_alignment_db():
    SQLITE_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    if SQLITE_FIXTURE.exists():
        SQLITE_FIXTURE.unlink()

    service = SemanticQueryService(dialect=SqliteDialect(), executor=SQLiteExecutor(str(SQLITE_FIXTURE)))
    service.register_model(create_fact_sales_model())

    init_sql = """
CREATE TABLE fact_sales (
  order_id TEXT,
  order_line_no INTEGER,
  order_status TEXT,
  payment_method TEXT,
  quantity INTEGER,
  sales_amount NUMERIC,
  cost_amount NUMERIC,
  profit_amount NUMERIC,
  discount_amount NUMERIC,
  tax_amount NUMERIC,
  date_key INTEGER,
  product_key INTEGER,
  customer_key INTEGER,
  store_key INTEGER,
  channel_key INTEGER,
  promotion_key INTEGER
)
""".strip()

    rows = [
        ("SO-001", 1, "COMPLETED", "ALIPAY", 2, 100, 70, 30, 0, 10, 1, 1, 1, 1, 1, 1),
        ("SO-002", 1, "COMPLETED", "CARD", 1, 200, 150, 50, 0, 20, 1, 1, 1, 1, 1, 1),
        ("SO-003", 1, "PAID", "ALIPAY", 1, 80, 50, 30, 0, 8, 1, 1, 1, 1, 1, 1),
        ("SO-004", 1, "PENDING", "WECHAT", 1, 60, 40, 20, 0, 6, 1, 1, 1, 1, 1, 1),
        ("SO-005", 1, "SHIPPED", "ALIPAY", 1, 120, 90, 30, 0, 12, 1, 1, 1, 1, 1, 1),
    ]

    insert_sql = """
INSERT INTO fact_sales (
  order_id, order_line_no, order_status, payment_method, quantity, sales_amount,
  cost_amount, profit_amount, discount_amount, tax_amount, date_key, product_key,
  customer_key, store_key, channel_key, promotion_key
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip()

    loop = service._get_sync_loop()
    executor = service._executor
    loop.run_until_complete(executor.execute(init_sql))
    for row in rows:
        loop.run_until_complete(executor.execute(insert_sql, list(row)))

    yield SQLITE_FIXTURE

    loop.run_until_complete(service._executor.close())
    if SQLITE_FIXTURE.exists():
        SQLITE_FIXTURE.unlink()


@pytest.mark.parametrize(
    ("scenario", "expression", "metric_sql", "alias"),
    [
        (
            "sum_if_one_zero",
            "sum(if(orderStatus == 'COMPLETED', 1, 0))",
            "SUM(CASE WHEN t.order_status = 'COMPLETED' THEN 1 ELSE 0 END)",
            "completedRowCount",
        ),
        (
            "sum_if_measure_zero",
            "sum(if(orderStatus == 'COMPLETED', salesAmount, 0))",
            "SUM(CASE WHEN t.order_status = 'COMPLETED' THEN t.sales_amount ELSE 0 END)",
            "completedSales",
        ),
        (
            "avg_if_measure_null",
            "avg(if(orderStatus == 'COMPLETED', salesAmount, null))",
            "AVG(CASE WHEN t.order_status = 'COMPLETED' THEN t.sales_amount ELSE NULL END)",
            "avgCompletedSales",
        ),
        (
            "count_if_one_null",
            "count(if(orderStatus == 'COMPLETED', 1, null))",
            "COUNT(CASE WHEN t.order_status = 'COMPLETED' THEN 1 ELSE NULL END)",
            "completedCount",
        ),
    ],
)
def test_conditional_aggregate_if_reconciles_with_sqlite(sqlite_alignment_db, scenario, expression, metric_sql, alias):
    executor = SQLiteExecutor(str(sqlite_alignment_db))
    service = _build_service(SqliteDialect(), executor)
    request = _build_request(expression, alias)

    sql, actual_rows = _query_and_sql(service, request)
    assert "CASE WHEN" in sql.upper()

    native_executor = executor
    native_sql = _native_sql(metric_sql, '"')
    native_result = service._get_sync_loop().run_until_complete(native_executor.execute(native_sql))
    assert native_result.error is None, native_result.error

    expected_rows = [
        {GROUP_ALIAS: row[GROUP_ALIAS], alias: row["metric_value"]}
        for row in native_result.rows
    ]
    _assert_rows_match(actual_rows, expected_rows, alias)
    service._get_sync_loop().run_until_complete(executor.close())


class TestConditionalAggregateIfGovernance:
    def test_conditional_aggregate_if_order_by_alias_stays_quoted(self):
        service = _build_service(MySqlDialect(), executor=None)
        request = SemanticQueryRequest(
            columns=[GROUP_FIELD, "sum(if(orderStatus == 'COMPLETED', salesAmount, 0)) as completedSales"],
            order_by=[{"field": "completedSales", "dir": "desc"}],
        )
        response = service.query_model("FactSalesModel", request, mode="validate")
        assert response.error is None
        assert response.sql is not None
        order_clause = response.sql[response.sql.upper().index("ORDER BY"):]
        assert "`completedSales`" in order_clause

    def test_conditional_aggregate_if_respects_denied_columns(self):
        service = _build_service(MySqlDialect(), executor=None)
        request = SemanticQueryRequest(
            columns=[GROUP_FIELD, "sum(if(orderStatus == 'COMPLETED', salesAmount, 0)) as completedSales"],
            denied_columns=[DeniedColumn(table="fact_sales", column="sales_amount")],
        )
        response = service.query_model("FactSalesModel", request, mode="validate")
        assert response.error is not None
        assert "salesAmount" in response.error

    def test_conditional_aggregate_if_respects_field_access_dependencies(self):
        service = _build_service(MySqlDialect(), executor=None)
        request = SemanticQueryRequest(
            columns=[GROUP_FIELD, "sum(if(orderStatus == 'COMPLETED', salesAmount, 0)) as completedSales"],
            field_access=FieldAccessDef(visible=["orderStatus"]),
        )
        response = service.query_model("FactSalesModel", request, mode="validate")
        assert response.error is not None
        assert "salesAmount" in response.error

    def test_conditional_aggregate_if_passes_with_full_field_access(self):
        service = _build_service(MySqlDialect(), executor=None)
        request = SemanticQueryRequest(
            columns=[GROUP_FIELD, "sum(if(orderStatus == 'COMPLETED', salesAmount, 0)) as completedSales"],
            field_access=FieldAccessDef(visible=["orderStatus", "salesAmount"]),
        )
        response = service.query_model("FactSalesModel", request, mode="validate")
        assert response.error is None
        assert response.sql is not None
        assert "CASE WHEN" in response.sql.upper()


class TestConditionalAggregateIfRealDbAlignment:
    @pytest.fixture(scope="class")
    def mysql_service(self):
        executor = MySQLExecutor(**MYSQL_CONFIG)
        service = _build_service(MySqlDialect(), executor)
        yield service
        service._get_sync_loop().run_until_complete(executor.close())

    @pytest.fixture(scope="class")
    def postgres_service(self):
        executor = PostgreSQLExecutor(**POSTGRES_CONFIG)
        service = _build_service(PostgresDialect(), executor)
        yield service
        service._get_sync_loop().run_until_complete(executor.close())

    @pytest.mark.parametrize(
        ("scenario", "expression", "metric_sql", "alias"),
        [
            (
                "sum_if_one_zero",
                "sum(if(orderStatus == 'COMPLETED', 1, 0))",
                "SUM(CASE WHEN t.order_status = 'COMPLETED' THEN 1 ELSE 0 END)",
                "completedRowCount",
            ),
            (
                "sum_if_measure_zero",
                "sum(if(orderStatus == 'COMPLETED', salesAmount, 0))",
                "SUM(CASE WHEN t.order_status = 'COMPLETED' THEN t.sales_amount ELSE 0 END)",
                "completedSales",
            ),
            (
                "avg_if_measure_null",
                "avg(if(orderStatus == 'COMPLETED', salesAmount, null))",
                "AVG(CASE WHEN t.order_status = 'COMPLETED' THEN t.sales_amount ELSE NULL END)",
                "avgCompletedSales",
            ),
            (
                "count_if_one_null",
                "count(if(orderStatus == 'COMPLETED', 1, null))",
                "COUNT(CASE WHEN t.order_status = 'COMPLETED' THEN 1 ELSE NULL END)",
                "completedCount",
            ),
        ],
    )
    def test_mysql_alignment_against_native_sql(self, mysql_service, scenario, expression, metric_sql, alias):
        sql, actual_rows = _query_and_sql(mysql_service, _build_request(expression, alias))
        assert "CASE WHEN" in sql.upper()
        assert "IF(" not in sql.upper()

        native_sql = _native_sql(metric_sql, "`")
        native_result = mysql_service._get_sync_loop().run_until_complete(mysql_service._executor.execute(native_sql))
        assert native_result.error is None, native_result.error

        expected_rows = [
            {GROUP_ALIAS: row[GROUP_ALIAS], alias: row["metric_value"]}
            for row in native_result.rows
        ]
        _assert_rows_match(actual_rows, expected_rows, alias)

    @pytest.mark.parametrize(
        ("scenario", "expression", "metric_sql", "alias"),
        [
            (
                "sum_if_one_zero",
                "sum(if(orderStatus == 'COMPLETED', 1, 0))",
                "SUM(CASE WHEN t.order_status = 'COMPLETED' THEN 1 ELSE 0 END)",
                "completedRowCount",
            ),
            (
                "sum_if_measure_zero",
                "sum(if(orderStatus == 'COMPLETED', salesAmount, 0))",
                "SUM(CASE WHEN t.order_status = 'COMPLETED' THEN t.sales_amount ELSE 0 END)",
                "completedSales",
            ),
            (
                "avg_if_measure_null",
                "avg(if(orderStatus == 'COMPLETED', salesAmount, null))",
                "AVG(CASE WHEN t.order_status = 'COMPLETED' THEN t.sales_amount ELSE NULL END)",
                "avgCompletedSales",
            ),
            (
                "count_if_one_null",
                "count(if(orderStatus == 'COMPLETED', 1, null))",
                "COUNT(CASE WHEN t.order_status = 'COMPLETED' THEN 1 ELSE NULL END)",
                "completedCount",
            ),
        ],
    )
    def test_postgres_alignment_against_native_sql(self, postgres_service, scenario, expression, metric_sql, alias):
        sql, actual_rows = _query_and_sql(postgres_service, _build_request(expression, alias))
        assert "CASE WHEN" in sql.upper()
        assert "IF(" not in sql.upper()

        native_sql = _native_sql(metric_sql, '"')
        native_result = postgres_service._get_sync_loop().run_until_complete(postgres_service._executor.execute(native_sql))
        assert native_result.error is None, native_result.error

        expected_rows = [
            {GROUP_ALIAS: row[GROUP_ALIAS], alias: row["metric_value"]}
            for row in native_result.rows
        ]
        _assert_rows_match(actual_rows, expected_rows, alias)
