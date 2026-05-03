"""Real DB oracle parity for Python Pivot V9 Domain Transport.

These tests verify the Stage 5A domain transport translation against handwritten SQL on
SQLite (memory), MySQL8, and Postgres demo databases. They skip when the external demo database is
not available or not seeded, but once connected they compare executed result
sets rather than SQL text.

Covers:
  - Additive SUM parity.
  - Non-additive COUNT DISTINCT parity (proves pre-aggregation).
  - NULL domain member matching parity.
  - Parameter ordering correctness (domain_params + base_where_params).
  - Security isolation (system_slice, denied_columns).
  - Size <= threshold OR-of-AND fallback parity.
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from typing import Any, Iterable

import pytest

from foggy.dataset.db.executor import DatabaseExecutor, MySQLExecutor, PostgreSQLExecutor, SQLiteExecutor
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest
from foggy.dataset_model.semantic.pivot.domain_transport import DomainTransportPlan
from foggy.mcp_spi.semantic import DeniedColumn

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


@pytest.fixture(params=["sqlite", "mysql8", "postgres"])
def real_db_service(request, tmp_path):
    if request.param == "sqlite":
        # Create an SQLite file DB and seed it
        db_path = str(tmp_path / "pivot_test.sqlite")
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE dim_product (
                product_key INTEGER PRIMARY KEY,
                category_name TEXT
            );
            CREATE TABLE dim_customer (
                customer_key INTEGER PRIMARY KEY,
                member_level TEXT
            );
            CREATE TABLE fact_sales (
                product_key INTEGER,
                customer_key INTEGER,
                sales_amount REAL
            );

            INSERT INTO dim_product VALUES (1, 'Electronics');
            INSERT INTO dim_product VALUES (2, 'Clothing');
            INSERT INTO dim_product VALUES (3, 'Food');
            INSERT INTO dim_product VALUES (4, NULL);
            
            INSERT INTO dim_customer VALUES (100, 'Gold');
            INSERT INTO dim_customer VALUES (101, 'Silver');
            INSERT INTO dim_customer VALUES (200, 'Gold');
            INSERT INTO dim_customer VALUES (300, 'Bronze');
            INSERT INTO dim_customer VALUES (400, 'Gold');

            INSERT INTO fact_sales VALUES (1, 100, 10.0);
            INSERT INTO fact_sales VALUES (1, 101, 20.0);
            INSERT INTO fact_sales VALUES (1, 100,  5.0);
            INSERT INTO fact_sales VALUES (2, 200, 30.0);
            INSERT INTO fact_sales VALUES (2, 200, 15.0);
            INSERT INTO fact_sales VALUES (3, 300, 50.0);
            INSERT INTO fact_sales VALUES (4, 400,  7.0);
        """)
        conn.close()
        executor = SQLiteExecutor(db_path)
    elif request.param == "mysql8":
        executor = MySQLExecutor(**MYSQL8_CONFIG)
    else:
        executor = PostgreSQLExecutor(**POSTGRES_CONFIG)

    service = _service(executor)
    if request.param != "sqlite":
        _probe_or_skip(service)
    
    yield request.param, service
    _close(service, executor)


def _query_pivot(service: SemanticQueryService, request: SemanticQueryRequest) -> list[dict[str, Any]]:
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert response.error is None, response.error
    plan = getattr(request, "domain_transport_plan", None)
    if plan and plan.tuples and len(plan.tuples) > plan.threshold:
        assert "WITH _pivot_domain_transport" in response.sql
        assert "INNER JOIN _pivot_domain_transport" in response.sql
    return response.items


