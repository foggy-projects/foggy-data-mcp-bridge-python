# P0-44 Compose SQL Server Union Derived Fallback Snapshot Replay Progress

## 2026-06-10

Implemented the next dialect SQL-shape expansion after P0-43.

Changes:

- Java `JavaComposeSnapshotTest` now exports
  `sqlserver-union-result-alias-derived-fallback`.
- The new fixture covers `derived(union(...))` on SQL Server where the union
  result alias `combined` is used in projection, slice, and orderBy.
- Python local union coverage now verifies this SQL Server shape and forbids
  `FROM (WITH`.
- Existing Python dialect fallback coverage includes a SQL Server derived-chain
  guard that asserts Java-aligned subquery fallback and no embedded
  `FROM (WITH`.

Evidence:

- Java focused exporter:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  passed with `3` profile executions.
- Python focused coverage:
  `.venv/bin/python -m pytest tests/compose/compilation/test_union.py::TestUnionWithDerived::test_sqlserver_derived_over_union_result_alias_avoids_from_with tests/compose/compilation/test_dialect_fallback.py::TestDerivedChain4Dialects::test_derived_chain_sqlserver_uses_java_subquery_fallback tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  passed with `8 passed in 0.14s`.
- Python compose compilation suite:
  `.venv/bin/python -m pytest tests/compose/compilation -q`
  passed with `275 passed in 0.70s`.
- Python full suite:
  `.venv/bin/python -m pytest -q`
  passed with `4082 passed, 232 skipped, 53 warnings in 22.16s`.

Status:

- SQL Server union-as-derived fallback is covered by the active compose
  snapshot lane.
- Broader cross-dialect SQL golden coverage remains separate.
