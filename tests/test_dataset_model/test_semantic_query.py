"""Tests for SemanticQueryService — field resolution, auto-JOIN, aggregation, and V3 metadata.

Aligned with Java tests:
  - BasicQueryTest
  - MultiFactTableJoinTest
  - AggregationQueryTest
  - SemanticServiceV3Test
"""

import pytest
from pathlib import Path

from foggy.dataset_model.semantic.service import SemanticQueryService, QueryBuildResult
from foggy.dataset_model.impl.model import (
    DbTableModelImpl,
    DbModelDimensionImpl,
    DbModelMeasureImpl,
    DimensionJoinDef,
    DimensionPropertyDef,
)
from foggy.dataset_model.definitions.base import DbColumnDef, ColumnType
from foggy.demo.models.ecommerce_models import (
    create_fact_sales_model,
    create_fact_order_model,
)
from foggy.mcp_spi import SemanticQueryRequest
from foggy.dataset_model.impl.loader import load_models_from_directory


# ==================== Fixtures ====================


@pytest.fixture
def sales_model() -> DbTableModelImpl:
    """Create FactSalesModel for testing."""
    return create_fact_sales_model()


@pytest.fixture
def order_model() -> DbTableModelImpl:
    """Create FactOrderModel for testing."""
    return create_fact_order_model()


@pytest.fixture
def service(sales_model: DbTableModelImpl) -> SemanticQueryService:
    """Create a SemanticQueryService with FactSalesModel registered."""
    svc = SemanticQueryService()
    svc.register_model(sales_model)
    return svc


@pytest.fixture
def multi_model_service(
    sales_model: DbTableModelImpl,
    order_model: DbTableModelImpl,
) -> SemanticQueryService:
    """Service with both sales and order models registered."""
    svc = SemanticQueryService()
    svc.register_model(sales_model)
    svc.register_model(order_model)
    return svc


@pytest.fixture
def ecommerce_join_service() -> SemanticQueryService:
    """Service with ecommerce TM+QM models loaded from FSScript demo files."""
    svc = SemanticQueryService()
    models = load_models_from_directory(str(Path("src") / "foggy" / "demo" / "models" / "ecommerce"))
    for model in models:
        svc.register_model(model)
    return svc


def _build_sql(service: SemanticQueryService, model_name: str, request: SemanticQueryRequest) -> str:
    """Helper: build query in validate mode and return the SQL string."""
    response = service.query_model(model_name, request, mode="validate")
    assert response.error is None, f"Query build failed: {response.error}"
    assert response.sql is not None
    return response.sql


# ==================== TestFieldResolution ====================


