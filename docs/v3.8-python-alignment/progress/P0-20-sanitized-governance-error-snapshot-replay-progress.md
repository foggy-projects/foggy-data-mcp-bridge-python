# P0-20 Sanitized Governance Error Snapshot Replay Progress

Date: 2026-06-07

## Completed

- Extended Java `query-validation` snapshot assertions with
  `expected.forbiddenMarkers`.
- Added Java-exported neutral cases:
  - `query-denied-sanitized-measure-error-payload`
  - `query-denied-sanitized-relation-error-payload`
- Regenerated `tests/fixtures/java_governance_snapshot_parity.json`. The
  governance fixture now contains 23 cases.
- Extended Python governance replay to assert forbidden physical table/column
  markers are absent from validation errors.
- Updated the Java snapshot manifest and alignment docs for the P0-20 evidence.

## Verification

Passed:

- `mvn test -pl foggy-dataset-model -Dtest=JavaGovernanceSnapshotTest`
  - first run hit a transient Maven incremental testCompile/classpath failure on
    existing pivot/preagg classes
  - immediate rerun passed:
    `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`
- `.venv/bin/ruff check tests/integration/test_java_governance_snapshot_parity.py`
  - `All checks passed!`
- `.venv/bin/python -m pytest tests/integration/test_java_governance_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - `6 passed in 0.47s`
- `.venv/bin/python -m pytest -q`
  - `4049 passed, 232 skipped, 43 warnings in 22.00s`

## Notes

- This item does not change Python production governance behavior.
- The Java worktree contains existing unrelated aggregate-join changes; this
  item only stages the governance snapshot producer when committing.
- The Python worktree contains existing unrelated dictionary discovery changes;
  this item only stages the P0-20 fixture, manifest, replay test, and alignment
  docs.
