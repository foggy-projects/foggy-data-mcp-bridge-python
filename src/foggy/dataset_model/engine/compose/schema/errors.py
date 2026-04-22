"""``ComposeSchemaError`` — structured failure for schema derivation.

See :mod:`foggy.dataset_model.engine.compose.schema.error_codes` for the
frozen code catalogue and its cross-language parity contract.
"""

from __future__ import annotations

from typing import Optional

from . import error_codes


class ComposeSchemaError(Exception):
    """Raised when :func:`derive_schema` cannot complete due to a
    structural (non-security) defect in the plan tree.

    Attributes
    ----------
    code:
        One of :data:`error_codes.ALL_CODES`. Validated on construction.
    phase:
        ``plan-build`` or ``schema-derive`` — helps error sinks decide
        which stage of the pipeline produced the failure. Validated
        against :data:`error_codes.VALID_PHASES`.
    plan_path:
        Optional human-readable path into the plan tree (e.g.
        ``"union/left/query/2"``). Schema validation often happens deep
        inside a tree; this makes the failure message actionable.
    offending_field:
        Optional field / alias / model name that caused the failure.
        Used by tests and by the error-sink UI to highlight the
        offender.

    Sanitisation
    ------------
    Like other compose errors, messages must not embed raw QM physical
    column names or ``ir.rule.domain_force`` text. Schema derivation
    runs *before* authority binding, so in practice only user-written
    aliases / model names / column references appear here — but callers
    should still keep messages developer-facing and concise.
    """

    def __init__(
        self,
        code: str,
        message: str,
        phase: str = error_codes.PHASE_SCHEMA_DERIVE,
        plan_path: Optional[str] = None,
        offending_field: Optional[str] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        if code not in error_codes.ALL_CODES:
            raise ValueError(
                f"ComposeSchemaError.code must be one of "
                f"error_codes.ALL_CODES, got {code!r}"
            )
        if phase not in error_codes.VALID_PHASES:
            raise ValueError(
                f"ComposeSchemaError.phase must be one of "
                f"error_codes.VALID_PHASES, got {phase!r}"
            )

        super().__init__(message)
        self.code = code
        self.phase = phase
        self.plan_path = plan_path
        self.offending_field = offending_field
        if cause is not None:
            self.__cause__ = cause

    def __repr__(self) -> str:
        extras: list = []
        if self.plan_path:
            extras.append(f"plan_path={self.plan_path!r}")
        if self.offending_field:
            extras.append(f"offending_field={self.offending_field!r}")
        extra = (", " + ", ".join(extras)) if extras else ""
        return (
            f"ComposeSchemaError(code={self.code!r}, phase={self.phase!r}"
            f"{extra}, message={self.args[0]!r})"
        )
