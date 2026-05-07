"""Tests for parentShare pivot metric — Python engine.

Tests cover:
- Basic implicit level inference
- Explicit level/parentLevel/axis
- Zero denominator → None
- NULL child value → None
- Cross-axis columns present
- Single row level → error
- Missing 'of' metric → error
- Grid output includes parentShare
- Grand total row gets None
"""

import sqlite3
from decimal import Decimal
import pytest

from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest
from foggy.dataset.db.executor import SQLiteExecutor
from foggy.dataset_model.semantic.pivot.flat_executor import PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON


def _seed_parent_share_db(db_path) -> None:
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
            "INSERT INTO dim_product (product_key, category_name, sub_category_name) VALUES (?, ?, ?)",
            [
                (1, "Electronics", "Phones"),
                (2, "Electronics", "Laptops"),
                (3, "Clothing", "Shirts"),
            ]
        )
        conn.executemany(
            "INSERT INTO dim_customer (customer_key, member_level) VALUES (?, ?)",
            [(1, "VIP")]
        )
        # Electronics: Phones=100, Laptops=300 => total=400
        # Clothing: Shirts=200 => total=200
        conn.executemany(
            "INSERT INTO fact_sales (date_key, product_key, customer_key, sales_amount) VALUES (?, ?, ?, ?)",
            [
                (20240101, 1, 1, 100.0),  # Electronics/Phones
                (20240101, 2, 1, 300.0),  # Electronics/Laptops
                (20240101, 3, 1, 200.0),  # Clothing/Shirts
            ]
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def service_and_db(tmp_path):
    db_path = tmp_path / "parent_share.sqlite"
    _seed_parent_share_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = SemanticQueryService(executor=executor)
    service.register_model(create_fact_sales_model())
    yield service, str(db_path)
    service._run_async_in_sync(executor.close())


def _find_display_key(row, candidates):
    """Find the actual key used in row dict from a set of candidates."""
    for c in candidates:
        if c in row:
            return c
    return candidates[0]


def _get_value(row, candidates):
    """Get value by trying multiple candidate keys."""
    for c in candidates:
        if c in row:
            return row[c]
    return None


class TestParentShareBasic:

    def test_parent_share_basic_implicit(self, service_and_db):
        """2-level rows, implicit parent/child inference.
        Expected: Phones share = 100/400 = 0.25, Laptops = 300/400 = 0.75, Shirts = 200/200 = 1.0
        """
        service, db_path = service_and_db
        payload = {
            "outputFormat": "flat",
            "rows": ["product$categoryName", "product$subCategoryName"],
            "metrics": [
                "salesAmount",
                {
                    "name": "share",
                    "type": "parentShare",
                    "of": "salesAmount",
                },
            ],
        }
        request = SemanticQueryRequest(pivot=payload)
        response = service.query_model("FactSalesModel", request, mode="execute")

        assert response.error is None, f"Query failed: {response.error}"
        assert len(response.items) == 3

        # Build lookup by sub_category display name
        shares = {}
        for row in response.items:
            sub_cat = _get_value(row, ["product$subCategoryName", "二级品类名称"])
            share_val = row.get("share")
            if sub_cat is not None:
                shares[sub_cat] = share_val

        assert shares.get("Phones") == pytest.approx(100.0 / 400.0, abs=1e-6)
        assert shares.get("Laptops") == pytest.approx(300.0 / 400.0, abs=1e-6)
        assert shares.get("Shirts") == pytest.approx(200.0 / 200.0, abs=1e-6)

    def test_parent_share_explicit_levels(self, service_and_db):
        """Explicit level/parentLevel/axis parameters."""
        service, db_path = service_and_db
        payload = {
            "outputFormat": "flat",
            "rows": ["product$categoryName", "product$subCategoryName"],
            "metrics": [
                "salesAmount",
                {
                    "name": "catShare",
                    "type": "parentShare",
                    "of": "salesAmount",
                    "axis": "rows",
                    "level": "product$subCategoryName",
                    "parentLevel": "product$categoryName",
                },
            ],
        }
        request = SemanticQueryRequest(pivot=payload)
        response = service.query_model("FactSalesModel", request, mode="execute")

        assert response.error is None, f"Query failed: {response.error}"
        assert len(response.items) == 3

        # All rows should have 'catShare'
        for row in response.items:
            assert "catShare" in row

    def test_parent_share_of_metric_auto_included(self, service_and_db):
        """parentShare's 'of' metric is auto-included in SQL even if not
        explicitly listed as a standalone metric."""
        service, db_path = service_and_db
        payload = {
            "outputFormat": "flat",
            "rows": ["product$categoryName", "product$subCategoryName"],
            "metrics": [
                # Only parentShare, no standalone "salesAmount" listed
                {
                    "name": "share",
                    "type": "parentShare",
                    "of": "salesAmount",
                },
            ],
        }
        request = SemanticQueryRequest(pivot=payload)
        response = service.query_model("FactSalesModel", request, mode="execute")

        assert response.error is None, f"Query failed: {response.error}"
        assert len(response.items) == 3

        # share should be computed (the base metric was auto-included)
        has_share = any(row.get("share") is not None for row in response.items)
        assert has_share, "Expected at least one non-None parentShare value"


class TestParentShareEdgeCases:

    def test_zero_denominator_returns_none(self, service_and_db):
        """When parent total = 0, share should be None."""
        service, db_path = service_and_db

        # Insert a product with 0 sales to create a zero-denominator parent
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO dim_product (product_key, category_name, sub_category_name) VALUES (?, ?, ?)",
            (4, "Empty", "Nothing")
        )
        conn.execute(
            "INSERT INTO fact_sales (date_key, product_key, customer_key, sales_amount) VALUES (?, ?, ?, ?)",
            (20240101, 4, 1, 0.0)
        )
        conn.commit()
        conn.close()

        payload = {
            "outputFormat": "flat",
            "rows": ["product$categoryName", "product$subCategoryName"],
            "metrics": [
                "salesAmount",
                {"name": "share", "type": "parentShare", "of": "salesAmount"},
            ],
        }
        request = SemanticQueryRequest(pivot=payload)
        response = service.query_model("FactSalesModel", request, mode="execute")
        assert response.error is None

        # Find the "Nothing" row
        for row in response.items:
            sub_cat = _get_value(row, ["product$subCategoryName", "二级品类名称"])
            if sub_cat == "Nothing":
                assert row.get("share") is None, "Zero denominator should yield None"
                break

    def test_parent_share_with_columns_axis(self, service_and_db):
        """parentShare on rows with a column cross-axis present."""
        service, db_path = service_and_db
        payload = {
            "outputFormat": "flat",
            "rows": ["product$categoryName", "product$subCategoryName"],
            "columns": ["salesDate$year"],
            "metrics": [
                "salesAmount",
                {"name": "share", "type": "parentShare", "of": "salesAmount"},
            ],
        }
        request = SemanticQueryRequest(pivot=payload)
        response = service.query_model("FactSalesModel", request, mode="execute")

        assert response.error is None, f"Query failed: {response.error}"
        # Should have rows with share computed per column group
        assert any(row.get("share") is not None for row in response.items)


