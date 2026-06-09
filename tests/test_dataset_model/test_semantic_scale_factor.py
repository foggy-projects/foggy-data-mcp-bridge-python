from __future__ import annotations

from foggy.dataset_model.definitions.base import AggregationType, ColumnType, DbColumnDef
from foggy.dataset_model.impl.model import (
    DbModelMeasureImpl,
    DbTableModelImpl,
    DimensionJoinDef,
    DimensionPropertyDef,
)
from foggy.dataset_model.impl.semantic_scale import (
    apply_semantic_scale,
    semantic_scale_sql_literal,
    validate_semantic_scale_column,
)
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.mcp_spi import SemanticQueryRequest


def _norm(sql: str) -> str:
    return " ".join(sql.split())


def _model() -> DbTableModelImpl:
    model = DbTableModelImpl(name="SemanticScaleFact", source_table="fact_sales")
    model.columns["orderId"] = DbColumnDef(name="order_id", column_type=ColumnType.STRING)
    model.columns["formulaLeafYuan"] = DbColumnDef(
        name="sales_amount",
        alias="Formula Leaf Yuan",
        column_type=ColumnType.DECIMAL,
        semantic_scale_factor="100",
        semantic_unit="CNY",
        semantic_unit_label="yuan",
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
                    semantic_unit_label="yuan",
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
            semantic_unit_label="yuan",
        )
    )
    model.add_measure(
        DbModelMeasureImpl(
            name="salesAmountFormulaYuan",
            aggregation=AggregationType.SUM,
            formula_def_raw={"value": "alias.sales_amount + 1"},
            semantic_scale_factor="100",
            semantic_unit="CNY",
            semantic_unit_label="yuan",
        )
    )
    return model


def _service() -> SemanticQueryService:
    service = SemanticQueryService()
    service.register_model(_model())
    return service


def _validate(request: SemanticQueryRequest) -> str:
    response = _service().query_model("SemanticScaleFact", request, mode="validate")
    assert response.error is None, response.error
    assert response.sql
    return _norm(response.sql)


def test_semantic_scale_helpers_follow_java_literal_contract():
    assert semantic_scale_sql_literal("100") == "100.0"
    assert semantic_scale_sql_literal("2.50") == "2.5"
    assert apply_semantic_scale("t.sales_amount", "100") == "((t.sales_amount) / 100.0)"


def test_semantic_scale_rejects_sql_expression_column():
    try:
        validate_semantic_scale_column("100", "sales_amount + 0", field_name="sales")
    except ValueError as exc:
        assert "physical column name" in str(exc)
    else:
        raise AssertionError("semanticScaleFactor should reject SQL expression columns")


def test_dimension_property_query_uses_semantic_unit_sql():
    sql = _validate(SemanticQueryRequest(columns=["orderId", "product$unitPriceYuan"]))

    assert "LEFT JOIN dim_product AS dp ON t.product_key = dp.product_key" in sql
    assert '((dp.unit_price) / 100.0) AS "unitPriceYuan"' in sql


def test_measure_select_and_slice_lift_use_semantic_unit_sql():
    sql = _validate(
        SemanticQueryRequest(
            columns=["orderId", "salesAmountYuan"],
            group_by=["orderId"],
            slice=[{"field": "salesAmountYuan", "op": ">", "value": 2000}],
        )
    )

    assert 'SUM(((t.sales_amount) / 100.0)) AS "salesAmountYuan"' in sql
    assert "HAVING SUM(((t.sales_amount) / 100.0)) > ?" in sql


def test_direct_measure_having_requires_selected_aggregate_alias():
    response = _service().query_model(
        "SemanticScaleFact",
        SemanticQueryRequest(
            columns=["orderId", "salesAmountYuan"],
            group_by=["orderId"],
            having=[{"field": "salesAmountYuan", "op": ">", "value": 2000}],
        ),
        mode="validate",
    )

    assert response.sql is None
    assert response.error is not None
    assert "HAVING_REQUIRES_AGGREGATE_FIELD" in response.error
    assert "selected aggregate alias" in response.error


def test_aggregate_alias_having_uses_semantic_unit_sql():
    sql = _validate(
        SemanticQueryRequest(
            columns=["orderId", "sum(salesAmountYuan) as totalSalesAmountYuan"],
            group_by=["orderId"],
            having=[{"field": "totalSalesAmountYuan", "op": ">", "value": 2000}],
        )
    )

    assert 'SUM(((t.sales_amount) / 100.0)) AS "totalSalesAmountYuan"' in sql
    assert "HAVING SUM(((t.sales_amount) / 100.0)) > ?" in sql


def test_property_slice_uses_semantic_unit_sql():
    sql = _validate(
        SemanticQueryRequest(
            columns=["orderId", "formulaLeafYuan"],
            slice=[{"field": "formulaLeafYuan", "op": ">", "value": 1000}],
        )
    )

    assert "WHERE ((t.sales_amount + 2) / 100.0) > ?" in sql


def test_calculated_field_references_scaled_leaf_without_manual_conversion():
    service = _service()
    response = service.query_model(
        "SemanticScaleFact",
        SemanticQueryRequest(
            columns=["salesAmountPlusTen"],
            calculated_fields=[
                {"name": "salesAmountPlusTen", "expression": "salesAmountYuan + 10"},
            ],
        ),
        mode="validate",
    )

    assert response.error is None, response.error
    assert "((t.sales_amount) / 100.0)" in _norm(response.sql or "")
    assert response.params == [10]


def test_formula_def_results_support_semantic_scale_factor():
    sql = _validate(
        SemanticQueryRequest(
            columns=["salesAmountFormulaYuan", "formulaLeafYuan"],
            group_by=["formulaLeafYuan"],
        )
    )

    assert 'SUM(((t.sales_amount + 1) / 100.0)) AS "salesAmountFormulaYuan"' in sql
    assert '((t.sales_amount + 2) / 100.0) AS "Formula Leaf Yuan"' in sql


def test_metadata_exposes_semantic_scale_unit_metadata():
    metadata = _service().get_metadata_v3(model_names=["SemanticScaleFact"])
    fields = metadata["fields"]

    for field_name in ("salesAmountYuan", "formulaLeafYuan", "product$unitPriceYuan"):
        field = fields[field_name]
        assert field["semanticScaleFactor"] == "100"
        assert field["semanticUnit"] == "CNY"
        assert field["semanticUnitLabel"] == "yuan"
