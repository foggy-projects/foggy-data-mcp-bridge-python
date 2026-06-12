"""SQLite aggregate-relation parity tests for P0-82 through P0-85."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from foggy.dataset.db.executor import SQLiteExecutor
from foggy.dataset_model.aggregate_join import (
    AGGREGATE_JOIN_DENIED_SOURCE_COLUMN_CODE,
    AGGREGATE_JOIN_GROUPBY_MISSING_RIGHT_KEY_CODE,
    AGGREGATE_JOIN_RUNTIME_FILTER_MISSING_CODE,
)
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
)
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.mcp_spi import SemanticQueryRequest, SemanticRequestContext
from foggy.mcp_spi.semantic import DeniedColumn

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_querymodel_aggregate_join_snapshot_parity.json"
)

ORDER_1 = "ORD20240101000001"
ORDER_2 = "ORD20240102000004"


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
            "customerKey": DbColumnDef(
                name="customer_key",
                column_type=ColumnType.LONG,
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


def _left_model(
    *,
    name: str = "OrderSalesAggregateRelationQueryModel",
    alias: str | None = "fsByOrder",
    measures: list[AggregateRelationMeasureDef] | None = None,
    filters: list[AggregateRelationFilterDef] | None = None,
    group_by: list[str] | None = None,
) -> DbTableModelImpl:
    return DbTableModelImpl(
        name=name,
        source_table="fact_order",
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
                    )
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


def _service(*models: DbTableModelImpl, executor: Any | None = None) -> SemanticQueryService:
    service = SemanticQueryService(executor=executor, enable_cache=False)
    for model in models:
        service.register_model(model)
    return service


def _request(**kwargs: Any) -> SemanticQueryRequest:
    return SemanticQueryRequest(
        columns=["orderId", "amount", "salesAmount", "uniqueCustomers"],
        **kwargs,
    )


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


def _seed_aggregate_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            create table fact_order (
                order_id text primary key,
                total_amount real
            );
            create table fact_sales (
                order_id text,
                order_status text,
                sales_amount real,
                customer_key integer
            );
            """
        )
        conn.executemany(
            "insert into fact_order(order_id, total_amount) values (?, ?)",
            [
                (ORDER_1, 10998.0),
                (ORDER_2, 2500.0),
            ],
        )
        conn.executemany(
            """
            insert into fact_sales(
                order_id,
                order_status,
                sales_amount,
                customer_key
            ) values (?, ?, ?, ?)
            """,
            [
                (ORDER_1, "COMPLETED", 5000.0, 7),
                (ORDER_1, "COMPLETED", 4898.2, 7),
                (ORDER_1, "CANCELLED", 1000.0, 8),
                (ORDER_2, "COMPLETED", 2500.0, 9),
            ],
        )
        conn.commit()
    finally:
        conn.close()
