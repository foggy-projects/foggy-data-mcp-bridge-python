"""Tests for SuspensionManager in-process resume / reject API (P2.1)."""

from __future__ import annotations
import pytest
from foggy.dataset_model.engine.compose.runtime.suspension import (
    PauseRequest, RejectCommand, ResumeCommand,
    ScriptRunContext, ScriptRunState,
)
from foggy.dataset_model.engine.compose.runtime.suspension_manager import (
    SuspensionManager,
)
from foggy.dataset_model.engine.compose.runtime.suspend_errors import (
    ScriptResumeTokenInvalidError,
    ScriptSuspendRejectedError,
    ScriptSuspendStateInvalidError,
    ScriptSuspendTimeoutError,
)

def _pause() -> PauseRequest:
    return PauseRequest(reason="test.pause", summary={"k": "v"}, timeout_ms=5000)


class TestRegisterAndLookup:
    def test_register_and_get(self):
        mgr = SuspensionManager()
        ctx = ScriptRunContext()
        mgr.register_run(ctx)
        assert mgr.get_run(ctx.run_id) is ctx

    def test_get_unknown_returns_none(self):
        mgr = SuspensionManager()
        assert mgr.get_run("sr_nonexistent") is None

    def test_double_register_rejected(self):
        mgr = SuspensionManager()
        ctx = ScriptRunContext()
        mgr.register_run(ctx)
        with pytest.raises(ValueError, match="already registered"):
            mgr.register_run(ctx)

    def test_active_run_count(self):
        mgr = SuspensionManager()
        mgr.register_run(ScriptRunContext())
        mgr.register_run(ScriptRunContext())
        assert mgr.active_run_count() == 2


class TestRequestSuspension:
    def test_suspends_running(self):
        mgr = SuspensionManager()
        ctx = ScriptRunContext()
        mgr.register_run(ctx)
        result = mgr.request_suspension(ctx.run_id, _pause())
        assert result.type == "script_suspended"
        assert result.script_run_id == ctx.run_id
        assert result.reason == "test.pause"
        assert ctx.state == ScriptRunState.SUSPENDED

    def test_unknown_run_fails(self):
        mgr = SuspensionManager()
        with pytest.raises(ScriptResumeTokenInvalidError):
            mgr.request_suspension("sr_unknown", _pause())

    def test_double_suspend_fails(self):
        mgr = SuspensionManager()
        ctx = ScriptRunContext()
        mgr.register_run(ctx)
        mgr.request_suspension(ctx.run_id, _pause())
        with pytest.raises(ScriptSuspendStateInvalidError):
            mgr.request_suspension(ctx.run_id, _pause())

    def test_active_suspension_count(self):
        mgr = SuspensionManager()
        c1, c2 = ScriptRunContext(), ScriptRunContext()
        mgr.register_run(c1)
        mgr.register_run(c2)
        assert mgr.active_suspension_count() == 0
        mgr.request_suspension(c1.run_id, _pause())
        assert mgr.active_suspension_count() == 1


class TestResume:
    def test_resume_returns_payload(self):
        mgr = SuspensionManager()
        ctx = ScriptRunContext()
        mgr.register_run(ctx)
        result = mgr.request_suspension(ctx.run_id, _pause())
        payload = mgr.resume(ResumeCommand(
            script_run_id=ctx.run_id,
            suspend_id=result.suspend_id,
            payload={"approved": True},
        ))
        assert payload == {"approved": True}
        assert ctx.state == ScriptRunState.RUNNING
        assert ctx.suspension is None

    def test_wrong_run_id(self):
        mgr = SuspensionManager()
        ctx = ScriptRunContext()
        mgr.register_run(ctx)
        result = mgr.request_suspension(ctx.run_id, _pause())
        with pytest.raises(ScriptResumeTokenInvalidError):
            mgr.resume(ResumeCommand(
                script_run_id="sr_wrong",
                suspend_id=result.suspend_id,
                payload={},
            ))

    def test_wrong_suspend_id(self):
        mgr = SuspensionManager()
        ctx = ScriptRunContext()
        mgr.register_run(ctx)
        mgr.request_suspension(ctx.run_id, _pause())
        with pytest.raises(ScriptResumeTokenInvalidError):
            mgr.resume(ResumeCommand(
                script_run_id=ctx.run_id,
                suspend_id="sp_wrong",
                payload={},
            ))

    def test_double_resume_fails(self):
        mgr = SuspensionManager()
        ctx = ScriptRunContext()
        mgr.register_run(ctx)
        result = mgr.request_suspension(ctx.run_id, _pause())
        cmd = ResumeCommand(
            script_run_id=ctx.run_id,
            suspend_id=result.suspend_id,
            payload={},
        )
        mgr.resume(cmd)
        with pytest.raises(ScriptSuspendStateInvalidError):
            mgr.resume(cmd)


