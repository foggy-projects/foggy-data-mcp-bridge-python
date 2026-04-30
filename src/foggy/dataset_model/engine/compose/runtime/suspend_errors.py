"""Structured error hierarchy for v1.9 script suspend / resume.

Error codes live in the ``script/*`` namespace, separate from the
``capability/*`` codes in :mod:`capability.errors`.  Messages are
sanitized: no module paths, host object repr, thread details,
principal, resolver, semantic service, or context details.

All errors are subclasses of :class:`ScriptSuspendError` so callers can
catch the family in a single handler.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Error codes — frozen strings, must match Java when Java aligns.
# ---------------------------------------------------------------------------

PAUSE_NOT_IN_RUN = "script/pause-not-in-run"
PAUSE_NOT_ALLOWED = "script/pause-not-allowed"
SUSPEND_LIMIT_EXCEEDED = "script/suspend-limit-exceeded"
SUSPEND_TIMEOUT = "script/suspend-timeout"
SUSPEND_REJECTED = "script/suspend-rejected"
RESUME_TOKEN_INVALID = "script/resume-token-invalid"
RESUME_PAYLOAD_INVALID = "script/resume-payload-invalid"
SUSPEND_STATE_INVALID = "script/suspend-state-invalid"

ALL_SUSPEND_CODES: frozenset[str] = frozenset({
    PAUSE_NOT_IN_RUN,
    PAUSE_NOT_ALLOWED,
    SUSPEND_LIMIT_EXCEEDED,
    SUSPEND_TIMEOUT,
    SUSPEND_REJECTED,
    RESUME_TOKEN_INVALID,
    RESUME_PAYLOAD_INVALID,
    SUSPEND_STATE_INVALID,
})


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class ScriptSuspendError(Exception):
    """Base for all script suspend / resume errors.

    Attributes
    ----------
    code:
        One of the ``script/*`` constants above.
    """

    def __init__(self, code: str, message: str) -> None:
        if code not in ALL_SUSPEND_CODES:
            raise ValueError(
                f"ScriptSuspendError.code must be one of ALL_SUSPEND_CODES, "
                f"got {code!r}"
            )
        super().__init__(message)
        self.code = code

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(code={self.code!r}, "
            f"message={self.args[0]!r})"
        )


# ---------------------------------------------------------------------------
# Concrete subclasses
# ---------------------------------------------------------------------------

class ScriptPauseNotInRunError(ScriptSuspendError):
    """pause() called outside a FSScript run context."""

    def __init__(self, message: str = "pause is not allowed outside a script run") -> None:
        super().__init__(PAUSE_NOT_IN_RUN, message)


class ScriptPauseNotAllowedError(ScriptSuspendError):
    """Current policy does not allow script-visible pause."""

    def __init__(self, message: str = "pause is not allowed by current policy") -> None:
        super().__init__(PAUSE_NOT_ALLOWED, message)


class ScriptSuspendLimitExceededError(ScriptSuspendError):
    """Suspend count or resource quota exceeded."""

    def __init__(self, message: str = "suspend limit exceeded") -> None:
        super().__init__(SUSPEND_LIMIT_EXCEEDED, message)


class ScriptSuspendTimeoutError(ScriptSuspendError):
    """Pause timed out — auto-rejected."""

    def __init__(self, message: str = "suspend timed out") -> None:
        super().__init__(SUSPEND_TIMEOUT, message)


class ScriptSuspendRejectedError(ScriptSuspendError):
    """Upstream explicitly rejected the suspension."""

    def __init__(self, message: str = "suspend rejected") -> None:
        super().__init__(SUSPEND_REJECTED, message)


class ScriptResumeTokenInvalidError(ScriptSuspendError):
    """Resume command does not match the current suspension."""

    def __init__(self, message: str = "resume token does not match active suspension") -> None:
        super().__init__(RESUME_TOKEN_INVALID, message)


class ScriptResumePayloadInvalidError(ScriptSuspendError):
    """Resume payload fails schema validation."""

    def __init__(self, message: str = "resume payload is invalid") -> None:
        super().__init__(RESUME_PAYLOAD_INVALID, message)


class ScriptSuspendStateInvalidError(ScriptSuspendError):
    """Suspension is in a terminal state and cannot be resumed / rejected."""

    def __init__(self, message: str = "suspension is in a terminal or invalid state") -> None:
        super().__init__(SUSPEND_STATE_INVALID, message)
