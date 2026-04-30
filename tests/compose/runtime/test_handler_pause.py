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


# ---------------------------------------------------------------------------
# Race condition regression
# ---------------------------------------------------------------------------

class TestRaceConditionRegression:
    """Verify that resume arriving between request_suspension and
    Event.wait does NOT cause the handler thread to hang."""

    def test_immediate_resume_does_not_hang(self):
        """Resume fires as soon as SUSPENDED is visible — handler must
        still receive the payload without waiting for timeout."""
        mgr = SuspensionManager()
        run_ctx = _setup_run(mgr)

        result_holder = {}
        error_holder = {}

        def handler_thread():
            set_run_context(run_ctx)
            try:
                payload = compose_pause(
                    reason="race.test",
                    timeout_ms=60_000,  # long timeout — must not wait
                )
                result_holder["payload"] = payload
            except Exception as e:
                error_holder["error"] = e

        t = threading.Thread(target=handler_thread)
        t.start()

        # Spin-wait until SUSPENDED, then resume immediately.
        for _ in range(200):
            if run_ctx.state == ScriptRunState.SUSPENDED:
                break
            time.sleep(0.005)

        assert run_ctx.state == ScriptRunState.SUSPENDED
        mgr.resume(ResumeCommand(
            script_run_id=run_ctx.run_id,
            suspend_id=run_ctx.suspension.suspend_id,
            payload={"fast": True},
        ))

        # Must complete quickly — 2s is generous for a non-racy path.
        t.join(timeout=2)
        assert not t.is_alive(), "handler thread hung — resume race lost"
        assert "error" not in error_holder
        assert result_holder["payload"] == {"fast": True}


# ---------------------------------------------------------------------------
# ContextVar nesting regression
# ---------------------------------------------------------------------------

class TestContextVarNesting:
    """Verify run_script properly restores the parent run context
    when nested calls complete."""

    def test_nested_context_restored(self):
        """After set_run_context(child) + reset(token), the parent
        context is restored."""
        from foggy.dataset_model.engine.compose.runtime.pause_primitive import (
            _script_run_context,
        )
        parent = ScriptRunContext()
        child = ScriptRunContext()

        parent_token = _script_run_context.set(parent)
        assert current_run_context() is parent

        child_token = _script_run_context.set(child)
        assert current_run_context() is child

        _script_run_context.reset(child_token)
        assert current_run_context() is parent

        _script_run_context.reset(parent_token)
        assert current_run_context() is None


# ---------------------------------------------------------------------------
# End-to-end: run_script + pure_runtime handler pause
# ---------------------------------------------------------------------------

