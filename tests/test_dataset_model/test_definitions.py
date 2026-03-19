"""Unit tests for dataset_model definitions and implementations."""

import pytest
from datetime import datetime

from foggy.dataset_model.definitions.base import (
    AiDef,
    ColumnType,
    AggregationType,
    DimensionType,
    DbColumnDef,
    DbTableDef,
)
from foggy.dataset_model.definitions.access import (
    DbAccessDef,
    AccessType,
    RowFilterType,
)
from foggy.dataset_model.definitions.column import DbColumnGroupDef
from foggy.dataset_model.definitions.dict_def import DbDictDef, DbDictItemDef
from foggy.dataset_model.definitions.measure import (
    DbMeasureDef,
    DbFormulaDef,
    MeasureType,
)
from foggy.dataset_model.definitions.order import OrderDef, OrderDirection, NullSortOrder
from foggy.dataset_model.definitions.preagg import (
    PreAggregationDef,
    PreAggFilterDef,
    PreAggMeasureDef,
    PreAggRefreshDef,
    PreAggStatus,
    PreAggRefreshType,
)
from foggy.dataset_model.definitions.query_model import (
    DbQueryModelDef,
    QueryConditionDef,
    QueryModelType,
    JoinDef,
)
from foggy.dataset_model.definitions.query_request import (
    SelectColumnDef,
    CalculatedFieldDef,
    CondRequestDef,
    FilterRequestDef,
    GroupRequestDef,
    OrderRequestDef,
    SliceRequestDef,
    FilterType,
    AggregateFunc,
)
from foggy.dataset_model.engine.expression import (
    SqlExp,
    SqlLiteralExp,
    SqlColumnExp,
    SqlBinaryExp,
    SqlUnaryExp,
    SqlInExp,
    SqlBetweenExp,
    SqlFunctionExp,
    SqlOperator,
    col,
    lit,
    and_,
    or_,
)
from foggy.dataset_model.engine.hierarchy import (
    ChildrenOfOperator,
    DescendantsOfOperator,
    SelfAndDescendantsOfOperator,
    AncestorsOfOperator,
    SiblingsOfOperator,
    LevelOperator,
)
from foggy.dataset_model.impl.model import (
    DbModelDimensionImpl,
    DbModelMeasureImpl,
    DbTableModelImpl,
    DbModelLoadContext,
)


class TestAiDef:
    """Tests for AiDef base class."""

    def test_create_ai_def(self):
        """Test creating an AiDef instance."""
        defn = AiDef(name="test_model")
        assert defn.name == "test_model"
        assert defn.alias is None
        assert defn.description is None
        assert defn.tags == []

    def test_ai_def_with_alias(self):
        """Test AiDef with alias."""
        defn = AiDef(name="test_model", alias="Test Model")
        assert defn.get_display_name() == "Test Model"

    def test_ai_def_validation(self):
        """Test AiDef validation."""
        defn = AiDef(name="test")
        errors = defn.validate_definition()
        assert errors == []

    def test_ai_def_metadata(self):
        """Test AiDef metadata fields."""
        defn = AiDef(
            name="test",
            tags=["tag1", "tag2"],
            metadata={"key": "value"},
            ai_description="AI friendly description",
            ai_examples=["example query 1"]
        )
        assert "tag1" in defn.tags
        assert defn.metadata["key"] == "value"
        assert len(defn.ai_examples) == 1


class TestDbAccessDef:
    """Tests for access control definitions."""

    def test_create_access_def(self):
        """Test creating an access definition."""
        access = DbAccessDef(name="test_access")
        assert access.enabled is True
        assert access.access_type == AccessType.READ

    def test_role_check(self):
        """Test role-based access checking."""
        access = DbAccessDef(
            name="test",
            allowed_roles=["admin", "manager"],
            denied_roles=["guest"]
        )
        assert access.is_role_allowed(["admin"]) is True
        assert access.is_role_allowed(["manager"]) is True
        assert access.is_role_allowed(["guest"]) is False
        assert access.is_role_allowed(["user"]) is False

    def test_row_filter_sql(self):
        """Test row filter SQL generation."""
        access = DbAccessDef(
            name="test",
            row_filter_enabled=True,
            row_filter_expression="region = 'US'"
        )
        sql = access.get_row_filter_sql()
        assert sql == "region = 'US'"


