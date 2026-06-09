# P0-37 Compose Source Alias Qualified Ref Snapshot Expansion Progress

Date: 2026-06-09

## Completed

- Reviewed the active Python fixture
  `tests/fixtures/java_compose_snapshot_parity.json`.
- Confirmed current coverage includes the existing qualified source-alias join,
  dropped-column source alias refusal, and SQL Server fallback guard.
- Recorded the next expansion list without changing compose compile behavior.
- Added Java exporter cases:
  - `qualified-source-alias-slice-order-postgres`
  - `inherited-source-alias-through-derived-postgres`
  - `ambiguous-duplicate-source-alias-ref-refused`
- Regenerated `tests/fixtures/java_compose_snapshot_parity.json`.
- Updated the Python replay harness so derived snapshot nodes are rebuilt
  through `QueryPlan.query(...)`, preserving source alias bindings exactly as
  the production compose DSL path does.
- Added fail-closed duplicate source-alias detection in Java
  `PlanQualifiedFieldResolver` and Python schema/lowering source scopes.
- Added Python join regression coverage for duplicate source-alias qualified
  refs.
- Added Java snapshot cases for:
  - `qualified-source-alias-slice-order-mysql8`
  - `qualified-source-alias-slice-order-sqlserver`
  - `source-alias-shadowed-by-projected-alias-refused`
  - `union-branch-source-alias-ref-refused`
  - `union-result-alias-qualified-ref-postgres`
- Aligned Java `PlanQualifiedFieldResolver` with the P0-42 boundary:
  projected aliases cannot shadow visible source aliases; union-as-source only
  exposes the union result alias while treating branch aliases as fail-closed
  unknown prefixes.
- Aligned Python schema derivation and compile lowering with the same
  projected source-alias shadowing and union-as-source boundary.
- Added Python focused regressions for projected source-alias shadowing, union
  branch-alias refusal, and union result-alias acceptance.
- Added P0-42 progress documentation for the source-alias boundary closeout.

## Verification

Passed:

- `.venv/bin/python -m pytest tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_domain_fixture_runner.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - result: `8 passed in 0.47s`
- `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  - result: `BUILD SUCCESS`; default, MySQL, and PostgreSQL executions passed.
- `.venv/bin/python -m pytest tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - result: `6 passed in 0.48s`
- `.venv/bin/python -m pytest tests/compose/compilation/test_join.py::TestJoinBasic::test_postgres_query_after_join_accepts_side_and_local_qualified_refs tests/compose/compilation/test_join.py::TestJoinBasic::test_postgres_query_after_join_accepts_inherited_source_alias_refs -q`
  - result: `2 passed in 0.07s`
- `.venv/bin/ruff check tests/integration/test_java_compose_snapshot_parity.py`
  - result: `All checks passed!`
- `.venv/bin/python -m pytest -q`
  - result: `4075 passed, 232 skipped, 52 warnings in 17.87s`
- `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest,JoinCompileTest`
  - result: `BUILD SUCCESS`; default, MySQL, and PostgreSQL executions passed.
- `.venv/bin/python -m pytest tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - result: `6 passed in 0.48s`
- `.venv/bin/python -m pytest tests/compose/compilation/test_join.py::TestJoinBasic::test_postgres_query_after_join_accepts_side_and_local_qualified_refs tests/compose/compilation/test_join.py::TestJoinBasic::test_postgres_query_after_join_accepts_inherited_source_alias_refs tests/compose/compilation/test_join.py::TestJoinBasic::test_query_after_join_rejects_duplicate_source_alias_refs -q`
  - result: `3 passed in 0.13s`
- `.venv/bin/python -m pytest -q`
  - result: `4076 passed, 232 skipped, 53 warnings in 23.55s`
- `git diff --check`
  - result: passed in both Java and Python repos.
- `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest,JoinCompileTest`
  - result: `BUILD SUCCESS`; default, MySQL, and PostgreSQL executions passed;
    22 tests passed per profile.
- `.venv/bin/python -m pytest tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - result: `6 passed in 0.49s`
- `.venv/bin/python -m pytest tests/compose/compilation/test_join.py -k 'duplicate_source_alias_refs or projected_alias_shadowing_source_alias' tests/compose/compilation/test_union.py -k 'branch_source_alias_reference or union_result_alias_reference' -q`
  - result: `2 passed, 49 deselected in 0.11s`
- `.venv/bin/python -m pytest -q`
  - result: `4079 passed, 232 skipped, 53 warnings in 20.54s`

Observed but not used as a blocker:

- `.venv/bin/ruff check ...` over broad source files reports existing
  pyupgrade/import-sort debt in `compose_planner.py`, `derive.py`, and
  `test_join.py`; this was not introduced by the P0-37/P0-42 behavior change
  and is not part of this scoped signoff.

## Follow-Up

Stable relation reuse with qualified refs remains separate. P0-37/P0-42 source
alias boundary work is closed by the P0-42 progress evidence and
[P0-37 acceptance](../acceptance/P0-37-compose-source-alias-qualified-ref-snapshot-expansion-acceptance.md).
