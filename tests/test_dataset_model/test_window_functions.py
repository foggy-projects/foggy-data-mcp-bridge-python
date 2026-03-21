"""Tests for calculatedFields + window function support.

Covers:
  - CalculatedFieldDef model (agg, partition_by, window_order_by, window_frame)
  - Window function SQL generation (RANK, ROW_NUMBER, LAG, AVG OVER ...)
  - SemanticQueryService._build_query() integration with calculatedFields
  - Payload passthrough from MCP layer

Aligned with Java AdvancedAnalyticsTest.
"""

import pytest

from foggy.dataset_model.semantic.service import SemanticQueryService, QueryBuildResult
from foggy.dataset_model.impl.model import DbTableModelImpl
from foggy.dataset_model.definitions.query_request import CalculatedFieldDef
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest


# ==================== Fixtures ====================


@pytest.fixture
def sales_model() -> DbTableModelImpl:
    return create_fact_sales_model()


@pytest.fixture
def service(sales_model: DbTableModelImpl) -> SemanticQueryService:
    svc = SemanticQueryService()
    svc.register_model(sales_model)
    return svc


def _build_sql(service: SemanticQueryService, model_name: str, request: SemanticQueryRequest) -> str:
    """Helper: build query in validate mode and return the SQL string."""
    response = service.query_model(model_name, request, mode="validate")
    assert response.error is None, f"Query build failed: {response.error}"
    assert response.sql is not None
    return response.sql


# ==================== CalculatedFieldDef Model Tests ====================


class TestCalculatedFieldDef:
    """Test CalculatedFieldDef with window function fields."""

    def test_basic_fields(self):
        cf = CalculatedFieldDef(name="net", expression="salesAmount - discountAmount")
        assert cf.name == "net"
        assert cf.expression == "salesAmount - discountAmount"
        assert cf.agg is None
        assert cf.partition_by == []
        assert cf.window_order_by == []
        assert cf.window_frame is None
        assert not cf.is_window_function()

    def test_with_agg(self):
        cf = CalculatedFieldDef(name="totalNet", expression="salesAmount - discountAmount", agg="SUM")
        assert cf.agg == "SUM"
        assert not cf.is_window_function()

    def test_is_window_function_with_partition(self):
        cf = CalculatedFieldDef(
            name="salesRank", expression="RANK()",
            partition_by=["product$categoryName"],
            window_order_by=[{"field": "salesAmount", "dir": "desc"}],
        )
        assert cf.is_window_function()

    def test_is_window_function_order_only(self):
        cf = CalculatedFieldDef(
            name="rn", expression="ROW_NUMBER()",
            window_order_by=[{"field": "salesAmount", "dir": "asc"}],
        )
        assert cf.is_window_function()

    def test_is_window_function_partition_only(self):
        cf = CalculatedFieldDef(
            name="partSum", expression="salesAmount",
            agg="SUM", partition_by=["product$categoryName"],
        )
        assert cf.is_window_function()

    def test_window_frame(self):
        cf = CalculatedFieldDef(
            name="ma7", expression="AVG(salesAmount)",
            partition_by=["product$caption"],
            window_order_by=[{"field": "salesDate$caption", "dir": "asc"}],
            window_frame="ROWS BETWEEN 6 PRECEDING AND CURRENT ROW",
        )
        assert cf.is_window_function()
        assert cf.window_frame == "ROWS BETWEEN 6 PRECEDING AND CURRENT ROW"

    def test_extra_fields_allowed(self):
        """Extra fields from Java payload (like 'caption') should not cause errors."""
        cf = CalculatedFieldDef(
            name="test", expression="RANK()",
            caption="排名",  # extra field from Java
        )
        assert cf.name == "test"


# ==================== Window Function SQL Generation ====================


