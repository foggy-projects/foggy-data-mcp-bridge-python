from pathlib import Path

import pytest
from pydantic import ValidationError

from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp.schemas.tool_config_loader import get_tool_config_loader
from foggy.dataset_model.semantic.pivot.flat_executor import PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON
from foggy.mcp_spi import SemanticQueryRequest
from foggy.mcp_spi.accessor import build_query_request
from foggy.mcp_spi.semantic import PivotMetricItem


_SCHEMA_DESC_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "foggy"
    / "mcp"
    / "schemas"
    / "descriptions"
)


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
        "columns": ["salesDate$month"],
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
                "axis": "columns",
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
    metrics_items_schema = pivot_schema["properties"]["metrics"]["items"]["oneOf"][1]
    parent_share_schema = metrics_items_schema["oneOf"][0]
    pivot_desc = pivot_schema["description"]

    assert "metrics" in pivot_schema["required"]
    assert parent_share_schema["required"] == ["name", "type", "of"]
    assert parent_share_schema["properties"]["type"]["enum"] == ["parentShare"]
    assert parent_share_schema["properties"]["axis"]["enum"] == ["rows"]
    assert "expr" not in parent_share_schema["properties"]




def test_query_model_description_variants_keep_python_pivot_boundaries() -> None:
    for file_name in [
        "query_model_v3.md",
        "query_model_v3_basic.md",
        "query_model_v3_no_vector.md",
    ]:
        text = (_SCHEMA_DESC_DIR / file_name).read_text(encoding="utf-8")

        assert "flat" in text or "grid" in text
        assert "parentShare" in text
        assert "baselineRatio" in text
        assert "CELL_AT" in text
        assert "AXIS_MEMBER" in text
