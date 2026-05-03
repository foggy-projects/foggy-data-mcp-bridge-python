---
quality_scope: feature
quality_mode: pre-coverage-audit
version: v1.9
target: pivot-stage5b-c2-cascade
status: reviewed
decision: ready-for-coverage-audit
reviewed_by: root-controller
reviewed_at: 2026-05-03
follow_up_required: yes
---

# Implementation Quality Gate

## Background

This record reviews the scoped Python Pivot 9.1 Stage 5B C2 implementation:
rows-axis exactly two-level cascade TopN via staged SQL. The public Pivot DSL
is unchanged. Unsupported cascade shapes must fail closed and must not enter
the existing memory-only fallback path.

## Check Basis

- `docs/v1.9/P0-Pivot-9.1-Java-Parity-Requirement.md`
- `docs/v1.9/P0-Pivot-9.1-Java-Parity-Implementation-Plan.md`
- `docs/v1.9/P0-Pivot-9.1-Java-Parity-progress.md`
- `src/foggy/dataset_model/semantic/pivot/cascade_detector.py`
- `src/foggy/dataset_model/semantic/pivot/cascade_staged_sql.py`
- `tests/test_dataset_model/test_pivot_v9_cascade_validation.py`
- `tests/test_dataset_model/test_pivot_v9_cascade_semantics.py`
- `tests/integration/test_pivot_v9_cascade_real_db_matrix.py`

## Changed Surface

- Cascade routing in `SemanticQueryService.query_model()` enters
  `execute_cascade_staged_sql()` only for the whitelisted rows-axis two-level
  TopN shape.
- `cascade_staged_sql.py` builds the base query through queryModel validation,
  wraps it in staged CTEs, applies parent and child ranking, executes SQL, then
  shapes results with a cloned Pivot request.
- Real DB tests compare Pivot results with handwritten SQL oracle queries for
  SQLite, MySQL8, and PostgreSQL.
- CALCULATE cleanup in `_calculate_window_supported()` respects the dialect
  capability flag and is verified separately.

## Quality Checklist

| Dimension | Result | Notes |
|---|---|---|
| scope conformance | pass | No public DSL or result-shape change was introduced for cascade. |
| code hygiene | pass | Debug `print` statements were removed from runtime and tests. |
| request mutation | pass | Pivot request is deep-copied before SQL-applied limits/havings are cleared. |
| error handling | pass | Unsupported cascade shapes are rejected with stable `PIVOT_CASCADE_*` errors. |
| no memory fallback | pass | C2 requests are routed to staged SQL; unsupported shapes fail closed before memory processing. |
| dialect behavior | pass | Cascade domain joins use SQLite `IS`, PostgreSQL `IS NOT DISTINCT FROM`, and MySQL8 `<=>`. |
| lifecycle preservation | pass | Base SQL is produced through queryModel validation, preserving model resolution and governance path. |
| params / alias handling | pass | Staged SQL reuses base params; aliases are reverse-mapped for final flat output. |
| documentation writeback | pass | Progress, requirement, implementation plan, quality, coverage, and acceptance docs are updated. |
| release readiness | pass with follow-up | Cascade subtotal/grandTotal parity is explicitly deferred to Python 9.2. |

## Findings

No blocking implementation issues remain for the scoped P4 feature.

The original P4 plan mentioned additive subtotal/grandTotal over the surviving
domain. That capability is not signed off here because Python's current
`MemoryCubeProcessor` does not yet emit cascade subtotal rows. The scope was
adjusted in the requirement and implementation plan to keep the signoff honest.

## Risks / Follow-ups

- Cascade subtotal/grandTotal parity remains a Python 9.2 follow-up.
- SQL Server and MySQL 5.7 live cascade evidence remain deferred.
- Tree + cascade and cross-axis cascade remain refused/deferred.

## Recommended Next Skills

- `foggy-test-coverage-audit`
- `foggy-acceptance-signoff`

## Decision

Decision: `ready-for-coverage-audit`.

The scoped implementation is clean enough to enter coverage audit and formal
feature acceptance.
