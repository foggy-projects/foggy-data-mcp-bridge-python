"""Tests for inline aggregate expression support.

Python now supports Java-aligned inline aggregate expressions, including
conditional aggregates such as ``sum(if(...))`` that lower to ``CASE WHEN``.
"""

import pytest

from foggy.dataset_model.semantic import SemanticQueryService
from foggy.mcp_spi import SemanticQueryRequest
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


def _normalize_sql_whitespace(sql: str) -> str:
    """Collapse repeated whitespace so assertions focus on SQL semantics."""
    return " ".join(sql.split())


class TestInlineExpression:
    """Test inline aggregate expression parsing in column names."""

    def test_parse_sum_expression(self, service):
        """'sum(salesAmount) as totalSales' should produce SUM(t.sales_amount) AS `totalSales`."""
        request = SemanticQueryRequest(
            columns=["orderStatus", "sum(salesAmount) as totalSales"]
        )
        sql = _build_sql(service, request)
        select_part = sql.split("FROM")[0].upper()
        assert "SUM(" in select_part
        # Should not produce a warning for this column
        response = service.query_model("FactSalesModel", request, mode="validate")
        assert not any("sum(salesAmount)" in w for w in (response.warnings or []))

    def test_parse_count_expression(self, service):
        """'count(orderId) as cnt' should produce COUNT(t.order_id) AS `cnt`."""
        request = SemanticQueryRequest(
            columns=["orderStatus", "count(orderId) as cnt"]
        )
        sql = _build_sql(service, request)
        select_part = sql.split("FROM")[0].upper()
        assert "COUNT(" in select_part

    def test_parse_avg_expression(self, service):
        """'avg(salesAmount) as avgSales' should produce AVG(t.sales_amount) AS `avgSales`."""
        request = SemanticQueryRequest(
            columns=["orderStatus", "avg(salesAmount) as avgSales"]
        )
        sql = _build_sql(service, request)
        select_part = sql.split("FROM")[0].upper()
        assert "AVG(" in select_part

    def test_simple_column_not_expression(self, service):
        """'orderId' is a plain dimension, not an expression."""
        request = SemanticQueryRequest(columns=["orderId"])
        sql = _build_sql(service, request)
        # Should appear as a simple column reference
        assert "t.order_id" in sql
        response = service.query_model("FactSalesModel", request, mode="validate")
        assert len(response.warnings or []) == 0

    def test_dimension_reference_not_expression(self, service):
        """'product$caption' is a dimension join reference, not an expression."""
        request = SemanticQueryRequest(columns=["product$caption"])
        sql = _build_sql(service, request)
        assert "dp.product_name" in sql
        response = service.query_model("FactSalesModel", request, mode="validate")
        assert len(response.warnings or []) == 0

    def test_parse_count_distinct_expression(self, service):
        """'count_distinct(orderId) as uniqueOrders' should produce COUNT(DISTINCT ...)."""
        request = SemanticQueryRequest(
            columns=["orderStatus", "count_distinct(orderId) as uniqueOrders"]
        )
        sql = _build_sql(service, request)
        select_part = sql.split("FROM")[0].upper()
        assert "COUNT(DISTINCT" in select_part

    def test_parse_max_expression(self, service):
        """'max(salesAmount) as maxSales' should produce MAX(t.sales_amount)."""
        request = SemanticQueryRequest(
            columns=["orderStatus", "max(salesAmount) as maxSales"]
        )
        sql = _build_sql(service, request)
        select_part = sql.split("FROM")[0].upper()
        assert "MAX(" in select_part

    def test_parse_min_expression(self, service):
        """'min(salesAmount) as minSales' should produce MIN(t.sales_amount)."""
        request = SemanticQueryRequest(
            columns=["orderStatus", "min(salesAmount) as minSales"]
        )
        sql = _build_sql(service, request)
        select_part = sql.split("FROM")[0].upper()
        assert "MIN(" in select_part

    def test_known_measure_uses_default_aggregation(self, service):
        """A known measure name like 'salesAmount' uses its model-defined aggregation (SUM)."""
        request = SemanticQueryRequest(columns=["orderStatus", "salesAmount"])
        sql = _build_sql(service, request)
        select_part = sql.split("FROM")[0].upper()
        assert "SUM(" in select_part
        assert "SALES_AMOUNT" in select_part

    def test_sum_if_constant_lowered_to_case_when(self, service):
        request = SemanticQueryRequest(
            columns=["orderStatus", "sum(if(orderStatus == 'COMPLETED', 1, 0)) as completedRows"]
        )
        sql = _build_sql(service, request)
        select_part = _normalize_sql_whitespace(sql.split("FROM")[0]).upper()
        assert "SUM(CASE WHEN" in select_part
        assert "THEN 1 ELSE 0 END" in select_part
        assert "T.ORDER_STATUS = 'COMPLETED'" in select_part

    def test_sum_if_measure_lowered_to_case_when(self, service):
        request = SemanticQueryRequest(
            columns=["orderStatus", "sum(if(orderStatus == 'COMPLETED', salesAmount, 0)) as completedSales"]
        )
        sql = _build_sql(service, request)
        select_part = _normalize_sql_whitespace(sql.split("FROM")[0]).upper()
        assert "SUM(CASE WHEN" in select_part
        assert "THEN T.SALES_AMOUNT ELSE 0 END" in select_part
        assert "T.ORDER_STATUS = 'COMPLETED'" in select_part

    def test_avg_if_null_lowered_to_case_when(self, service):
        request = SemanticQueryRequest(
            columns=["orderStatus", "avg(if(orderStatus == 'COMPLETED', salesAmount, null)) as avgCompletedSales"]
        )
        sql = _build_sql(service, request)
        select_part = _normalize_sql_whitespace(sql.split("FROM")[0]).upper()
        assert "AVG(CASE WHEN" in select_part
        assert "THEN T.SALES_AMOUNT ELSE NULL END" in select_part

    def test_count_if_null_lowered_to_case_when(self, service):
        request = SemanticQueryRequest(
            columns=["orderStatus", "count(if(orderStatus == 'COMPLETED', 1, null)) as completedCount"]
        )
        sql = _build_sql(service, request)
        select_part = _normalize_sql_whitespace(sql.split("FROM")[0]).upper()
        assert "COUNT(CASE WHEN" in select_part
        assert "THEN 1 ELSE NULL END" in select_part

    def test_if_expression_supports_multi_conditions(self, service):
        request = SemanticQueryRequest(
            columns=[
                "orderStatus",
                "sum(if(orderStatus == 'COMPLETED' && paymentMethod == 'ALIPAY', salesAmount, 0)) as completedAlipaySales",
            ]
        )
        sql = _build_sql(service, request)
        select_part = _normalize_sql_whitespace(sql.split("FROM")[0]).upper()
        assert "CASE WHEN T.ORDER_STATUS = 'COMPLETED' AND T.PAYMENT_METHOD = 'ALIPAY'" in select_part

    def test_if_expression_keeps_join_field_access(self, service):
        request = SemanticQueryRequest(
            columns=[
                "product$categoryName",
                "sum(if(product$categoryName == '电子产品', salesAmount, 0)) as electronicsSales",
            ]
        )
        sql = _build_sql(service, request)
        normalized_sql = _normalize_sql_whitespace(sql)
        assert "LEFT JOIN dim_product" in normalized_sql
        assert "dp.category_name = '电子产品'" in normalized_sql
