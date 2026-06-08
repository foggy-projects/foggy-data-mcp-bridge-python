"""Replay Java compose-script runtime/tool snapshots when available."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from foggy.dataset_model.engine.compose import ComposedSql
from foggy.dataset_model.engine.compose.capability import (
    CapabilityPolicy,
    CapabilityRegistry,
    FunctionDescriptor,
)
from foggy.dataset_model.engine.compose.context import ComposeQueryContext, Principal
from foggy.dataset_model.engine.compose.plan.plan import (
    BaseModelPlan,
    DerivedQueryPlan,
    JoinPlan,
    QueryPlan,
    UnionPlan,
)
from foggy.dataset_model.engine.compose.runtime import (
    ALLOWED_SCRIPT_GLOBALS,
    run_script,
)
from foggy.dataset_model.engine.compose.security import (
    AuthorityRequest,
    AuthorityResolution,
    ModelBinding,
)
from foggy.mcp.schemas.tool_config_loader import get_tool_config_loader

SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_compose_script_snapshot_parity.json"
)


def _load_snapshot() -> dict[str, Any]:
    if not SNAPSHOT_PATH.exists():
        pytest.skip(
            "Java compose-script snapshot export not available yet: "
            f"{SNAPSHOT_PATH}. P0-4 keeps this replay optional until the Java "
            "worktree exports the neutral script/runtime fixture.",
        )
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


class _PermissiveResolver:
    def resolve(self, request: AuthorityRequest) -> AuthorityResolution:
        return AuthorityResolution(
            bindings={model_query.model: ModelBinding() for model_query in request.models}
        )


class _StubSemanticService:
    def execute_sql(self, sql, params, *, route_model=None):
        return [{"routeModel": route_model, "stub": 1}]


def _compose_context() -> ComposeQueryContext:
    return ComposeQueryContext(
        principal=Principal(user_id="snapshot-user", tenant_id="demo", roles=["analyst"]),
        namespace="demo",
        authority_resolver=_PermissiveResolver(),
    )


def test_snapshot_schema() -> None:
    snapshot = _load_snapshot()
    assert snapshot["schemaVersion"] == 1
    assert snapshot["feature"] == "scriptRuntimeTool"
    assert snapshot["source"]
    assert snapshot.get("tool", {}).get("name") == "dataset.compose_script"
    assert snapshot.get("cases")


def test_java_compose_script_tool_snapshot_matches_python_resources() -> None:
    snapshot = _load_snapshot()
    tool_snapshot = snapshot["tool"]

    loader = get_tool_config_loader()
    tool = loader.get_tool(tool_snapshot["name"])
    assert tool is not None
    assert tool.name == tool_snapshot["name"]

    schema = tool.inputSchema
    assert schema.get("type") == "object"
    assert list(schema.get("required") or []) == list(tool_snapshot["required"])
    schema_text = json.dumps(schema, ensure_ascii=False)
    for marker in tool_snapshot.get("schemaMarkers", []):
        assert marker in schema_text

    for marker in tool_snapshot.get("descriptionMarkers", []):
        assert marker in tool.description
    for marker in tool_snapshot.get("forbiddenMarkers", []):
        assert marker not in tool.description
        assert marker not in schema_text


def test_java_runtime_global_surface_is_covered_by_python() -> None:
    snapshot = _load_snapshot()
    java_globals = set(snapshot["runtime"]["allowedScriptGlobals"])
    accepted_extras = set(snapshot["runtime"].get("acceptedPythonExtraGlobals", []))

    assert java_globals <= set(ALLOWED_SCRIPT_GLOBALS)
    assert set(ALLOWED_SCRIPT_GLOBALS) <= java_globals | accepted_extras


def test_java_compose_script_runtime_snapshot_replays_in_python(monkeypatch) -> None:
    snapshot = _load_snapshot()

    monkeypatch.setattr(
        "foggy.dataset_model.engine.compose.runtime.plan_execution.compile_plan_to_sql",
        _stub_compile,
    )
    monkeypatch.setattr(
        "foggy.dataset_model.engine.compose.compilation.compiler.compile_plan_to_sql",
        _stub_compile,
    )

    for case in snapshot.get("cases", []):
        _assert_case_replays(case)


def _stub_compile(plan: QueryPlan, *_args, **_kwargs) -> ComposedSql:
    return ComposedSql(sql=_stub_sql(plan), params=[])


def _stub_sql(plan: QueryPlan) -> str:
    if isinstance(plan, BaseModelPlan):
        columns = _columns_sql(plan.columns)
        return f"SELECT '{plan.model}' AS __model__{columns} FROM {plan.model}"
    if isinstance(plan, DerivedQueryPlan):
        columns = _columns_sql(plan.columns, leading=False)
        return f"SELECT {columns} FROM ({_stub_sql(plan.source)}) AS derived_stub"
    if isinstance(plan, UnionPlan):
        operator = "UNION ALL" if plan.all else "UNION"
        return f"{_stub_sql(plan.left)} {operator} {_stub_sql(plan.right)}"
    if isinstance(plan, JoinPlan):
        join_type = plan.type.upper()
        conditions = " AND ".join(
            f"{condition.left} {condition.op} {condition.right}" for condition in plan.on
        )
        return (
            f"{_stub_sql(plan.left)} {join_type} JOIN ({_stub_sql(plan.right)}) "
            f"ON {conditions}"
        )
    raise AssertionError(f"Unsupported compose snapshot plan: {type(plan).__name__}")


def _columns_sql(columns: tuple[str, ...], *, leading: bool = True) -> str:
    if not columns:
        return "" if leading else "*"
    joined = ", ".join(str(column) for column in columns)
    return f", {joined}" if leading else joined


def _assert_case_replays(case: dict[str, Any]) -> None:
    expected = case.get("expected", {})
    capability_registry, capability_policy = _capability_inputs(case)
    error_marker = expected.get("errorMarker")
    if error_marker:
        with pytest.raises(Exception) as exc_info:  # noqa: BLE001
            run_script(
                case["script"],
                _compose_context(),
                semantic_service=_StubSemanticService(),
                dialect=case.get("dialect", "mysql"),
                preview_mode=bool(case.get("previewMode")),
                capability_registry=capability_registry,
                capability_policy=capability_policy,
            )
        assert error_marker in str(exc_info.value)
        return

    result = run_script(
        case["script"],
        _compose_context(),
        semantic_service=_StubSemanticService(),
        dialect=case.get("dialect", "mysql"),
        preview_mode=bool(case.get("previewMode")),
        capability_registry=capability_registry,
        capability_policy=capability_policy,
    )
    value_type = expected.get("valueType")
    if value_type == "number":
        assert isinstance(result.value, (int, float))
        assert int(result.value) == int(expected["value"])
    elif value_type == "map":
        assert isinstance(result.value, dict)
    else:
        raise AssertionError(f"Unsupported script snapshot valueType: {value_type!r}")

    if expected.get("hasSql"):
        plans = result.value["plans"]
        assert isinstance(plans, ComposedSql)
        for marker in expected.get("sqlMarkers", []):
            assert marker in plans.sql
        if "params" in expected:
            assert list(plans.params) == list(expected["params"])

    if expected.get("hasRows"):
        plans = result.value["plans"]
        assert isinstance(plans, list)
        assert plans == expected.get("rows")


def _capability_inputs(
    case: dict[str, Any],
) -> tuple[CapabilityRegistry | None, CapabilityPolicy | None]:
    scenario = case.get("capabilityScenario")
    if scenario not in {"fiscal-year-allow", "fiscal-year-deny"}:
        return None, None

    registry = CapabilityRegistry()
    registry.register_function(
        FunctionDescriptor(
            name="fiscalYear",
            kind="pure_runtime",
            args_schema=[{"name": "month", "type": "int"}],
            return_type="int",
            deterministic=True,
            side_effect="none",
            allowed_in=["compose_runtime"],
            audit_tag="test.fiscalYear",
            dialects=None,
        ),
        handler=lambda month: 2025 if int(month) >= 4 else 2024,
    )
    if scenario == "fiscal-year-allow":
        policy = CapabilityPolicy(allowed_functions=frozenset({"fiscalYear"}))
    else:
        policy = CapabilityPolicy.empty()
    return registry, policy
