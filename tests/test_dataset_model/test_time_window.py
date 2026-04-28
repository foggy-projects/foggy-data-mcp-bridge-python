"""Python mirror tests for Java TimeWindowDef / TimeWindowValidator."""

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

    def test_valid_time_window_fails_closed_until_execution_parity(self):
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
                    "value": ["-30D", "now"],
                    "targetMetrics": ["salesAmount"],
                    "rollingAggregator": "avg",
                },
            ),
            mode="validate",
        )

        assert response.error is not None
        assert "TIMEWINDOW_NOT_IMPLEMENTED" in response.error

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
