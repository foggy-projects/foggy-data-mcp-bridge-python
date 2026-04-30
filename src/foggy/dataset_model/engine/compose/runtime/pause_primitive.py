"""v1.9 P2.2 — Pause primitive and run-context propagation.

Provides :func:`compose_pause`, the handler-callable pause API, and
:func:`current_run_context` / :func:`set_run_context`, the ContextVar
accessors that carry :class:`ScriptRunContext` through the evaluator
call stack.

Design decisions
~~~~~~~~~~~~~~~~
* A new ContextVar ``_script_run_context`` parallels the existing
  ``_compose_runtime`` ContextVar.  ``run_script`` pushes context at
  entry and resets in ``finally``.
* ``compose_pause`` blocks the calling thread with
  ``threading.Event.wait(timeout_seconds)`` — this works for both
  pure_runtime handlers (same thread as evaluator) and facade method
  handlers (child thread inside ``_MethodDispatcher``), provided the
  child thread receives the ContextVar value (see ``facade_proxy``
  changes).
* ``SuspensionManager`` is extended with an ``_events`` dict keyed by
  ``suspend_id``; ``resume`` / ``reject`` / ``timeout`` set the event
  after state transition so the blocked thread wakes up.
* A ``threading.Timer`` auto-fires timeout; it is cancelled on resume
  or reject.
* ``compose_pause`` returns the resume payload on success, or raises
  ``ScriptSuspendRejectedError`` / ``ScriptSuspendTimeoutError``.

Thread safety
~~~~~~~~~~~~~
``compose_pause`` is meant to be called from the handler's execution
thread.  The ``Event.wait()`` blocks that thread.  Resume / reject /
timeout may arrive from any thread.  All shared state goes through
``SuspensionManager._lock``.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Dict, Optional

from .suspend_errors import ScriptPauseNotInRunError
from .suspension import PauseRequest, ScriptRunContext

__all__ = [
    "compose_pause",
    "current_run_context",
    "set_run_context",
]


# ---------------------------------------------------------------------------
# ContextVar for ScriptRunContext
# ---------------------------------------------------------------------------

_script_run_context: ContextVar[Optional[ScriptRunContext]] = ContextVar(
    "_script_run_context", default=None,
)


def current_run_context() -> Optional[ScriptRunContext]:
    """Return the active :class:`ScriptRunContext`, or ``None`` outside
    a script run."""
    return _script_run_context.get()


def set_run_context(run_ctx: Optional[ScriptRunContext]):
    """Install *run_ctx* on the ContextVar and return the reset token.

    Callers MUST use ``try/finally`` to reset the token.
    """
    return _script_run_context.set(run_ctx)


# ---------------------------------------------------------------------------
# Pause primitive
# ---------------------------------------------------------------------------

def compose_pause(
    *,
    reason: str,
    summary: Optional[Dict[str, Any]] = None,
    timeout_ms: int,
    resume_schema: Optional[Dict[str, Any]] = None,
    audit_tag: Optional[str] = None,
) -> Dict[str, Any]:
    """Pause the current FSScript run and block until resume or reject.

    This is the handler-callable pause primitive.  It MUST be called from
    within a FSScript run context (i.e. during ``run_script`` evaluation).

    Parameters
    ----------
    reason:
        Stable string for upstream identification.
    summary:
        JSON-serializable dict for upstream display.
    timeout_ms:
        How long to wait (ms).  Must be > 0 and ≤ MAX_TIMEOUT_MS.
    resume_schema:
        Optional JSON Schema for the expected resume payload.
    audit_tag:
        Optional trace tag.

    Returns
    -------
    Dict[str, Any]
        The resume payload submitted by upstream.

    Raises
    ------
    ScriptPauseNotInRunError
        If called outside a FSScript run context.
    ScriptSuspendRejectedError
        If upstream rejects the suspension.
    ScriptSuspendTimeoutError
        If the pause times out.
    """
    # Import here to avoid circular import at module load time.
    from .suspension_manager import SuspensionManager

    run_ctx = current_run_context()
    if run_ctx is None:
        raise ScriptPauseNotInRunError()

    # Access the manager from the run context.
    mgr: Optional[SuspensionManager] = getattr(run_ctx, "_manager", None)
    if mgr is None:
        raise ScriptPauseNotInRunError(
            "pause primitive has no SuspensionManager bound to run context"
        )

    request = PauseRequest(
        reason=reason,
        summary=summary if summary is not None else {},
        timeout_ms=timeout_ms,
        resume_schema=resume_schema,
        audit_tag=audit_tag,
    )

    return mgr.pause_and_wait(run_ctx.run_id, request)
