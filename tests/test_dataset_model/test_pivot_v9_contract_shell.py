import pytest
from pydantic import ValidationError

from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp.schemas.tool_config_loader import get_tool_config_loader
from foggy.dataset_model.semantic.pivot.flat_executor import PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON
from foggy.mcp_spi import SemanticQueryRequest
from foggy.mcp_spi.accessor import build_query_request
from foggy.mcp_spi.semantic import PivotMetricItem


def _pivot_payload() -> dict:
    return {
        "rows": [
            "product$categoryName",
            {
                "field": "product$subCategoryName",
                "limit": 2,
                "orderBy": [{"field": "salesAmount", "dir": "desc"}],
            },
        ],
        "metrics": [
            "salesAmount",
            {
                "name": "categoryShare",
                "type": "parentShare",
                "of": "salesAmount",
                "level": "product$subCategoryName",
                "parentLevel": "product$categoryName",
                "axis": "rows",
            },
            {
                "name": "firstMonthRatio",
                "type": "baselineRatio",
                "of": "salesAmount",
                "level": "salesDate$month",
                "baseline": "first",
                "axis": "rows",
                "orderBy": [{"field": "salesDate$month", "dir": "asc"}],
            },
        ],
        "properties": ["product$brandName"],
        "options": {"rowSubtotals": True, "grandTotal": True},
        "outputFormat": "tree",
    }


def test_pivot_request_parses_string_and_object_metrics() -> None:
    request = SemanticQueryRequest(pivot=_pivot_payload())

    assert request.pivot is not None
    assert request.pivot.rows[0] == "product$categoryName"
    assert request.pivot.rows[1].field == "product$subCategoryName"
    assert request.pivot.rows[1].limit == 2
    assert request.pivot.metrics[0] == "salesAmount"
    assert isinstance(request.pivot.metrics[1], PivotMetricItem)
    assert request.pivot.metrics[1].type == "parentShare"
    assert request.pivot.metrics[1].parent_level == "product$categoryName"
    assert request.pivot.metrics[2].type == "baselineRatio"
    assert request.pivot.options.row_subtotals is True
    assert request.pivot.output_format == "tree"


def test_pivot_metric_item_rejects_expr_contract() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SemanticQueryRequest(
            pivot={
                "metrics": [
                    {
                        "name": "badMetric",
                        "type": "expr",
                        "of": "salesAmount",
                        "expr": "CELL_AT(...)",
                    }
                ]
            }
        )

    assert "extra_forbidden" in str(exc_info.value)


def test_build_query_request_transfers_pivot_payload() -> None:
    request = build_query_request({"pivot": _pivot_payload()})

    assert request.pivot is not None
    assert request.pivot.metrics[0] == "salesAmount"
    assert request.pivot.metrics[1].name == "categoryShare"


def test_query_model_pivot_fails_closed_before_sql_generation() -> None:
    service = SemanticQueryService()
    service.register_model(create_fact_sales_model())
    request = SemanticQueryRequest(pivot=_pivot_payload())

    response = service.query_model("FactSalesModel", request, mode="validate")

    assert PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON in response.error


def test_build_query_with_governance_pivot_fails_closed() -> None:
    service = SemanticQueryService()
    service.register_model(create_fact_sales_model())
    request = SemanticQueryRequest(pivot=_pivot_payload())

    with pytest.raises(NotImplementedError) as exc_info:
        service.build_query_with_governance("FactSalesModel", request)

    assert PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON in str(exc_info.value)


def test_query_model_v3_schema_exposes_pivot_contract_and_guards() -> None:
    tool = get_tool_config_loader().get_tool("dataset.query_model")
    assert tool is not None

    schema = tool.inputSchema
    payload_schema = schema["properties"]["payload"]
    pivot_schema = payload_schema["properties"]["pivot"]
    metric_schema = schema["definitions"]["pivotMetricItem"]

    assert pivot_schema["additionalProperties"] is False
    assert "metrics" in pivot_schema["required"]
    assert metric_schema["additionalProperties"] is False
    assert metric_schema["required"] == ["name", "type", "of"]
    assert metric_schema["properties"]["type"]["enum"] == [
        "native",
        "parentShare",
        "baselineRatio",
    ]
    assert metric_schema["properties"]["axis"]["enum"] == ["rows"]
    assert "expr" not in metric_schema["properties"]

    not_required_sets = [
        tuple(item["not"]["required"])
        for item in payload_schema["allOf"]
        if "not" in item and "required" in item["not"]
    ]
    assert ("pivot", "columns") in not_required_sets
    assert ("pivot", "timeWindow") in not_required_sets
