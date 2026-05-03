import pytest
import sqlite3
from typing import Any, Dict

from foggy.dataset.db.executor import SQLiteExecutor
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.mcp_spi import SemanticQueryRequest
from foggy.demo.models.ecommerce_models import create_fact_sales_model


def _seed_flat_pivot_db(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE dim_product (
                product_key INTEGER PRIMARY KEY,
                category_id INTEGER,
                category_name TEXT
            );
            CREATE TABLE dim_customer (
                customer_key INTEGER PRIMARY KEY,
                member_level TEXT
            );
            CREATE TABLE dim_date (
                date_key INTEGER PRIMARY KEY,
                year INTEGER
            );
            CREATE TABLE fact_sales (
                date_key INTEGER,
                product_key INTEGER,
                customer_key INTEGER,
                sales_amount REAL
            );
            """
        )
        conn.executemany(
            "INSERT INTO dim_product VALUES (?, ?, ?)",
            [
                (1, 10, "Electronics"),
                (2, 20, "Clothing"),
            ]
        )
        conn.executemany(
            "INSERT INTO dim_customer VALUES (?, ?)",
            [
                (1, "VIP"),
                (2, "Normal"),
            ]
        )
        conn.executemany(
            "INSERT INTO dim_date VALUES (?, ?)",
            [
                (20240101, 2024),
                (20230101, 2023),
            ]
        )
        conn.executemany(
            "INSERT INTO fact_sales VALUES (?, ?, ?, ?)",
            [
                (20240101, 1, 1, 100.0), # Electronics, VIP, 2024
                (20240101, 1, 2, 50.0),  # Electronics, Normal, 2024
                (20230101, 2, 1, 200.0), # Clothing, VIP, 2023
            ]
        )
        conn.commit()
    finally:
        conn.close()

def _execute_oracle(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

@pytest.fixture
def service_and_db(tmp_path):
    db_path = tmp_path / "grid_pivot.sqlite"
    _seed_flat_pivot_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = SemanticQueryService(executor=executor)
    service.register_model(create_fact_sales_model())
    yield service, str(db_path)
    service._run_async_in_sync(executor.close())

def test_grid_base_shape(service_and_db):
    service, db_path = service_and_db
    payload = {
        "outputFormat": "grid",
        "rows": ["product$categoryName"],
        "columns": ["salesDate$year"],
        "metrics": ["salesAmount"]
    }
    request = SemanticQueryRequest(pivot=payload)
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert response.error is None
    assert len(response.items) == 1

    grid = response.items[0]
    assert grid["format"] == "grid"
    assert grid["layout"]["metricPlacement"] == "columns"

    oracle_sql = """
        SELECT p.category_name AS cat, d.year AS yr, SUM(f.sales_amount) AS sales
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        LEFT JOIN dim_date d ON f.date_key = d.date_key
        GROUP BY p.category_name, d.year
    """
    oracle_rows = _execute_oracle(db_path, oracle_sql)

    # Extract expected domains
    cats = sorted(list(set(r["cat"] for r in oracle_rows)))
    yrs = sorted(list(set(r["yr"] for r in oracle_rows)))
    lookup = {(r["cat"], r["yr"]): r["sales"] for r in oracle_rows}

    # Verify headers matches domains
    row_headers = grid["rowHeaders"]
    assert len(row_headers) == len(cats)
    for i, h in enumerate(row_headers):
        assert h["product$categoryName"] == cats[i]

    col_headers = grid["columnHeaders"]
    assert len(col_headers) == len(yrs)
    for i, h in enumerate(col_headers):
        assert h["salesDate$year"] == yrs[i]
        assert h["metric"] == "salesAmount"

    # Verify cells against lookup
    cells = grid["cells"]
    assert len(cells) == len(cats)
    for i, cat in enumerate(cats):
        assert len(cells[i]) == len(yrs)
        for j, yr in enumerate(yrs):
            expected = lookup.get((cat, yr))
            assert cells[i][j] == expected

def test_grid_having(service_and_db):
    service, db_path = service_and_db
    payload = {
        "outputFormat": "grid",
        "rows": [{"field": "product$categoryName", "having": {"metric": "salesAmount", "op": ">", "value": 160.0}}],
        "metrics": ["salesAmount"]
    }
    request = SemanticQueryRequest(pivot=payload)
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert response.error is None

    grid = response.items[0]

    oracle_sql = """
        SELECT p.category_name AS cat, SUM(f.sales_amount) AS sales
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY p.category_name
        HAVING SUM(f.sales_amount) > 160.0
    """
    oracle_rows = _execute_oracle(db_path, oracle_sql)
    cats = sorted(list(set(r["cat"] for r in oracle_rows)))

    row_headers = grid["rowHeaders"]
    assert len(row_headers) == len(cats)
    for i, h in enumerate(row_headers):
        assert h["product$categoryName"] == cats[i]

def test_grid_topn(service_and_db):
    service, db_path = service_and_db
    # Seed an extra row to test limit
    conn = sqlite3.connect(db_path)
    conn.executescript("INSERT INTO dim_product VALUES (3, 30, 'Books'); INSERT INTO fact_sales VALUES (20240101, 3, 1, 500.0);")
    conn.commit()
    conn.close()

    payload = {
        "outputFormat": "grid",
        "rows": [{"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]}],
        "metrics": ["salesAmount"]
    }
    request = SemanticQueryRequest(pivot=payload)
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert response.error is None

    grid = response.items[0]

    oracle_sql = """
        SELECT p.category_name AS cat, SUM(f.sales_amount) AS sales
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY p.category_name
        ORDER BY sales DESC, cat ASC
        LIMIT 2
    """
    oracle_rows = _execute_oracle(db_path, oracle_sql)
    cats = [r["cat"] for r in oracle_rows]

    row_headers = grid["rowHeaders"]
    assert len(row_headers) == len(cats)

    actual_cats = [h["product$categoryName"] for h in row_headers]
    assert set(actual_cats) == set(cats)

def test_grid_crossjoin(service_and_db):
    service, db_path = service_and_db
    payload = {
        "outputFormat": "grid",
        "options": {"crossjoin": True},
        "rows": ["product$categoryName"],
        "columns": ["salesDate$year"],
        "metrics": ["salesAmount"]
    }
    request = SemanticQueryRequest(pivot=payload)
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert response.error is None
    grid = response.items[0]

    oracle_sql = """
        SELECT p.category_name AS cat, d.year AS yr, SUM(f.sales_amount) AS sales
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        LEFT JOIN dim_date d ON f.date_key = d.date_key
        GROUP BY p.category_name, d.year
    """
    oracle_rows = _execute_oracle(db_path, oracle_sql)
    cats = sorted(list(set(r["cat"] for r in oracle_rows)))
    yrs = sorted(list(set(r["yr"] for r in oracle_rows)))
    lookup = {(r["cat"], r["yr"]): r["sales"] for r in oracle_rows}

    # We must explicitly verify that Option A is fulfilled:
    # 1. Row headers contain the full domain of cats.
    # 2. Column headers contain the full domain of yrs.
    # 3. Cells contain values for explicit combinations, and `None` for missing ones, forming a dense matrix.
    row_headers = grid["rowHeaders"]
    col_headers = grid["columnHeaders"]
    cells = grid["cells"]

    assert len(row_headers) == len(cats)
    assert len(col_headers) == len(yrs)
    assert len(cells) == len(cats)

    for i, cat in enumerate(cats):
        for j, yr in enumerate(yrs):
            expected = lookup.get((cat, yr))
            assert cells[i][j] == expected

def test_grid_metric_placement_rows(service_and_db):
    service, db_path = service_and_db
    payload = {
        "outputFormat": "grid",
        "layout": {"metricPlacement": "rows"},
        "rows": ["product$categoryName"],
        "columns": ["salesDate$year"],
        "metrics": ["salesAmount"]
    }
    request = SemanticQueryRequest(pivot=payload)
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert response.error is None

    grid = response.items[0]
    assert grid["layout"]["metricPlacement"] == "rows"

    row_headers = grid["rowHeaders"]
    assert len(row_headers) == 2
    assert all("metric" in h for h in row_headers)
    assert all("isSubtotal" in h for h in row_headers)

    col_headers = grid["columnHeaders"]
    assert len(col_headers) == 2
    assert all("metric" not in h for h in col_headers)

def test_grid_fail_closed_unsupported_features(service_and_db):
    service, db_path = service_and_db
    payload = {
        "outputFormat": "grid",
        "options": {"rowSubtotals": True},
        "rows": ["product$categoryName"],
        "metrics": ["salesAmount"]
    }
    request = SemanticQueryRequest(pivot=payload)
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert response.error is not None
    assert "subtotals" in response.error

    payload = {
        "outputFormat": "grid",
        "rows": [{"field": "product$categoryName", "hierarchyMode": "tree"}],
        "metrics": ["salesAmount"]
    }
    request = SemanticQueryRequest(pivot=payload)
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert response.error is not None
    assert "hierarchyMode" in response.error
