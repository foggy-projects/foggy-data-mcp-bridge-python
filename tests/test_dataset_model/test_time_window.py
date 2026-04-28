"""Python mirror tests for Java TimeWindowDef / TimeWindowValidator."""

from datetime import date

import pytest

from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.dataset_model.semantic.time_window import (
    RelativeDateParser,
    TimeWindowDef,
    TimeWindowExpander,
    TimeWindowValidator,
    collect_time_window_field_sets,
)
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest


ALL_FIELDS = {
    "salesDate$id",
    "salesDate$year",
    "salesDate$quarter",
    "salesDate$month",
    "salesDate$week",
    "salesDate$dayOfYear",
    "salesDate$dayOfWeek",
    "product$id",
    "salesAmount",
    "costAmount",
}
TIME_FIELDS = {"salesDate$id"}
MEASURES = {"salesAmount", "costAmount"}


def _validate(tw: TimeWindowDef):
    return TimeWindowValidator.validate(tw, ALL_FIELDS, TIME_FIELDS, MEASURES)


class TestRelativeDateParser:
    def test_accepts_java_supported_shapes(self):
        assert RelativeDateParser.is_valid("now")
        assert RelativeDateParser.is_valid("-30D")
        assert RelativeDateParser.is_valid("+1M")
        assert RelativeDateParser.is_valid("2024-01-01")
        assert RelativeDateParser.is_valid("20240101")

    def test_rejects_unparseable_values(self):
        assert not RelativeDateParser.is_valid("")
        assert not RelativeDateParser.is_valid("not-a-date")
        assert not RelativeDateParser.is_valid("2024-99-99")

    def test_resolves_relative_values_against_anchor(self):
        anchor = date(2024, 3, 31)

        assert RelativeDateParser.resolve("now", today=anchor) == "2024-03-31"
        assert RelativeDateParser.resolve("-1D", today=anchor) == "2024-03-30"
        assert RelativeDateParser.resolve("+1M", today=anchor) == "2024-04-30"
        assert RelativeDateParser.resolve("-1Q", today=anchor) == "2023-12-31"
        assert RelativeDateParser.resolve("-1Y", today=anchor) == "2023-03-31"
        assert RelativeDateParser.resolve("20240101", today=anchor) == "20240101"


class TestTimeWindowValidator:
    def test_yoy_month_passes(self):
        tw = TimeWindowDef(
            "salesDate$id",
            "month",
            "yoy",
            "[)",
            ("2024-01-01", "2025-01-01"),
            ("salesAmount",),
        )
        assert _validate(tw) is None

    def test_rolling_7d_day_passes(self):
        tw = TimeWindowDef(
            "salesDate$id",
            "day",
            "rolling_7d",
            "[)",
            ("-30D", "now"),
            ("salesAmount",),
            "avg",
        )
        assert _validate(tw) is None

    def test_ytd_month_passes(self):
        tw = TimeWindowDef(
            "salesDate$id",
            "month",
            "ytd",
            "[)",
            ("2024-01-01", "now"),
        )
        assert _validate(tw) is None

    @pytest.mark.parametrize(
        ("tw", "error_code"),
        [
            (
                TimeWindowDef("nonExistentField", "month", "yoy", "[)", ("2024-01-01", "2025-01-01")),
                TimeWindowValidator.FIELD_NOT_FOUND,
            ),
            (
                TimeWindowDef("product$id", "month", "yoy", "[)", ("2024-01-01", "2025-01-01")),
                TimeWindowValidator.FIELD_NOT_TIME,
            ),
            (
                TimeWindowDef("salesDate$id", "day", "yoy", "[)", ("2024-01-01", "2025-01-01")),
                TimeWindowValidator.GRAIN_INCOMPATIBLE,
            ),
            (
                TimeWindowDef("salesDate$id", "week", "mom", "[)", ("2024-01-01", "2025-01-01")),
                TimeWindowValidator.GRAIN_INCOMPATIBLE,
            ),
            (
                TimeWindowDef("salesDate$id", "month", "rolling_7d", "[)", ("2024-01-01", "2025-01-01")),
                TimeWindowValidator.GRAIN_INCOMPATIBLE,
            ),
            (
                TimeWindowDef("salesDate$id", "month", "yoy", "(]", ("2024-01-01", "2025-01-01")),
                TimeWindowValidator.RANGE_INVALID,
            ),
            (
                TimeWindowDef("salesDate$id", "month", "yoy", "[)", ("2024-01-01",)),
                TimeWindowValidator.VALUE_PARSE_FAILED,
            ),
            (
                TimeWindowDef("salesDate$id", "month", "yoy", "[)", ("not-a-date", "also-not-a-date")),
                TimeWindowValidator.VALUE_PARSE_FAILED,
            ),
            (
                TimeWindowDef("salesDate$id", "month", "yoy", "[)", ("2024-01-01", "2025-01-01"), ("missingMetric",)),
                TimeWindowValidator.TARGET_NOT_AGGREGATE,
            ),
            (
                TimeWindowDef("salesDate$id", "day", "rolling_7d", "[)", ("-30D", "now"), ("salesAmount",), "median"),
                TimeWindowValidator.AGG_INVALID,
            ),
        ],
    )
    def test_error_codes_match_java(self, tw, error_code):
        assert _validate(tw) == error_code

    def test_grain_field_not_found(self):
        limited_fields = {"salesDate$id", "salesDate$year", "salesAmount"}
        tw = TimeWindowDef(
            "salesDate$id",
            "month",
            "yoy",
            "[)",
            ("2024-01-01", "2025-01-01"),
            ("salesAmount",),
        )
        assert (
            TimeWindowValidator.validate(tw, limited_fields, TIME_FIELDS, MEASURES)
            == TimeWindowValidator.GRAIN_FIELD_NOT_FOUND
        )


