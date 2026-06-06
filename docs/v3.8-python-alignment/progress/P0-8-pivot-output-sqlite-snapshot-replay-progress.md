# P0-8 Pivot Output SQLite Snapshot Replay Progress

Date: 2026-06-06

## Progress

- Added Java exporter for real Pivot output snapshots over an isolated neutral
  seed.
- Generated `tests/fixtures/java_pivot_output_snapshot_parity.json`.
- Added Python replay for flat row output, flat row+column output, and grid
  row+column output.
- Activated the `pivot-output-sqlite-snapshots` manifest lane.
- Recorded the Python Pivot cache-key collision for same-axis flat/grid
  requests as a planned follow-up, without changing production service code.

## Verification

- Default Java focused command failed because the local Postgres service for
  the `multi-db` profile was unavailable at `localhost:15432`:
  `mvn test -pl foggy-dataset-model -Dtest=JavaPivotOutputSnapshotTest`.
- Java producer passed against the SQLite-focused profile:
  `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaPivotOutputSnapshotTest`.
- Focused Python replay passed:
  `.venv/bin/python -m pytest tests/integration/test_java_pivot_output_snapshot_parity.py -q --tb=short`
  -> `2 passed in 0.42s`.
- Focused Python P0-7/P0-8 replay plus manifest passed:
  `.venv/bin/python -m pytest tests/integration/test_java_pivot_domain_snapshot_parity.py tests/integration/test_java_pivot_output_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q --tb=short`
  -> `8 passed in 0.45s`.
- Ruff passed:
  `.venv/bin/python -m ruff check tests/integration/test_java_pivot_output_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py`.

## Follow-Up

- Add subtotal and grand-total output snapshots.
- Add `parentShare` output snapshots.
- Add `baselineRatio` output snapshots.
- Add non-additive auxiliary requery output snapshots.
- Fix or explicitly key Python Pivot cache by output format before combining
  multiple output-shape cases in one service instance.
- Add pivot/domain governance propagation snapshots.