class TestFieldResolution:
    """Test resolve_field() on DbTableModelImpl for V3 field names."""

    def test_resolve_dimension_id(self, sales_model: DbTableModelImpl):
        """product$id resolves to dp.product_key."""
        resolved = sales_model.resolve_field("product$id")
        assert resolved is not None
        assert resolved["sql_expr"] == "dp.product_key"
        assert resolved["is_measure"] is False
        assert resolved["join_def"] is not None

    def test_resolve_dimension_caption(self, sales_model: DbTableModelImpl):
        """product$caption resolves to dp.product_name."""
        resolved = sales_model.resolve_field("product$caption")
        assert resolved is not None
        assert resolved["sql_expr"] == "dp.product_name"
        assert resolved["is_measure"] is False

    def test_resolve_dimension_property(self, sales_model: DbTableModelImpl):
        """product$categoryName resolves to dp.category_name."""
        resolved = sales_model.resolve_field("product$categoryName")
        assert resolved is not None
        assert resolved["sql_expr"] == "dp.category_name"
        assert resolved["is_measure"] is False

    def test_resolve_dimension_brand_property(self, sales_model: DbTableModelImpl):
        """product$brand resolves to dp.brand."""
        resolved = sales_model.resolve_field("product$brand")
        assert resolved is not None
        assert resolved["sql_expr"] == "dp.brand"

    def test_resolve_date_dimension_year(self, sales_model: DbTableModelImpl):
        """salesDate$year resolves to dd.year."""
        resolved = sales_model.resolve_field("salesDate$year")
        assert resolved is not None
        assert resolved["sql_expr"] == "dd.year"
        assert resolved["table_alias"] == "dd"

    def test_resolve_date_dimension_month(self, sales_model: DbTableModelImpl):
        """salesDate$month resolves to dd.month."""
        resolved = sales_model.resolve_field("salesDate$month")
        assert resolved is not None
        assert resolved["sql_expr"] == "dd.month"

    def test_resolve_customer_province(self, sales_model: DbTableModelImpl):
        """customer$province resolves to dc.province."""
        resolved = sales_model.resolve_field("customer$province")
        assert resolved is not None
        assert resolved["sql_expr"] == "dc.province"
        assert resolved["table_alias"] == "dc"

    def test_resolve_customer_member_level(self, sales_model: DbTableModelImpl):
        """customer$memberLevel resolves to dc.member_level."""
        resolved = sales_model.resolve_field("customer$memberLevel")
        assert resolved is not None
        assert resolved["sql_expr"] == "dc.member_level"

    def test_resolve_measure(self, sales_model: DbTableModelImpl):
        """salesAmount is a measure with SUM aggregation."""
        resolved = sales_model.resolve_field("salesAmount")
        assert resolved is not None
        assert resolved["is_measure"] is True
        assert resolved["aggregation"] == "SUM"
        assert resolved["sql_expr"] == "t.sales_amount"

    def test_resolve_measure_quantity(self, sales_model: DbTableModelImpl):
        """quantity is a measure with SUM aggregation."""
        resolved = sales_model.resolve_field("quantity")
        assert resolved is not None
        assert resolved["is_measure"] is True
        assert resolved["aggregation"] == "SUM"

    def test_resolve_fact_dimension(self, sales_model: DbTableModelImpl):
        """orderStatus resolves to t.order_status (fact table own column)."""
        resolved = sales_model.resolve_field("orderStatus")
        assert resolved is not None
        assert resolved["sql_expr"] == "t.order_status"
        assert resolved["is_measure"] is False
        assert resolved["join_def"] is None

    def test_resolve_fact_dimension_payment_method(self, sales_model: DbTableModelImpl):
        """paymentMethod resolves to t.payment_method."""
        resolved = sales_model.resolve_field("paymentMethod")
        assert resolved is not None
        assert resolved["sql_expr"] == "t.payment_method"

    def test_resolve_unknown_field(self, sales_model: DbTableModelImpl):
        """nonExistent$id returns None."""
        resolved = sales_model.resolve_field("nonExistent$id")
        assert resolved is None

    def test_resolve_unknown_property(self, sales_model: DbTableModelImpl):
        """product$nonExistent returns None."""
        resolved = sales_model.resolve_field("product$nonExistent")
        assert resolved is None

    def test_resolve_completely_unknown(self, sales_model: DbTableModelImpl):
        """Completely unknown field name returns None."""
        resolved = sales_model.resolve_field("totallyBogus")
        assert resolved is None

    def test_resolve_join_def_present_for_dimension(self, sales_model: DbTableModelImpl):
        """Resolved dimension field carries its join_def."""
        resolved = sales_model.resolve_field("product$id")
        assert resolved is not None
        join_def = resolved["join_def"]
        assert join_def is not None
        assert join_def.table_name == "dim_product"
        assert join_def.foreign_key == "product_key"


# ==================== TestAutoJoinQuery ====================


