# P0-14 Pivot Non-Additive Output Snapshot Replay Progress

Date: 2026-06-06

## Completed

- Added Java snapshot producer case for flat two-level rows with
  `rowSubtotals`, `grandTotal`, additive `salesAmount`, and non-additive
  `uniqueCustomers`.
- Updated the neutral seed with `customer_key` values that make additive
  subtotal behavior visibly wrong for `COUNT_DISTINCT`.
- Added Python auxiliary total requery support for ordinary Pivot generated
  subtotal and grand-total rows.
- Extended Python output replay to seed `customer_key` and compare
  `uniqueCustomers`.
- Regenerated `tests/fixtures/java_pivot_output_snapshot_parity.json` from the
  Java exporter. The fixture now contains thirteen cases.
- Updated alignment docs and Java-side snapshot workitem.

## Verification

Passed:

- `JAVA_HOME=/Users/fengjianguang/.jdk/temurin-17/Contents/Home mvn -pl foggy-dataset-model -am -P'!multi-db' -Dspring.profiles.active=sqlite -Dtest='JavaPivotOutputSnapshotTest' -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false test`
  - `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`
- `.venv/bin/python -m pytest tests/integration/test_java_pivot_output_snapshot_parity.py -q`
  - `2 passed in 0.43s`
- `.venv/bin/python -m ruff check src/foggy/dataset_model/semantic/pivot/non_additive_totals.py tests/integration/test_java_pivot_output_snapshot_parity.py`
  - `All checks passed!`
- `.venv/bin/python -m pytest -q`
  - `4041 passed, 232 skipped, 43 warnings in 17.50s`

## Notes

- This item intentionally does not touch Odoo business models.
- The Java worktree contains existing unrelated aggregate-join changes; this
  item only stages the Pivot snapshot producer and Pivot snapshot workitem
  doc.
- The Python worktree contains existing unrelated dictionary discovery changes;
  this item only stages the P0-14 service hunk and P0-14 files when committing.
