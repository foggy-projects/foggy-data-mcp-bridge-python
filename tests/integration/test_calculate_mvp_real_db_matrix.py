"""Real DB oracle parity for restricted CALCULATE.

The supported public subset is:

    CALCULATE(SUM(metric), REMOVE(groupByDim...))

It lowers to grouped aggregate windows. These tests compare the Python
query_model execution path with handwritten SQL on SQLite, MySQL 8, and
PostgreSQL. The conservative base ``mysql`` dialect remains fail-closed; the
MySQL 8 path opts into the explicit MySql8Dialect capability profile.
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from typing import Any, Iterable

import pytest

from foggy.dataset.db.executor import (
    DatabaseExecutor,
    MySQLExecutor,
    PostgreSQLExecutor,
    SQLiteExecutor,
)
from foggy.dataset.dialects.mysql import MySql8Dialect
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


def _seed_sqlite(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE dim_product (
                product_key INTEGER PRIMARY KEY,
                category_name TEXT
            );
            CREATE TABLE dim_customer (
                customer_key INTEGER PRIMARY KEY,
                customer_type TEXT
            );
            CREATE TABLE fact_sales (
                product_key INTEGER,
                customer_key INTEGER,
                sales_amount REAL
            );

            INSERT INTO dim_product VALUES (1, 'Electronics');
            INSERT INTO dim_product VALUES (2, 'Clothing');

            INSERT INTO dim_customer VALUES (100, 'Retail');
            INSERT INTO dim_customer VALUES (200, 'Wholesale');

            INSERT INTO fact_sales VALUES (1, 100, 10.0);
            INSERT INTO fact_sales VALUES (1, 100, 30.0);
            INSERT INTO fact_sales VALUES (2, 100, 20.0);
            INSERT INTO fact_sales VALUES (1, 200, 60.0);
            INSERT INTO fact_sales VALUES (2, 200, 80.0);
            """
        )
        conn.commit()
    finally:
        conn.close()


def _service(executor: DatabaseExecutor, dialect: Any | None = None) -> SemanticQueryService:
    service = SemanticQueryService(executor=executor, dialect=dialect, enable_cache=False)
    service.register_model(create_fact_sales_model())
    return service


def _close(service: SemanticQueryService, executor: DatabaseExecutor) -> None:
    service._run_async_in_sync(executor.close())


def _execute(service: SemanticQueryService, sql: str, params: list[Any] | None = None):
    return service._run_async_in_sync(service._executor.execute(sql, params=params))


def _probe_or_skip(service: SemanticQueryService) -> None:
    result = _execute(service, "SELECT 1 AS ok")
    if result.error:
        pytest.skip(f"demo database unavailable: {result.error}")

    result = _execute(service, "SELECT COUNT(*) AS cnt FROM fact_sales")
    if result.error:
        pytest.skip(f"demo database schema unavailable: {result.error}")
    if not result.rows or int(result.rows[0]["cnt"]) == 0:
        pytest.skip("demo database has no fact_sales seed rows")


@pytest.fixture(params=["sqlite", "mysql8", "postgres"])
def real_db_service(request, tmp_path):
    if request.param == "sqlite":
        db_path = str(tmp_path / "calculate_mvp.sqlite")
        _seed_sqlite(db_path)
        executor = SQLiteExecutor(db_path)
        service = _service(executor)
    elif request.param == "mysql8":
        executor = MySQLExecutor(**MYSQL8_CONFIG)
        service = _service(executor, dialect=MySql8Dialect())
        _probe_or_skip(service)
    else:
        executor = PostgreSQLExecutor(**POSTGRES_CONFIG)
        service = _service(executor)
        _probe_or_skip(service)

    yield request.param, service
    _close(service, executor)


def _query(service: SemanticQueryService, request: SemanticQueryRequest) -> list[dict[str, Any]]:
    response = service.query_model("FactSalesModel", request, mode="execute")
    assert response.error is None, response.error
    assert "SUM(SUM(" in (response.sql or "")
    return response.items


def _oracle(service: SemanticQueryService, sql: str) -> list[dict[str, Any]]:
    result = _execute(service, sql)
    assert result.error is None, result.error
    return result.rows