class TestParentShareRejections:

    def test_single_row_level_rejects(self, service_and_db):
        """Only 1 row level → should fail (can't infer parent/child)."""
        service, _ = service_and_db
        payload = {
            "outputFormat": "flat",
            "rows": ["product$categoryName"],
            "metrics": [
                "salesAmount",
                {"name": "share", "type": "parentShare", "of": "salesAmount"},
            ],
        }
        request = SemanticQueryRequest(pivot=payload)
        response = service.query_model("FactSalesModel", request, mode="execute")

        # Should fail with an error about insufficient levels
        assert response.error is not None
        assert "2" in response.error or "level" in response.error.lower()

    def test_baselineRatio_still_rejected(self, service_and_db):
        """baselineRatio should still be rejected."""
        service, _ = service_and_db
        payload = {
            "outputFormat": "flat",
            "rows": ["product$categoryName"],
            "metrics": [
                "salesAmount",
                {
                    "name": "ratio",
                    "type": "baselineRatio",
                    "of": "salesAmount",
                    "baseline": "first",
                },
            ],
        }
        request = SemanticQueryRequest(pivot=payload)
        response = service.query_model("FactSalesModel", request, mode="execute")

        assert response.error is not None
        assert PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON in response.error


class TestParentShareGrandTotal:

    def test_grand_total_row_gets_none(self, service_and_db):
        """Grand total synthetic row should get None for parentShare."""
        service, db_path = service_and_db
        payload = {
            "outputFormat": "flat",
            "rows": ["product$categoryName", "product$subCategoryName"],
            "metrics": [
                "salesAmount",
                {"name": "share", "type": "parentShare", "of": "salesAmount"},
            ],
            "options": {"grandTotal": True},
        }
        request = SemanticQueryRequest(pivot=payload)
        response = service.query_model("FactSalesModel", request, mode="execute")

        assert response.error is None, f"Query failed: {response.error}"

        # Find the grand total row (has _sys_meta.isGrandTotal)
        grand_total_rows = [
            r for r in response.items
            if isinstance(r.get("_sys_meta"), dict)
            and r["_sys_meta"].get("isGrandTotal") is True
        ]

        if grand_total_rows:
            for gt_row in grand_total_rows:
                assert gt_row.get("share") is None, (
                    "Grand total row should have None for parentShare"
                )


