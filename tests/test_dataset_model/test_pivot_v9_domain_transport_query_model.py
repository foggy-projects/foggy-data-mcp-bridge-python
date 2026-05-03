import sqlite3
import pytest

from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi.semantic import SemanticQueryRequest, DeniedColumn
from foggy.dataset.db.executor import SQLiteExecutor
from foggy.dataset.dialects.mysql import MySqlDialect
from foggy.dataset_model.semantic.pivot.domain_transport import (
    DomainTransportPlan, PIVOT_DOMAIN_TRANSPORT_REFUSED
)

def _seed_db(db_path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
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

            INSERT INTO dim_customer VALUES (100, 'VIP');
            INSERT INTO dim_customer VALUES (101, 'Normal');
            INSERT INTO dim_customer VALUES (200, 'VIP');
            INSERT INTO dim_customer VALUES (300, 'VIP');
            INSERT INTO dim_customer VALUES (400, 'Normal');

            -- Electronics: 2 distinct customers (100, 101)
            INSERT INTO fact_sales VALUES (1, 100, 10.0);
            INSERT INTO fact_sales VALUES (1, 101, 20.0);
            INSERT INTO fact_sales VALUES (1, 100, 5.0);

            -- Clothing: 1 distinct customer
            INSERT INTO fact_sales VALUES (2, 200, 30.0);
            INSERT INTO fact_sales VALUES (2, 200, 15.0);

            -- Food: 1 distinct customer
            INSERT INTO fact_sales VALUES (3, 300, 50.0);

            -- NULL category
            INSERT INTO fact_sales VALUES (4, 400, 7.0);
            """
        )
        conn.commit()
    finally:
        conn.close()

@pytest.fixture
def service_and_db(tmp_path):
    db_path = tmp_path / "domain_transport.sqlite"
    _seed_db(db_path)
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

class TestPivotV9DomainTransportQueryModel:

    def test_additive_sum_parity(self, service_and_db):
        service, db_path = service_and_db
        plan = DomainTransportPlan(
            columns=("product$categoryName",),
            tuples=(("Electronics",), ("Clothing",)),
            threshold=0
        )
        request = SemanticQueryRequest(
            columns=["product$categoryName", "salesAmount"],
            group_by=["product$categoryName"]
        )
        request.domain_transport_plan = plan
        # Note: caller typically sets request.slice but for domain transport injection,
        # we assume `executor.py` strips it. Here we just rely on the CTE.
        response = service.query_model("FactSalesModel", request, mode="execute")
        assert response.error is None

        # Sort for deterministic comparison
        result = sorted(
            [{"category": r.get("一级品类名称") or r.get("product$categoryName"),
              "sales": r.get("销售金额") or r.get("salesAmount")}
             for r in response.items],
            key=lambda x: x["category"]
        )

        # Verify CTE injection happened
        sql = response.sql
        assert "WITH _pivot_domain_transport" in sql
        assert "INNER JOIN _pivot_domain_transport" in sql

        # Oracle
        oracle_sql = """
            SELECT p.category_name, SUM(f.sales_amount) as sales
            FROM fact_sales f
            LEFT JOIN dim_product p ON f.product_key = p.product_key
            WHERE p.category_name IN ('Electronics', 'Clothing')
            GROUP BY p.category_name
        """
        oracle_rows = sorted(
            [{"category": r["category_name"], "sales": r["sales"]}
             for r in _execute_oracle(db_path, oracle_sql)],
            key=lambda x: x["category"]
        )
        assert result == oracle_rows
        assert len(result) == 2

    def test_non_additive_count_distinct_parity(self, service_and_db):
        service, db_path = service_and_db
        plan = DomainTransportPlan(
            columns=("product$categoryName",),
            tuples=(("Electronics",),),
            threshold=0
        )
        request = SemanticQueryRequest(
            columns=["product$categoryName", "uniqueCustomers"],
            group_by=["product$categoryName"]
        )
        request.domain_transport_plan = plan
        response = service.query_model("FactSalesModel", request, mode="execute")
        assert response.error is None

        result = response.items
        assert len(result) == 1

        cat = result[0].get("一级品类名称") or result[0].get("product$categoryName")
        cnt = result[0].get("独立客户数") or result[0].get("uniqueCustomers")
        assert cat == "Electronics"
        assert cnt == 2  # Customer 100, 101

    def test_null_domain_member_parity(self, service_and_db):
        service, db_path = service_and_db
        plan = DomainTransportPlan(
            columns=("product$categoryName",),
            tuples=(("Electronics",), (None,)),
            threshold=0
        )
        request = SemanticQueryRequest(
            columns=["product$categoryName", "salesAmount"],
            group_by=["product$categoryName"]
        )
        request.domain_transport_plan = plan
        response = service.query_model("FactSalesModel", request, mode="execute")
        assert response.error is None

        result = sorted(
            [{"category": r.get("一级品类名称") or r.get("product$categoryName"),
              "sales": r.get("销售金额") or r.get("salesAmount")}
             for r in response.items],
            key=lambda x: str(x["category"])
        )

        oracle_sql = """
            SELECT p.category_name, SUM(f.sales_amount) as sales
            FROM fact_sales f
            LEFT JOIN dim_product p ON f.product_key = p.product_key
            WHERE p.category_name = 'Electronics' OR p.category_name IS NULL
            GROUP BY p.category_name
        """
        oracle_rows = sorted(
            [{"category": r["category_name"], "sales": r["sales"]}
             for r in _execute_oracle(db_path, oracle_sql)],
            key=lambda x: str(x["category"])
        )
        assert result == oracle_rows

    def test_security_isolation_system_slice(self, service_and_db):
        service, db_path = service_and_db
        plan = DomainTransportPlan(
            columns=("product$categoryName",),
            tuples=(("Electronics",), ("Clothing",)),
            threshold=0
        )
        request = SemanticQueryRequest(
            columns=["product$categoryName", "salesAmount"],
            group_by=["product$categoryName"],
            system_slice=[{"field": "customer$memberLevel", "op": "=", "value": "VIP"}]
        )
        request.domain_transport_plan = plan
        response = service.query_model("FactSalesModel", request, mode="execute")
        assert response.error is None

        # Clothing has customer 200 (VIP). Electronics has 100 (VIP), 101 (Normal).
        # Electronics VIP sales: 10 + 5 = 15. Clothing VIP sales: 30 + 15 = 45.
        result = sorted(
            [{"category": r.get("一级品类名称") or r.get("product$categoryName"),
              "sales": r.get("销售金额") or r.get("salesAmount")}
             for r in response.items],
            key=lambda x: x["category"]
        )

        oracle_sql = """
            SELECT p.category_name, SUM(f.sales_amount) as sales
            FROM fact_sales f
            LEFT JOIN dim_product p ON f.product_key = p.product_key
            LEFT JOIN dim_customer c ON f.customer_key = c.customer_key
            WHERE p.category_name IN ('Electronics', 'Clothing')
              AND c.member_level = 'VIP'
            GROUP BY p.category_name
        """
        oracle_rows = sorted(
            [{"category": r["category_name"], "sales": r["sales"]}
             for r in _execute_oracle(db_path, oracle_sql)],
            key=lambda x: x["category"]
        )
        assert result == oracle_rows

    def test_denied_columns_fail_closed(self, service_and_db):
        service, _ = service_and_db
        plan = DomainTransportPlan(
            columns=("product$categoryName",),
            tuples=(("Electronics",),),
            threshold=0
        )
        request = SemanticQueryRequest(
            columns=["product$categoryName", "salesAmount"],
            group_by=["product$categoryName"],
            denied_columns=[DeniedColumn(table="dim_product", column="category_name")]
        )
        request.domain_transport_plan = plan
        response = service.query_model("FactSalesModel", request, mode="execute")
        assert "not accessible" in response.error.lower()

    def test_size_fallback(self, service_and_db):
        """If domain <= threshold, injection should not happen."""
        service, _ = service_and_db
        plan = DomainTransportPlan(
            columns=("product$categoryName",),
            tuples=(("Electronics",),),
            threshold=500
        )

        request = SemanticQueryRequest(
            columns=["product$categoryName", "salesAmount"],
            group_by=["product$categoryName"]
        )
        request.domain_transport_plan = plan
        response = service.query_model("FactSalesModel", request, mode="execute")
        assert response.error is None

        # Verify CTE injection did NOT happen
        sql = response.sql
        assert "WITH _pivot_domain_transport" not in sql
        assert "INNER JOIN _pivot_domain_transport" not in sql

        # Verify result is filtered
        result = response.items
        assert len(result) == 1
        cat = result[0].get("一级品类名称") or result[0].get("product$categoryName")
        sales = result[0].get("销售金额") or result[0].get("salesAmount")
        assert cat == "Electronics"
        assert sales == 35.0  # (10 + 20 + 5)

    def test_unsupported_dialect_fail_closed(self, service_and_db):
        service, _ = service_and_db
        # Mock dialect to MySQL
        service._dialect = MySqlDialect()

        plan = DomainTransportPlan(
            columns=("product$categoryName",),
            tuples=(("Electronics",),),
            threshold=0
        )
        request = SemanticQueryRequest(
            columns=["product$categoryName", "salesAmount"],
            group_by=["product$categoryName"]
        )
        request.domain_transport_plan = plan
        response = service.query_model("FactSalesModel", request, mode="execute")
        assert PIVOT_DOMAIN_TRANSPORT_REFUSED in str(response.error)

    def test_domain_transport_plan_schema_isolation(self):
        # 1. Not in JSON schema
        schema = SemanticQueryRequest.model_json_schema()
        assert "domain_transport_plan" not in schema["properties"]

        # 2. Not populated from external JSON
        payload = {
            "columns": ["salesAmount"],
            "domain_transport_plan": {"some": "data"}
        }
        req = SemanticQueryRequest.model_validate(payload)
        assert "domain_transport_plan" not in req.model_dump()
        assert req.domain_transport_plan is None

    def test_domain_join_without_explicit_selection(self, service_and_db):
        service, db_path = service_and_db
        plan = DomainTransportPlan(
            columns=("product$categoryName",),
            tuples=(("Electronics",),),
            threshold=0
        )
        # CategoryName is NOT in columns, nor in group_by
        request = SemanticQueryRequest(
            columns=["salesAmount"],
        )
        request.domain_transport_plan = plan

        response = service.query_model("FactSalesModel", request, mode="execute")
        assert response.error is None

        # It should compute total sales ONLY for Electronics, which is 35.0
        result = response.items
        assert len(result) == 1
        sales = result[0].get("销售金额") or result[0].get("salesAmount")
        assert sales == 35.0

        # Verify CTE injection and implicit join
        sql = response.sql
        assert "WITH _pivot_domain_transport" in sql
        assert "LEFT JOIN dim_product" in sql

        oracle_sql = """
            SELECT SUM(f.sales_amount) as sales
            FROM fact_sales f
            LEFT JOIN dim_product p ON f.product_key = p.product_key
            WHERE p.category_name = 'Electronics'
        """
        oracle_rows = _execute_oracle(db_path, oracle_sql)
        assert sales == oracle_rows[0]["sales"]