class TestAutoJoinQuery:
    """Test auto-JOIN SQL generation (aligned with Java BasicQueryTest + MultiFactTableJoinTest)."""

    def test_simple_field_query(self, service: SemanticQueryService):
        """columns=[orderStatus, salesAmount] -> FROM fact_sales, no JOIN."""
        request = SemanticQueryRequest(columns=["orderStatus", "salesAmount"])
        sql = _build_sql(service, "FactSalesModel", request)
        assert "fact_sales" in sql
        assert "t.order_status" in sql
        assert "SUM(t.sales_amount)" in sql
        assert "JOIN" not in sql.upper().split("WHERE")[0].replace("LEFT", "").replace("RIGHT", "").replace("INNER", "") or "JOIN" not in sql

    def test_simple_field_query_no_join(self, service: SemanticQueryService):
        """Fact-only columns should produce no JOIN clause at all."""
        request = SemanticQueryRequest(columns=["orderStatus", "salesAmount"])
        sql = _build_sql(service, "FactSalesModel", request)
        # No LEFT JOIN, INNER JOIN, or any JOIN
        assert "LEFT JOIN" not in sql
        assert "INNER JOIN" not in sql

    def test_dimension_join_query(self, service: SemanticQueryService):
        """product$caption + product$categoryName + salesAmount -> LEFT JOIN dim_product."""
        request = SemanticQueryRequest(
            columns=["product$caption", "product$categoryName", "salesAmount"]
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "LEFT JOIN dim_product" in sql
        assert "dp.product_name" in sql
        assert "dp.category_name" in sql
        assert "SUM(t.sales_amount)" in sql

    def test_dimension_join_on_condition(self, service: SemanticQueryService):
        """JOIN ON condition links fact FK to dimension PK."""
        request = SemanticQueryRequest(columns=["product$caption", "salesAmount"])
        sql = _build_sql(service, "FactSalesModel", request)
        assert "t.product_key = dp.product_key" in sql

    def test_multiple_dimension_join(self, service: SemanticQueryService):
        """product$brand + customer$province + salesAmount -> 2 LEFT JOINs."""
        request = SemanticQueryRequest(
            columns=["product$brand", "customer$province", "salesAmount"]
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "LEFT JOIN dim_product" in sql
        assert "LEFT JOIN dim_customer" in sql
        assert "dp.brand" in sql
        assert "dc.province" in sql

    def test_three_dimension_join(self, service: SemanticQueryService):
        """Three dimension fields from three different tables -> 3 LEFT JOINs."""
        request = SemanticQueryRequest(
            columns=["product$brand", "customer$province", "store$storeType", "salesAmount"]
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "LEFT JOIN dim_product" in sql
        assert "LEFT JOIN dim_customer" in sql
        assert "LEFT JOIN dim_store" in sql

    def test_filter_on_dimension_property(self, service: SemanticQueryService):
        """Filter customer$memberLevel = '钻石' -> LEFT JOIN dim_customer WHERE dc.member_level = ?."""
        request = SemanticQueryRequest(
            columns=["salesAmount"],
            slice=[{"column": "customer$memberLevel", "operator": "=", "value": "钻石"}],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "LEFT JOIN dim_customer" in sql
        assert "dc.member_level" in sql

    def test_filter_on_dimension_generates_join(self, service: SemanticQueryService):
        """Even if dimension is only in filter (not in columns), JOIN is added."""
        request = SemanticQueryRequest(
            columns=["orderStatus", "salesAmount"],
            slice=[{"column": "product$categoryName", "operator": "=", "value": "电子产品"}],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "LEFT JOIN dim_product" in sql
        assert "dp.category_name" in sql

    def test_or_compound_filter(self, service: SemanticQueryService):
        """$or compound filter generates (cond1 OR cond2) SQL."""
        request = SemanticQueryRequest(
            columns=["salesAmount"],
            slice=[{
                "$or": [
                    {"field": "customer$id", "op": "=", "value": 6},
                    {"field": "customer$id", "op": "is null"},
                ]
            }],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert " OR " in sql
        assert "t.customer_key" in sql

    def test_and_compound_filter(self, service: SemanticQueryService):
        """$and compound filter generates cond1 AND cond2 SQL."""
        request = SemanticQueryRequest(
            columns=["salesAmount"],
            slice=[{
                "$and": [
                    {"field": "orderStatus", "op": "=", "value": "completed"},
                    {"field": "customer$id", "op": "=", "value": 1},
                ]
            }],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "t.order_status" in sql
        assert "t.customer_key" in sql

    def test_nested_or_and_filter(self, service: SemanticQueryService):
        """Nested $or with $and generates correct SQL grouping."""
        request = SemanticQueryRequest(
            columns=["salesAmount"],
            slice=[{
                "$or": [
                    {"$and": [
                        {"field": "orderStatus", "op": "=", "value": "completed"},
                        {"field": "customer$id", "op": "=", "value": 1},
                    ]},
                    {"field": "customer$id", "op": "=", "value": 2},
                ]
            }],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert " OR " in sql
        # The $and sub-group should be parenthesized
        assert "(" in sql

    def test_or_filter_triggers_join(self, service: SemanticQueryService):
        """$or with dimension property fields triggers the necessary JOINs."""
        request = SemanticQueryRequest(
            columns=["salesAmount"],
            slice=[{
                "$or": [
                    {"field": "product$categoryName", "op": "=", "value": "电子"},
                    {"field": "product$categoryName", "op": "=", "value": "服装"},
                ]
            }],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "LEFT JOIN dim_product" in sql
        assert "dp.category_name" in sql
        assert " OR " in sql

    def test_order_by_dimension(self, service: SemanticQueryService):
        """ORDER BY product$categoryName -> ORDER BY dp.category_name."""
        request = SemanticQueryRequest(
            columns=["product$categoryName", "salesAmount"],
            order_by=[{"column": "product$categoryName", "direction": "ASC"}],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "ORDER BY" in sql
        assert "dp.category_name" in sql

    def test_order_by_dimension_generates_join(self, service: SemanticQueryService):
        """ORDER BY on a dimension field triggers its JOIN."""
        request = SemanticQueryRequest(
            columns=["salesAmount"],
            order_by=[{"column": "customer$province", "direction": "DESC"}],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "LEFT JOIN dim_customer" in sql

    def test_auto_group_by(self, service: SemanticQueryService):
        """columns=[product$categoryName, salesAmount] -> auto GROUP BY dp.category_name."""
        request = SemanticQueryRequest(
            columns=["product$categoryName", "salesAmount"]
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "GROUP BY" in sql
        assert "dp.category_name" in sql

    def test_explicit_group_by(self, service: SemanticQueryService):
        """Explicit group_by=[product$categoryName] works."""
        request = SemanticQueryRequest(
            columns=["product$categoryName", "salesAmount"],
            group_by=["product$categoryName"],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "GROUP BY" in sql
        assert "dp.category_name" in sql

    def test_no_duplicate_join(self, service: SemanticQueryService):
        """Multiple fields from same dimension -> only 1 LEFT JOIN dim_product."""
        request = SemanticQueryRequest(
            columns=["product$caption", "product$brand", "product$categoryName", "salesAmount"]
        )
        sql = _build_sql(service, "FactSalesModel", request)
        count = sql.count("LEFT JOIN dim_product")
        assert count == 1, f"Expected exactly 1 LEFT JOIN dim_product, got {count}"

    def test_date_dimension_join(self, service: SemanticQueryService):
        """salesDate$year -> LEFT JOIN dim_date."""
        request = SemanticQueryRequest(
            columns=["salesDate$year", "salesAmount"]
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "LEFT JOIN dim_date" in sql
        assert "dd.year" in sql


# ==================== TestAggregationQuery ====================


class TestAggregationQuery:
    """Test aggregation queries (aligned with Java AggregationQueryTest)."""

    def test_group_by_category(self, service: SemanticQueryService):
        """product$categoryName + SUM measures -> GROUP BY dp.category_name."""
        request = SemanticQueryRequest(
            columns=["product$categoryName", "salesAmount", "quantity"]
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "GROUP BY" in sql
        assert "dp.category_name" in sql
        assert "SUM(t.sales_amount)" in sql
        assert "SUM(t.quantity)" in sql

    def test_group_by_date(self, service: SemanticQueryService):
        """salesDate$year + salesDate$month + SUM -> GROUP BY dd.year, dd.month."""
        request = SemanticQueryRequest(
            columns=["salesDate$year", "salesDate$month", "salesAmount"]
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "GROUP BY" in sql
        assert "dd.year" in sql
        assert "dd.month" in sql

    def test_group_by_with_condition(self, service: SemanticQueryService):
        """Filter + group by -> SQL has WHERE + GROUP BY."""
        request = SemanticQueryRequest(
            columns=["product$categoryName", "salesAmount"],
            slice=[{"column": "customer$memberLevel", "operator": "=", "value": "金卡"}],
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "WHERE" in sql
        assert "GROUP BY" in sql
        assert "dc.member_level" in sql
        assert "dp.category_name" in sql

    def test_count_distinct(self, service: SemanticQueryService):
        """uniqueCustomers -> COUNT(DISTINCT t.customer_key)."""
        request = SemanticQueryRequest(
            columns=["product$categoryName", "uniqueCustomers"]
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "COUNT(DISTINCT t.customer_key)" in sql

    def test_multiple_aggregates(self, service: SemanticQueryService):
        """quantity(SUM) + salesAmount(SUM) + orderCount(COUNT_DISTINCT)."""
        request = SemanticQueryRequest(
            columns=["product$categoryName", "quantity", "salesAmount", "orderCount"]
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "SUM(t.quantity)" in sql
        assert "SUM(t.sales_amount)" in sql
        assert "COUNT(DISTINCT t.order_id)" in sql

    def test_aggregation_auto_group_by_fact_dim(self, service: SemanticQueryService):
        """Fact-table dimension + measure -> auto GROUP BY on the dimension column."""
        request = SemanticQueryRequest(
            columns=["orderStatus", "salesAmount"]
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "GROUP BY" in sql
        assert "t.order_status" in sql

    def test_aggregation_auto_group_by_multiple(self, service: SemanticQueryService):
        """Two dimension columns + measure -> GROUP BY both."""
        request = SemanticQueryRequest(
            columns=["orderStatus", "paymentMethod", "salesAmount"]
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "GROUP BY" in sql
        assert "t.order_status" in sql
        assert "t.payment_method" in sql

    def test_no_group_by_when_no_measure(self, service: SemanticQueryService):
        """Only dimension columns (no measure) -> no GROUP BY."""
        request = SemanticQueryRequest(
            columns=["orderStatus", "paymentMethod"]
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "GROUP BY" not in sql

    def test_profit_sum(self, service: SemanticQueryService):
        """profitAmount -> SUM(t.profit_amount)."""
        request = SemanticQueryRequest(
            columns=["product$categoryName", "profitAmount"]
        )
        sql = _build_sql(service, "FactSalesModel", request)
        assert "SUM(t.profit_amount)" in sql

    def test_limit_applied(self, service: SemanticQueryService):
        """LIMIT is applied to the generated SQL."""
        request = SemanticQueryRequest(columns=["salesAmount"], limit=50)
        sql = _build_sql(service, "FactSalesModel", request)
        assert "LIMIT 50" in sql


class TestMultiFactJoinQuery:
    """Test explicit multi-fact JOIN QM SQL generation."""

    def test_order_payment_join_sql_uses_physical_columns(self, ecommerce_join_service: SemanticQueryService):
        request = SemanticQueryRequest(
            columns=["orderId", "paymentId", "payAmount"],
            limit=20,
        )
        sql = _build_sql(ecommerce_join_service, "OrderPaymentJoinQueryModel", request)
        assert "FROM fact_order AS t" in sql
        assert "LEFT JOIN fact_payment AS j1" in sql
        assert "t.order_id = j1.order_id" in sql
        assert "j1.payment_id" in sql
        assert "SUM(j1.pay_amount)" in sql

    def test_sales_return_join_sql_uses_multi_condition_on_physical_columns(self, ecommerce_join_service: SemanticQueryService):
        request = SemanticQueryRequest(
            columns=["orderId", "orderLineNo", "returnId", "returnAmount"],
            limit=20,
        )
        sql = _build_sql(ecommerce_join_service, "SalesReturnJoinQueryModel", request)
        assert "FROM fact_sales AS t" in sql
        assert "LEFT JOIN fact_return AS j1" in sql
        assert "t.order_id = j1.order_id" in sql
        assert "t.order_line_no = j1.order_line_no" in sql
        assert "SUM(j1.return_amount)" in sql

    def test_multi_fact_join_dimension_field_keeps_base_alias_and_adds_join(self, ecommerce_join_service: SemanticQueryService):
        request = SemanticQueryRequest(
            columns=["product$brand", "returnAmount"],
            limit=20,
        )
        sql = _build_sql(ecommerce_join_service, "SalesReturnJoinQueryModel", request)
        assert "LEFT JOIN fact_return AS j1" in sql
        assert "LEFT JOIN dim_product AS dp" in sql
        assert "t.product_key = dp.product_key" in sql
        assert "SUM(j1.return_amount)" in sql


# ==================== TestMetadataV3 ====================


class TestMetadataV3:
    """Test V3 metadata generation (aligned with Java SemanticServiceV3Test)."""

    def test_metadata_json_contains_dimension_fields(self, service: SemanticQueryService):
        """V3 JSON has product$id, product$caption, product$categoryName."""
        meta = service.get_metadata_v3()
        fields = meta["fields"]
        assert "product$id" in fields
        assert "product$caption" in fields
        assert "product$categoryName" in fields

    def test_metadata_json_contains_measures(self, service: SemanticQueryService):
        """V3 JSON has salesAmount with aggregation=SUM."""
        meta = service.get_metadata_v3()
        fields = meta["fields"]
        assert "salesAmount" in fields
        sa = fields["salesAmount"]
        assert sa["measure"] is True
        assert sa["aggregation"] == "SUM"

    def test_metadata_json_count_distinct_measure(self, service: SemanticQueryService):
        """uniqueCustomers has aggregation=COUNT_DISTINCT."""
        meta = service.get_metadata_v3()
        fields = meta["fields"]
        assert "uniqueCustomers" in fields
        uc = fields["uniqueCustomers"]
        assert uc["measure"] is True
        assert uc["aggregation"] == "COUNT_DISTINCT"

    def test_metadata_markdown_contains_dimensions(self, service: SemanticQueryService):
        """Markdown has product$id, product$caption."""
        md = service.get_metadata_v3_markdown()
        assert "product$id" in md
        assert "product$caption" in md

    def test_metadata_markdown_contains_measures(self, service: SemanticQueryService):
        """Markdown has salesAmount."""
        md = service.get_metadata_v3_markdown()
        assert "salesAmount" in md

    def test_metadata_model_info(self, service: SemanticQueryService):
        """models dict has FactSalesModel with factTable=fact_sales."""
        meta = service.get_metadata_v3()
        models = meta["models"]
        assert "FactSalesModel" in models
        info = models["FactSalesModel"]
        assert info["factTable"] == "fact_sales"

    def test_metadata_version(self, service: SemanticQueryService):
        """version = 'v3'."""
        meta = service.get_metadata_v3()
        assert meta["version"] == "v3"

    def test_metadata_has_prompt(self, service: SemanticQueryService):
        """V3 metadata includes a prompt/usage instructions field."""
        meta = service.get_metadata_v3()
        assert "prompt" in meta
        assert len(meta["prompt"]) > 0

    def test_metadata_customer_dimension_fields(self, service: SemanticQueryService):
        """V3 JSON has customer$id, customer$caption, customer$memberLevel."""
        meta = service.get_metadata_v3()
        fields = meta["fields"]
        assert "customer$id" in fields
        assert "customer$caption" in fields
        assert "customer$memberLevel" in fields

    def test_metadata_date_dimension_fields(self, service: SemanticQueryService):
        """V3 JSON has salesDate$id, salesDate$caption, salesDate$year, salesDate$month."""
        meta = service.get_metadata_v3()
        fields = meta["fields"]
        assert "salesDate$id" in fields
        assert "salesDate$caption" in fields
        assert "salesDate$year" in fields
        assert "salesDate$month" in fields

    def test_metadata_multi_model(self, multi_model_service: SemanticQueryService):
        """Multiple models appear in V3 metadata."""
        meta = multi_model_service.get_metadata_v3()
        models = meta["models"]
        assert "FactSalesModel" in models
        assert "FactOrderModel" in models

    def test_metadata_multi_model_markdown_index(self, multi_model_service: SemanticQueryService):
        """Multi-model markdown contains model index header."""
        md = multi_model_service.get_metadata_v3_markdown()
        assert "FactSalesModel" in md
        assert "FactOrderModel" in md

    def test_metadata_field_type_for_measure(self, service: SemanticQueryService):
        """Measure fields have type=NUMBER."""
        meta = service.get_metadata_v3()
        sa = meta["fields"]["salesAmount"]
        assert sa["type"] == "NUMBER"

    def test_metadata_dimension_not_measure(self, service: SemanticQueryService):
        """Dimension fields have measure=False."""
        meta = service.get_metadata_v3()
        pid = meta["fields"]["product$id"]
        assert pid["measure"] is False

    def test_metadata_fact_dimension_present(self, service: SemanticQueryService):
        """Fact table own dimensions (e.g. orderStatus) use plain name (no $id suffix)."""
        meta = service.get_metadata_v3()
        fields = meta["fields"]
        assert "orderStatus" in fields
        # Should NOT have $id suffix for fact table own dimensions
        assert "orderStatus$id" not in fields

    def test_metadata_columns_appear_in_v3(self, service: SemanticQueryService):
        """TM properties stored in model.columns should appear in V3 JSON metadata.

        This tests the fix for the bug where get_metadata_v3() only iterated
        model.dimensions and model.measures, missing model.columns entirely.
        Properties like partner_share (loaded via TM properties section)
        were invisible in V3 metadata.
        """
        # Add a property directly to model.columns (simulating TM properties loading)
        model = service._models["FactSalesModel"]
        model.columns["partnerShare"] = DbColumnDef(
            name="partner_share",   # SQL column name (snake_case)
            alias="Is Shared",
            column_type=ColumnType.BOOLEAN,
            comment="Shared with portal",
        )

        meta = service.get_metadata_v3()
        fields = meta["fields"]
        assert "partnerShare" in fields
        field = fields["partnerShare"]
        assert field["fieldName"] == "partnerShare"
        assert field["sourceColumn"] == "partner_share"
        assert field["type"] == "BOOLEAN"
        assert field["measure"] is False
        assert "FactSalesModel" in field["models"]

        # Clean up
        del model.columns["partnerShare"]

    def test_metadata_columns_sourceColumn_unique(self, service: SemanticQueryService):
        """model.columns entries should NOT create duplicate sourceColumn
        with existing dimension JOIN fields.

        If a column has the same name as an existing field (e.g., already
        added via model.dimensions), the `if col_name not in fields` guard
        should prevent duplication.
        """
        model = service._models["FactSalesModel"]
        # orderStatus already exists in model.dimensions
        model.columns["orderStatus"] = DbColumnDef(
            name="order_status",
            column_type=ColumnType.STRING,
        )

        meta = service.get_metadata_v3()
        fields = meta["fields"]
        # Should still be present (from dimensions), no error
        assert "orderStatus" in fields

        # Clean up
        del model.columns["orderStatus"]

    def test_metadata_columns_not_duplicated_with_dimensions(self, service: SemanticQueryService):
        """Verify no sourceColumn collision between model.columns and dimension JOINs.

        A model.columns entry with the same fieldName as a JOIN dimension's
        $id field should not overwrite it (guarded by `if col_name not in fields`).
        """
        meta = service.get_metadata_v3()
        fields = meta["fields"]
        # product$id exists from dimension JOIN — no plain 'product' entry should exist
        assert "product$id" in fields
        # Verify sourceColumn points to the JOIN FK
        assert fields["product$id"]["sourceColumn"] == "product_key"
