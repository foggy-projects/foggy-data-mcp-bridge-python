# P0-11 Pivot RowSubtotals Output Snapshot Replay Progress

Date: 2026-06-06

## Status

Implemented and verified locally.

## Changes

Java:

- Extended `JavaPivotOutputSnapshotTest` with two row subtotal cases:
  - `pivot-flat-rows-subtotals-grand-total`
  - `pivot-grid-rows-columns-subtotals-grand-total`
- Extended the isolated seed contract with `subCategory` so the two-level row
  axis is represented in the Java-exported fixture.

Python:

- Updated ordinary Pivot post-processing to append row subtotal rows through
  the existing additive totals helper when `options.rowSubtotals=true`.
- Preserved the previous grandTotal-only path for requests that do not enable
  `rowSubtotals`.
- Updated the Java Pivot output replay seed and canonicalization to include
  optional `subCategory` values.
- Regenerated the Java Pivot output fixture with eight total cases.

Docs/manifest:

- Added this workitem and progress record.
- Updated the active Pivot output manifest lane to advertise rowSubtotals output
  coverage.

## Verification

Passed:

- `mvn clean test -P!multi-db -pl foggy-dataset-model -Dtest=JavaPivotOutputSnapshotTest`
- `.venv/bin/python -m pytest tests/integration/test_java_pivot_output_snapshot_parity.py -q`
- `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_pivot_domain_snapshot_parity.py tests/integration/test_java_pivot_output_snapshot_parity.py tests/test_dataset_model/test_pivot_v9_cascade_totals.py tests/test_dataset_model/test_pivot_parent_share.py::TestParentShareGrandTotal -q`
- `.venv/bin/python -m ruff check tests/integration/test_java_pivot_output_snapshot_parity.py`
- Direct rerun of the only full-suite failure:
  `.venv/bin/python -m pytest tests/compose/runtime/test_suspend_limits.py::TestResourceCleanup::test_cleanup_on_abort_suspended_run -q`

Ruff note:

- `.venv/bin/python -m ruff check tests/integration/test_java_pivot_output_snapshot_parity.py src/foggy/dataset_model/semantic/service.py`
  still fails on `service.py` with broad existing import ordering, typing
  modernization, and unused-import findings. This matches the previously
  recorded `service.py` lint debt and was not auto-fixed in this Pivot item.

Full-suite note:

- `.venv/bin/python -m pytest --tb=short -q` produced
  `1 failed, 4040 passed, 232 skipped, 43 warnings`.
- The failure was
  `tests/compose/runtime/test_suspend_limits.py::TestResourceCleanup::test_cleanup_on_abort_suspended_run`
  with an already-cleaned suspension slot.
- The same test passed when rerun directly. This matches the known intermittent
  compose suspend/cleanup area observed in earlier P0 runs and is not in the
  Pivot rowSubtotals path.

## Notes

The first Python replay after Java fixture export failed on
`pivot-flat-rows-subtotals-grand-total`, proving the row subtotal output gap.
After the scoped ordinary Pivot post-processing change, the replay passed
against the Java fixture without normalizing away Java's `ALL` and
`GRAND_TOTAL` markers.
