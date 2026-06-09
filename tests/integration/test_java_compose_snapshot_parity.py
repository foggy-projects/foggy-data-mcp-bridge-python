"""Replay Java compose-query SQL snapshots when the export is available.

P0-3 intentionally keeps this lane optional until Java exports the neutral
snapshot file. Once ``tests/fixtures/java_compose_snapshot_parity.json`` is
present, these tests compile the JSON plan contract through Python and compare
the SQL/param/error markers captured by Java.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from foggy.dataset_model.engine.compose.compilation import compile_plan_to_sql
from foggy.dataset_model.engine.compose.context import ComposeQueryContext, Principal
from foggy.dataset_model.engine.compose.plan import QueryPlan, from_
from foggy.dataset_model.engine.compose.plan.plan import JoinOn
from foggy.dataset_model.engine.compose.security import (
    AuthorityRequest,
    AuthorityResolution,
    ModelBinding,
)
from foggy.dataset_model.semantic import SemanticQueryService
from foggy.demo.models.ecommerce_models import (
    create_fact_order_model,
    create_fact_payment_model,
    create_fact_sales_model,
)

SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_compose_snapshot_parity.json"
)


def _load_snapshot() -> dict[str, Any]:
    if not SNAPSHOT_PATH.exists():
        pytest.skip(
            "Java compose snapshot export not available yet: "
            f"{SNAPSHOT_PATH}. P0-3 keeps the replay harness optional until "
            "the Java worktree exports engine-neutral compose snapshots.",
        )
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


class _PermissiveResolver:
    def resolve(self, request: AuthorityRequest) -> AuthorityResolution:
        return AuthorityResolution(
            bindings={model_query.model: ModelBinding() for model_query in request.models}
        )


def _semantic_service() -> SemanticQueryService:
    service = SemanticQueryService()
    service.register_model(create_fact_sales_model())
    service.register_model(create_fact_order_model())
    service.register_model(create_fact_payment_model())
    return service


def _compose_context() -> ComposeQueryContext:
    return ComposeQueryContext(
        principal=Principal(user_id="snapshot-user", tenant_id="demo", roles=["analyst"]),
        namespace="demo",
        authority_resolver=_PermissiveResolver(),
    )


def _get_list(node: dict[str, Any], *names: str) -> list[Any] | None:
    for name in names:
        if name in node:
            value = node[name]
            return list(value) if value is not None else None
    return None


def _get_bool(node: dict[str, Any], *names: str, default: bool = False) -> bool:
    for name in names:
        if name in node:
            return bool(node[name])
    return default


def _get_int(node: dict[str, Any], *names: str) -> int | None:
    for name in names:
        if name in node:
            value = node[name]
            return int(value) if value is not None else None
    return None


def _plan_from_snapshot(node: dict[str, Any]) -> QueryPlan:
    node_type = node.get("type")

    if node_type == "base":
        return _bind_aliases(
            from_(
                model=node["model"],
                columns=list(node["columns"]),
                slice=_get_list(node, "slice"),
                having=_get_list(node, "having"),
                group_by=_get_list(node, "groupBy", "group_by"),
                order_by=_get_list(node, "orderBy", "order_by"),
                calculated_fields=_get_list(node, "calculatedFields", "calculated_fields"),
                limit=_get_int(node, "limit"),
                start=_get_int(node, "start"),
                distinct=_get_bool(node, "distinct"),
            ),
            node,
        )

    if node_type == "derived":
        source = _plan_from_snapshot(node["source"])
        return _bind_aliases(
            source.query(
                columns=list(node["columns"]),
                slice=_get_list(node, "slice"),
                group_by=_get_list(node, "groupBy", "group_by"),
                order_by=_get_list(node, "orderBy", "order_by"),
                limit=_get_int(node, "limit"),
                start=_get_int(node, "start"),
                distinct=_get_bool(node, "distinct"),
            ),
            node,
        )

    if node_type == "union":
        return _bind_aliases(
            _plan_from_snapshot(node["left"]).union(
                _plan_from_snapshot(node["right"]),
                all=_get_bool(node, "all", "unionAll"),
            ),
            node,
        )

    if node_type == "join":
        join_type = node.get("joinType", node.get("typeName", "left"))
        on = [
            JoinOn(left=item["left"], op=item.get("op", "="), right=item["right"])
            for item in node.get("on", [])
        ]
        return _bind_aliases(
            _plan_from_snapshot(node["left"]).join(
                _plan_from_snapshot(node["right"]),
                type=join_type,
                on=on,
            ),
            node,
        )

    raise AssertionError(f"Unsupported compose snapshot plan type: {node_type!r}")


def _bind_aliases(plan: QueryPlan, node: dict[str, Any]) -> QueryPlan:
    for alias in node.get("aliases", []):
        plan.__fsscript_bind_alias__(alias)
    return plan


def test_snapshot_schema() -> None:
    snapshot = _load_snapshot()
    assert snapshot["schemaVersion"] == 1
    assert snapshot["feature"] == "composeQuery"
    assert snapshot["source"]
    assert snapshot.get("cases")


def test_java_compose_snapshot_replays_in_python() -> None:
    snapshot = _load_snapshot()
    for case in snapshot.get("cases", []):
        _assert_case_replays(case)


def _assert_case_replays(case: dict[str, Any]) -> None:
    expected = case.get("expected", {})
    dialect = case.get("dialect", "mysql8")

    expected_error = expected.get("errorCode")
    if expected_error:
        with pytest.raises(Exception) as exc_info:  # noqa: BLE001
            plan = _plan_from_snapshot(case["plan"])
            compile_plan_to_sql(
                plan,
                _compose_context(),
                semantic_service=_semantic_service(),
                dialect=dialect,
            )
        assert expected_error in str(exc_info.value)
        return

    plan = _plan_from_snapshot(case["plan"])
    composed = compile_plan_to_sql(
        plan,
        _compose_context(),
        semantic_service=_semantic_service(),
        dialect=dialect,
    )

    sql = composed.sql
    for marker in expected.get("sqlMarkers", []):
        assert marker in sql, f"[{case['id']}] SQL marker missing: {marker}"
    for marker in expected.get("forbiddenSqlMarkers", []):
        assert marker not in sql, f"[{case['id']}] forbidden SQL marker present: {marker}"
    if "params" in expected:
        assert list(composed.params) == list(expected["params"])
