import pytest

from foggy.dataset_model.semantic import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest


@pytest.fixture
def service():
    svc = SemanticQueryService()
    svc.register_model(create_fact_sales_model())
    return svc


def _build_sql(service: SemanticQueryService, request: SemanticQueryRequest) -> str:
    response = service.query_model("FactSalesModel", request, mode="validate")
    assert response.error is None, f"Unexpected error: {response.error}"
    assert response.sql is not None
    return response.sql


def _over_clause(sql: str) -> str:
    over_idx = sql.upper().index("OVER")
    return sql[over_idx:]


def test_hidden_partition_dependency_is_projected_for_outer_cte(service):
    request = SemanticQueryRequest(
        columns=["product$caption", "salesAmount"],
        group_by=["product$caption", "product$categoryName"],
        calculated_fields=[
            {
                "name": "salesRank",
                "expression": "ROW_NUMBER()",
                "partition_by": ["product$categoryName"],
                "window_order_by": [{"field": "salesAmount", "dir": "desc"}],
            }
        ],
    )

    sql = _build_sql(service, request)
    over_clause = _over_clause(sql)

    assert '"product$categoryName"' in sql
    assert '"product$categoryName"' in over_clause
    assert '"销售金额"' in over_clause
    assert "dp.category_name" not in over_clause
    assert "t.sales_amount" not in over_clause


def test_hidden_partition_dependency_must_be_grouped_in_aggregate_query(service):
    request = SemanticQueryRequest(
        columns=["product$caption", "salesAmount"],
        calculated_fields=[
            {
                "name": "salesRank",
                "expression": "ROW_NUMBER()",
                "partition_by": ["product$categoryName"],
                "window_order_by": [{"field": "salesAmount", "dir": "desc"}],
            }
        ],
    )

    response = service.query_model("FactSalesModel", request, mode="validate")

    assert response.error is not None
    assert "WINDOW_DEPENDENCY_GROUPING_ERROR" in response.error
