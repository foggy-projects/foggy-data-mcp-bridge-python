"""Frozen error codes for Compose Query schema-derivation failures.

These are **structural / correctness** errors (missing field references,
union column-count mismatch, join-on resolution failures) that occur
during plan-build / schema-derive phases. They are deliberately NOT
grouped under ``compose-sandbox-violation`` — sandbox codes are for
*security* enforcement (Layer A/B/C whitelists); schema codes are for
*correctness* (did the user write a structurally-valid plan?).

Cross-language invariant: every constant here must match the Java
``ComposeSchemaErrorCodes.java`` class byte-for-byte.
"""

from __future__ import annotations

NAMESPACE: str = "compose-schema-error"


def _qualify(kind: str) -> str:
    return f"{NAMESPACE}/{kind}"


# ---------------------------------------------------------------------------
# Per-plan-type error codes
# ---------------------------------------------------------------------------

# Derived query references a column that is NOT in source.output_schema.
DERIVED_QUERY_UNKNOWN_FIELD: str = _qualify("derived-query/unknown-field")

# Base-model plan has a column spec whose expression references the
# empty alias slot (``... AS``) or similar malformed shape. Usually
# caught at ``extract_column_alias`` but this code exists so derivation
# can surface it consistently.
COLUMN_SPEC_MALFORMED: str = _qualify("column-spec/malformed")

# Output schema after derivation contains duplicate output names (e.g.
# two columns aliased to the same name, or a join left+right clash not
# resolved by explicit alias).
DUPLICATE_OUTPUT_COLUMN: str = _qualify("duplicate-output-column")

# ``UnionPlan`` two sides have different column counts.
UNION_COLUMN_COUNT_MISMATCH: str = _qualify("union/column-count-mismatch")

# ``JoinPlan`` ``on[*].left`` does not resolve in left's output schema.
JOIN_ON_LEFT_UNKNOWN_FIELD: str = _qualify("join/on-left-unknown-field")

# ``JoinPlan`` ``on[*].right`` does not resolve in right's output schema.
JOIN_ON_RIGHT_UNKNOWN_FIELD: str = _qualify("join/on-right-unknown-field")

# Join left.output + right.output share an output column name without
# explicit alias disambiguation.
#
# G10: Only thrown when ``g10_enabled() == False`` (legacy behaviour).
# When G10 is enabled, the column is marked ``is_ambiguous=True`` and the
# conflict is detected at downstream reference resolution as
# ``JOIN_AMBIGUOUS_COLUMN``.
JOIN_OUTPUT_COLUMN_CONFLICT: str = _qualify("join/output-column-conflict")

# G10 PR2 · A lookup against ``OutputSchema.get(name)`` or
# ``require_unique(name)`` resolved a column name marked
# ``is_ambiguous=True`` (multiple plans contribute the same name).
#
# The error message lists every candidate column's plan provenance so
# the caller can disambiguate via F5 plan-qualified column ref
# (``{plan: <handle>, field: <name>}``).
OUTPUT_SCHEMA_AMBIGUOUS_LOOKUP: str = _qualify("output-schema/ambiguous-lookup")

# G10 PR3 · Downstream reference (in derived/projected expression,
# group-by, or order-by) targets a column that the upstream join marked
# ``is_ambiguous=True``, and the reference itself is not plan-qualified
# (F5).
#
# Emitted by ``ComposePlanAwarePermissionValidator`` (G10 PR4) during
# bare-field resolution; reserved here since PR2 so producers have a
# stable code.
JOIN_AMBIGUOUS_COLUMN: str = _qualify("join/ambiguous-column")

# G10 PR4 · Field access denied. Either a plan-qualified
# ``PlanColumnRef`` was rejected by its plan's ``fieldAccess`` whitelist,
# or a bare field was uniquely resolved to a plan whose whitelist
# excludes it.
FIELD_ACCESS_DENIED: str = _qualify("field-access/denied")

