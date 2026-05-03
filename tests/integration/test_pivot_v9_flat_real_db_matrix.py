"""Real DB oracle parity for Python Pivot V9 flat MVP.

These tests verify the S2 flat Pivot translation against handwritten SQL on
the local MySQL8/Postgres demo databases. They skip when the demo database is
not available or not seeded, but once connected they compare executed result
sets rather than SQL text.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

import pytest

from foggy.dataset.db.executor import DatabaseExecutor, MySQLExecutor, PostgreSQLExecutor
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest


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


def _service(executor: DatabaseExecutor) -> SemanticQueryService:
    service = SemanticQueryService(executor=executor, enable_cache=False)
    service.register_model(create_fact_sales_model())
    return service


def _close(service: SemanticQueryService, executor: DatabaseExecutor) -> None:
    service._run_async_in_sync(executor.close())


def _execute(service: SemanticQueryService, sql: str, params: list[Any] | None = None):
    return service._run_async_in_sync(service._executor.execute(sql, params=params))


def _probe_or_skip(service: SemanticQueryService) -> None:
    result = _execute(service, "SELECT 1 AS ok")
    if result.error:
        pytest.skip(f"demo database unavailable: {result.error}")

    result = _execute(service, "SELECT COUNT(*) AS cnt FROM fact_sales")
    if result.error:
        pytest.skip(f"demo database schema unavailable: {result.error}")
    if not result.rows or int(result.rows[0]["cnt"]) == 0:
        pytest.skip("demo database has no fact_sales seed rows")


@pytest.fixture(params=["mysql8", "postgres"])
def real_db_service(request):
    if request.param == "mysql8":
        executor = MySQLExecutor(**MYSQL8_CONFIG)
    else:
        executor = PostgreSQLExecutor(**POSTGRES_CONFIG)

    service = _service(executor)
    _probe_or_skip(service)
    yield request.param, service
    _close(service, executor)


def _query_pivot(service: SemanticQueryService, request: SemanticQueryRequest) -> list[dict[str, Any]]:
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert response.error is None, response.error
    return response.items


def _oracle(service: SemanticQueryService, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    result = _execute(service, sql, params=params)
    assert result.error is None, result.error
    return result.rows


def _pick(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    raise AssertionError(f"missing any of {keys} in row {row}")


def _number(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _norm_category_sales(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [
        {
            "category": _pick(row, "一级品类名称", "product$categoryName", "category_name", "category"),
            "sales": _number(_pick(row, "销售金额", "salesAmount", "sales")),
        }
        for row in rows
    ]
    return sorted(normalized, key=lambda row: str(row["category"]))


def _norm_category_year_sales(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [
        {
            "category": _pick(row, "一级品类名称", "product$categoryName", "category_name", "category"),
            "year": _pick(row, "年", "salesDate$year", "year"),
            "sales": _number(_pick(row, "销售金额", "salesAmount", "sales")),
        }
        for row in rows
    ]
    return sorted(
        normalized,
        key=lambda row: (str(row["category"]), row["year"] is None, row["year"]),
    )


def _first_value(service: SemanticQueryService, sql: str, column: str) -> Any:
    rows = _oracle(service, sql)
    if not rows:
        pytest.skip(f"no candidate value for {column}")
    value = rows[0].get(column)
    if value is None:
        pytest.skip(f"candidate value for {column} is NULL")
    return value


def test_real_db_flat_pivot_rows_and_metrics_oracle_parity(real_db_service):
    _, service = real_db_service

    pivot_rows = _query_pivot(
        service,
        SemanticQueryRequest(
            pivot={
                "outputFormat": "flat",
                "rows": ["product$categoryName"],
                "metrics": ["salesAmount"],
            }
        ),
    )

    oracle_rows = _oracle(
        service,
        """
        SELECT p.category_name AS category, SUM(f.sales_amount) AS sales
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY p.category_name
        """,
    )

    assert _norm_category_sales(pivot_rows) == _norm_category_sales(oracle_rows)


def test_real_db_flat_pivot_rows_columns_and_metrics_oracle_parity(real_db_service):
    _, service = real_db_service

    pivot_rows = _query_pivot(
        service,
        SemanticQueryRequest(
            pivot={
                "outputFormat": "flat",
                "rows": ["product$categoryName"],
                "columns": ["salesDate$year"],
                "metrics": ["salesAmount"],
            }
        ),
    )

    oracle_rows = _oracle(
        service,
        """
        SELECT p.category_name AS category, d.year AS year, SUM(f.sales_amount) AS sales
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        LEFT JOIN dim_date d ON f.date_key = d.date_key
        GROUP BY p.category_name, d.year
        """,
    )

    assert _norm_category_year_sales(pivot_rows) == _norm_category_year_sales(oracle_rows)


def test_real_db_flat_pivot_slice_oracle_parity(real_db_service):
    _, service = real_db_service
    year = _first_value(
        service,
        """
        SELECT MAX(d.year) AS year
        FROM fact_sales f
        LEFT JOIN dim_date d ON f.date_key = d.date_key
        """,
        "year",
    )

    pivot_rows = _query_pivot(
        service,
        SemanticQueryRequest(
            pivot={
                "outputFormat": "flat",
                "rows": ["product$categoryName"],
                "metrics": ["salesAmount"],
            },
            slice=[{"field": "salesDate$year", "op": "=", "value": year}],
        ),
    )

    oracle_rows = _oracle(
        service,
        """
        SELECT p.category_name AS category, SUM(f.sales_amount) AS sales
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        LEFT JOIN dim_date d ON f.date_key = d.date_key
        WHERE d.year = ?
        GROUP BY p.category_name
        """,
        [year],
    )

    assert _norm_category_sales(pivot_rows) == _norm_category_sales(oracle_rows)


def test_real_db_flat_pivot_system_slice_oracle_parity(real_db_service):
    _, service = real_db_service
    member_level = _first_value(
        service,
        """
        SELECT c.member_level AS member_level
        FROM fact_sales f
        LEFT JOIN dim_customer c ON f.customer_key = c.customer_key
        WHERE c.member_level IS NOT NULL
        GROUP BY c.member_level
        ORDER BY COUNT(*) DESC
        LIMIT 1
        """,
        "member_level",
    )

    pivot_rows = _query_pivot(
        service,
        SemanticQueryRequest(
            pivot={
                "outputFormat": "flat",
                "rows": ["product$categoryName"],
                "metrics": ["salesAmount"],
            },
            system_slice=[{"field": "customer$memberLevel", "op": "=", "value": member_level}],
        ),
    )

    oracle_rows = _oracle(
        service,
        """
        SELECT p.category_name AS category, SUM(f.sales_amount) AS sales
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        LEFT JOIN dim_customer c ON f.customer_key = c.customer_key
        WHERE c.member_level = ?
        GROUP BY p.category_name
        """,
        [member_level],
    )

    assert _norm_category_sales(pivot_rows) == _norm_category_sales(oracle_rows)
