"""SQLite execution coverage for Python timeWindow SQL lowering."""

from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from foggy.dataset.db.executor import SQLiteExecutor
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest
from foggy.mcp_spi.semantic import DeniedColumn, FieldAccessDef

_CATALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_time_window_parity_catalog.json"
)


@pytest.fixture()
def sqlite_time_window_service(tmp_path):
    db_path = tmp_path / "time_window.sqlite"
    _seed_time_window_db(db_path)

    executor = SQLiteExecutor(str(db_path))
    service = SemanticQueryService(executor=executor, enable_cache=False)
    service.register_model(create_fact_sales_model())

    yield service

    service._run_async_in_sync(executor.close())


def _load_java_time_window_happy_cases() -> list[dict[str, Any]]:
    if not _CATALOG_PATH.exists():
        pytest.skip(f"timeWindow catalog missing: {_CATALOG_PATH}")
    catalog = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    return [case for case in catalog["cases"] if "expectedError" not in case]


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _catalog_query_shape(case: dict[str, Any]) -> tuple[list[str], list[str]]:
    comparison = case["comparison"]
    expected_columns = list(case.get("expectedColumns", ()))
    request_columns = case.get("requestColumns")

    if comparison.startswith("rolling_"):
        columns = request_columns or ["salesDate$id", "salesAmount", *expected_columns]
        return _unique(list(columns)), ["salesDate$id"]

    if comparison == "yoy":
        group_by = ["salesDate$year", "salesDate$month"]
        columns = request_columns or expected_columns
        return _unique(list(columns)), group_by

    if comparison == "mom":
        group_by = ["salesDate$month", "salesDate$id"]
        columns = request_columns or expected_columns
        return _unique(list(columns)), group_by

    if comparison == "mtd":
        group_by = ["salesDate$year", "salesDate$month", "salesDate$id"]
        columns = request_columns or [*group_by, "salesAmount", *expected_columns]
        return _unique(list(columns)), group_by

    if comparison == "ytd":
        group_by = ["salesDate$year", "salesDate$id"]
        columns = request_columns or [*group_by, "salesAmount", *expected_columns]
        return _unique(list(columns)), group_by

    if comparison == "wow":
        group_by = ["salesDate$week", "salesDate$dayOfWeek"]
        columns = request_columns or expected_columns
        return _unique(list(columns)), group_by

    columns = request_columns or ["salesDate$id", "salesAmount", *expected_columns]
    return _unique(list(columns)), ["salesDate$id"]


def _execution_time_window(case: dict[str, Any]) -> dict[str, Any]:
    """Clone Java catalog timeWindow and pin ranges for deterministic SQLite data."""
    time_window = deepcopy(case["timeWindow"])
    comparison = case["comparison"]
    if comparison in {"yoy", "mom"}:
        time_window["value"] = ["20230101", "20250101"]
    elif comparison == "wow":
        time_window["value"] = ["20240201", "20240209"]
    elif comparison == "ytd":
        time_window["value"] = ["20240101", "20240202"]
    else:
        time_window["value"] = ["20240101", "20240109"]
    return time_window


@pytest.mark.parametrize(
    "case",
    _load_java_time_window_happy_cases(),
    ids=lambda case: case["name"],
)
def test_java_time_window_catalog_happy_cases_execute_on_sqlite(
    sqlite_time_window_service,
    case: dict[str, Any],
):
    columns, group_by = _catalog_query_shape(case)
    response = sqlite_time_window_service.query_model(
        "FactSalesModel",
        SemanticQueryRequest(
            columns=columns,
            group_by=group_by,
            time_window=_execution_time_window(case),
            calculated_fields=case.get("calculatedFields", []),
        ),
        mode="execute",
    )

    assert response.error is None, (
        f"[{case['name']}] Python execution failed: {response.error}"
    )
    assert response.items, f"[{case['name']}] expected non-empty SQLite result"

    produced_columns = {column["name"] for column in response.columns}
    expected_columns = set(case["expectedColumns"])
    assert expected_columns.issubset(produced_columns), (
        f"[{case['name']}] missing columns: {expected_columns - produced_columns}"
    )
    for expected in expected_columns:
        assert expected in response.items[0], (
            f"[{case['name']}] result row missing expected field {expected}"
        )

    _assert_catalog_live_result_semantics(case, response.items)


