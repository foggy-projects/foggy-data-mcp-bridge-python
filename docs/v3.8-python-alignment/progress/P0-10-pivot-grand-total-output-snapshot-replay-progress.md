# P0-10 Pivot GrandTotal Output Snapshot Replay Progress

Date: 2026-06-06

## Status

Implemented and verified locally.

## Changes

Java:

- Extended `JavaPivotOutputSnapshotTest` with three grandTotal cases:
  - `pivot-flat-rows-grand-total`
  - `pivot-flat-rows-columns-grand-total`
  - `pivot-grid-rows-columns-grand-total`
- Exported request `options.grandTotal=true` into
  `java_pivot_output_snapshot_parity.json`.

Python:

- Updated grandTotal row-axis marker from `ALL` to `GRAND_TOTAL` while keeping
  row subtotal marker as `ALL`.
- Updated existing cascade total expectations to match Java's grandTotal
  marker.
- Updated Java Pivot output replay to include request `options`.
- Regenerated the Java Pivot output fixture with six total cases.

Docs/manifest:

- Added this workitem and progress record.
- Updated the active Pivot output manifest lane to advertise grandTotal output
  coverage.

## Verification

Passed:

- `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaPivotOutputSnapshotTest`
- `.venv/bin/python -m pytest tests/integration/test_java_pivot_output_snapshot_parity.py tests/test_dataset_model/test_pivot_v9_cascade_totals.py tests/test_dataset_model/test_pivot_parent_share.py::TestParentShareGrandTotal -q`
- `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_pivot_domain_snapshot_parity.py tests/integration/test_java_pivot_output_snapshot_parity.py tests/test_dataset_model/test_pivot_v9_cascade_totals.py tests/test_dataset_model/test_pivot_parent_share.py::TestParentShareGrandTotal -q`
- `.venv/bin/python -m pytest tests/integration/test_pivot_v9_cascade_real_db_matrix.py -q`
- `.venv/bin/python -m ruff check src/foggy/dataset_model/semantic/pivot/cascade_totals.py tests/integration/test_java_pivot_output_snapshot_parity.py tests/test_dataset_model/test_pivot_v9_cascade_totals.py tests/integration/test_pivot_v9_cascade_real_db_matrix.py`
- Direct rerun of the only full-suite failure:
  `.venv/bin/python -m pytest tests/compose/runtime/test_handler_pause.py::TestTimerCleanup::test_completed_run_removed_from_manager -q`

Full-suite note:

- `.venv/bin/python -m pytest --tb=short -q` produced
  `1 failed, 4110 passed, 162 skipped, 44 warnings`.
- The failure was
  `tests/compose/runtime/test_handler_pause.py::TestTimerCleanup::test_completed_run_removed_from_manager`
  with `run_ctx.suspension is None`.
- The same test passed when rerun directly. This matches the known intermittent
  compose pause/cleanup area observed in earlier P0 runs and is not in the
  Pivot grandTotal path.

## Notes

This item deliberately does not claim rowSubtotals snapshot parity. Java and
Python both keep single-level rowSubtotals as a no-op, but two-level cascade
rowSubtotals need their own Java fixture and replay lane.
