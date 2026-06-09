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

## Follow-Up

The next P0-37 batch should clarify source-alias shadowing by projected column
alias, then cover union-as-source and stable relation reuse with qualified
refs.
