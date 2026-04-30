"""v1.9 P2.1 — In-process suspension manager.

:class:`SuspensionManager` maintains a dict of active
:class:`ScriptRunContext` keyed by ``run_id``.  It provides the
Engine-internal resume / reject API that upstream callers use to
resolve a suspended script run.

P2.1 scope
----------
* Register / lookup / complete / abort runs.
* ``request_suspension`` — validate run is RUNNING, transition to
  SUSPENDED, produce :class:`SuspensionResult`.
* ``resume`` — validate run_id + suspend_id, clear stale suspension,
  transition back to RUNNING, return payload.
* ``reject`` — validate same, transition to REJECTED.
* ``timeout`` — validate same, transition to TIMED_OUT.

P2.2 additions (not implemented here)
--------------------------------------
* Actual thread / coroutine blocking on pause.
* Timer-based automatic timeout scheduling.
* Resource-limit enforcement (P2.3).

Design decisions
~~~~~~~~~~~~~~~~
* All mutations are ``threading.Lock``-protected for P2.2-readiness.
* ``resume()`` returns the payload dict.  ``reject()`` raises
  :class:`ScriptSuspendRejectedError`.  ``timeout()`` raises
  :class:`ScriptSuspendTimeoutError`.  This matches the spec
  requirement: reject / timeout raise controlled exceptions, they
  do not return status values.
* Completed / aborted runs are removed from the active map to bound
  memory usage.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from .suspend_errors import (
    ScriptResumeTokenInvalidError,
    ScriptSuspendRejectedError,
    ScriptSuspendStateInvalidError,
    ScriptSuspendTimeoutError,
)
from .suspension import (
    PauseRequest,
    RejectCommand,
    ResumeCommand,
    ScriptRunContext,
    ScriptRunState,
    SuspensionResult,
    generate_suspend_id,
)

__all__ = [
    "SuspensionManager",
]


class SuspensionManager:
    """In-process registry of active FSScript runs.

    Thread-safe.  All public methods acquire :attr:`_lock` before
    mutating internal state.

    Typical lifecycle::

        mgr = SuspensionManager()

        # Script execution starts.
        run_ctx = ScriptRunContext()
        mgr.register_run(run_ctx)

        # Handler calls pause → engine suspends the run.
        result = mgr.request_suspension(run_ctx.run_id, pause_request)

        # Upstream later submits resume or reject.
        payload = mgr.resume(ResumeCommand(...))
        # — or —
        mgr.reject(RejectCommand(...))

        # Script finishes.
        mgr.complete_run(run_ctx.run_id)
    """

    def __init__(self) -> None:
        self._runs: Dict[str, ScriptRunContext] = {}
        self._lock = threading.Lock()

    # -- registration -------------------------------------------------------

    def register_run(self, run_ctx: ScriptRunContext) -> None:
        """Register a new run context.

        Raises
        ------
        ValueError
            If a run with the same ``run_id`` is already registered.
        """
        with self._lock:
            if run_ctx.run_id in self._runs:
                raise ValueError(
                    f"run {run_ctx.run_id} is already registered"
                )
            self._runs[run_ctx.run_id] = run_ctx

    def get_run(self, run_id: str) -> Optional[ScriptRunContext]:
        """Look up a run by ID.  Returns ``None`` if not found."""
        with self._lock:
            return self._runs.get(run_id)

    # -- suspension ---------------------------------------------------------

    def request_suspension(
        self,
        run_id: str,
        request: PauseRequest,
    ) -> SuspensionResult:
        """Suspend a RUNNING script run.

        Returns a :class:`SuspensionResult` that upstream can use to
        build a user-facing prompt.

        Raises
        ------
        ScriptResumeTokenInvalidError
            If ``run_id`` is not registered.
        ScriptSuspendStateInvalidError
            If the run is not in ``RUNNING`` state.
        """
        with self._lock:
            run_ctx = self._runs.get(run_id)
            if run_ctx is None:
                raise ScriptResumeTokenInvalidError(
                    f"run {run_id} is not registered"
                )
            # transition validates RUNNING → SUSPENDED
            run_ctx.transition(ScriptRunState.SUSPENDED)

            suspend_id = generate_suspend_id()
            timeout_at = datetime.now(timezone.utc) + timedelta(
                milliseconds=request.timeout_ms
            )
            result = SuspensionResult(
                script_run_id=run_id,
                suspend_id=suspend_id,
                reason=request.reason,
                summary=request.summary,
                timeout_at=timeout_at,
            )
            run_ctx.suspension = result
            return result

    # -- resume / reject / timeout ------------------------------------------

    def resume(self, command: ResumeCommand) -> Dict[str, Any]:
        """Resume a suspended run.

        Returns the ``payload`` dict from the command so the pause call
        site can receive it as the return value.

        Raises
        ------
        ScriptResumeTokenInvalidError
            If ``run_id`` is unknown or ``suspend_id`` does not match.
        ScriptSuspendStateInvalidError
            If the run is not in ``SUSPENDED`` state.
        """
        with self._lock:
            run_ctx = self._require_suspended(
                command.script_run_id, command.suspend_id,
            )
            # clear suspension result when resuming to prevent leaking stale data
            run_ctx.suspension = None
            run_ctx.transition(ScriptRunState.RUNNING)
            return dict(command.payload)

    def reject(self, command: RejectCommand) -> None:
        """Reject a suspended run.

        Raises
        ------
        ScriptSuspendRejectedError
            Always raised after a successful state transition so the
            pause call site receives a controlled exception.
        ScriptResumeTokenInvalidError
            If tokens do not match.
        ScriptSuspendStateInvalidError
            If state is not SUSPENDED.
        """
        with self._lock:
            run_ctx = self._require_suspended(
                command.script_run_id, command.suspend_id,
            )
            run_ctx.transition(ScriptRunState.REJECTED)
        # Raise OUTSIDE the lock — callers catch this.
        reason = command.reason or "suspend rejected"
        raise ScriptSuspendRejectedError(reason)

    def timeout(self, run_id: str, suspend_id: str) -> None:
        """Mark a suspended run as timed out.

        Raises
        ------
        ScriptSuspendTimeoutError
            Always raised after a successful state transition.
        ScriptResumeTokenInvalidError
            If tokens do not match.
        ScriptSuspendStateInvalidError
            If state is not SUSPENDED.
        """
        with self._lock:
            run_ctx = self._require_suspended(run_id, suspend_id)
            run_ctx.transition(ScriptRunState.TIMED_OUT)
        raise ScriptSuspendTimeoutError("suspend timed out")

    # -- lifecycle ----------------------------------------------------------

    def complete_run(self, run_id: str) -> None:
        """Mark a run as completed and remove it from the active map.

        Raises
        ------
        ScriptResumeTokenInvalidError
            If ``run_id`` is unknown.
        ScriptSuspendStateInvalidError
            If the transition is illegal.
        """
        with self._lock:
            run_ctx = self._require_run(run_id)
            run_ctx.transition(ScriptRunState.COMPLETED)
            del self._runs[run_id]

    def abort_run(self, run_id: str) -> None:
        """Abort a run and remove it from the active map.

        Can be called from RUNNING or SUSPENDED state.

        Raises
        ------
        ScriptResumeTokenInvalidError
            If ``run_id`` is unknown.
        ScriptSuspendStateInvalidError
            If the transition is illegal (run already terminal).
        """
        with self._lock:
            run_ctx = self._require_run(run_id)
            run_ctx.transition(ScriptRunState.ABORTED)
            del self._runs[run_id]

    # -- query --------------------------------------------------------------

    def active_suspension_count(self) -> int:
        """Number of runs currently in ``SUSPENDED`` state."""
        with self._lock:
            return sum(
                1 for r in self._runs.values()
                if r.state == ScriptRunState.SUSPENDED
            )

    def active_run_count(self) -> int:
        """Total number of tracked (non-terminal) runs."""
        with self._lock:
            return len(self._runs)

    # -- internal helpers ---------------------------------------------------

    def _require_run(self, run_id: str) -> ScriptRunContext:
        """Return run or raise ``ScriptResumeTokenInvalidError``."""
        run_ctx = self._runs.get(run_id)
        if run_ctx is None:
            raise ScriptResumeTokenInvalidError(
                f"run {run_id} is not registered"
            )
        return run_ctx

    def _require_suspended(
        self, run_id: str, suspend_id: str,
    ) -> ScriptRunContext:
        """Return run and validate it is SUSPENDED with matching
        ``suspend_id``.
        """
        run_ctx = self._require_run(run_id)
        if run_ctx.suspension is None:
            raise ScriptSuspendStateInvalidError(
                f"run {run_id} has no active suspension"
            )
        if run_ctx.suspension.suspend_id != suspend_id:
            raise ScriptResumeTokenInvalidError(
                f"suspend_id mismatch for run {run_id}"
            )
        if run_ctx.state != ScriptRunState.SUSPENDED:
            raise ScriptSuspendStateInvalidError(
                f"run {run_id} is in state {run_ctx.state.value}, "
                f"expected SUSPENDED"
            )
        return run_ctx
