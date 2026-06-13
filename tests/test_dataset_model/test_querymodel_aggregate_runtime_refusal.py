"""Runtime/compiler refusal tests for unsupported aggregate relation carriers."""

import pytest

from foggy.dataset_model.aggregate_join import AGGREGATE_JOIN_UNSUPPORTED_CODE
from foggy.dataset_model.impl.model import (
    AggregateRelationConditionDef,
    AggregateRelationDef,
    AggregateRelationFilterDef,
    AggregateRelationMeasureDef,
)
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import (
    create_fact_order_model,
    create_fact_sales_model,
)
from foggy.mcp_spi import SemanticQueryRequest


def _order_model_with_aggregate_relation():
    model = create_fact_order_model().model_copy(deep=True)
    model.aggregate_relations = [
        AggregateRelationDef(
            left_model="FactOrderModel",
            right_model="FactSalesModel",
            alias="salesAgg",
            group_by=["orderId"],
            filters=[
                AggregateRelationFilterDef(
                    model="FactSalesModel",
                    field="orderStatus",
                    op="=",
                    value="PAID",
                )
            ],
            measures=[
                AggregateRelationMeasureDef(
                    model="FactSalesModel",
                    field="salesAmount",
                    aggregation="SUM",
                    alias="salesAmount",
                )
            ],
            conditions=[
                AggregateRelationConditionDef(
                    left_model="FactOrderModel",
                    left_field="orderId",
                    right_model="FactSalesModel",
                    right_field="orderId",
                )
            ],
        )
    ]
    return model


def _service_with(model):
    service = SemanticQueryService()
    service.register_model(model)
    return service


def _service_with_registered_aggregate_relation():
    service = SemanticQueryService()
    service.register_model(_order_model_with_aggregate_relation())
    service.register_model(create_fact_sales_model())
    return service


def test_query_model_refuses_aggregate_relations_when_rhs_model_is_missing():
    model = _order_model_with_aggregate_relation()
    service = _service_with(model)

    response = service.query_model(
        "FactOrderModel",
        SemanticQueryRequest(columns=["totalAmount"], limit=10),
        mode="validate",
    )

    assert response.sql is None
    assert response.error is not None
    assert AGGREGATE_JOIN_UNSUPPORTED_CODE in response.error
    assert "right model is not registered" in response.error
    assert "fact_order" not in response.error
    assert response.error_detail == {
        "code": AGGREGATE_JOIN_UNSUPPORTED_CODE,
        "carrierCount": 1,
        "model": "FactOrderModel",
    }


@pytest.mark.parametrize(
    ("request_kwargs", "expected_marker"),
    [
        ({"group_by": ["orderId"]}, "groupBy"),
        ({"having": [{"field": "salesAmount", "op": ">", "value": 0}]}, "having"),
        (
            {
                "post_aggregate_calculations": [
                    {"name": "salesRatio", "expression": "salesAmount / totalAmount"}
                ]
            },
            "post stages",
        ),
        (
            {
                "post_aggregate_calculations": [
                    {"name": "salesRatio", "expression": "salesAmount / totalAmount"}
                ],
                "post_slice": [{"field": "salesRatio", "op": ">", "value": 0}],
            },
            "post stages",
        ),
        (
            {
                "time_window": {
                    "field": "orderDate",
                    "grain": "month",
                    "comparison": "yoy",
                    "targetMetrics": ["salesAmount"],
                }
            },
            "timeWindow",
        ),
    ],
    ids=[
        "group-by",
        "having",
        "post-aggregate-calculation",
        "post-slice",
        "time-window",
    ],
)
def test_query_model_refuses_aggregate_relation_broader_request_stages(
    request_kwargs,
    expected_marker,
):
    service = _service_with_registered_aggregate_relation()

    response = service.query_model(
        "FactOrderModel",
        SemanticQueryRequest(
            columns=["orderId", "salesAmount"],
            limit=10,
            **request_kwargs,
        ),
        mode="validate",
    )

    assert response.sql is None
    assert response.error is not None
    assert AGGREGATE_JOIN_UNSUPPORTED_CODE in response.error
    assert expected_marker in response.error
    assert "fact_order" not in response.error
    assert "fact_sales" not in response.error
    assert response.error_detail == {
        "code": AGGREGATE_JOIN_UNSUPPORTED_CODE,
        "carrierCount": 1,
        "model": "FactOrderModel",
    }


def test_internal_build_query_refuses_aggregate_relation_pivot_before_sql_generation():
    model = _order_model_with_aggregate_relation()
    service = _service_with_registered_aggregate_relation()

    with pytest.raises(ValueError) as exc_info:
        service._build_query(
            model,
            SemanticQueryRequest(
                pivot={
                    "outputFormat": "flat",
                    "rows": ["orderId"],
                    "metrics": ["salesAmount"],
                },
            ),
        )

    error = str(exc_info.value)
    assert AGGREGATE_JOIN_UNSUPPORTED_CODE in error
    assert "pivot" in error
    assert "fact_order" not in error
    assert "fact_sales" not in error


def test_build_query_with_governance_refuses_missing_rhs_model():
    model = _order_model_with_aggregate_relation()
    service = _service_with(model)

    with pytest.raises(ValueError) as exc_info:
        service.build_query_with_governance(
            "FactOrderModel",
            SemanticQueryRequest(columns=["orderId"], limit=10),
        )

    error = str(exc_info.value)
    assert AGGREGATE_JOIN_UNSUPPORTED_CODE in error
    assert "right model is not registered" in error
    assert "fact_order" not in error


def test_internal_build_query_refuses_missing_rhs_model_directly():
    model = _order_model_with_aggregate_relation()
    service = _service_with(model)

    with pytest.raises(ValueError) as exc_info:
        service._build_query(model, SemanticQueryRequest(columns=["orderId"], limit=10))

    error = str(exc_info.value)
    assert AGGREGATE_JOIN_UNSUPPORTED_CODE in error
    assert "right model is not registered" in error
    assert "fact_order" not in error


@pytest.mark.asyncio
async def test_query_model_async_refuses_missing_rhs_model():
    model = _order_model_with_aggregate_relation()
    service = _service_with(model)

    response = await service.query_model_async(
        "FactOrderModel",
        SemanticQueryRequest(columns=["orderId"], limit=10),
        mode="validate",
    )

    assert response.sql is None
    assert response.error is not None
    assert AGGREGATE_JOIN_UNSUPPORTED_CODE in response.error
    assert "right model is not registered" in response.error
    assert "fact_order" not in response.error
    assert response.error_detail == {
        "code": AGGREGATE_JOIN_UNSUPPORTED_CODE,
        "carrierCount": 1,
        "model": "FactOrderModel",
    }


def test_normal_query_model_still_compiles_without_aggregate_relations():
    model = create_fact_order_model()
    service = _service_with(model)

    response = service.query_model(
        "FactOrderModel",
        SemanticQueryRequest(columns=["totalAmount"], limit=10),
        mode="validate",
    )

    assert response.error is None
    assert response.sql is not None
    assert "SELECT" in response.sql
    assert "fact_order" in response.sql
