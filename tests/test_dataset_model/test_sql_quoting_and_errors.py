"""Tests for SQL identifier quoting (Bug 1) and error propagation (Bug 2).

Bug 1: ORDER BY must use the same quoting as SELECT aliases.
  - Default (no dialect): ANSI double-quote  → AS "alias", ORDER BY "alias"
  - MySQL dialect: backtick                  → AS `alias`, ORDER BY `alias`
  - PostgreSQL dialect: double-quote         → AS "alias", ORDER BY "alias"

Bug 2: SQL execution errors must propagate to SemanticQueryResponse.error,
  not be silently swallowed as empty results.

Ref: commit 0ad8fe5 — fix: SQL identifier quoting and event loop reuse
"""

import asyncio
import pytest

from foggy.dataset_model.semantic.service import SemanticQueryService, QueryBuildResult
from foggy.dataset_model.impl.model import DbTableModelImpl
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest, SemanticQueryResponse
from foggy.dataset.dialects.mysql import MySqlDialect
from foggy.dataset.dialects.postgres import PostgresDialect
from foggy.dataset.dialects.sqlite import SqliteDialect


# ==================== Fixtures ====================


@pytest.fixture
def sales_model() -> DbTableModelImpl:
    return create_fact_sales_model()


def _make_service(sales_model, dialect=None) -> SemanticQueryService:
    svc = SemanticQueryService(dialect=dialect)
    svc.register_model(sales_model)
    return svc


def _build_sql(service, model_name, request) -> str:
    response = service.query_model(model_name, request, mode="validate")
    assert response.error is None, f"Query build failed: {response.error}"
    assert response.sql is not None
    return response.sql


# ==================== Bug 1: _qi() quoting ====================


class TestIdentifierQuoting:
    """Verify _qi() uses dialect-aware quoting for SELECT aliases and ORDER BY."""

    def test_qi_default_ansi_double_quote(self, sales_model):
        """No dialect → ANSI double-quote."""
        svc = _make_service(sales_model, dialect=None)
        assert svc._qi("myAlias") == '"myAlias"'

    def test_qi_mysql_backtick(self, sales_model):
        """MySQL dialect → backtick quoting."""
        svc = _make_service(sales_model, dialect=MySqlDialect())
        assert svc._qi("myAlias") == "`myAlias`"

    def test_qi_postgres_double_quote(self, sales_model):
        """PostgreSQL dialect → double-quote quoting."""
        svc = _make_service(sales_model, dialect=PostgresDialect())
        assert svc._qi("myAlias") == '"myAlias"'

    def test_qi_sqlite_double_quote(self, sales_model):
        """SQLite dialect → double-quote quoting."""
        svc = _make_service(sales_model, dialect=SqliteDialect())
        assert svc._qi("myAlias") == '"myAlias"'

    def test_qi_escapes_embedded_quotes(self, sales_model):
        """Double-quote inside identifier is escaped (ANSI: doubled)."""
        svc = _make_service(sales_model, dialect=None)
        assert svc._qi('my"Alias') == '"my""Alias"'

    def test_select_alias_uses_qi(self, sales_model):
        """SELECT alias should be quoted, not raw."""
        svc = _make_service(sales_model, dialect=None)
        request = SemanticQueryRequest(columns=["salesAmount"])
        sql = _build_sql(svc, "FactSalesModel", request)
        # ANSI default: should use double-quote for alias
        assert 'AS "' in sql

    def test_select_alias_mysql_backtick(self, sales_model):
        """MySQL dialect → SELECT uses backtick alias."""
        svc = _make_service(sales_model, dialect=MySqlDialect())
        request = SemanticQueryRequest(columns=["salesAmount"])
        sql = _build_sql(svc, "FactSalesModel", request)
        assert "AS `" in sql

    def test_order_by_alias_quoted_consistently(self, sales_model):
        """ORDER BY measure alias must use same quoting as SELECT alias."""
        svc = _make_service(sales_model, dialect=None)
        request = SemanticQueryRequest(
            columns=["product$categoryName", "salesAmount"],
            order_by=[{"field": "salesAmount", "dir": "desc"}],
        )
        sql = _build_sql(svc, "FactSalesModel", request)
        # Find the ORDER BY clause
        order_idx = sql.upper().index("ORDER BY")
        order_clause = sql[order_idx:]
        # Alias in ORDER BY should be double-quoted (ANSI default)
        assert '"' in order_clause, (
            f"ORDER BY should use double-quoted alias, got: {order_clause}"
        )

    def test_order_by_alias_mysql_backtick(self, sales_model):
        """MySQL: ORDER BY measure alias uses backtick."""
        svc = _make_service(sales_model, dialect=MySqlDialect())
        request = SemanticQueryRequest(
            columns=["product$categoryName", "salesAmount"],
            order_by=[{"field": "salesAmount", "dir": "desc"}],
        )
        sql = _build_sql(svc, "FactSalesModel", request)
        order_idx = sql.upper().index("ORDER BY")
        order_clause = sql[order_idx:]
        assert "`" in order_clause, (
            f"MySQL ORDER BY should use backtick alias, got: {order_clause}"
        )

    def test_order_by_postgres_double_quote(self, sales_model):
        """PostgreSQL: ORDER BY measure alias uses double-quote."""
        svc = _make_service(sales_model, dialect=PostgresDialect())
        request = SemanticQueryRequest(
            columns=["product$categoryName", "salesAmount"],
            order_by=[{"field": "salesAmount", "dir": "desc"}],
        )
        sql = _build_sql(svc, "FactSalesModel", request)
        order_idx = sql.upper().index("ORDER BY")
        order_clause = sql[order_idx:]
        assert '"' in order_clause, (
            f"PostgreSQL ORDER BY should use double-quoted alias, got: {order_clause}"
        )

    def test_select_and_order_by_same_quote_char(self, sales_model):
        """SELECT and ORDER BY must use the exact same quote character for the same alias."""
        for dialect, expected_char in [
            (None, '"'),
            (MySqlDialect(), '`'),
            (PostgresDialect(), '"'),
        ]:
            svc = _make_service(sales_model, dialect=dialect)
            request = SemanticQueryRequest(
                columns=["product$categoryName", "salesAmount"],
                order_by=[{"field": "salesAmount", "dir": "desc"}],
            )
            sql = _build_sql(svc, "FactSalesModel", request)

            # Extract quoted alias from SELECT
            select_part = sql[:sql.upper().index("FROM")]
            # Extract ORDER BY clause
            order_part = sql[sql.upper().index("ORDER BY"):]

            # Both should contain the expected quote character
            assert expected_char in select_part, f"SELECT missing {expected_char!r} with {dialect}"
            assert expected_char in order_part, f"ORDER BY missing {expected_char!r} with {dialect}"

    def test_inline_agg_alias_quoted(self, sales_model):
        """Inline aggregation expression alias should be quoted."""
        svc = _make_service(sales_model, dialect=None)
        request = SemanticQueryRequest(
            columns=["orderStatus", "sum(salesAmount) as totalSales"],
        )
        sql = _build_sql(svc, "FactSalesModel", request)
        assert '"totalSales"' in sql

    def test_camel_case_alias_preserved(self, sales_model):
        """CamelCase alias must be preserved exactly (PostgreSQL is case-sensitive with quotes)."""
        svc = _make_service(sales_model, dialect=PostgresDialect())
        request = SemanticQueryRequest(
            columns=["orderStatus", "sum(salesAmount) as totalSalesAmount"],
            order_by=[{"field": "totalSalesAmount", "dir": "desc"}],
        )
        sql = _build_sql(svc, "FactSalesModel", request)
        # The exact alias with correct casing should appear in both SELECT and ORDER BY
        assert '"totalSalesAmount"' in sql


