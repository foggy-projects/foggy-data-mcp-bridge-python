"""SQLite execution coverage for Python timeWindow SQL lowering."""

from __future__ import annotations

import sqlite3

import pytest

from foggy.dataset.db.executor import SQLiteExecutor
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest
from foggy.mcp_spi.semantic import DeniedColumn, FieldAccessDef


@pytest.fixture()
def sqlite_time_window_service(tmp_path):
    db_path = tmp_path / "time_window.sqlite"
    _seed_time_window_db(db_path)

    executor = SQLiteExecutor(str(db_path))
    service = SemanticQueryService(executor=executor, enable_cache=False)
    service.register_model(create_fact_sales_model())

    yield service

    service._run_async_in_sync(executor.close())


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
            ],
        )
        conn.commit()
    finally:
        conn.close()