class TestDbDictDef:
    """Tests for dictionary definitions."""

    def test_create_dict_def(self):
        """Test creating a dictionary definition."""
        dic = DbDictDef(name="status_dict")
        assert dic.dict_type == "static"
        assert dic.items == []

    def test_dict_items(self):
        """Test dictionary with items."""
        dic = DbDictDef(
            name="status_dict",
            items=[
                DbDictItemDef(code="1", name="Active"),
                DbDictItemDef(code="2", name="Inactive"),
            ]
        )
        assert len(dic.items) == 2
        assert dic.get_item_by_code("1").name == "Active"
        assert dic.get_item_by_code("3") is None

    def test_hierarchy_items(self):
        """Test hierarchical dictionary items."""
        dic = DbDictDef(
            name="category_dict",
            items=[
                DbDictItemDef(code="1", name="Electronics", level=1),
                DbDictItemDef(code="1-1", name="Phones", parent_code="1", level=2),
                DbDictItemDef(code="1-2", name="Laptops", parent_code="1", level=2),
            ]
        )
        children = dic.get_children("1")
        assert len(children) == 2
        root_items = dic.get_children(None)
        assert len(root_items) == 1


class TestDbMeasureDef:
    """Tests for measure definitions."""

    def test_create_measure(self):
        """Test creating a measure definition."""
        measure = DbMeasureDef(
            name="sales_amount",
            column="amount",
            aggregation=AggregationType.SUM
        )
        assert measure.name == "sales_amount"
        assert measure.aggregation == AggregationType.SUM

    def test_measure_sql(self):
        """Test measure SQL generation."""
        measure = DbMeasureDef(
            name="total_sales",
            column="sales",
            aggregation=AggregationType.SUM
        )
        sql = measure.get_sql_aggregation()
        assert sql == "SUM(sales)"

    def test_count_distinct_measure(self):
        """Test COUNT DISTINCT measure."""
        measure = DbMeasureDef(
            name="unique_users",
            column="user_id",
            aggregation=AggregationType.COUNT_DISTINCT
        )
        sql = measure.get_sql_aggregation()
        assert sql == "COUNT(DISTINCT user_id)"


class TestDbFormulaDef:
    """Tests for formula definitions."""

    def test_create_formula(self):
        """Test creating a formula definition."""
        formula = DbFormulaDef(
            name="profit_margin",
            expression="profit / revenue * 100",
            depends_on=["profit", "revenue"]
        )
        assert formula.name == "profit_margin"
        assert len(formula.depends_on) == 2

    def test_formula_evaluation(self):
        """Test formula evaluation."""
        formula = DbFormulaDef(
            name="total",
            expression="a + b * 2"
        )
        result = formula.evaluate({"a": 10, "b": 5})
        assert result == 20.0

    def test_formula_validation(self):
        """Test formula validation for unsafe operations."""
        formula = DbFormulaDef(
            name="unsafe",
            expression="import os"
        )
        errors = formula.validate_definition()
        assert len(errors) > 0
        assert any("unsafe" in e for e in errors)


