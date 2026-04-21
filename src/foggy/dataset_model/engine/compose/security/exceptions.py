"""Authority-resolution exception type.

Fail-closed: any violation of the M1 contract (missing binding, malformed
response, upstream failure, ir.rule unmapped field, principal mismatch, etc.)
must raise :class:`AuthorityResolutionError`. Callers do NOT catch to fall
back — they propagate and the Compose Query execution aborts.
"""

from __future__ import annotations

from typing import Optional

from . import error_codes


class AuthorityResolutionError(Exception):
    """Structured failure for authority resolution.

    Attributes
    ----------
    code:
        One of the ``error_codes`` namespace strings
        (``compose-authority-resolve/<kind>``). Validated on construction
        against :data:`error_codes.ALL_CODES`.
    model_involved:
        Optional. QM model name that triggered the failure; ``None`` when
        the failure is resolver-wide (e.g. ``resolver-not-available``).
    phase:
        String tag for the pipeline phase at which the failure surfaced.
        Defaults to ``authority-resolve``; validated against
        :data:`error_codes.VALID_PHASES`.

    Sanitisation
    ------------
    Constructors **must not** embed raw physical column names, raw
    ``ir.rule.domain_force`` text, or other users' identities in ``args[0]``.
    Upstream callers are expected to sanitise their messages before
    raising. (v1.3 already provides a sanitiser utility.)
    """

    def __init__(
        self,
        code: str,
        message: str,
        model_involved: Optional[str] = None,
        phase: str = error_codes.PHASE_AUTHORITY_RESOLVE,
        cause: Optional[BaseException] = None,
    ) -> None:
        if code not in error_codes.ALL_CODES:
            raise ValueError(
                f"AuthorityResolutionError.code must be one of ALL_CODES, "
                f"got {code!r}"
            )
        if phase not in error_codes.VALID_PHASES:
            raise ValueError(
                f"AuthorityResolutionError.phase must be one of VALID_PHASES, "
                f"got {phase!r}"
            )

        super().__init__(message)
        self.code = code
        self.model_involved = model_involved
        self.phase = phase
        if cause is not None:
            # PEP 3134 exception chaining — ``raise X from cause`` is the
            # idiomatic way, but we also accept cause via ctor for callers
            # that build the exception in a helper.
            self.__cause__ = cause

    def __repr__(self) -> str:
        return (
            f"AuthorityResolutionError(code={self.code!r}, "
            f"model_involved={self.model_involved!r}, phase={self.phase!r}, "
            f"message={self.args[0]!r})"
        )
