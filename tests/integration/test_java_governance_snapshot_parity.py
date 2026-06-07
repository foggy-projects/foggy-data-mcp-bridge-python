"""Replay Java governance snapshots when the export is available.

P0-5/P0-6 keep this lane engine-neutral: binding three-state semantics,
per-base governance forwarding into the v1.3 query boundary, missing
visible-model binding fail-closed behavior, deniedColumns mapping, query
validation, and metadata trimming.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from foggy.dataset_model.engine.compose.compilation import compile_plan_to_sql
from foggy.dataset_model.engine.compose.compilation.errors import ComposeCompileError
from foggy.dataset_model.engine.compose.context import ComposeQueryContext, Principal
from foggy.dataset_model.engine.compose.plan import QueryPlan, from_
from foggy.dataset_model.engine.compose.security import (
    AuthorityRequest,
    AuthorityResolution,
    AuthorityResolutionError,
    ModelBinding,
)
from foggy.dataset_model.semantic.pivot.domain_transport import DomainTransportPlan
from foggy.dataset_model.semantic.service import QueryBuildResult, SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest
from foggy.mcp_spi.semantic import DeniedColumn

SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_governance_snapshot_parity.json"
)


def _load_snapshot() -> dict[str, Any]:
    if not SNAPSHOT_PATH.exists():
        pytest.skip(
            "Java governance snapshot export not available yet: "
            f"{SNAPSHOT_PATH}. P0-5 keeps the replay harness optional until "
            "the Java worktree exports engine-neutral governance snapshots.",
        )
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


class _PermissiveResolver:
    def resolve(self, request: AuthorityRequest) -> AuthorityResolution:
        return AuthorityResolution(
            bindings={model_query.model: ModelBinding() for model_query in request.models}
        )


class _StaticResolver:
    def __init__(self, bindings: dict[str, ModelBinding]) -> None:
        self.bindings = bindings

    def resolve(self, request: AuthorityRequest) -> AuthorityResolution:
        return AuthorityResolution(bindings=self.bindings)


class _CapturingSemanticService:
    def __init__(self) -> None:
        self.model: str | None = None
        self.request: Any = None

    def build_query_with_governance(
        self,
        model: str,
        request: Any,
    ) -> QueryBuildResult:
        self.model = model
        self.request = request
        return QueryBuildResult(
            sql="SELECT 1 AS __governance_stub__",
            params=[],
            columns=[{"name": column} for column in request.columns],
        )


def _sales_service() -> SemanticQueryService:
    service = SemanticQueryService()
    service.register_model(create_fact_sales_model())
    return service


def _compose_context(authority_resolver: Any | None = None) -> ComposeQueryContext:
    return ComposeQueryContext(
        principal=Principal(user_id="snapshot-user", tenant_id="demo", roles=["analyst"]),
        namespace="demo",
        authority_resolver=authority_resolver or _PermissiveResolver(),
        trace_id="java-governance-snapshot",
    )


def _plan_from_snapshot(node: dict[str, Any]) -> QueryPlan:
    assert node["type"] == "base"
    return from_(
        model=node["model"],
        columns=list(node["columns"]),
        slice=list(node.get("slice", [])),
    )


def _binding_from_snapshot(node: dict[str, Any]) -> ModelBinding:
    field_access = None
    if "fieldAccess" in node:
        field_access = list(node["fieldAccess"])
    return ModelBinding(
        field_access=field_access,
        denied_columns=[
            DeniedColumn(**denied_column)
            for denied_column in node.get("deniedColumns", [])
        ],
        system_slice=list(node.get("systemSlice", [])),
    )


def _denied_columns_to_dicts(items: list[DeniedColumn] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items or []:
        row = item.model_dump(by_alias=True, exclude_none=True)
        out.append(row)
    return out


def _denied_columns_from_snapshot(items: list[dict[str, Any]] | None) -> list[DeniedColumn]:
    return [DeniedColumn(**item) for item in items or []]


def test_snapshot_schema() -> None:
    snapshot = _load_snapshot()
    assert snapshot["schemaVersion"] == 1
    assert snapshot["feature"] == "governance"
    assert snapshot["source"]
    assert snapshot.get("cases")


def test_java_governance_snapshot_replays_in_python() -> None:
    snapshot = _load_snapshot()
    for case in snapshot.get("cases", []):
        _assert_case_replays(case)


def _assert_case_replays(case: dict[str, Any]) -> None:
    case_type = case["type"]
    if case_type == "binding-semantics":
        _assert_binding_semantics(case)
    elif case_type == "compile-forwarding":
        _assert_compile_forwarding(case)
    elif case_type == "compile-error":
        _assert_compile_error(case)
    elif case_type == "authority-resolution":
        _assert_authority_resolution(case)
    elif case_type == "denied-column-mapping":
        _assert_denied_column_mapping(case)
    elif case_type == "query-validation":
        _assert_query_validation(case)
    elif case_type == "pivot-query-validation":
        _assert_pivot_query_validation(case)
    elif case_type == "domain-transport-query-validation":
        _assert_domain_transport_query_validation(case)
    elif case_type == "metadata-trimming":
        _assert_metadata_trimming(case)
    else:
        raise AssertionError(f"Unsupported governance snapshot case type: {case_type!r}")


def _assert_binding_semantics(case: dict[str, Any]) -> None:
    binding = _binding_from_snapshot(case["binding"])
    expected = case["expected"]
    if expected.get("fieldAccessIsNull"):
        assert binding.field_access is None
    else:
        assert binding.field_access == expected["fieldAccess"]
    assert len(binding.denied_columns) == expected["deniedColumnsSize"]
    assert len(binding.system_slice) == expected["systemSliceSize"]


def _assert_compile_forwarding(case: dict[str, Any]) -> None:
    service = _CapturingSemanticService()
    binding = _binding_from_snapshot(case["binding"])
    composed = compile_plan_to_sql(
        _plan_from_snapshot(case["plan"]),
        _compose_context(),
        semantic_service=service,
        bindings={case["plan"]["model"]: binding},
        dialect="mysql8",
    )

    expected = case["expected"]
    for marker in expected.get("sqlMarkers", []):
        assert marker in composed.sql, f"[{case['id']}] SQL marker missing: {marker}"

    assert service.request is not None
    assert service.request.columns == expected["forwardedColumns"]
    assert service.request.field_access is not None
    assert service.request.field_access.visible == expected["forwardedFieldAccess"]
    assert _denied_columns_to_dicts(service.request.denied_columns) == expected[
        "forwardedDeniedColumns"
    ]
    assert service.request.system_slice == expected["forwardedSystemSlice"]


def _assert_compile_error(case: dict[str, Any]) -> None:
    expected = case["expected"]
    service = _CapturingSemanticService()
    with pytest.raises(ComposeCompileError) as exc_info:
        compile_plan_to_sql(
            _plan_from_snapshot(case["plan"]),
            _compose_context(),
            semantic_service=service,
            bindings={},
            dialect="mysql8",
        )

    assert exc_info.value.code == expected["errorCode"]
    assert exc_info.value.phase == expected["phase"]


def _assert_authority_resolution(case: dict[str, Any]) -> None:
    expected = case["expected"]
    service = _CapturingSemanticService()
    resolver_bindings = {
        model: _binding_from_snapshot(binding)
        for model, binding in case.get("resolverBindings", {}).items()
    }

    if expected["passes"]:
        composed = compile_plan_to_sql(
            _plan_from_snapshot(case["plan"]),
            _compose_context(_StaticResolver(resolver_bindings)),
            semantic_service=service,
            dialect="mysql8",
        )
        for marker in expected.get("sqlMarkers", []):
            assert marker in composed.sql, f"[{case['id']}] SQL marker missing: {marker}"
        assert service.model == expected["forwardedModel"]
        assert service.request is not None
        assert service.request.columns == expected["forwardedColumns"]
        assert service.request.field_access is not None
        assert service.request.field_access.visible == expected["forwardedFieldAccess"]
        return

    with pytest.raises(AuthorityResolutionError) as exc_info:
        compile_plan_to_sql(
            _plan_from_snapshot(case["plan"]),
            _compose_context(_StaticResolver(resolver_bindings)),
            semantic_service=service,
            dialect="mysql8",
        )

    assert exc_info.value.code == expected["errorCode"]
    assert exc_info.value.phase == expected["phase"]
    assert exc_info.value.model_involved == expected["modelInvolved"]


def _assert_denied_column_mapping(case: dict[str, Any]) -> None:
    service = _sales_service()
    mapping = service.get_physical_column_mapping(case["model"])
    assert mapping is not None
    actual = sorted(
        mapping.to_denied_qm_fields(
            _denied_columns_from_snapshot(case.get("deniedColumns"))
        )
    )
    assert actual == case["expected"]["deniedQmFields"]


def _assert_query_validation(case: dict[str, Any]) -> None:
    request = SemanticQueryRequest(
        columns=list(case.get("columns", [])),
        order_by=list(case.get("orderBy", [])),
        denied_columns=_denied_columns_from_snapshot(case.get("deniedColumns")),
    )
    _assert_semantic_query_validation(case, request)


def _assert_pivot_query_validation(case: dict[str, Any]) -> None:
    request = SemanticQueryRequest(
        **case["request"],
        denied_columns=_denied_columns_from_snapshot(case.get("deniedColumns")),
    )
    _assert_semantic_query_validation(case, request)


def _assert_domain_transport_query_validation(case: dict[str, Any]) -> None:
    request = SemanticQueryRequest(
        columns=list(case.get("columns", [])),
        order_by=list(case.get("orderBy", [])),
        denied_columns=_denied_columns_from_snapshot(case.get("deniedColumns")),
    )
    plan = case["domainTransportPlan"]
    request.domain_transport_plan = DomainTransportPlan(
        columns=tuple(plan["columns"]),
        tuples=tuple(tuple(row) for row in plan["tuples"]),
        threshold=int(plan["threshold"]),
    )
    _assert_semantic_query_validation(case, request)


def _assert_semantic_query_validation(
    case: dict[str, Any],
    request: SemanticQueryRequest,
) -> None:
    service = _sales_service()
    response = service.query_model(case["model"], request, mode="validate")

    expected = case["expected"]
    if expected["passes"]:
        assert response.error is None, response.error
        return

    assert response.error is not None
    for marker in expected.get("messageMarkers", []):
        assert marker in response.error


def _assert_metadata_trimming(case: dict[str, Any]) -> None:
    service = _sales_service()
    metadata = service.get_metadata_v3(
        model_names=[case["model"]],
        visible_fields=case.get("visibleFields"),
        denied_columns=_denied_columns_from_snapshot(case.get("deniedColumns")),
    )
    fields = metadata["fields"]

    expected = case["expected"]
    for field_name in expected.get("presentFields", []):
        assert field_name in fields, f"[{case['id']}] expected field to remain"
    for field_name in expected.get("absentFields", []):
        assert field_name not in fields, f"[{case['id']}] expected field to be trimmed"
