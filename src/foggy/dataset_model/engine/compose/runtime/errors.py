"""Structured runtime error for Compose Query M7 script execution.

``ScriptRuntimeError`` wraps M1–M6 family exceptions with a light shell so
MCP-layer callers can branch on ``phase`` / ``error_code`` without importing
every upstream module. Original exceptions are always preserved on
``__cause__``.

Design notes
------------
* M7 does NOT introduce new ``compose-*-error/*`` namespace codes — the
  ``error_code`` attribute is whatever upstream assigned (or an M7-only
  plain-text tag like ``host-misconfig`` / ``internal-error`` when the
  failure is purely a host configuration bug).
* ``phase`` follows spec §错误模型规划 — one of ``permission-resolve`` /
  ``schema-derive`` / ``compile`` / ``execute`` / ``internal``. It maps
  the upstream exception family to the 4 user-facing phase buckets plus
  an ``internal`` bucket for pure host bugs.
* ``script_location`` is optional ``(line, column)`` when available from
  an upstream sandbox violation; otherwise ``None``.
"""

from __future__ import annotations

from typing import Optional, Tuple


class ScriptRuntimeError(Exception):
    """Light structured wrapper over any compose script-execution failure.

    The runtime rarely RAISES this directly; it mostly lets upstream
    structured exceptions propagate. This class exists for the ~1 case
    where a host-configuration bug is caught and surfaced as a plain
    ``internal`` error (see §7.5 in the M7 execution prompt).

    Attributes
    ----------
    error_code:
        Upstream code (``compose-compile-error/*`` / ``compose-sandbox-violation/*``
        / ``authority-resolution-error/*``) **or** an M7-only tag
        (``host-misconfig`` / ``internal-error``).
    phase:
        One of ``permission-resolve`` / ``schema-derive`` / ``compile`` /
        ``execute`` / ``internal``.
    model:
        Optional QM name when the error is model-scoped (e.g.
        ``MISSING_BINDING`` → the model whose binding was missing).
    script_location:
        Optional ``(line, column)`` — passed through from sandbox layer
        errors.
    """

    __slots__ = ("error_code", "phase", "model", "script_location")

    def __init__(
        self,
        error_code: str,
        phase: str,
        message: str,
        *,
        model: Optional[str] = None,
        script_location: Optional[Tuple[int, int]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.phase = phase
        self.model = model
        self.script_location = script_location
        if cause is not None:
            self.__cause__ = cause

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (
            f"ScriptRuntimeError(error_code={self.error_code!r}, "
            f"phase={self.phase!r}, model={self.model!r}, "
            f"message={self.args[0]!r})"
        )