# G10 PR4 · A ``PlanColumnRef`` targets a ``QueryPlan`` that is not
# registered in the active ``PlanFieldAccessContext``. Fail-closed
# safeguard.
COLUMN_PLAN_NOT_BOUND: str = _qualify("column/plan-not-bound")

# G10 PR4 · A bare-field column reference does not resolve to any
# column in the plan's ``OutputSchema``.
COLUMN_FIELD_NOT_FOUND: str = _qualify("column/field-not-found")

# G5 Phase 2 (F5) · An F5 plan-qualified column entry
# (``{plan, field, ...}``) carries a ``plan`` value that is not a
# ``QueryPlan`` instance. Surfaces at the DSL parse stage in
# ``column_normalizer._normalize_map()`` as a ``ValueError`` with this
# code as message prefix — same convention as the F4 parser-stage
# codes (``COLUMN_FIELD_REQUIRED`` etc.). Listed here for cross-language
# parity (Java ``ComposeSchemaErrorCodes`` carries the same string).
COLUMN_PLAN_TYPE_INVALID: str = _qualify("column/plan-type-invalid")

# G5 Phase 2 (F5) · An F5 plan-qualified column references a plan
# that is not in the current plan's visibility lineage per spec §5.1.
# Identity-keyed: same model name referenced via two distinct ``dsl()``
# calls produces two distinct plan instances that are NOT
# interchangeable. Surfaces at plan build stage as a ``ValueError`` with
# this code as message prefix. Distinct from ``COLUMN_PLAN_NOT_BOUND``
# (PR4 permission-validate stage).
COLUMN_PLAN_NOT_VISIBLE: str = _qualify("column/plan-not-visible")

# S7a — Relation output schema is unavailable (e.g. not yet compiled).
RELATION_OUTPUT_SCHEMA_UNAVAILABLE: str = _qualify("relation/output-schema-unavailable")

# S7a — Column reference within relation is unsupported (e.g. aggregatable
# on a ratio column).
RELATION_COLUMN_REFERENCE_UNSUPPORTED: str = _qualify("relation/column-reference-unsupported")


# ---------------------------------------------------------------------------
# Phase tags (kept compatible with the sandbox-error phase set so error
# sinks can consume both error families uniformly)
# ---------------------------------------------------------------------------

PHASE_PLAN_BUILD: str = "plan-build"
PHASE_SCHEMA_DERIVE: str = "schema-derive"
# G10 PR4 · plan-aware permission validation.
PHASE_PERMISSION_VALIDATE: str = "permission-validate"


VALID_PHASES: frozenset = frozenset(
    {
        PHASE_PLAN_BUILD,
        PHASE_SCHEMA_DERIVE,
        PHASE_PERMISSION_VALIDATE,
    }
)


ALL_CODES: frozenset = frozenset(
    {
        DERIVED_QUERY_UNKNOWN_FIELD,
        COLUMN_SPEC_MALFORMED,
        DUPLICATE_OUTPUT_COLUMN,
        UNION_COLUMN_COUNT_MISMATCH,
        JOIN_ON_LEFT_UNKNOWN_FIELD,
        JOIN_ON_RIGHT_UNKNOWN_FIELD,
        JOIN_OUTPUT_COLUMN_CONFLICT,
        OUTPUT_SCHEMA_AMBIGUOUS_LOOKUP,
        JOIN_AMBIGUOUS_COLUMN,
        FIELD_ACCESS_DENIED,
        COLUMN_PLAN_NOT_BOUND,
        COLUMN_FIELD_NOT_FOUND,
        COLUMN_PLAN_TYPE_INVALID,
        COLUMN_PLAN_NOT_VISIBLE,
        RELATION_OUTPUT_SCHEMA_UNAVAILABLE,
        RELATION_COLUMN_REFERENCE_UNSUPPORTED,
    }
)
