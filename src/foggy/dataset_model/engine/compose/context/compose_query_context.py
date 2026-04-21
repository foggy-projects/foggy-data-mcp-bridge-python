"""ComposeQueryContext — the single server-side context object threaded
through every ``QueryPlan`` in a Compose Query script execution.

Corresponds to Java ``com.foggyframework.dataset.db.model.engine.compose.context.ComposeQueryContext``.

Critical invariant: the script host MUST NOT expose this object, ``principal``,
``authority_resolver``, or ``trace_id`` to the JavaScript sandbox. Only
``params`` is pierced through as a read-only map accessible via the script's
``params.xxx`` surface (see ``M9-三层沙箱防护测试脚手架.md`` A-08, A-10).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Mapping, Optional

from .principal import Principal

if TYPE_CHECKING:
    from ..security.authority_resolver import AuthorityResolver


def _freeze_mapping(m: Optional[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    """Wrap a mapping in an unmodifiable view. None stays None."""
    if m is None:
        return None
    # dict(m) makes a shallow snapshot; MappingProxyType makes it read-only.
    return MappingProxyType(dict(m))


@dataclass(frozen=True)
class ComposeQueryContext:
    """Immutable execution context for one Compose Query script invocation.

    Lifecycle: constructed by the MCP ``script`` tool entrypoint after the
    host resolves ``ToolExecutionContext`` (principal, namespace, resolver)
    and then threaded through every ``BaseModelPlan`` / ``DerivedQueryPlan``
    / ``UnionPlan`` / ``JoinPlan`` node.

    Fields
    ------
    principal:
        Required. Identity for this invocation; see :class:`Principal`.
    namespace:
        Required, non-blank. Used as ``X-NS`` on remote mode and as the
        ``namespace`` on ``AuthorityRequest``.
    authority_resolver:
        Required, non-null. The SPI implementation the resolution pipeline
        calls before exposing any ``BaseModelPlan`` schema.
    trace_id:
        Optional. Propagated to ``AuthorityRequest.trace_id`` and any
        downstream error payloads. No effect on resolution itself.
    params:
        Read-only map of host-injected business parameters. May be ``None``
        (equivalent to empty). The sandbox layer pierces *only* this field
        into the script globals (see ``M9`` A-10).
    extensions:
        Optional read-only map for forward-compat upstream-to-downstream
        passthrough. Not exposed to scripts.

    Notes
    -----
    ``authority_resolver`` is typed as ``Any`` at the dataclass level to
    avoid an import cycle with ``security.authority_resolver``; at
    type-check time it is ``AuthorityResolver``. A runtime duck-typing
    check in ``__post_init__`` confirms the ``.resolve`` method exists.
    """

    principal: Principal
    namespace: str
    authority_resolver: Any  # AuthorityResolver — see module docstring
    trace_id: Optional[str] = None
    params: Optional[Mapping[str, Any]] = None
    extensions: Optional[Mapping[str, str]] = None

    def __post_init__(self) -> None:
        if not isinstance(self.principal, Principal):
            raise TypeError(
                "ComposeQueryContext.principal must be a Principal instance"
            )

        if self.namespace is None or self.namespace == "":
            raise ValueError("ComposeQueryContext.namespace must be non-blank")

        if self.authority_resolver is None:
            raise ValueError(
                "ComposeQueryContext.authority_resolver is required; "
                "fail-closed means we never resolve with a null resolver"
            )

        # Duck-type check for Protocol compatibility without importing the
        # concrete Protocol (avoids circular import).
        if not hasattr(self.authority_resolver, "resolve") or not callable(
            getattr(self.authority_resolver, "resolve")
        ):
            raise TypeError(
                "ComposeQueryContext.authority_resolver must implement "
                "AuthorityResolver Protocol (callable .resolve method)"
            )

        # Snapshot + freeze the two map fields.
        object.__setattr__(self, "params", _freeze_mapping(self.params))
        object.__setattr__(self, "extensions", _freeze_mapping(self.extensions))

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def param(self, key: str, default: Any = None) -> Any:
        """Read a single host-injected param. Returns ``default`` when the
        key is absent or when ``params`` itself is ``None``.

        Used by ``SandboxRunner`` to back the script's ``params.xxx``
        surface; never exposes the underlying mapping.
        """
        if self.params is None:
            return default
        return self.params.get(key, default)
