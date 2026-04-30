"""Tests for ScriptRunState transitions (P2.1)."""

from __future__ import annotations
import pytest
from foggy.dataset_model.engine.compose.runtime.suspension import (
    ScriptRunContext, ScriptRunState, TERMINAL_STATES, VALID_TRANSITIONS,
)
from foggy.dataset_model.engine.compose.runtime.suspend_errors import (
    ScriptSuspendStateInvalidError,
)


class TestValidTransitions:
    def test_running_to_suspended(self):
        ctx = ScriptRunContext()
        ctx.transition(ScriptRunState.SUSPENDED)
        assert ctx.state == ScriptRunState.SUSPENDED

    def test_running_to_completed(self):
        ctx = ScriptRunContext()
        ctx.transition(ScriptRunState.COMPLETED)
        assert ctx.state == ScriptRunState.COMPLETED

    def test_running_to_aborted(self):
        ctx = ScriptRunContext()
        ctx.transition(ScriptRunState.ABORTED)
        assert ctx.state == ScriptRunState.ABORTED

    def test_suspended_to_running(self):
        ctx = ScriptRunContext()
        ctx.transition(ScriptRunState.SUSPENDED)
        ctx.transition(ScriptRunState.RUNNING)
        assert ctx.state == ScriptRunState.RUNNING

    def test_suspended_to_rejected(self):
        ctx = ScriptRunContext()
        ctx.transition(ScriptRunState.SUSPENDED)
        ctx.transition(ScriptRunState.REJECTED)
        assert ctx.state == ScriptRunState.REJECTED

    def test_suspended_to_timed_out(self):
        ctx = ScriptRunContext()
        ctx.transition(ScriptRunState.SUSPENDED)
        ctx.transition(ScriptRunState.TIMED_OUT)
        assert ctx.state == ScriptRunState.TIMED_OUT

    def test_suspended_to_aborted(self):
        ctx = ScriptRunContext()
        ctx.transition(ScriptRunState.SUSPENDED)
        ctx.transition(ScriptRunState.ABORTED)
        assert ctx.state == ScriptRunState.ABORTED


class TestTerminalStatesBlockAll:
    @pytest.mark.parametrize("terminal", list(TERMINAL_STATES))
    def test_terminal_to_running(self, terminal):
        ctx = ScriptRunContext(state=terminal)
        with pytest.raises(ScriptSuspendStateInvalidError):
            ctx.transition(ScriptRunState.RUNNING)

    @pytest.mark.parametrize("terminal", list(TERMINAL_STATES))
    def test_terminal_to_suspended(self, terminal):
        ctx = ScriptRunContext(state=terminal)
        with pytest.raises(ScriptSuspendStateInvalidError):
            ctx.transition(ScriptRunState.SUSPENDED)


class TestIllegalNonTerminal:
    def test_running_to_rejected(self):
        ctx = ScriptRunContext()
        with pytest.raises(ScriptSuspendStateInvalidError):
            ctx.transition(ScriptRunState.REJECTED)

    def test_running_to_running(self):
        ctx = ScriptRunContext()
        with pytest.raises(ScriptSuspendStateInvalidError):
            ctx.transition(ScriptRunState.RUNNING)

    def test_suspended_to_completed(self):
        ctx = ScriptRunContext()
        ctx.transition(ScriptRunState.SUSPENDED)
        with pytest.raises(ScriptSuspendStateInvalidError):
            ctx.transition(ScriptRunState.COMPLETED)


class TestTransitionTable:
    def test_every_state_has_entry(self):
        for state in ScriptRunState:
            assert state in VALID_TRANSITIONS

    def test_terminal_states_have_empty_transitions(self):
        for state in TERMINAL_STATES:
            assert VALID_TRANSITIONS[state] == frozenset()

    def test_terminal_states_count(self):
        assert len(TERMINAL_STATES) == 4

class TestTransitionErrorMessage:
    def test_error_mentions_states(self):
        ctx = ScriptRunContext()
        with pytest.raises(ScriptSuspendStateInvalidError, match="RUNNING"):
            ctx.transition(ScriptRunState.REJECTED)

    def test_error_code_is_correct(self):
        ctx = ScriptRunContext()
        try:
            ctx.transition(ScriptRunState.REJECTED)
        except ScriptSuspendStateInvalidError as exc:
            assert exc.code == "script/suspend-state-invalid"
