"""Frozen error-code constants for Compose Query sandbox violations.

Three layers:
    * Layer A — script host (JavaScript / fsscript surface)
    * Layer B — DSL expression (FSScript function whitelist)
    * Layer C — QueryPlan verb whitelist

Cross-language invariant: every string here must match the Java
``ComposeSandboxErrorCodes.java`` constants **byte for byte**. Code names
align with the M9 scaffold document (see
``foggy-data-mcp-bridge/docs/8.2.0.beta/M9-三层沙箱防护测试脚手架.md``
§ "错误码定义").

Adding codes: append only. Renaming / removing requires an SPI version
bump of the compose sandbox surface.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Namespace
# ---------------------------------------------------------------------------

NAMESPACE: str = "compose-sandbox-violation"


def _qualify(layer: str, kind: str) -> str:
    """Return ``{NAMESPACE}/{layer}/{kind}``. Internal helper; consumers
    should use the concrete constants below."""
    return f"{NAMESPACE}/{layer}/{kind}"


# ---------------------------------------------------------------------------
# Layer A — 脚本宿主层
# ---------------------------------------------------------------------------

LAYER_A_EVAL_DENIED: str = _qualify("A", "eval-denied")
LAYER_A_ASYNC_DENIED: str = _qualify("A", "async-denied")
LAYER_A_NETWORK_DENIED: str = _qualify("A", "network-denied")
LAYER_A_IO_DENIED: str = _qualify("A", "io-denied")
LAYER_A_GLOBAL_DENIED: str = _qualify("A", "global-denied")
LAYER_A_TIME_DENIED: str = _qualify("A", "time-denied")
LAYER_A_SECURITY_PARAM: str = _qualify("A", "security-param-denied")
LAYER_A_CONTEXT_ACCESS: str = _qualify("A", "context-access-denied")


# ---------------------------------------------------------------------------
# Layer B — DSL 表达式层
# ---------------------------------------------------------------------------

LAYER_B_FUNCTION_DENIED: str = _qualify("B", "function-denied")
LAYER_B_DERIVED_FN_DENIED: str = _qualify("B", "derived-plan-function-denied")
LAYER_B_INJECTION_SUSPECTED: str = _qualify("B", "injection-suspected")


# ---------------------------------------------------------------------------
# Layer C — Plan 动词白名单
# ---------------------------------------------------------------------------

LAYER_C_METHOD_DENIED: str = _qualify("C", "method-denied")
LAYER_C_RESULT_ITERATION: str = _qualify("C", "result-iteration-denied")
LAYER_C_CROSS_DS: str = _qualify("C", "cross-datasource-denied")


# ---------------------------------------------------------------------------
# Phase enumeration (duck-typed as str — avoids Enum import at this layer)
# ---------------------------------------------------------------------------

PHASE_SCRIPT_PARSE: str = "script-parse"
PHASE_SCRIPT_EVAL: str = "script-eval"
PHASE_PLAN_BUILD: str = "plan-build"
PHASE_SCHEMA_DERIVE: str = "schema-derive"
PHASE_AUTHORITY_RESOLVE: str = "authority-resolve"
PHASE_COMPILE: str = "compile"
PHASE_EXECUTE: str = "execute"


VALID_PHASES: frozenset = frozenset(
    {
        PHASE_SCRIPT_PARSE,
        PHASE_SCRIPT_EVAL,
        PHASE_PLAN_BUILD,
        PHASE_SCHEMA_DERIVE,
        PHASE_AUTHORITY_RESOLVE,
        PHASE_COMPILE,
        PHASE_EXECUTE,
    }
)


ALL_CODES: frozenset = frozenset(
    {
        # Layer A (8)
        LAYER_A_EVAL_DENIED,
        LAYER_A_ASYNC_DENIED,
        LAYER_A_NETWORK_DENIED,
        LAYER_A_IO_DENIED,
        LAYER_A_GLOBAL_DENIED,
        LAYER_A_TIME_DENIED,
        LAYER_A_SECURITY_PARAM,
        LAYER_A_CONTEXT_ACCESS,
        # Layer B (3)
        LAYER_B_FUNCTION_DENIED,
        LAYER_B_DERIVED_FN_DENIED,
        LAYER_B_INJECTION_SUSPECTED,
        # Layer C (3)
        LAYER_C_METHOD_DENIED,
        LAYER_C_RESULT_ITERATION,
        LAYER_C_CROSS_DS,
    }
)


# ---------------------------------------------------------------------------
# Layer ↔ code mapping (for validator / reflection helpers)
# ---------------------------------------------------------------------------

LAYER_PREFIX_A: str = f"{NAMESPACE}/A/"
LAYER_PREFIX_B: str = f"{NAMESPACE}/B/"
LAYER_PREFIX_C: str = f"{NAMESPACE}/C/"


def layer_of(code: str) -> str:
    """Return the single-letter layer (``A`` / ``B`` / ``C``) for a code
    string; raises ``ValueError`` when the code does not belong to a
    known sandbox layer."""
    if code.startswith(LAYER_PREFIX_A):
        return "A"
    if code.startswith(LAYER_PREFIX_B):
        return "B"
    if code.startswith(LAYER_PREFIX_C):
        return "C"
    raise ValueError(
        f"code {code!r} does not belong to any compose-sandbox-violation layer"
    )


def kind_of(code: str) -> str:
    """Return the trailing ``kind`` segment of a code (e.g. ``"eval-denied"``
    for ``LAYER_A_EVAL_DENIED``)."""
    layer = layer_of(code)
    prefix = f"{NAMESPACE}/{layer}/"
    return code[len(prefix):]
