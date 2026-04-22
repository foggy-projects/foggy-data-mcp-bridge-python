"""Exception type raised by the Compose Query SQL compiler (M6).

Mirrors the shape pattern already used by :class:`AuthorityResolutionError`
(M5) and :class:`ComposeSchemaError` (M4): a single exception class with
a structured ``code`` / ``phase`` pair. Callers discriminate on ``code``
rather than subclass, to keep the error surface flat and to let Java
(``ComposeCompileException``) mirror 1:1.
"""
from __future__ import annotations

from foggy.dataset_model.engine.compose.compilation import error_codes
from foggy.dataset_model.engine.compose.compilation.error_codes import (
    CompilePhase,
)


class ComposeCompileError(Exception):
    """Raised when Compose Query SQL compilation fails.

    Construct with one of the 4 codes from :mod:`error_codes`; typos are
    rejected at construction time so tests can't silently assert the
    wrong string.

    Attributes
    ----------
    code:
        One of ``error_codes.ALL_CODES`` (4 full ``compose-compile-error/*``
        strings). Never just the ``NAMESPACE`` prefix.
    phase:
        ``"plan-lower"`` for structural errors before SQL gen, or
        ``"compile"`` for failures during SQL gen. Matches the phase
        labels used by the upstream M3/M5 error types.
    message:
        Human-readable detail. Never parsed programmatically — callers
        should match on ``code``.
    """

    def __init__(
        self,
        *,
        code: str,
        phase: CompilePhase,
        message: str,
    ) -> None:
        if not error_codes.is_valid_code(code):
            raise ValueError(
                f"Invalid ComposeCompileError code {code!r}; "
                f"must be one of {sorted(error_codes.ALL_CODES)}"
            )
        if not error_codes.is_valid_phase(phase):
            raise ValueError(
                f"Invalid ComposeCompileError phase {phase!r}; "
                f"must be one of {sorted(error_codes.VALID_PHASES)}"
            )
        self.code = code
        self.phase = phase
        self.message = message
        super().__init__(f"[{code}] ({phase}) {message}")

    def __repr__(self) -> str:  # pragma: no cover — debug formatting
        return (
            f"ComposeCompileError(code={self.code!r}, "
            f"phase={self.phase!r}, message={self.message!r})"
        )
