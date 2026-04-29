"""Structured capability error hierarchy for v1.7.

Error codes align with the usage manual §Error Codes.  Messages are
sanitized: no module paths, host object repr, physical table/column
details, principal, resolver, semantic service, or context details.

All errors are subclasses of :class:`CapabilityError` so callers can
catch the family in a single handler.
"""

from __future__ import annotations

from typing import Optional


# ---------------------------------------------------------------------------
# Error codes — frozen strings, must match Java when Java aligns.
# ---------------------------------------------------------------------------

CAPABILITY_NOT_REGISTERED = "capability/not-registered"
CAPABILITY_NOT_ALLOWED = "capability/not-allowed"
CAPABILITY_INVALID_DESCRIPTOR = "capability/invalid-descriptor"
CAPABILITY_UNSUPPORTED_DIALECT = "capability/unsupported-dialect"
CAPABILITY_METHOD_NOT_DECLARED = "capability/method-not-declared"
CAPABILITY_SIDE_EFFECT_DENIED = "capability/side-effect-denied"
CAPABILITY_RETURN_TYPE_DENIED = "capability/return-type-denied"
CAPABILITY_TIMEOUT = "capability/timeout"

ALL_CAPABILITY_CODES: frozenset[str] = frozenset({
    CAPABILITY_NOT_REGISTERED,
    CAPABILITY_NOT_ALLOWED,
    CAPABILITY_INVALID_DESCRIPTOR,
    CAPABILITY_UNSUPPORTED_DIALECT,
    CAPABILITY_METHOD_NOT_DECLARED,
    CAPABILITY_SIDE_EFFECT_DENIED,
    CAPABILITY_RETURN_TYPE_DENIED,
    CAPABILITY_TIMEOUT,
})


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class CapabilityError(Exception):
    """Base for all capability registry errors.

    Attributes
    ----------
    code:
        One of the ``CAPABILITY_*`` constants above.
    """

    def __init__(self, code: str, message: str) -> None:
        if code not in ALL_CAPABILITY_CODES:
            raise ValueError(
                f"CapabilityError.code must be one of ALL_CAPABILITY_CODES, "
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

class CapabilityNotRegisteredError(CapabilityError):
    """Function or object not registered in the capability registry."""

    def __init__(self, message: str) -> None:
        super().__init__(CAPABILITY_NOT_REGISTERED, message)


class CapabilityNotAllowedError(CapabilityError):
    """Capability is registered but current policy does not allow it."""

    def __init__(self, message: str) -> None:
        super().__init__(CAPABILITY_NOT_ALLOWED, message)


class CapabilityInvalidDescriptorError(CapabilityError):
    """Descriptor fields are invalid or incomplete."""

    def __init__(self, message: str) -> None:
        super().__init__(CAPABILITY_INVALID_DESCRIPTOR, message)


class CapabilityUnsupportedDialectError(CapabilityError):
    """SQL function does not support the current dialect."""

    def __init__(self, message: str) -> None:
        super().__init__(CAPABILITY_UNSUPPORTED_DIALECT, message)


class CapabilityMethodNotDeclaredError(CapabilityError):
    """Object facade method not declared in the descriptor."""

    def __init__(self, message: str) -> None:
        super().__init__(CAPABILITY_METHOD_NOT_DECLARED, message)


class CapabilitySideEffectDeniedError(CapabilityError):
    """Descriptor or handler declares / exhibits side effects."""

    def __init__(self, message: str) -> None:
        super().__init__(CAPABILITY_SIDE_EFFECT_DENIED, message)


class CapabilityReturnTypeDeniedError(CapabilityError):
    """Return value type is not in the allowed set."""

    def __init__(self, message: str) -> None:
        super().__init__(CAPABILITY_RETURN_TYPE_DENIED, message)


class CapabilityTimeoutError(CapabilityError):
    """Object facade method exceeded timeout."""

    def __init__(self, message: str) -> None:
        super().__init__(CAPABILITY_TIMEOUT, message)
