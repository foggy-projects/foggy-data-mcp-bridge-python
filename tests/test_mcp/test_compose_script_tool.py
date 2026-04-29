"""Tests for ``ComposeScriptTool`` — MCP entry point for Compose Query."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import pytest

from foggy.dataset_model.engine.compose import ComposedSql
from foggy.dataset_model.engine.compose.authority.resolver import (
    AuthorityResolutionError,
)
from foggy.dataset_model.engine.compose.compilation import error_codes as cc_codes
from foggy.dataset_model.engine.compose.compilation.errors import (
    ComposeCompileError,
)
from foggy.dataset_model.engine.compose.sandbox.error_codes import (
    LAYER_B_FUNCTION_DENIED,
    PHASE_SCRIPT_EVAL,
)
from foggy.dataset_model.engine.compose.sandbox.exceptions import (
    ComposeSandboxViolationError,
)
from foggy.dataset_model.engine.compose.schema.error_codes import (
    DUPLICATE_OUTPUT_COLUMN,
    PHASE_SCHEMA_DERIVE,
)
from foggy.dataset_model.engine.compose.schema.errors import ComposeSchemaError
from foggy.dataset_model.engine.compose.security import (
    AuthorityResolution,
    ModelBinding,
)
from foggy.mcp.tools.compose_script_tool import ComposeScriptTool
from foggy.mcp_spi.context import ToolExecutionContext


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _StubResolver:
    def resolve(self, request):
        return AuthorityResolution(bindings={
            mq.model: ModelBinding() for mq in request.models
        })


class _StubSemanticService:
    def __init__(self, rows=None):
        self.rows = rows if rows is not None else [{"id": 1}]

    def execute_sql(self, sql, params, *, route_model=None):
        return list(self.rows)


def _resolver_factory(_ctx):
    return _StubResolver()


def _tool_ctx(**kwargs) -> ToolExecutionContext:
    kwargs.setdefault("request_id", "req-1")
    kwargs.setdefault("namespace", "default")
    kwargs.setdefault("headers", {"X-User-Id": "u1"})
    return ToolExecutionContext(**kwargs)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if asyncio._get_running_loop() is None else None


async def _exec_tool(tool, arguments, context):
    return await tool.execute(arguments, context)


# ---------------------------------------------------------------------------
# Construction guards
# ---------------------------------------------------------------------------


def test_factory_required():
    with pytest.raises(ValueError, match="authority_resolver_factory is required"):
        ComposeScriptTool(
            authority_resolver_factory=None,
            semantic_service=_StubSemanticService(),
        )


def test_service_required():
    with pytest.raises(ValueError, match="semantic_service is required"):
        ComposeScriptTool(
            authority_resolver_factory=_resolver_factory,
            semantic_service=None,
        )


def test_parameters_schema_exposes_only_script():
    tool = ComposeScriptTool(
        authority_resolver_factory=_resolver_factory,
        semantic_service=_StubSemanticService(),
    )
    params = tool.get_parameters()
    assert len(params) == 1
    assert params[0]["name"] == "script"
    assert params[0]["required"] is True
    assert params[0]["type"] == "string"
    assert "dsl({...})" in params[0]["description"]
    assert "return { plans: plan }" in params[0]["description"]
    assert "Do not call `.execute()` directly" in params[0]["description"]
    assert "host-controlled" in params[0]["description"]
    assert "from({" not in params[0]["description"]


def test_tool_identity():
    tool = ComposeScriptTool(
        authority_resolver_factory=_resolver_factory,
        semantic_service=_StubSemanticService(),
    )
    assert tool.tool_name == "dataset.compose_script"
    assert tool.name == "dataset.compose_script"
    assert "SemanticDSL" in tool.description
    assert "return { plans: plan }" in tool.description
    assert "do not call .execute() directly" in tool.description
    assert "raw SQL" in tool.description


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_script_argument_returns_error():
    tool = ComposeScriptTool(
        authority_resolver_factory=_resolver_factory,
        semantic_service=_StubSemanticService(),
    )
    result = await tool.execute({}, _tool_ctx())
    assert result.success is False
    assert result.data["error_code"] == "host-misconfig"
    assert result.data["phase"] == "internal"


@pytest.mark.asyncio
async def test_empty_script_argument_returns_error():
    tool = ComposeScriptTool(
        authority_resolver_factory=_resolver_factory,
        semantic_service=_StubSemanticService(),
    )
    result = await tool.execute({"script": ""}, _tool_ctx())
    assert result.success is False
    assert result.data["error_code"] == "host-misconfig"


@pytest.mark.asyncio
async def test_missing_context_returns_error():
    tool = ComposeScriptTool(
        authority_resolver_factory=_resolver_factory,
        semantic_service=_StubSemanticService(),
    )
    result = await tool.execute({"script": "1"}, None)
    assert result.success is False
    assert "ToolExecutionContext" in result.data["message"]


# ---------------------------------------------------------------------------
# Resolver factory errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_factory_raising_wraps_to_host_misconfig():
    def bad_factory(_ctx):
        raise RuntimeError("can't build resolver")

    tool = ComposeScriptTool(
        authority_resolver_factory=bad_factory,
        semantic_service=_StubSemanticService(),
    )
    result = await tool.execute({"script": "1"}, _tool_ctx())
    assert result.success is False
    assert result.data["error_code"] == "host-misconfig"
    assert "can't build resolver" in result.data["message"]


@pytest.mark.asyncio
async def test_factory_returning_none_is_host_misconfig():
    tool = ComposeScriptTool(
        authority_resolver_factory=lambda _c: None,
        semantic_service=_StubSemanticService(),
    )
    result = await tool.execute({"script": "1"}, _tool_ctx())
    assert result.success is False
    assert result.data["error_code"] == "host-misconfig"


# ---------------------------------------------------------------------------
# Context bridge errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_user_id_bridges_to_host_misconfig():
    tool = ComposeScriptTool(
        authority_resolver_factory=_resolver_factory,
        semantic_service=_StubSemanticService(),
    )
    tc = ToolExecutionContext(
        request_id="r1", namespace="default", headers={},
    )
    result = await tool.execute({"script": "1"}, tc)
    assert result.success is False
    assert result.data["error_code"] == "host-misconfig"
    assert "principal identity" in result.data["message"]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_returns_value():
    tool = ComposeScriptTool(
        authority_resolver_factory=_resolver_factory,
        semantic_service=_StubSemanticService(),
    )
    result = await tool.execute({"script": "2 + 3"}, _tool_ctx())
    assert result.success is True
    assert result.data["value"] == 5


@pytest.mark.asyncio
async def test_happy_path_returns_plan_object(monkeypatch):
    tool = ComposeScriptTool(
        authority_resolver_factory=_resolver_factory,
        semantic_service=_StubSemanticService(),
    )
    result = await tool.execute(
        {"script": 'dsl({model: "X", columns: ["id"]})'},
        _tool_ctx(),
    )
    assert result.success is True
    # Plan object surface
    value = result.data["value"]
    assert value.model == "X"


@pytest.mark.asyncio
async def test_documented_join_signature_returns_plan_object():
    tool = ComposeScriptTool(
        authority_resolver_factory=_resolver_factory,
        semantic_service=_StubSemanticService(),
    )
    result = await tool.execute(
        {
            "script": (
                'const left = dsl({model: "X", columns: ["id"]});'
                'const right = dsl({model: "Y", columns: ["xId"]});'
                'return left.join(right, "left", [{left: "id", op: "=", right: "xId"}]);'
            )
        },
        _tool_ctx(),
    )
    assert result.success is True
    assert result.data["value"].type == "left"


# ---------------------------------------------------------------------------
# Error family routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authority_resolution_error_routes_to_permission_resolve():
    """Raise AuthorityResolutionError inside resolver.resolve; the compiler
    will call resolve and bubble it."""

    from foggy.dataset_model.engine.compose.security import error_codes as auth_codes

    class _FailingResolver:
        def resolve(self, request):
            raise AuthorityResolutionError(
                code=auth_codes.UPSTREAM_FAILURE,
                message="resolver down",
            )

    tool = ComposeScriptTool(
        authority_resolver_factory=lambda _c: _FailingResolver(),
        semantic_service=_StubSemanticService(),
    )
    result = await tool.execute(
        {"script": 'from({model: "X", columns: ["id"]}).execute()'},
        _tool_ctx(),
    )
    assert result.success is False
    assert result.data["phase"] == "permission-resolve"
    assert result.data["error_code"] == auth_codes.UPSTREAM_FAILURE


@pytest.mark.asyncio
async def test_compose_compile_error_routes_to_compile(monkeypatch):
    """Monkeypatch the compiler to raise ComposeCompileError."""

    def raising_compile(plan, ctx, *, semantic_service, bindings=None,
                        model_info_provider=None, dialect="mysql"):
        raise ComposeCompileError(
            code=cc_codes.MISSING_BINDING,
            message="binding missing for X",
            phase="compile",
        )

    monkeypatch.setattr(
        "foggy.dataset_model.engine.compose.runtime.plan_execution.compile_plan_to_sql",
        raising_compile,
    )

    tool = ComposeScriptTool(
        authority_resolver_factory=_resolver_factory,
        semantic_service=_StubSemanticService(),
    )
    result = await tool.execute(
        {"script": 'from({model: "X", columns: ["id"]}).execute()'},
        _tool_ctx(),
    )
    assert result.success is False
    assert result.data["phase"] == "compile"
    assert result.data["error_code"] == cc_codes.MISSING_BINDING


@pytest.mark.asyncio
async def test_execute_phase_runtimeerror_routes_to_execute(monkeypatch):
    """compile succeeds but semantic_service.execute_sql raises."""
    def fake_compile(plan, ctx, *, semantic_service, bindings=None,
                    model_info_provider=None, dialect="mysql"):
        return ComposedSql(sql="SELECT 1", params=[])

    monkeypatch.setattr(
        "foggy.dataset_model.engine.compose.runtime.plan_execution.compile_plan_to_sql",
        fake_compile,
    )

    class _BombSvc:
        def execute_sql(self, sql, params, *, route_model=None):
            raise RuntimeError("db crashed")

    tool = ComposeScriptTool(
        authority_resolver_factory=_resolver_factory,
        semantic_service=_BombSvc(),
    )
    result = await tool.execute(
        {"script": 'from({model: "X", columns: ["id"]}).execute()'},
        _tool_ctx(),
    )
    assert result.success is False
    assert result.data["phase"] == "execute"
    assert result.data["error_code"] == "execute-phase-error"


@pytest.mark.asyncio
async def test_error_payload_has_four_field_shape():
    """All error branches must expose error_code / phase / message."""
    tool = ComposeScriptTool(
        authority_resolver_factory=_resolver_factory,
        semantic_service=_StubSemanticService(),
    )
    result = await tool.execute({}, _tool_ctx())
    assert result.success is False
    for field in ("error_code", "phase", "message"):
        assert field in result.data, f"missing {field!r} in error payload"


# ---------------------------------------------------------------------------
# Success payload fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_plan_build_omits_sql_when_not_executed():
    tool = ComposeScriptTool(
        authority_resolver_factory=_resolver_factory,
        semantic_service=_StubSemanticService(),
    )
    result = await tool.execute(
        {"script": 'from({model: "X", columns: ["id"]})'},
        _tool_ctx(),
    )
    assert result.success is True
    assert "sql" not in result.data  # Plan wasn't compiled


@pytest.mark.asyncio
async def test_embedded_mode_principal_state_is_respected():
    """Host can push state['compose.principal'] and skip header parsing."""
    from foggy.dataset_model.engine.compose.context.principal import Principal

    tool = ComposeScriptTool(
        authority_resolver_factory=_resolver_factory,
        semantic_service=_StubSemanticService(),
    )
    tc = ToolExecutionContext(
        request_id="r1",
        namespace="default",
        state={"compose.principal": Principal(user_id="emb-user")},
        headers={},
    )
    result = await tool.execute({"script": "1"}, tc)
    assert result.success is True
