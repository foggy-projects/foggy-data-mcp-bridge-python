"""Memory Grid parity tests for the Java P0.9 resolver contract cut."""

from datetime import UTC, datetime, timedelta

from foggy.dataset_model.semantic.memory_grid import (
    InMemoryResultHandleStore,
    InMemoryResultStorageAdapter,
    MemoryGridColumn,
    MemoryGridRegistryResultResolver,
    MemoryGridStoreBackedResultResolver,
    ResolvedMemoryGridResult,
    ResultHandleMetadata,
    ResultHandleWriter,
    ResultHandleWriteRequest,
)
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.mcp_spi import SemanticQueryRequest, SemanticRequestContext


def _third009_plan(**overrides):
    plan = {
        "inputs": [
            {
                "name": "actual",
                "source_route": "DSL_CTE",
                "result_handle": "dsl_cte_result_actual_by_team_2026_05",
                "governed": True,
                "row_limit": 200,
                "grain": ["salesTeam.name"],
                "metrics": [{"name": "actualSalesAmount"}],
            },
            {
                "name": "target",
                "source_route": "DSL",
                "result_handle": "dsl_result_target_by_team_2026_05_approved",
                "governed": True,
                "row_limit": 200,
                "grain": ["salesTeam.name"],
                "metrics": [{"name": "targetSalesAmount"}],
            },
        ],
        "join": {"type": "inner", "keys": ["salesTeam.name"]},
        "derived": [
            {
                "name": "targetAchievementRate",
                "expr": "actualSalesAmount / targetSalesAmount",
            }
        ],
        "output": [
            "salesTeam.name",
            "actualSalesAmount",
            "targetSalesAmount",
            "targetAchievementRate",
        ],
        "output_limit": 200,
    }
    plan.update(overrides)
    return plan


def _resolver(
    namespace=None,
    actual_schema=None,
    *,
    actual_route="DSL_CTE",
    actual_rows=None,
    actual_storage_ref=None,
    expires_at=None,
):
    expires_at = expires_at or datetime.now(UTC) + timedelta(hours=1)
    return (
        MemoryGridRegistryResultResolver()
        .register(
            _resolved(
                "dsl_cte_result_actual_by_team_2026_05",
                actual_route,
                namespace,
                "SaleOrder",
                "actualSalesAmount",
                actual_rows or [
                    {"salesTeam.name": "Team A", "actualSalesAmount": 120},
                    {"salesTeam.name": "Team B", "actualSalesAmount": 80},
                ],
                expires_at,
                schema=actual_schema,
                storage_ref=actual_storage_ref,
            )
        )
        .register(
            _resolved(
                "dsl_result_target_by_team_2026_05_approved",
                "DSL",
                namespace,
                "SalesTarget",
                "targetSalesAmount",
                [
                    {"salesTeam.name": "Team A", "targetSalesAmount": 100},
                    {"salesTeam.name": "Team C", "targetSalesAmount": 50},
                ],
                expires_at,
            )
        )
    )


def _resolved(handle, route, namespace, model, metric, rows, expires_at, schema=None, storage_ref=None):
    return ResolvedMemoryGridResult(
        result_handle=handle,
        source_route=route,
        namespace=namespace,
        grain=["salesTeam.name"],
        schema=schema or _schema(metric),
        rows=rows,
        lineage={"model": model},
        metadata=ResultHandleMetadata(
            handle_id=handle,
            namespace=namespace,
            source_route=route,
            source_model_refs=[model],
            query_hash=f"hash_{handle}",
            created_at=datetime.now(UTC) - timedelta(minutes=1),
            expires_at=expires_at,
            row_count=len(rows),
            row_limit=200,
            lineage={"model": model},
            storage_ref=storage_ref if storage_ref is not None else f"memory://result/{handle}",
        ),
    )


