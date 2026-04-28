"""Golden checks against Java 8.3.0.beta timeWindow parity fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest


CATALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_time_window_parity_catalog.json"
)


def _load_cases() -> list[dict[str, Any]]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return catalog["cases"]


def _service() -> SemanticQueryService:
    service = SemanticQueryService()
    service.register_model(create_fact_sales_model())
    return service


def _query_shape(case: dict[str, Any]) -> tuple[list[str], list[str]]:
    comparison = case["comparison"]
    expected_columns = list(case.get("expectedColumns", ()))
    request_columns = case.get("requestColumns")

    if comparison.startswith("rolling_"):
        columns = request_columns or ["salesDate$id", "salesAmount", *expected_columns]
        return _unique(list(columns)), ["salesDate$id"]

    if comparison == "mtd":
        group_by = ["salesDate$year", "salesDate$month", "salesDate$id"]
        columns = request_columns or [*group_by, "salesAmount", *expected_columns]
        return _unique(list(columns)), group_by

    if comparison == "ytd":
        group_by = ["salesDate$year", "salesDate$id"]
        columns = request_columns or [*group_by, "salesAmount", *expected_columns]
        return _unique(list(columns)), group_by

    if comparison == "yoy":
        group_by = ["salesDate$year", "salesDate$month"]
        columns = request_columns or expected_columns
        return _unique(list(columns)), group_by

    if comparison == "mom":
        group_by = ["salesDate$month", "salesDate$id"]
        columns = request_columns or expected_columns
        return _unique(list(columns)), group_by

    if comparison == "wow":
        group_by = ["salesDate$week", "salesDate$dayOfWeek"]
        columns = request_columns or expected_columns
        return _unique(list(columns)), group_by

    columns = request_columns or ["salesDate$id", "salesAmount", *expected_columns]
    return _unique(list(columns)), ["salesDate$id"]


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


@pytest.mark.parametrize(
    "case",
    [case for case in _load_cases() if "expectedError" not in case],
    ids=lambda case: case["name"],
)
def test_java_time_window_happy_fixture_matches_python_sql_contract(case):
    columns, group_by = _query_shape(case)
    response = _service().query_model(
        "FactSalesModel",
        SemanticQueryRequest(
            columns=columns,
            group_by=group_by,
            time_window=case["timeWindow"],
            calculated_fields=case.get("calculatedFields", []),
        ),
        mode="validate",
    )

    assert response.error is None, response.error
    produced_columns = {column["name"] for column in response.columns}
    assert set(case["expectedColumns"]).issubset(produced_columns)

    sql = response.sql or ""
    assertions = case.get("assertions", {})
    if "windowFrame" in assertions:
        assert assertions["windowFrame"] in sql
    if case["timeWindow"].get("rollingAggregator") == "avg":
        assert 'AVG("salesAmount") OVER' in sql
    if case["comparison"] in {"yoy", "mom", "wow"}:
        _assert_comparative_sql(case, sql)
    if case["comparison"] == "ytd":
        assert 'PARTITION BY "salesDate$year"' in sql
        assert "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW" in sql
    if case["comparison"] == "mtd":
        assert 'PARTITION BY "salesDate$year", "salesDate$month"' in sql
        assert "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW" in sql
    if assertions.get("postCalcFieldPresent"):
        assert "FROM (\n" in sql
        for calc in case.get("calculatedFields", []):
            assert f'AS "{calc["name"]}"' in sql
    if assertions.get("growthPercentEqualsRatioTimes100"):
        assert 'tw_result."salesAmount__ratio"' in sql
    if assertions.get("rollingGapEqualsAmountMinusRolling"):
        assert 'tw_result."salesAmount__rolling_7d"' in sql


@pytest.mark.parametrize(
    "case",
    [case for case in _load_cases() if "expectedError" in case],
    ids=lambda case: case["name"],
)
def test_java_time_window_negative_fixture_matches_python_error_code(case):
    response = _service().query_model(
        "FactSalesModel",
        SemanticQueryRequest(
            columns=["salesDate$id", "salesAmount"],
            group_by=["salesDate$id"],
            time_window=case["timeWindow"],
            calculated_fields=case.get("calculatedFields", []),
        ),
        mode="validate",
    )

    assert response.error is not None
    assert case["expectedError"] in response.error


def _assert_comparative_sql(case: dict[str, Any], sql: str) -> None:
    assert "WITH __time_window_base AS" in sql
    assert "LEFT JOIN __time_window_base prior ON" in sql
    assert 'prior."salesAmount" AS "salesAmount__prior"' in sql
    assert '(cur."salesAmount" - prior."salesAmount") AS "salesAmount__diff"' in sql
    assert (
        'CASE WHEN prior."salesAmount" IS NULL OR prior."salesAmount" = 0 '
        'THEN NULL ELSE (cur."salesAmount" - prior."salesAmount") * 1.0 / '
        'prior."salesAmount" END AS "salesAmount__ratio"'
    ) in sql

    comparison = case["comparison"]
    if comparison == "yoy":
        assert 'cur."salesDate$year" = prior."salesDate$year" + 1' in sql
        assert 'cur."salesDate$month" = prior."salesDate$month"' in sql
    elif comparison == "mom":
        assert (
            '(cur."salesDate$year" * 12 + cur."salesDate$month") = '
            '(prior."salesDate$year" * 12 + prior."salesDate$month" + 1)'
        ) in sql
    elif comparison == "wow":
        assert (
            '(cur."salesDate$year" * 53 + cur."salesDate$week") = '
            '(prior."salesDate$year" * 53 + prior."salesDate$week" + 1)'
        ) in sql
