"""Tests for suspension data models — serialization, validation (P2.1)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from foggy.dataset_model.engine.compose.runtime.suspension import (
    MAX_TIMEOUT_MS,
    PauseRequest,
    RejectCommand,
    ResumeCommand,
    ScriptRunContext,
    ScriptRunState,
    SuspensionResult,
    generate_run_id,
    generate_suspend_id,
)


# ---------------------------------------------------------------------------
# ID generators
# ---------------------------------------------------------------------------

class TestIdGenerators:

    def test_run_id_format(self):
        rid = generate_run_id()
        assert rid.startswith("sr_")
        assert len(rid) == 15  # "sr_" + 12 hex chars

    def test_suspend_id_format(self):
        sid = generate_suspend_id()
        assert sid.startswith("sp_")
        assert len(sid) == 15

    def test_run_ids_unique(self):
        ids = {generate_run_id() for _ in range(100)}
        assert len(ids) == 100

    def test_suspend_ids_unique(self):
        ids = {generate_suspend_id() for _ in range(100)}
        assert len(ids) == 100


# ---------------------------------------------------------------------------
# PauseRequest
# ---------------------------------------------------------------------------

class TestPauseRequest:

    def test_valid_construction(self):
        req = PauseRequest(
            reason="order.close",
            summary={"app_id": "A1"},
            timeout_ms=60_000,
        )
        assert req.reason == "order.close"
        assert req.summary == {"app_id": "A1"}
        assert req.timeout_ms == 60_000
        assert req.resume_schema is None
        assert req.audit_tag is None

    def test_with_optional_fields(self):
        req = PauseRequest(
            reason="test",
            summary={},
            timeout_ms=1000,
            resume_schema={"type": "object"},
            audit_tag="trace-123",
        )
        assert req.resume_schema == {"type": "object"}
        assert req.audit_tag == "trace-123"

    def test_empty_reason_rejected(self):
        with pytest.raises(Exception, match="non-empty"):
            PauseRequest(reason="", summary={}, timeout_ms=1000)

    def test_whitespace_reason_rejected(self):
        with pytest.raises(Exception, match="non-empty"):
            PauseRequest(reason="   ", summary={}, timeout_ms=1000)

    def test_zero_timeout_rejected(self):
        with pytest.raises(Exception, match="must be > 0"):
            PauseRequest(reason="r", summary={}, timeout_ms=0)

    def test_negative_timeout_rejected(self):
        with pytest.raises(Exception, match="must be > 0"):
            PauseRequest(reason="r", summary={}, timeout_ms=-100)

    def test_timeout_exceeds_max_rejected(self):
        with pytest.raises(Exception, match=str(MAX_TIMEOUT_MS)):
            PauseRequest(
                reason="r", summary={}, timeout_ms=MAX_TIMEOUT_MS + 1
            )

    def test_timeout_at_max_accepted(self):
        req = PauseRequest(
            reason="r", summary={}, timeout_ms=MAX_TIMEOUT_MS
        )
        assert req.timeout_ms == MAX_TIMEOUT_MS

    def test_non_serializable_summary_rejected(self):
        """Host objects in summary must be rejected."""
        with pytest.raises(Exception, match="JSON-serializable"):
            PauseRequest(
                reason="r",
                summary={"bad": object()},
                timeout_ms=1000,
            )

    def test_frozen(self):
        req = PauseRequest(reason="r", summary={}, timeout_ms=1000)
        with pytest.raises(Exception):
            req.reason = "changed"  # type: ignore[misc]

    def test_json_round_trip(self):
        req = PauseRequest(
            reason="order.close",
            summary={"id": 42, "nested": {"ok": True}},
            timeout_ms=5000,
        )
        data = json.loads(req.model_dump_json())
        assert data["reason"] == "order.close"
        assert data["summary"]["nested"]["ok"] is True
        assert data["timeout_ms"] == 5000


# ---------------------------------------------------------------------------
# SuspensionResult
# ---------------------------------------------------------------------------

class TestSuspensionResult:

    def _make(self) -> SuspensionResult:
        return SuspensionResult(
            script_run_id="sr_aabbccddeeff",
            suspend_id="sp_112233445566",
            reason="order.close",
            summary={"app": "1"},
            timeout_at=datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc),
        )

    def test_construction(self):
        r = self._make()
        assert r.type == "script_suspended"
        assert r.script_run_id == "sr_aabbccddeeff"
        assert r.suspend_id == "sp_112233445566"

    def test_json_no_host_objects(self):
        r = self._make()
        data = json.loads(r.model_dump_json())
        assert data["type"] == "script_suspended"
        assert "thread" not in json.dumps(data).lower()
        assert "handler" not in json.dumps(data).lower()

    def test_frozen(self):
        r = self._make()
        with pytest.raises(Exception):
            r.type = "modified"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ResumeCommand
# ---------------------------------------------------------------------------

class TestResumeCommand:

    def test_valid(self):
        cmd = ResumeCommand(
            script_run_id="sr_a",
            suspend_id="sp_b",
            payload={"approved": True},
        )
        assert cmd.payload == {"approved": True}

    def test_json_round_trip(self):
        cmd = ResumeCommand(
            script_run_id="sr_a",
            suspend_id="sp_b",
            payload={"k": "v"},
        )
        data = json.loads(cmd.model_dump_json())
        assert data["payload"]["k"] == "v"

    def test_non_serializable_payload_rejected(self):
        with pytest.raises(Exception, match="JSON-serializable"):
            ResumeCommand(
                script_run_id="sr_a",
                suspend_id="sp_b",
                payload={"bad": object()},
            )

    def test_frozen(self):
        cmd = ResumeCommand(
            script_run_id="sr_a",
            suspend_id="sp_b",
            payload={},
        )
        with pytest.raises(Exception):
            cmd.payload = {"x": 1}  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RejectCommand
# ---------------------------------------------------------------------------

class TestRejectCommand:

    def test_with_reason(self):
        cmd = RejectCommand(
            script_run_id="sr_a",
            suspend_id="sp_b",
            reason="operator denied",
        )
        assert cmd.reason == "operator denied"

    def test_without_reason(self):
        cmd = RejectCommand(
            script_run_id="sr_a",
            suspend_id="sp_b",
        )
        assert cmd.reason is None

    def test_json_round_trip(self):
        cmd = RejectCommand(
            script_run_id="sr_a",
            suspend_id="sp_b",
            reason="denied",
        )
        data = json.loads(cmd.model_dump_json())
        assert data["reason"] == "denied"


# ---------------------------------------------------------------------------
# ScriptRunContext
# ---------------------------------------------------------------------------

class TestScriptRunContext:

    def test_default_state_is_running(self):
        ctx = ScriptRunContext()
        assert ctx.state == ScriptRunState.RUNNING

    def test_auto_generated_run_id(self):
        ctx = ScriptRunContext()
        assert ctx.run_id.startswith("sr_")

    def test_created_at_is_utc(self):
        ctx = ScriptRunContext()
        assert ctx.created_at.tzinfo is not None

    def test_suspension_initially_none(self):
        ctx = ScriptRunContext()
        assert ctx.suspension is None

    def test_is_terminal_false_for_running(self):
        ctx = ScriptRunContext()
        assert ctx.is_terminal is False

    def test_is_terminal_true_for_completed(self):
        ctx = ScriptRunContext()
        ctx.transition(ScriptRunState.COMPLETED)
        assert ctx.is_terminal is True
