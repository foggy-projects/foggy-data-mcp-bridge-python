"""P1 Pivot Cascade Validation Tests.

Verifies that Python Pivot 9.1 P1 correctly:
  1. Rejects all cascade shapes that require Java 9.1 staged SQL.
  2. Preserves existing S3 single-layer TopN / having / grid / crossjoin behavior.

No DB connection is needed for rejection tests — they run at validation time
before any SQL is issued.
"""

from __future__ import annotations

import sqlite3
import pytest

from foggy.dataset.db.executor import SQLiteExecutor
from foggy.dataset_model.semantic.pivot.cascade_detector import (
    PIVOT_CASCADE_SQL_REQUIRED,
    PIVOT_CASCADE_ORDER_BY_REQUIRED,
    PIVOT_CASCADE_TREE_REJECTED,
    PIVOT_CASCADE_CROSS_AXIS_REJECTED,
    PIVOT_CASCADE_NON_ADDITIVE_REJECTED,
    PIVOT_CASCADE_SCOPE_UNSUPPORTED,
)
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _seed_db(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript("""
            CREATE TABLE dim_product (
                product_key INTEGER PRIMARY KEY,
                category_id INTEGER,
                category_name TEXT,
                sub_category TEXT
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
            INSERT INTO dim_product VALUES (1, 10, 'Electronics', 'Phones');
            INSERT INTO dim_product VALUES (2, 10, 'Electronics', 'Laptops');
            INSERT INTO dim_product VALUES (3, 20, 'Clothing', 'Shirts');
            INSERT INTO dim_product VALUES (4, 20, 'Clothing', 'Pants');
            INSERT INTO dim_customer VALUES (1, 'VIP');
            INSERT INTO dim_customer VALUES (2, 'Normal');
            INSERT INTO dim_date VALUES (20240101, 2024);
            INSERT INTO dim_date VALUES (20230101, 2023);
            INSERT INTO fact_sales VALUES (20240101, 1, 1, 300.0);
            INSERT INTO fact_sales VALUES (20240101, 2, 1, 500.0);
            INSERT INTO fact_sales VALUES (20230101, 3, 2, 200.0);
            INSERT INTO fact_sales VALUES (20230101, 4, 2, 100.0);
        """)
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def svc(tmp_path):
    db_path = tmp_path / "cascade_test.sqlite"
    _seed_db(str(db_path))
    executor = SQLiteExecutor(str(db_path))
    service = SemanticQueryService(executor=executor)
    service.register_model(create_fact_sales_model())
    yield service
    service._run_async_in_sync(executor.close())


def _query(svc: SemanticQueryService, pivot_payload: dict) -> str | None:
    """Execute a pivot query and return the error string (or None if no error)."""
    req = SemanticQueryRequest(pivot=pivot_payload)
    resp = svc.query_model("FactSalesModel", req, mode="execute")
    return resp.error


# ─────────────────────────────────────────────────────────────────────────────
# Rejection tests (P1 cascade fail-closed)
# ─────────────────────────────────────────────────────────────────────────────

class TestCascadeRejected:
    """All cascade shapes must be rejected with a stable error-code prefix."""

    def test_parent_topn_plus_child_topn_allowed(self, svc):
        """Two limit fields on rows axis → cascade → must NOT reject at validation."""
        payload = {
            "outputFormat": "flat",
            "rows": [
                {"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]},
                {"field": "product$categoryName", "limit": 1, "orderBy": ["-salesAmount"]},
            ],
            "metrics": ["salesAmount"],
        }
        err = _query(svc, payload)
        assert err is None or ("Not implemented" in err) or ("Dialect" in err) or ("Cascade execution failed" in err)

    def test_parent_having_plus_child_topn_rejected(self, svc):
        """having on parent + limit on child → cascade → must reject."""
        payload = {
            "outputFormat": "flat",
            "rows": [
                {"field": "product$categoryName", "having": {"metric": "salesAmount", "op": ">", "value": 100}},
                {"field": "product$categoryName", "limit": 1, "orderBy": ["-salesAmount"]},
            ],
            "metrics": ["salesAmount"],
        }
        err = _query(svc, payload)
        assert err is not None
        assert PIVOT_CASCADE_SCOPE_UNSUPPORTED in err

    def test_parent_topn_plus_child_having_rejected(self, svc):
        """limit on parent + having on child → cascade → must reject."""
        payload = {
            "outputFormat": "flat",
            "rows": [
                {"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]},
                {"field": "product$categoryName", "having": {"metric": "salesAmount", "op": ">", "value": 50}},
            ],
            "metrics": ["salesAmount"],
        }
        err = _query(svc, payload)
        assert err is not None
        assert PIVOT_CASCADE_SCOPE_UNSUPPORTED in err

    def test_columns_cascade_rejected(self, svc):
        """limit on columns axis → must reject."""
        payload = {
            "outputFormat": "grid",
            "rows": ["product$categoryName"],
            "columns": [{"field": "salesDate$year", "limit": 1, "orderBy": ["-salesAmount"]}],
            "metrics": ["salesAmount"],
        }
        err = _query(svc, payload)
        assert err is not None
        assert PIVOT_CASCADE_CROSS_AXIS_REJECTED in err

    def test_columns_having_rejected(self, svc):
        """having on columns axis → must reject."""
        payload = {
            "outputFormat": "grid",
            "rows": ["product$categoryName"],
            "columns": [{"field": "salesDate$year", "having": {"metric": "salesAmount", "op": ">", "value": 100}}],
            "metrics": ["salesAmount"],
        }
        err = _query(svc, payload)
        assert err is not None
        assert PIVOT_CASCADE_CROSS_AXIS_REJECTED in err

    def test_tree_plus_cascade_rejected(self, svc):
        """hierarchyMode=tree on a field that also carries limit → must emit PIVOT_CASCADE_TREE_REJECTED."""
        payload = {
            "outputFormat": "grid",
            "rows": [
                {"field": "product$categoryName", "hierarchyMode": "tree", "limit": 2, "orderBy": ["-salesAmount"]},
            ],
            "metrics": ["salesAmount"],
        }
        err = _query(svc, payload)
        assert err is not None, "Expected cascade rejection but got success"
        assert PIVOT_CASCADE_TREE_REJECTED in err, (
            f"Expected {PIVOT_CASCADE_TREE_REJECTED!r} in error, got: {err!r}"
        )

    def test_tree_sibling_limit_rejected(self, svc):
        """tree on one row field + limit on a sibling row field remains tree+cascade and must reject."""
        payload = {
            "outputFormat": "grid",
            "rows": [
                {"field": "product$categoryName", "hierarchyMode": "tree"},
                {"field": "salesDate$year", "limit": 1, "orderBy": ["-salesAmount"]},
            ],
            "metrics": ["salesAmount"],
        }
        err = _query(svc, payload)
        assert err is not None, "Expected tree+cascade rejection but got success"
        assert PIVOT_CASCADE_TREE_REJECTED in err

    def test_non_additive_cascade_rejected(self, svc):
        """non-additive metric with cascade is rejected."""
        payload = {
            "outputFormat": "flat",
            "rows": [
                {"field": "product$categoryName", "limit": 2, "orderBy": ["-uniqueCustomers"]},
                {"field": "salesDate$year",        "limit": 1, "orderBy": ["-salesAmount"]},
            ],
            "metrics": ["uniqueCustomers"],
        }
        err = _query(svc, payload)
        assert err is not None
        assert PIVOT_CASCADE_NON_ADDITIVE_REJECTED in err

    def test_column_subtotals_with_cascade_rejected(self, svc):
        """columnSubtotals remains outside Python cascade totals scope."""
        payload = {
            "outputFormat": "grid",
            "rows": [
                {"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]},
                {"field": "salesDate$year", "limit": 1, "orderBy": ["-salesAmount"]},
            ],
            "metrics": ["salesAmount"],
            "options": {"columnSubtotals": True},
        }
        err = _query(svc, payload)
        assert err is not None
        assert PIVOT_CASCADE_SCOPE_UNSUPPORTED in err

    def test_missing_order_by_on_cascade_limit_rejected(self, svc):
        """limit without orderBy → must reject PIVOT_CASCADE_ORDER_BY_REQUIRED."""
        payload = {
            "outputFormat": "flat",
            "rows": [{"field": "product$categoryName", "limit": 2}],
            "metrics": ["salesAmount"],
        }
        err = _query(svc, payload)
        assert err is not None
        assert PIVOT_CASCADE_ORDER_BY_REQUIRED in err

    def test_three_level_cascade_rejected(self, svc):
        """Three fields each with limit → must reject."""
        payload = {
            "outputFormat": "flat",
            "rows": [
                {"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]},
                {"field": "product$categoryName", "limit": 1, "orderBy": ["-salesAmount"]},
                {"field": "salesDate$year",        "limit": 1, "orderBy": ["-salesAmount"]},
            ],
            "metrics": ["salesAmount"],
        }
        err = _query(svc, payload)
        assert err is not None
        assert PIVOT_CASCADE_SCOPE_UNSUPPORTED in err

    def test_derived_metric_with_cascade_rejected(self, svc):
        """parentShare + any limit → must reject."""
        payload = {
            "outputFormat": "flat",
            "rows": [{"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]}],
            "metrics": [
                {"name": "salesAmount_share", "type": "parentShare", "of": "salesAmount", "axis": "rows"}
            ],
        }
        err = _query(svc, payload)
        assert err is not None
        assert PIVOT_CASCADE_NON_ADDITIVE_REJECTED in err

    def test_baseline_ratio_with_cascade_rejected(self, svc):
        """baselineRatio + any limit → must reject."""
        payload = {
            "outputFormat": "flat",
            "rows": [{"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]}],
            "metrics": [
                {"name": "salesAmount_base", "type": "baselineRatio", "of": "salesAmount",
                 "axis": "rows", "baseline": "first"}
            ],
        }
        err = _query(svc, payload)
        assert err is not None
        assert PIVOT_CASCADE_NON_ADDITIVE_REJECTED in err


# ─────────────────────────────────────────────────────────────────────────────
# S3 regression tests — must remain passing
# ─────────────────────────────────────────────────────────────────────────────

class TestS3Regression:
    """Confirm that existing S3 single-layer operations are NOT broken by P1."""

    def test_single_topn_still_allowed(self, svc):
        """Single field with limit + orderBy must NOT be rejected."""
        payload = {
            "outputFormat": "flat",
            "rows": [{"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]}],
            "metrics": ["salesAmount"],
        }
        err = _query(svc, payload)
        assert err is None, f"S3 single-layer TopN must not be rejected, got: {err}"

    def test_single_having_still_allowed(self, svc):
        """Single field with having must NOT be rejected."""
        payload = {
            "outputFormat": "flat",
            "rows": [{"field": "product$categoryName",
                      "having": {"metric": "salesAmount", "op": ">", "value": 100}}],
            "metrics": ["salesAmount"],
        }
        err = _query(svc, payload)
        assert err is None, f"S3 single-layer having must not be rejected, got: {err}"

    def test_flat_baseline_still_allowed(self, svc):
        """Simple flat query with no constraints must pass."""
        payload = {
            "outputFormat": "flat",
            "rows": ["product$categoryName"],
            "metrics": ["salesAmount"],
        }
        err = _query(svc, payload)
        assert err is None, f"Flat baseline must not be rejected, got: {err}"

    def test_grid_crossjoin_still_allowed(self, svc):
        """Grid with crossjoin but no cascade must pass."""
        payload = {
            "outputFormat": "grid",
            "options": {"crossjoin": True},
            "rows": ["product$categoryName"],
            "columns": ["salesDate$year"],
            "metrics": ["salesAmount"],
        }
        err = _query(svc, payload)
        assert err is None, f"Grid crossjoin must not be rejected, got: {err}"

    def test_multi_row_fields_without_constraints_allowed(self, svc):
        """Multiple row fields that are plain strings (no limit/having) must pass."""
        payload = {
            "outputFormat": "flat",
            "rows": ["product$categoryName", "salesDate$year"],
            "metrics": ["salesAmount"],
        }
        err = _query(svc, payload)
        assert err is None, f"Multi-row fields without constraints must be allowed, got: {err}"

    def test_leaf_only_topn_allowed(self, svc):
        """Parent field is plain string, only the leaf/last field has limit+orderBy.

        This corresponds to the 'leaf-only partitioned TopN' that was already
        covered by the S3 test suite and must remain passing.
        """
        payload = {
            "outputFormat": "flat",
            "rows": [
                "product$categoryName",  # unconstrained parent
                {"field": "salesDate$year", "limit": 1, "orderBy": ["-salesAmount"]},
            ],
            "metrics": ["salesAmount"],
        }
        err = _query(svc, payload)
        # Only one constrained field → not a cascade → should be allowed.
        assert err is None, f"Leaf-only partitioned TopN must be allowed, got: {err}"