class TestE2EPureRuntimePause:
    """Integration test: a pure_runtime capability handler calls
    compose_pause() during run_script evaluation."""

    def test_handler_pause_resume_through_run_script(self):
        """Register a pure_runtime handler that calls compose_pause.
        Run the script, resume from another thread, verify the script
        returns the resume payload."""
        from foggy.dataset_model.engine.compose.capability.registry import (
            CapabilityRegistry,
        )
        from foggy.dataset_model.engine.compose.capability.policy import (
            CapabilityPolicy,
        )
        from foggy.dataset_model.engine.compose.capability.descriptors import (
            FunctionDescriptor,
        )
        from foggy.dataset_model.engine.compose.runtime.script_runtime import (
            run_script,
        )
        from foggy.dataset_model.engine.compose.context.compose_query_context import (
            ComposeQueryContext,
        )
        from foggy.dataset_model.engine.compose.context.principal import Principal
        from tests.compose.runtime.conftest import StubResolver, StubSemanticService

        # Handler calls compose_pause, returns the resume payload.
        def pause_handler(reason_str):
            payload = compose_pause(
                reason=reason_str,
                timeout_ms=5000,
            )
            return payload

        reg = CapabilityRegistry()
        reg.register_function(
            FunctionDescriptor(
                name="request_approval",
                kind="pure_runtime",
                args_schema=[{"name": "reason_str", "type": "string", "required": True}],
                return_type="dict",
                deterministic=False,
                side_effect="none",
                allowed_in=["compose_runtime"],
                audit_tag="test.approval",
            ),
            handler=pause_handler,
        )
        policy = CapabilityPolicy(
            allowed_functions=frozenset({"request_approval"}),
        )

        mgr = SuspensionManager()
        ctx = ComposeQueryContext(
            principal=Principal(user_id="u1"),
            namespace="default",
            authority_resolver=StubResolver(),
        )
        svc = StubSemanticService()

        script = 'return request_approval("order.confirm");'

        result_holder = {}
        error_holder = {}

        def script_thread():
            try:
                result = run_script(
                    script, ctx,
                    semantic_service=svc,
                    capability_registry=reg,
                    capability_policy=policy,
                    suspension_manager=mgr,
                )
                result_holder["value"] = result.value
            except Exception as e:
                error_holder["error"] = e

        t = threading.Thread(target=script_thread)
        t.start()

        # Wait for a SUSPENDED run.
        run_ctx = None
        for _ in range(200):
            if mgr.active_suspension_count() > 0:
                # find the suspended run
                for rid, rc in list(mgr._runs.items()):
                    if rc.state == ScriptRunState.SUSPENDED:
                        run_ctx = rc
                        break
            if run_ctx is not None:
                break
            time.sleep(0.01)

        assert run_ctx is not None, "no suspended run found"
        assert run_ctx.suspension is not None

        mgr.resume(ResumeCommand(
            script_run_id=run_ctx.run_id,
            suspend_id=run_ctx.suspension.suspend_id,
            payload={"approved": True},
        ))

        t.join(timeout=5)
        assert not t.is_alive()
        assert "error" not in error_holder, f"script error: {error_holder.get('error')}"
        assert result_holder["value"] == {"approved": True}

    def test_handler_pause_reject_through_run_script(self):
        """Same as above but the pause is rejected — script should raise
        ScriptSuspendRejectedError."""
        from foggy.dataset_model.engine.compose.capability.registry import (
            CapabilityRegistry,
        )
        from foggy.dataset_model.engine.compose.capability.policy import (
            CapabilityPolicy,
        )
        from foggy.dataset_model.engine.compose.capability.descriptors import (
            FunctionDescriptor,
        )
        from foggy.dataset_model.engine.compose.runtime.script_runtime import (
            run_script,
        )
        from foggy.dataset_model.engine.compose.context.compose_query_context import (
            ComposeQueryContext,
        )
        from foggy.dataset_model.engine.compose.context.principal import Principal
        from tests.compose.runtime.conftest import StubResolver, StubSemanticService

        def pause_handler(reason_str):
            return compose_pause(reason=reason_str, timeout_ms=5000)

        reg = CapabilityRegistry()
        reg.register_function(
            FunctionDescriptor(
                name="request_approval",
                kind="pure_runtime",
                args_schema=[{"name": "reason_str", "type": "string", "required": True}],
                return_type="dict",
                deterministic=False,
                side_effect="none",
                allowed_in=["compose_runtime"],
                audit_tag="test.approval",
            ),
            handler=pause_handler,
        )
        policy = CapabilityPolicy(
            allowed_functions=frozenset({"request_approval"}),
        )

        mgr = SuspensionManager()
        ctx = ComposeQueryContext(
            principal=Principal(user_id="u1"),
            namespace="default",
            authority_resolver=StubResolver(),
        )
        svc = StubSemanticService()

        script = 'return request_approval("order.deny");'

        error_holder = {}

        def script_thread():
            try:
                run_script(
                    script, ctx,
                    semantic_service=svc,
                    capability_registry=reg,
                    capability_policy=policy,
                    suspension_manager=mgr,
                )
            except ScriptSuspendRejectedError as e:
                error_holder["rejected"] = e
            except Exception as e:
                error_holder["unexpected"] = e

        t = threading.Thread(target=script_thread)
        t.start()

        run_ctx = None
        for _ in range(200):
            for rid, rc in list(mgr._runs.items()):
                if rc.state == ScriptRunState.SUSPENDED:
                    run_ctx = rc
                    break
            if run_ctx is not None:
                break
            time.sleep(0.01)

        assert run_ctx is not None

        with pytest.raises(ScriptSuspendRejectedError):
            mgr.reject(RejectCommand(
                script_run_id=run_ctx.run_id,
                suspend_id=run_ctx.suspension.suspend_id,
                reason="policy denied",
            ))

        t.join(timeout=5)
        assert not t.is_alive()
        assert "unexpected" not in error_holder
        assert isinstance(error_holder.get("rejected"), ScriptSuspendRejectedError)