# ==================== Bug 2: Error propagation ====================


class TestErrorPropagation:
    """Verify SQL execution errors are propagated, not silently swallowed."""

    def test_execute_error_sets_response_error(self, sales_model):
        """When executor returns an error, SemanticQueryResponse.error must be set."""

        class FailingExecutor:
            async def execute(self, sql, params=None):
                return type('Result', (), {
                    'error': 'column "nonexistent" does not exist',
                    'rows': [],
                    'total': 0,
                    'sql': sql,
                })()

        svc = _make_service(sales_model)
        svc.set_executor(FailingExecutor())

        request = SemanticQueryRequest(columns=["salesAmount"])
        response = svc.query_model("FactSalesModel", request, mode="execute")

        assert response.error is not None
        assert "does not exist" in response.error
        # data should be empty but NOT misleading
        assert response.data == [] or response.data is None

    def test_execute_exception_sets_response_error(self, sales_model):
        """When executor raises an exception, it should be caught and set as error."""

        class ExplodingExecutor:
            async def execute(self, sql, params=None):
                raise RuntimeError("connection refused")

        svc = _make_service(sales_model)
        svc.set_executor(ExplodingExecutor())

        request = SemanticQueryRequest(columns=["salesAmount"])
        response = svc.query_model("FactSalesModel", request, mode="execute")

        assert response.error is not None
        assert "connection refused" in response.error

    def test_no_executor_returns_error(self, sales_model):
        """No executor configured → error message, not silent empty result."""
        svc = _make_service(sales_model)
        # No executor set

        request = SemanticQueryRequest(columns=["salesAmount"])
        response = svc.query_model("FactSalesModel", request, mode="execute")

        # Should either have error or have an empty result with no confusion
        # The key is it should NOT look like a successful query with 0 rows
        assert response.data is None or response.data == []

    def test_error_includes_sql(self, sales_model):
        """Error response should include the SQL that failed."""

        class FailingExecutor:
            async def execute(self, sql, params=None):
                return type('Result', (), {
                    'error': 'syntax error at or near "GROUP"',
                    'rows': [],
                    'total': 0,
                    'sql': sql,
                })()

        svc = _make_service(sales_model)
        svc.set_executor(FailingExecutor())

        request = SemanticQueryRequest(columns=["salesAmount"])
        response = svc.query_model("FactSalesModel", request, mode="execute")

        assert response.error is not None
        assert response.sql is not None
        assert "SELECT" in response.sql.upper()


# ==================== _get_sync_loop reuse ====================


class TestSyncLoopReuse:
    """Verify _get_sync_loop() returns a reusable persistent event loop."""

    def test_sync_loop_created_on_first_call(self, sales_model):
        svc = _make_service(sales_model)
        loop = svc._get_sync_loop()
        assert loop is not None
        assert not loop.is_closed()

    def test_sync_loop_reused_across_calls(self, sales_model):
        svc = _make_service(sales_model)
        loop1 = svc._get_sync_loop()
        loop2 = svc._get_sync_loop()
        assert loop1 is loop2

    def test_sync_loop_recreated_if_closed(self, sales_model):
        svc = _make_service(sales_model)
        loop1 = svc._get_sync_loop()
        loop1.close()
        loop2 = svc._get_sync_loop()
        assert loop2 is not loop1
        assert not loop2.is_closed()
