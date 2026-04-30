"""v1.9 P2.1 + P2.2 — In-process suspension manager.

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

P2.2 additions
--------------
* ``pause_and_wait`` — handler-callable blocking pause.  Creates the
  suspension, starts a ``threading.Timer`` for auto-timeout, and
  blocks the calling thread on a ``threading.Event`` until resume,
  reject, or timeout.
* ``resume`` / ``reject`` / ``timeout`` now wake the blocked thread
  by setting the ``Event``.
* Timer is cancelled on resume or reject.

Design decisions
~~~~~~~~~~~~~~~~
* All mutations are ``threading.Lock``-protected.
* ``resume()`` returns the payload dict.  ``reject()`` raises
  :class:`ScriptSuspendRejectedError`.  ``timeout()`` raises
  :class:`ScriptSuspendTimeoutError`.  This matches the spec
  requirement: reject / timeout raise controlled exceptions, they
  do not return status values.
* Completed / aborted runs are removed from the active map to bound
  memory usage.
* ``_WaitSlot`` bundles the ``Event``, result/error, and ``Timer``
  for each suspended run.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
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


# ---------------------------------------------------------------------------
# Internal wait slot — one per active suspension
# ---------------------------------------------------------------------------

@dataclass
class _WaitSlot:
    """Bundles the synchronization primitives for one suspension.

    Created by ``pause_and_wait``, consumed by ``resume`` / ``reject``
    / ``timeout``.

    Attributes
    ----------
    event:
        The ``Event`` the handler thread blocks on.
    payload:
        Set by ``resume()`` before signalling the event.
    error:
        Set by ``reject()`` or ``timeout()`` before signalling.
    timer:
        The auto-timeout ``Timer``; cancelled on resume or reject.
    """

    event: threading.Event = field(default_factory=threading.Event)
    payload: Optional[Dict[str, Any]] = None
    error: Optional[BaseException] = None
    timer: Optional[threading.Timer] = None


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
        self._slots: Dict[str, _WaitSlot] = {}  # keyed by suspend_id
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

    # -- P2.2: blocking pause -----------------------------------------------

    def pause_and_wait(
        self,
        run_id: str,
        request: PauseRequest,
    ) -> Dict[str, Any]:
        """Suspend a RUNNING run and block until resume, reject, or timeout.

        This is the handler-thread entry point.  It:

        1. Calls ``request_suspension`` to transition to SUSPENDED.
        2. Creates a ``_WaitSlot`` with a ``threading.Event``.
        3. Starts a ``threading.Timer`` for auto-timeout.
        4. Blocks on ``Event.wait()``.
        5. On wake-up, returns the payload or raises the error.

        Returns
        -------
        Dict[str, Any]
            The resume payload.

        Raises
        ------
        ScriptSuspendRejectedError
            On explicit reject.
        ScriptSuspendTimeoutError
            On timeout.
        ScriptResumeTokenInvalidError / ScriptSuspendStateInvalidError
            On invalid state.
        """
        result = self.request_suspension(run_id, request)
        suspend_id = result.suspend_id
        timeout_seconds = request.timeout_ms / 1000.0

        slot = _WaitSlot()

        # Schedule auto-timeout timer.
        timer = threading.Timer(
            timeout_seconds,
            self._auto_timeout,
            args=(run_id, suspend_id),
        )
        timer.daemon = True
        slot.timer = timer

        with self._lock:
            self._slots[suspend_id] = slot

        timer.start()

        # Block until resume / reject / timeout wakes us.
        slot.event.wait()

        # Clean up slot reference.
        with self._lock:
            self._slots.pop(suspend_id, None)

        # Check outcome.
        if slot.error is not None:
            raise slot.error

        return slot.payload if slot.payload is not None else {}

    def _auto_timeout(self, run_id: str, suspend_id: str) -> None:
        """Timer callback — mark the run as timed out and wake the
        blocked thread.

        Swallows ``ScriptSuspendStateInvalidError`` if the run was
        already resumed/rejected before the timer fired.
        """
        try:
            self._resolve(
                run_id, suspend_id,
                new_state=ScriptRunState.TIMED_OUT,
                error=ScriptSuspendTimeoutError("suspend timed out"),
            )
        except (ScriptSuspendStateInvalidError, ScriptResumeTokenInvalidError):
            # Already resolved — timer arrived late.  Ignore.
            pass

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
            # clear suspension result when resuming
            run_ctx.suspension = None
            run_ctx.transition(ScriptRunState.RUNNING)

            # Wake blocked thread with payload.
            slot = self._slots.get(command.suspend_id)
            if slot is not None:
                if slot.timer is not None:
                    slot.timer.cancel()
                slot.payload = dict(command.payload)
                slot.event.set()

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
        reason = command.reason or "suspend rejected"
        error = ScriptSuspendRejectedError(reason)

        self._resolve(
            command.script_run_id, command.suspend_id,
            new_state=ScriptRunState.REJECTED,
            error=error,
        )

        # Raise for direct callers (non-blocking path / P2.1 compat).
        raise error

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
        error = ScriptSuspendTimeoutError("suspend timed out")

        self._resolve(
            run_id, suspend_id,
            new_state=ScriptRunState.TIMED_OUT,
            error=error,
        )

        raise error

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
            # If there's an active suspension slot, wake it with abort.
            if run_ctx.suspension is not None:
                slot = self._slots.pop(run_ctx.suspension.suspend_id, None)
                if slot is not None:
                    if slot.timer is not None:
                        slot.timer.cancel()
                    slot.error = ScriptSuspendTimeoutError(
                        "run aborted while suspended"
                    )
                    slot.event.set()
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

    def _resolve(
        self,
        run_id: str,
        suspend_id: str,
        *,
        new_state: ScriptRunState,
        error: Optional[BaseException] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Transition state and wake the blocked thread.

        Used internally by ``resume``, ``reject``, ``timeout``, and
        the auto-timeout timer.
        """
        with self._lock:
            run_ctx = self._require_suspended(run_id, suspend_id)
            run_ctx.transition(new_state)

            slot = self._slots.get(suspend_id)
            if slot is not None:
                if slot.timer is not None:
                    slot.timer.cancel()
                slot.error = error
                slot.payload = payload
                slot.event.set()
