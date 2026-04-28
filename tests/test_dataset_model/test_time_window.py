"""Python mirror tests for Java TimeWindowDef / TimeWindowValidator."""

import pytest

from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.dataset_model.semantic.time_window import (
    RelativeDateParser,
    TimeWindowDef,
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
