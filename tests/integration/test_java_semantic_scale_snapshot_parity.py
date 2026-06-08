"""Replay Java semanticScaleFactor neutral snapshots in Python."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from foggy.dataset_model.definitions.base import AggregationType, ColumnType, DbColumnDef
from foggy.dataset_model.impl.model import (
    DbModelMeasureImpl,
    DbTableModelImpl,
    DimensionJoinDef,
    DimensionPropertyDef,
)
from foggy.dataset_model.impl.semantic_scale import (
    apply_semantic_scale,
    validate_semantic_scale_column,
)
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.mcp_spi import SemanticQueryRequest

SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_semantic_scale_snapshot_parity.json"
)


def _norm(sql: str) -> str:
    return " ".join(sql.split())


def _load_snapshot() -> dict[str, Any]:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def _model() -> DbTableModelImpl:
    model = DbTableModelImpl(name="SemanticScaleFact", source_table="fact_sales")
    model.columns["orderId"] = DbColumnDef(
        name="order_id",
        column_type=ColumnType.STRING,
    )
    model.columns["salesAmountFormulaLeafYuan"] = DbColumnDef(
        name="sales_amount",
        alias="salesAmountFormulaLeafYuan",
        column_type=ColumnType.DECIMAL,
        semantic_scale_factor="100",
        semantic_unit="CNY",
        semantic_unit_label="元",
        formula_def_raw={"value": "alias.sales_amount + 2"},
    )
    model.dimension_joins.append(
        DimensionJoinDef(
            name="product",
            table_name="dim_product",
            foreign_key="product_key",
            primary_key="product_key",
            caption_column="product_name",
            properties=[
                DimensionPropertyDef(
                    column="unit_price",
                    name="unitPriceYuan",
                    data_type="MONEY",
                    semantic_scale_factor="100",
                    semantic_unit="CNY",
                    semantic_unit_label="元",
                )
            ],
        )
    )
    model.add_measure(
        DbModelMeasureImpl(
            name="salesAmountYuan",
            column="sales_amount",
            aggregation=AggregationType.SUM,
            semantic_scale_factor="100",
            semantic_unit="CNY",
            semantic_unit_label="元",
        )
    )
    return model


def _service() -> SemanticQueryService:
    service = SemanticQueryService()
    service.register_model(_model())
    return service


def _request(raw: dict[str, Any]) -> SemanticQueryRequest:
    return SemanticQueryRequest(
        columns=list(raw.get("columns", [])),
        slice=raw.get("slice", []),
        having=raw.get("having", []),
        group_by=raw.get("groupBy", []),
        calculated_fields=raw.get("calculatedFields", []),
    )


def test_snapshot_schema() -> None:
    snapshot = _load_snapshot()
    assert snapshot["schemaVersion"] == 1
    assert snapshot["feature"] == "semanticScaleFactor"
    assert snapshot["source"] == "JavaSemanticScaleSnapshotTest"
    assert snapshot.get("cases")


def test_java_semantic_scale_snapshot_replays_in_python() -> None:
    snapshot = _load_snapshot()
    for case in snapshot["cases"]:
        _assert_case_replays(case)


def _assert_case_replays(case: dict[str, Any]) -> None:
    case_type = case["type"]
    if case_type == "helper":
        _assert_helper_case(case)
    elif case_type == "sql":
        _assert_sql_case(case)
    elif case_type == "metadata":
        _assert_metadata_case(case)
    elif case_type == "model-load-error":
        _assert_model_load_error_case(case)
    else:
        raise AssertionError(f"Unsupported semantic scale snapshot case: {case_type!r}")


def _assert_helper_case(case: dict[str, Any]) -> None:
    expected = case["expected"]
    assert apply_semantic_scale("t.amount", "100") == expected["scaled100"]
    assert apply_semantic_scale("t.amount", "2.50") == expected["scaled250"]


def _assert_sql_case(case: dict[str, Any]) -> None:
    response = _service().query_model(
        "SemanticScaleFact",
        _request(case["request"]),
        mode="validate",
    )
    assert response.error is None, f"[{case['id']}] {response.error}"
    sql = _norm(response.sql or "")
    expected = case["expected"]
    for marker in expected["pythonSqlMarkers"]:
        assert marker in sql, f"[{case['id']}] SQL marker missing: {marker}\n{sql}"
    assert (response.params or []) == expected["pythonParams"]


def _assert_metadata_case(case: dict[str, Any]) -> None:
    metadata = _service().get_metadata_v3(model_names=["SemanticScaleFact"])
    fields = metadata["fields"]
    expected = case["expected"]
    for field_name in case["fields"]:
        field = fields[field_name]
        assert field["semanticScaleFactor"] == expected["semanticScaleFactor"]
        assert field["semanticUnit"] == expected["semanticUnit"]
        assert field["semanticUnitLabel"] == expected["semanticUnitLabel"]


def _assert_model_load_error_case(case: dict[str, Any]) -> None:
    try:
        validate_semantic_scale_column(
            "100",
            case["invalidColumn"],
            field_name=case["field"],
        )
    except ValueError as exc:
        message = str(exc).lower()
    else:
        raise AssertionError(f"[{case['id']}] invalid column should fail closed")

    for marker in case["expected"]["errorMarkers"]:
        assert marker in message
