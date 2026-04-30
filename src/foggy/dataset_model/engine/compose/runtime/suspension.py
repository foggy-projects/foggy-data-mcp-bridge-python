"""v1.9 P2.1 — Script run state machine and suspension data models.

This module defines:

1. :class:`ScriptRunState` — the run lifecycle enum.
2. :data:`VALID_TRANSITIONS` — legal state transitions (fail-closed).
3. :class:`PauseRequest` / :class:`SuspensionResult` / :class:`ResumeCommand`
   / :class:`RejectCommand` — Pydantic v2 frozen models.
4. :class:`ScriptRunContext` — mutable per-run tracker with validated
   state transitions.

Design decisions:

* Models are Pydantic ``frozen=True`` BaseModels so they can be
  serialized to JSON without leaking host objects.
* ``ScriptRunContext`` is a plain dataclass (not Pydantic) because it
  carries mutable state (``state``, ``suspension``).
* ``generate_run_id`` / ``generate_suspend_id`` produce short prefixed
  hex strings. Full UUIDs are overkill for in-process, short-lived
  runs.
* ``TERMINAL_STATES`` is the set of states from which no further
  transition is allowed.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, FrozenSet, Optional

from pydantic import BaseModel, field_validator

from .suspend_errors import ScriptSuspendStateInvalidError

__all__ = [
    "MAX_TIMEOUT_MS",
    "PauseRequest",
    "RejectCommand",
    "ResumeCommand",
    "ScriptRunContext",
    "ScriptRunState",
    "SuspensionResult",
    "TERMINAL_STATES",
    "VALID_TRANSITIONS",
    "generate_run_id",
    "generate_suspend_id",
]


# ---------------------------------------------------------------------------
# System constants
# ---------------------------------------------------------------------------

#: System-level maximum timeout for any single pause (milliseconds).
#: Individual pause requests may specify a shorter timeout, but never
#: longer.  Default 5 minutes.
MAX_TIMEOUT_MS: int = 300_000


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class ScriptRunState(str, Enum):
    """Lifecycle states for a single FSScript run.

    Terminal states: ``REJECTED``, ``TIMED_OUT``,
    ``ABORTED``, ``COMPLETED``.  Once a run enters any terminal state
    no further transition is allowed.
    """

    RUNNING = "RUNNING"
    SUSPENDED = "SUSPENDED"
    REJECTED = "REJECTED"
    TIMED_OUT = "TIMED_OUT"
    ABORTED = "ABORTED"
    COMPLETED = "COMPLETED"


#: Legal transitions.  Any transition NOT listed here is illegal and
#: must be rejected fail-closed.
VALID_TRANSITIONS: Dict[ScriptRunState, FrozenSet[ScriptRunState]] = {
    ScriptRunState.RUNNING: frozenset({
        ScriptRunState.SUSPENDED,
        ScriptRunState.COMPLETED,
        ScriptRunState.ABORTED,
    }),
    ScriptRunState.SUSPENDED: frozenset({
        ScriptRunState.RUNNING,
        ScriptRunState.REJECTED,
        ScriptRunState.TIMED_OUT,
        ScriptRunState.ABORTED,
    }),
    # Terminal — no outgoing edges.
    ScriptRunState.REJECTED: frozenset(),
    ScriptRunState.TIMED_OUT: frozenset(),
    ScriptRunState.ABORTED: frozenset(),
    ScriptRunState.COMPLETED: frozenset(),
}

#: States from which no transition is allowed.
TERMINAL_STATES: FrozenSet[ScriptRunState] = frozenset({
    ScriptRunState.REJECTED,
    ScriptRunState.TIMED_OUT,
    ScriptRunState.ABORTED,
    ScriptRunState.COMPLETED,
})


# ---------------------------------------------------------------------------
# ID generators
# ---------------------------------------------------------------------------

def generate_run_id() -> str:
    """Return a prefixed run identifier, e.g. ``sr_a1b2c3d4e5f6``."""
    return f"sr_{uuid.uuid4().hex[:12]}"


def generate_suspend_id() -> str:
    """Return a prefixed suspend identifier, e.g. ``sp_a1b2c3d4e5f6``."""
    return f"sp_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Data models (Pydantic v2, frozen)
# ---------------------------------------------------------------------------

def _check_json_serializable(value: Any, field_name: str) -> None:
    """Raise ``ValueError`` if *value* is not JSON-serializable.

    Used by Pydantic validators to reject host objects, threads,
    connections, etc.
    """
    try:
        json.dumps(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            f"{field_name} must be JSON-serializable: {exc}"
        ) from None


class PauseRequest(BaseModel, frozen=True):
    """What a handler passes to the pause primitive.

    Attributes
    ----------
    reason:
        Stable string identifying the pause reason (e.g.
        ``"order.close.submit"``).
    summary:
        JSON-serializable dict for upstream display / routing.  Must not
        contain host objects, connections, DAOs, tokens, or passwords.
    timeout_ms:
        How long to wait for resume (positive int, ≤ MAX_TIMEOUT_MS).
    resume_schema:
        Optional JSON Schema describing the expected resume payload.
    audit_tag:
        Optional trace/audit tag.
    """

    reason: str
    summary: Dict[str, Any]
    timeout_ms: int
    resume_schema: Optional[Dict[str, Any]] = None
    audit_tag: Optional[str] = None

    @field_validator("reason")
    @classmethod
    def _reason_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("reason must be a non-empty string")
        return v

    @field_validator("timeout_ms")
    @classmethod
    def _timeout_positive_and_bounded(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("timeout_ms must be > 0")
        if v > MAX_TIMEOUT_MS:
            raise ValueError(
                f"timeout_ms must be ≤ {MAX_TIMEOUT_MS}, got {v}"
            )
        return v

    @field_validator("summary")
    @classmethod
    def _summary_serializable(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        _check_json_serializable(v, "summary")
        return v

    @field_validator("resume_schema")
    @classmethod
    def _resume_schema_serializable(
        cls, v: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        if v is not None:
            _check_json_serializable(v, "resume_schema")
        return v


class SuspensionResult(BaseModel, frozen=True):
    """What the engine returns / publishes when a run is suspended.

    No thread objects, handler references, host context, or call stacks.
    """

    type: str = "script_suspended"
    script_run_id: str
    suspend_id: str
    reason: str
    summary: Dict[str, Any]
    timeout_at: datetime


class ResumeCommand(BaseModel, frozen=True):
    """What upstream submits to resume a suspended run."""

    script_run_id: str
    suspend_id: str
    payload: Dict[str, Any]

    @field_validator("payload")
    @classmethod
    def _payload_serializable(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        _check_json_serializable(v, "payload")
        return v


class RejectCommand(BaseModel, frozen=True):
    """What upstream submits to reject (abort) a suspended run."""

    script_run_id: str
    suspend_id: str
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Mutable run context
# ---------------------------------------------------------------------------

@dataclass
class ScriptRunContext:
    """Per-run lifecycle tracker.

    Mutable: ``state`` and ``suspension`` are updated via
    :meth:`transition`.

    Attributes
    ----------
    run_id:
        Unique run identifier (``sr_…``).
    state:
        Current :class:`ScriptRunState`.
    suspension:
        Set when the run transitions to ``SUSPENDED``.
    created_at:
        UTC timestamp of context creation.
    """

    run_id: str = field(default_factory=generate_run_id)
    state: ScriptRunState = ScriptRunState.RUNNING
    suspension: Optional[SuspensionResult] = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # -- state transition ---------------------------------------------------

    def transition(self, new_state: ScriptRunState) -> None:
        """Move to *new_state* if the transition is legal.

        Raises
        ------
        ScriptSuspendStateInvalidError
            If the transition is not in :data:`VALID_TRANSITIONS`.
        """
        allowed = VALID_TRANSITIONS.get(self.state, frozenset())
        if new_state not in allowed:
            raise ScriptSuspendStateInvalidError(
                f"cannot transition from {self.state.value} to "
                f"{new_state.value}"
            )
        self.state = new_state

    @property
    def is_terminal(self) -> bool:
        """``True`` when the run is in a terminal state."""
        return self.state in TERMINAL_STATES
