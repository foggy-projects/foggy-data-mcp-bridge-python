"""Real DB oracle parity for Python Pivot V9 Grid S3.

These tests verify the S3 Grid Pivot memory shaping and post-processing
(Having, TopN, Crossjoin) against local MySQL8/Postgres demo databases.
"""

from __future__ import annotations

import pytest
from typing import Any, Iterable

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

def _number(value: Any) -> float:
    from decimal import Decimal
    if isinstance(value, Decimal):
        return float(value)
    if value is None:
        return None
    return float(value)

def test_real_db_grid_pivot_base_shape(real_db_service):
    _, service = real_db_service

    pivot_items = _query_pivot(
        service,
        SemanticQueryRequest(
            pivot={
                "outputFormat": "grid",
                "rows": ["product$categoryName"],
                "columns": ["salesDate$year"],
                "metrics": ["salesAmount"],
            }
        ),
    )

    assert len(pivot_items) == 1
    grid = pivot_items[0]
    assert grid["format"] == "grid"
    assert grid["layout"]["metricPlacement"] == "columns"
    oracle_sql = """
        SELECT p.category_name AS cat, d.year AS yr, SUM(f.sales_amount) AS sales
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        LEFT JOIN dim_date d ON f.date_key = d.date_key
        GROUP BY p.category_name, d.year
    """
    oracle_rows = _oracle(service, oracle_sql)

    cats = sorted(list(set(r["cat"] for r in oracle_rows)), key=lambda x: (x is None, x))
    yrs = sorted(list(set(r["yr"] for r in oracle_rows)), key=lambda x: (x is None, x))
    lookup = {(r["cat"], r["yr"]): _number(r["sales"]) for r in oracle_rows}

    row_headers = grid["rowHeaders"]
    col_headers = grid["columnHeaders"]
    cells = grid["cells"]

    assert len(row_headers) == len(cats)
    assert len(col_headers) == len(yrs)
    assert len(cells) == len(cats)

    row_idx = {h["product$categoryName"]: i for i, h in enumerate(row_headers)}
    col_idx = {h["salesDate$year"]: j for j, h in enumerate(col_headers)}

    for cat in cats:
        for yr in yrs:
            i = row_idx.get(cat)
            j = col_idx.get(yr)
            expected = lookup.get((cat, yr))
            actual = cells[i][j]
            if expected is None:
                assert actual is None
            else:
                assert actual is not None
                assert abs(float(actual) - expected) < 0.01

def test_real_db_grid_pivot_having(real_db_service):
    _, service = real_db_service

    # Find a threshold to split the results
    result = _execute(service, "SELECT AVG(amount) AS threshold FROM (SELECT SUM(sales_amount) as amount FROM fact_sales GROUP BY product_key) t")
    assert result.error is None
    threshold = float(result.rows[0]["threshold"])

    pivot_items = _query_pivot(
        service,
        SemanticQueryRequest(
            pivot={
                "outputFormat": "grid",
                "rows": [{"field": "product$categoryName", "having": {"metric": "salesAmount", "op": ">", "value": threshold}}],
                "metrics": ["salesAmount"],
            }
        ),
    )

    assert len(pivot_items) == 1
    grid = pivot_items[0]

    oracle_sql = """
        SELECT p.category_name AS cat, SUM(f.sales_amount) AS sales
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY p.category_name
        HAVING SUM(f.sales_amount) > ?
    """
    oracle_rows = _oracle(service, oracle_sql, [threshold])
    cats = sorted(list(set(r["cat"] for r in oracle_rows)), key=lambda x: (x is None, x))

    row_headers = grid["rowHeaders"]
    assert len(row_headers) == len(cats)
    actual_cats = [h["product$categoryName"] for h in row_headers]
    assert set(actual_cats) == set(cats)

def test_real_db_grid_pivot_topn(real_db_service):
    _, service = real_db_service

    pivot_items = _query_pivot(
        service,
        SemanticQueryRequest(
            pivot={
                "outputFormat": "grid",
                "rows": [{"field": "product$categoryName", "limit": 1, "orderBy": ["-salesAmount"]}],
                "metrics": ["salesAmount"],
            }
        ),
    )

    assert len(pivot_items) == 1
    grid = pivot_items[0]

    oracle_sql = """
        SELECT p.category_name AS cat, SUM(f.sales_amount) AS sales
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY p.category_name
        ORDER BY sales DESC, cat ASC
        LIMIT 1
    """
    oracle_rows = _oracle(service, oracle_sql)
    cats = [r["cat"] for r in oracle_rows]

    row_headers = grid["rowHeaders"]
    assert len(row_headers) == len(cats)

    actual_cats = [h["product$categoryName"] for h in row_headers]
    assert set(actual_cats) == set(cats)

def test_real_db_grid_pivot_crossjoin(real_db_service):
    _, service = real_db_service

    pivot_items = _query_pivot(
        service,
        SemanticQueryRequest(
            pivot={
                "outputFormat": "grid",
                "options": {"crossjoin": True},
                "rows": ["product$categoryName"],
                "columns": ["salesDate$year"],
                "metrics": ["salesAmount"],
            }
        ),
    )

    assert len(pivot_items) == 1
    grid = pivot_items[0]
    oracle_sql = """
        SELECT p.category_name AS cat, d.year AS yr, SUM(f.sales_amount) AS sales
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        LEFT JOIN dim_date d ON f.date_key = d.date_key
        GROUP BY p.category_name, d.year
    """
    oracle_rows = _oracle(service, oracle_sql)
    cats = sorted(list(set(r["cat"] for r in oracle_rows)), key=lambda x: (x is None, x))
    yrs = sorted(list(set(r["yr"] for r in oracle_rows)), key=lambda x: (x is None, x))
    lookup = {(r["cat"], r["yr"]): _number(r["sales"]) for r in oracle_rows}

    row_headers = grid["rowHeaders"]
    col_headers = grid["columnHeaders"]
    cells = grid["cells"]

    assert len(row_headers) == len(cats)
    assert len(col_headers) == len(yrs)
    assert len(cells) == len(cats)

    row_idx = {h["product$categoryName"]: i for i, h in enumerate(row_headers)}
    col_idx = {h["salesDate$year"]: j for j, h in enumerate(col_headers)}

    for cat in cats:
        for yr in yrs:
            i = row_idx.get(cat)
            j = col_idx.get(yr)
            expected = lookup.get((cat, yr))
            actual = cells[i][j]
            if expected is None:
                assert actual is None
            else:
                assert actual is not None
                assert abs(float(actual) - expected) < 0.01