def _schema(metric, *, sensitive=False):
    return {
        "salesTeam.name": MemoryGridColumn(
            "salesTeam.name",
            "string",
            join_allowed=True,
            output_allowed=True,
        ),
        metric: MemoryGridColumn(
            metric,
            "number",
            derived_allowed=True,
            output_allowed=True,
            sensitive=sensitive,
        ),
    }


def _write_request(route, model, metric, rows, *, max_read_count=3):
    return ResultHandleWriteRequest(
        source_route=route,
        source_model_refs=[model],
        query_hash=f"hash_{model}_{metric}",
        grain=["salesTeam.name"],
        schema=_schema(metric),
        rows=rows,
        lineage={"model": model},
        row_limit=200,
        cell_limit=500,
        ttl=timedelta(hours=1),
        max_read_count=max_read_count,
    )


def test_memory_grid_validate_returns_bridge_ready_plan_evidence():
    response = SemanticQueryService().query_model(
        "AnyModel",
        SemanticQueryRequest(route="MEMORY_GRID", memory_grid_plan=_third009_plan()),
        mode="validate",
    )

    assert response.error is None
    assert response.execution is not None
    assert response.execution.route == "MEMORY_GRID"
    assert response.execution.status == "PLAN_READY"
    assert response.execution.memory_grid_validation["memory_grid_bridge_status"] == "BRIDGE_READY"
    assert response.execution.memory_grid_validation["output_limit"] == 200


def test_memory_grid_full_outer_remains_bridge_deferred():
    plan = _third009_plan(join={"type": "full_outer", "keys": ["salesTeam.name"]})
    response = SemanticQueryService().query_model(
        "AnyModel",
        SemanticQueryRequest(route="MEMORY_GRID", memory_grid_plan=plan),
        mode="validate",
    )

    assert response.error is None
    validation = response.execution.memory_grid_validation
    assert validation["memory_grid_bridge_status"] == "BRIDGE_DEFERRED"
    assert "Memory Grid bridge v1 supports inner join only" in validation["memory_grid_bridge_unsupported"]


def test_memory_grid_rejects_missing_result_handle():
    plan = _third009_plan()
    del plan["inputs"][0]["result_handle"]

    response = SemanticQueryService().query_model(
        "AnyModel",
        SemanticQueryRequest(route="MEMORY_GRID", memory_grid_plan=plan),
        mode="validate",
    )

    assert response.error is not None
    assert "MEMORY_GRID_UNGOVERNED_SOURCE" in response.error
    assert response.error_detail["errorCode"] == "MEMORY_GRID_UNGOVERNED_SOURCE"


def test_memory_grid_execute_fails_closed_without_resolver():
    response = SemanticQueryService().query_model(
        "AnyModel",
        SemanticQueryRequest(
            route="MEMORY_GRID",
            memory_grid_plan=_third009_plan(),
            hints={"memoryGridExecute": True},
        ),
    )

    assert response.error is not None
    assert "MEMORY_GRID_RESULT_HANDLE_NOT_FOUND" in response.error
    assert response.error_detail["errorCode"] == "MEMORY_GRID_RESULT_HANDLE_NOT_FOUND"


def test_memory_grid_execute_uses_resolver_and_returns_audit_summary():
    response = SemanticQueryService(memory_grid_result_resolver=_resolver()).query_model(
        "AnyModel",
        SemanticQueryRequest(
            route="MEMORY_GRID",
            memory_grid_plan=_third009_plan(),
            hints={"memoryGridExecute": True},
        ),
    )

    assert response.error is None
    assert response.items == [
        {
            "salesTeam.name": "Team A",
            "actualSalesAmount": 120,
            "targetSalesAmount": 100,
            "targetAchievementRate": 1.2,
        }
    ]
    summary = response.execution.memory_grid_execution_summary
    assert summary["memory_grid_bridge_status"] == "BRIDGE_READY"
    assert summary["resolver_audit"][0]["query_hash"] == "hash_dsl_cte_result_actual_by_team_2026_05"
    assert summary["resolver_audit"][0]["storage_ref"] == "memory://result/dsl_cte_result_actual_by_team_2026_05"


