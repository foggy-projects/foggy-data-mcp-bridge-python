"""Tests for ``to_compose_context`` — MCP → compose context bridge."""

from __future__ import annotations

from typing import Any

import pytest

from foggy.dataset_model.engine.compose.context.compose_query_context import (
    ComposeQueryContext,
)
from foggy.dataset_model.engine.compose.context.principal import Principal
from foggy.dataset_model.engine.compose.runtime.context_bridge import (
    STATE_NAMESPACE,
    STATE_PRINCIPAL,
    STATE_TRACE_ID,
    to_compose_context,
)
from foggy.mcp_spi.context import ToolExecutionContext


class _DuckResolver:
    """Minimal AuthorityResolver duck — exposes .resolve callable."""

    def resolve(self, request: Any):  # pragma: no cover - not invoked in bridge tests
        return None


def _tool_ctx(**kwargs) -> ToolExecutionContext:
    """Build ToolExecutionContext with safe defaults."""
    kwargs.setdefault("request_id", "req-1")
    return ToolExecutionContext(**kwargs)


# ---------------------------------------------------------------------------
# Embedded-mode path
# ---------------------------------------------------------------------------


def test_embedded_principal_and_namespace_wins_over_headers():
    tc = _tool_ctx(
        state={
            STATE_PRINCIPAL: Principal(user_id="embed-user", roles=("admin",)),
            STATE_NAMESPACE: "embed-ns",
        },
        headers={
            "X-User-Id": "header-user",
            "X-Namespace": "header-ns",
        },
    )
    resolver = _DuckResolver()

    ctx = to_compose_context(tc, authority_resolver=resolver)

    assert isinstance(ctx, ComposeQueryContext)
    assert ctx.principal.user_id == "embed-user"
    assert ctx.principal.roles == ("admin",)
    assert ctx.namespace == "embed-ns"
    assert ctx.authority_resolver is resolver


def test_embedded_principal_must_be_principal_instance():
    tc = _tool_ctx(state={STATE_PRINCIPAL: "not-a-principal"})
    with pytest.raises(TypeError) as exc:
        to_compose_context(tc, authority_resolver=_DuckResolver())
    assert "Principal instance" in str(exc.value)


# ---------------------------------------------------------------------------
# Header-mode path
# ---------------------------------------------------------------------------


def test_header_mode_builds_full_principal():
    tc = _tool_ctx(
        headers={
            "Authorization": "Bearer xyz",
            "X-User-Id": "u1",
            "X-Tenant-Id": "t1",
            "X-Roles": "admin,reader, writer",
            "X-Dept-Id": "d1",
            "X-Policy-Snapshot-Id": "snap-42",
            "X-Namespace": "sales",
            "X-Trace-Id": "tr-1",
        },
    )

    ctx = to_compose_context(tc, authority_resolver=_DuckResolver())

    p = ctx.principal
    assert p.user_id == "u1"
    assert p.tenant_id == "t1"
    assert p.roles == ("admin", "reader", "writer")
    assert p.dept_id == "d1"
    assert p.authorization_hint == "Bearer xyz"
    assert p.policy_snapshot_id == "snap-42"
    assert ctx.namespace == "sales"
    assert ctx.trace_id == "tr-1"


def test_header_mode_missing_user_id_raises():
    tc = _tool_ctx(headers={"X-Namespace": "sales"})
    with pytest.raises(ValueError) as exc:
        to_compose_context(tc, authority_resolver=_DuckResolver())
    assert "principal identity" in str(exc.value)


def test_header_mode_falls_back_to_tool_ctx_user_id():
    tc = _tool_ctx(user_id="fallback-u", namespace="sales")
    ctx = to_compose_context(tc, authority_resolver=_DuckResolver())
    assert ctx.principal.user_id == "fallback-u"
    assert ctx.namespace == "sales"


