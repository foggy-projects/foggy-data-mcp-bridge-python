"""Tests for ``script/*`` error codes and exception hierarchy (P2.1)."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.runtime.suspend_errors import (
    ALL_SUSPEND_CODES,
    PAUSE_NOT_ALLOWED,
    PAUSE_NOT_IN_RUN,
    RESUME_PAYLOAD_INVALID,
    RESUME_TOKEN_INVALID,
    SUSPEND_LIMIT_EXCEEDED,
    SUSPEND_REJECTED,
    SUSPEND_STATE_INVALID,
    SUSPEND_TIMEOUT,
    ScriptPauseNotAllowedError,
    ScriptPauseNotInRunError,
    ScriptResumePayloadInvalidError,
    ScriptResumeTokenInvalidError,
    ScriptSuspendError,
    ScriptSuspendLimitExceededError,
    ScriptSuspendRejectedError,
    ScriptSuspendStateInvalidError,
    ScriptSuspendTimeoutError,
)


# ---------------------------------------------------------------------------
# Error code constants
# ---------------------------------------------------------------------------

class TestErrorCodeConstants:
    """Error code strings are stable and match the v1.9 spec."""

    def test_pause_not_in_run(self):
        assert PAUSE_NOT_IN_RUN == "script/pause-not-in-run"

    def test_pause_not_allowed(self):
        assert PAUSE_NOT_ALLOWED == "script/pause-not-allowed"

    def test_suspend_limit_exceeded(self):
        assert SUSPEND_LIMIT_EXCEEDED == "script/suspend-limit-exceeded"

    def test_suspend_timeout(self):
        assert SUSPEND_TIMEOUT == "script/suspend-timeout"

    def test_suspend_rejected(self):
        assert SUSPEND_REJECTED == "script/suspend-rejected"

    def test_resume_token_invalid(self):
        assert RESUME_TOKEN_INVALID == "script/resume-token-invalid"

    def test_resume_payload_invalid(self):
        assert RESUME_PAYLOAD_INVALID == "script/resume-payload-invalid"

    def test_suspend_state_invalid(self):
        assert SUSPEND_STATE_INVALID == "script/suspend-state-invalid"

    def test_all_codes_frozen_set(self):
        assert isinstance(ALL_SUSPEND_CODES, frozenset)
        assert len(ALL_SUSPEND_CODES) == 8

    def test_all_codes_contain_every_constant(self):
        expected = {
            PAUSE_NOT_IN_RUN,
            PAUSE_NOT_ALLOWED,
            SUSPEND_LIMIT_EXCEEDED,
            SUSPEND_TIMEOUT,
            SUSPEND_REJECTED,
            RESUME_TOKEN_INVALID,
            RESUME_PAYLOAD_INVALID,
            SUSPEND_STATE_INVALID,
        }
        assert ALL_SUSPEND_CODES == expected

    def test_all_codes_in_script_namespace(self):
        for code in ALL_SUSPEND_CODES:
            assert code.startswith("script/"), f"{code} not in script/ namespace"


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class TestScriptSuspendError:
    """Base error class contract."""

    def test_valid_code(self):
        err = ScriptSuspendError(SUSPEND_TIMEOUT, "test message")
        assert err.code == SUSPEND_TIMEOUT
        assert str(err) == "test message"

    def test_invalid_code_rejected(self):
        with pytest.raises(ValueError, match="ALL_SUSPEND_CODES"):
            ScriptSuspendError("capability/not-registered", "wrong namespace")

    def test_empty_code_rejected(self):
        with pytest.raises(ValueError, match="ALL_SUSPEND_CODES"):
            ScriptSuspendError("", "no code")

    def test_repr_sanitized(self):
        err = ScriptSuspendError(SUSPEND_REJECTED, "safe message")
        r = repr(err)
        assert "ScriptSuspendError" in r
        assert "script/suspend-rejected" in r
        assert "safe message" in r
        # Must not leak internal details.
        assert "Traceback" not in r
        assert "Thread" not in r

    def test_is_exception(self):
        err = ScriptSuspendError(PAUSE_NOT_IN_RUN, "test")
        assert isinstance(err, Exception)


# ---------------------------------------------------------------------------
# Concrete subclasses
# ---------------------------------------------------------------------------

_SUBCLASS_MAP = [
    (ScriptPauseNotInRunError, PAUSE_NOT_IN_RUN),
    (ScriptPauseNotAllowedError, PAUSE_NOT_ALLOWED),
    (ScriptSuspendLimitExceededError, SUSPEND_LIMIT_EXCEEDED),
    (ScriptSuspendTimeoutError, SUSPEND_TIMEOUT),
    (ScriptSuspendRejectedError, SUSPEND_REJECTED),
    (ScriptResumeTokenInvalidError, RESUME_TOKEN_INVALID),
    (ScriptResumePayloadInvalidError, RESUME_PAYLOAD_INVALID),
    (ScriptSuspendStateInvalidError, SUSPEND_STATE_INVALID),
]


class TestConcreteErrors:
    """Each subclass maps to the correct code and is catchable."""

    @pytest.mark.parametrize("cls,expected_code", _SUBCLASS_MAP)
    def test_default_message(self, cls, expected_code):
        err = cls()
        assert err.code == expected_code
        assert isinstance(err, ScriptSuspendError)
        assert isinstance(err, Exception)

    @pytest.mark.parametrize("cls,expected_code", _SUBCLASS_MAP)
    def test_custom_message(self, cls, expected_code):
        err = cls("custom")
        assert err.code == expected_code
        assert str(err) == "custom"

    @pytest.mark.parametrize("cls,_", _SUBCLASS_MAP)
    def test_catchable_as_base(self, cls, _):
        with pytest.raises(ScriptSuspendError):
            raise cls()

    def test_subclass_count_matches_codes(self):
        assert len(_SUBCLASS_MAP) == len(ALL_SUSPEND_CODES)
