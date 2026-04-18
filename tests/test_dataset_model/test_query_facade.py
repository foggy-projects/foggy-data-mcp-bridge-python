"""Tests for QueryFacade pipeline (service/facade.py).

20+ tests covering ModelResultContext, QueryStep ordering, validation,
inline expression detection, auto group-by, and facade orchestration.
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.service.facade import (
    AutoGroupByStep,
    InlineExpressionStep,
    ModelResultContext,
    QueryFacade,
    QueryRequestValidationStep,
    QueryStep,
)
from foggy.demo.models.ecommerce_models import create_fact_sales_model


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sales_model():
    return create_fact_sales_model()


@pytest.fixture()
def ctx(sales_model):
    """Basic context with a couple of valid columns."""
    return ModelResultContext(
        model_name="FactSalesModel",
        request={"columns": ["salesAmount", "product$caption"]},
        query_model=sales_model,
    )


# ===================================================================
# TestQueryStep — ordering & custom steps
# ===================================================================

class TestQueryStep:

    def test_step_ordering(self):
        """Steps are sorted by their order property."""
        steps = [AutoGroupByStep(), QueryRequestValidationStep(), InlineExpressionStep()]
        sorted_steps = sorted(steps, key=lambda s: s.order)
        assert [s.order for s in sorted_steps] == [0, 5, 10]

    def test_custom_step(self):
        """A user-defined step can be added to the facade."""

        class MyStep(QueryStep):
            @property
            def order(self) -> int:
                return 50

            def before_query(self, context: ModelResultContext) -> bool:
                context.ext_data["custom_ran"] = True
                return True

        facade = QueryFacade()
        facade.add_step(MyStep())
        assert any(isinstance(s, MyStep) for s in facade.steps)

    def test_default_order_is_100(self):
        """The ABC default order is 100."""

        class PlainStep(QueryStep):
            pass

        assert PlainStep().order == 100

    def test_step_name(self):
        assert QueryRequestValidationStep().name == "QueryRequestValidationStep"


# ===================================================================
# TestQueryRequestValidationStep
# ===================================================================

class TestQueryRequestValidationStep:

    def test_valid_columns_no_warnings(self, sales_model):
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": ["salesAmount", "quantity"]},
            query_model=sales_model,
        )
        step = QueryRequestValidationStep()
        result = step.before_query(ctx)
        assert result is True
        assert ctx.warnings == []

    def test_invalid_column_adds_warning(self, sales_model):
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": ["salesAmount", "nonExistentField"]},
            query_model=sales_model,
        )
        step = QueryRequestValidationStep()
        step.before_query(ctx)
        assert len(ctx.warnings) == 1
        assert "nonExistentField" in ctx.warnings[0]

    def test_dimension_join_field_valid(self, sales_model):
        """product$caption is a valid dimension join field."""
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": ["product$caption"]},
            query_model=sales_model,
        )
        step = QueryRequestValidationStep()
        step.before_query(ctx)
        assert ctx.warnings == []

    def test_does_not_abort(self, sales_model):
        """Validation step never aborts, even with all bad columns."""
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": ["bad1", "bad2"]},
            query_model=sales_model,
        )
        step = QueryRequestValidationStep()
        result = step.before_query(ctx)
        assert result is True
        assert len(ctx.warnings) == 2

    def test_empty_columns(self, sales_model):
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": []},
            query_model=sales_model,
        )
        step = QueryRequestValidationStep()
        assert step.before_query(ctx) is True
        assert ctx.warnings == []

    def test_no_columns_key(self, sales_model):
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={},
            query_model=sales_model,
        )
        step = QueryRequestValidationStep()
        assert step.before_query(ctx) is True


# ===================================================================
# TestInlineExpressionStep
# ===================================================================

class TestInlineExpressionStep:

    def test_detects_sum_expression(self, sales_model):
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": ["sum(amount) as total"]},
            query_model=sales_model,
        )
        step = InlineExpressionStep()
        step.before_query(ctx)
        parsed = ctx.ext_data["parsed_inline_expressions"]
        assert len(parsed) == 1
        assert parsed[0]["function"] == "SUM"
        assert parsed[0]["field"] == "amount"
        assert parsed[0]["alias"] == "total"

    def test_ignores_plain_column(self, sales_model):
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": ["orderId"]},
            query_model=sales_model,
        )
        step = InlineExpressionStep()
        step.before_query(ctx)
        assert ctx.ext_data["parsed_inline_expressions"] == []

    def test_stores_in_ext_data(self, sales_model):
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": ["avg(salesAmount) as avgSales"]},
            query_model=sales_model,
        )
        step = InlineExpressionStep()
        step.before_query(ctx)
        assert "parsed_inline_expressions" in ctx.ext_data
        assert ctx.ext_data["parsed_inline_expressions"][0]["function"] == "AVG"

    def test_count_distinct_detected(self, sales_model):
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": ["count_distinct(customer_key)"]},
            query_model=sales_model,
        )
        step = InlineExpressionStep()
        step.before_query(ctx)
        parsed = ctx.ext_data["parsed_inline_expressions"]
        assert len(parsed) == 1
        assert parsed[0]["function"] == "COUNT_DISTINCT"
        assert parsed[0]["alias"] == "count_distinct_customer_key"

    def test_mixed_columns(self, sales_model):
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": ["orderId", "sum(quantity) as qty"]},
            query_model=sales_model,
        )
        step = InlineExpressionStep()
        step.before_query(ctx)
        parsed = ctx.ext_data["parsed_inline_expressions"]
        assert len(parsed) == 1
        assert parsed[0]["field"] == "quantity"

    def test_detects_nested_if_expression(self, sales_model):
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": ["sum(if(orderStatus == 'COMPLETED', salesAmount, 0)) as completedSales"]},
            query_model=sales_model,
        )
        step = InlineExpressionStep()
        step.before_query(ctx)
        parsed = ctx.ext_data["parsed_inline_expressions"]
        assert len(parsed) == 1
        assert parsed[0]["function"] == "SUM"
        assert parsed[0]["field"] == "if(orderStatus == 'COMPLETED', salesAmount, 0)"
        assert parsed[0]["alias"] == "completedSales"


# ===================================================================
# TestAutoGroupByStep
# ===================================================================

class TestAutoGroupByStep:

    def test_auto_group_by_inferred(self, sales_model):
        """Mix of dimension + measure columns => auto groupBy for dims."""
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": ["product$caption", "salesAmount"]},
            query_model=sales_model,
        )
        step = AutoGroupByStep()
        step.before_query(ctx)
        assert ctx.ext_data.get("auto_group_by") == ["product$caption"]
        assert ctx.request["groupBy"] == ["product$caption"]

    def test_explicit_group_by_not_overridden(self, sales_model):
        """Explicit groupBy is preserved."""
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={
                "columns": ["product$caption", "salesAmount"],
                "groupBy": ["product$id"],
            },
            query_model=sales_model,
        )
        step = AutoGroupByStep()
        step.before_query(ctx)
        assert ctx.request["groupBy"] == ["product$id"]
        assert "auto_group_by" not in ctx.ext_data

    def test_no_group_by_without_aggregation(self, sales_model):
        """No measures => no auto groupBy."""
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": ["orderId", "orderStatus"]},
            query_model=sales_model,
        )
        step = AutoGroupByStep()
        step.before_query(ctx)
        assert "auto_group_by" not in ctx.ext_data
        assert "groupBy" not in ctx.request

    def test_inline_expression_triggers_group_by(self, sales_model):
        """Inline expressions count as measures for auto groupBy."""
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": ["orderId", "sum(salesAmount) as total"]},
            query_model=sales_model,
        )
        # Run inline step first to populate ext_data
        InlineExpressionStep().before_query(ctx)
        AutoGroupByStep().before_query(ctx)
        assert ctx.ext_data.get("auto_group_by") == ["orderId"]

    def test_nested_inline_expression_triggers_group_by(self, sales_model):
        """Nested inline aggregates should still count as measures for auto groupBy."""
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": ["orderId", "sum(if(orderStatus == 'COMPLETED', salesAmount, 0)) as completedSales"]},
            query_model=sales_model,
        )
        InlineExpressionStep().before_query(ctx)
        AutoGroupByStep().before_query(ctx)
        assert ctx.ext_data.get("auto_group_by") == ["orderId"]


# ===================================================================
# TestQueryFacade
# ===================================================================

class TestQueryFacade:

    def test_full_pipeline(self, sales_model):
        """All steps execute in order through the facade."""
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": ["product$caption", "salesAmount"]},
            query_model=sales_model,
        )
        facade = QueryFacade()
        result = facade.execute(ctx)
        assert not result.aborted
        # Auto group-by should have been applied
        assert result.request.get("groupBy") == ["product$caption"]

    def test_abort_stops_pipeline(self, sales_model):
        """If a step returns False, the query is not executed."""

        class AbortStep(QueryStep):
            @property
            def order(self) -> int:
                return 1  # runs after validation (0) but before inline (5)

            def before_query(self, context: ModelResultContext) -> bool:
                return False

        called = []

        def query_fn(ctx):
            called.append(True)

        facade = QueryFacade(steps=[QueryRequestValidationStep(), AbortStep()])
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": ["salesAmount"]},
            query_model=sales_model,
        )
        result = facade.execute(ctx, query_fn=query_fn)
        assert result.aborted is True
        assert called == []

    def test_query_fn_called(self, sales_model):
        """query_fn is called between before and after phases."""
        called = []

        def query_fn(ctx):
            called.append("query")
            ctx.result = [{"total": 100}]

        facade = QueryFacade()
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": ["salesAmount"]},
            query_model=sales_model,
        )
        result = facade.execute(ctx, query_fn=query_fn)
        assert called == ["query"]
        assert result.result == [{"total": 100}]

    def test_default_steps(self):
        facade = QueryFacade()
        names = [s.name for s in facade.steps]
        assert "QueryRequestValidationStep" in names
        assert "InlineExpressionStep" in names
        assert "AutoGroupByStep" in names
        assert len(facade.steps) == 3

    def test_add_step_maintains_order(self):

        class EarlyStep(QueryStep):
            @property
            def order(self) -> int:
                return -1

        facade = QueryFacade()
        facade.add_step(EarlyStep())
        assert facade.steps[0].name == "EarlyStep"

    def test_no_query_fn(self, sales_model):
        """Pipeline runs without error when query_fn is None."""
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": ["salesAmount"]},
            query_model=sales_model,
        )
        facade = QueryFacade()
        result = facade.execute(ctx)
        assert not result.aborted
        assert result.result is None

    def test_after_query_runs(self, sales_model):
        """after_query phase runs after the query."""

        class TrackingStep(QueryStep):
            @property
            def order(self) -> int:
                return 200

            def after_query(self, context: ModelResultContext) -> bool:
                context.ext_data["after_ran"] = True
                return True

        facade = QueryFacade(steps=[TrackingStep()])
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": []},
            query_model=sales_model,
        )
        result = facade.execute(ctx)
        assert result.ext_data.get("after_ran") is True

    def test_after_query_abort_stops_remaining(self, sales_model):
        """If after_query returns False, remaining after steps are skipped."""
        order_log = []

        class StopAfterStep(QueryStep):
            @property
            def order(self) -> int:
                return 10

            def after_query(self, context: ModelResultContext) -> bool:
                order_log.append("stop")
                return False

        class LaterAfterStep(QueryStep):
            @property
            def order(self) -> int:
                return 20

            def after_query(self, context: ModelResultContext) -> bool:
                order_log.append("later")
                return True

        facade = QueryFacade(steps=[StopAfterStep(), LaterAfterStep()])
        ctx = ModelResultContext(
            model_name="FactSalesModel",
            request={"columns": []},
            query_model=sales_model,
        )
        facade.execute(ctx)
        assert order_log == ["stop"]
