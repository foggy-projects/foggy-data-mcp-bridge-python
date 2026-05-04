"""
Unit tests for PostgreSQLExecutor._auto_convert_params().

Regression: asyncpg requires Python datetime objects for timestamp/date
columns, not strings. MCP clients pass JSON strings like "2026-03-01"
which must be converted before hitting asyncpg's prepared statement protocol.
"""

import asyncio
import sys
import types

import pytest
from datetime import datetime, date

from foggy.dataset.db.executor import PostgreSQLExecutor


class TestAutoConvertParams:
    """Verify string-to-datetime auto-conversion for asyncpg parameters."""

    def test_date_string_converted_to_date(self):
        """'YYYY-MM-DD' string → datetime.date object."""
        result = PostgreSQLExecutor._auto_convert_params(['2026-03-01'])
        assert result == [date(2026, 3, 1)]
        assert isinstance(result[0], date)
        assert not isinstance(result[0], datetime)  # date, not datetime

    def test_datetime_string_T_format(self):
        """'YYYY-MM-DDTHH:MM:SS' string → datetime.datetime object."""
        result = PostgreSQLExecutor._auto_convert_params(['2026-03-01T10:30:00'])
        assert result == [datetime(2026, 3, 1, 10, 30, 0)]
        assert isinstance(result[0], datetime)

    def test_datetime_string_space_format(self):
        """'YYYY-MM-DD HH:MM:SS' string → datetime.datetime object."""
        result = PostgreSQLExecutor._auto_convert_params(['2026-03-01 10:30:00'])
        assert result == [datetime(2026, 3, 1, 10, 30, 0)]
        assert isinstance(result[0], datetime)

    def test_non_date_string_unchanged(self):
        """Regular strings are not converted."""
        result = PostgreSQLExecutor._auto_convert_params(['hello', 'world'])
        assert result == ['hello', 'world']

    def test_non_string_types_unchanged(self):
        """int, float, None, bool pass through unchanged."""
        params = [42, 3.14, None, True]
        result = PostgreSQLExecutor._auto_convert_params(params)
        assert result == [42, 3.14, None, True]

    def test_mixed_params(self):
        """Mixed types: dates converted, others pass through."""
        params = ['2026-03-01', 'hello', 42, '2026-03-01T10:30:00', None]
        result = PostgreSQLExecutor._auto_convert_params(params)
        assert result == [
            date(2026, 3, 1),
            'hello',
            42,
            datetime(2026, 3, 1, 10, 30, 0),
            None,
        ]

    def test_empty_list(self):
        """Empty list returns empty list."""
        assert PostgreSQLExecutor._auto_convert_params([]) == []

    def test_none_returns_none(self):
        """None input returns None."""
        assert PostgreSQLExecutor._auto_convert_params(None) is None

    def test_invalid_date_string_unchanged(self):
        """Strings that look date-ish but aren't valid stay as strings."""
        params = ['2026-13-01', '2026-02-30', 'not-a-date', '2026/03/01']
        result = PostgreSQLExecutor._auto_convert_params(params)
        # All should remain strings (invalid dates or wrong format)
        for r in result:
            assert isinstance(r, str)


class TestConvertParamsIntegration:
    """Verify _convert_params calls _auto_convert_params."""

    def test_convert_params_applies_date_conversion(self):
        """_convert_params should convert date strings in params."""
        executor = PostgreSQLExecutor()
        sql, params = executor._convert_params(
            "SELECT * FROM t WHERE created_at >= ? AND created_at <= ?",
            ['2026-03-01', '2026-03-31'],
        )
        assert sql == "SELECT * FROM t WHERE created_at >= $1 AND created_at <= $2"
        assert params == [date(2026, 3, 1), date(2026, 3, 31)]
        assert isinstance(params[0], date)
        assert isinstance(params[1], date)


class TestPostgreSQLExecutorLoopScopedPools:
    """Regression coverage for asyncpg pools bound to event loops."""

    def test_execute_uses_separate_pool_per_event_loop(self, monkeypatch):
        created_pools = []

        class FakePool:
            def __init__(self):
                self.loop = asyncio.get_running_loop()
                self.closed = False
                created_pools.append(self)

            def acquire(self):
                return FakeAcquire(self)

            async def close(self):
                self.closed = True

        class FakeAcquire:
            def __init__(self, pool):
                self.pool = pool

            async def __aenter__(self):
                if asyncio.get_running_loop() is not self.pool.loop:
                    raise RuntimeError("Future attached to a different loop")
                return FakeConnection()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class FakeConnection:
            async def fetch(self, sql, *params):
                return [{"value": len(params)}]

        async def create_pool(**kwargs):
            return FakePool()

        monkeypatch.setitem(
            sys.modules,
            "asyncpg",
            types.SimpleNamespace(create_pool=create_pool),
        )

        executor = PostgreSQLExecutor()

        def run_in_fresh_loop():
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(executor.execute("SELECT 1"))
            finally:
                loop.close()

        first = run_in_fresh_loop()
        second = run_in_fresh_loop()

        assert first.error is None
        assert second.error is None
        assert len(created_pools) == 2
