# P0-50 Compose Success Shape Strict Closure Progress

## 2026-06-10

Promoted all remaining successful compose snapshot cases to strict SQL-shape
replay.

Changes:

- Java `JavaComposeSnapshotTest` now marks the final three successful
  non-strict cases with `strictSqlShape`.
- Python compose fixture now has `16` successful cases and `16` strict SQL
  shape contracts.
- No Python engine behavior changed.

Evidence:

- Java focused exporter:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  passed with `3` profile executions.
- Python strict coverage check:
  `success 16 strict 16 non_strict 0`.
- Python focused replay and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  passed with `6 passed in 0.49s`.

Status:

- Compose successful snapshot SQL-shape replay is now fully strict for current
  neutral fixtures.
