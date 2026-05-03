"""P4 Cascade Generate Semantics Validation Tests.

Verifies the correct structural generation of the Cascade Generate CTE SQL.
"""

import pytest
from foggy.dataset.db.executor import SQLiteExecutor
from foggy.dataset_model.semantic.pivot.cascade_detector import PIVOT_CASCADE_NON_ADDITIVE_REJECTED
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest, PivotRequest
from foggy.dataset_model.impl.model import DbModelMeasureImpl

import pytest
from foggy.dataset.db.executor import SQLiteExecutor
from foggy.dataset_model.semantic.pivot.cascade_detector import PIVOT_CASCADE_NON_ADDITIVE_REJECTED
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest, PivotRequest
from foggy.dataset_model.impl.model import DbModelMeasureImpl

import sqlite3

@pytest.fixture
def sqlite_service(tmp_path):
    db_path = str(tmp_path / "test_semantics.sqlite")
    conn = sqlite3.connect(db_path)
    # Seed specific data for testing semantic boundaries
    conn.executescript("""
        CREATE TABLE dim_product (
            product_key INTEGER PRIMARY KEY,
            category_name TEXT,
            sub_category_id INTEGER
        );
        CREATE TABLE fact_sales (
            product_key INTEGER,
            customer_key INTEGER,
            sales_amount REAL
        );
        -- Parent 1: Cat A (Total: 100). Sub 1: 90, Sub 2: 10
        INSERT INTO dim_product VALUES (1, 'Cat A', 11);
        INSERT INTO dim_product VALUES (2, 'Cat A', 12);
        INSERT INTO fact_sales VALUES (1, 100, 90.0);
        INSERT INTO fact_sales VALUES (2, 100, 10.0);

        -- Parent 2: Cat B (Total: 80). Sub 3: 40, Sub 4: 40
        INSERT INTO dim_product VALUES (3, 'Cat B', 13);
        INSERT INTO dim_product VALUES (4, 'Cat B', 14);
        INSERT INTO fact_sales VALUES (3, 100, 40.0);
        INSERT INTO fact_sales VALUES (4, 100, 40.0);

        -- Parent 3: Cat C (Total: 50). Sub 5: 50
        INSERT INTO dim_product VALUES (5, 'Cat C', 15);
        INSERT INTO fact_sales VALUES (5, 100, 50.0);

        -- Parent 4: Cat NULL (Total: 10). Sub 6: 10
        INSERT INTO dim_product VALUES (6, NULL, 16);
        INSERT INTO fact_sales VALUES (6, 100, 10.0);

        -- Parent 5: Cat D (Total: NULL). Sub 7: NULL
        INSERT INTO dim_product VALUES (7, 'Cat D', 17);
        INSERT INTO fact_sales VALUES (7, 100, NULL);
    """)
    conn.close()
    executor = SQLiteExecutor(db_path)
    service = SemanticQueryService(executor=executor, enable_cache=False)
    service.register_model(create_fact_sales_model())
    return service