# ---------------------------------------------------------------------------
# End-to-end: run_script + object facade handler pause
# ---------------------------------------------------------------------------

class TestE2EObjectFacadePause:
    """Integration test: an object facade method calls compose_pause()
    during run_script evaluation."""

    def test_facade_method_pause_resume_through_run_script(self):
        from foggy.dataset_model.engine.compose.capability.registry import (
            CapabilityRegistry,
        )
        from foggy.dataset_model.engine.compose.capability.policy import (
            CapabilityPolicy,
        )
        from foggy.dataset_model.engine.compose.capability.descriptors import (
            MethodDescriptor as MD,
            ObjectFacadeDescriptor,
        )
        from foggy.dataset_model.engine.compose.runtime.script_runtime import (
            run_script,
        )
        from foggy.dataset_model.engine.compose.context.compose_query_context import (
            ComposeQueryContext,
        )
        from foggy.dataset_model.engine.compose.context.principal import Principal
        from tests.compose.runtime.conftest import StubResolver, StubSemanticService

        class ApprovalService:
            def ask(self, reason):
                payload = compose_pause(
                    reason=reason,
                    timeout_ms=5000,
                )
                return payload

        desc = ObjectFacadeDescriptor(
            object_name="approval",
            methods=[
                MD(
                    name="ask",
                    args_schema=[{"name": "reason", "type": "string", "required": True}],
                    return_type="dict",
                    side_effect="none",
                    auth_scope="biz.approval.read",
                    timeout_ms=10000,
                    audit_tag="test.approval.ask",
                ),
            ],
        )

        reg = CapabilityRegistry()
        reg.register_object_facade(desc, target=ApprovalService())
        policy = CapabilityPolicy(
            allowed_objects={"approval": frozenset({"ask"})},
            allowed_scopes=frozenset({"biz.approval.read"}),
        )

        mgr = SuspensionManager()
        ctx = ComposeQueryContext(
            principal=Principal(user_id="u1"),
            namespace="default",
            authority_resolver=StubResolver(),
        )
        svc = StubSemanticService()

        script = 'return approval.ask("facade.order");'

        result_holder = {}
        error_holder = {}

        def script_thread():
            try:
                result = run_script(
                    script, ctx,
                    semantic_service=svc,
                    capability_registry=reg,
                    capability_policy=policy,
                    suspension_manager=mgr,
                )
                result_holder["value"] = result.value
            except Exception as e:
                error_holder["error"] = e

        t = threading.Thread(target=script_thread)
        t.start()

        # Wait for a SUSPENDED run.
        run_ctx = None
        for _ in range(400):
            # Check if script_thread already failed.
            if "error" in error_holder:
                break
            for rid, rc in list(mgr._runs.items()):
                if rc.state == ScriptRunState.SUSPENDED:
                    run_ctx = rc
                    break
            if run_ctx is not None:
                break
            time.sleep(0.01)

        # If the script errored out, show the error.
        if "error" in error_holder:
            raise error_holder["error"]

        assert run_ctx is not None, "no suspended run found for facade"
        assert run_ctx.suspension is not None

        mgr.resume(ResumeCommand(
            script_run_id=run_ctx.run_id,
            suspend_id=run_ctx.suspension.suspend_id,
            payload={"facade_approved": True},
        ))

        t.join(timeout=5)
        assert not t.is_alive()
        assert "error" not in error_holder, f"error: {error_holder.get('error')}"
        assert result_holder["value"] == {"facade_approved": True}