class TestPreAggregationDef:
    """Tests for pre-aggregation definitions."""

    def test_create_preagg(self):
        """Test creating a pre-aggregation definition."""
        preagg = PreAggregationDef(
            name="daily_sales",
            query_model="sales_qm",
            dimensions=["date", "region"],
            measures=[
                PreAggMeasureDef(measure_name="sales", aggregation="sum")
            ]
        )
        assert preagg.status == PreAggStatus.PENDING

    def test_preagg_table_name(self):
        """Test auto-generated pre-agg table name."""
        preagg = PreAggregationDef(
            name="daily_sales",
            query_model="sales_qm",
            dimensions=["date", "region"],
            measures=[PreAggMeasureDef(measure_name="sales")]
        )
        table_name = preagg.get_target_table_name()
        assert "preagg" in table_name
        assert "sales_qm" in table_name

    def test_preagg_refresh_check(self):
        """Test pre-agg refresh checking."""
        preagg = PreAggregationDef(
            name="test",
            query_model="test_qm",
            dimensions=["date"],
            measures=[PreAggMeasureDef(measure_name="sales")],
            status=PreAggStatus.READY,
            refresh=PreAggRefreshDef(refresh_type=PreAggRefreshType.MANUAL)
        )
        assert preagg.is_refresh_needed() is False


class TestDbQueryModelDef:
    """Tests for query model definitions."""

    def test_create_query_model(self):
        """Test creating a query model definition."""
        qm = DbQueryModelDef(
            name="sales_qm",
            model_type=QueryModelType.TABLE,
            source_table="sales"
        )
        assert qm.name == "sales_qm"
        assert qm.model_type == QueryModelType.TABLE

    def test_query_model_source_expression(self):
        """Test source expression generation."""
        qm = DbQueryModelDef(
            name="sales_qm",
            source_table="sales",
            source_schema="public"
        )
        source = qm.get_source_expression()
        assert "public.sales" == source

    def test_query_model_with_joins(self):
        """Test query model with joins."""
        qm = DbQueryModelDef(
            name="sales_with_products",
            model_type=QueryModelType.JOIN,
            source_table="sales",
            joins=[
                JoinDef(
                    table="products",
                    join_type="LEFT",
                    on_conditions=[
                        QueryConditionDef(column="sales.product_id", operator="=", value="products.id")
                    ]
                )
            ]
        )
        source = qm.get_source_expression()
        assert "LEFT JOIN" in source


class TestQueryRequestDefs:
    """Tests for query request definitions."""

    def test_select_column(self):
        """Test select column definition."""
        sel = SelectColumnDef(name="amount", alias="total_amount")
        sql = sel.get_select_sql()
        assert "amount" in sql
        assert "total_amount" in sql

    def test_select_column_with_aggregation(self):
        """Test select column with aggregation."""
        sel = SelectColumnDef(
            name="amount",
            aggregate=AggregateFunc.SUM,
            alias="total"
        )
        sql = sel.get_select_sql()
        assert "SUM(amount)" in sql

    def test_condition_request(self):
        """Test condition request."""
        cond = CondRequestDef(
            condition_type=FilterType.SIMPLE,
            column="status",
            operator="=",
            value="active"
        )
        sql = cond.to_sql()
        assert "status" in sql
        assert "active" in sql

    def test_filter_request(self):
        """Test complex filter request."""
        filter_req = FilterRequestDef(
            logic="and",
            conditions=[
                CondRequestDef(column="status", operator="=", value="active"),
                CondRequestDef(column="amount", operator=">", value=100),
            ]
        )
        sql = filter_req.to_sql()
        assert "AND" in sql

    def test_group_request_with_time(self):
        """Test group request with time granularity."""
        group = GroupRequestDef(column="created_at", time_granularity="month")
        sql = group.get_group_sql()
        assert "DATE_FORMAT" in sql

    def test_slice_request_pagination(self):
        """Test slice request pagination."""
        slice_req = SliceRequestDef(page=3, page_size=20)
        offset = slice_req.get_offset()
        assert offset == 40  # (3-1) * 20


