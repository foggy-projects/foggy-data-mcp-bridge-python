# P0-13 Pivot BaselineRatio Output Snapshot Replay Progress

Date: 2026-06-06

## Completed

- Added Java snapshot producer cases for:
  - flat rows + columns `baselineRatio(first)`
  - grid rows + columns `baselineRatio(last)`
- Added Python runtime support for ordinary columns-axis `baselineRatio`.
- Extended Python output replay canonicalization to include arbitrary derived
  metric object names in flat output.
- Added baselineRatio output cases to
  `tests/fixtures/java_pivot_output_snapshot_parity.json`.
- Updated cascade and contract shell tests to use the Java-aligned
  `axis=columns` baselineRatio contract.
- Updated snapshot manifest and alignment docs.

## Verification

Passed:

- `.venv/bin/python -m pytest tests/test_dataset_model/test_pivot_parent_share.py::TestParentShareRejections::test_baseline_ratio_columns_first tests/integration/test_java_pivot_output_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_pivot_domain_snapshot_parity.py tests/test_dataset_model/test_pivot_v9_cascade_validation.py::TestCascadeRejected::test_baseline_ratio_with_cascade_rejected tests/test_dataset_model/test_pivot_v9_contract_shell.py -q --tb=short`
  - `17 passed in 0.53s`
- `.venv/bin/python -m ruff check src/foggy/dataset_model/semantic/pivot/baseline_ratio.py src/foggy/dataset_model/semantic/pivot/executor.py`
  - `All checks passed!`
- `.venv/bin/python -m pytest -q`
  - `4041 passed, 232 skipped, 43 warnings in 17.19s`

Observed but not used as a gate:

- A broad ruff run over legacy touched files reports existing project-wide
  pyupgrade/import debt in `src/foggy/mcp_spi/semantic.py` and older pivot
  tests. This workitem keeps the lint gate scoped to the new module and
  modified executor to avoid unrelated modernize churn.

Blocked:

- `mvn -pl foggy-dataset-model test -Dtest=JavaPivotOutputSnapshotTest`
  - testCompile failed before the target test executed because existing
    Java module test classpath classes were missing after compile.
- `mvn -pl foggy-dataset-model clean test -Dtest=JavaPivotOutputSnapshotTest`
  - Maven clean failed deleting `foggy-dataset-model/target/classes/.../engine`,
    then a direct rerun still failed during unrelated testCompile.

## Notes

- The Java worktree also contains existing unrelated changes in
  `AggregateJoinTableModel.java` and `AggregateJoinQueryModelTest.java`; this
  item does not modify or stage them.
- The Python worktree contains existing unrelated dictionary discovery changes;
  this item only stages baselineRatio-related hunks when committing.
