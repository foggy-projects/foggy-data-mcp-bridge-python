# P0-12 Pivot ParentShare Output Snapshot Replay Progress

Date: 2026-06-06

## Status

Implemented and verified locally.

## Changes

Java:

- Extended `JavaPivotOutputSnapshotTest` with two `parentShare` cases:
  - `pivot-flat-rows-parent-share`
  - `pivot-grid-rows-columns-parent-share`
- Extended the isolated neutral seed with a second electronics subcategory so
  Java exports non-trivial shares:
  - `Align-Electronics-Sub`: `150 / 200 = 0.75`
  - `Align-Electronics-Alt`: `50 / 200 = 0.25`
  - `Align-Clothing-Sub`: `200 / 200 = 1`
- Updated the existing Java expected totals from `350` to `400` because the
  neutral seed now has four fact rows.

Python:

- Updated the Java Pivot output replay canonicalizer to include `share` in flat
  output rows when the request contains a metric named `share`.
- Added mixed metric detection for both string metrics and object metrics.
- Regenerated the Java Pivot output fixture with ten total cases.
- No Python production engine code was changed in this item.

Docs/manifest:

- Added this workitem and progress record.
- Updated the active Pivot output manifest lane to advertise parentShare output
  coverage.

## Verification

Passed:

- `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaPivotOutputSnapshotTest`
- `.venv/bin/python -m pytest tests/integration/test_java_pivot_output_snapshot_parity.py -q`
- `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_pivot_domain_snapshot_parity.py tests/integration/test_java_pivot_output_snapshot_parity.py tests/test_dataset_model/test_pivot_parent_share.py -q`
- `.venv/bin/python -m ruff check tests/integration/test_java_pivot_output_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py`
- `.venv/bin/python -m pytest --tb=short -q`

Initial replay evidence:

- The first Python replay after Java fixture export failed on
  `pivot-flat-rows-parent-share` because the replay canonicalizer omitted
  `share` from flat rows.
- After the scoped replay update, the same focused replay passed.

Full-suite result:

- `4041 passed, 232 skipped, 43 warnings in 17.23s`.

## Remaining Gaps

- `baselineRatio` output snapshots.
- Non-additive auxiliary requery output snapshots.
- Large-domain threshold and fail-closed snapshots.
- Pivot/domain governance propagation snapshots.
