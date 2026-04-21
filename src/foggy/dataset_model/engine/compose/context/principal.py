"""Principal — identity information for a Compose Query execution.

Corresponds to Java ``com.foggyframework.dataset.db.model.engine.compose.context.Principal``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Principal:
    """Immutable identity descriptor for a single Compose Query invocation.

    Frozen dataclass chosen (not Protocol) because ``Principal`` carries state
    and must be value-equal across requests for cache-key purposes. ``roles``
    is exposed as a tuple internally to preserve hashability while keeping
    list-like iteration for callers.

    Fields
    ------
    user_id:
        Required; non-empty. The upstream user identity for this invocation.
    tenant_id:
        Optional tenant/organisation identifier.
    roles:
        Non-null (may be empty). Role names granted to this principal. Stored
        as a tuple internally but accepts any iterable on construction.
    dept_id:
        Optional department identifier.
    authorization_hint:
        Optional. Used only by remote-mode ``HttpAuthorityResolver`` to
        serialise the ``Authorization`` header. Embedded-mode resolvers
        ignore this field.
    policy_snapshot_id:
        Optional. Tracing/audit token; has no effect on resolution in the
        first version.

    Notes
    -----
    Frozen: any attempt at attribute mutation raises ``FrozenInstanceError``.
    This is intentional — ``Principal`` instances are passed between the
    script host, SPI, and resolver; mutation would lead to TOCTOU class bugs.
    """

    user_id: str
    tenant_id: Optional[str] = None
    roles: Tuple[str, ...] = field(default_factory=tuple)
    dept_id: Optional[str] = None
    authorization_hint: Optional[str] = None
    policy_snapshot_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.user_id is None or self.user_id == "":
            raise ValueError("Principal.user_id must be non-empty")

        # Accept any iterable for roles but store as tuple for hashability.
        if not isinstance(self.roles, tuple):
            object.__setattr__(self, "roles", tuple(self.roles))

        # roles must contain only str values
        for r in self.roles:
            if not isinstance(r, str):
                raise TypeError(
                    f"Principal.roles entries must be str, got {type(r).__name__}"
                )

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def roles_list(self) -> List[str]:
        """Return roles as a fresh list (for callers that mutate their copy)."""
        return list(self.roles)
