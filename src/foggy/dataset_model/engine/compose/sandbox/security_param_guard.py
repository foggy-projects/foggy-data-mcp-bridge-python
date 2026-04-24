"""Layer A — runtime parameter guard.

Ensures scripts do not attempt to bypass host-level security by manually
injecting security parameters (authorization, systemSlice, etc.) into the DSL.
"""

from __future__ import annotations

from typing import Any

from .error_codes import LAYER_A_SECURITY_PARAM
from .exceptions import ComposeSandboxViolationError

# Security parameters that are strictly controlled by the host
# and must never be provided by the script itself.
_FORBIDDEN_PARAMS: frozenset = frozenset(
    {
        "authorization",
        "userId",
        "tenantId",
        "roles",
        "deniedColumns",
        "systemSlice",
        "fieldAccess",
        "policySnapshotId",
    }
)


def validate(args: dict[str, Any], phase: str) -> None:
    """Validate DSL arguments to ensure no security parameters are injected.

    Parameters
    ----------
    args : dict[str, Any]
        The arguments dictionary passed to from() / dsl().
    phase : str
        Pipeline phase for error reporting.

    Raises
    ------
    ComposeSandboxViolationError
        If a forbidden security parameter is found in the arguments.
    """
    if not args:
        return

    for key in args:
        if key in _FORBIDDEN_PARAMS:
            raise ComposeSandboxViolationError(
                LAYER_A_SECURITY_PARAM,
                f"Security parameter '{key}' cannot be provided by the script.",
                phase,
            )
