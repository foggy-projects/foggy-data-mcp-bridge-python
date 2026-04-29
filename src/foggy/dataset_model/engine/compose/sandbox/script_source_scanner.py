"""Layer A — pre-execution source scanner for Compose Query scripts.

Scans the raw script source text for forbidden identifiers and patterns
**before** fsscript compilation. This catches eval/Function/fetch/require/
Date/Object.getPrototypeOf/__context__ etc. at the earliest possible moment,
so that dangerous scripts never reach the evaluator.
"""

from __future__ import annotations

import re

from .error_codes import (
    LAYER_A_ASYNC_DENIED,
    LAYER_A_CONTEXT_ACCESS,
    LAYER_A_EVAL_DENIED,
    LAYER_A_GLOBAL_DENIED,
    LAYER_A_IO_DENIED,
    LAYER_A_NETWORK_DENIED,
    LAYER_A_SECURITY_PARAM,
    LAYER_A_TIME_DENIED,
    LAYER_B_DERIVED_FN_DENIED,
    LAYER_C_METHOD_DENIED,
    LAYER_C_RESULT_ITERATION,
    PHASE_SCRIPT_PARSE,
)
from .exceptions import ComposeSandboxViolationError

# ---------------------------------------------------------------------------
# Pattern lists — keep in sync with P0 sandbox spec §Layer A
# ---------------------------------------------------------------------------

# A-01 / A-02: eval / Function constructor
EVAL_PATTERNS = [
    # eval(...)
    re.compile(r"\beval\s*\("),
    # new Function(...)
    re.compile(r"\bnew\s+Function\s*\("),
    # Function(...)  — called without new (lookbehind not matching dot)
    re.compile(r"(?<!\.)\bFunction\s*\("),
]

# A-03: async / await / setTimeout / setInterval / Promise
ASYNC_PATTERNS = [
    re.compile(r"\bawait\b"),
    re.compile(r"\basync\b"),
    re.compile(r"\bsetTimeout\s*\("),
    re.compile(r"\bsetInterval\s*\("),
    re.compile(r"\bPromise\b"),
]

# A-03 also: network primitives
NETWORK_PATTERNS = [
    re.compile(r"\bfetch\s*\("),
    re.compile(r"\bXMLHttpRequest\b"),
    re.compile(r"\bWebSocket\b"),
]

# A-04: global / reflective access
GLOBAL_PATTERNS = [
    re.compile(r"\bglobalThis\b"),
    re.compile(r"\bwindow\b"),
    re.compile(r"\bself\b"),
    re.compile(r"\bReflect\b"),
    re.compile(r"\bObject\s*\.\s*getPrototypeOf\s*\("),
    re.compile(r"\bObject\s*\.\s*keys\s*\("),
    re.compile(r"\bObject\s*\.\s*defineProperty\s*\("),
]

# A-05: time access
TIME_PATTERNS = [
    re.compile(r"\bDate\s*\.\s*now\s*\("),
    re.compile(r"\bnew\s+Date\s*\("),
    re.compile(r"\bDate\s*\.\s*parse\s*\("),
]

# A-08: context access
CONTEXT_PATTERNS = [
    re.compile(r"__context__"),
    re.compile(r"\bComposeQueryContext\b"),
    re.compile(r"\bprincipal\b"),
    re.compile(r"\bauthorityResolver\b"),
]

# A-09: module / IO
IO_PATTERNS = [
    re.compile(r"\brequire\s*\("),
    re.compile(r"\bimport\s"),
    re.compile(r"\bprocess\b"),
    re.compile(r"\bfs\s*\."),
    re.compile(r"\bFile\b"),
]

CONTROLLED_IMPORT_STATEMENT = re.compile(
    r"""
    \bimport\s+
    (?:
        \*\s+as\s+[A-Za-z_][A-Za-z0-9_]* |
        \{[^{};]+\} |
        [A-Za-z_][A-Za-z0-9_]*
    )
    \s+from\s+
    ['"][A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*['"]
    \s*;?
    """,
    re.VERBOSE,
)

DYNAMIC_IMPORT_PATTERN = re.compile(r"\bimport\s*\(")

# A-06 / A-07: security parameter keywords that must not appear in DSL bodies
SECURITY_PARAM_PATTERNS = [
    re.compile(r"\bauthorization\b\s*:"),
    re.compile(r"\buserId\b\s*:"),
    re.compile(r"\btenantId\b\s*:"),
    re.compile(r"\broles\b\s*:"),
    # namespace is too common; only match inside object-key context
    re.compile(r"\bdeniedColumns\b\s*:"),
    re.compile(r"\bsystemSlice\b\s*:"),
    re.compile(r"\bfieldAccess\b\s*:"),
    re.compile(r"\bpolicySnapshotId\b\s*:"),
]

# Layer B: blocked SQL function names detected at source level
BLOCKED_SQL_FN_PATTERNS = [
    re.compile(r"(?i)\bRAW_SQL\s*\("),
    re.compile(r"(?i)\bEXEC\s*\("),
    re.compile(r"(?i)\bXP_CMDSHELL\s*\("),
    re.compile(r"(?i)\bDBMS_PIPE\s*\("),
]

