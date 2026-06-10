# P0-43 Compose Stable Relation Reuse Qualified Ref Snapshot Replay Progress

## 2026-06-10

Implemented the P0-37 residual follow-up for stable relation reuse with
qualified refs.

Changes:

- Java `JavaComposeSnapshotTest` now supports a test-only `reuseKey` in the
  neutral snapshot plan DSL.
- Added `stable-reused-base-qualified-ref-postgres`, where one reused
  `FactSalesModel` base plan feeds two derived branches, the branches project
  `statusLeft`/`amountLeft` and `statusRight`/`amountRight`, and the outer
  query uses `left.amountLeft` / `right.amountRight` in projection, slice, and
  orderBy.
- Python snapshot replay now preserves `reuseKey` identity when rebuilding
  plans from `tests/fixtures/java_compose_snapshot_parity.json`.
- Added a focused Python local regression for reused base + derived branch
  side-qualified refs.

Evidence:

- Java focused exporter:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  passed with `3` profile executions.
- Python local regression:
  `.venv/bin/python -m pytest tests/compose/compilation/test_join.py::TestJoinBasic::test_postgres_reused_base_allows_side_qualified_refs -q`
  passed with `1 passed in 0.13s`.
- Python replay and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  passed with `6 passed in 0.50s`.
- Python full suite:
  `.venv/bin/python -m pytest -q`
  passed with `4080 passed, 232 skipped, 53 warnings in 17.97s`.

Status:

- Stable relation reuse qualified-ref residual is now covered by the active
  compose snapshot lane.
- Broader dialect SQL-shape expansion remains separate.
