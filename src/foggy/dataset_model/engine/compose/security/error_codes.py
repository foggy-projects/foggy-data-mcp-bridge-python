"""Frozen error-code constants for Compose Query authority resolution.

Cross-language invariant: every constant's string value must match the Java
counterpart in ``AuthorityErrorCodes.java`` **byte for byte**. A parity test
at ``tests/compose/test_authority_resolution_error_code.py`` asserts the
full set exists, and a cross-repo manual review catches any drift.

See:
    ``foggy-data-mcp-bridge/docs/8.2.0.beta/M1-AuthorityResolver-SPI签名冻结-需求.md``
    (section "AuthorityResolutionException" — error-code table)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Authority-resolution namespace
# ---------------------------------------------------------------------------

NAMESPACE: str = "compose-authority-resolve"


def _qualify(kind: str) -> str:
    """Join the namespace and a kind suffix with '/'. Kept out of the public
    API surface; consumers use the concrete constants below.
    """
    return f"{NAMESPACE}/{kind}"


# Seven frozen codes (M1 contract). Additions allowed; renames are a SemVer
# breakage and require a version bump of the whole SPI.
RESOLVER_NOT_AVAILABLE: str = _qualify("resolver-not-available")
MODEL_BINDING_MISSING: str = _qualify("model-binding-missing")
MODEL_NOT_MAPPED: str = _qualify("model-not-mapped")
PRINCIPAL_MISMATCH: str = _qualify("principal-mismatch")
UPSTREAM_FAILURE: str = _qualify("upstream-failure")
INVALID_RESPONSE: str = _qualify("invalid-response")
IR_RULE_UNMAPPED_FIELD: str = _qualify("ir-rule-unmapped-field")


# ---------------------------------------------------------------------------
# Phase enum (duck-typed as str; an Enum would force import cycles)
# ---------------------------------------------------------------------------

PHASE_AUTHORITY_RESOLVE: str = "authority-resolve"
PHASE_SCHEMA_DERIVE: str = "schema-derive"
PHASE_COMPILE: str = "compile"
PHASE_EXECUTE: str = "execute"


VALID_PHASES: frozenset = frozenset(
    {
        PHASE_AUTHORITY_RESOLVE,
        PHASE_SCHEMA_DERIVE,
        PHASE_COMPILE,
        PHASE_EXECUTE,
        # Extra phases that apply to sandbox errors rather than authority:
        "script-parse",
        "script-eval",
        "plan-build",
    }
)


ALL_CODES: frozenset = frozenset(
    {
        RESOLVER_NOT_AVAILABLE,
        MODEL_BINDING_MISSING,
        MODEL_NOT_MAPPED,
        PRINCIPAL_MISMATCH,
        UPSTREAM_FAILURE,
        INVALID_RESPONSE,
        IR_RULE_UNMAPPED_FIELD,
    }
)