class TestTimeWindowExpander:
    def test_rolling_7d_expands_to_window_projection_ir(self):
        tw = TimeWindowDef(
            "salesDate$id",
            "day",
            "rolling_7d",
            "[)",
            ("-30D", "now"),
            ("salesAmount",),
            "avg",
        )

        result = TimeWindowExpander.expand_rolling(
            tw,
            ["salesDate$id", "product$categoryName"],
            MEASURES,
        )

        assert result.order_by_field == "salesDate$id"
        assert result.partition_by_fields == ("product$categoryName",)
        assert result.window_frame == "ROWS BETWEEN 6 PRECEDING AND CURRENT ROW"
        assert len(result.additional_columns) == 1

        column = result.additional_columns[0]
        assert column.alias == "salesAmount__rolling_7d"
        assert column.agg == "AVG"
        assert column.partition_by == ("product$categoryName",)
        assert column.order_by == ("salesDate$id",)
        assert column.window_frame == "ROWS BETWEEN 6 PRECEDING AND CURRENT ROW"
        assert column.to_calculated_field() == {
            "name": "salesAmount__rolling_7d",
            "expression": "salesAmount",
            "agg": "AVG",
            "partition_by": ["product$categoryName"],
            "window_order_by": [{"field": "salesDate$id", "dir": "asc"}],
            "window_frame": "ROWS BETWEEN 6 PRECEDING AND CURRENT ROW",
        }

    def test_ytd_expands_to_year_partition_with_default_sum(self):
        tw = TimeWindowDef(
            "salesDate$id",
            "month",
            "ytd",
            "[)",
            ("2024-01-01", "now"),
            ("salesAmount",),
        )

        result = TimeWindowExpander.expand_cumulative(
            tw,
            ["salesDate$month", "product$categoryName"],
            MEASURES,
        )

        assert result.partition_by_fields == (
            "product$categoryName",
            "salesDate$year",
        )
        assert result.window_frame == "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW"
        column = result.additional_columns[0]
        assert column.alias == "salesAmount__ytd"
        assert column.agg == "SUM"
        assert column.order_by == ("salesDate$id",)

    def test_mtd_expands_to_year_and_month_partition(self):
        tw = TimeWindowDef(
            "salesDate$id",
            "day",
            "mtd",
            "[)",
            ("2024-01-01", "now"),
            ("salesAmount",),
        )

        result = TimeWindowExpander.expand_cumulative(
            tw,
            ["salesDate$dayOfYear", "product$categoryName"],
            MEASURES,
        )

        assert result.partition_by_fields == (
            "product$categoryName",
            "salesDate$year",
            "salesDate$month",
        )
        assert result.additional_columns[0].alias == "salesAmount__mtd"

    def test_default_target_metrics_are_sorted(self):
        tw = TimeWindowDef(
            "salesDate$id",
            "day",
            "rolling_7d",
            "[)",
            ("-30D", "now"),
        )

        result = TimeWindowExpander.expand_rolling(tw, [], MEASURES)

        assert [column.metric for column in result.additional_columns] == [
            "costAmount",
            "salesAmount",
        ]
        assert [column.alias for column in result.additional_columns] == [
            "costAmount__rolling_7d",
            "salesAmount__rolling_7d",
        ]

    def test_rolling_expander_rejects_non_rolling_comparison(self):
        tw = TimeWindowDef(
            "salesDate$id",
            "month",
            "ytd",
            "[)",
            ("2024-01-01", "now"),
        )

        with pytest.raises(ValueError, match="Not a rolling time window"):
            TimeWindowExpander.expand_rolling(tw, [], MEASURES)

    def test_cumulative_expander_rejects_non_cumulative_comparison(self):
        tw = TimeWindowDef(
            "salesDate$id",
            "day",
            "rolling_7d",
            "[)",
            ("-30D", "now"),
        )

        with pytest.raises(ValueError, match="Not a cumulative time window"):
            TimeWindowExpander.expand_cumulative(tw, [], MEASURES)


