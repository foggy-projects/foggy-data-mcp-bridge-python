"""Tests for ``SemanticQueryService.execute_sql`` (M7 Step 0)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

import pytest

from foggy.dataset_model.semantic.service import SemanticQueryService


@dataclass
class _FakeResult:
    rows: List[Any] = field(default_factory=list)
    total: Optional[int] = None
    has_more: bool = False
    error: Optional[str] = None


class _RecordingExecutor:
    """Async executor double that records (sql, params) calls."""

    def __init__(self, result: Optional[_FakeResult] = None,
                 raise_exc: Optional[BaseException] = None):
        self._result = result or _FakeResult(rows=[])
        self._raise = raise_exc
        self.calls: List[tuple] = []

    async def execute(self, sql: str, params: List[Any]):
        self.calls.append((sql, list(params)))
        if self._raise is not None:
            raise self._raise
        return self._result


def _make_service() -> SemanticQueryService:
    return SemanticQueryService(default_limit=1000, enable_cache=False)


def test_execute_sql_requires_executor():
    svc = _make_service()
    with pytest.raises(RuntimeError) as exc:
        svc.execute_sql("SELECT 1", [])
    assert "no executor configured" in str(exc.value)


def test_execute_sql_returns_rows_on_success():
    svc = _make_service()
    executor = _RecordingExecutor(
        _FakeResult(rows=[{"a": 1}, {"a": 2}], total=2)
    )
    svc.set_executor(executor)

    rows = svc.execute_sql("SELECT a FROM t WHERE b = ?", [42])

    assert rows == [{"a": 1}, {"a": 2}]
    assert executor.calls == [("SELECT a FROM t WHERE b = ?", [42])]


def test_execute_sql_none_params_coerced_to_empty_list():
    svc = _make_service()
    executor = _RecordingExecutor(_FakeResult(rows=[]))
    svc.set_executor(executor)

    svc.execute_sql("SELECT 1", None)

    assert executor.calls == [("SELECT 1", [])]


def test_execute_sql_wraps_driver_error():
    svc = _make_service()
    driver_error = RuntimeError("db connection lost")
    executor = _RecordingExecutor(raise_exc=driver_error)
    svc.set_executor(executor)

    with pytest.raises(RuntimeError) as exc_info:
        svc.execute_sql("SELECT 1", [])
    assert "execute_sql failed" in str(exc_info.value)
    assert exc_info.value.__cause__ is driver_error


def test_execute_sql_surfaces_result_error():
    svc = _make_service()
    executor = _RecordingExecutor(
        _FakeResult(rows=[], error="syntax error at or near \"SELEKT\"")
    )
    svc.set_executor(executor)

    with pytest.raises(RuntimeError) as exc_info:
        svc.execute_sql("SELEKT bogus", [])
    assert "syntax error" in str(exc_info.value)


def test_execute_sql_route_model_falls_back_to_default_when_unknown():
    """route_model pointing at an unregistered model falls back to
    the default executor rather than erroring."""
    svc = _make_service()
    executor = _RecordingExecutor(_FakeResult(rows=[{"x": 1}]))
    svc.set_executor(executor)

    rows = svc.execute_sql("SELECT x", [], route_model="NotRegistered")

    assert rows == [{"x": 1}]
    assert executor.calls == [("SELECT x", [])]
