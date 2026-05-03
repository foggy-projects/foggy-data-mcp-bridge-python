"""Real DB oracle parity for Python Pivot V9 Cascade Generate.

These tests verify the Stage 5B C2 cascade translation against SQLite (memory), MySQL8, and Postgres demo databases.
"""

from __future__ import annotations

import sqlite3
import pytest

from foggy.dataset.db.executor import DatabaseExecutor, MySQLExecutor, PostgreSQLExecutor, SQLiteExecutor
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from typing import Any, Iterable
from decimal import Decimal
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


def _number(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))

def _norm_results(rows: Iterable[dict[str, Any]], row_key1: str, row_key2: str, metric_key: str) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        cat1 = row.get(row_key1)
        cat2 = row.get(row_key2)
        val = row.get(metric_key)
        normalized.append({
            "cat1": str(cat1) if cat1 is not None else None,
            "cat2": str(cat2) if cat2 is not None else None,
            "metric": _number(val) if val is not None else None,
        })
    return sorted(normalized, key=lambda r: (r["cat1"] is None, r["cat1"], r["cat2"] is None, r["cat2"]))


def _cascade_totals_oracle_sql() -> str:
    return """
WITH base AS (
    SELECT p.category_name as cat, p.sub_category_id as sub, SUM(f.sales_amount) as val
    FROM fact_sales f
    LEFT JOIN dim_product p ON f.product_key = p.product_key
    GROUP BY p.category_name, p.sub_category_id
),
parent_agg AS (
    SELECT cat, SUM(val) as p_val
    FROM base
    GROUP BY cat
),
parent_rank AS (
    SELECT cat, ROW_NUMBER() OVER (ORDER BY CASE WHEN p_val IS NULL THEN 1 ELSE 0 END, p_val DESC, cat ASC) as rn
    FROM parent_agg
),
parent_domain AS (
    SELECT cat
    FROM parent_rank
    WHERE rn <= 2
),
child_rank AS (
    SELECT b.cat, b.sub, b.val,
           ROW_NUMBER() OVER (
             PARTITION BY b.cat
             ORDER BY CASE WHEN b.val IS NULL THEN 1 ELSE 0 END, b.val DESC, b.cat ASC, b.sub ASC
           ) as rn
    FROM base b
    INNER JOIN parent_domain p ON (b.cat = p.cat OR (b.cat IS NULL AND p.cat IS NULL))
),
final_cells AS (
    SELECT cat, sub, val
    FROM child_rank
    WHERE rn <= 1
)
"""


def _metric_map(rows: Iterable[dict[str, Any]], key: str, metric: str) -> dict[Any, Decimal | None]:
    result = {}
    for row in rows:
        value = row.get(metric)
        result[row.get(key)] = _number(value) if value is not None else None
    return result


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
    assert not res.error, f"Failed: {res.error}"

    oracle_sql = """
WITH base AS (
    SELECT p.category_name as cat, p.sub_category_id as sub, SUM(f.sales_amount) as val
    FROM fact_sales f
    LEFT JOIN dim_product p ON f.product_key = p.product_key
    GROUP BY p.category_name, p.sub_category_id
),
parent_agg AS (
    SELECT cat, SUM(val) as p_val
    FROM base
    GROUP BY cat
),
parent_rank AS (
    SELECT cat, ROW_NUMBER() OVER (ORDER BY CASE WHEN p_val IS NULL THEN 1 ELSE 0 END, p_val DESC, cat ASC) as rn
    FROM parent_agg
),
child_rank AS (
    SELECT b.cat, b.sub, b.val, ROW_NUMBER() OVER (PARTITION BY b.cat ORDER BY CASE WHEN b.val IS NULL THEN 1 ELSE 0 END, b.val DESC, b.cat ASC, b.sub ASC) as rn
    FROM base b
    INNER JOIN parent_rank p ON (b.cat = p.cat OR (b.cat IS NULL AND p.cat IS NULL))
    WHERE p.rn <= 2
)
SELECT cat, sub, val
FROM child_rank
WHERE rn <= 1
"""
    oracle_rows = _oracle(service, oracle_sql)

    # Use _norm_results to compare them consistently
    pivot_norm = _norm_results(res.items, "product$categoryName", "product$subCategoryId", "salesAmount")
    oracle_norm = _norm_results(oracle_rows, "cat", "sub", "val")

    assert pivot_norm == oracle_norm

