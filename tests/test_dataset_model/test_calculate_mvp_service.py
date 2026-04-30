"""v1.5.1 restricted CALCULATE MVP service-path tests."""

from foggy.dataset.dialects.mysql import MySqlDialect
from foggy.dataset.dialects.sqlite import SqliteDialect
from foggy.dataset_model.semantic import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest


def _service(dialect):
    svc = SemanticQueryService(dialect=dialect)
    svc.register_model(create_fact_sales_model())
    return svc


def test_service_calculate_context_lowers_remove_to_grouped_window() -> None:
    request = SemanticQueryRequest(
        columns=["customer$customerType", "totalShare"],
        group_by=["customer$customerType"],
        calculated_fields=[
            {
                "name": "totalShare",
                "expression": (
                    "SUM(salesAmount) / NULLIF(CALCULATE(SUM(salesAmount), "
                    "REMOVE(customer$customerType)), 0)"
                ),
            }
        ],
    )

    response = _service(SqliteDialect()).query_model(
        "FactSalesModel",
        request,
        mode="validate",
    )

    assert response.error is None
    assert response.sql is not None
    assert "SUM(SUM(t.sales_amount)) OVER ()" in response.sql
    assert "NULLIF(SUM(SUM(t.sales_amount)) OVER (), 0)" in response.sql
    assert "GROUP BY dc.customer_type" in response.sql


def test_service_calculate_rejects_mysql_window_unsupported() -> None:
    request = SemanticQueryRequest(
        columns=["customer$customerType", "totalShare"],
        group_by=["customer$customerType"],
        calculated_fields=[
            {
                "name": "totalShare",
                "expression": (
                    "SUM(salesAmount) / NULLIF(CALCULATE(SUM(salesAmount), "
                    "REMOVE(customer$customerType)), 0)"
                ),
            }
        ],
    )

    response = _service(MySqlDialect()).query_model(
        "FactSalesModel",
        request,
        mode="validate",
    )

    assert response.error is not None
    assert "CALCULATE_WINDOW_UNSUPPORTED" in response.error