def test_parent_rank_unaffected_by_child_limit(sqlite_service):
    # Cat A has 100, Cat B has 80.
    # If child limit is 1, Cat A keeps Sub 1 (90). Cat B keeps Sub 3 (40).
    # If parent rank was calculated AFTER child limit, Cat A would still be 90, Cat B 40.
    # Wait, both parent ranks would be calculated correctly regardless.
    # But let's verify we get Cat A and Cat B when parent limit is 2.
    payload = {
        "outputFormat": "flat",
        "rows": [
            {"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]},
            {"field": "product$subCategoryId", "limit": 1, "orderBy": ["-salesAmount"]},
        ],
        "metrics": ["salesAmount"]
    }
    req = SemanticQueryRequest(pivot=PivotRequest(**payload))
    res = sqlite_service.query_model("FactSalesModel", req, mode="execute")
    assert not res.error

    # Expect Cat A and Cat B
    categories = {item["product$categoryName"] for item in res.items}
    assert categories == {"Cat A", "Cat B"}
    assert len(res.items) == 2

def test_parent_having_before_child_rank(sqlite_service):
    # Parent having salesAmount > 85
    # Only Cat A (100) survives.
    payload = {
        "outputFormat": "flat",
        "rows": [
            {"field": "product$categoryName", "having": {"metric": "salesAmount", "op": ">", "value": 85}, "limit": 2, "orderBy": ["-salesAmount"]},
            {"field": "product$subCategoryId", "limit": 1, "orderBy": ["-salesAmount"]},
        ],
        "metrics": ["salesAmount"]
    }
    req = SemanticQueryRequest(pivot=PivotRequest(**payload))
    res = sqlite_service.query_model("FactSalesModel", req, mode="execute")
    assert not res.error

    categories = {item["product$categoryName"] for item in res.items}
    assert categories == {"Cat A"}

def test_child_having_not_affecting_parent(sqlite_service):
    # Child having salesAmount > 45
    # Cat A has Sub 1 (90) which survives.
    # Cat B has Sub 3 (40) and Sub 4 (40) which are BOTH dropped.
    # Cat C has Sub 5 (50) which survives.
    # But because Cat A and Cat B are top 2 parents (100, 80), Cat B is still selected as a parent, but yields 0 children!
    # So the final result should only have Cat A!
    payload = {
        "outputFormat": "flat",
        "rows": [
            {"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]},
            {"field": "product$subCategoryId", "having": {"metric": "salesAmount", "op": ">", "value": 45}, "limit": 1, "orderBy": ["-salesAmount"]},
        ],
        "metrics": ["salesAmount"]
    }
    req = SemanticQueryRequest(pivot=PivotRequest(**payload))
    res = sqlite_service.query_model("FactSalesModel", req, mode="execute")
    assert not res.error

    categories = {item["product$categoryName"] for item in res.items}
    # Cat B's children were filtered, but Cat C shouldn't be promoted to top 2 because parent domain is fixed.
    assert categories == {"Cat A"}

def test_null_tie_breaking(sqlite_service):
    payload = {
        "outputFormat": "flat",
        "rows": [
            {"field": "product$categoryName", "limit": 5, "orderBy": ["salesAmount"]},
            {"field": "product$subCategoryId", "limit": 1, "orderBy": ["salesAmount"]},
        ],
        "metrics": ["salesAmount"]
    }
    req = SemanticQueryRequest(pivot=PivotRequest(**payload))
    res = sqlite_service.query_model("FactSalesModel", req, mode="execute")
    assert not res.error

    # NULL metric goes to the end
    last_item = res.items[-1]
    assert last_item["product$categoryName"] == "Cat D"
    assert last_item["salesAmount"] is None

def test_unsupported_dialect_fallback_rejection(sqlite_service):
    # Simulate an unsupported dialect (e.g. MSSQL or Oracle)
    payload = {
        "outputFormat": "flat",
        "rows": [
            {"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]},
            {"field": "product$subCategoryId", "limit": 1, "orderBy": ["-salesAmount"]},
        ],
        "metrics": ["salesAmount"]
    }
    req = SemanticQueryRequest(pivot=PivotRequest(**payload))

    # Temporarily override dialect
    original_dialect = sqlite_service._dialect
    class MockDialect:
        def name(self):
            return "mssql"

    sqlite_service._dialect = MockDialect()
    try:
        res = sqlite_service.query_model("FactSalesModel", req, mode="execute")

        assert res.error is not None
        assert "Cascade Staged SQL" in res.error and "not supported" in res.error.lower()
    finally:
        sqlite_service._dialect = original_dialect

def test_non_additive_cascade_rejection(sqlite_service):
    table_model = sqlite_service._models.get("FactSalesModel")
    table_model.measures["uniqueProducts"] = DbModelMeasureImpl(name="uniqueProducts", column="product_key", aggregation="count_distinct")

    payload = {
        "outputFormat": "flat",
        "rows": [
            {"field": "product$categoryName", "limit": 2, "orderBy": ["-uniqueProducts"]},
            {"field": "product$subCategoryId", "limit": 1, "orderBy": ["-uniqueProducts"]},
        ],
        "metrics": ["uniqueProducts"]
    }
    req = SemanticQueryRequest(pivot=PivotRequest(**payload))
    res = sqlite_service.query_model("FactSalesModel", req, mode="execute")

    assert res.error is not None
    assert PIVOT_CASCADE_NON_ADDITIVE_REJECTED in res.error