class TestWindowFunctionSQL:
    """Test SQL generation for window functions via _build_query()."""

    def test_rank_over_partition_and_order(self, service: SemanticQueryService):
        """RANK() + partitionBy + orderBy → RANK() OVER (PARTITION BY ... ORDER BY ...)."""
        request = SemanticQueryRequest(
            columns=["product$categoryName"],
            calculated_fields=[{
                "name": "salesRank",
                "expression": "RANK()",
                "partition_by": ["product$categoryName"],
                "window_order_by": [{"field": "salesAmount", "dir": "desc"}],
            }],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        sql_upper = sql.upper()
        assert "RANK() OVER (" in sql.upper() or "RANK() OVER(" in sql.upper()
        assert "PARTITION BY" in sql_upper
        assert "ORDER BY" in sql_upper
        assert "DESC" in sql_upper

    def test_row_number_window(self, service: SemanticQueryService):
        """ROW_NUMBER() window function."""
        request = SemanticQueryRequest(
            columns=["product$caption"],
            calculated_fields=[{
                "name": "rn",
                "expression": "ROW_NUMBER()",
                "window_order_by": [{"field": "salesAmount", "dir": "desc"}],
            }],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "ROW_NUMBER()" in sql
        assert "OVER" in sql.upper()

    def test_dense_rank_window(self, service: SemanticQueryService):
        """DENSE_RANK() window function."""
        request = SemanticQueryRequest(
            columns=["product$categoryName"],
            calculated_fields=[{
                "name": "denseRank",
                "expression": "DENSE_RANK()",
                "partition_by": ["product$categoryName"],
                "window_order_by": [{"field": "salesAmount", "dir": "desc"}],
            }],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "DENSE_RANK()" in sql
        assert "OVER" in sql.upper()

    def test_lag_window_function(self, service: SemanticQueryService):
        """LAG(salesAmount, 1) — field name inside function should be resolved."""
        request = SemanticQueryRequest(
            columns=["product$caption", "salesDate$caption"],
            calculated_fields=[{
                "name": "prevAmount",
                "expression": "LAG(salesAmount, 1)",
                "partition_by": ["product$caption"],
                "window_order_by": [{"field": "salesDate$caption", "dir": "asc"}],
            }],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        sql_upper = sql.upper()
        assert "LAG(" in sql_upper
        assert "OVER" in sql_upper
        # salesAmount should be resolved to actual column
        assert "SALES_AMOUNT" in sql_upper

    def test_avg_with_window_frame(self, service: SemanticQueryService):
        """AVG(salesAmount) + windowFrame → moving average."""
        request = SemanticQueryRequest(
            columns=["product$caption", "salesDate$caption"],
            calculated_fields=[{
                "name": "ma7",
                "expression": "salesAmount",
                "agg": "AVG",
                "partition_by": ["product$caption"],
                "window_order_by": [{"field": "salesDate$caption", "dir": "asc"}],
                "window_frame": "ROWS BETWEEN 6 PRECEDING AND CURRENT ROW",
            }],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        sql_upper = sql.upper()
        assert "AVG(" in sql_upper
        assert "OVER" in sql_upper
        assert "ROWS BETWEEN 6 PRECEDING AND CURRENT ROW" in sql_upper

    def test_sum_window_partition_only(self, service: SemanticQueryService):
        """SUM(salesAmount) with only PARTITION BY (no ORDER BY)."""
        request = SemanticQueryRequest(
            columns=["product$categoryName"],
            calculated_fields=[{
                "name": "categoryTotal",
                "expression": "salesAmount",
                "agg": "SUM",
                "partition_by": ["product$categoryName"],
            }],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        sql_upper = sql.upper()
        assert "SUM(" in sql_upper
        assert "OVER" in sql_upper
        assert "PARTITION BY" in sql_upper
        # Should NOT have ORDER BY inside OVER
        over_idx = sql_upper.index("OVER")
        over_clause = sql_upper[over_idx:]
        closing = over_clause.index(")")
        over_content = over_clause[:closing]
        assert "ORDER BY" not in over_content


# ==================== Non-Window Calculated Fields ====================


class TestCalculatedFieldAggregation:
    """Test calculatedFields with agg but no window (pure aggregation)."""

    def test_sum_expression(self, service: SemanticQueryService):
        """agg=SUM + expression → SUM(resolved_expr)."""
        request = SemanticQueryRequest(
            columns=["product$categoryName"],
            calculated_fields=[{
                "name": "totalAmount",
                "expression": "salesAmount",
                "agg": "SUM",
            }],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        sql_upper = sql.upper()
        assert "SUM(" in sql_upper
        assert "OVER" not in sql_upper  # Not a window function

    def test_arithmetic_expression_with_agg(self, service: SemanticQueryService):
        """salesAmount - discountAmount with agg=SUM."""
        request = SemanticQueryRequest(
            columns=["product$categoryName"],
            calculated_fields=[{
                "name": "netAmount",
                "expression": "salesAmount - discountAmount",
                "agg": "SUM",
            }],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        sql_upper = sql.upper()
        assert "SUM(" in sql_upper
        # Both fields should be resolved
        assert "SALES_AMOUNT" in sql_upper
        assert "DISCOUNT_AMOUNT" in sql_upper

    def test_plain_expression_no_agg(self, service: SemanticQueryService):
        """Expression without agg — just resolved field references."""
        request = SemanticQueryRequest(
            columns=["product$caption"],
            calculated_fields=[{
                "name": "calc",
                "expression": "salesAmount",
            }],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        # Should have the resolved column, no aggregation wrapper
        assert "`calc`" in sql


# ==================== Integration Tests ====================


class TestCalculatedFieldIntegration:
    """Test calculatedFields integration with existing query features."""

    def test_window_does_not_go_to_group_by(self, service: SemanticQueryService):
        """Window function columns should trigger GROUP BY for dims but not appear in GROUP BY themselves."""
        request = SemanticQueryRequest(
            columns=["product$categoryName", "sum(salesAmount) as total"],
            calculated_fields=[{
                "name": "salesRank",
                "expression": "RANK()",
                "partition_by": ["product$categoryName"],
                "window_order_by": [{"field": "salesAmount", "dir": "desc"}],
            }],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        sql_upper = sql.upper()
        # Should have GROUP BY for the dimension
        assert "GROUP BY" in sql_upper
        # RANK() OVER ... should appear in SELECT, not in GROUP BY
        assert "RANK()" in sql
        # The group by clause should reference the dimension column, not RANK
        group_idx = sql_upper.index("GROUP BY")
        group_clause = sql_upper[group_idx:]
        assert "RANK" not in group_clause

    def test_mixed_columns_and_calculated(self, service: SemanticQueryService):
        """Mix regular columns with calculatedFields."""
        request = SemanticQueryRequest(
            columns=["product$caption", "salesAmount"],
            calculated_fields=[{
                "name": "rn",
                "expression": "ROW_NUMBER()",
                "window_order_by": [{"field": "salesAmount", "dir": "desc"}],
            }],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        sql_upper = sql.upper()
        # Regular columns present
        assert "PRODUCT_NAME" in sql_upper or "DP.PRODUCT_NAME" in sql_upper
        assert "SALES_AMOUNT" in sql_upper
        # Window function present
        assert "ROW_NUMBER()" in sql
        assert "OVER" in sql_upper

    def test_partition_by_join_dimension(self, service: SemanticQueryService):
        """partitionBy referencing a JOIN dimension like product$categoryName → LEFT JOIN + correct column."""
        request = SemanticQueryRequest(
            columns=["product$caption"],
            calculated_fields=[{
                "name": "catRank",
                "expression": "RANK()",
                "partition_by": ["product$categoryName"],
                "window_order_by": [{"field": "salesAmount", "dir": "desc"}],
            }],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        # Must have LEFT JOIN for dim_product
        assert "LEFT JOIN dim_product" in sql or "LEFT JOIN `dim_product`" in sql
        # partition by should reference the joined column
        assert "category_name" in sql.lower()

    def test_window_order_by_uses_resolved_column(self, service: SemanticQueryService):
        """windowOrderBy field names should be resolved to SQL columns."""
        request = SemanticQueryRequest(
            columns=["product$caption"],
            calculated_fields=[{
                "name": "amountRank",
                "expression": "RANK()",
                "window_order_by": [{"field": "salesAmount", "dir": "desc"}],
            }],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        # salesAmount should be resolved to t.sales_amount in ORDER BY within OVER
        over_idx = sql.upper().index("OVER")
        over_clause = sql[over_idx:]
        assert "sales_amount" in over_clause.lower()


# ==================== Payload Passthrough Tests ====================


class TestPayloadPassthrough:
    """Test that calculatedFields flows through the MCP payload pipeline."""

    def test_semantic_request_carries_calculated_fields(self):
        """SemanticQueryRequest should accept and carry calculated_fields."""
        request = SemanticQueryRequest(
            columns=["product$caption"],
            calculated_fields=[
                {"name": "rn", "expression": "ROW_NUMBER()",
                 "window_order_by": [{"field": "salesAmount", "dir": "desc"}]},
            ],
        )
        assert len(request.calculated_fields) == 1
        assert request.calculated_fields[0]["name"] == "rn"

    def test_v3_payload_to_accessor(self):
        """V3 payload with calculatedFields should be passed through LocalDatasetAccessor."""
        from foggy.mcp_spi import LocalDatasetAccessor

        class MockResolver:
            def query_model(self, model, request, mode, context):
                # Capture the request for assertion
                self.captured_request = request
                return type('Resp', (), {
                    'data': [], 'total': 0, 'sql': '', 'columns': [],
                    'error': None, 'warnings': [], 'metrics': {},
                })()

        resolver = MockResolver()
        accessor = LocalDatasetAccessor(resolver)

        payload = {
            "columns": ["product$caption"],
            "calculatedFields": [
                {"name": "rn", "expression": "ROW_NUMBER()",
                 "window_order_by": [{"field": "salesAmount", "dir": "desc"}]},
            ],
        }
        accessor.query_model("TestModel", payload)

        assert hasattr(resolver, 'captured_request')
        assert len(resolver.captured_request.calculated_fields) == 1
        assert resolver.captured_request.calculated_fields[0]["name"] == "rn"

    def test_empty_calculated_fields_default(self):
        """SemanticQueryRequest defaults to empty calculated_fields."""
        request = SemanticQueryRequest(columns=["x"])
        assert request.calculated_fields == []
