"""
Unit tests for ExecutorManager — named executor registry with default fallback.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from foggy.dataset.db.executor import (
    ExecutorManager,
    DatabaseExecutor,
    QueryResult,
)


class FakeExecutor(DatabaseExecutor):
    """Minimal executor stub for testing."""

    def __init__(self, name: str = "fake"):
        self.name = name
        self.closed = False

    async def execute(self, sql, params=None, limit=None):
        return QueryResult(columns=[], rows=[], total=0, sql=sql)

    async def execute_count(self, sql, params=None):
        return 0

    async def close(self):
        self.closed = True


# ==================== Registration ====================


class TestExecutorManagerRegistration:
    """Tests for executor registration."""

    def test_register_single(self):
        mgr = ExecutorManager()
        ex = FakeExecutor("a")
        mgr.register("alpha", ex)

        assert mgr.get("alpha") is ex
        assert mgr.list_names() == ["alpha"]

    def test_first_registration_becomes_default(self):
        mgr = ExecutorManager()
        ex = FakeExecutor("first")
        mgr.register("first", ex)

        assert mgr.get_default() is ex
        assert mgr.get() is ex  # None → default

    def test_explicit_set_default(self):
        mgr = ExecutorManager()
        ex1 = FakeExecutor("a")
        ex2 = FakeExecutor("b")
        mgr.register("a", ex1)
        mgr.register("b", ex2, set_default=True)

        assert mgr.get_default() is ex2

    def test_second_registration_does_not_override_default(self):
        mgr = ExecutorManager()
        ex1 = FakeExecutor("a")
        ex2 = FakeExecutor("b")
        mgr.register("a", ex1)
        mgr.register("b", ex2)  # set_default=False

        assert mgr.get_default() is ex1

    def test_register_replaces_existing(self):
        mgr = ExecutorManager()
        ex1 = FakeExecutor("v1")
        ex2 = FakeExecutor("v2")
        mgr.register("x", ex1)
        mgr.register("x", ex2)

        assert mgr.get("x") is ex2
        assert mgr.list_names() == ["x"]

    def test_list_names_multiple(self):
        mgr = ExecutorManager()
        mgr.register("a", FakeExecutor())
        mgr.register("b", FakeExecutor())
        mgr.register("c", FakeExecutor())

        assert sorted(mgr.list_names()) == ["a", "b", "c"]


# ==================== Lookup ====================


class TestExecutorManagerLookup:
    """Tests for executor lookup and fallback."""

    def test_get_by_name(self):
        mgr = ExecutorManager()
        ex = FakeExecutor()
        mgr.register("odoo", ex)

        assert mgr.get("odoo") is ex

    def test_get_unknown_name_falls_back_to_default(self):
        mgr = ExecutorManager()
        default_ex = FakeExecutor("default")
        mgr.register("default", default_ex)

        assert mgr.get("nonexistent") is default_ex

    def test_get_none_returns_default(self):
        mgr = ExecutorManager()
        ex = FakeExecutor()
        mgr.register("ds", ex)

        assert mgr.get(None) is ex

    def test_get_empty_string_returns_default(self):
        mgr = ExecutorManager()
        ex = FakeExecutor()
        mgr.register("ds", ex)

        assert mgr.get("") is ex

    def test_get_default_with_no_registrations(self):
        mgr = ExecutorManager()
        assert mgr.get_default() is None
        assert mgr.get("anything") is None

    def test_get_returns_correct_executor_among_multiple(self):
        mgr = ExecutorManager()
        ex_a = FakeExecutor("a")
        ex_b = FakeExecutor("b")
        ex_c = FakeExecutor("c")
        mgr.register("a", ex_a)
        mgr.register("b", ex_b)
        mgr.register("c", ex_c)

        assert mgr.get("b") is ex_b
        assert mgr.get("c") is ex_c
        assert mgr.get("a") is ex_a


# ==================== Close ====================


class TestExecutorManagerCloseAll:
    """Tests for closing all executors."""

    @pytest.mark.asyncio
    async def test_close_all(self):
        mgr = ExecutorManager()
        ex1 = FakeExecutor("a")
        ex2 = FakeExecutor("b")
        mgr.register("a", ex1)
        mgr.register("b", ex2)

        await mgr.close_all()

        assert ex1.closed
        assert ex2.closed
        assert mgr.list_names() == []
        assert mgr.get_default() is None

    @pytest.mark.asyncio
    async def test_close_all_empty(self):
        mgr = ExecutorManager()
        await mgr.close_all()  # Should not raise

    @pytest.mark.asyncio
    async def test_close_all_tolerates_error(self):
        """One executor failing close should not prevent others from closing."""
        mgr = ExecutorManager()
        ex_good = FakeExecutor("good")

        ex_bad = FakeExecutor("bad")
        async def _fail_close():
            raise RuntimeError("close failed")
        ex_bad.close = _fail_close

        mgr.register("good", ex_good)
        mgr.register("bad", ex_bad)

        await mgr.close_all()  # Should not raise

        assert ex_good.closed
        assert mgr.list_names() == []
