"""``ToolExecutionContext → ComposeQueryContext`` bridge.

The MCP layer hands compose tools a :class:`ToolExecutionContext` (headers,
state, namespace). The engine layer demands a :class:`ComposeQueryContext`
(principal, namespace, authority resolver). This module is the boundary.

Resolution priority (mirrors M7 execution prompt §7.1):

1. **Embedded mode** — if the host set
   ``tool_ctx.state["compose.principal"] = Principal(...)`` (and optionally
   ``state["compose.namespace"]``), we use that directly. This lets an
   embedded host (e.g. Odoo Pro) push an already-authenticated principal
   without round-tripping through HTTP headers.
2. **Header mode** — fall back to parsing ``X-User-Id`` / ``Authorization``
   / ``X-Tenant-Id`` / ``X-Roles`` / ``X-Dept-Id`` / ``X-Policy-Snapshot-Id``
   / ``X-Trace-Id`` / ``X-Namespace``.

Fail-closed: if neither branch produces a non-empty ``user_id`` or a non-
empty ``namespace``, we raise :class:`ValueError`. Sandbox layer M9 will
decide later whether anonymous access is ever permitted; M7 does not
relax this.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from foggy.mcp_spi.context import ToolExecutionContext

from ..context.compose_query_context import ComposeQueryContext
from ..context.principal import Principal


__all__ = ["to_compose_context"]


# State keys the embedded host can use to push values without HTTP round-trip.
STATE_PRINCIPAL = "compose.principal"
STATE_NAMESPACE = "compose.namespace"
STATE_TRACE_ID = "compose.trace_id"


def _parse_roles(raw: Optional[str]) -> tuple:
    if not raw:
        return ()
    return tuple(
        piece.strip() for piece in raw.split(",") if piece.strip()
    )


def _build_principal_from_headers(tool_ctx: ToolExecutionContext) -> Principal:
    user_id = tool_ctx.get_header("X-User-Id") or tool_ctx.user_id
    if not user_id:
        raise ValueError(
            "ToolExecutionContext missing principal identity: "
            "neither state['compose.principal'] nor X-User-Id / user_id are "
            "set. Compose script requires a non-empty user identity."
        )
    tenant_id = tool_ctx.get_header("X-Tenant-Id")
    roles = _parse_roles(tool_ctx.get_header("X-Roles"))
    dept_id = tool_ctx.get_header("X-Dept-Id")
    authorization = tool_ctx.get_header("Authorization")
    snapshot = tool_ctx.get_header("X-Policy-Snapshot-Id")
    return Principal(
        user_id=user_id,
        tenant_id=tenant_id,
        roles=roles,
        dept_id=dept_id,
        authorization_hint=authorization,
        policy_snapshot_id=snapshot,
    )


def _resolve_namespace(tool_ctx: ToolExecutionContext) -> str:
    """Pick namespace with priority:

    1. ``state["compose.namespace"]`` — embedded override
    2. ``tool_ctx.namespace`` — set by MCP dispatcher
    3. ``X-Namespace`` header

    Raises ValueError if none present / all empty.
    """
    ns = tool_ctx.get_state(STATE_NAMESPACE)
    if ns:
        return ns
    if tool_ctx.namespace:
        return tool_ctx.namespace
    header_ns = tool_ctx.get_header("X-Namespace")
    if header_ns:
        return header_ns
    raise ValueError(
        "ToolExecutionContext missing namespace: neither "
        "state['compose.namespace'] nor tool_ctx.namespace nor X-Namespace "
        "header supplied a non-empty value."
    )


def _resolve_trace_id(tool_ctx: ToolExecutionContext) -> Optional[str]:
    trace = tool_ctx.get_state(STATE_TRACE_ID)
    if trace:
        return trace
    return tool_ctx.get_header("X-Trace-Id")


def to_compose_context(
    tool_ctx: ToolExecutionContext,
    *,
    authority_resolver: Any,
    extensions: Optional[Dict[str, str]] = None,
) -> ComposeQueryContext:
    """Translate an MCP :class:`ToolExecutionContext` into a
    :class:`ComposeQueryContext` ready for the compose engine.

    Parameters
    ----------
    tool_ctx:
        MCP tool execution context.
    authority_resolver:
        The :class:`AuthorityResolver` implementation (embedded or remote)
        that M5 should consult. Required; ``None`` raises.
    extensions:
        Optional upstream → downstream passthrough map. ``None`` stays
        ``None`` (matches :class:`ComposeQueryContext`'s ``extensions``
        forward-compat contract).

    Returns
    -------
    ComposeQueryContext
        Fully validated compose context.

    Raises
    ------
    ValueError
        When principal identity or namespace cannot be resolved from either
        embedded state or headers.
    TypeError
        When ``authority_resolver`` does not implement the
        ``.resolve(request)`` Protocol — delegated to
        :class:`ComposeQueryContext`'s own ``__post_init__`` check.
    """
    if tool_ctx is None:
        raise ValueError("to_compose_context: tool_ctx is required")
    if authority_resolver is None:
        raise ValueError(
            "to_compose_context: authority_resolver is required; "
            "fail-closed means we never construct a context with a null resolver"
        )

    embedded_principal = tool_ctx.get_state(STATE_PRINCIPAL)
    if isinstance(embedded_principal, Principal):
        principal = embedded_principal
    elif embedded_principal is not None:
        raise TypeError(
            "state['compose.principal'] must be a Principal instance "
            f"when set; got {type(embedded_principal).__name__}"
        )
    else:
        principal = _build_principal_from_headers(tool_ctx)

    namespace = _resolve_namespace(tool_ctx)
    trace_id = _resolve_trace_id(tool_ctx)

    return ComposeQueryContext(
        principal=principal,
        namespace=namespace,
        authority_resolver=authority_resolver,
        trace_id=trace_id,
        params=None,
        extensions=extensions,
    )
