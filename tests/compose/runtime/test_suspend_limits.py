"""Tests for P2.3 Resource Limits and Cleanup.

Covers:
- ScriptSuspendLimitExceededError when exceeding max_suspend_count.
- Bounds check for timeout_ms (0 and > MAX_TIMEOUT_MS).
- slot and timer cleanup on resume, reject, timeout, abort, complete.
"""

from __future__ import annotations

import threading
import time

import pytest

from foggy.dataset_model.engine.compose.runtime.pause_primitive import (
    compose_pause,
    set_run_context,
)
from foggy.dataset_model.engine.compose.runtime.suspend_errors import (
    ScriptSuspendLimitExceededError,
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
    MAX_TIMEOUT_MS,
)
from foggy.dataset_model.engine.compose.runtime.suspension_manager import (
    SuspensionManager,
)


def _setup_run(mgr: SuspensionManager) -> ScriptRunContext:
    run_ctx = ScriptRunContext()
    run_ctx._manager = mgr  # type: ignore[attr-defined]
    mgr.register_run(run_ctx)
    return run_ctx


# ---------------------------------------------------------------------------
# Suspend Limit Tests
# ---------------------------------------------------------------------------

class TestSuspendLimit:

    def test_exceeding_max_suspend_count_raises(self):
        """When max_suspend_count is reached, next pause fails and no slot is leaked."""
        mgr = SuspensionManager(max_suspend_count=1)
        run1 = _setup_run(mgr)
        run2 = _setup_run(mgr)

        # 1. Suspend first run (success)
        def handler_thread1():
            set_run_context(run1)
            compose_pause(reason="r1", timeout_ms=5000)

        t1 = threading.Thread(target=handler_thread1)
        t1.start()

        # wait for first run to suspend
        for _ in range(100):
            if run1.state == ScriptRunState.SUSPENDED:
                break
            time.sleep(0.01)

        assert mgr.active_suspension_count() == 1
        assert len(mgr._slots) == 1

        # 2. Try to suspend second run (should fail)
        error_holder = {}

        def handler_thread2():
            set_run_context(run2)
            try:
                compose_pause(reason="r2", timeout_ms=5000)
            except Exception as e:
                error_holder["error"] = e

        t2 = threading.Thread(target=handler_thread2)
        t2.start()
        t2.join(timeout=2)

        # Verify limit error
        assert "error" in error_holder
        err = error_holder["error"]
        assert isinstance(err, ScriptSuspendLimitExceededError)
        assert err.code == "script/suspend-limit-exceeded"

        # Verify no slot leaked and state did not change
        assert mgr.active_suspension_count() == 1
        assert len(mgr._slots) == 1
        assert run2.state == ScriptRunState.RUNNING

        # Clean up t1
        mgr.resume(ResumeCommand(
            script_run_id=run1.run_id,
            suspend_id=run1.suspension.suspend_id,
            payload={},
        ))
        t1.join(timeout=2)


# ---------------------------------------------------------------------------
# Max Timeout Tests
# ---------------------------------------------------------------------------

class TestMaxTimeoutBounds:

    def test_timeout_zero_or_negative(self):
        with pytest.raises(ValueError, match="timeout_ms must be > 0"):
            PauseRequest(reason="r", summary={}, timeout_ms=0)

    def test_timeout_exceeds_max(self):
        with pytest.raises(ValueError, match=f"timeout_ms must be ≤ {MAX_TIMEOUT_MS}"):
            PauseRequest(reason="r", summary={}, timeout_ms=MAX_TIMEOUT_MS + 1)

    def test_timeout_max_allowed(self):
        req = PauseRequest(reason="r", summary={}, timeout_ms=MAX_TIMEOUT_MS)
        assert req.timeout_ms == MAX_TIMEOUT_MS


# ---------------------------------------------------------------------------
# Cleanup Tests
# ---------------------------------------------------------------------------

class TestResourceCleanup:

    def test_cleanup_on_resume(self):
        mgr = SuspensionManager()
        run = _setup_run(mgr)

        def handler():
            set_run_context(run)
            compose_pause(reason="r", timeout_ms=5000)

        t = threading.Thread(target=handler)
        t.start()

        for _ in range(100):
            if run.state == ScriptRunState.SUSPENDED:
                break
            time.sleep(0.01)

        suspend_id = run.suspension.suspend_id
        assert suspend_id in mgr._slots

        mgr.resume(ResumeCommand(
            script_run_id=run.run_id, suspend_id=suspend_id, payload={}
        ))
        t.join(timeout=2)

        assert suspend_id not in mgr._slots

    def test_cleanup_on_reject(self):
        mgr = SuspensionManager()
        run = _setup_run(mgr)

        def handler():
            set_run_context(run)
            try:
                compose_pause(reason="r", timeout_ms=5000)
            except:
                pass

        t = threading.Thread(target=handler)
        t.start()

        for _ in range(100):
            if run.state == ScriptRunState.SUSPENDED:
                break
            time.sleep(0.01)

        suspend_id = run.suspension.suspend_id
        with pytest.raises(ScriptSuspendRejectedError):
            mgr.reject(RejectCommand(
                script_run_id=run.run_id, suspend_id=suspend_id
            ))
        t.join(timeout=2)

        assert suspend_id not in mgr._slots

    def test_cleanup_on_timeout(self):
        mgr = SuspensionManager()
        run = _setup_run(mgr)

        def handler():
            set_run_context(run)
            try:
                compose_pause(reason="r", timeout_ms=50)
            except:
                pass

        t = threading.Thread(target=handler)
        t.start()
        t.join(timeout=2)

        assert len(mgr._slots) == 0
        assert run.state == ScriptRunState.TIMED_OUT

    def test_cleanup_on_abort_suspended_run(self):
        mgr = SuspensionManager()
        run = _setup_run(mgr)

        error_holder = {}
        def handler():
            set_run_context(run)
            try:
                compose_pause(reason="r", timeout_ms=5000)
            except Exception as e:
                error_holder["err"] = e

        t = threading.Thread(target=handler)
        t.start()

        for _ in range(100):
            if run.state == ScriptRunState.SUSPENDED:
                break
            time.sleep(0.01)

        assert len(mgr._slots) == 1
        mgr.abort_run(run.run_id)
        t.join(timeout=2)

        # Slot removed, timer cancelled, thread woken with timeout error
        assert len(mgr._slots) == 0
        assert "err" in error_holder
        assert isinstance(error_holder["err"], ScriptSuspendTimeoutError)

    def test_cleanup_on_complete_run(self):
        mgr = SuspensionManager()
        run = _setup_run(mgr)
        assert run.run_id in mgr._runs

        mgr.complete_run(run.run_id)
        assert run.run_id not in mgr._runs
