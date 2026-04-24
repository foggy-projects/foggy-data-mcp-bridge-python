"""Tests for ``QueryPlan.execute`` / ``.to_sql`` wiring and
``execute_plan`` / ``pick_route_model``."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any, Dict, List, Optional

import pytest

from foggy.dataset_model.engine.compose import ComposedSql
from foggy.dataset_model.engine.compose.authority.resolver import (
    AuthorityResolutionError,
)
from foggy.dataset_model.engine.compose.compilation.errors import (
    ComposeCompileError,
)
from foggy.dataset_model.engine.compose.compilation import error_codes as cc_codes
from foggy.dataset_model.engine.compose.context.compose_query_context import (
    ComposeQueryContext,
)
from foggy.dataset_model.engine.compose.context.principal import Principal
from foggy.dataset_model.engine.compose.plan import (
    BaseModelPlan,
    DerivedQueryPlan,
    JoinPlan,
    UnionPlan,
    from_,
)
from foggy.dataset_model.engine.compose.plan.plan import JoinOn
from foggy.dataset_model.engine.compose.runtime import (
    ComposeRuntimeBundle,
    current_bundle,
    execute_plan,
    pick_route_model,
    set_bundle,
)
from foggy.dataset_model.engine.compose.runtime.script_runtime import (
    _compose_runtime,
)
from foggy.dataset_model.engine.compose.security import AuthorityResolution, ModelBinding
from foggy.dataset_model.engine.compose.security.authority_resolver import (
    AuthorityResolver,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _StubResolver:
    """Returns ``ModelBinding(None, [], [])`` for every requested model."""

    def resolve(self, request):
        bindings = {
            mq.model: ModelBinding(field_access=None, denied_columns=[], system_slice=[])
            for mq in request.models
        }
        return AuthorityResolution(bindings=bindings)


class _StubSemanticService:
    """Captures compile / execute interactions without touching SQL generation."""

    def __init__(self,
                 composed: Optional[ComposedSql] = None,
                 rows: Optional[List[Dict[str, Any]]] = None,
                 raise_on_execute: Optional[BaseException] = None):
        self._composed = composed or ComposedSql(sql="SELECT 1", params=[])
        self._rows = rows if rows is not None else [{"id": 1}]
        self._raise_on_execute = raise_on_execute
        self.execute_calls: List[tuple] = []

    # Matches the kw-only signature compile_plan_to_sql expects — but
    # we monkeypatch compile_plan_to_sql directly in these tests rather
    # than mocking out the semantic service compile path.

    def execute_sql(self, sql, params, *, route_model=None):
        self.execute_calls.append((sql, list(params), route_model))
        if self._raise_on_execute is not None:
            raise self._raise_on_execute
        return list(self._rows)


def _make_ctx(resolver=None) -> ComposeQueryContext:
    resolver = resolver or _StubResolver()
    return ComposeQueryContext(
        principal=Principal(user_id="u1"),
        namespace="default",
        authority_resolver=resolver,
    )


# ---------------------------------------------------------------------------
# pick_route_model
# ---------------------------------------------------------------------------


def test_pick_route_model_for_base():
    p = BaseModelPlan(model="Sales", columns=("id",))
    assert pick_route_model(p) == "Sales"


def test_pick_route_model_for_derived():
    p = from_(model="Sales", columns=["id"]).query(columns=["id"])
    assert pick_route_model(p) == "Sales"


def test_pick_route_model_for_union_left_preorder():
    left = from_(model="L", columns=["id"])
    right = from_(model="R", columns=["id"])
    p = left.union(right)
    assert pick_route_model(p) == "L"


def test_pick_route_model_for_join_left_preorder():
    left = from_(model="L", columns=["id"])
    right = from_(model="R", columns=["id"])
    p = left.join(right, type="left", on=[JoinOn(left="id", op="=", right="id")])
    assert pick_route_model(p) == "L"


def test_pick_route_model_none_plan_returns_none():
    assert pick_route_model(None) is None


# ---------------------------------------------------------------------------
# ComposeRuntimeBundle: frozen, ContextVar behaviour
# ---------------------------------------------------------------------------


def test_compose_runtime_bundle_is_frozen():
    ctx = _make_ctx()
    svc = _StubSemanticService()
    bundle = ComposeRuntimeBundle(ctx=ctx, semantic_service=svc)
    with pytest.raises(FrozenInstanceError):
        bundle.dialect = "postgres"  # type: ignore[misc]


def test_current_bundle_returns_none_outside_run_script():
    assert current_bundle() is None


def test_set_bundle_and_reset_token_isolates():
    svc = _StubSemanticService()
    ctx = _make_ctx()
    bundle = ComposeRuntimeBundle(ctx=ctx, semantic_service=svc)
    token = set_bundle(bundle)
    try:
        assert current_bundle() is bundle
    finally:
        _compose_runtime.reset(token)
    assert current_bundle() is None


# ---------------------------------------------------------------------------
# QueryPlan.execute / .to_sql — bundle-required behaviour
# ---------------------------------------------------------------------------


def test_execute_without_bundle_raises_runtimeerror():
    p = from_(model="M", columns=["id"])
    with pytest.raises(RuntimeError) as exc:
        p.execute()
    assert "ComposeRuntimeBundle" in str(exc.value)


def test_execute_with_explicit_ctx_still_requires_bundle():
    """execute() needs semantic_service even when ctx is passed."""
    p = from_(model="M", columns=["id"])
    ctx = _make_ctx()
    with pytest.raises(RuntimeError):
        p.execute(ctx)


def test_to_sql_without_bundle_or_ctx_raises():
    p = from_(model="M", columns=["id"])
    with pytest.raises(RuntimeError) as exc:
        p.to_sql()
    assert (
        "explicit context" in str(exc.value)
        or "ComposeRuntimeBundle" in str(exc.value)
    )


def test_to_sql_with_bundle_returns_composed_sql(monkeypatch):
    """When bundle is set and compile succeeds, to_sql returns ComposedSql."""
    captured: Dict[str, Any] = {}

    def fake_compile(plan, ctx, *, semantic_service, bindings=None,
                    model_info_provider=None, dialect="mysql"):
        captured["called"] = True
        captured["dialect"] = dialect
        return ComposedSql(sql=f"-- dialect={dialect}\nSELECT 1", params=[])

    # Patch the compiler that QueryPlan.to_sql ultimately imports
    monkeypatch.setattr(
        "foggy.dataset_model.engine.compose.compilation.compiler.compile_plan_to_sql",
        fake_compile,
    )

    svc = _StubSemanticService()
    ctx = _make_ctx()
    bundle = ComposeRuntimeBundle(ctx=ctx, semantic_service=svc, dialect="mysql")
    token = set_bundle(bundle)
    try:
        p = from_(model="M", columns=["id"])
        result = p.to_sql()
    finally:
        _compose_runtime.reset(token)

    assert isinstance(result, ComposedSql)
    assert captured["called"] is True
    assert captured["dialect"] == "mysql"


def test_to_sql_dialect_override_wins_over_bundle(monkeypatch):
    captured: Dict[str, Any] = {}

    def fake_compile(plan, ctx, *, semantic_service, bindings=None,
                    model_info_provider=None, dialect="mysql"):
        captured["dialect"] = dialect
        return ComposedSql(sql="SELECT 1", params=[])

    monkeypatch.setattr(
        "foggy.dataset_model.engine.compose.compilation.compiler.compile_plan_to_sql",
        fake_compile,
    )
    svc = _StubSemanticService()
    ctx = _make_ctx()
    bundle = ComposeRuntimeBundle(ctx=ctx, semantic_service=svc, dialect="mysql")
    token = set_bundle(bundle)
    try:
        from_(model="M", columns=["id"]).to_sql(dialect="postgres")
    finally:
        _compose_runtime.reset(token)

    assert captured["dialect"] == "postgres"


# ---------------------------------------------------------------------------
# execute_plan: compile-then-execute; error routing
# ---------------------------------------------------------------------------


def test_execute_plan_happy_path(monkeypatch):
    def fake_compile(plan, ctx, *, semantic_service, bindings=None,
                    model_info_provider=None, dialect="mysql"):
        return ComposedSql(sql="SELECT id FROM m", params=[])

    monkeypatch.setattr(
        "foggy.dataset_model.engine.compose.runtime.plan_execution.compile_plan_to_sql",
        fake_compile,
    )

    svc = _StubSemanticService(rows=[{"id": 1}, {"id": 2}])
    ctx = _make_ctx()
    plan = from_(model="M", columns=["id"])

    rows = execute_plan(plan, ctx, semantic_service=svc)

    assert rows == [{"id": 1}, {"id": 2}]
    # route_model threaded through
    assert svc.execute_calls == [("SELECT id FROM m", [], "M")]


def test_execute_plan_compile_error_propagates(monkeypatch):
    def raising_compile(plan, ctx, *, semantic_service, bindings=None,
                        model_info_provider=None, dialect="mysql"):
        raise ComposeCompileError(
            code=cc_codes.MISSING_BINDING,
            message="no binding for M",
            phase="compile",
        )

    monkeypatch.setattr(
        "foggy.dataset_model.engine.compose.runtime.plan_execution.compile_plan_to_sql",
        raising_compile,
    )

    svc = _StubSemanticService()
    ctx = _make_ctx()
    plan = from_(model="M", columns=["id"])

    # ComposeCompileError propagates verbatim, NOT wrapped in RuntimeError
    with pytest.raises(ComposeCompileError) as exc:
        execute_plan(plan, ctx, semantic_service=svc)
    assert exc.value.code == cc_codes.MISSING_BINDING


def test_execute_plan_execute_sql_error_wraps_to_runtimeerror(monkeypatch):
    def fake_compile(plan, ctx, *, semantic_service, bindings=None,
                    model_info_provider=None, dialect="mysql"):
        return ComposedSql(sql="SELECT 1", params=[])

    monkeypatch.setattr(
        "foggy.dataset_model.engine.compose.runtime.plan_execution.compile_plan_to_sql",
        fake_compile,
    )

    db_err = RuntimeError("db connection lost")
    svc = _StubSemanticService(raise_on_execute=db_err)
    ctx = _make_ctx()
    plan = from_(model="M", columns=["id"])

    with pytest.raises(RuntimeError) as exc_info:
        execute_plan(plan, ctx, semantic_service=svc)
    assert "Plan execution failed at execute phase" in str(exc_info.value)
    assert exc_info.value.__cause__ is db_err


# ---------------------------------------------------------------------------
# Nested set_bundle isolation
# ---------------------------------------------------------------------------


def test_nested_bundle_restores_parent():
    svc1 = _StubSemanticService()
    svc2 = _StubSemanticService()
    ctx = _make_ctx()
    outer = ComposeRuntimeBundle(ctx=ctx, semantic_service=svc1, dialect="mysql")
    inner = ComposeRuntimeBundle(ctx=ctx, semantic_service=svc2, dialect="postgres")

    outer_tok = set_bundle(outer)
    try:
        assert current_bundle().dialect == "mysql"
        inner_tok = set_bundle(inner)
        try:
            assert current_bundle().dialect == "postgres"
        finally:
            _compose_runtime.reset(inner_tok)
        assert current_bundle().dialect == "mysql"
    finally:
        _compose_runtime.reset(outer_tok)
    assert current_bundle() is None