def test_memory_grid_execute_uses_store_backed_result_handles():
    store = InMemoryResultHandleStore()
    storage = InMemoryResultStorageAdapter()
    handles = iter(["mgr_actual_2026_05", "mgr_target_2026_05"])
    writer = ResultHandleWriter(store, storage, handle_supplier=lambda: next(handles))
    actual_handle = writer.write(
        _write_request(
            "DSL_CTE",
            "SaleOrder",
            "actualSalesAmount",
            [{"salesTeam.name": "Team A", "actualSalesAmount": 120}, {"salesTeam.name": "Team B", "actualSalesAmount": 80}],
        )
    )
    target_handle = writer.write(
        _write_request(
            "DSL",
            "SalesTarget",
            "targetSalesAmount",
            [{"salesTeam.name": "Team A", "targetSalesAmount": 100}, {"salesTeam.name": "Team C", "targetSalesAmount": 50}],
        )
    )

    response = SemanticQueryService(memory_grid_result_resolver=MemoryGridStoreBackedResultResolver(store, storage)).query_model(
        "AnyModel",
        SemanticQueryRequest(
            route="MEMORY_GRID",
            memory_grid_plan=_third009_plan(
                inputs=[
                    dict(_third009_plan()["inputs"][0], result_handle=actual_handle),
                    dict(_third009_plan()["inputs"][1], result_handle=target_handle),
                ]
            ),
            hints={"memoryGridExecute": True},
        ),
    )

    assert response.error is None
    assert response.items == [
        {
            "salesTeam.name": "Team A",
            "actualSalesAmount": 120,
            "targetSalesAmount": 100,
            "targetAchievementRate": 1.2,
        }
    ]
    summary = response.execution.memory_grid_execution_summary
    assert summary["resolver_audit"][0]["storage_ref"] == "memory-grid://result/mgr_actual_2026_05"
    assert summary["resolver_audit"][0]["read_count"] == 1
    assert summary["resolver_audit"][0]["cell_count"] == 4


def test_memory_grid_execute_rejects_invalidated_store_backed_handle():
    store = InMemoryResultHandleStore()
    storage = InMemoryResultStorageAdapter()
    writer = ResultHandleWriter(store, storage, handle_supplier=lambda: "mgr_actual_2026_05")
    actual_handle = writer.write(
        _write_request(
            "DSL_CTE",
            "SaleOrder",
            "actualSalesAmount",
            [{"salesTeam.name": "Team A", "actualSalesAmount": 120}],
        )
    )
    store.invalidate(actual_handle)
    resolver = MemoryGridStoreBackedResultResolver(store, storage)

    response = SemanticQueryService(memory_grid_result_resolver=resolver).query_model(
        "AnyModel",
        SemanticQueryRequest(
            route="MEMORY_GRID",
            memory_grid_plan=_third009_plan(inputs=[dict(_third009_plan()["inputs"][0], result_handle=actual_handle), _third009_plan()["inputs"][1]]),
            hints={"memoryGridExecute": True},
        ),
    )

    assert response.error is not None
    assert response.error_detail["errorCode"] == "MEMORY_GRID_RESULT_HANDLE_EXPIRED"


