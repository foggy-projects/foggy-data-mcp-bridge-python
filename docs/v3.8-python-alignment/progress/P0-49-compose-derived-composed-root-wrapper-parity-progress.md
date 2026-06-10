# P0-49 Compose Derived Composed Root Wrapper Parity Progress

## 2026-06-10

Closed the P0-46 root-wrapper follow-up for derived queries over join/union
sources.

Changes:

- Python `compose_planner._compile_derived` now returns terminal `ComposedSql`
  when the derived source compiled to `ComposedSql`, matching Java
  `ComposePlanner.compileDerived`.
- Python `_compile_any` skips `CteUnit` dedup caching for this terminal derived
  result.
- Java compose snapshot exporter marks six derived-over-composed cases with
  `strictSqlShape`.
- Python compose fixture now carries those strict root-wrapper checks.

Evidence:

- Python pre-check showed no remaining Java/Python root-wrapper mismatch across
  successful compose snapshots.
- Python focused compose replay:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_snapshot_parity.py -q`
  passed with `2 passed in 0.50s`.
- Python compose compilation regression:
  `.venv/bin/python -m pytest tests/compose/compilation/test_derived.py tests/compose/compilation/test_dialect_fallback.py tests/compose/compilation/test_union.py -q`
  passed with `85 passed in 0.33s`.
- Python focused semantic lint:
  `.venv/bin/ruff check --select F src/foggy/dataset_model/engine/compose/compilation/compose_planner.py tests/integration/test_java_compose_snapshot_parity.py`
  passed.
- Java focused exporter:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  passed with `3` profile executions.

Status:

- Derived-over-join and derived-over-union root-wrapper shape is now strict
  snapshot replay coverage instead of a tolerated drift.
