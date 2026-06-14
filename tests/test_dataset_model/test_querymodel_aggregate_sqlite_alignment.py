"""SQLite aggregate-relation parity tests for P0-82 through P0-89."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from foggy.dataset.db.executor import SQLiteExecutor
from foggy.dataset_model.aggregate_join import (
    AGGREGATE_JOIN_DENIED_SOURCE_COLUMN_CODE,
    AGGREGATE_JOIN_FIELD_ACCESS_DENIED_CODE,
    AGGREGATE_JOIN_GROUPBY_MISSING_RIGHT_KEY_CODE,
    AGGREGATE_JOIN_RUNTIME_FILTER_MISSING_CODE,
    AGGREGATE_JOIN_RUNTIME_FILTER_UNSAFE_CODE,
    AGGREGATE_JOIN_UNSUPPORTED_CODE,
)
from foggy.dataset_model.definitions.access import DbAccessDef, RowFilterType
from foggy.dataset_model.definitions.base import (
    AggregationType,
    ColumnType,
    DbColumnDef,
)
from foggy.dataset_model.impl.model import (
    AggregateRelationConditionDef,
    AggregateRelationDef,
    AggregateRelationFilterDef,
    AggregateRelationMeasureDef,
    DbModelMeasureImpl,
    DbTableModelImpl,
    DimensionJoinDef,
    DimensionPropertyDef,
)
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.mcp_spi import SemanticQueryRequest, SemanticRequestContext
from foggy.mcp_spi.semantic import DeniedColumn, FieldAccessDef

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_querymodel_aggregate_join_snapshot_parity.json"
)

ORDER_1 = "ORD20240101000001"
ORDER_2 = "ORD20240102000004"
TENANT_A = "TENANT_A"
TENANT_B = "TENANT_B"


def _case(case_id: str) -> dict[str, Any]:
    snapshot = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    for case in snapshot["cases"]:
        if case["id"] == case_id:
            return case
    raise AssertionError(f"missing Java aggregate join fixture case: {case_id}")


def _normal(sql: str) -> str:
    return " ".join(sql.split())


def _right_model() -> DbTableModelImpl:
    return DbTableModelImpl(
        name="FactSalesModel",
        source_table="fact_sales",
        columns={
            "orderId": DbColumnDef(name="order_id", column_type=ColumnType.STRING),
            "orderStatus": DbColumnDef(
                name="order_status",
                column_type=ColumnType.STRING,
            ),
            "paymentMethod": DbColumnDef(
                name="payment_method",
                column_type=ColumnType.STRING,
            ),
            "customerKey": DbColumnDef(
                name="customer_key",
                column_type=ColumnType.LONG,
            ),
            "quantity": DbColumnDef(
                name="quantity",
                column_type=ColumnType.DECIMAL,
            ),
            "unitPrice": DbColumnDef(
                name="unit_price",
                column_type=ColumnType.DECIMAL,
            ),
            "unitCost": DbColumnDef(
                name="unit_cost",
                column_type=ColumnType.DECIMAL,
            ),
            "discountAmount": DbColumnDef(
                name="discount_amount",
                column_type=ColumnType.DECIMAL,
            ),
            "costAmount": DbColumnDef(
                name="cost_amount",
                column_type=ColumnType.DECIMAL,
            ),
            "taxAmount": DbColumnDef(
                name="tax_amount",
                column_type=ColumnType.DECIMAL,
            ),
            "profitAmount": DbColumnDef(
                name="profit_amount",
                column_type=ColumnType.DECIMAL,
            ),
        },
        measures={
            "salesAmount": DbModelMeasureImpl(
                name="salesAmount",
                alias="salesAmount",
                column="sales_amount",
                aggregation=AggregationType.SUM,
            )
        },
    )


def _composite_right_model() -> DbTableModelImpl:
    model = _right_model()
    model.columns["storeKey"] = DbColumnDef(
        name="store_key",
        column_type=ColumnType.LONG,
    )
    return model


def _tenant_right_model() -> DbTableModelImpl:
    model = _right_model()
    model.columns["tenantId"] = DbColumnDef(
        name="tenant_id",
        column_type=ColumnType.STRING,
    )
    return model


def _rhs_dimension_filter_right_model() -> DbTableModelImpl:
    model = _right_model()
    model.columns["productKey"] = DbColumnDef(
        name="product_key",
        column_type=ColumnType.LONG,
    )
    model.dimension_joins.append(
        DimensionJoinDef(
            name="product",
            table_name="dim_product",
            foreign_key="product_key",
            primary_key="product_key",
            properties=[
                DimensionPropertyDef(
                    name="categoryId",
                    column="category_id",
                    caption="Category ID",
                )
            ],
        )
    )
    return model


def _rhs_nested_dimension_filter_right_model() -> DbTableModelImpl:
    model = _rhs_dimension_filter_right_model()
    model.dimension_joins.append(
        DimensionJoinDef(
            name="category",
            table_name="dim_category",
            foreign_key="category_key",
            primary_key="category_key",
            join_to="product",
            properties=[
                DimensionPropertyDef(
                    name="segment",
                    column="segment",
                    caption="Category Segment",
                )
            ],
        )
    )
    return model


def _store_dimension_right_model() -> DbTableModelImpl:
    return DbTableModelImpl(
        name="DimStoreModel",
        source_table="dim_store",
        columns={
            "storeId": DbColumnDef(name="store_id", column_type=ColumnType.STRING),
            "status": DbColumnDef(name="status", column_type=ColumnType.STRING),
        },
        measures={
            "areaSqm": DbModelMeasureImpl(
                name="areaSqm",
                alias="areaSqm",
                column="area_sqm",
                aggregation=AggregationType.SUM,
            )
        },
    )


def _left_model(
    *,
    name: str = "OrderSalesAggregateRelationQueryModel",
    alias: str | None = "fsByOrder",
    measures: list[AggregateRelationMeasureDef] | None = None,
    filters: list[AggregateRelationFilterDef] | None = None,
    group_by: list[str] | None = None,
    predefined_calculated_fields: list[dict[str, Any]] | None = None,
    access: DbAccessDef | None = None,
) -> DbTableModelImpl:
    return DbTableModelImpl(
        name=name,
        source_table="fact_order",
        access=access,
        predefined_calculated_fields=predefined_calculated_fields or [],
        columns={
            "orderId": DbColumnDef(name="order_id", column_type=ColumnType.STRING),
            "amount": DbColumnDef(name="total_amount", column_type=ColumnType.DECIMAL),
        },
        aggregate_relations=[
            AggregateRelationDef(
                left_model=name,
                right_model="FactSalesModel",
                alias=alias,
                group_by=group_by if group_by is not None else ["orderId"],
                filters=filters
                if filters is not None
                else [
                    AggregateRelationFilterDef(
                        model="FactSalesModel",
                        field="orderStatus",
                        op="=",
                        value="COMPLETED",
                    )
                ],
                measures=measures
                if measures is not None
                else [
                    AggregateRelationMeasureDef(
                        model="FactSalesModel",
                        field="salesAmount",
                        aggregation="SUM",
                        alias="salesAmount",
                        caption="销售明细金额",
                        sourceCaption="销售金额",
                        type="MONEY",
                    ),
                    AggregateRelationMeasureDef(
                        model="FactSalesModel",
                        field="customerKey",
                        aggregation="COUNT_DISTINCT",
                        alias="uniqueCustomers",
                        caption="独立客户数",
                        sourceCaption="独立客户数",
                        type="BIGINT",
                    ),
                ],
                conditions=[
                    AggregateRelationConditionDef(
                        left_model=name,
                        left_field="orderId",
                        right_model="FactSalesModel",
                        right_field="orderId",
                    )
                ],
            )
        ],
    )


def _composite_left_model() -> DbTableModelImpl:
    name = "TmsStyleOrderStoreSalesAggregateRelationQueryModel"
    return DbTableModelImpl(
        name=name,
        source_table="fact_order",
        columns={
            "orderId": DbColumnDef(name="order_id", column_type=ColumnType.STRING),
            "amount": DbColumnDef(name="total_amount", column_type=ColumnType.DECIMAL),
            "quantity": DbColumnDef(
                name="total_quantity",
                column_type=ColumnType.DECIMAL,
            ),
            "store$id": DbColumnDef(name="store_key", column_type=ColumnType.LONG),
        },
        aggregate_relations=[
            AggregateRelationDef(
                left_model=name,
                right_model="FactSalesModel",
                alias="salesByOrderStore",
                group_by=["orderId", "storeKey"],
                filters=[
                    AggregateRelationFilterDef(
                        model="FactSalesModel",
                        field="orderStatus",
                        op="=",
                        value="COMPLETED",
                    )
                ],
                measures=[
                    AggregateRelationMeasureDef(
                        model="FactSalesModel",
                        field="salesAmount",
                        aggregation="SUM",
                        alias="salesAmount",
                    ),
                    AggregateRelationMeasureDef(
                        model="FactSalesModel",
                        field="customerKey",
                        aggregation="COUNT_DISTINCT",
                        alias="uniqueCustomers",
                    ),
                ],
                conditions=[
                    AggregateRelationConditionDef(
                        left_model=name,
                        left_field="orderId",
                        right_model="FactSalesModel",
                        right_field="orderId",
                    ),
                    AggregateRelationConditionDef(
                        left_model=name,
                        left_field="store$id",
                        right_model="FactSalesModel",
                        right_field="storeKey",
                    ),
                ],
            )
        ],
    )


def _left_alias_key_model() -> DbTableModelImpl:
    name = "OrderSalesAggregateRelationAliasKeyQueryModel"
    return DbTableModelImpl(
        name=name,
        source_table="fact_order",
        columns={
            "orderNo": DbColumnDef(name="order_id", column_type=ColumnType.STRING),
            "amount": DbColumnDef(name="total_amount", column_type=ColumnType.DECIMAL),
        },
        aggregate_relations=[
            AggregateRelationDef(
                left_model=name,
                right_model="FactSalesModel",
                alias="fsByOrderAliasKey",
                group_by=["orderId"],
                filters=[
                    AggregateRelationFilterDef(
                        model="FactSalesModel",
                        field="orderStatus",
                        op="=",
                        value="COMPLETED",
                    )
                ],
                measures=[
                    AggregateRelationMeasureDef(
                        model="FactSalesModel",
                        field="salesAmount",
                        aggregation="SUM",
                        alias="salesAmount",
                        caption="销售明细金额",
                        sourceCaption="销售金额",
                        type="MONEY",
                    ),
                    AggregateRelationMeasureDef(
                        model="FactSalesModel",
                        field="customerKey",
                        aggregation="COUNT_DISTINCT",
                        alias="uniqueCustomers",
                        caption="独立客户数",
                        sourceCaption="独立客户数",
                        type="BIGINT",
                    ),
                ],
                conditions=[
                    AggregateRelationConditionDef(
                        left_model=name,
                        left_field="orderNo",
                        right_model="FactSalesModel",
                        right_field="orderId",
                    )
                ],
            )
        ],
    )


def _tenant_guard_model() -> DbTableModelImpl:
    name = "OrderSalesAggregateRelationTenantGuardQueryModel"
    return DbTableModelImpl(
        name=name,
        source_table="fact_order",
        columns={
            "orderId": DbColumnDef(name="order_id", column_type=ColumnType.STRING),
            "amount": DbColumnDef(name="total_amount", column_type=ColumnType.DECIMAL),
            "tenantId": DbColumnDef(name="tenant_id", column_type=ColumnType.STRING),
        },
        aggregate_relations=[
            AggregateRelationDef(
                left_model=name,
                right_model="FactSalesModel",
                alias="fsByTenantOrder",
                group_by=["orderId", "tenantId"],
                filters=[
                    AggregateRelationFilterDef(
                        model="FactSalesModel",
                        field="orderStatus",
                        op="=",
                        value="COMPLETED",
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
                        left_model=name,
                        left_field="orderId",
                        right_model="FactSalesModel",
                        right_field="orderId",
                    ),
                    AggregateRelationConditionDef(
                        left_model=name,
                        left_field="tenantId",
                        right_model="FactSalesModel",
                        right_field="tenantId",
                    ),
                ],
            )
        ],
    )


def _fallback_alias_model() -> DbTableModelImpl:
    return _left_model(
        name="OrderSalesAggregateJoinQueryModel",
        alias=None,
        measures=[
            AggregateRelationMeasureDef(
                model="FactSalesModel",
                field="salesAmount",
                aggregation="SUM",
                alias="salesAggAmount",
            ),
            AggregateRelationMeasureDef(
                model="FactSalesModel",
                field=None,
                aggregation="COUNT",
                alias="salesLineCount",
            ),
        ],
    )


def _raw_access_model() -> DbTableModelImpl:
    return _left_model(
        name="OrderSalesAggregateRelationRawAccessQueryModel",
        alias="fsByOrderRawAccess",
        access=DbAccessDef(
            name="raw_access_order_scope",
            row_filter_enabled=True,
            row_filter_type=RowFilterType.SQL,
            row_filter_expression="t1.order_id = ?",
            row_filter_params=[ORDER_1],
        ),
        measures=[
            AggregateRelationMeasureDef(
                model="FactSalesModel",
                field="quantity",
                aggregation="SUM",
                alias="quantity",
            ),
            AggregateRelationMeasureDef(
                model="FactSalesModel",
                field="unitPrice",
                aggregation="SUM",
                alias="unitPrice",
            ),
            AggregateRelationMeasureDef(
                model="FactSalesModel",
                field="unitCost",
                aggregation="SUM",
                alias="unitCost",
            ),
            AggregateRelationMeasureDef(
                model="FactSalesModel",
                field="discountAmount",
                aggregation="SUM",
                alias="discountAmount",
            ),
            AggregateRelationMeasureDef(
                model="FactSalesModel",
                field="salesAmount",
                aggregation="SUM",
                alias="salesAmount",
            ),
            AggregateRelationMeasureDef(
                model="FactSalesModel",
                field="costAmount",
                aggregation="SUM",
                alias="costAmount",
            ),
            AggregateRelationMeasureDef(
                model="FactSalesModel",
                field="profitAmount",
                aggregation="SUM",
                alias="profitAmount",
            ),
            AggregateRelationMeasureDef(
                model="FactSalesModel",
                field="taxAmount",
                aggregation="SUM",
                alias="taxAmount",
            ),
            AggregateRelationMeasureDef(
                model="FactSalesModel",
                field="customerKey",
                aggregation="COUNT_DISTINCT",
                alias="uniqueCustomers",
            ),
        ],
    )


def _structured_access_model() -> DbTableModelImpl:
    return _left_model(
        name="OrderSalesAggregateRelationAccessQueryModel",
        alias="fsByOrderAccess",
        access=DbAccessDef(
            name="structured_access_order_scope",
            row_filter_enabled=True,
            row_filter_type=RowFilterType.EXPRESSION,
            row_filter_expression=f'orderId == "{ORDER_1}"',
        ),
    )


def _rhs_dimension_filter_model() -> DbTableModelImpl:
    return _left_model(
        name="OrderSalesAggregateRelationRhsDimensionFilterQueryModel",
        alias="fsByProductCategory",
        filters=[
            AggregateRelationFilterDef(
                model="FactSalesModel",
                field="orderStatus",
                op="=",
                value="COMPLETED",
            ),
            AggregateRelationFilterDef(
                model="FactSalesModel",
                field="product$categoryId",
                op="=",
                value="CAT001",
            ),
        ],
    )


def _rhs_dimension_id_filter_model() -> DbTableModelImpl:
    return _left_model(
        name="OrderSalesAggregateRelationRhsDimensionIdFilterQueryModel",
        alias="fsByProductId",
        filters=[
            AggregateRelationFilterDef(
                model="FactSalesModel",
                field="orderStatus",
                op="=",
                value="COMPLETED",
            ),
            AggregateRelationFilterDef(
                model="FactSalesModel",
                field="product$id",
                op="=",
                value=101,
            ),
        ],
        measures=[
            AggregateRelationMeasureDef(
                model="FactSalesModel",
                field="salesAmount",
                aggregation="SUM",
                alias="salesAmount",
            )
        ],
    )


def _rhs_nested_dimension_filter_model() -> DbTableModelImpl:
    return _left_model(
        name="OrderSalesAggregateRelationNestedRhsDimensionFilterQueryModel",
        alias="fsByNestedCategory",
        filters=[
            AggregateRelationFilterDef(
                model="FactSalesModel",
                field="orderStatus",
                op="=",
                value="COMPLETED",
            ),
            AggregateRelationFilterDef(
                model="FactSalesModel",
                field="category$segment",
                op="=",
                value="PREMIUM",
            ),
        ],
    )


def _left_dimension_key_model() -> DbTableModelImpl:
    name = "OrderStoreAggregateRelationDimensionKeyQueryModel"
    return DbTableModelImpl(
        name=name,
        source_table="fact_order",
        columns={
            "orderId": DbColumnDef(name="order_id", column_type=ColumnType.STRING),
            "amount": DbColumnDef(name="total_amount", column_type=ColumnType.DECIMAL),
        },
        dimension_joins=[
            DimensionJoinDef(
                name="store",
                table_name="dim_store",
                foreign_key="store_key",
                primary_key="store_key",
                properties=[
                    DimensionPropertyDef(
                        name="storeId",
                        column="store_id",
                        caption="Store ID",
                    )
                ],
            )
        ],
        aggregate_relations=[
            AggregateRelationDef(
                left_model=name,
                right_model="DimStoreModel",
                alias="storeAggByBusinessId",
                group_by=["storeId"],
                filters=[
                    AggregateRelationFilterDef(
                        model="DimStoreModel",
                        field="status",
                        op="=",
                        value="ACTIVE",
                    )
                ],
                measures=[
                    AggregateRelationMeasureDef(
                        model="DimStoreModel",
                        field="areaSqm",
                        aggregation="SUM",
                        alias="areaSqm",
                    )
                ],
                conditions=[
                    AggregateRelationConditionDef(
                        left_model=name,
                        left_field="store$storeId",
                        right_model="DimStoreModel",
                        right_field="storeId",
                    )
                ],
            )
        ],
    )


def _left_dimension_slice_non_key_model() -> DbTableModelImpl:
    name = "OrderSalesAggregateRelationDimensionSliceNonKeyQueryModel"
    return DbTableModelImpl(
        name=name,
        source_table="fact_order",
        columns={
            "orderId": DbColumnDef(name="order_id", column_type=ColumnType.STRING),
            "amount": DbColumnDef(name="total_amount", column_type=ColumnType.DECIMAL),
        },
        dimension_joins=[
            DimensionJoinDef(
                name="store",
                table_name="dim_store",
                foreign_key="store_key",
                primary_key="store_key",
                properties=[
                    DimensionPropertyDef(
                        name="storeId",
                        column="store_id",
                        caption="Store ID",
                    )
                ],
            )
        ],
        aggregate_relations=[
            AggregateRelationDef(
                left_model=name,
                right_model="FactSalesModel",
                alias="fsByOrderDimensionSliceNonKey",
                group_by=["orderId"],
                filters=[
                    AggregateRelationFilterDef(
                        model="FactSalesModel",
                        field="orderStatus",
                        op="=",
                        value="COMPLETED",
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
                        left_model=name,
                        left_field="orderId",
                        right_model="FactSalesModel",
                        right_field="orderId",
                    )
                ],
            )
        ],
    )


def _left_nested_dimension_key_model(
    *,
    name: str = "OrderStoreAggregateRelationNestedDimensionKeyQueryModel",
    nested_on_condition: bool = True,
) -> DbTableModelImpl:
    left_field = "region$regionId" if nested_on_condition else "store$storeId"
    return DbTableModelImpl(
        name=name,
        source_table="fact_order",
        columns={
            "orderId": DbColumnDef(name="order_id", column_type=ColumnType.STRING),
            "amount": DbColumnDef(name="total_amount", column_type=ColumnType.DECIMAL),
        },
        dimension_joins=[
            DimensionJoinDef(
                name="store",
                table_name="dim_store",
                foreign_key="store_key",
                primary_key="store_key",
                properties=[
                    DimensionPropertyDef(
                        name="storeId",
                        column="store_id",
                        caption="Store ID",
                    )
                ],
            ),
            DimensionJoinDef(
                name="region",
                table_name="dim_region",
                foreign_key="region_key",
                primary_key="region_key",
                join_to="store",
                properties=[
                    DimensionPropertyDef(
                        name="regionId",
                        column="region_id",
                        caption="Region ID",
                    )
                ],
            ),
        ],
        aggregate_relations=[
            AggregateRelationDef(
                left_model=name,
                right_model="DimStoreModel",
                alias="storeAggByNestedKey",
                group_by=["storeId"],
                filters=[
                    AggregateRelationFilterDef(
                        model="DimStoreModel",
                        field="status",
                        op="=",
                        value="ACTIVE",
                    )
                ],
                measures=[
                    AggregateRelationMeasureDef(
                        model="DimStoreModel",
                        field="areaSqm",
                        aggregation="SUM",
                        alias="areaSqm",
                    )
                ],
                conditions=[
                    AggregateRelationConditionDef(
                        left_model=name,
                        left_field=left_field,
                        right_model="DimStoreModel",
                        right_field="storeId",
                    )
                ],
            )
        ],
    )


def _wide_projection_model() -> DbTableModelImpl:
    return _left_model(
        name="OrderSalesAggregateRelationWideProjectionQueryModel",
        alias="fsByOrderWide",
        measures=[
            AggregateRelationMeasureDef(
                model="FactSalesModel",
                field="quantity",
                aggregation="SUM",
                alias="quantity",
            ),
            AggregateRelationMeasureDef(
                model="FactSalesModel",
                field="unitPrice",
                aggregation="SUM",
                alias="unitPrice",
            ),
            AggregateRelationMeasureDef(
                model="FactSalesModel",
                field="salesAmount",
                aggregation="SUM",
                alias="salesAmount",
                caption="销售明细金额",
                sourceCaption="销售金额",
                type="MONEY",
            ),
            AggregateRelationMeasureDef(
                model="FactSalesModel",
                field="customerKey",
                aggregation="COUNT_DISTINCT",
                alias="uniqueCustomers",
                caption="独立客户数",
                sourceCaption="独立客户数",
                type="BIGINT",
            ),
        ],
    )


def _runtime_filter_model() -> DbTableModelImpl:
    return _left_model(
        name="OrderSalesAggregateRelationRuntimeFilterQueryModel",
        alias="fsByRuntimeOrder",
        filters=[
            AggregateRelationFilterDef(
                model="FactSalesModel",
                field="orderStatus",
                op="=",
                value="COMPLETED",
            ),
            AggregateRelationFilterDef(
                model="FactSalesModel",
                field="orderId",
                op="=",
                value={"extData": "orderId"},
            ),
        ],
    )


def _payment_method_group_model() -> DbTableModelImpl:
    return _left_model(
        name="OrderSalesAggregateRelationPaymentMethodQueryModel",
        alias="fsByPaymentMethod",
        group_by=["orderId", "paymentMethod"],
        filters=[
            AggregateRelationFilterDef(
                model="FactSalesModel",
                field="orderStatus",
                op="=",
                value="COMPLETED",
            ),
            AggregateRelationFilterDef(
                model="FactSalesModel",
                field="paymentMethod",
                op="=",
                value="CREDIT_CARD",
            ),
        ],
    )


def _service(*models: DbTableModelImpl, executor: Any | None = None) -> SemanticQueryService:
    service = SemanticQueryService(executor=executor, enable_cache=False)
    for model in models:
        service.register_model(model)
    return service


def _request(**kwargs: Any) -> SemanticQueryRequest:
    kwargs.setdefault("columns", ["orderId", "amount", "salesAmount", "uniqueCustomers"])
    return SemanticQueryRequest(**kwargs)


def _assert_aggregate_relation_unsupported_response(
    response: Any,
    message_marker: str,
) -> None:
    assert response.sql is None
    assert response.error is not None
    assert AGGREGATE_JOIN_UNSUPPORTED_CODE in response.error
    assert message_marker in response.error
    assert response.error_detail is not None
    assert response.error_detail["code"] == AGGREGATE_JOIN_UNSUPPORTED_CODE
    assert "dim_category" not in response.error
    assert "dim_region" not in response.error


def test_p0_82_sqlite_shape_matches_java_fixed_filter_markers() -> None:
    case = _case("aggregate-join-fixed-rhs-filter")
    service = _service(_right_model(), _left_model())

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationQueryModel",
        _request(),
    )

    normalized = _normal(result.sql)
    expected = case["expected"]
    assert result.params == expected["params"]
    for marker in expected["sqlMarkers"]:
        assert marker in normalized
    for marker in expected["forbiddenSqlMarkers"]:
        assert marker not in normalized
    assert result.diagnostics == expected["diagnostics"]


def test_p0_82_sqlite_shape_uses_fallback_relation_alias_and_count_star() -> None:
    case = _case("aggregate-join-sql-shape-sqlite")
    service = _service(_right_model(), _fallback_alias_model())

    result = service.build_query_with_governance(
        "OrderSalesAggregateJoinQueryModel",
        SemanticQueryRequest(
            columns=["orderId", "amount", "salesAggAmount", "salesLineCount"],
        ),
    )

    normalized = _normal(result.sql).lower()
    expected = case["expected"]
    assert result.params == expected["params"]
    for marker in expected["sqlMarkers"]:
        assert marker.lower() in normalized
    for marker in expected["forbiddenSqlMarkers"]:
        assert marker.lower() not in normalized


def test_p0_82_missing_right_key_groupby_fails_closed() -> None:
    service = _service(_right_model(), _left_model(group_by=["orderStatus"]))

    with pytest.raises(ValueError) as exc_info:
        service.build_query_with_governance(
            "OrderSalesAggregateRelationQueryModel",
            _request(),
        )

    error = str(exc_info.value)
    assert AGGREGATE_JOIN_GROUPBY_MISSING_RIGHT_KEY_CODE in error
    assert "orderId" in error


def test_p0_83_sqlite_live_result_keeps_left_measure_unmultiplied(tmp_path) -> None:
    db_path = tmp_path / "aggregate_relation.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(_right_model(), _left_model(), executor=executor)

    try:
        response = service.query_model(
            "OrderSalesAggregateRelationQueryModel",
            _request(slice=[{"field": "orderId", "op": "=", "value": ORDER_1}]),
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert response.items == [
        {
            "orderId": ORDER_1,
            "amount": 10998,
            "salesAmount": 9898.2,
            "uniqueCustomers": 1,
        }
    ]


def test_p0_84_denied_rhs_source_column_fails_closed() -> None:
    service = _service(_right_model(), _left_model())

    response = service.query_model(
        "OrderSalesAggregateRelationQueryModel",
        _request(
            denied_columns=[
                DeniedColumn(table="fact_sales", column="sales_amount")
            ]
        ),
        mode="validate",
    )

    assert response.sql is None
    assert response.error is not None
    assert AGGREGATE_JOIN_DENIED_SOURCE_COLUMN_CODE in response.error
    assert "salesAmount" in response.error
    assert "fact_sales" in response.error
    assert "sales_amount" in response.error


def test_p0_84_aggregate_output_lineage_is_attached_to_columns() -> None:
    service = _service(_right_model(), _left_model())

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationQueryModel",
        _request(),
    )

    columns = {column["name"]: column for column in result.columns}
    sales_relation = columns["salesAmount"]["aggregateRelation"]
    unique_relation = columns["uniqueCustomers"]["aggregateRelation"]
    required = {
        "aggregation",
        "sourceCaption",
        "sourceMeasure",
        "sourceAlias",
        "sourceExpression",
        "aggregateExpression",
        "sourceColumn",
    }
    assert required.issubset(sales_relation)
    assert required.issubset(unique_relation)
    assert sales_relation["sourceExpression"] == "agg_src.sales_amount"
    assert sales_relation["aggregateExpression"] == "sum(agg_src.sales_amount)"
    assert unique_relation["aggregateExpression"] == (
        "count(distinct agg_src.customer_key)"
    )
    for internal_key in (
        "semanticScaleFactor",
        "semanticUnit",
        "semanticUnitLabel",
    ):
        assert internal_key in sales_relation


def test_p0_88_public_v3_metadata_exposes_java_seven_key_lineage() -> None:
    case = _case("aggregate-join-metadata-lineage")
    expected = case["expected"]
    expected_public_keys = set(expected["aggregateRelation"])
    service = _service(_right_model(), _left_model())

    metadata = service.get_metadata_v3(
        model_names=["OrderSalesAggregateRelationQueryModel"],
    )

    fields = metadata["fields"]
    assert {"salesAmount", "uniqueCustomers"}.issubset(fields)
    for field_name in ("salesAmount", "uniqueCustomers"):
        field = fields[field_name]
        expected_field = expected["fields"][field_name]
        java_relation = expected_field["aggregateRelation"]
        relation = field["aggregateRelation"]

        assert field["fieldName"] == field_name
        assert field["name"] == expected_field["caption"]
        assert field["type"] == expected_field["type"]
        assert field["measure"] is True
        assert field["aggregatable"] is True
        assert field["aggregation"] == java_relation["aggregation"]
        assert field["sourceColumn"] == field_name
        assert field["sourceExpression"] == expected_field["sourceExpression"]
        assert field["aggregateExpression"] == expected_field["aggregateExpression"]
        assert "OrderSalesAggregateRelationQueryModel" in field["models"]

        assert set(relation) == expected_public_keys
        assert all(isinstance(value, str) for value in relation.values())
        assert relation == {
            key: str(java_relation[key])
            for key in expected["aggregateRelation"]
        }
        for internal_key in (
            "semanticScaleFactor",
            "semanticUnit",
            "semanticUnitLabel",
        ):
            assert internal_key not in relation

        non_expression_field = dict(field)
        non_expression_field.pop("sourceExpression", None)
        non_expression_field.pop("aggregateExpression", None)
        non_expression_relation = dict(relation)
        non_expression_relation.pop("sourceExpression", None)
        non_expression_relation.pop("aggregateExpression", None)
        non_expression_field["aggregateRelation"] = non_expression_relation
        serialized = json.dumps(non_expression_field, ensure_ascii=False)
        assert "sales_amount" not in serialized
        assert "customer_key" not in serialized


def test_p0_88_public_v3_metadata_respects_rhs_denied_source_columns() -> None:
    service = _service(_right_model(), _left_model())

    metadata = service.get_metadata_v3(
        model_names=["OrderSalesAggregateRelationQueryModel"],
        denied_columns=[
            DeniedColumn(table="fact_sales", column="sales_amount")
        ],
    )

    fields = metadata["fields"]
    assert "salesAmount" not in fields
    assert "uniqueCustomers" in fields
    assert fields["uniqueCustomers"]["aggregateRelation"]["sourceColumn"] == (
        "uniqueCustomers"
    )


def test_p0_87_field_access_allows_aggregate_outputs(tmp_path) -> None:
    _case("aggregate-join-field-access-allow-output")
    db_path = tmp_path / "aggregate_relation_field_access.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(_right_model(), _left_model(), executor=executor)

    try:
        response = service.query_model(
            "OrderSalesAggregateRelationQueryModel",
            _request(
                slice=[{"field": "orderId", "op": "=", "value": ORDER_1}],
                field_access=FieldAccessDef(
                    visible=[
                        "orderId",
                        "amount",
                        "salesAmount",
                        "uniqueCustomers",
                    ]
                ),
            ),
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert response.items == [
        {
            "orderId": ORDER_1,
            "amount": 10998,
            "salesAmount": 9898.2,
            "uniqueCustomers": 1,
        }
    ]


def test_p0_87_field_access_denies_aggregate_output() -> None:
    case = _case("aggregate-join-field-access-deny-output-refusal")
    service = _service(_right_model(), _left_model())

    response = service.query_model(
        "OrderSalesAggregateRelationQueryModel",
        _request(
            field_access=FieldAccessDef(
                visible=["orderId", "amount", "uniqueCustomers"]
            )
        ),
        mode="validate",
    )

    assert response.sql is None
    assert response.error is not None
    assert AGGREGATE_JOIN_FIELD_ACCESS_DENIED_CODE in response.error
    for marker in case["expected"]["messageMarkers"]:
        assert marker in response.error
    assert response.error_detail == {
        "code": AGGREGATE_JOIN_FIELD_ACCESS_DENIED_CODE,
        "field": "salesAmount",
    }


def test_p0_87_system_slice_guard_does_not_leak_aggregate_output(tmp_path) -> None:
    case = _case("aggregate-join-system-slice-guard-bypass-no-leak")
    db_path = tmp_path / "aggregate_relation_system_slice.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(_right_model(), _left_model(), executor=executor)

    try:
        response = service.query_model(
            "OrderSalesAggregateRelationQueryModel",
            SemanticQueryRequest(
                columns=["orderId", "amount"],
                slice=[{"field": "orderId", "op": "=", "value": ORDER_1}],
                system_slice=[{"field": "salesAmount", "op": ">", "value": 0}],
                field_access=FieldAccessDef(visible=["orderId", "amount"]),
            ),
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert response.items == [{"orderId": ORDER_1, "amount": 10998}]
    debug_sql = response.debug.extra["sql"]
    assert "having sum(agg_src.sales_amount) > ?" in debug_sql
    for field in case["expected"]["rowsForbiddenFields"]:
        assert field not in response.items[0]


def test_p0_87_unreferenced_denied_source_column_passes(tmp_path) -> None:
    case = _case("aggregate-join-denied-source-column-unreferenced-pass")
    db_path = tmp_path / "aggregate_relation_unreferenced_denied_source.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(_right_model(), _left_model(), executor=executor)

    try:
        response = service.query_model(
            "OrderSalesAggregateRelationQueryModel",
            _request(
                slice=[{"field": "orderId", "op": "=", "value": ORDER_1}],
                denied_columns=[
                    DeniedColumn(table="fact_sales", column="profit_amount")
                ],
            ),
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert response.items == case["expected"]["rows"]
    debug_sql = _normal(response.debug.extra["sql"])
    for marker in case["expected"]["sqlMarkers"]:
        assert marker in debug_sql
    for marker in case["expected"]["forbiddenSqlMarkers"]:
        assert marker not in debug_sql


def test_p0_87_calculated_field_denied_source_fails_closed() -> None:
    case = _case("aggregate-join-calculated-field-denied-source-refusal")
    service = _service(_right_model(), _left_model())

    response = service.query_model(
        "OrderSalesAggregateRelationQueryModel",
        _request(
            columns=case["request"]["columns"],
            slice=case["request"]["slice"],
            calculated_fields=case["expected"]["calculatedFields"],
            denied_columns=[
                DeniedColumn(table="fact_sales", column="sales_amount")
            ],
        ),
        mode="validate",
    )

    assert response.sql is None
    assert response.error is not None
    assert AGGREGATE_JOIN_DENIED_SOURCE_COLUMN_CODE in response.error
    for marker in case["expected"]["messageMarkers"]:
        assert marker in response.error
    assert response.error_detail is not None
    assert response.error_detail["field"] == "salesAmount"
    assert response.error_detail["table"] == "fact_sales"
    assert response.error_detail["column"] == "sales_amount"
    assert response.error_detail["calculatedFields"] == ["salesAmountWithTax"]


def test_p0_87_calculated_field_chain_denied_source_fails_closed() -> None:
    case = _case("aggregate-join-calculated-field-chain-denied-source-refusal")
    service = _service(_right_model(), _left_model())

    response = service.query_model(
        "OrderSalesAggregateRelationQueryModel",
        _request(
            columns=case["request"]["columns"],
            slice=case["request"]["slice"],
            calculated_fields=case["expected"]["calculatedFields"],
            denied_columns=[
                DeniedColumn(table="fact_sales", column="sales_amount")
            ],
        ),
        mode="validate",
    )

    assert response.sql is None
    assert response.error is not None
    assert AGGREGATE_JOIN_DENIED_SOURCE_COLUMN_CODE in response.error
    for marker in case["expected"]["messageMarkers"]:
        assert marker in response.error
    assert response.error_detail is not None
    assert response.error_detail["field"] == "salesAmount"
    assert response.error_detail["table"] == "fact_sales"
    assert response.error_detail["column"] == "sales_amount"
    assert set(response.error_detail["calculatedFields"]) == {
        "salesAmountWithTax",
        "salesAmountScore",
    }


def test_p0_87_predefined_calculated_field_denied_source_fails_closed() -> None:
    case = _case("aggregate-join-predefined-calculated-field-denied-source-refusal")
    service = _service(
        _right_model(),
        _left_model(
            predefined_calculated_fields=[
                {
                    "name": case["expected"]["predefinedCalculatedField"],
                    "expression": "salesAmount * 1.1",
                }
            ],
        ),
    )

    response = service.query_model(
        "OrderSalesAggregateRelationQueryModel",
        _request(
            columns=case["request"]["columns"],
            slice=case["request"]["slice"],
            denied_columns=[
                DeniedColumn(table="fact_sales", column="sales_amount")
            ],
        ),
        mode="validate",
    )

    assert response.sql is None
    assert response.error is not None
    assert AGGREGATE_JOIN_DENIED_SOURCE_COLUMN_CODE in response.error
    for marker in case["expected"]["messageMarkers"]:
        assert marker in response.error
    assert response.error_detail is not None
    assert response.error_detail["field"] == case["expected"]["predefinedCalculatedField"]
    assert response.error_detail["sourceField"] == "salesAmount"
    assert response.error_detail["table"] == "fact_sales"
    assert response.error_detail["column"] == "sales_amount"
    assert response.error_detail["predefinedCalculatedFields"] == [
        case["expected"]["predefinedCalculatedField"]
    ]


def test_p0_87_predefined_calculated_field_allowed_exec(tmp_path) -> None:
    case = _case("aggregate-join-predefined-calculated-field-allowed-exec")
    predefined_field = "salesAmountPredefinedTax"
    db_path = tmp_path / "aggregate_relation_predefined_calculated.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(
        _right_model(),
        _left_model(
            predefined_calculated_fields=[
                {
                    "name": predefined_field,
                    "expression": "salesAmount * 1.1",
                }
            ],
        ),
        executor=executor,
    )

    try:
        response = service.query_model(
            "OrderSalesAggregateRelationQueryModel",
            _request(
                columns=case["request"]["columns"],
                slice=case["request"]["slice"],
            ),
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert len(response.items) == 1
    row = response.items[0]
    assert row["orderId"] == ORDER_1
    assert row["amount"] == 10998
    assert row[predefined_field] == pytest.approx(10888.020000000002)
    debug_sql = _normal(response.debug.extra["sql"])
    for marker in case["expected"]["sqlMarkers"]:
        assert marker in debug_sql
    assert "fsByOrder.salesAmount * ?" in debug_sql


def test_p0_87_custom_calculated_field_still_fails_closed() -> None:
    service = _service(_right_model(), _left_model())

    response = service.query_model(
        "OrderSalesAggregateRelationQueryModel",
        _request(
            columns=["orderId", "amount", "salesAmountWithTax"],
            calculated_fields=[
                {
                    "name": "salesAmountWithTax",
                    "expression": "salesAmount * 1.1",
                }
            ],
        ),
        mode="validate",
    )

    assert response.sql is None
    assert response.error is not None
    assert AGGREGATE_JOIN_UNSUPPORTED_CODE in response.error
    assert "request-level calculatedFields are not supported" in response.error


def test_p0_87_raw_access_builder_stays_outer_only(tmp_path) -> None:
    case = _case("aggregate-join-raw-sql-access-builder-outer-only")
    db_path = tmp_path / "aggregate_relation_raw_access.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(
        _right_model(),
        _raw_access_model(),
        executor=executor,
    )
    request = _request(columns=case["request"]["columns"])
    build_result = service.build_query_with_governance(
        "OrderSalesAggregateRelationRawAccessQueryModel",
        request,
    )
    build_sql = _normal(build_result.sql)
    assert build_result.params == case["expected"]["params"]
    assert build_result.diagnostics == case["expected"]["diagnostics"]
    for marker in case["expected"]["sqlMarkers"]:
        assert marker in build_sql
    for marker in case["expected"]["forbiddenSqlMarkers"]:
        assert marker not in build_sql

    try:
        response = service.query_model(
            "OrderSalesAggregateRelationRawAccessQueryModel",
            request,
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert response.params == case["expected"]["params"]
    assert response.items == [
        {
            "orderId": ORDER_1,
            "amount": 10998,
            "salesAmount": 9898.2,
            "uniqueCustomers": 1,
        }
    ]
    debug_sql = _normal(response.debug.extra["sql"])
    for marker in case["expected"]["sqlMarkers"]:
        assert marker in debug_sql
    for marker in case["expected"]["forbiddenSqlMarkers"]:
        assert marker not in debug_sql


def test_p0_96_structured_access_builder_pushes_join_key_rhs_where(
    tmp_path,
) -> None:
    case = _case("aggregate-join-structured-access-builder-pushdown")
    db_path = tmp_path / "aggregate_relation_structured_access.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(
        _right_model(),
        _structured_access_model(),
        executor=executor,
    )
    request = _request(columns=case["request"]["columns"])

    build_result = service.build_query_with_governance(
        "OrderSalesAggregateRelationAccessQueryModel",
        request,
    )
    build_sql = _normal(build_result.sql)
    assert build_result.params == case["expected"]["params"]
    assert build_result.diagnostics == case["expected"]["diagnostics"]
    for marker in case["expected"]["sqlMarkers"]:
        assert marker in build_sql
    for marker in case["expected"]["forbiddenSqlMarkers"]:
        assert marker not in build_sql
    assert "agg_src.order_id = ?" in build_sql
    assert "t1.order_id = ?" in build_sql

    try:
        response = service.query_model(
            "OrderSalesAggregateRelationAccessQueryModel",
            request,
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert response.params == case["expected"]["params"]
    assert response.items == case["expected"]["rows"]
    debug_sql = _normal(response.debug.extra["sql"])
    assert "agg_src.order_id = ?" in debug_sql
    assert "t1.order_id = ?" in debug_sql


def test_p0_97_composite_key_request_slice_pushes_each_rhs_key(
    tmp_path,
) -> None:
    case = _case("aggregate-join-composite-key-pushdown")
    db_path = tmp_path / "aggregate_relation_composite_key.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(
        _composite_right_model(),
        _composite_left_model(),
        executor=executor,
    )
    request = _request(
        columns=case["request"]["columns"],
        slice=case["request"]["slice"],
    )

    result = service.build_query_with_governance(
        "TmsStyleOrderStoreSalesAggregateRelationQueryModel",
        request,
    )
    normalized = _normal(result.sql)
    assert result.params == case["expected"]["params"]
    assert result.diagnostics == case["expected"]["diagnostics"]
    for marker in case["expected"]["sqlMarkers"]:
        assert marker in normalized
    assert "t1.order_id = salesByOrderStore.orderId" in normalized
    assert "t1.store_key = salesByOrderStore.storeKey" in normalized
    assert "t1.order_id = ?" in normalized
    assert "t1.store_key = ?" in normalized

    try:
        response = service.query_model(
            "TmsStyleOrderStoreSalesAggregateRelationQueryModel",
            request,
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert response.params == case["expected"]["params"]
    assert response.items == case["expected"]["rows"]


def test_p0_98_rhs_dimension_fixed_filter_joins_dimension_inside_rhs(
    tmp_path,
) -> None:
    case = _case("aggregate-join-rhs-dimension-fixed-filter")
    db_path = tmp_path / "aggregate_relation_rhs_dimension_filter.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(
        _rhs_dimension_filter_right_model(),
        _rhs_dimension_filter_model(),
        executor=executor,
    )
    request = _request(
        columns=case["request"]["columns"],
        slice=case["request"]["slice"],
    )

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationRhsDimensionFilterQueryModel",
        request,
    )
    normalized = _normal(result.sql)
    assert result.params == case["expected"]["params"]
    for marker in case["expected"]["sqlMarkers"]:
        assert marker in normalized
    for marker in case["expected"]["forbiddenSqlMarkers"]:
        assert marker not in normalized
    assert "left join dim_product dp on agg_src.product_key = dp.product_key" in normalized
    assert "dp.category_id = ?" in normalized
    assert "agg_src.category_id" not in normalized

    try:
        response = service.query_model(
            "OrderSalesAggregateRelationRhsDimensionFilterQueryModel",
            request,
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert response.params == case["expected"]["params"]
    assert response.items == case["expected"]["rows"]
    debug_sql = _normal(response.debug.extra["sql"])
    assert "left join dim_product dp on agg_src.product_key = dp.product_key" in debug_sql
    assert "dp.category_id = ?" in debug_sql


def test_p0_99_left_dimension_key_joins_root_dimension_before_aggregate(
    tmp_path,
) -> None:
    case = _case("aggregate-join-left-dimension-key")
    db_path = tmp_path / "aggregate_relation_left_dimension_key.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(
        _store_dimension_right_model(),
        _left_dimension_key_model(),
        executor=executor,
    )
    request = _request(
        columns=case["request"]["columns"],
        slice=case["request"]["slice"],
    )

    result = service.build_query_with_governance(
        "OrderStoreAggregateRelationDimensionKeyQueryModel",
        request,
    )
    normalized = _normal(result.sql)
    assert result.params == case["expected"]["params"]
    assert result.diagnostics == case["expected"]["diagnostics"]
    for marker in case["expected"]["sqlMarkers"]:
        assert marker in normalized
    for marker in case["expected"]["forbiddenSqlMarkers"]:
        assert marker not in normalized
    assert "left join dim_store ds on t1.store_key = ds.store_key" in normalized
    assert "ds.store_id = storeAggByBusinessId.storeId" in normalized

    try:
        response = service.query_model(
            "OrderStoreAggregateRelationDimensionKeyQueryModel",
            request,
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert response.params == case["expected"]["params"]
    assert response.items == case["expected"]["rows"]
    debug_sql = _normal(response.debug.extra["sql"])
    assert "left join dim_store ds on t1.store_key = ds.store_key" in debug_sql
    assert "ds.store_id = storeAggByBusinessId.storeId" in debug_sql


def test_p0_100_left_dimension_key_request_slice_pushes_rhs_key(
    tmp_path,
) -> None:
    db_path = tmp_path / "aggregate_relation_left_dimension_slice.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(
        _store_dimension_right_model(),
        _left_dimension_key_model(),
        executor=executor,
    )
    request = SemanticQueryRequest(
        columns=["orderId", "amount", "areaSqm"],
        slice=[{"field": "store$storeId", "op": "=", "value": "STORE001"}],
    )

    result = service.build_query_with_governance(
        "OrderStoreAggregateRelationDimensionKeyQueryModel",
        request,
    )
    normalized = _normal(result.sql)
    assert result.params == ["ACTIVE", "STORE001", "STORE001"]
    assert "left join dim_store ds on t1.store_key = ds.store_key" in normalized
    assert "ds.store_id = storeAggByBusinessId.storeId" in normalized
    assert "agg_src.store_id = ?" in normalized
    assert "ds.store_id = ?" in normalized
    assert "store$storeId" not in normalized
    assert result.diagnostics == [
        {
            "decision": "pushed",
            "field": "store$storeId",
            "op": "=",
            "target": "where",
            "reasonCode": None,
            "expression": "agg_src.store_id = ?",
        }
    ]

    try:
        response = service.query_model(
            "OrderStoreAggregateRelationDimensionKeyQueryModel",
            request,
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert response.params == ["ACTIVE", "STORE001", "STORE001"]
    assert response.items == [
        {"orderId": ORDER_1, "amount": 10998, "areaSqm": 350},
        {"orderId": ORDER_2, "amount": 2500, "areaSqm": 350},
    ]


def test_p0_101_rhs_nested_dimension_filter_fails_closed() -> None:
    service = _service(
        _rhs_nested_dimension_filter_right_model(),
        _rhs_nested_dimension_filter_model(),
    )

    response = service.query_model(
        "OrderSalesAggregateRelationNestedRhsDimensionFilterQueryModel",
        SemanticQueryRequest(columns=["orderId", "amount", "salesAmount"]),
        mode="validate",
    )

    _assert_aggregate_relation_unsupported_response(
        response,
        "nested RHS dimension filters are not supported",
    )


def test_p0_101_left_nested_dimension_on_key_fails_closed() -> None:
    service = _service(
        _store_dimension_right_model(),
        _left_nested_dimension_key_model(),
    )

    response = service.query_model(
        "OrderStoreAggregateRelationNestedDimensionKeyQueryModel",
        SemanticQueryRequest(columns=["orderId", "amount", "areaSqm"]),
        mode="validate",
    )

    _assert_aggregate_relation_unsupported_response(
        response,
        "nested root dimension join keys are not supported",
    )


def test_p0_101_left_nested_dimension_request_slice_fails_closed() -> None:
    model_name = "OrderStoreAggregateRelationNestedDimensionSliceQueryModel"
    service = _service(
        _store_dimension_right_model(),
        _left_nested_dimension_key_model(
            name=model_name,
            nested_on_condition=False,
        ),
    )

    response = service.query_model(
        model_name,
        SemanticQueryRequest(
            columns=["orderId", "amount", "areaSqm"],
            slice=[{"field": "region$regionId", "op": "=", "value": "REGION001"}],
        ),
        mode="validate",
    )

    _assert_aggregate_relation_unsupported_response(
        response,
        "nested root dimension join keys are not supported",
    )


def test_p0_102_alias_key_no_columns_request_defaults_and_pushes_rhs_key(
    tmp_path,
) -> None:
    db_path = tmp_path / "aggregate_relation_alias_key_no_columns.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(_right_model(), _left_alias_key_model(), executor=executor)
    request = SemanticQueryRequest(
        columns=[],
        slice=[{"field": "orderNo", "op": "=", "value": ORDER_1}],
    )

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationAliasKeyQueryModel",
        request,
    )
    normalized = _normal(result.sql)
    assert result.params == ["COMPLETED", ORDER_1, ORDER_1]
    assert [column["name"] for column in result.columns] == [
        "orderNo",
        "amount",
        "salesAmount",
        "uniqueCustomers",
    ]
    assert 't1.order_id "orderNo"' in normalized
    assert "agg_src.order_id = ?" in normalized
    assert "t1.order_id = ?" in normalized

    try:
        response = service.query_model(
            "OrderSalesAggregateRelationAliasKeyQueryModel",
            request,
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert response.items == [
        {
            "orderNo": ORDER_1,
            "amount": 10998,
            "salesAmount": 9898.2,
            "uniqueCustomers": 1,
        }
    ]


def test_p0_102_tenant_system_slice_pushes_rhs_without_leaking_guard(
    tmp_path,
) -> None:
    db_path = tmp_path / "aggregate_relation_tenant_guard.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(_tenant_right_model(), _tenant_guard_model(), executor=executor)
    request = SemanticQueryRequest(
        columns=["orderId", "amount", "salesAmount"],
        system_slice=[{"field": "tenantId", "op": "=", "value": TENANT_A}],
        field_access=FieldAccessDef(visible=["orderId", "amount", "salesAmount"]),
    )

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationTenantGuardQueryModel",
        request,
    )
    normalized = _normal(result.sql)
    assert result.params == ["COMPLETED", TENANT_A, TENANT_A]
    assert [column["name"] for column in result.columns] == [
        "orderId",
        "amount",
        "salesAmount",
    ]
    assert "tenantId" not in {column["name"] for column in result.columns}
    assert "agg_src.tenant_id = ?" in normalized
    assert "group by agg_src.order_id, agg_src.tenant_id" in normalized
    assert "t1.tenant_id = fsByTenantOrder.tenantId" in normalized
    assert "t1.tenant_id = ?" in normalized
    assert result.diagnostics == [
        {
            "decision": "pushed",
            "field": "tenantId",
            "op": "=",
            "target": "where",
            "reasonCode": None,
            "expression": "agg_src.tenant_id = ?",
        }
    ]

    try:
        response = service.query_model(
            "OrderSalesAggregateRelationTenantGuardQueryModel",
            request,
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert response.params == ["COMPLETED", TENANT_A, TENANT_A]
    assert response.items == [
        {
            "orderId": ORDER_1,
            "amount": 10998,
            "salesAmount": 9898.2,
        }
    ]
    assert "tenantId" not in response.items[0]
    debug_sql = _normal(response.debug.extra["sql"])
    assert "agg_src.tenant_id = ?" in debug_sql


def test_p0_103_non_join_dimension_property_slice_stays_outer_only(
    tmp_path,
) -> None:
    db_path = tmp_path / "aggregate_relation_non_join_dimension_property_slice.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(
        _right_model(),
        _left_dimension_slice_non_key_model(),
        executor=executor,
    )
    request = SemanticQueryRequest(
        columns=["orderId", "amount", "salesAmount"],
        slice=[{"field": "store$storeId", "op": "=", "value": "STORE001"}],
    )

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationDimensionSliceNonKeyQueryModel",
        request,
    )
    normalized = _normal(result.sql)
    assert result.params == ["COMPLETED", "STORE001"]
    assert "left join dim_store ds on t1.store_key = ds.store_key" in normalized
    assert "ds.store_id = ?" in normalized
    assert "agg_src.store_id = ?" not in normalized
    assert "store$storeId" not in normalized
    assert result.diagnostics == [
        {
            "decision": "refused",
            "field": "store$storeId",
            "op": "=",
            "target": None,
            "reasonCode": "NO_JOIN_KEY_MAPPING",
            "expression": None,
        }
    ]

    try:
        response = service.query_model(
            "OrderSalesAggregateRelationDimensionSliceNonKeyQueryModel",
            request,
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert response.params == ["COMPLETED", "STORE001"]
    assert response.items == [
        {"orderId": ORDER_1, "amount": 10998, "salesAmount": 9898.2},
        {"orderId": ORDER_2, "amount": 2500, "salesAmount": 2500},
    ]
    debug_sql = _normal(response.debug.extra["sql"])
    assert "ds.store_id = ?" in debug_sql
    assert "agg_src.store_id = ?" not in debug_sql


def test_p0_103_non_join_dimension_id_slice_stays_outer_only(
    tmp_path,
) -> None:
    db_path = tmp_path / "aggregate_relation_non_join_dimension_id_slice.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(
        _right_model(),
        _left_dimension_slice_non_key_model(),
        executor=executor,
    )
    request = SemanticQueryRequest(
        columns=["orderId", "amount", "salesAmount"],
        slice=[{"field": "store$id", "op": "=", "value": 1}],
    )

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationDimensionSliceNonKeyQueryModel",
        request,
    )
    normalized = _normal(result.sql)
    assert result.params == ["COMPLETED", 1]
    assert "left join dim_store ds on t1.store_key = ds.store_key" in normalized
    assert "ds.store_key = ?" in normalized
    assert "agg_src.store_key = ?" not in normalized
    assert "store$id" not in normalized
    assert result.diagnostics == [
        {
            "decision": "refused",
            "field": "store$id",
            "op": "=",
            "target": None,
            "reasonCode": "NO_JOIN_KEY_MAPPING",
            "expression": None,
        }
    ]

    try:
        response = service.query_model(
            "OrderSalesAggregateRelationDimensionSliceNonKeyQueryModel",
            request,
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert response.params == ["COMPLETED", 1]
    assert response.items == [
        {"orderId": ORDER_1, "amount": 10998, "salesAmount": 9898.2},
        {"orderId": ORDER_2, "amount": 2500, "salesAmount": 2500},
    ]
    debug_sql = _normal(response.debug.extra["sql"])
    assert "ds.store_key = ?" in debug_sql
    assert "agg_src.store_key = ?" not in debug_sql


def test_p0_104_rhs_dimension_id_fixed_filter_joins_dimension_inside_rhs(
    tmp_path,
) -> None:
    db_path = tmp_path / "aggregate_relation_rhs_dimension_id_filter.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(
        _rhs_dimension_filter_right_model(),
        _rhs_dimension_id_filter_model(),
        executor=executor,
    )
    request = SemanticQueryRequest(
        columns=["orderId", "amount", "salesAmount"],
        slice=[{"field": "orderId", "op": "=", "value": ORDER_1}],
    )

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationRhsDimensionIdFilterQueryModel",
        request,
    )
    normalized = _normal(result.sql)
    assert result.params == ["COMPLETED", 101, ORDER_1, ORDER_1]
    assert "left join dim_product dp on agg_src.product_key = dp.product_key" in normalized
    assert "dp.product_key = ?" in normalized
    assert "agg_src.product$id" not in normalized
    assert "product$id" not in normalized
    assert result.diagnostics == [
        {
            "decision": "pushed",
            "field": "orderId",
            "op": "=",
            "target": "where",
            "reasonCode": None,
            "expression": "agg_src.order_id = ?",
        }
    ]

    try:
        response = service.query_model(
            "OrderSalesAggregateRelationRhsDimensionIdFilterQueryModel",
            request,
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert response.params == ["COMPLETED", 101, ORDER_1, ORDER_1]
    assert response.items == [
        {"orderId": ORDER_1, "amount": 10998, "salesAmount": 5000}
    ]
    debug_sql = _normal(response.debug.extra["sql"])
    assert "left join dim_product dp on agg_src.product_key = dp.product_key" in debug_sql
    assert "dp.product_key = ?" in debug_sql
    assert "product$id" not in debug_sql


def test_p0_85_and_filters_push_to_rhs_with_diagnostics() -> None:
    case = _case("aggregate-join-and-pushdown-diagnostics")
    service = _service(_right_model(), _left_model())

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationQueryModel",
        _request(
            slice=[
                {"field": "orderId", "op": "in", "value": [ORDER_1, ORDER_2]},
                {"field": "salesAmount", "op": "[]", "value": [0, 999999999]},
            ],
        ),
    )

    normalized = _normal(result.sql)
    for marker in case["expected"]["sqlMarkers"]:
        assert marker in normalized
    assert {
        (item["decision"], item["field"], item["target"], item["expression"])
        for item in result.diagnostics
    } == {
        ("pushed", "orderId", "where", "agg_src.order_id in (?, ?)"),
        ("pushed", "salesAmount", "having", "sum(agg_src.sales_amount) >= ?"),
        ("pushed", "salesAmount", "having", "sum(agg_src.sales_amount) <= ?"),
    }


def test_p0_89_group_key_alias_request_slice_pushes_rhs_where(tmp_path) -> None:
    db_path = tmp_path / "aggregate_relation_alias_key.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(_right_model(), _left_alias_key_model(), executor=executor)
    request = SemanticQueryRequest(
        columns=["orderNo", "amount", "salesAmount", "uniqueCustomers"],
        slice=[{"field": "orderNo", "op": "=", "value": ORDER_1}],
    )

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationAliasKeyQueryModel",
        request,
    )
    normalized = _normal(result.sql)
    assert result.params == ["COMPLETED", ORDER_1, ORDER_1]
    assert 't1.order_id "orderNo"' in normalized
    assert "agg_src.order_id = ?" in normalized
    assert "t1.order_id = ?" in normalized
    assert result.diagnostics == [
        {
            "decision": "pushed",
            "field": "orderNo",
            "op": "=",
            "target": "where",
            "reasonCode": None,
            "expression": "agg_src.order_id = ?",
        }
    ]

    try:
        response = service.query_model(
            "OrderSalesAggregateRelationAliasKeyQueryModel",
            request,
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert response.items == [
        {
            "orderNo": ORDER_1,
            "amount": 10998,
            "salesAmount": 9898.2,
            "uniqueCustomers": 1,
        }
    ]


def test_p0_89_derived_relation_params_explain_with_pushed_filters(
    tmp_path,
) -> None:
    db_path = tmp_path / "aggregate_relation_derived_params_explain.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(_right_model(), _left_model(), executor=executor)
    request = _request(
        slice=[
            {"field": "orderId", "op": "=", "value": ORDER_1},
            {"field": "salesAmount", "op": ">", "value": 0},
        ],
    )

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationQueryModel",
        request,
    )
    normalized = _normal(result.sql)
    assert "agg_src.order_status = ?" in normalized
    assert "agg_src.order_id = ?" in normalized
    assert "having sum(agg_src.sales_amount) > ?" in normalized
    assert "t1.order_id = ?" in normalized
    assert "fsByOrder.salesAmount > ?" in normalized
    assert result.params == ["COMPLETED", ORDER_1, 0, ORDER_1, 0]
    assert "COMPLETED" not in result.sql
    assert ORDER_1 not in result.sql
    assert result.sql.count("?") == len(result.params)

    conn = sqlite3.connect(db_path)
    try:
        explain_rows = conn.execute(
            f"EXPLAIN QUERY PLAN {result.sql}",
            result.params,
        ).fetchall()
    finally:
        conn.close()
    assert explain_rows
    assert {
        (item["decision"], item["field"], item["target"], item["expression"])
        for item in result.diagnostics
    } == {
        ("pushed", "orderId", "where", "agg_src.order_id = ?"),
        ("pushed", "salesAmount", "having", "sum(agg_src.sales_amount) > ?"),
    }

    try:
        response = service.query_model(
            "OrderSalesAggregateRelationQueryModel",
            request,
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert response.items == [
        {
            "orderId": ORDER_1,
            "amount": 10998,
            "salesAmount": 9898.2,
            "uniqueCustomers": 1,
        }
    ]


def test_p0_89_structured_request_prunes_unreferenced_rhs_measures() -> None:
    service = _service(_right_model(), _wide_projection_model())

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationWideProjectionQueryModel",
        SemanticQueryRequest(
            columns=["orderId", "amount", "salesAmount", "uniqueCustomers"],
        ),
    )

    normalized = _normal(result.sql)
    assert "sum(agg_src.sales_amount) salesAmount" in normalized
    assert "count(distinct agg_src.customer_key) uniqueCustomers" in normalized
    assert "sum(agg_src.quantity) quantity" not in normalized
    assert "sum(agg_src.unit_price) unitPrice" not in normalized
    assert "fsByOrderWide.quantity" not in normalized
    assert "fsByOrderWide.unitPrice" not in normalized
    assert result.params == ["COMPLETED"]
    assert result.diagnostics == []


def test_p0_89_slice_only_aggregate_ref_keeps_required_rhs_measure() -> None:
    service = _service(_right_model(), _wide_projection_model())

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationWideProjectionQueryModel",
        SemanticQueryRequest(
            columns=["orderId", "amount"],
            slice=[{"and": [{"field": "salesAmount", "op": ">", "value": 0}]}],
        ),
    )

    normalized = _normal(result.sql)
    assert "sum(agg_src.sales_amount) salesAmount" in normalized
    assert "having sum(agg_src.sales_amount) > ?" in normalized
    assert "fsByOrderWide.salesAmount > ?" in normalized
    assert "sum(agg_src.quantity) quantity" not in normalized
    assert "sum(agg_src.unit_price) unitPrice" not in normalized
    assert result.params == ["COMPLETED", 0, 0]
    assert result.diagnostics == [
        {
            "decision": "pushed",
            "field": "salesAmount",
            "op": ">",
            "target": "having",
            "reasonCode": None,
            "expression": "sum(agg_src.sales_amount) > ?",
        }
    ]


def test_p0_89_mixed_or_join_key_and_measure_stays_outer_only(tmp_path) -> None:
    db_path = tmp_path / "aggregate_relation_mixed_or.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(_right_model(), _left_model(), executor=executor)
    request = _request(
        slice=[
            {
                "or": [
                    {"field": "orderId", "op": "=", "value": ORDER_2},
                    {"field": "salesAmount", "op": ">", "value": 9000},
                ]
            }
        ],
    )

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationQueryModel",
        request,
    )
    normalized = _normal(result.sql)
    assert result.params == ["COMPLETED", ORDER_2, 9000]
    assert "t1.order_id = ?" in normalized
    assert "fsByOrder.salesAmount > ?" in normalized
    assert " or " in normalized.lower()
    assert "agg_src.order_id = ?" not in normalized
    assert "having sum(agg_src.sales_amount) > ?" not in normalized
    assert {
        (item["decision"], item["field"], item["target"], item["reasonCode"])
        for item in result.diagnostics
    } == {
        ("retained", "orderId", "outer", "OR_CONDITION_OUTER_ONLY"),
        ("retained", "salesAmount", "outer", "OR_CONDITION_OUTER_ONLY"),
    }

    try:
        response = service.query_model(
            "OrderSalesAggregateRelationQueryModel",
            request,
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert sorted(item["orderId"] for item in response.items) == [ORDER_1, ORDER_2]


def test_p0_89_and_wrapper_in_range_slices_push_rhs_filters() -> None:
    service = _service(_right_model(), _left_model())

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationQueryModel",
        _request(
            slice=[
                {
                    "and": [
                        {"field": "orderId", "op": "in", "value": [ORDER_1, ORDER_2]},
                        {
                            "field": "salesAmount",
                            "op": "[]",
                            "value": [0, 999999999],
                        },
                    ]
                }
            ],
        ),
    )

    normalized = _normal(result.sql)
    assert "agg_src.order_id in (?, ?)" in normalized
    assert "having sum(agg_src.sales_amount) >= ?" in normalized
    assert "sum(agg_src.sales_amount) <= ?" in normalized
    assert "t1.order_id in (?, ?)" in normalized
    assert "fsByOrder.salesAmount >= ?" in normalized
    assert "fsByOrder.salesAmount <= ?" in normalized
    assert result.params == [
        "COMPLETED",
        ORDER_1,
        ORDER_2,
        0,
        999999999,
        ORDER_1,
        ORDER_2,
        0,
        999999999,
    ]
    assert {
        (item["decision"], item["field"], item["target"], item["expression"])
        for item in result.diagnostics
    } == {
        ("pushed", "orderId", "where", "agg_src.order_id in (?, ?)"),
        ("pushed", "salesAmount", "having", "sum(agg_src.sales_amount) >= ?"),
        ("pushed", "salesAmount", "having", "sum(agg_src.sales_amount) <= ?"),
    }


def test_p0_85_or_filters_stay_outer_with_retained_diagnostics() -> None:
    case = _case("aggregate-join-or-outer-only-diagnostics")
    service = _service(_right_model(), _left_model())

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationQueryModel",
        _request(
            slice=[
                {
                    "or": [
                        {"field": "orderId", "op": "=", "value": ORDER_1},
                        {"field": "orderId", "op": "=", "value": ORDER_2},
                    ]
                }
            ],
        ),
    )

    normalized = _normal(result.sql)
    for marker in case["expected"]["sqlMarkers"]:
        assert marker in normalized
    for marker in case["expected"]["forbiddenSqlMarkers"]:
        assert marker not in normalized
    assert [item["reasonCode"] for item in result.diagnostics] == [
        "OR_CONDITION_OUTER_ONLY",
        "OR_CONDITION_OUTER_ONLY",
    ]


def test_p0_85_runtime_extdata_filter_resolves_or_fails_closed() -> None:
    service = _service(_right_model(), _runtime_filter_model())

    response = service.query_model(
        "OrderSalesAggregateRelationRuntimeFilterQueryModel",
        _request(slice=[{"field": "orderId", "op": "=", "value": ORDER_1}]),
        mode="validate",
        context=SemanticRequestContext(attributes={"extData": {"orderId": ORDER_1}}),
    )

    assert response.error is None
    assert response.sql is not None
    assert "ctx.extData" not in response.sql
    assert response.params == ["COMPLETED", ORDER_1, ORDER_1, ORDER_1]

    missing = service.query_model(
        "OrderSalesAggregateRelationRuntimeFilterQueryModel",
        _request(),
        mode="validate",
    )
    assert missing.sql is None
    assert missing.error is not None
    assert AGGREGATE_JOIN_RUNTIME_FILTER_MISSING_CODE in missing.error


def test_p0_94_runtime_extdata_filter_rejects_unsafe_strings() -> None:
    case = _case("aggregate-join-runtime-filter-unsafe-refusal")
    service = _service(_right_model(), _runtime_filter_model())
    unsafe_value = "ORD001' OR '1'='1"

    response = service.query_model(
        "OrderSalesAggregateRelationRuntimeFilterQueryModel",
        _request(),
        mode="validate",
        context=SemanticRequestContext(
            attributes={"extData": {"orderId": unsafe_value}},
        ),
    )

    assert response.sql is None
    assert response.error is not None
    assert AGGREGATE_JOIN_RUNTIME_FILTER_UNSAFE_CODE in response.error
    for marker in case["expected"]["messageMarkers"]:
        assert marker in response.error
    for marker in case["expected"]["forbiddenMessageMarkers"]:
        assert marker not in response.error
    assert response.error_detail is not None
    assert response.error_detail["code"] == AGGREGATE_JOIN_RUNTIME_FILTER_UNSAFE_CODE


@pytest.mark.parametrize(
    ("case_id", "op", "outer_marker", "forbidden_marker"),
    [
        (
            "aggregate-join-null-check-outer-only-is-null",
            "is null",
            "fsByPaymentMethod.paymentMethod is null",
            "agg_src.payment_method is null",
        ),
        (
            "aggregate-join-null-check-outer-only-is-not-null",
            "is not null",
            "fsByPaymentMethod.paymentMethod is not null",
            "agg_src.payment_method is not null",
        ),
    ],
)
def test_p0_94_null_check_on_relation_group_key_stays_outer_only(
    case_id: str,
    op: str,
    outer_marker: str,
    forbidden_marker: str,
) -> None:
    case = _case(case_id)
    service = _service(_right_model(), _payment_method_group_model())

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationPaymentMethodQueryModel",
        SemanticQueryRequest(
            columns=["orderId", "amount"],
            slice=[{"field": "paymentMethod", "op": op}],
        ),
    )

    normalized = _normal(result.sql)
    assert result.params == ["COMPLETED", "CREDIT_CARD"]
    assert "agg_src.payment_method = ?" in normalized
    assert outer_marker in normalized
    assert forbidden_marker not in normalized
    assert result.diagnostics == case["expected"]["diagnostics"]


def test_p0_94_debug_extra_exposes_aggregate_relation_diagnostics() -> None:
    case = _case("aggregate-join-semantic-debug-extra-diagnostics")
    service = _service(_right_model(), _left_model())

    response = service.query_model(
        "OrderSalesAggregateRelationQueryModel",
        _request(
            slice=[
                {"field": "orderId", "op": "in", "value": [ORDER_1, ORDER_2]},
                {"field": "salesAmount", "op": "[]", "value": [0, 999999999]},
            ],
        ),
        mode="validate",
    )

    assert response.error is None
    assert response.debug is not None
    extra = response.debug.extra or {}
    assert {"sql", "params", "aggregateRelationDiagnostics"}.issubset(extra)
    diagnostics = extra["aggregateRelationDiagnostics"]
    assert diagnostics == case["expected"]["diagnostics"]
    assert set(case["expected"]["requiredDecisions"]).issubset(
        {item["decision"] for item in diagnostics}
    )
    assert set(case["expected"]["requiredTargets"]).issubset(
        {item["target"] for item in diagnostics}
    )
    assert set(case["expected"]["requiredFields"]).issubset(
        {item["field"] for item in diagnostics}
    )


def test_p0_95_order_by_aggregate_output_uses_outer_alias(tmp_path) -> None:
    case = _case("aggregate-join-orderby-aggregate-output")
    db_path = tmp_path / "aggregate_relation_order_by.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(_right_model(), _left_model(), executor=executor)
    request = _request(order_by=case["request"]["orderBy"])

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationQueryModel",
        request,
    )
    normalized = _normal(result.sql)
    assert result.params == case["expected"]["params"]
    assert "order by fsByOrder.salesAmount desc" in normalized
    for marker in case["expected"]["sqlMarkers"]:
        assert marker in normalized
    for marker in case["expected"]["forbiddenSqlMarkers"]:
        assert marker not in normalized

    try:
        response = service.query_model(
            "OrderSalesAggregateRelationQueryModel",
            request,
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert [item["orderId"] for item in response.items] == [ORDER_1, ORDER_2]
    assert response.items[0]["salesAmount"] > response.items[1]["salesAmount"]


def test_p0_95_return_total_executes_aggregate_total_data(tmp_path) -> None:
    case = _case("aggregate-join-return-total")
    db_path = tmp_path / "aggregate_relation_return_total.sqlite"
    _seed_aggregate_db(db_path)
    executor = SQLiteExecutor(str(db_path))
    service = _service(_right_model(), _left_model(), executor=executor)
    request = _request(
        slice=case["request"]["slice"],
        return_total=case["request"]["returnTotal"],
    )

    result = service.build_query_with_governance(
        "OrderSalesAggregateRelationQueryModel",
        request,
    )
    assert result.params == case["expected"]["params"]
    assert result.total_params == case["expected"]["params"]
    assert result.total_sql is not None
    total_sql = _normal(result.total_sql)
    assert "from (select" in total_sql
    assert 'count(*) "total"' in total_sql
    assert 't1.total_amount "amount"' in total_sql
    assert 't1.order_id "orderId"' not in total_sql
    for marker in case["expected"]["totalSqlMarkers"]:
        assert marker in total_sql

    try:
        response = service.query_model(
            "OrderSalesAggregateRelationQueryModel",
            request,
            mode="execute",
        )
    finally:
        service._run_async_in_sync(executor.close())

    assert response.error is None
    assert response.total == case["expected"]["total"]
    assert response.total_data is not None
    assert response.total_data["amount"] == pytest.approx(
        case["expected"]["totalData"]["amount"]
    )
    assert response.total_data["salesAmount"] == pytest.approx(
        case["expected"]["totalData"]["salesAmount"]
    )
    assert response.total_data["uniqueCustomers"] == (
        case["expected"]["totalData"]["uniqueCustomers"]
    )
    assert response.total_data["total"] == case["expected"]["totalData"]["total"]
    assert response.debug is not None
    extra = response.debug.extra or {}
    assert "totalSql" in extra
    assert extra["totalParams"] == case["expected"]["params"]


@pytest.mark.asyncio
async def test_p0_85_async_validate_preserves_runtime_extdata_params() -> None:
    service = _service(_right_model(), _runtime_filter_model())

    response = await service.query_model_async(
        "OrderSalesAggregateRelationRuntimeFilterQueryModel",
        _request(slice=[{"field": "orderId", "op": "=", "value": ORDER_1}]),
        mode="validate",
        context=SemanticRequestContext(attributes={"extData": {"orderId": ORDER_1}}),
    )

    assert response.error is None
    assert response.sql is not None
    assert response.params == ["COMPLETED", ORDER_1, ORDER_1, ORDER_1]


def _seed_aggregate_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            create table fact_order (
                order_id text primary key,
                total_amount real,
                store_key integer,
                total_quantity real,
                tenant_id text
            );
            create table fact_sales (
                order_id text,
                store_key integer,
                product_key integer,
                tenant_id text,
                order_status text,
                sales_amount real,
                customer_key integer,
                quantity real,
                unit_price real,
                unit_cost real,
                discount_amount real,
                cost_amount real,
                profit_amount real,
                tax_amount real
            );
            create table dim_product (
                product_key integer primary key,
                category_id text,
                product_name text
            );
            create table dim_store (
                store_key integer primary key,
                store_id text,
                status text,
                area_sqm real
            );
            """
        )
        conn.executemany(
            """
            insert into fact_order(
                order_id,
                total_amount,
                store_key,
                total_quantity,
                tenant_id
            ) values (?, ?, ?, ?, ?)
            """,
            [
                (ORDER_1, 10998.0, 1, 3.0, TENANT_A),
                (ORDER_2, 2500.0, 1, 4.0, TENANT_B),
            ],
        )
        conn.executemany(
            """
            insert into fact_sales(
                order_id,
                store_key,
                product_key,
                tenant_id,
                order_status,
                sales_amount,
                customer_key,
                quantity,
                unit_price,
                unit_cost,
                discount_amount,
                cost_amount,
                profit_amount,
                tax_amount
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (ORDER_1, 2, 101, TENANT_A, "COMPLETED", 5000.0, 7, 2, 2500.0, 1800.0, 0.0, 3600.0, 1400.0, 300.0),
                (ORDER_1, 2, 102, TENANT_A, "COMPLETED", 4898.2, 7, 1, 4898.2, 3100.0, 0.0, 3100.0, 1798.2, 293.89),
                (ORDER_1, 1, 201, TENANT_A, "CANCELLED", 1000.0, 8, 1, 1000.0, 650.0, 0.0, 650.0, 350.0, 60.0),
                (ORDER_2, 1, 201, TENANT_B, "COMPLETED", 2500.0, 9, 4, 625.0, 430.0, 0.0, 1720.0, 780.0, 150.0),
            ],
        )
        conn.executemany(
            """
            insert into dim_product(
                product_key,
                category_id,
                product_name
            ) values (?, ?, ?)
            """,
            [
                (101, "CAT001", "Phone"),
                (102, "CAT001", "Laptop"),
                (201, "CAT002", "Accessory"),
            ],
        )
        conn.executemany(
            """
            insert into dim_store(
                store_key,
                store_id,
                status,
                area_sqm
            ) values (?, ?, ?, ?)
            """,
            [
                (1, "STORE001", "ACTIVE", 350.0),
                (2, "STORE002", "ACTIVE", 150.0),
                (3, "STORE003", "INACTIVE", 50.0),
            ],
        )
        conn.commit()
    finally:
        conn.close()