class TestTimeWindowServiceGuard:
    def test_collects_ecommerce_time_window_fields(self):
        model = create_fact_sales_model()
        available, time_fields, measures = collect_time_window_field_sets(model)

        assert "salesDate$id" in available
        assert "salesDate$month" in available
        assert "salesDate$id" in time_fields
        assert "salesAmount" in measures

    def test_time_window_value_range_lowers_to_base_cte_filter(self):
        svc = SemanticQueryService()
        svc.register_model(create_fact_sales_model())

        response = svc.query_model(
            "FactSalesModel",
            SemanticQueryRequest(
                columns=["salesDate$id", "salesAmount"],
                group_by=["salesDate$id"],
                time_window={
                    "field": "salesDate$id",
                    "grain": "day",
                    "comparison": "rolling_7d",
                    "value": ["2024-01-01", "2024-02-01"],
                    "targetMetrics": ["salesAmount"],
                    "rollingAggregator": "avg",
                },
            ),
            mode="validate",
        )

        assert response.error is None
        sql = response.sql or ""
        assert "WHERE dd.date_key >= ? AND dd.date_key < ?" in sql
        assert response.params == ["2024-01-01", "2024-02-01"]

    def test_time_window_closed_range_lowers_to_inclusive_end_filter(self):
        svc = SemanticQueryService()
        svc.register_model(create_fact_sales_model())

        response = svc.query_model(
            "FactSalesModel",
            SemanticQueryRequest(
                columns=["salesDate$id", "salesAmount", "salesAmount__ytd"],
                group_by=["salesDate$year", "salesDate$id"],
                time_window={
                    "field": "salesDate$id",
                    "grain": "month",
                    "comparison": "ytd",
                    "range": "[]",
                    "value": ["2024-01-01", "2024-12-31"],
                    "targetMetrics": ["salesAmount"],
                },
            ),
            mode="validate",
        )

        assert response.error is None
        sql = response.sql or ""
        assert "WHERE dd.date_key >= ? AND dd.date_key <= ?" in sql
        assert response.params == ["2024-01-01", "2024-12-31"]

    def test_rolling_7d_sql_preview_uses_two_stage_window_plan(self):
        svc = SemanticQueryService()
        svc.register_model(create_fact_sales_model())

        response = svc.query_model(
            "FactSalesModel",
            SemanticQueryRequest(
                columns=["salesDate$id", "salesAmount", "salesAmount__rolling_7d"],
                group_by=["salesDate$id"],
                time_window={
                    "field": "salesDate$id",
                    "grain": "day",
                    "comparison": "rolling_7d",
                    "targetMetrics": ["salesAmount"],
                },
            ),
            mode="validate",
        )

        assert response.error is None
        sql = response.sql or ""
        assert "WITH __time_window_base AS" in sql
        assert 'SUM(t.sales_amount) AS "salesAmount"' in sql
        assert 'GROUP BY dd.date_key' in sql
        assert (
            'SUM("salesAmount") OVER (ORDER BY "salesDate$id" ASC '
            'ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS "salesAmount__rolling_7d"'
        ) in sql
        assert [column["name"] for column in response.columns] == [
            "salesDate$id",
            "salesAmount",
            "salesAmount__rolling_7d",
        ]

    def test_time_window_group_fields_do_not_infer_metric_as_dimension(self):
        svc = SemanticQueryService()
        svc.register_model(create_fact_sales_model())

        response = svc.query_model(
            "FactSalesModel",
            SemanticQueryRequest(
                columns=["salesDate$id", "salesAmount", "salesAmount__rolling_7d"],
                time_window={
                    "field": "salesDate$id",
                    "grain": "day",
                    "comparison": "rolling_7d",
                    "targetMetrics": ["salesAmount"],
                },
            ),
            mode="validate",
        )

        assert response.error is None
        sql = response.sql or ""
        assert "GROUP BY dd.date_key" in sql
        assert "GROUP BY dd.date_key, t.sales_amount" not in sql

    def test_mtd_sql_preview_partitions_by_year_and_month(self):
        svc = SemanticQueryService()
        svc.register_model(create_fact_sales_model())

        response = svc.query_model(
            "FactSalesModel",
            SemanticQueryRequest(
                columns=[
                    "salesDate$year",
                    "salesDate$month",
                    "salesDate$id",
                    "salesAmount",
                    "salesAmount__mtd",
                ],
                group_by=["salesDate$year", "salesDate$month", "salesDate$id"],
                time_window={
                    "field": "salesDate$id",
                    "grain": "day",
                    "comparison": "mtd",
                    "targetMetrics": ["salesAmount"],
                },
            ),
            mode="validate",
        )

        assert response.error is None
        sql = response.sql or ""
        assert 'dd.year AS "salesDate$year"' in sql
        assert 'dd.month AS "salesDate$month"' in sql
        assert (
            'SUM("salesAmount") OVER (PARTITION BY "salesDate$year", '
            '"salesDate$month" ORDER BY "salesDate$id" ASC '
            'ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS "salesAmount__mtd"'
        ) in sql

    def test_ytd_sql_preview_partitions_by_year(self):
        svc = SemanticQueryService()
        svc.register_model(create_fact_sales_model())

        response = svc.query_model(
            "FactSalesModel",
            SemanticQueryRequest(
                columns=[
                    "salesDate$year",
                    "salesDate$id",
                    "salesAmount",
                    "salesAmount__ytd",
                ],
                group_by=["salesDate$year", "salesDate$id"],
                time_window={
                    "field": "salesDate$id",
                    "grain": "month",
                    "comparison": "ytd",
                    "targetMetrics": ["salesAmount"],
                },
            ),
            mode="validate",
        )

        assert response.error is None
        sql = response.sql or ""
        assert (
            'SUM("salesAmount") OVER (PARTITION BY "salesDate$year" '
            'ORDER BY "salesDate$id" ASC '
            'ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS "salesAmount__ytd"'
        ) in sql

    def test_comparative_time_window_still_fails_closed(self):
        svc = SemanticQueryService()
        svc.register_model(create_fact_sales_model())

        response = svc.query_model(
            "FactSalesModel",
            SemanticQueryRequest(
                columns=["salesDate$month", "salesAmount", "salesAmount__yoy"],
                group_by=["salesDate$month"],
                time_window={
                    "field": "salesDate$id",
                    "grain": "month",
                    "comparison": "yoy",
                    "targetMetrics": ["salesAmount"],
                },
            ),
            mode="validate",
        )

        assert response.error is not None
        assert "TIMEWINDOW_COMPARATIVE_NOT_IMPLEMENTED" in response.error

    def test_invalid_time_window_returns_java_error_code(self):
        svc = SemanticQueryService()
        svc.register_model(create_fact_sales_model())

        response = svc.query_model(
            "FactSalesModel",
            SemanticQueryRequest(
                columns=["salesDate$id", "salesAmount"],
                time_window={
                    "field": "salesDate$id",
                    "grain": "day",
                    "comparison": "yoy",
                    "value": ["2024-01-01", "2025-01-01"],
                    "targetMetrics": ["salesAmount"],
                },
            ),
            mode="validate",
        )

        assert response.error is not None
        assert TimeWindowValidator.GRAIN_INCOMPATIBLE in response.error
