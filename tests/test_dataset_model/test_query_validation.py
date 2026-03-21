"""Tests for query validation (mode='validate') in SemanticQueryService.

Validation mode builds the SQL but does not execute it, returning
the generated SQL, column metadata, and any warnings.
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


class TestQueryValidation:
    """Test query validation (mode='validate')."""

    def test_validate_returns_sql(self, service):
        """mode='validate' should return sql without executing."""
        request = SemanticQueryRequest(columns=["orderStatus", "salesAmount"])
        response = service.query_model("FactSalesModel", request, mode="validate")
        assert response.error is None
        assert response.sql is not None
        assert "SELECT" in response.sql
        assert "FROM fact_sales" in response.sql
        # No data should be returned in validate mode
        assert response.data == []

    def test_validate_unknown_model(self, service):
        """Querying a non-existent model should return an error."""
        request = SemanticQueryRequest(columns=["salesAmount"])
        response = service.query_model("NonExistentModel", request, mode="validate")
        assert response.error is not None
        assert "not found" in response.error.lower()

    def test_validate_unknown_column(self, service):
        """An unknown column name should produce a warning."""
        request = SemanticQueryRequest(columns=["orderStatus", "totallyBogusColumn"])
        response = service.query_model("FactSalesModel", request, mode="validate")
        assert response.sql is not None
        assert len(response.warnings) > 0
        assert any("totallyBogusColumn" in w for w in response.warnings)

    def test_validate_no_columns(self, service):
        """Empty columns should select all visible dimensions and measures."""
        request = SemanticQueryRequest(columns=[])
        response = service.query_model("FactSalesModel", request, mode="validate")
        assert response.error is None
        assert response.sql is not None
        # Should include visible dimensions and measures in SELECT
        select_part = response.sql.split("FROM")[0]
        # Check that at least one dimension and one measure are selected
        assert "order_status" in select_part or "order_id" in select_part
        assert "SUM(" in select_part.upper() or "COUNT(" in select_part.upper()

    def test_validate_with_filter(self, service):
        """Filter conditions should appear in the generated SQL."""
        request = SemanticQueryRequest(
            columns=["orderStatus", "salesAmount"],
            slice=[{"column": "orderStatus", "operator": "=", "value": "COMPLETED"}],
        )
        response = service.query_model("FactSalesModel", request, mode="validate")
        assert response.error is None
        assert response.sql is not None
        assert "WHERE" in response.sql

    def test_validate_with_limit(self, service):
        """LIMIT should appear in the generated SQL."""
        request = SemanticQueryRequest(
            columns=["orderStatus", "salesAmount"],
            limit=50,
        )
        response = service.query_model("FactSalesModel", request, mode="validate")
        assert response.error is None
        assert response.sql is not None
        assert "LIMIT 50" in response.sql

    def test_validate_returns_columns_metadata(self, service):
        """Validation response should include column metadata."""
        request = SemanticQueryRequest(columns=["orderStatus", "salesAmount"])
        response = service.query_model("FactSalesModel", request, mode="validate")
        assert response.error is None
        assert len(response.columns) == 2

    def test_validate_returns_metrics(self, service):
        """Validation response should include timing metrics."""
        request = SemanticQueryRequest(columns=["orderStatus", "salesAmount"])
        response = service.query_model("FactSalesModel", request, mode="validate")
        assert response.error is None
        # After Java alignment, timing is in debug.durationMs and metrics property
        assert "duration_ms" in response.metrics

    def test_validate_with_order_by(self, service):
        """ORDER BY should appear in the generated SQL."""
        request = SemanticQueryRequest(
            columns=["orderStatus", "salesAmount"],
            order_by=[{"column": "salesAmount", "direction": "DESC"}],
        )
        response = service.query_model("FactSalesModel", request, mode="validate")
        assert response.error is None
        assert response.sql is not None
        assert "ORDER BY" in response.sql
        assert "DESC" in response.sql

    def test_validate_default_limit_applied(self, service):
        """When no limit is specified, the default limit should be applied."""
        request = SemanticQueryRequest(columns=["orderStatus", "salesAmount"])
        response = service.query_model("FactSalesModel", request, mode="validate")
        assert response.error is None
        assert response.sql is not None
        assert "LIMIT" in response.sql
