"""``ComposeSandboxViolationError`` — structured three-layer sandbox error.

Fail-closed: any violation raised by the sandbox enforcement pipeline
(Layer A script host, Layer B DSL expression, Layer C QueryPlan verb)
must instantiate this class with a valid ``code`` + ``phase``. Callers
propagate; they do not catch-and-continue.
"""

from __future__ import annotations

from typing import Optional

from . import error_codes


class ComposeSandboxViolationError(Exception):
    """Structured failure for any Compose Query sandbox violation.

    Attributes
    ----------
    code:
        One of ``error_codes.ALL_CODES``. Validated on construction.
    layer:
        ``"A"`` / ``"B"`` / ``"C"`` — derived from ``code`` at
        construction; kept as an attribute for ergonomic test assertions.
    kind:
        The trailing segment of ``code`` (e.g. ``"eval-denied"``).
        Like ``layer``, derived once at construction.
    phase:
        Pipeline phase (``"script-parse"``, ``"script-eval"``,
        ``"plan-build"``, etc.). Validated against
        :data:`error_codes.VALID_PHASES`.
    script_location:
        Optional ``(line, column)`` tuple pointing to the offending
        source position. Not required; set when the host can produce it
        cheaply.

    Sanitisation
    ------------
    Error messages must not embed raw QM physical column names, raw
    ``ir.rule.domain_force`` text, other users' identifiers, or verbatim
    snippets of the user script beyond what's needed to disambiguate.
    Keep ``args[0]`` developer-facing and redacted.
    """

    def __init__(
        self,
        code: str,
        message: str,
        phase: str,
        script_location: Optional[tuple] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        if code not in error_codes.ALL_CODES:
            raise ValueError(
                f"ComposeSandboxViolationError.code must be one of "
                f"error_codes.ALL_CODES, got {code!r}"
            )
        if phase not in error_codes.VALID_PHASES:
            raise ValueError(
                f"ComposeSandboxViolationError.phase must be one of "
                f"error_codes.VALID_PHASES, got {phase!r}"
            )

        super().__init__(message)
        self.code = code
        # Derived once; callers don't have to reparse the code string.
        self.layer = error_codes.layer_of(code)
        self.kind = error_codes.kind_of(code)
        self.phase = phase
        self.script_location = script_location
        if cause is not None:
            self.__cause__ = cause

    def __repr__(self) -> str:
        loc = f", loc={self.script_location!r}" if self.script_location else ""
        return (
            f"ComposeSandboxViolationError(code={self.code!r}, "
            f"layer={self.layer!r}, kind={self.kind!r}, phase={self.phase!r}"
            f"{loc}, message={self.args[0]!r})"
        )