def test_roles_header_empty_parts_are_stripped():
    tc = _tool_ctx(
        headers={
            "X-User-Id": "u1",
            "X-Roles": " ,admin,,reader, ",
            "X-Namespace": "ns",
        },
    )
    ctx = to_compose_context(tc, authority_resolver=_DuckResolver())
    assert ctx.principal.roles == ("admin", "reader")


def test_no_roles_header_means_empty_tuple():
    tc = _tool_ctx(
        headers={"X-User-Id": "u1", "X-Namespace": "ns"},
    )
    ctx = to_compose_context(tc, authority_resolver=_DuckResolver())
    assert ctx.principal.roles == ()


# ---------------------------------------------------------------------------
# Namespace resolution priority
# ---------------------------------------------------------------------------


def test_namespace_priority_state_over_tool_ctx_over_header():
    tc = _tool_ctx(
        namespace="tool-ctx-ns",
        state={STATE_NAMESPACE: "state-ns"},
        headers={"X-User-Id": "u1", "X-Namespace": "header-ns"},
    )
    ctx = to_compose_context(tc, authority_resolver=_DuckResolver())
    assert ctx.namespace == "state-ns"


def test_namespace_priority_tool_ctx_over_header():
    tc = _tool_ctx(
        namespace="tool-ctx-ns",
        headers={"X-User-Id": "u1", "X-Namespace": "header-ns"},
    )
    ctx = to_compose_context(tc, authority_resolver=_DuckResolver())
    assert ctx.namespace == "tool-ctx-ns"


def test_namespace_from_header_when_ctx_missing():
    tc = _tool_ctx(
        headers={"X-User-Id": "u1", "X-Namespace": "header-ns"},
    )
    ctx = to_compose_context(tc, authority_resolver=_DuckResolver())
    assert ctx.namespace == "header-ns"


def test_namespace_missing_everywhere_raises():
    tc = _tool_ctx(headers={"X-User-Id": "u1"})
    with pytest.raises(ValueError) as exc:
        to_compose_context(tc, authority_resolver=_DuckResolver())
    assert "namespace" in str(exc.value)


# ---------------------------------------------------------------------------
# Trace id + extensions passthrough
# ---------------------------------------------------------------------------


def test_trace_id_state_takes_precedence_over_header():
    tc = _tool_ctx(
        state={STATE_TRACE_ID: "state-trace"},
        headers={"X-User-Id": "u1", "X-Namespace": "ns", "X-Trace-Id": "hdr-trace"},
    )
    ctx = to_compose_context(tc, authority_resolver=_DuckResolver())
    assert ctx.trace_id == "state-trace"


def test_trace_id_missing_is_none():
    tc = _tool_ctx(headers={"X-User-Id": "u1", "X-Namespace": "ns"})
    ctx = to_compose_context(tc, authority_resolver=_DuckResolver())
    assert ctx.trace_id is None


def test_extensions_passed_through():
    tc = _tool_ctx(headers={"X-User-Id": "u1", "X-Namespace": "ns"})
    ctx = to_compose_context(
        tc,
        authority_resolver=_DuckResolver(),
        extensions={"flag": "true"},
    )
    assert ctx.extensions is not None
    assert ctx.extensions["flag"] == "true"


# ---------------------------------------------------------------------------
# Fail-closed guards
# ---------------------------------------------------------------------------


def test_null_tool_ctx_raises():
    with pytest.raises(ValueError):
        to_compose_context(None, authority_resolver=_DuckResolver())


def test_null_resolver_raises():
    tc = _tool_ctx(headers={"X-User-Id": "u1", "X-Namespace": "ns"})
    with pytest.raises(ValueError) as exc:
        to_compose_context(tc, authority_resolver=None)
    assert "authority_resolver is required" in str(exc.value)


def test_resolver_without_resolve_method_raises_typeerror():
    """Forwarded through ComposeQueryContext.__post_init__."""
    tc = _tool_ctx(headers={"X-User-Id": "u1", "X-Namespace": "ns"})

    class _NotAResolver:
        pass

    with pytest.raises(TypeError):
        to_compose_context(tc, authority_resolver=_NotAResolver())