def _assert_catalog_live_result_semantics(
    case: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    comparison = case["comparison"]
    if comparison in {"yoy", "mom", "wow"}:
        _assert_comparative_math(case["name"], rows)
    if comparison in {"mtd", "ytd"}:
        alias = f"salesAmount__{comparison}"
        assert all(row[alias] is not None for row in rows)
        first_by_partition = _first_cumulative_rows(comparison, rows)
        assert first_by_partition
        for row in first_by_partition:
            assert row[alias] == pytest.approx(row["salesAmount"])
    if comparison.startswith("rolling_"):
        alias = f"salesAmount__{comparison}"
        assert all(row[alias] is not None for row in rows)
        if case["name"] == "rolling_7d-post-calc-gap-happy":
            for row in rows:
                assert row["rollingGap"] == pytest.approx(
                    row["salesAmount"] - row[alias]
                )
    if case["name"] == "yoy-month-post-calc-growth-happy":
        matching_rows = [row for row in rows if row["salesAmount__ratio"] is not None]
        assert matching_rows
        for row in matching_rows:
            assert row["growthPercent"] == pytest.approx(
                row["salesAmount__ratio"] * 100
            )


def _assert_comparative_math(case_name: str, rows: list[dict[str, Any]]) -> None:
    rows_with_prior = [row for row in rows if row["salesAmount__prior"] is not None]
    assert rows_with_prior, f"[{case_name}] expected at least one prior-period match"
    for row in rows:
        prior = row["salesAmount__prior"]
        if prior is None:
            assert row["salesAmount__diff"] is None
            assert row["salesAmount__ratio"] is None
            continue
        expected_diff = row["salesAmount"] - prior
        assert row["salesAmount__diff"] == pytest.approx(expected_diff)
        if prior == 0:
            assert row["salesAmount__ratio"] is None
        else:
            assert row["salesAmount__ratio"] == pytest.approx(expected_diff / prior)


def _first_cumulative_rows(
    comparison: str,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sorted_rows = sorted(rows, key=lambda row: row["salesDate$id"])
    first_by_partition: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in sorted_rows:
        if comparison == "mtd":
            key = (row["salesDate$year"], row["salesDate$month"])
        else:
            key = (row["salesDate$year"],)
        first_by_partition.setdefault(key, row)
    return list(first_by_partition.values())


def test_rolling_range_executes_on_sqlite(sqlite_time_window_service):
    response = sqlite_time_window_service.query_model(
        "FactSalesModel",
        SemanticQueryRequest(
            columns=["salesDate$id", "salesAmount", "salesAmount__rolling_7d"],
            group_by=["salesDate$id"],
            time_window={
                "field": "salesDate$id",
                "grain": "day",
                "comparison": "rolling_7d",
                "range": "[)",
                "value": ["20240101", "20240104"],
                "targetMetrics": ["salesAmount"],
            },
            order_by=[{"field": "salesDate$id", "dir": "asc"}],
        ),
        mode="execute",
    )

    assert response.error is None
    assert response.params == [20240101, 20240104]
    assert [
        (
            row["salesDate$id"],
            row["salesAmount"],
            row["salesAmount__rolling_7d"],
        )
        for row in response.items
    ] == [
        (20240101, 150.0, 150.0),
        (20240102, 20.0, 170.0),
        (20240103, 30.0, 200.0),
    ]


def test_rolling_post_calculated_field_executes_on_sqlite(sqlite_time_window_service):
    response = sqlite_time_window_service.query_model(
        "FactSalesModel",
        SemanticQueryRequest(
            columns=[
                "salesDate$id",
                "salesAmount",
                "salesAmount__rolling_7d",
                "rollingGap",
            ],
            group_by=["salesDate$id"],
            time_window={
                "field": "salesDate$id",
                "grain": "day",
                "comparison": "rolling_7d",
                "range": "[)",
                "value": ["20240101", "20240104"],
                "targetMetrics": ["salesAmount"],
            },
            calculated_fields=[
                {
                    "name": "rollingGap",
                    "expression": "salesAmount - salesAmount__rolling_7d",
                }
            ],
            order_by=[{"field": "salesDate$id", "dir": "asc"}],
        ),
        mode="execute",
    )

    assert response.error is None
    assert response.params == [20240101, 20240104]
    assert [
        (
            row["salesDate$id"],
            row["salesAmount"],
            row["salesAmount__rolling_7d"],
            row["rollingGap"],
        )
        for row in response.items
    ] == [
        (20240101, 150.0, 150.0, 0.0),
        (20240102, 20.0, 170.0, -150.0),
        (20240103, 30.0, 200.0, -170.0),
    ]


def test_yoy_comparative_executes_on_sqlite(sqlite_time_window_service):
    response = sqlite_time_window_service.query_model(
        "FactSalesModel",
        SemanticQueryRequest(
            columns=[
                "salesDate$year",
                "salesDate$month",
                "salesAmount",
                "salesAmount__prior",
                "salesAmount__diff",
                "salesAmount__ratio",
            ],
            group_by=["salesDate$year", "salesDate$month"],
            time_window={
                "field": "salesDate$id",
                "grain": "month",
                "comparison": "yoy",
                "targetMetrics": ["salesAmount"],
            },
            order_by=[
                {"field": "salesDate$year", "dir": "asc"},
                {"field": "salesDate$month", "dir": "asc"},
            ],
        ),
        mode="execute",
    )

    assert response.error is None
    row_2024_jan = next(
        row for row in response.items
        if row["salesDate$year"] == 2024 and row["salesDate$month"] == 1
    )
    assert row_2024_jan["salesAmount"] == 200.0
    assert row_2024_jan["salesAmount__prior"] == 100.0
    assert row_2024_jan["salesAmount__diff"] == 100.0
    assert row_2024_jan["salesAmount__ratio"] == 1.0


def test_yoy_post_calculated_field_executes_on_sqlite(sqlite_time_window_service):
    response = sqlite_time_window_service.query_model(
        "FactSalesModel",
        SemanticQueryRequest(
            columns=[
                "salesDate$year",
                "salesDate$month",
                "salesAmount",
                "salesAmount__prior",
                "salesAmount__diff",
                "salesAmount__ratio",
                "growthPercent",
            ],
            group_by=["salesDate$year", "salesDate$month"],
            time_window={
                "field": "salesDate$id",
                "grain": "month",
                "comparison": "yoy",
                "targetMetrics": ["salesAmount"],
            },
            calculated_fields=[
                {
                    "name": "growthPercent",
                    "expression": "salesAmount__ratio * 100",
                }
            ],
            order_by=[
                {"field": "salesDate$year", "dir": "asc"},
                {"field": "salesDate$month", "dir": "asc"},
            ],
        ),
        mode="execute",
    )

    assert response.error is None
    assert response.params == [100]
    row_2024_jan = next(
        row for row in response.items
        if row["salesDate$year"] == 2024 and row["salesDate$month"] == 1
    )
    assert row_2024_jan["growthPercent"] == 100.0


def test_time_window_post_calculated_field_alias_is_orderable(sqlite_time_window_service):
    response = sqlite_time_window_service.query_model(
        "FactSalesModel",
        SemanticQueryRequest(
            columns=[
                "salesDate$year",
                "salesDate$month",
                "salesAmount__ratio",
                "growthPercent",
            ],
            group_by=["salesDate$year", "salesDate$month"],
            time_window={
                "field": "salesDate$id",
                "grain": "month",
                "comparison": "yoy",
                "targetMetrics": ["salesAmount"],
            },
            calculated_fields=[
                {
                    "name": "growthPercent",
                    "alias": "growth_pct",
                    "expression": "salesAmount__ratio * 100",
                }
            ],
            order_by=[{"field": "growthPercent", "dir": "desc"}],
        ),
        mode="execute",
    )

    assert response.error is None
    assert 'ORDER BY "growth_pct" DESC' in response.sql
    assert response.items[0]["growth_pct"] == 100.0


def test_time_window_system_slice_applies_to_base_cte(sqlite_time_window_service):
    response = sqlite_time_window_service.query_model(
        "FactSalesModel",
        SemanticQueryRequest(
            columns=["salesDate$id", "salesAmount", "salesAmount__rolling_7d"],
            group_by=["salesDate$id"],
            time_window={
                "field": "salesDate$id",
                "grain": "day",
                "comparison": "rolling_7d",
                "range": "[)",
                "value": ["20240101", "20240104"],
                "targetMetrics": ["salesAmount"],
            },
            system_slice=[
                {"field": "salesDate$id", "op": "=", "value": 20240102}
            ],
            order_by=[{"field": "salesDate$id", "dir": "asc"}],
        ),
        mode="execute",
    )

    assert response.error is None
    assert [row["salesDate$id"] for row in response.items] == [20240102]
    assert response.items[0]["salesAmount"] == 20.0
    assert response.items[0]["salesAmount__rolling_7d"] == 20.0


def test_time_window_denied_columns_fail_closed(sqlite_time_window_service):
    response = sqlite_time_window_service.query_model(
        "FactSalesModel",
        SemanticQueryRequest(
            columns=["salesDate$id", "salesAmount", "salesAmount__rolling_7d"],
            group_by=["salesDate$id"],
            time_window={
                "field": "salesDate$id",
                "grain": "day",
                "comparison": "rolling_7d",
                "range": "[)",
                "value": ["20240101", "20240104"],
                "targetMetrics": ["salesAmount"],
            },
            denied_columns=[
                DeniedColumn(table="fact_sales", column="sales_amount")
            ],
        ),
        mode="execute",
    )

    assert response.error is not None
    assert "not accessible" in response.error.lower()


def test_time_window_masking_applies_after_execution(sqlite_time_window_service):
    response = sqlite_time_window_service.query_model(
        "FactSalesModel",
        SemanticQueryRequest(
            columns=["salesDate$id", "salesAmount", "salesAmount__rolling_7d"],
            group_by=["salesDate$id"],
            time_window={
                "field": "salesDate$id",
                "grain": "day",
                "comparison": "rolling_7d",
                "range": "[)",
                "value": ["20240101", "20240104"],
                "targetMetrics": ["salesAmount"],
            },
            field_access=FieldAccessDef(
                masking={"salesAmount": "full_mask"}
            ),
            order_by=[{"field": "salesDate$id", "dir": "asc"}],
        ),
        mode="execute",
    )

    assert response.error is None
    assert response.items[0]["salesAmount"] == "***"
    assert response.items[0]["salesAmount__rolling_7d"] == 150.0


def _seed_time_window_db(db_path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE dim_date (
                date_key INTEGER PRIMARY KEY,
                full_date TEXT NOT NULL,
                year INTEGER NOT NULL,
                quarter INTEGER NOT NULL,
                month INTEGER NOT NULL,
                week_of_year INTEGER NOT NULL,
                month_name TEXT,
                day_of_week INTEGER,
                is_weekend INTEGER
            );

            CREATE TABLE fact_sales (
                date_key INTEGER NOT NULL,
                sales_amount REAL NOT NULL
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO dim_date (
                date_key, full_date, year, quarter, month, week_of_year,
                month_name, day_of_week, is_weekend
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (20230101, "2023-01-01", 2023, 1, 1, 52, "Jan", 7, 1),
                (20230201, "2023-02-01", 2023, 1, 2, 5, "Feb", 3, 0),
                (20240101, "2024-01-01", 2024, 1, 1, 1, "Jan", 1, 0),
                (20240102, "2024-01-02", 2024, 1, 1, 1, "Jan", 2, 0),
                (20240103, "2024-01-03", 2024, 1, 1, 1, "Jan", 3, 0),
                (20240201, "2024-02-01", 2024, 1, 2, 5, "Feb", 4, 0),
                (20240208, "2024-02-08", 2024, 1, 2, 6, "Feb", 4, 0),
            ],
        )
        conn.executemany(
            "INSERT INTO fact_sales (date_key, sales_amount) VALUES (?, ?)",
            [
                (20230101, 100.0),
                (20230201, 120.0),
                (20240101, 150.0),
                (20240102, 20.0),
                (20240103, 30.0),
                (20240201, 90.0),
                (20240208, 40.0),
            ],
        )
        conn.commit()
    finally:
        conn.close()