def test_memory_grid_execute_rejects_store_backed_storage_unavailable():
    store = InMemoryResultHandleStore()
    writer = ResultHandleWriter(store, InMemoryResultStorageAdapter(), handle_supplier=lambda: "mgr_actual_2026_05")
    actual_handle = writer.write(
        _write_request(
            "DSL_CTE",
            "SaleOrder",
            "actualSalesAmount",
            [{"salesTeam.name": "Team A", "actualSalesAmount": 120}],
        )
    )
    resolver = MemoryGridStoreBackedResultResolver(store, InMemoryResultStorageAdapter())

    response = SemanticQueryService(memory_grid_result_resolver=resolver).query_model(
        "AnyModel",
        SemanticQueryRequest(
            route="MEMORY_GRID",
            memory_grid_plan=_third009_plan(inputs=[dict(_third009_plan()["inputs"][0], result_handle=actual_handle), _third009_plan()["inputs"][1]]),
            hints={"memoryGridExecute": True},
        ),
    )

    assert response.error is not None
    assert response.error_detail["errorCode"] == "MEMORY_GRID_RESULT_STORAGE_UNAVAILABLE"


def test_memory_grid_execute_rejects_store_backed_handle_after_max_read_count():
    store = InMemoryResultHandleStore()
    storage = InMemoryResultStorageAdapter()
    handles = iter(["mgr_actual_2026_05", "mgr_target_2026_05"])
    writer = ResultHandleWriter(store, storage, handle_supplier=lambda: next(handles))
    actual_handle = writer.write(
        _write_request(
            "DSL_CTE",
            "SaleOrder",
            "actualSalesAmount",
            [{"salesTeam.name": "Team A", "actualSalesAmount": 120}],
            max_read_count=1,
        )
    )
    target_handle = writer.write(
        _write_request(
            "DSL",
            "SalesTarget",
            "targetSalesAmount",
            [{"salesTeam.name": "Team A", "targetSalesAmount": 100}],
        )
    )
    request = SemanticQueryRequest(
        route="MEMORY_GRID",
        memory_grid_plan=_third009_plan(
            inputs=[
                dict(_third009_plan()["inputs"][0], result_handle=actual_handle),
                dict(_third009_plan()["inputs"][1], result_handle=target_handle),
            ]
        ),
        hints={"memoryGridExecute": True},
    )
    service = SemanticQueryService(memory_grid_result_resolver=MemoryGridStoreBackedResultResolver(store, storage))

    assert service.query_model("AnyModel", request).error is None
    response = service.query_model("AnyModel", request)

    assert response.error is not None
    assert response.error_detail["errorCode"] == "MEMORY_GRID_RESULT_GOVERNANCE_MISMATCH"


def test_memory_grid_execute_rejects_sensitive_derived_operand():
    response = SemanticQueryService(
        memory_grid_result_resolver=_resolver(actual_schema=_schema("actualSalesAmount", sensitive=True))
    ).query_model(
        "AnyModel",
        SemanticQueryRequest(
            route="MEMORY_GRID",
            memory_grid_plan=_third009_plan(),
            hints={"memoryGridExecute": True},
        ),
    )

    assert response.error is not None
    assert "MEMORY_GRID_RESULT_GOVERNANCE_MISMATCH" in response.error
    assert response.error_detail["errorCode"] == "MEMORY_GRID_RESULT_GOVERNANCE_MISMATCH"


def test_memory_grid_execute_rejects_sensitive_output_path():
    plan = _third009_plan(output=["salesTeam.name", "actualSalesAmount"])
    response = SemanticQueryService(
        memory_grid_result_resolver=_resolver(actual_schema=_schema("actualSalesAmount", sensitive=True))
    ).query_model(
        "AnyModel",
        SemanticQueryRequest(
            route="MEMORY_GRID",
            memory_grid_plan=plan,
            hints={"memoryGridExecute": True},
        ),
    )

    assert response.error is not None
    assert "MEMORY_GRID_RESULT_GOVERNANCE_MISMATCH" in response.error
    assert response.error_detail["errorCode"] == "MEMORY_GRID_RESULT_GOVERNANCE_MISMATCH"