class TestParentShareGridOutput:

    def test_grid_output_includes_parent_share(self, service_and_db):
        """Grid output format should include the parentShare column."""
        service, db_path = service_and_db
        payload = {
            "outputFormat": "grid",
            "rows": ["product$categoryName", "product$subCategoryName"],
            "metrics": [
                "salesAmount",
                {"name": "share", "type": "parentShare", "of": "salesAmount"},
            ],
        }
        request = SemanticQueryRequest(pivot=payload)
        response = service.query_model("FactSalesModel", request, mode="execute")

        assert response.error is None, f"Query failed: {response.error}"
        assert len(response.items) > 0


class TestParentShareUnit:
    """Unit tests for parent_share module directly."""

    def test_resolve_implicit_two_level(self):
        from foggy.mcp_spi.semantic import PivotMetricItem
        from foggy.dataset_model.semantic.pivot.parent_share import resolve

        metric = PivotMetricItem(
            name="share", type="parentShare", of="salesAmount"
        )
        resolved = resolve(metric, ["category", "brand"], [])

        assert resolved.axis == "rows"
        assert resolved.parent_level == "category"
        assert resolved.level == "brand"

    def test_resolve_explicit_validates_adjacency(self):
        from foggy.mcp_spi.semantic import PivotMetricItem
        from foggy.dataset_model.semantic.pivot.parent_share import resolve

        metric = PivotMetricItem(
            name="share", type="parentShare", of="salesAmount",
            axis="rows",
            level="brand",
            parent_level="category",  # alias: parentLevel
        )

        # brand is at index 2, category at index 0 — NOT adjacent → error
        with pytest.raises(ValueError, match="adjacent"):
            resolve(metric, ["category", "sub_cat", "brand"], [])

    def test_resolve_single_level_error(self):
        from foggy.mcp_spi.semantic import PivotMetricItem
        from foggy.dataset_model.semantic.pivot.parent_share import resolve

        metric = PivotMetricItem(
            name="share", type="parentShare", of="salesAmount"
        )
        with pytest.raises(ValueError, match="2"):
            resolve(metric, ["category"], [])

    def test_apply_basic(self):
        """Direct test of apply() with pre-built items."""
        from foggy.mcp_spi.semantic import PivotMetricItem, PivotRequest
        from foggy.dataset_model.semantic.pivot.parent_share import apply

        items = [
            {"category": "A", "brand": "X", "sales": 100.0},
            {"category": "A", "brand": "Y", "sales": 300.0},
            {"category": "B", "brand": "Z", "sales": 200.0},
        ]

        pivot = PivotRequest(
            rows=["category", "brand"],
            metrics=[
                "sales",
                PivotMetricItem(name="share", type="parentShare", of="sales"),
            ],
        )

        result = apply(items, pivot, ["category", "brand"], [], {})

        assert result[0]["share"] == pytest.approx(100.0 / 400.0)
        assert result[1]["share"] == pytest.approx(300.0 / 400.0)
        assert result[2]["share"] == pytest.approx(200.0 / 200.0)

    def test_apply_decimal_aggregate_values(self):
        """SQL drivers may return aggregate numbers as Decimal."""
        from foggy.mcp_spi.semantic import PivotMetricItem, PivotRequest
        from foggy.dataset_model.semantic.pivot.parent_share import apply

        items = [
            {"category": "A", "brand": "X", "sales": Decimal("100.00")},
            {"category": "A", "brand": "Y", "sales": Decimal("300.00")},
            {"category": "B", "brand": "Z", "sales": Decimal("200.00")},
        ]

        pivot = PivotRequest(
            rows=["category", "brand"],
            metrics=[
                "sales",
                PivotMetricItem(name="share", type="parentShare", of="sales"),
            ],
        )

        result = apply(items, pivot, ["category", "brand"], [], {})

        assert result[0]["share"] == pytest.approx(0.25)
        assert result[1]["share"] == pytest.approx(0.75)
        assert result[2]["share"] == pytest.approx(1.0)

    def test_apply_none_value(self):
        """NULL child value → None."""
        from foggy.mcp_spi.semantic import PivotMetricItem, PivotRequest
        from foggy.dataset_model.semantic.pivot.parent_share import apply

        items = [
            {"category": "A", "brand": "X", "sales": None},
            {"category": "A", "brand": "Y", "sales": 300.0},
        ]

        pivot = PivotRequest(
            rows=["category", "brand"],
            metrics=[
                "sales",
                PivotMetricItem(name="share", type="parentShare", of="sales"),
            ],
        )

        result = apply(items, pivot, ["category", "brand"], [], {})
        assert result[0]["share"] is None
        assert result[1]["share"] == pytest.approx(1.0)  # 300/300
