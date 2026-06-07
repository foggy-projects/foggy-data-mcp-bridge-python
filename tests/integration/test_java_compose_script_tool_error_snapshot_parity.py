"""Replay Java MCP compose-script error payload snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from foggy.dataset_model.engine.compose.security import (
    AuthorityResolution,
    ModelBinding,
)
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp.tools.compose_script_tool import ComposeScriptTool
from foggy.mcp_spi.context import ToolExecutionContext

SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_compose_script_tool_error_snapshot_parity.json"
)


def _load_snapshot() -> dict[str, Any]:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


class _StubSemanticService:
    def execute_sql(self, sql, params, *, route_model=None):
        raise AssertionError("execute_sql is not used by tool error snapshots")


class _PermissiveResolver:
    def resolve(self, request):
        return AuthorityResolution(
            bindings={model_query.model: ModelBinding() for model_query in request.models}
        )


def _tool_context(raw: dict[str, Any]) -> ToolExecutionContext:
    return ToolExecutionContext(
        request_id=raw.get("traceId", "java-compose-script-tool-error-snapshot"),
        namespace=raw.get("namespace"),
        headers=dict(raw.get("headers") or {}),
    )


def test_snapshot_schema() -> None:
    snapshot = _load_snapshot()
    assert snapshot["schemaVersion"] == 1
    assert snapshot["feature"] == "scriptRuntimeToolErrors"
    assert snapshot["source"] == "JavaComposeScriptToolErrorSnapshotTest"
    assert snapshot["tool"] == "dataset.compose_script"
    assert snapshot.get("cases")


async def _execute_case(case: dict[str, Any]):
    if case["id"] == "remote-principal-mismatch":
        service = SemanticQueryService()
        service.register_model(create_fact_sales_model())
        tool = ComposeScriptTool(
            authority_resolver_factory=lambda _ctx: _PermissiveResolver(),
            semantic_service=service,
        )
        return await tool.execute(dict(case["arguments"]), _tool_context(case["context"]))

    tool = ComposeScriptTool(
        authority_resolver_factory=lambda _ctx: None,
        semantic_service=_StubSemanticService(),
    )
    return await tool.execute(dict(case["arguments"]), _tool_context(case["context"]))


@pytest.mark.asyncio
async def test_java_compose_script_tool_error_snapshot_replays_in_python() -> None:
    snapshot = _load_snapshot()

    for case in snapshot["cases"]:
        result = await _execute_case(case)
        expected = case["expected"]
        assert result.success is False
        assert result.tool_name == snapshot["tool"]
        assert result.error_code == expected["errorCode"]

        data = result.data
        assert data["error_code"] == expected["errorCode"]
        assert data["phase"] == expected["phase"]
        assert "model" not in data
        assert result.error == data["message"]

        payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
        for marker in expected.get("messageMarkers", []):
            assert marker in data["message"]
        for marker in expected.get("forbiddenMarkers", []):
            assert marker not in payload
