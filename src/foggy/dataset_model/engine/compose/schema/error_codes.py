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
# Reserved here so PR3 / PR4 producers can throw a stable code; not yet
# emitted by PR2.
JOIN_AMBIGUOUS_COLUMN: str = _qualify("join/ambiguous-column")


# ---------------------------------------------------------------------------
# Phase tags (kept compatible with the sandbox-error phase set so error
# sinks can consume both error families uniformly)
# ---------------------------------------------------------------------------

PHASE_PLAN_BUILD: str = "plan-build"
PHASE_SCHEMA_DERIVE: str = "schema-derive"


VALID_PHASES: frozenset = frozenset(
    {
        PHASE_PLAN_BUILD,
        PHASE_SCHEMA_DERIVE,
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
    }
)