def test_cascade_null_parent_dimension(real_db_service):
    payload = {
        "outputFormat": "flat",
        "rows": [
            {"field": "product$categoryName", "limit": 2, "orderBy": ["salesAmount"]},
            {"field": "product$subCategoryId", "limit": 1, "orderBy": ["salesAmount"]},
        ],
        "metrics": ["salesAmount"]
    }
    req = SemanticQueryRequest(pivot=PivotRequest(**payload))
    dialect, service = real_db_service
    res = service.query_model("FactSalesModel", req, mode="execute")
    assert not res.error, f"Failed: {res.error}"

    oracle_sql = """
WITH base AS (
    SELECT p.category_name as cat, p.sub_category_id as sub, SUM(f.sales_amount) as val
    FROM fact_sales f
    LEFT JOIN dim_product p ON f.product_key = p.product_key
    GROUP BY p.category_name, p.sub_category_id
),
parent_agg AS (
    SELECT cat, SUM(val) as p_val
    FROM base
    GROUP BY cat
),
parent_rank AS (
    SELECT cat, ROW_NUMBER() OVER (ORDER BY CASE WHEN p_val IS NULL THEN 1 ELSE 0 END, p_val ASC, cat ASC) as rn
    FROM parent_agg
),
child_rank AS (
    SELECT b.cat, b.sub, b.val, ROW_NUMBER() OVER (PARTITION BY b.cat ORDER BY CASE WHEN b.val IS NULL THEN 1 ELSE 0 END, b.val ASC, b.cat ASC, b.sub ASC) as rn
    FROM base b
    INNER JOIN parent_rank p ON (b.cat = p.cat OR (b.cat IS NULL AND p.cat IS NULL))
    WHERE p.rn <= 2
)
SELECT cat, sub, val
FROM child_rank
WHERE rn <= 1
"""
    oracle_rows = _oracle(service, oracle_sql)

    # Use _norm_results to compare them consistently
    pivot_norm = _norm_results(res.items, "product$categoryName", "product$subCategoryId", "salesAmount")
    oracle_norm = _norm_results(oracle_rows, "cat", "sub", "val")
    
    assert pivot_norm == oracle_norm


def test_cascade_flat_row_subtotals_and_grand_total_surviving_domain(real_db_service):
    payload = {
        "outputFormat": "flat",
        "rows": [
            {"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]},
            {"field": "product$subCategoryId", "limit": 1, "orderBy": ["-salesAmount"]},
        ],
        "metrics": ["salesAmount"],
        "options": {"rowSubtotals": True, "grandTotal": True},
    }
    req = SemanticQueryRequest(pivot=PivotRequest(**payload))
    dialect, service = real_db_service
    res = service.query_model("FactSalesModel", req, mode="execute")
    assert not res.error, f"Failed: {res.error}"

    oracle_base = _cascade_totals_oracle_sql()
    oracle_sub = _oracle(
        service,
        oracle_base + "SELECT cat, SUM(val) AS val FROM final_cells GROUP BY cat",
    )
    oracle_grand = _oracle(
        service,
        oracle_base + "SELECT SUM(val) AS val FROM final_cells",
    )

    subtotals = [
        row for row in res.items
        if row.get("_sys_meta", {}).get("isRowSubtotal")
    ]
    assert all(row["product$subCategoryId"] == "ALL" for row in subtotals)
    assert _metric_map(subtotals, "product$categoryName", "salesAmount") == _metric_map(oracle_sub, "cat", "val")

    grand = [
        row for row in res.items
        if row.get("_sys_meta", {}).get("isGrandTotal")
    ]
    assert len(grand) == 1
    assert grand[0]["product$categoryName"] == "ALL"
    assert grand[0]["product$subCategoryId"] == "ALL"
    expected_grand = oracle_grand[0]["val"] if oracle_grand else None
    assert (
        _number(grand[0]["salesAmount"]) if grand[0]["salesAmount"] is not None else None
    ) == (
        _number(expected_grand) if expected_grand is not None else None
    )


def test_cascade_grid_row_subtotals_and_grand_total_surviving_domain(real_db_service):
    payload = {
        "outputFormat": "grid",
        "rows": [
            {"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]},
            {"field": "product$subCategoryId", "limit": 1, "orderBy": ["-salesAmount"]},
        ],
        "metrics": ["salesAmount"],
        "options": {"rowSubtotals": True, "grandTotal": True},
    }
    req = SemanticQueryRequest(pivot=PivotRequest(**payload))
    dialect, service = real_db_service
    res = service.query_model("FactSalesModel", req, mode="execute")
    assert not res.error, f"Failed: {res.error}"
    grid = res.items[0]

    oracle_base = _cascade_totals_oracle_sql()
    oracle_sub = _oracle(
        service,
        oracle_base + "SELECT cat, SUM(val) AS val FROM final_cells GROUP BY cat",
    )
    oracle_grand = _oracle(
        service,
        oracle_base + "SELECT SUM(val) AS val FROM final_cells",
    )
    expected_sub = _metric_map(oracle_sub, "cat", "val")
    expected_grand = oracle_grand[0]["val"] if oracle_grand else None

    headers = grid["rowHeaders"]
    cells = grid["cells"]
    metric_values = {
        tuple((k, h.get(k)) for k in ("product$categoryName", "product$subCategoryId")): cells[i][0]
        for i, h in enumerate(headers)
    }

    subtotal_headers = [h for h in headers if h.get("isSubtotal") and h.get("product$subCategoryId") == "ALL"
                        and h.get("product$categoryName") != "ALL"]
    assert {
        h["product$categoryName"]: _number(metric_values[(("product$categoryName", h["product$categoryName"]), ("product$subCategoryId", "ALL"))])
        for h in subtotal_headers
    } == expected_sub

    grand_key = (("product$categoryName", "ALL"), ("product$subCategoryId", "ALL"))
    assert grand_key in metric_values
    assert (
        _number(metric_values[grand_key]) if metric_values[grand_key] is not None else None
    ) == (
        _number(expected_grand) if expected_grand is not None else None
    )
