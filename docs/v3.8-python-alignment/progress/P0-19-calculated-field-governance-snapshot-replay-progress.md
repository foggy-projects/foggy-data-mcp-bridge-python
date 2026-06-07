# P0-19 Calculated Field Governance Snapshot Replay Progress

Date: 2026-06-07

## Completed

- Extended `JavaGovernanceSnapshotTest.java` so `query-validation` cases can
  carry `calculatedFields`.
- Added Java-exported neutral cases:
  - `query-denied-calculated-direct-dependency-refused`
  - `query-denied-calculated-transitive-dependency-refused`
  - `query-denied-calculated-relation-dependency-refused`
- Regenerated `tests/fixtures/java_governance_snapshot_parity.json`. The
  governance fixture now contains 21 cases.
- Extended Python governance replay to pass snapshot `calculatedFields` into
  `SemanticQueryRequest`.
- Updated the Java snapshot manifest and alignment docs for the P0-19 evidence.

## Verification

Passed:

- `mvn test -pl foggy-dataset-model -Dtest=JavaGovernanceSnapshotTest`
  - `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`
- `.venv/bin/ruff check tests/integration/test_java_governance_snapshot_parity.py`
  - `All checks passed!`
- `.venv/bin/python -m pytest tests/integration/test_java_governance_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - `6 passed in 0.45s`
- `.venv/bin/python -m pytest -q`
  - `4049 passed, 232 skipped, 43 warnings in 17.46s`

## Notes

- This item does not change Python production governance behavior.
- The Java worktree contains existing unrelated aggregate-join changes; this
  item only stages the governance snapshot producer when committing.
- The Python worktree contains existing unrelated dictionary discovery changes;
  this item only stages the P0-19 fixture, manifest, replay test, and alignment
  docs.
