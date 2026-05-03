"""SQL Server refusal evidence for Python Pivot C2 cascade.

Python v1.10 does not claim SQL Server cascade parity.  Until a SQL Server
renderer has oracle coverage, C2 cascade must fail closed before SQL execution
instead of falling back to memory ranking or emitting unverified T-SQL.
"""

from __future__ import annotations

from typing import Any

from foggy.dataset.db.executor import SQLServerExecutor
from foggy.dataset.dialects.sqlserver import SqlServerDialect
from foggy.dataset_model.semantic.pivot.cascade_detector import PIVOT_CASCADE_SQL_REQUIRED
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import PivotRequest, SemanticQueryRequest


def _cascade_request() -> SemanticQueryRequest:
    return SemanticQueryRequest(
        pivot=PivotRequest(
            outputFormat="flat",
            rows=[
                {"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]},
                {"field": "product$subCategoryId", "limit": 1, "orderBy": ["-salesAmount"]},
            ],
            metrics=["salesAmount"],
        )
    )


def _assert_sqlserver_cascade_refused(response) -> None:
    assert response.error is not None
    assert PIVOT_CASCADE_SQL_REQUIRED in response.error
    assert "sqlserver" in response.error.lower()
    assert "Cascade Staged SQL" in response.error
    assert not response.items


def test_sqlserver_cascade_refuses_with_explicit_dialect_before_sql_execution():
    calls: list[tuple[str, Any]] = []

    class NoExecuteExecutor:
        async def execute(self, sql: str, params=None, limit=None):
            calls.append((sql, params))
            raise AssertionError("SQL Server cascade refusal must happen before executor.execute")

    service = SemanticQueryService(
        executor=NoExecuteExecutor(),
        dialect=SqlServerDialect(),
        enable_cache=False,
    )
    service.register_model(create_fact_sales_model())

    response = service.query_model("FactSalesModel", _cascade_request(), mode="execute")

    _assert_sqlserver_cascade_refused(response)
    assert calls == []


def test_sqlserver_cascade_refuses_with_executor_inferred_dialect_before_connection():
    executor = SQLServerExecutor(
        host="127.0.0.1",
        port=11433,
        database="foggy_test",
        user="sa",
        password="Foggy_Test_123!",
    )
    calls: list[tuple[str, Any]] = []

    async def fail_if_called(sql: str, params=None, limit=None):
        calls.append((sql, params))
        raise AssertionError("SQL Server cascade refusal must happen before executor.execute")

    executor.execute = fail_if_called  # type: ignore[method-assign]
    service = SemanticQueryService(executor=executor, enable_cache=False)
    service.register_model(create_fact_sales_model())

    assert service._dialect is not None
    assert service._dialect.name == "sqlserver"

    response = service.query_model("FactSalesModel", _cascade_request(), mode="execute")

    _assert_sqlserver_cascade_refused(response)
    assert calls == []
