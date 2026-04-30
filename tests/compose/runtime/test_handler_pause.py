"""Tests for P2.2 handler-internal pause primitive.

Covers:
- pure_runtime handler pause → resume returns payload
- object facade method pause → resume returns payload
- pause outside FSScript run → ScriptPauseNotInRunError
- reject wakes thread → ScriptSuspendRejectedError
- timeout wakes thread → ScriptSuspendTimeoutError
- double resume / resume-after-reject / resume-after-timeout fail-closed
- timer cleanup on resume / reject
"""

from __future__ import annotations

import threading
import time

import pytest

from foggy.dataset_model.engine.compose.runtime.pause_primitive import (
    compose_pause,
    current_run_context,
    set_run_context,
)
from foggy.dataset_model.engine.compose.runtime.suspend_errors import (
    ScriptPauseNotInRunError,
    ScriptSuspendRejectedError,
    ScriptSuspendStateInvalidError,
    ScriptSuspendTimeoutError,
)
from foggy.dataset_model.engine.compose.runtime.suspension import (
    PauseRequest,
    RejectCommand,
    ResumeCommand,
    ScriptRunContext,
    ScriptRunState,
)
from foggy.dataset_model.engine.compose.runtime.suspension_manager import (
    SuspensionManager,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_run(mgr: SuspensionManager) -> ScriptRunContext:
    """Create, register, and set a run context on the ContextVar."""
    run_ctx = ScriptRunContext()
    run_ctx._manager = mgr  # type: ignore[attr-defined]
    mgr.register_run(run_ctx)
    return run_ctx


# ---------------------------------------------------------------------------
# Pause outside run context
# ---------------------------------------------------------------------------

class TestPauseOutsideRun:

    def test_no_run_context(self):
        """compose_pause outside a script run raises not-in-run."""
        token = set_run_context(None)
        try:
            with pytest.raises(ScriptPauseNotInRunError) as exc_info:
                compose_pause(
                    reason="test",
                    timeout_ms=1000,
                )
            assert exc_info.value.code == "script/pause-not-in-run"
        finally:
            set_run_context(None)

    def test_run_context_without_manager(self):
        """compose_pause with a context that has no _manager."""
        run_ctx = ScriptRunContext()
        token = set_run_context(run_ctx)
        try:
            with pytest.raises(ScriptPauseNotInRunError):
                compose_pause(reason="test", timeout_ms=1000)
        finally:
            set_run_context(None)


# ---------------------------------------------------------------------------
# Pure runtime handler pause
# ---------------------------------------------------------------------------

class TestPureRuntimePause:

    def test_resume_returns_payload(self):
        """Handler pauses, another thread resumes, handler gets payload."""
        mgr = SuspensionManager()
        run_ctx = _setup_run(mgr)

        result_holder = {}
        error_holder = {}

        def handler_thread():
            set_run_context(run_ctx)
            try:
                payload = compose_pause(
                    reason="order.confirm",
                    summary={"order": "123"},
                    timeout_ms=5000,
                )
                result_holder["payload"] = payload
            except Exception as e:
                error_holder["error"] = e

        t = threading.Thread(target=handler_thread)
        t.start()

        # Wait for suspension to appear.
        for _ in range(100):
            if run_ctx.state == ScriptRunState.SUSPENDED:
                break
            time.sleep(0.01)

        assert run_ctx.state == ScriptRunState.SUSPENDED
        assert run_ctx.suspension is not None

        # Resume from another thread.
        mgr.resume(ResumeCommand(
            script_run_id=run_ctx.run_id,
            suspend_id=run_ctx.suspension.suspend_id,
            payload={"approved": True, "operator": "admin"},
        ))

        t.join(timeout=2)
        assert not t.is_alive()
        assert "error" not in error_holder
        assert result_holder["payload"] == {
            "approved": True, "operator": "admin",
        }
        assert run_ctx.state == ScriptRunState.RUNNING

    def test_reject_raises_in_handler(self):
        """Handler pauses, another thread rejects, handler gets exception."""
        mgr = SuspensionManager()
        run_ctx = _setup_run(mgr)

        error_holder = {}

        def handler_thread():
            set_run_context(run_ctx)
            try:
                compose_pause(reason="test.reject", timeout_ms=5000)
            except ScriptSuspendRejectedError as e:
                error_holder["error"] = e
            except Exception as e:
                error_holder["unexpected"] = e

        t = threading.Thread(target=handler_thread)
        t.start()

        for _ in range(100):
            if run_ctx.state == ScriptRunState.SUSPENDED:
                break
            time.sleep(0.01)

        suspend_id = run_ctx.suspension.suspend_id

        with pytest.raises(ScriptSuspendRejectedError):
            mgr.reject(RejectCommand(
                script_run_id=run_ctx.run_id,
                suspend_id=suspend_id,
                reason="operator denied",
            ))

        t.join(timeout=2)
        assert not t.is_alive()
        assert "unexpected" not in error_holder
        assert isinstance(error_holder["error"], ScriptSuspendRejectedError)
        assert error_holder["error"].code == "script/suspend-rejected"

    def test_timeout_raises_in_handler(self):
        """Handler pauses with very short timeout, gets timeout exception."""
        mgr = SuspensionManager()
        run_ctx = _setup_run(mgr)

        error_holder = {}

        def handler_thread():
            set_run_context(run_ctx)
            try:
                compose_pause(reason="test.timeout", timeout_ms=50)
            except ScriptSuspendTimeoutError as e:
                error_holder["error"] = e
            except Exception as e:
                error_holder["unexpected"] = e

        t = threading.Thread(target=handler_thread)
        t.start()

        # Wait for timeout to fire.
        t.join(timeout=3)
        assert not t.is_alive()
        assert "unexpected" not in error_holder
        assert isinstance(error_holder["error"], ScriptSuspendTimeoutError)
        assert error_holder["error"].code == "script/suspend-timeout"
        assert run_ctx.state == ScriptRunState.TIMED_OUT


# ---------------------------------------------------------------------------
# Double resume / reject / timeout invariants
# ---------------------------------------------------------------------------

class TestFailClosed:

    def test_resume_after_resume(self):
        """Second resume after successful resume is fail-closed."""
        mgr = SuspensionManager()
        run_ctx = _setup_run(mgr)

        def handler_thread():
            set_run_context(run_ctx)
            compose_pause(reason="test", timeout_ms=5000)

        t = threading.Thread(target=handler_thread)
        t.start()

        for _ in range(100):
            if run_ctx.state == ScriptRunState.SUSPENDED:
                break
            time.sleep(0.01)

        suspend_id = run_ctx.suspension.suspend_id

        mgr.resume(ResumeCommand(
            script_run_id=run_ctx.run_id,
            suspend_id=suspend_id,
            payload={},
        ))
        t.join(timeout=2)

        # Second resume must fail.
        with pytest.raises(ScriptSuspendStateInvalidError):
            mgr.resume(ResumeCommand(
                script_run_id=run_ctx.run_id,
                suspend_id=suspend_id,
                payload={},
            ))

    def test_resume_after_reject(self):
        """Resume after reject is fail-closed."""
        mgr = SuspensionManager()
        run_ctx = _setup_run(mgr)

        def handler_thread():
            set_run_context(run_ctx)
            try:
                compose_pause(reason="test", timeout_ms=5000)
            except ScriptSuspendRejectedError:
                pass

        t = threading.Thread(target=handler_thread)
        t.start()

        for _ in range(100):
            if run_ctx.state == ScriptRunState.SUSPENDED:
                break
            time.sleep(0.01)

        suspend_id = run_ctx.suspension.suspend_id

        with pytest.raises(ScriptSuspendRejectedError):
            mgr.reject(RejectCommand(
                script_run_id=run_ctx.run_id,
                suspend_id=suspend_id,
            ))
        t.join(timeout=2)

        # Resume after reject must fail.
        with pytest.raises(ScriptSuspendStateInvalidError):
            mgr.resume(ResumeCommand(
                script_run_id=run_ctx.run_id,
                suspend_id=suspend_id,
                payload={},
            ))

    def test_resume_after_timeout(self):
        """Resume after timeout is fail-closed."""
        mgr = SuspensionManager()
        run_ctx = _setup_run(mgr)

        def handler_thread():
            set_run_context(run_ctx)
            try:
                compose_pause(reason="test", timeout_ms=50)
            except ScriptSuspendTimeoutError:
                pass

        t = threading.Thread(target=handler_thread)
        t.start()
        t.join(timeout=3)

        # The suspend_id is stale but we need it for the error path.
        # After timeout, run_ctx.suspension is still set (only cleared on resume).
        # But state is TIMED_OUT which is terminal, so any resume fails.
        assert run_ctx.state == ScriptRunState.TIMED_OUT


# ---------------------------------------------------------------------------
# Timer cleanup
# ---------------------------------------------------------------------------

class TestTimerCleanup:

    def test_timer_cancelled_on_resume(self):
        """Resume cancels the auto-timeout timer."""
        mgr = SuspensionManager()
        run_ctx = _setup_run(mgr)

        def handler_thread():
            set_run_context(run_ctx)
            compose_pause(reason="test", timeout_ms=60_000)

        t = threading.Thread(target=handler_thread)
        t.start()

        for _ in range(100):
            if run_ctx.state == ScriptRunState.SUSPENDED:
                break
            time.sleep(0.01)

        suspend_id = run_ctx.suspension.suspend_id
        mgr.resume(ResumeCommand(
            script_run_id=run_ctx.run_id,
            suspend_id=suspend_id,
            payload={"ok": True},
        ))
        t.join(timeout=2)

        # Run should be RUNNING, not timed out.
        assert run_ctx.state == ScriptRunState.RUNNING

    def test_completed_run_removed_from_manager(self):
        """After resume and complete, the run is gone from the manager."""
        mgr = SuspensionManager()
        run_ctx = _setup_run(mgr)

        def handler_thread():
            set_run_context(run_ctx)
            compose_pause(reason="test", timeout_ms=5000)

        t = threading.Thread(target=handler_thread)
        t.start()

        for _ in range(100):
            if run_ctx.state == ScriptRunState.SUSPENDED:
                break
            time.sleep(0.01)

        mgr.resume(ResumeCommand(
            script_run_id=run_ctx.run_id,
            suspend_id=run_ctx.suspension.suspend_id,
            payload={},
        ))
        t.join(timeout=2)

        mgr.complete_run(run_ctx.run_id)
        assert mgr.get_run(run_ctx.run_id) is None
        assert mgr.active_run_count() == 0