def _pick(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    raise AssertionError(f"missing any of {keys} in row {row}")


def _number(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _assert_decimal_close(actual: Decimal, expected: Decimal) -> None:
    assert abs(actual - expected) <= Decimal("0.000001")


def _norm_total_share(rows: Iterable[dict[str, Any]]) -> list[dict[str, Decimal | str | None]]:
    normalized = []
    for row in rows:
        normalized.append(
            {
                "customer": _pick(row, "客户类型", "customer$customerType", "customer_type", "customer"),
                "sales": _number(_pick(row, "销售金额", "salesAmount", "sales")),
                "share": _number(_pick(row, "totalShare", "total_share")),
            }
        )
    return sorted(normalized, key=lambda item: str(item["customer"]))


def _norm_partition_share(rows: Iterable[dict[str, Any]]) -> list[dict[str, Decimal | str | None]]:
    normalized = []
    for row in rows:
        normalized.append(
            {
                "customer": _pick(row, "客户类型", "customer$customerType", "customer_type", "customer"),
                "category": _pick(row, "一级品类名称", "product$categoryName", "category_name", "category"),
                "sales": _number(_pick(row, "销售金额", "salesAmount", "sales")),
                "share": _number(_pick(row, "categoryShareInCustomer", "category_share")),
            }
        )
    return sorted(
        normalized,
        key=lambda item: (str(item["customer"]), str(item["category"])),
    )


def test_calculate_global_share_oracle_parity(real_db_service):
    _, service = real_db_service

    query_rows = _query(
        service,
        SemanticQueryRequest(
            columns=["customer$customerType", "salesAmount", "totalShare"],
            group_by=["customer$customerType"],
            calculated_fields=[
                {
                    "name": "totalShare",
                    "expression": (
                        "SUM(salesAmount) / NULLIF(CALCULATE(SUM(salesAmount), "
                        "REMOVE(customer$customerType)), 0)"
                    ),
                }
            ],
        ),
    )

    oracle_rows = _oracle(
        service,
        """
        SELECT
          c.customer_type AS customer,
          SUM(f.sales_amount) AS sales,
          SUM(f.sales_amount) / NULLIF(SUM(SUM(f.sales_amount)) OVER (), 0) AS total_share
        FROM fact_sales f
        LEFT JOIN dim_customer c ON f.customer_key = c.customer_key
        GROUP BY c.customer_type
        """,
    )

    actual = _norm_total_share(query_rows)
    expected = _norm_total_share(oracle_rows)
    assert [(row["customer"], row["sales"]) for row in actual] == [
        (row["customer"], row["sales"]) for row in expected
    ]
    for left, right in zip(actual, expected):
        _assert_decimal_close(left["share"], right["share"])  # type: ignore[arg-type]


def test_calculate_partition_share_oracle_parity(real_db_service):
    _, service = real_db_service

    query_rows = _query(
        service,
        SemanticQueryRequest(
            columns=[
                "customer$customerType",
                "product$categoryName",
                "salesAmount",
                "categoryShareInCustomer",
            ],
            group_by=["customer$customerType", "product$categoryName"],
            calculated_fields=[
                {
                    "name": "categoryShareInCustomer",
                    "expression": (
                        "SUM(salesAmount) / NULLIF(CALCULATE(SUM(salesAmount), "
                        "REMOVE(product$categoryName)), 0)"
                    ),
                }
            ],
        ),
    )

    oracle_rows = _oracle(
        service,
        """
        SELECT
          c.customer_type AS customer,
          p.category_name AS category,
          SUM(f.sales_amount) AS sales,
          SUM(f.sales_amount) / NULLIF(
            SUM(SUM(f.sales_amount)) OVER (PARTITION BY c.customer_type),
            0
          ) AS category_share
        FROM fact_sales f
        LEFT JOIN dim_customer c ON f.customer_key = c.customer_key
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY c.customer_type, p.category_name
        """,
    )

    actual = _norm_partition_share(query_rows)
    expected = _norm_partition_share(oracle_rows)
    assert [(row["customer"], row["category"], row["sales"]) for row in actual] == [
        (row["customer"], row["category"], row["sales"]) for row in expected
    ]
    for left, right in zip(actual, expected):
        _assert_decimal_close(left["share"], right["share"])  # type: ignore[arg-type]
