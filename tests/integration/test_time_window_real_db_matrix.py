"""Real DB integration matrix for Python timeWindow SQL lowering.

These tests use the local Java demo databases when available. They skip rather
than fail if the demo containers are not running, but once connected they assert
real execution semantics instead of SQL preview only.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from foggy.dataset.db.executor import DatabaseExecutor, MySQLExecutor, PostgreSQLExecutor
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest


MYSQL8_CONFIG = {
    "host": "localhost",
    "port": 13308,
    "database": "foggy_test",
    "user": "foggy",
    "password": "foggy_test_123",
}

POSTGRES_CONFIG = {
    "host": "localhost",
    "port": 15432,
    "database": "foggy_test",
    "user": "foggy",
    "password": "foggy_test_123",
}


def _service(executor: DatabaseExecutor) -> SemanticQueryService:
    service = SemanticQueryService(executor=executor, enable_cache=False)
    service.register_model(create_fact_sales_model())
    return service


def _close(service: SemanticQueryService, executor: DatabaseExecutor) -> None:
    service._run_async_in_sync(executor.close())


def _probe_or_skip(service: SemanticQueryService) -> None:
    result = service._run_async_in_sync(service._executor.execute("SELECT 1 AS ok"))
    if result.error:
        service._run_async_in_sync(service._executor.close())
        pytest.skip(f"demo database unavailable: {result.error}")


def _query(service: SemanticQueryService, request: SemanticQueryRequest):
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert response.error is None, response.error
    assert response.items
    return response


def _numeric(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _assert_non_null_numeric(row: dict[str, Any], *fields: str) -> None:
    for field in fields:
        assert row[field] is not None, f"{field} should not be NULL in {row}"
        _numeric(row[field])


@pytest.fixture(scope="module")
def mysql8_service():
    executor = MySQLExecutor(**MYSQL8_CONFIG)
    service = _service(executor)
    _probe_or_skip(service)
    yield service
    _close(service, executor)


@pytest.fixture(scope="module")
def postgres_service():
    executor = PostgreSQLExecutor(**POSTGRES_CONFIG)
    service = _service(executor)
    _probe_or_skip(service)
    yield service
    _close(service, executor)


@pytest.fixture(params=["mysql8", "postgres"])
def real_db_service(request):
    if request.param == "mysql8":
        executor = MySQLExecutor(**MYSQL8_CONFIG)
    else:
        executor = PostgreSQLExecutor(**POSTGRES_CONFIG)

    service = _service(executor)
    _probe_or_skip(service)
    yield service
    _close(service, executor)


def test_real_db_rolling_range_uses_compact_date_key_bind_params(real_db_service):
    response = _query(
        real_db_service,
        SemanticQueryRequest(
            columns=["salesDate$id", "salesAmount", "salesAmount__rolling_7d"],
            group_by=["salesDate$id"],
            time_window={
                "field": "salesDate$id",
                "grain": "day",
                "comparison": "rolling_7d",
                "range": "[)",
                "value": ["20240101", "20240108"],
                "targetMetrics": ["salesAmount"],
            },
            order_by=[{"field": "salesDate$id", "dir": "asc"}],
        ),
    )

    assert response.params == [20240101, 20240108]
    assert len(response.items) == 7
    assert [row["salesDate$id"] for row in response.items] == [
        20240101,
        20240102,
        20240103,
        20240104,
        20240105,
        20240106,
        20240107,
    ]
    for row in response.items:
        _assert_non_null_numeric(row, "salesAmount", "salesAmount__rolling_7d")
        assert _numeric(row["salesAmount__rolling_7d"]) >= _numeric(row["salesAmount"])


@pytest.mark.parametrize(
    ("comparison", "grain", "columns", "group_by", "derived_field"),
    [
        (
            "ytd",
            "month",
            ["salesDate$year", "salesDate$month", "salesAmount", "salesAmount__ytd"],
            ["salesDate$year", "salesDate$month"],
            "salesAmount__ytd",
        ),
        (
            "mtd",
            "day",
            ["salesDate$year", "salesDate$month", "salesDate$id", "salesAmount", "salesAmount__mtd"],
            ["salesDate$year", "salesDate$month", "salesDate$id"],
            "salesAmount__mtd",
        ),
    ],
)
def test_real_db_cumulative_windows_execute(real_db_service, comparison, grain, columns, group_by, derived_field):
    response = _query(
        real_db_service,
        SemanticQueryRequest(
            columns=columns,
            group_by=group_by,
            time_window={
                "field": "salesDate$id",
                "grain": grain,
                "comparison": comparison,
                "range": "[)",
                "value": ["20240101", "20240108"],
                "targetMetrics": ["salesAmount"],
            },
            order_by=[{"field": field, "dir": "asc"} for field in group_by],
        ),
    )

    for row in response.items:
        _assert_non_null_numeric(row, "salesAmount", derived_field)
        assert _numeric(row[derived_field]) >= _numeric(row["salesAmount"])


@pytest.mark.parametrize(
    ("comparison", "grain", "columns", "group_by", "expected_min_rows"),
    [
        (
            "yoy",
            "month",
            [
                "salesDate$year",
                "salesDate$month",
                "salesAmount",
                "salesAmount__prior",
                "salesAmount__diff",
                "salesAmount__ratio",
            ],
            ["salesDate$year", "salesDate$month"],
            3,
        ),
        (
            "mom",
            "month",
            [
                "salesDate$year",
                "salesDate$month",
                "salesAmount",
                "salesAmount__prior",
                "salesAmount__diff",
                "salesAmount__ratio",
            ],
            ["salesDate$year", "salesDate$month"],
            2,
        ),
        (
            "wow",
            "week",
            [
                "salesDate$year",
                "salesDate$week",
                "salesAmount",
                "salesAmount__prior",
                "salesAmount__diff",
                "salesAmount__ratio",
            ],
            ["salesDate$year", "salesDate$week"],
            2,
        ),
    ],
)
def test_real_db_comparative_windows_execute(
    real_db_service,
    comparison,
    grain,
    columns,
    group_by,
    expected_min_rows,
):
    response = _query(
        real_db_service,
        SemanticQueryRequest(
            columns=columns,
            group_by=group_by,
            time_window={
                "field": "salesDate$id",
                "grain": grain,
                "comparison": comparison,
                "targetMetrics": ["salesAmount"],
            },
            order_by=[{"field": field, "dir": "asc"} for field in group_by],
        ),
    )

    rows_with_prior = [row for row in response.items if row["salesAmount__prior"] is not None]
    assert len(rows_with_prior) >= expected_min_rows
    for row in rows_with_prior:
        _assert_non_null_numeric(row, "salesAmount", "salesAmount__prior", "salesAmount__diff", "salesAmount__ratio")


def test_mysql8_2025_yoy_seed_returns_non_null_prior(mysql8_service):
    response = _query(
        mysql8_service,
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
    )

    rows_2025 = [row for row in response.items if row["salesDate$year"] == 2025]
    if not rows_2025:
        pytest.skip("MySQL8 demo database does not contain 2025 fact_sales seed rows")

    assert len(rows_2025) == 3
    for row in rows_2025:
        _assert_non_null_numeric(row, "salesAmount", "salesAmount__prior", "salesAmount__diff", "salesAmount__ratio")