# Layer C: forbidden QueryPlan method names
FORBIDDEN_METHOD_PATTERNS = [
    re.compile(r"\.\s*raw\s*\("),
    re.compile(r"\.\s*memoryFilter\s*\("),
    re.compile(r"\.\s*forEach\s*\("),
    re.compile(r"\.\s*toArray\s*\("),
]

# Layer C: result iteration patterns
RESULT_ITERATION_PATTERNS = [
    re.compile(r"\.\s*items\s*\."),
    re.compile(r"\.\s*rows\s*\."),
    re.compile(r"\.\s*iterator\s*\("),
]


def _matches_any(source: str, patterns: list[re.Pattern]) -> bool:
    return any(p.search(source) for p in patterns)


def scan_script_source(
    script: str,
    *,
    allow_controlled_imports: bool = False,
) -> None:
    """Scan the source for Layer A violations.

    Parameters
    ----------
    script : str
        The raw script source to scan.

    Raises
    ------
    ComposeSandboxViolationError
        If any forbidden pattern is detected.
    """
    if not script:
        return

    # A-01 / A-02: eval / Function
    if _matches_any(script, EVAL_PATTERNS):
        raise ComposeSandboxViolationError(
            LAYER_A_EVAL_DENIED,
            "Dynamic evaluation is not allowed in compose scripts.",
            PHASE_SCRIPT_PARSE,
        )

    # A-03: async primitives
    if _matches_any(script, ASYNC_PATTERNS):
        raise ComposeSandboxViolationError(
            LAYER_A_ASYNC_DENIED,
            "Asynchronous primitives are not allowed in compose scripts.",
            PHASE_SCRIPT_PARSE,
        )

    # A-03 also: network
    if _matches_any(script, NETWORK_PATTERNS):
        raise ComposeSandboxViolationError(
            LAYER_A_NETWORK_DENIED,
            "Network primitives are not available in compose scripts.",
            PHASE_SCRIPT_PARSE,
        )

    # A-04: global / reflective access
    if _matches_any(script, GLOBAL_PATTERNS):
        raise ComposeSandboxViolationError(
            LAYER_A_GLOBAL_DENIED,
            "Reflective or global access is blocked.",
            PHASE_SCRIPT_PARSE,
        )

    # A-05: time
    if _matches_any(script, TIME_PATTERNS):
        raise ComposeSandboxViolationError(
            LAYER_A_TIME_DENIED,
            "Direct time access is blocked; time must be injected by host.",
            PHASE_SCRIPT_PARSE,
        )

    # A-08: context access
    if _matches_any(script, CONTEXT_PATTERNS):
        raise ComposeSandboxViolationError(
            LAYER_A_CONTEXT_ACCESS,
            "ComposeQueryContext is not accessible from scripts.",
            PHASE_SCRIPT_PARSE,
        )

    # A-06 / A-07: security parameters in DSL body
    if _matches_any(script, SECURITY_PARAM_PATTERNS):
        raise ComposeSandboxViolationError(
            LAYER_A_SECURITY_PARAM,
            "Security parameters cannot be passed through DSL body; "
            "they are bound by ComposeQueryContext.",
            PHASE_SCRIPT_PARSE,
        )

    # Layer B: blocked SQL functions at source level (e.g. RAW_SQL)
    if _matches_any(script, BLOCKED_SQL_FN_PATTERNS):
        raise ComposeSandboxViolationError(
            LAYER_B_DERIVED_FN_DENIED,
            "Function is not allowed in compose scripts.",
            PHASE_SCRIPT_PARSE,
        )

    # Layer C: result iteration (check BEFORE forbidden methods)
    if _matches_any(script, RESULT_ITERATION_PATTERNS):
        raise ComposeSandboxViolationError(
            LAYER_C_RESULT_ITERATION,
            "DataSetResult does not support script-side iteration.",
            PHASE_SCRIPT_PARSE,
        )

    # Layer C: forbidden QueryPlan methods
    if _matches_any(script, FORBIDDEN_METHOD_PATTERNS):
        raise ComposeSandboxViolationError(
            LAYER_C_METHOD_DENIED,
            "Method is not part of the QueryPlan public surface.",
            PHASE_SCRIPT_PARSE,
        )

    # A-09: module / IO.  v1.8 can enable static registry-backed imports,
    # but all dynamic import / require / file / process forms remain denied.
    if allow_controlled_imports:
        io_patterns = [p for p in IO_PATTERNS if p.pattern != r"\bimport\s"]
        import_remainder = CONTROLLED_IMPORT_STATEMENT.sub("", script)
        import_denied = (
            DYNAMIC_IMPORT_PATTERN.search(script) is not None
            or re.search(r"\bimport\s", import_remainder) is not None
        )
    else:
        io_patterns = IO_PATTERNS
        import_denied = False

    if _matches_any(script, io_patterns) or import_denied:
        raise ComposeSandboxViolationError(
            LAYER_A_IO_DENIED,
            "File/process/module primitives are not available in compose scripts.",
            PHASE_SCRIPT_PARSE,
        )
