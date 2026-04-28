"""Error-code constants for Compose Query SQL compilation (M6).

r3 shape: **4 codes + 1 NAMESPACE constant** = 5 module-level constants.
Tests should assert ``NAMESPACE`` separately from the 4 full code
strings — see M6 execution prompt §错误码表 and §验收硬门槛 #3.

Phase labels (used by :class:`ComposeCompileError.phase`):
  - ``"plan-lower"`` — structural validation before SQL generation
  - ``"compile"`` — SQL generation through v1.3 ``_build_query``

These error codes intentionally do NOT overlap with
``compose-sandbox-violation/*`` (M3), ``compose-schema-error/*`` (M4),
or ``compose-authority-resolve/*`` (M1/M5). Errors from those phases are
propagated untouched by M6 — see spec §错误模型规划.
"""
from __future__ import annotations

from typing import FrozenSet, Literal

#: Type alias for the ``phase`` field on :class:`ComposeCompileError`.
#: Runtime validation lives in :func:`is_valid_phase` — this alias is
#: purely a signal to static type-checkers and IDE tooling.
CompilePhase = Literal["plan-lower", "compile"]

# ---------------------------------------------------------------------------
# Namespace (shared prefix for all 4 error codes below)
# ---------------------------------------------------------------------------

NAMESPACE: str = "compose-compile-error"
"""Top-level namespace shared by every M6 compile error code.

This is NOT itself a usable code — `ComposeCompileError.code` always
carries one of the 4 full strings below.
"""


# ---------------------------------------------------------------------------
# 4 error codes — full ``<namespace>/<kind>`` strings
# ---------------------------------------------------------------------------

UNSUPPORTED_PLAN_SHAPE: str = "compose-compile-error/unsupported-plan-shape"
"""The incoming QueryPlan tree uses a shape that this milestone does
not compile. Examples:
  - ``JoinPlan(type='full')`` against a SQLite target
  - Nested derivation depth > ``MAX_PLAN_DEPTH`` (DOS guard, r3)
  - A plan node whose ``QueryPlan`` subclass is unrecognised
"""

CROSS_DATASOURCE_REJECTED: str = "compose-compile-error/cross-datasource-rejected"
"""Union / join operands come from different data sources. M6 leaves
real detection to post-M6 follow-up F-7 — the ``ModelBinding`` and
``ModelInfoProvider`` contracts do not yet carry a datasource identity
field. This code is **defined** in M6 so call sites that want to raise
it programmatically have a stable constant, but the compiler does not
raise it by itself on live plans.
"""

MISSING_BINDING: str = "compose-compile-error/missing-binding"
"""An authority ``ModelBinding`` was expected for a ``BaseModelPlan.model``
but the ``bindings`` dict does not contain that key. In normal flow the
M5 resolver would have already failed with its own ``compose-authority-
resolve/model-binding-missing`` code; reaching this branch means either
the caller passed a hand-rolled ``bindings=...`` with gaps, or the QM
was not registered with the ``SemanticQueryService``.
"""

PER_BASE_COMPILE_FAILED: str = "compose-compile-error/per-base-compile-failed"
"""``SemanticQueryService._build_query`` raised while compiling a
``BaseModelPlan``. The original exception is kept on ``__cause__``; the
M6 wrapper only adds enough context (model name, QM shape) to route
the error without forcing callers to parse v1.3 engine stacks.
"""

# S7a — Relation cannot be wrapped for the target dialect.
RELATION_WRAP_UNSUPPORTED: str = "compose-compile-error/relation-wrap-unsupported"

# S7a — Relation contains inner CTE that cannot be hoisted for the target dialect.
RELATION_CTE_HOIST_UNSUPPORTED: str = "compose-compile-error/relation-cte-hoist-unsupported"

# S7a — Relation and outer plan target different datasources.
RELATION_DATASOURCE_MISMATCH: str = "compose-compile-error/relation-datasource-mismatch"


# ---------------------------------------------------------------------------
# Public registries
# ---------------------------------------------------------------------------

#: Immutable set of the 4 full error-code strings. Tests assert
#: ``len(ALL_CODES) == 4`` (NAMESPACE is excluded by design).
ALL_CODES: FrozenSet[str] = frozenset({
    UNSUPPORTED_PLAN_SHAPE,
    CROSS_DATASOURCE_REJECTED,
    MISSING_BINDING,
    PER_BASE_COMPILE_FAILED,
    RELATION_WRAP_UNSUPPORTED,
    RELATION_CTE_HOIST_UNSUPPORTED,
    RELATION_DATASOURCE_MISMATCH,
})

#: Valid phase labels carried by :class:`ComposeCompileError.phase`.
VALID_PHASES: FrozenSet[str] = frozenset({"plan-lower", "compile"})


def is_valid_code(code: str) -> bool:
    """Return True iff ``code`` is one of the 4 registered compile codes.

    Used by :class:`ComposeCompileError.__init__` to fail-closed on typos.
    """
    return code in ALL_CODES


def is_valid_phase(phase: str) -> bool:
    """Return True iff ``phase`` is one of the 2 registered phase labels."""
    return phase in VALID_PHASES
