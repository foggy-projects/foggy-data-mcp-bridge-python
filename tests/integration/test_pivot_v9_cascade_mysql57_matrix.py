"""MySQL 5.7 refusal evidence for Python Pivot cascade and domain transport.

Python v1.10 only supports MySQL8 for C2 cascade staged SQL.  A bare
``MySQLExecutor`` is used by the project MySQL8 profile, so MySQL 5.7 must be
represented explicitly by dialect name when validating refusal behavior.
"""

from __future__ import annotations

from typing import Any

from foggy.dataset.dialects.mysql import MySqlDialect
from foggy.dataset_model.semantic.pivot.cascade_detector import PIVOT_CASCADE_SQL_REQUIRED
from foggy.dataset_model.semantic.pivot.domain_transport import (
    DomainTransportPlan,
    PIVOT_DOMAIN_TRANSPORT_REFUSED,
)
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import PivotRequest, SemanticQueryRequest


class MySql57Dialect(MySqlDialect):
    @property
    def name(self) -> str:
        return "mysql5.7"

    @property
    def supports_cte(self) -> bool:
        return False


class NoExecuteExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    async def execute(self, sql: str, params=None, limit=None):
        self.calls.append((sql, params))
        raise AssertionError("MySQL 5.7 refusal must happen before executor.execute")

    async def execute_count(self, sql: str, params=None) -> int:
        self.calls.append((sql, params))
        raise AssertionError("MySQL 5.7 refusal must happen before executor.execute_count")

    async def close(self) -> None:
        return None


def _service() -> tuple[SemanticQueryService, NoExecuteExecutor]:
    executor = NoExecuteExecutor()
    service = SemanticQueryService(
        executor=executor,
        dialect=MySql57Dialect(),
        enable_cache=False,
    )
    service.register_model(create_fact_sales_model())
    return service, executor


def test_mysql57_cascade_refuses_before_sql_execution():
    service, executor = _service()
    request = SemanticQueryRequest(
        pivot=PivotRequest(
            outputFormat="flat",
            rows=[
                {"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]},
                {"field": "product$subCategoryId", "limit": 1, "orderBy": ["-salesAmount"]},
            ],
            metrics=["salesAmount"],
        )
    )

    response = service.query_model("FactSalesModel", request, mode="execute")

    assert response.error is not None
    assert PIVOT_CASCADE_SQL_REQUIRED in response.error
    assert "mysql5.7" in response.error
    assert "Cascade Staged SQL" in response.error
    assert executor.calls == []


def test_mysql57_large_domain_transport_refuses_at_build_time():
    service, executor = _service()
    request = SemanticQueryRequest(
        columns=["product$categoryName", "salesAmount"],
        group_by=["product$categoryName"],
    )
    request.domain_transport_plan = DomainTransportPlan(
        columns=("product$categoryName",),
        tuples=(("Electronics",),),
        threshold=0,
    )

    response = service.query_model("FactSalesModel", request, mode="validate")

    assert response.error is not None
    assert PIVOT_DOMAIN_TRANSPORT_REFUSED in response.error
    assert "mysql5.7" in response.error
    assert executor.calls == []