class TestSqlExpression:
    """Tests for SQL expression classes."""

    def test_literal_expression(self):
        """Test literal expression."""
        exp = SqlLiteralExp(value="hello")
        assert exp.to_sql() == "'hello'"

        exp_num = SqlLiteralExp(value=42)
        assert exp_num.to_sql() == "42"

        exp_null = SqlLiteralExp(value=None)
        assert exp_null.to_sql() == "NULL"

    def test_column_expression(self):
        """Test column expression."""
        exp = SqlColumnExp(name="id")
        assert exp.to_sql() == "id"

        exp_with_table = SqlColumnExp(name="id", table="users")
        assert exp_with_table.to_sql() == "users.id"

    def test_binary_expression(self):
        """Test binary expression."""
        left = SqlColumnExp(name="a")
        right = SqlLiteralExp(value=10)
        exp = SqlBinaryExp(left=left, operator=SqlOperator.GT, right=right)
        assert exp.to_sql() == "a > 10"

    def test_and_expression(self):
        """Test AND expression."""
        exp1 = SqlColumnExp(name="a").eq(SqlLiteralExp(value=1))
        exp2 = SqlColumnExp(name="b").eq(SqlLiteralExp(value=2))
        and_exp = exp1.and_(exp2)
        sql = and_exp.to_sql()
        assert "AND" in sql

    def test_or_expression(self):
        """Test OR expression."""
        exp1 = SqlColumnExp(name="status").eq(SqlLiteralExp(value="active"))
        exp2 = SqlColumnExp(name="status").eq(SqlLiteralExp(value="pending"))
        or_exp = exp1.or_(exp2)
        sql = or_exp.to_sql()
        assert "OR" in sql

    def test_in_expression(self):
        """Test IN expression."""
        exp = SqlColumnExp(name="id").in_([1, 2, 3])
        sql = exp.to_sql()
        assert "IN" in sql
        assert "1" in sql

    def test_fluent_api(self):
        """Test fluent API for expressions."""
        exp = col("amount").gt(lit(100)).and_(col("status").eq(lit("active")))
        sql = exp.to_sql()
        assert "amount > 100" in sql
        assert "status = 'active'" in sql

    def test_helper_functions(self):
        """Test helper functions."""
        exp = and_(
            col("a").eq(lit(1)),
            col("b").eq(lit(2)),
            col("c").gt(lit(0))
        )
        sql = exp.to_sql()
        assert "AND" in sql


class TestHierarchyOperators:
    """Tests for hierarchy operators."""

    def test_children_of_operator(self):
        """Test children of operator."""
        op = ChildrenOfOperator(dimension="org", member_value="dept_001")
        sql = op.get_descendants("org_closure")
        assert "depth = 1" in sql
        assert "dept_001" in sql

    def test_descendants_of_operator(self):
        """Test descendants of operator."""
        op = DescendantsOfOperator(dimension="org", member_value="dept_001")
        sql = op.get_descendants("org_closure")
        assert "depth > 0" in sql

    def test_descendants_with_max_depth(self):
        """Test descendants with max depth."""
        op = DescendantsOfOperator(
            dimension="org",
            member_value="dept_001",
            max_depth=3
        )
        sql = op.get_descendants("org_closure")
        assert "depth <= 3" in sql

    def test_self_and_descendants(self):
        """Test self and descendants operator."""
        op = SelfAndDescendantsOfOperator(dimension="org", member_value="dept_001")
        sql = op.get_descendants("org_closure")
        # Should include self (depth = 0) and descendants
        assert "parent_id = 'dept_001'" in sql

    def test_ancestors_of_operator(self):
        """Test ancestors of operator."""
        op = AncestorsOfOperator(dimension="org", member_value="dept_005")
        sql = op.get_ancestors("org_closure")
        assert "child_id = 'dept_005'" in sql
        assert "depth > 0" in sql

    def test_siblings_of_operator(self):
        """Test siblings of operator."""
        op = SiblingsOfOperator(
            dimension="org",
            member_value="dept_002",
            include_self=False
        )
        sql = op.get_siblings("org_closure")
        assert "depth = 1" in sql
        assert "dept_002" in sql  # excluded


