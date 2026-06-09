# P0-42 Compose Union Source Alias Shadowing Snapshot Replay Progress

Date: 2026-06-09

## Completed

- Added Java compose snapshot cases for projected source-alias shadowing,
  union branch-alias refusal, union result-alias qualified refs, and
  cross-dialect qualified source-alias slice/order markers.
- Aligned Java `PlanQualifiedFieldResolver` so derived projections reject
  aliases that shadow visible source aliases and union-as-source exposes the
  union result alias without leaking branch aliases.
- Aligned Python schema derivation and compile lowering with the same
  fail-closed source-alias shadowing boundary.
- Added Python union-as-source focused tests for branch alias refusal and
  union result alias acceptance.
- Added SQL Server embedded composed-source fallback so Python no longer
  renders `FROM (WITH` for the Java snapshot case.
- Updated the compose snapshot manifest/docs to advertise the P0-42 coverage.

## Verification

Passed:

- `.venv/bin/python -m pytest tests/compose/compilation/test_join.py::TestJoinBasic::test_query_after_join_rejects_projected_alias_shadowing_source_alias tests/compose/compilation/test_union.py::TestUnionWithDerived::test_derived_over_union_rejects_branch_source_alias_reference tests/compose/compilation/test_union.py::TestUnionWithDerived::test_derived_over_union_accepts_union_result_alias_reference -q`
  - result: `3 passed in 0.10s`
- `.venv/bin/python -m pytest tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - result: `6 passed in 0.52s`
- `.venv/bin/ruff check --select E,F src/foggy/dataset_model/engine/compose/compilation/compose_planner.py src/foggy/dataset_model/engine/compose/schema/derive.py tests/compose/compilation/test_join.py tests/compose/compilation/test_union.py tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py`
  - result: `All checks passed!`
- `.venv/bin/ruff check tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py`
  - result: `All checks passed!`
- `git diff --check`
  - result: passed in both Java and Python repos.
- `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest,JoinCompileTest`
  - result: `BUILD SUCCESS`; `22` tests passed.
- `.venv/bin/python -m pytest -q`
  - result: `4079 passed, 232 skipped, 53 warnings in 18.72s`

Note:

- A broader ruff run against full touched engine modules still reports existing
  modernization/import-order style debt (`UP`/`I`/`W`) outside this scoped
  closeout. The P0-42 gate uses the focused `E,F` risk check plus replay tests.

## Follow-Up

Stable relation reuse with qualified refs remains a separate compose parity
follow-up. P0-42 only closes the projected source-alias shadowing and
union-as-source alias boundary.
