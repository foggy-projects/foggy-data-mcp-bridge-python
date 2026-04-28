"""Execution-level smoke tests for the AST expression compiler.

Stage 6 unit tests prove the parser and visitor can emit SQL for
SQL-specific predicates.  These tests keep a production-like guardrail:
``SemanticQueryService(use_ast_expression_compiler=True)`` builds a real
query and executes it through the SQLite executor.
"""

from __future__ import annotations

import sqlite3

import pytest

from foggy.dataset.db.executor import SQLiteExecutor
from foggy.dataset_model.definitions.base import ColumnType
from foggy.dataset_model.impl.model import DbModelDimensionImpl, DbTableModelImpl
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.mcp_spi import SemanticQueryRequest


@pytest.fixture()
def sqlite_ast_service(tmp_path):
    db_path = tmp_path / "ast_expression_smoke.sqlite"
    _seed_ast_smoke_db(db_path)

    executor = SQLiteExecutor(str(db_path))
    service = SemanticQueryService(
        executor=executor,
        enable_cache=False,
        use_ast_expression_compiler=True,
    )
    service.register_model(_make_ast_smoke_model())

    yield service

    service._run_async_in_sync(executor.close())


def test_ast_compiler_predicates_and_cast_execute_on_sqlite(sqlite_ast_service):
    response = sqlite_ast_service.query_model(
        "AstSmokeSales",
        SemanticQueryRequest(
            columns=[
                "orderId$caption",
                "isMissingCategory",
                "isMidAmount",
                "isAlphaCustomer",
                "amountInt",
                "displayKey",
            ],
            calculated_fields=[
                {"name": "isMissingCategory", "expression": "category IS NULL"},
                {"name": "isMidAmount", "expression": "amount BETWEEN 10 AND 20"},
                {"name": "isAlphaCustomer", "expression": "customerName LIKE 'A%'"},
                {"name": "amountInt", "expression": "CAST(amountText AS INTEGER)"},
                {"name": "displayKey", "expression": "'VIP-' + customerName"},
            ],
            order_by=[{"field": "orderId$caption", "dir": "asc"}],
        ),
        mode="execute",
    )

    assert response.error is None, response.error
    assert " IS NULL" in response.sql
    assert " BETWEEN " in response.sql
    assert " LIKE " in response.sql
    assert "CAST(" in response.sql
    assert " || " in response.sql

    rows = response.items
    assert [row["orderId"] for row in rows] == [1, 2, 3]
    assert rows[0]["isMissingCategory"] == 0
    assert rows[0]["isMidAmount"] == 1
    assert rows[0]["isAlphaCustomer"] == 1
    assert rows[0]["amountInt"] == 12
    assert rows[0]["displayKey"] == "VIP-Alice"

    assert rows[1]["isMissingCategory"] == 1
    assert rows[1]["isMidAmount"] == 0
    assert rows[1]["isAlphaCustomer"] == 0
    assert rows[1]["amountInt"] == 25
    assert rows[1]["displayKey"] == "VIP-Bob"


def _make_ast_smoke_model() -> DbTableModelImpl:
    model = DbTableModelImpl(name="AstSmokeSales", source_table="ast_smoke_sales")
    model.add_dimension(
        DbModelDimensionImpl(
            name="orderId",
            column="order_id",
            data_type=ColumnType.INTEGER,
        )
    )
    model.add_dimension(DbModelDimensionImpl(name="customerName", column="customer_name"))
    model.add_dimension(DbModelDimensionImpl(name="category", column="category"))
    model.add_dimension(
        DbModelDimensionImpl(
            name="amount",
            column="amount",
            data_type=ColumnType.DECIMAL,
        )
    )
    model.add_dimension(DbModelDimensionImpl(name="amountText", column="amount_text"))
    return model


def _seed_ast_smoke_db(db_path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE ast_smoke_sales (
                order_id INTEGER PRIMARY KEY,
                customer_name TEXT NOT NULL,
                category TEXT,
                amount REAL NOT NULL,
                amount_text TEXT NOT NULL
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO ast_smoke_sales (
                order_id, customer_name, category, amount, amount_text
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (1, "Alice", "vip", 12.5, "12"),
                (2, "Bob", None, 25.0, "25"),
                (3, "Amy", "standard", 8.0, "8"),
            ],
        )
        conn.commit()
    finally:
        conn.close()