class TestDbModelImpl:
    """Tests for model implementations."""

    def test_dimension_impl(self):
        """Test dimension implementation."""
        dim = DbModelDimensionImpl(
            name="product_name",
            column="product_name",
            dimension_type=DimensionType.REGULAR
        )
        assert dim.name == "product_name"
        assert dim.get_display_name() == "product_name"
        assert dim.supports_hierarchy_operators() is False

    def test_hierarchical_dimension(self):
        """Test hierarchical dimension."""
        dim = DbModelDimensionImpl(
            name="organization",
            column="org_id",
            is_hierarchical=True,
            hierarchy_table="org_closure",
            parent_column="parent_org_id"
        )
        assert dim.supports_hierarchy_operators() is True

    def test_measure_impl(self):
        """Test measure implementation."""
        measure = DbModelMeasureImpl(
            name="total_sales",
            column="amount",
            aggregation=AggregationType.SUM
        )
        sql = measure.get_sql_expression()
        assert "SUM(amount)" in sql

    def test_calculated_measure(self):
        """Test calculated measure."""
        measure = DbModelMeasureImpl(
            name="profit_margin",
            measure_type=MeasureType.CALCULATED,
            expression="profit / revenue * 100",
            depends_on=["profit", "revenue"]
        )
        assert measure.expression == "profit / revenue * 100"
        assert measure.is_aggregated() is False

    def test_table_model_impl(self):
        """Test table model implementation."""
        model = DbTableModelImpl(
            name="sales_model",
            source_table="sales",
            dimensions={
                "date": DbModelDimensionImpl(name="date", column="sale_date"),
                "region": DbModelDimensionImpl(name="region", column="region_code"),
            },
            measures={
                "amount": DbModelMeasureImpl(
                    name="amount",
                    column="amount",
                    aggregation=AggregationType.SUM
                ),
            }
        )
        assert model.name == "sales_model"
        assert len(model.dimensions) == 2
        assert len(model.measures) == 1
        assert model.get_dimension("date") is not None

    def test_table_model_validation(self):
        """Test table model validation."""
        model = DbTableModelImpl(
            name="test_model",
            source_table="test_table"
        )
        errors = model.validate()
        assert errors == []  # No dimensions/measures required at model level

    def test_load_context(self):
        """Test model load context."""
        ctx = DbModelLoadContext(
            datasource="main_db",
            schema_name="public"
        )
        model = DbTableModelImpl(name="test", source_table="test_table")
        ctx.register_model(model)
        assert ctx.get_model("test") is not None


class TestEnums:
    """Tests for enumeration types."""

    def test_column_type(self):
        """Test column type enum."""
        assert ColumnType.STRING.value == "string"
        assert ColumnType.INTEGER.value == "integer"
        assert ColumnType.DATETIME.value == "datetime"

    def test_aggregation_type(self):
        """Test aggregation type enum."""
        assert AggregationType.SUM.value == "sum"
        assert AggregationType.COUNT_DISTINCT.value == "count_distinct"

    def test_dimension_type(self):
        """Test dimension type enum."""
        assert DimensionType.REGULAR.value == "regular"
        assert DimensionType.TIME.value == "time"
        assert DimensionType.HIERARCHY.value == "hierarchy"


class TestOrderDef:
    """Tests for order definitions."""

    def test_order_def(self):
        """Test order definition."""
        order = OrderDef(name="date_order", column="created_at", direction=OrderDirection.DESC)
        sql = order.to_sql()
        assert "DESC" in sql
        assert "created_at" in sql

    def test_order_with_nulls(self):
        """Test order with null handling."""
        order = OrderDef(
            name="test",
            column="value",
            direction=OrderDirection.ASC,
            nulls=NullSortOrder.FIRST
        )
        sql = order.to_sql()
        assert "NULLS FIRST" in sql


class TestJoinDef:
    """Tests for join definitions."""

    def test_join_def(self):
        """Test join definition."""
        join = JoinDef(
            table="products",
            join_type="LEFT",
            on_conditions=[
                QueryConditionDef(column="sales.product_id", operator="=", value="products.id")
            ]
        )
        sql = join.to_sql()
        assert "LEFT JOIN products" in sql
        assert "ON" in sql


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])