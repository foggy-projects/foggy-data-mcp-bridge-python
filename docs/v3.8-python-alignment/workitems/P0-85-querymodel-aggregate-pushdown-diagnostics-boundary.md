---
doc_purpose: Track aggregate relation pushdown diagnostics and runtime filter boundary.
version: v3.8-python-alignment
priority: P0-85
status: completed
owner: python-engine
---

# P0-85 QueryModel Aggregate Pushdown Diagnostics Boundary

Date: 2026-06-12

## Background

Java aggregate join evidence includes pushdown diagnostics. Python should not
grow a broad best-effort optimizer first; it should expose a deterministic
boundary for the Java fixture cases: simple AND filters can push to RHS where
or having, while OR filters remain outer-only with explicit diagnostics.

## Target Outcome

- Push root join-key AND filters into the RHS `where` clause.
- Push aggregate output range filters into the RHS `having` clause.
- Keep OR filters on the outer query and record retained diagnostics.
- Resolve relation-owned runtime filters from `SemanticRequestContext.extData`.
- Fail closed when a required runtime filter value is missing.

## Implementation

- Added aggregate-relation diagnostics to `QueryBuildResult`.
- Added outer filter rendering for the narrow SQLite aggregate relation path.
- Added pushdown diagnostics with stable `decision`, `field`, `target`,
  `reasonCode`, and `expression` fields.
- Added `QUERYMODEL_AGGREGATE_JOIN_RUNTIME_FILTER_MISSING` for missing runtime
  filter values.
- Added focused P0-85 tests in
  `tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py`.

## Acceptance Criteria

- Completed. Simple root join-key filters are emitted both as outer filters and
  pushed RHS `where` filters.
- Completed. Aggregate output range filters are emitted both as outer filters
  and pushed RHS `having` filters.
- Completed. OR filters remain outer-only and report
  `OR_CONDITION_OUTER_ONLY`.
- Completed. Runtime extData filters resolve into SQL params when present.
- Completed. Missing runtime extData fails closed before SQL is returned.

## Progress Tracking

- Development: completed.
- Testing: completed with focused pushdown, retained-diagnostics, and runtime
  filter assertions.
- Experience: N/A; this is backend SQL diagnostics behavior with no UI surface.

## Verification

- Passed:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py -q`
  (`14 passed`)
- Passed:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
  (`10 passed`)
- Passed:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_semantic_query.py tests/test_dataset_model/test_strict_column_resolution.py tests/test_dataset_model/test_window_functions.py -q`
  (`131 passed`)
- Passed:
  `.venv/bin/ruff check --select F src/foggy/dataset_model/aggregate_join.py src/foggy/dataset_model/semantic/field_validator.py src/foggy/dataset_model/semantic/service.py tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py tests/test_dataset_model/test_loader_fsscript.py`
- Passed: `git diff --check`

## Execution Check-in

- Code paths touched:
  - `src/foggy/dataset_model/aggregate_join.py`
  - `src/foggy/dataset_model/semantic/service.py`
  - `tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py`
- Self-check:
  - Diagnostics are deterministic for the covered fixture shapes.
  - OR filters are retained rather than guessed into a partial pushdown.
  - Runtime filter failure is fail-closed and uses an aggregate-specific code.

## Remaining Risks

- Mixed OR over aggregate outputs is still outside the narrow supported subset.
- No broad predicate optimizer is introduced yet.
- MySQL/PostgreSQL/TMS DB pushdown diagnostics remain future fixture work.
