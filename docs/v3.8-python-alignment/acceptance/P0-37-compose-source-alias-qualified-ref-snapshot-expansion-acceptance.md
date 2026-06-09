---
status: signed-off
decision: accepted-with-risks
feature: P0-37 compose source-alias qualified-ref snapshot expansion
date: 2026-06-09
follow_up_required: true
---

# P0-37 Compose Source Alias Qualified Ref Snapshot Expansion Acceptance

## Scope

This signoff covers the combined P0-37/P0-42 compose source-alias boundary:

- source-alias qualified refs in projection, slice, and orderBy after join,
- inherited source-alias refs through derived sources,
- duplicate source aliases across join sides fail closed,
- projected aliases that shadow visible source aliases fail closed,
- union branch aliases are hidden after the union boundary,
- union result aliases can qualify union output fields,
- MySQL8, PostgreSQL, and SQL Server marker replay for the active neutral
  fixture.

## Evidence

- Java focused exporter:
  `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest,JoinCompileTest`
  passed with `22` tests.
- Python snapshot replay and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  passed with `6 passed in 0.52s`.
- Python focused join/union regressions:
  `.venv/bin/python -m pytest tests/compose/compilation/test_join.py::TestJoinBasic::test_query_after_join_rejects_projected_alias_shadowing_source_alias tests/compose/compilation/test_union.py::TestUnionWithDerived::test_derived_over_union_rejects_branch_source_alias_reference tests/compose/compilation/test_union.py::TestUnionWithDerived::test_derived_over_union_accepts_union_result_alias_reference -q`
  passed with `3 passed in 0.10s`.
- Python full suite:
  `.venv/bin/python -m pytest -q` passed with
  `4079 passed, 232 skipped, 53 warnings in 18.72s`.

## Decision

Accepted with risks.

The current neutral fixture scope and Python/Java replay evidence are sufficient
to sign off source-alias qualified refs, shadowing refusal, and union-as-source
alias boundaries.

## Residual Risk

Stable relation reuse with qualified refs is still broader than the current
neutral source-alias boundary cases. Keep it as the next compose parity
follow-up instead of reopening P0-37.

## Follow-Up

- Add stable relation reuse qualified-ref fixtures.
- Keep broader dialect SQL-shape expansion separate from the source-alias
  boundary contract.
