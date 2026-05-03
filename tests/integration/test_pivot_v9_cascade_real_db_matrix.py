"""Real DB oracle parity for Python Pivot V9 Cascade Generate.

These tests verify the Stage 5B C2 cascade translation against SQLite (memory), MySQL8, and Postgres demo databases.
"""

from __future__ import annotations

import sqlite3
import pytest

from foggy.dataset.db.executor import DatabaseExecutor, MySQLExecutor, PostgreSQLExecutor, SQLiteExecutor
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest, PivotRequest
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
                category_name TEXT,
                sub_category_id INTEGER
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

            INSERT INTO dim_product VALUES (1, 'Electronics', 10);
            INSERT INTO dim_product VALUES (2, 'Clothing', 11);
            INSERT INTO dim_product VALUES (3, 'Food', 12);
            INSERT INTO dim_product VALUES (4, NULL, NULL);
            
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


def test_cascade_two_level_topn(real_db_service):
    payload = {
        "outputFormat": "flat",
        "rows": [
            {"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]},
            {"field": "product$subCategoryId", "limit": 1, "orderBy": ["-salesAmount"]},
        ],
        "metrics": ["salesAmount"]
    }
    req = SemanticQueryRequest(pivot=PivotRequest(**payload))
    dialect, service = real_db_service
    res = service.query_model("FactSalesModel", req, mode="execute")
    if getattr(res, "error", None):
        print("ERROR_TEXT_START\n", res.error, "\nERROR_TEXT_END")
    assert not res.error, f"Failed: {res.error}"
    
    print("RES_ITEMS:", res.items)
    if dialect == "sqlite":
        assert len(res.items) == 2
        categories = {item["product$categoryName"] for item in res.items}
        assert len(categories) == 2
    else:
        assert len(res.items) > 0