def test_memory_grid_execute_rejects_missing_declared_metric_schema():
    response = SemanticQueryService(memory_grid_result_resolver=_resolver(actual_schema=_schema("notActualSalesAmount"))).query_model(
        "AnyModel",
        SemanticQueryRequest(
            route="MEMORY_GRID",
            memory_grid_plan=_third009_plan(),
            hints={"memoryGridExecute": True},
        ),
    )

    assert response.error is not None
    assert "MEMORY_GRID_RESULT_SCHEMA_MISMATCH" in response.error
    assert response.error_detail["errorCode"] == "MEMORY_GRID_RESULT_SCHEMA_MISMATCH"


def test_memory_grid_execute_rejects_source_route_mismatch():
    response = SemanticQueryService(memory_grid_result_resolver=_resolver(actual_route="DSL")).query_model(
        "AnyModel",
        SemanticQueryRequest(
            route="MEMORY_GRID",
            memory_grid_plan=_third009_plan(),
            hints={"memoryGridExecute": True},
        ),
    )

    assert response.error is not None
    assert "MEMORY_GRID_RESULT_SOURCE_ROUTE_MISMATCH" in response.error
    assert response.error_detail["errorCode"] == "MEMORY_GRID_RESULT_SOURCE_ROUTE_MISMATCH"


def test_memory_grid_execute_rejects_expired_result_handle():
    response = SemanticQueryService(
        memory_grid_result_resolver=_resolver(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    ).query_model(
        "AnyModel",
        SemanticQueryRequest(
            route="MEMORY_GRID",
            memory_grid_plan=_third009_plan(),
            hints={"memoryGridExecute": True},
        ),
    )

    assert response.error is not None
    assert "MEMORY_GRID_RESULT_HANDLE_EXPIRED" in response.error
    assert response.error_detail["errorCode"] == "MEMORY_GRID_RESULT_HANDLE_EXPIRED"


def test_memory_grid_execute_rejects_missing_storage_ref():
    response = SemanticQueryService(memory_grid_result_resolver=_resolver(actual_storage_ref="")).query_model(
        "AnyModel",
        SemanticQueryRequest(
            route="MEMORY_GRID",
            memory_grid_plan=_third009_plan(),
            hints={"memoryGridExecute": True},
        ),
    )

    assert response.error is not None
    assert "MEMORY_GRID_RESULT_STORAGE_UNAVAILABLE" in response.error
    assert response.error_detail["errorCode"] == "MEMORY_GRID_RESULT_STORAGE_UNAVAILABLE"


def test_memory_grid_execute_rejects_rows_over_declared_limit():
    actual_input = dict(_third009_plan()["inputs"][0], row_limit=1)
    response = SemanticQueryService(
        memory_grid_result_resolver=_resolver(
            actual_rows=[
                {"salesTeam.name": "Team A", "actualSalesAmount": 120},
                {"salesTeam.name": "Team B", "actualSalesAmount": 80},
            ]
        )
    ).query_model(
        "AnyModel",
        SemanticQueryRequest(
            route="MEMORY_GRID",
            memory_grid_plan=_third009_plan(inputs=[actual_input, _third009_plan()["inputs"][1]]),
            hints={"memoryGridExecute": True},
        ),
    )

    assert response.error is not None
    assert "MEMORY_GRID_RESULT_GOVERNANCE_MISMATCH" in response.error
    assert response.error_detail["errorCode"] == "MEMORY_GRID_RESULT_GOVERNANCE_MISMATCH"


def test_memory_grid_execute_rejects_default_handle_from_named_namespace():
    response = SemanticQueryService(memory_grid_result_resolver=_resolver(namespace=None)).query_model(
        "AnyModel",
        SemanticQueryRequest(
            route="MEMORY_GRID",
            memory_grid_plan=_third009_plan(),
            hints={"memoryGridExecute": True},
        ),
        context=SemanticRequestContext(namespace="odoo"),
    )

    assert response.error is not None
    assert "MEMORY_GRID_RESULT_NAMESPACE_MISMATCH" in response.error
    assert response.error_detail["errorCode"] == "MEMORY_GRID_RESULT_NAMESPACE_MISMATCH"