class TestReject:
    def test_reject_raises(self):
        mgr = SuspensionManager()
        ctx = ScriptRunContext()
        mgr.register_run(ctx)
        result = mgr.request_suspension(ctx.run_id, _pause())
        with pytest.raises(ScriptSuspendRejectedError) as exc_info:
            mgr.reject(RejectCommand(
                script_run_id=ctx.run_id,
                suspend_id=result.suspend_id,
                reason="operator denied",
            ))
        assert exc_info.value.code == "script/suspend-rejected"
        assert ctx.state == ScriptRunState.REJECTED

    def test_resume_after_reject_fails(self):
        mgr = SuspensionManager()
        ctx = ScriptRunContext()
        mgr.register_run(ctx)
        result = mgr.request_suspension(ctx.run_id, _pause())
        with pytest.raises(ScriptSuspendRejectedError):
            mgr.reject(RejectCommand(
                script_run_id=ctx.run_id,
                suspend_id=result.suspend_id,
            ))
        with pytest.raises(ScriptSuspendStateInvalidError):
            mgr.resume(ResumeCommand(
                script_run_id=ctx.run_id,
                suspend_id=result.suspend_id,
                payload={},
            ))


class TestTimeout:
    def test_timeout_raises(self):
        mgr = SuspensionManager()
        ctx = ScriptRunContext()
        mgr.register_run(ctx)
        result = mgr.request_suspension(ctx.run_id, _pause())
        with pytest.raises(ScriptSuspendTimeoutError) as exc_info:
            mgr.timeout(ctx.run_id, result.suspend_id)
        assert exc_info.value.code == "script/suspend-timeout"
        assert ctx.state == ScriptRunState.TIMED_OUT

    def test_resume_after_timeout_fails(self):
        mgr = SuspensionManager()
        ctx = ScriptRunContext()
        mgr.register_run(ctx)
        result = mgr.request_suspension(ctx.run_id, _pause())
        with pytest.raises(ScriptSuspendTimeoutError):
            mgr.timeout(ctx.run_id, result.suspend_id)
        with pytest.raises(ScriptSuspendStateInvalidError):
            mgr.resume(ResumeCommand(
                script_run_id=ctx.run_id,
                suspend_id=result.suspend_id,
                payload={},
            ))


class TestLifecycle:
    def test_complete_run(self):
        mgr = SuspensionManager()
        ctx = ScriptRunContext()
        mgr.register_run(ctx)
        mgr.complete_run(ctx.run_id)
        assert mgr.get_run(ctx.run_id) is None
        assert ctx.state == ScriptRunState.COMPLETED

    def test_complete_run_after_resume(self):
        mgr = SuspensionManager()
        ctx = ScriptRunContext()
        mgr.register_run(ctx)
        result = mgr.request_suspension(ctx.run_id, _pause())
        mgr.resume(ResumeCommand(
            script_run_id=ctx.run_id,
            suspend_id=result.suspend_id,
            payload={},
        ))
        mgr.complete_run(ctx.run_id)
        assert mgr.get_run(ctx.run_id) is None
        assert ctx.state == ScriptRunState.COMPLETED

    def test_abort_running(self):
        mgr = SuspensionManager()
        ctx = ScriptRunContext()
        mgr.register_run(ctx)
        mgr.abort_run(ctx.run_id)
        assert mgr.get_run(ctx.run_id) is None
        assert ctx.state == ScriptRunState.ABORTED

    def test_abort_suspended(self):
        mgr = SuspensionManager()
        ctx = ScriptRunContext()
        mgr.register_run(ctx)
        mgr.request_suspension(ctx.run_id, _pause())
        mgr.abort_run(ctx.run_id)
        assert ctx.state == ScriptRunState.ABORTED

    def test_complete_unknown_fails(self):
        mgr = SuspensionManager()
        with pytest.raises(ScriptResumeTokenInvalidError):
            mgr.complete_run("sr_unknown")
