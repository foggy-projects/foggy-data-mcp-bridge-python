"""Java-aligned Memory Grid SPI serialization tests."""

from foggy.mcp_spi import SemanticQueryRequest, SemanticQueryResponse


def test_memory_grid_request_uses_java_aliases():
    req = SemanticQueryRequest(
        route="MEMORY_GRID",
        status="PLAN_READY",
        risk_flags=["result_size_risk"],
        memory_grid_plan={"inputs": [], "output_limit": 10},
        executable_plan={"kind": "memory_grid"},
    )

    payload = req.model_dump(by_alias=True, exclude_none=True)

    assert payload["route"] == "MEMORY_GRID"
    assert payload["status"] == "PLAN_READY"
    assert payload["risk_flags"] == ["result_size_risk"]
    assert payload["memory_grid_plan"] == {"inputs": [], "output_limit": 10}
    assert payload["executable_plan"] == {"kind": "memory_grid"}
    assert "memory_grid_plan" in payload
    assert "memoryGridPlan" not in payload


def test_memory_grid_response_execution_uses_java_aliases():
    resp = SemanticQueryResponse(
        items=[],
        execution={
            "route": "MEMORY_GRID",
            "status": "PLAN_READY",
            "memory_grid_plan": {"inputs": []},
            "memory_grid_validation": {"memory_grid_bridge_status": "BRIDGE_DEFERRED"},
            "error_code": None,
        },
    )

    payload = resp.model_dump(by_alias=True, exclude_none=True)

    assert payload["execution"]["route"] == "MEMORY_GRID"
    assert payload["execution"]["memory_grid_plan"] == {"inputs": []}
    assert payload["execution"]["memory_grid_validation"]["memory_grid_bridge_status"] == "BRIDGE_DEFERRED"
    assert "memoryGridPlan" not in payload["execution"]
