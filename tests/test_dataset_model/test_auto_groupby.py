"""Tests for auto GROUP BY behavior in SemanticQueryService._build_query().

When columns contain aggregated measures mixed with dimensions,
GROUP BY should be auto-generated for all non-aggregated dimension columns.
"""

import pytest

from foggy.dataset_model.semantic import SemanticQueryService
from foggy.mcp.spi import SemanticQueryRequest
from foggy.demo.models.ecommerce_models import create_fact_sales_model


@pytest.fixture
def service():
    """Create a SemanticQueryService with the FactSalesModel registered."""
    svc = SemanticQueryService()
    svc.register_model(create_fact_sales_model())
    return svc


def _build_sql(service: SemanticQueryService, request: SemanticQueryRequest) -> str:
    """Helper: build SQL via validate mode and return the SQL string."""
    response = service.query_model("FactSalesModel", request, mode="validate")
    assert response.error is None, f"Unexpected error: {response.error}"
    assert response.sql is not None, "Expected SQL in response"
    return response.sql


class TestAutoGroupBy:
    """Test auto GROUP BY generation when mixing dimensions and measures."""

    def test_auto_groupby_single_dimension(self, service):
        """columns=[orderStatus, salesAmount] should GROUP BY t.order_status."""
        request = SemanticQueryRequest(columns=["orderStatus", "salesAmount"])
        sql = _build_sql(service, request)
        assert "GROUP BY" in sql
        assert "t.order_status" in sql.split("GROUP BY")[1]

    def test_auto_groupby_multi_dimension(self, service):
        """columns=[orderStatus, paymentMethod, salesAmount] should GROUP BY both dims."""
        request = SemanticQueryRequest(
            columns=["orderStatus", "paymentMethod", "salesAmount"]
        )
        sql = _build_sql(service, request)
        group_part = sql.split("GROUP BY")[1]
        assert "t.order_status" in group_part
        assert "t.payment_method" in group_part

    def test_auto_groupby_with_dimension_join(self, service):
        """columns=[product$categoryName, salesAmount] should GROUP BY dp.category_name."""
        request = SemanticQueryRequest(
            columns=["product$categoryName", "salesAmount"]
        )
        sql = _build_sql(service, request)
        assert "GROUP BY" in sql
        assert "dp.category_name" in sql.split("GROUP BY")[1]

    def test_auto_groupby_no_aggregation(self, service):
        """columns=[orderId, orderStatus] (no measures) should NOT generate GROUP BY."""
        request = SemanticQueryRequest(columns=["orderId", "orderStatus"])
        sql = _build_sql(service, request)
        assert "GROUP BY" not in sql

    def test_explicit_groupby_overrides(self, service):
        """Explicit group_by prevents auto GROUP BY; only the explicit columns appear."""
        request = SemanticQueryRequest(
            columns=["orderStatus", "paymentMethod", "salesAmount"],
            group_by=["orderStatus"],
        )
        sql = _build_sql(service, request)
        group_part = sql.split("GROUP BY")[1]
        assert "t.order_status" in group_part
        # paymentMethod should NOT be in GROUP BY since explicit groupby was provided
        assert "t.payment_method" not in group_part

    def test_auto_groupby_mixed_measures(self, service):
        """Multiple measures with a single dimension should still auto GROUP BY."""
        request = SemanticQueryRequest(
            columns=["orderStatus", "salesAmount", "quantity", "profitAmount"]
        )
        sql = _build_sql(service, request)
        assert "GROUP BY" in sql
        group_part = sql.split("GROUP BY")[1]
        assert "t.order_status" in group_part

    def test_case_sensitivity_agg(self, service):
        """Aggregation detection works regardless of case (SUM vs sum)."""
        # The model defines AggregationType.SUM which resolves to uppercase.
        # This test verifies the generated SQL has a valid aggregation wrapper.
        request = SemanticQueryRequest(columns=["orderStatus", "salesAmount"])
        sql = _build_sql(service, request)
        # SUM should appear in the SELECT clause
        select_part = sql.split("FROM")[0].upper()
        assert "SUM(" in select_part

    def test_auto_groupby_with_join_dimension_id(self, service):
        """product$id mixed with measure should auto GROUP BY the id column."""
        request = SemanticQueryRequest(columns=["product$id", "salesAmount"])
        sql = _build_sql(service, request)
        assert "GROUP BY" in sql
        group_part = sql.split("GROUP BY")[1]
        assert "dp.product_key" in group_part

    def test_auto_groupby_with_join_caption(self, service):
        """product$caption mixed with measure should auto GROUP BY the caption column."""
        request = SemanticQueryRequest(columns=["product$caption", "salesAmount"])
        sql = _build_sql(service, request)
        assert "GROUP BY" in sql
        group_part = sql.split("GROUP BY")[1]
        assert "dp.product_name" in group_part

    def test_auto_groupby_multiple_join_dims(self, service):
        """Multiple joined dimensions with a measure should all appear in GROUP BY."""
        request = SemanticQueryRequest(
            columns=["product$categoryName", "customer$city", "salesAmount"]
        )
        sql = _build_sql(service, request)
        assert "GROUP BY" in sql
        group_part = sql.split("GROUP BY")[1]
        assert "dp.category_name" in group_part
        assert "dc.city" in group_part

    def test_auto_groupby_count_distinct(self, service):
        """COUNT_DISTINCT measure should trigger auto GROUP BY."""
        request = SemanticQueryRequest(columns=["orderStatus", "uniqueCustomers"])
        sql = _build_sql(service, request)
        assert "GROUP BY" in sql
        select_part = sql.split("FROM")[0].upper()
        assert "COUNT(DISTINCT" in select_part

    def test_no_groupby_only_measures(self, service):
        """Only measures, no dimensions: should have aggregation but no GROUP BY."""
        request = SemanticQueryRequest(columns=["salesAmount", "quantity"])
        sql = _build_sql(service, request)
        # All columns are measures with aggregation, but no dimension columns
        # selected_dims list will be empty so no GROUP BY
        assert "GROUP BY" not in sql

    def test_auto_groupby_preserves_select_order(self, service):
        """The SELECT clause should have columns in the requested order."""
        request = SemanticQueryRequest(
            columns=["salesAmount", "orderStatus"]
        )
        sql = _build_sql(service, request)
        select_part = sql.split("FROM")[0]
        sum_pos = select_part.upper().find("SUM(")
        status_pos = select_part.find("order_status")
        assert sum_pos < status_pos, "salesAmount should come before orderStatus in SELECT"

    def test_auto_groupby_with_fact_and_join_dims(self, service):
        """Mix of fact-table dimension and join dimension with a measure."""
        request = SemanticQueryRequest(
            columns=["orderStatus", "product$brand", "salesAmount"]
        )
        sql = _build_sql(service, request)
        assert "GROUP BY" in sql
        group_part = sql.split("GROUP BY")[1]
        assert "t.order_status" in group_part
        assert "dp.brand" in group_part

    def test_auto_groupby_generates_left_join(self, service):
        """When a joined dimension is selected, LEFT JOIN should be generated."""
        request = SemanticQueryRequest(
            columns=["product$categoryName", "salesAmount"]
        )
        sql = _build_sql(service, request)
        assert "LEFT JOIN" in sql
        assert "dim_product" in sql
