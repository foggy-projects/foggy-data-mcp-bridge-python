import sqlite3
import pytest

from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest
from foggy.dataset.db.executor import SQLiteExecutor
from foggy.mcp_spi.semantic import DeniedColumn
from foggy.dataset_model.semantic.pivot.flat_executor import PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON

def _seed_flat_pivot_db(db_path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE dim_date (
                date_key INTEGER PRIMARY KEY,
                full_date TEXT, year INTEGER, quarter INTEGER, month INTEGER,
                week_of_year INTEGER, month_name TEXT, day_of_week INTEGER, is_weekend INTEGER
            );
            CREATE TABLE dim_product (
                product_key INTEGER PRIMARY KEY,
                product_name TEXT, product_id TEXT, category_id TEXT, category_name TEXT,
                sub_category_id TEXT, sub_category_name TEXT, brand TEXT, unit_price REAL, unit_cost REAL
            );
            CREATE TABLE dim_customer (
                customer_key INTEGER PRIMARY KEY,
                customer_name TEXT, customer_id TEXT, customer_type TEXT, gender TEXT,
                age_group TEXT, province TEXT, city TEXT, member_level TEXT
            );
            CREATE TABLE fact_sales (
                date_key INTEGER, product_key INTEGER, customer_key INTEGER,
                store_key INTEGER, channel_key INTEGER, promotion_key INTEGER,
                order_id TEXT, order_line_no INTEGER, order_status TEXT, payment_method TEXT,
                quantity INTEGER, sales_amount REAL, cost_amount REAL, profit_amount REAL,
                discount_amount REAL, tax_amount REAL
            );
            """
        )
        conn.executemany(
            "INSERT INTO dim_date (date_key, year) VALUES (?, ?)",
            [(20240101, 2024), (20230101, 2023)]
        )
        conn.executemany(
            "INSERT INTO dim_product (product_key, category_name) VALUES (?, ?)",
            [(1, "Electronics"), (2, "Clothing")]
        )
        conn.executemany(
            "INSERT INTO dim_customer (customer_key, member_level) VALUES (?, ?)",
            [(1, "VIP"), (2, "Normal")]
        )
        conn.executemany(
            "INSERT INTO fact_sales (date_key, product_key, customer_key, sales_amount) VALUES (?, ?, ?, ?)",
            [
                (20240101, 1, 1, 100.0),
                (20240101, 1, 2, 50.0),
                (20230101, 2, 1, 200.0),
            ]
        )
        conn.commit()
    finally:
        conn.close()

@pytest.fixture
def service_and_db(tmp_path):
    db_path = tmp_path / "flat_pivot.sqlite"
    _seed_flat_pivot_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = SemanticQueryService(executor=executor)
    service.register_model(create_fact_sales_model())
    yield service, str(db_path)
    service._run_async_in_sync(executor.close())

def _execute_oracle(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

def test_flat_pivot_rows_and_metrics_parity(service_and_db):
    service, db_path = service_and_db
    payload = {
        "outputFormat": "flat",
        "rows": ["product$categoryName"],
        "metrics": ["salesAmount"]
    }
    request = SemanticQueryRequest(pivot=payload)
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert response.error is None

    rows = sorted([{"category": r.get("一级品类名称") or r.get("product$categoryName"), "sales": r.get("销售金额") or r.get("salesAmount")} for r in response.items], key=lambda x: x["category"])

    oracle_sql = """
        SELECT p.category_name, SUM(f.sales_amount) as sales
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY p.category_name
    """
    oracle_rows = sorted([{"category": r["category_name"], "sales": r["sales"]} for r in _execute_oracle(db_path, oracle_sql)], key=lambda x: x["category"])

    assert rows == oracle_rows

def test_flat_pivot_rows_columns_and_metrics_parity(service_and_db):
    service, db_path = service_and_db
    payload = {
        "outputFormat": "flat",
        "rows": ["product$categoryName"],
        "columns": ["salesDate$year"],
        "metrics": ["salesAmount"]
    }
    request = SemanticQueryRequest(pivot=payload)
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert response.error is None

    rows = sorted([{"category": r.get("一级品类名称") or r.get("product$categoryName"), "year": r.get("年") or r.get("salesDate$year"), "sales": r.get("销售金额") or r.get("salesAmount")} for r in response.items], key=lambda x: (x["category"], x["year"]))

    oracle_sql = """
        SELECT p.category_name, d.year, SUM(f.sales_amount) as sales
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        LEFT JOIN dim_date d ON f.date_key = d.date_key
        GROUP BY p.category_name, d.year
    """
    oracle_rows = sorted([{"category": r["category_name"], "year": r["year"], "sales": r["sales"]} for r in _execute_oracle(db_path, oracle_sql)], key=lambda x: (x["category"], x["year"]))

    assert rows == oracle_rows

def test_flat_pivot_slice_parity(service_and_db):
    service, db_path = service_and_db
    payload = {
        "outputFormat": "flat",
        "rows": ["product$categoryName"],
        "metrics": ["salesAmount"]
    }
    request = SemanticQueryRequest(
        pivot=payload,
        slice=[{"field": "salesDate$year", "op": "=", "value": 2024}]
    )
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert response.error is None
    assert len(response.items) == 1

    category = response.items[0].get("一级品类名称") or response.items[0].get("product$categoryName")
    sales = response.items[0].get("销售金额") or response.items[0].get("salesAmount")

    oracle_sql = """
        SELECT p.category_name, SUM(f.sales_amount) as sales
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        LEFT JOIN dim_date d ON f.date_key = d.date_key
        WHERE d.year = 2024
        GROUP BY p.category_name
    """
    oracle_rows = _execute_oracle(db_path, oracle_sql)
    assert len(oracle_rows) == 1

    assert category == oracle_rows[0]["category_name"]
    assert sales == oracle_rows[0]["sales"]

def test_flat_pivot_system_slice_parity(service_and_db):
    service, db_path = service_and_db
    payload = {
        "outputFormat": "flat",
        "rows": ["product$categoryName"],
        "metrics": ["salesAmount"]
    }
    request = SemanticQueryRequest(
        pivot=payload,
        system_slice=[{"field": "customer$memberLevel", "op": "=", "value": "VIP"}]
    )
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert response.error is None

    rows = sorted([{"category": r.get("一级品类名称") or r.get("product$categoryName"), "sales": r.get("销售金额") or r.get("salesAmount")} for r in response.items], key=lambda x: x["category"])

    oracle_sql = """
        SELECT p.category_name, SUM(f.sales_amount) as sales
        FROM fact_sales f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        LEFT JOIN dim_customer c ON f.customer_key = c.customer_key
        WHERE c.member_level = 'VIP'
        GROUP BY p.category_name
    """
    oracle_rows = sorted([{"category": r["category_name"], "sales": r["sales"]} for r in _execute_oracle(db_path, oracle_sql)], key=lambda x: x["category"])

    assert rows == oracle_rows

def test_flat_pivot_denied_columns_fail_closed(service_and_db):
    service, _ = service_and_db
    payload = {
        "outputFormat": "flat",
        "rows": ["product$categoryName"],
        "metrics": ["salesAmount"]
    }
    request = SemanticQueryRequest(
        pivot=payload,
        denied_columns=[
            DeniedColumn(table="dim_product", column="category_name")
        ]
    )
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert "not accessible" in response.error.lower()

def test_flat_pivot_rejects_columns_at_runtime(service_and_db):
    service, _ = service_and_db
    payload = {
        "outputFormat": "flat",
        "rows": ["product$categoryName"],
        "metrics": ["salesAmount"]
    }
    request = SemanticQueryRequest(pivot=payload, columns=["customer$memberLevel"])
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON in response.error
    assert "pivot + columns" in response.error

def test_flat_pivot_rejects_time_window_at_runtime(service_and_db):
    service, _ = service_and_db
    payload = {
        "outputFormat": "flat",
        "rows": ["product$categoryName"],
        "metrics": ["salesAmount"]
    }
    request = SemanticQueryRequest(
        pivot=payload,
        time_window={"field": "salesDate$id", "grain": "month", "comparison": "yoy", "targetMetrics": ["salesAmount"]}
    )
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON in response.error
    assert "pivot + timeWindow" in response.error