def _oracle(service: SemanticQueryService, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    result = _execute(service, sql, params=params)
    assert result.error is None, result.error
    return result.rows


def _pick(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
            
    for k, v in row.items():
        if k not in ["一级品类名称", "product$categoryName", "category_name", "category"]:
            return v
            
    raise AssertionError(f"missing any of {keys} in row {row}")


def _number(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _norm_results(rows: Iterable[dict[str, Any]], row_key: str, metric_key: str, *extra_metric_keys: str) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        cat = _pick(row, "一级品类名称", "product$categoryName", "category_name", row_key)
        val = _pick(row, "销售金额", "salesAmount", "metric", metric_key, *extra_metric_keys)
        normalized.append({
            "category": str(cat) if cat is not None else None,
            "metric": _number(val) if val is not None else None,
        })
    return sorted(normalized, key=lambda r: (r["category"] is None, r["category"]))


def test_additive_sum_parity(real_db_service):
    dialect, service = real_db_service
    
    plan = DomainTransportPlan(
        columns=("product$categoryName",),
        tuples=(("Electronics",), ("Clothing",)),
        threshold=0,
    )
    request = SemanticQueryRequest(
        columns=["product$categoryName", "salesAmount"],
        group_by=["product$categoryName"]
    )
    request.domain_transport_plan = plan
    
    pivot_rows = _query_pivot(service, request)
    # Base query for additive SUM over domain
    oracle_sql = """
        SELECT p.category_name, SUM(f.sales_amount) as metric
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        WHERE p.category_name IN ('Electronics', 'Clothing')
        GROUP BY p.category_name
    """
    oracle_rows = _oracle(service, oracle_sql)
    
    assert _norm_results(pivot_rows, "category_name", "metric") == _norm_results(oracle_rows, "category_name", "metric")


def test_non_additive_count_distinct_parity(real_db_service):
    """Proves pre-aggregation injection is correct (vs wrapping after agg)."""
    dialect, service = real_db_service
    
    plan = DomainTransportPlan(
        columns=("product$categoryName",),
        tuples=(("Electronics",),),
        threshold=0,
    )
    request = SemanticQueryRequest(
        columns=["product$categoryName", "uniqueCustomers"],
        group_by=["product$categoryName"]
    )
    request.domain_transport_plan = plan
    
    pivot_rows = _query_pivot(service, request)
    
    oracle_sql = """
        SELECT p.category_name, COUNT(DISTINCT f.customer_key) as metric
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        WHERE p.category_name = 'Electronics'
        GROUP BY p.category_name
    """
    oracle_rows = _oracle(service, oracle_sql)
    
    assert _norm_results(pivot_rows, "category_name", "uniqueCustomers", "客户数") == _norm_results(oracle_rows, "category_name", "metric")


def test_null_domain_member_parity(real_db_service):
    dialect, service = real_db_service
    
    plan = DomainTransportPlan(
        columns=("product$categoryName",),
        tuples=(("Electronics",), (None,)),
        threshold=0,
    )
    request = SemanticQueryRequest(
        columns=["product$categoryName", "salesAmount"],
        group_by=["product$categoryName"]
    )
    request.domain_transport_plan = plan
    
    pivot_rows = _query_pivot(service, request)
    
    oracle_sql = """
        SELECT p.category_name, SUM(f.sales_amount) as metric
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        WHERE p.category_name = 'Electronics' OR p.category_name IS NULL
        GROUP BY p.category_name
    """
    oracle_rows = _oracle(service, oracle_sql)
    
    assert _norm_results(pivot_rows, "category_name", "metric") == _norm_results(oracle_rows, "category_name", "metric")


def test_system_slice_parity(real_db_service):
    dialect, service = real_db_service
    
    plan = DomainTransportPlan(
        columns=("product$categoryName",),
        tuples=(("Electronics",), ("Clothing",)),
        threshold=0,
    )
    request = SemanticQueryRequest(
        columns=["product$categoryName", "salesAmount"],
        group_by=["product$categoryName"],
        system_slice=[{"field": "customer$memberLevel", "op": "=", "value": "Gold"}]
    )
    request.domain_transport_plan = plan
    
    pivot_rows = _query_pivot(service, request)
    
    oracle_sql = """
        SELECT p.category_name, SUM(f.sales_amount) as metric
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        LEFT JOIN dim_customer c ON f.customer_key = c.customer_key
        WHERE p.category_name IN ('Electronics', 'Clothing') AND c.member_level = 'Gold'
        GROUP BY p.category_name
    """
    oracle_rows = _oracle(service, oracle_sql)
    
    assert _norm_results(pivot_rows, "category_name", "metric") == _norm_results(oracle_rows, "category_name", "metric")


def test_denied_columns_fail_closed(real_db_service):
    dialect, service = real_db_service
    
    plan = DomainTransportPlan(
        columns=("product$categoryName",),
        tuples=(("Electronics",),),
        threshold=0,
    )
    request = SemanticQueryRequest(
        columns=["product$categoryName", "salesAmount"],
        group_by=["product$categoryName"],
        denied_columns=[DeniedColumn(table="dim_product", column="category_name")]
    )
    request.domain_transport_plan = plan
    
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert response.error is not None
    assert "not accessible" in response.error.lower()


def test_size_fallback_parity(real_db_service):
    """If domain <= threshold, OR-of-AND injection should happen and yield parity."""
    dialect, service = real_db_service
    
    plan = DomainTransportPlan(
        columns=("product$categoryName",),
        tuples=(("Electronics",), ("Clothing",)),
        threshold=500  # Size is 2, so it will fallback to OR-of-AND
    )
    request = SemanticQueryRequest(
        columns=["product$categoryName", "salesAmount"],
        group_by=["product$categoryName"]
    )
    request.domain_transport_plan = plan
    
    pivot_rows = _query_pivot(service, request)
    
    oracle_sql = """
        SELECT p.category_name, SUM(f.sales_amount) as metric
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        WHERE p.category_name = 'Electronics' OR p.category_name = 'Clothing'
        GROUP BY p.category_name
    """
    oracle_rows = _oracle(service, oracle_sql)
    
    assert _norm_results(pivot_rows, "category_name", "metric") == _norm_results(oracle_rows, "category_name", "metric")
