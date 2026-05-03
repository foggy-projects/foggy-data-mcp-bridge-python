"""Tests for active suspension inspection APIs (v1.9.1 P0)."""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from foggy.dataset_model.engine.compose.runtime.suspend_errors import (
    ScriptSuspendRejectedError,
    ScriptSuspendTimeoutError,
)
from foggy.dataset_model.engine.compose.runtime.suspension import (
    PauseRequest,
    RejectCommand,
    ResumeCommand,
    ScriptRunContext,
    SuspensionResult,
)
from foggy.dataset_model.engine.compose.runtime.suspension_manager import (
    SuspensionManager,
)


def _pause(
    reason: str = "test.pause",
    *,
    summary: dict[str, Any] | None = None,
    timeout_ms: int = 5000,
) -> PauseRequest:
    return PauseRequest(
        reason=reason,
        summary=summary or {"k": "v"},
        timeout_ms=timeout_ms,
    )


def _wait_until(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition was not met before timeout")


def _start_paused_run(
    mgr: SuspensionManager,
    *,
    reason: str = "test.pause",
    summary: dict[str, Any] | None = None,
    timeout_ms: int = 5000,
) -> tuple[ScriptRunContext, threading.Thread, dict[str, Any]]:
    run_ctx = ScriptRunContext()
    mgr.register_run(run_ctx)
    holder: dict[str, Any] = {}

    def target() -> None:
        try:
            holder["payload"] = mgr.pause_and_wait(
                run_ctx.run_id,
                _pause(reason, summary=summary, timeout_ms=timeout_ms),
            )
        except Exception as exc:
            holder["error"] = exc

    thread = threading.Thread(target=target)
    thread.start()
    _wait_until(lambda: mgr.get_active_suspension(run_ctx.run_id) is not None)
    return run_ctx, thread, holder


def _resume(mgr: SuspensionManager, result: SuspensionResult) -> dict[str, Any]:
    return mgr.resume(ResumeCommand(
        script_run_id=result.script_run_id,
        suspend_id=result.suspend_id,
        payload={"approved": True},
    ))


class TestListAndGetActiveSuspensions:

    def test_list_empty_without_active_wait_slot(self) -> None:
        mgr = SuspensionManager()
        assert mgr.list_active_suspensions() == []

        run_ctx = ScriptRunContext()
        mgr.register_run(run_ctx)
        result = mgr.request_suspension(run_ctx.run_id, _pause())

        assert mgr.get_active_suspension(run_ctx.run_id) is None
        assert mgr.list_active_suspensions() == []
        mgr.resume(ResumeCommand(
            script_run_id=run_ctx.run_id,
            suspend_id=result.suspend_id,
            payload={},
        ))

    def test_list_and_get_single_active_suspension(self) -> None:
        mgr = SuspensionManager()
        run_ctx, thread, holder = _start_paused_run(
            mgr,
            reason="order.confirm",
            summary={"order_id": "O-1"},
        )
        try:
            active = mgr.list_active_suspensions()
            assert len(active) == 1
            assert active[0].script_run_id == run_ctx.run_id
            assert active[0].reason == "order.confirm"
            assert active[0].summary == {"order_id": "O-1"}

            by_id = mgr.get_active_suspension(run_ctx.run_id)
            assert by_id == active[0]
        finally:
            result = mgr.get_active_suspension(run_ctx.run_id)
            if result is not None:
                _resume(mgr, result)
            thread.join(timeout=2)
        assert "error" not in holder

    def test_list_multiple_active_suspensions(self) -> None:
        mgr = SuspensionManager()
        started = [
            _start_paused_run(mgr, reason="r1", summary={"idx": 1}),
            _start_paused_run(mgr, reason="r2", summary={"idx": 2}),
        ]
        try:
            active = mgr.list_active_suspensions()
            assert {item.reason for item in active} == {"r1", "r2"}
            assert {item.summary["idx"] for item in active} == {1, 2}
        finally:
            for run_ctx, thread, _holder in started:
                result = mgr.get_active_suspension(run_ctx.run_id)
                if result is not None:
                    _resume(mgr, result)
                thread.join(timeout=2)

    def test_get_unknown_returns_none(self) -> None:
        mgr = SuspensionManager()
        assert mgr.get_active_suspension("sr_missing") is None


class TestResolvedSuspensionsAreNotVisible:

    def test_resume_removes_from_active_query(self) -> None:
        mgr = SuspensionManager()
        run_ctx, thread, holder = _start_paused_run(mgr)
        result = mgr.get_active_suspension(run_ctx.run_id)
        assert result is not None

        assert _resume(mgr, result) == {"approved": True}
        thread.join(timeout=2)

        assert not thread.is_alive()
        assert "error" not in holder
        assert mgr.get_active_suspension(run_ctx.run_id) is None
        assert mgr.list_active_suspensions() == []

    def test_reject_removes_from_active_query(self) -> None:
        mgr = SuspensionManager()
        run_ctx, thread, holder = _start_paused_run(mgr)
        result = mgr.get_active_suspension(run_ctx.run_id)
        assert result is not None

        with pytest.raises(ScriptSuspendRejectedError):
            mgr.reject(RejectCommand(
                script_run_id=result.script_run_id,
                suspend_id=result.suspend_id,
                reason="denied",
            ))
        thread.join(timeout=2)

        assert not thread.is_alive()
        assert isinstance(holder["error"], ScriptSuspendRejectedError)
        assert mgr.get_active_suspension(run_ctx.run_id) is None
        assert mgr.list_active_suspensions() == []

    def test_timeout_removes_from_active_query(self) -> None:
        mgr = SuspensionManager()
        run_ctx, thread, holder = _start_paused_run(mgr)
        result = mgr.get_active_suspension(run_ctx.run_id)
        assert result is not None

        with pytest.raises(ScriptSuspendTimeoutError):
            mgr.timeout(result.script_run_id, result.suspend_id)
        thread.join(timeout=2)

        assert not thread.is_alive()
        assert isinstance(holder["error"], ScriptSuspendTimeoutError)
        assert mgr.get_active_suspension(run_ctx.run_id) is None
        assert mgr.list_active_suspensions() == []


class TestConcurrencyAndSnapshotSafety:

    def test_query_during_resume_and_reject_does_not_raise(self) -> None:
        mgr = SuspensionManager()
        run_resume, thread_resume, _holder_resume = _start_paused_run(
            mgr, reason="resume"
        )
        run_reject, thread_reject, _holder_reject = _start_paused_run(
            mgr, reason="reject"
        )
        errors: list[BaseException] = []
        stop = threading.Event()

        def query_loop() -> None:
            try:
                while not stop.is_set():
                    mgr.list_active_suspensions()
                    mgr.get_active_suspension(run_resume.run_id)
                    mgr.get_active_suspension(run_reject.run_id)
            except BaseException as exc:
                errors.append(exc)

        query_thread = threading.Thread(target=query_loop)
        query_thread.start()

        resume_result = mgr.get_active_suspension(run_resume.run_id)
        reject_result = mgr.get_active_suspension(run_reject.run_id)
        assert resume_result is not None
        assert reject_result is not None

        def reject() -> None:
            with pytest.raises(ScriptSuspendRejectedError):
                mgr.reject(RejectCommand(
                    script_run_id=reject_result.script_run_id,
                    suspend_id=reject_result.suspend_id,
                ))

        resume_thread = threading.Thread(
            target=lambda: _resume(mgr, resume_result)
        )
        reject_thread = threading.Thread(target=reject)
        resume_thread.start()
        reject_thread.start()
        resume_thread.join(timeout=2)
        reject_thread.join(timeout=2)
        stop.set()
        query_thread.join(timeout=2)
        thread_resume.join(timeout=2)
        thread_reject.join(timeout=2)

        assert errors == []
        assert mgr.get_active_suspension(run_resume.run_id) is None
        assert mgr.get_active_suspension(run_reject.run_id) is None

    def test_returned_snapshot_does_not_expose_internal_objects(self) -> None:
        mgr = SuspensionManager()
        run_ctx, thread, _holder = _start_paused_run(mgr)
        try:
            result = mgr.get_active_suspension(run_ctx.run_id)
            assert result is not None
            assert isinstance(result, SuspensionResult)
            assert set(result.__dict__) == {
                "type",
                "script_run_id",
                "suspend_id",
                "reason",
                "summary",
                "timeout_at",
            }
            assert "_WaitSlot" not in repr(result)
            assert "Event" not in repr(result)
            assert "Timer" not in repr(result)
            assert "lock" not in repr(result).lower()
            assert "thread" not in repr(result).lower()
        finally:
            result = mgr.get_active_suspension(run_ctx.run_id)
            if result is not None:
                _resume(mgr, result)
            thread.join(timeout=2)

    def test_mutating_returned_summary_does_not_affect_manager_state(self) -> None:
        mgr = SuspensionManager()
        run_ctx, thread, _holder = _start_paused_run(
            mgr,
            summary={"nested": {"approved": False}},
        )
        try:
            first = mgr.get_active_suspension(run_ctx.run_id)
            assert first is not None
            first.summary["nested"]["approved"] = True

            second = mgr.get_active_suspension(run_ctx.run_id)
            assert second is not None
            assert second.summary == {"nested": {"approved": False}}
        finally:
            result = mgr.get_active_suspension(run_ctx.run_id)
            if result is not None:
                _resume(mgr, result)
            thread.join(timeout=2)


class TestOnSuspendedCallback:

    def test_callback_runs_after_registration_outside_lock_with_snapshot(
        self,
    ) -> None:
        callback_seen = threading.Event()
        callback_results: list[SuspensionResult] = []

        def on_suspended(result: SuspensionResult) -> None:
            callback_results.append(result)
            assert mgr.get_active_suspension(result.script_run_id) is not None
            acquired = mgr._lock.acquire(blocking=False)
            assert acquired
            mgr._lock.release()
            result.summary["k"] = "changed"
            callback_seen.set()

        mgr = SuspensionManager(on_suspended=on_suspended)
        run_ctx, thread, _holder = _start_paused_run(mgr)
        try:
            assert callback_seen.wait(timeout=2)
            assert len(callback_results) == 1
            active = mgr.get_active_suspension(run_ctx.run_id)
            assert active is not None
            assert active.summary == {"k": "v"}
        finally:
            result = mgr.get_active_suspension(run_ctx.run_id)
            if result is not None:
                _resume(mgr, result)
            thread.join(timeout=2)

    def test_callback_exception_does_not_break_query_or_resume(self) -> None:
        called = threading.Event()

        def on_suspended(_result: SuspensionResult) -> None:
            called.set()
            raise RuntimeError("publish failed")

        mgr = SuspensionManager(on_suspended=on_suspended)
        run_ctx, thread, holder = _start_paused_run(mgr)
        assert called.wait(timeout=2)

        result = mgr.get_active_suspension(run_ctx.run_id)
        assert result is not None
        _resume(mgr, result)
        thread.join(timeout=2)

        assert not thread.is_alive()
        assert "error" not in holder
        assert holder["payload"] == {"approved": True}

    def test_callback_can_resume_immediately_without_lost_wakeup(self) -> None:
        def on_suspended(result: SuspensionResult) -> None:
            mgr.resume(ResumeCommand(
                script_run_id=result.script_run_id,
                suspend_id=result.suspend_id,
                payload={"from_callback": True},
            ))

        mgr = SuspensionManager(on_suspended=on_suspended)
        run_ctx = ScriptRunContext()
        mgr.register_run(run_ctx)
        holder: dict[str, Any] = {}

        def target() -> None:
            try:
                holder["payload"] = mgr.pause_and_wait(
                    run_ctx.run_id,
                    _pause(),
                )
            except Exception as exc:
                holder["error"] = exc

        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout=2)

        assert not thread.is_alive()
        assert "error" not in holder
        assert holder["payload"] == {"from_callback": True}
        assert mgr.get_active_suspension(run_ctx.run_id) is None
