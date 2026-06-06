# P0-16 Pivot Domain Governance Snapshot Replay Progress

Date: 2026-06-06

## Completed

- Extended `JavaGovernanceSnapshotTest.java` with Pivot and domain transport
  query-validation case types.
- Added Java-exported neutral cases:
  - `pivot-denied-row-axis-refused`
  - `pivot-parent-share-denied-native-metric-refused`
  - `domain-transport-denied-domain-column-refused`
- Regenerated `tests/fixtures/java_governance_snapshot_parity.json`. The
  governance fixture now contains 16 cases.
- Extended Python governance replay to validate Pivot requests and requests
  carrying a `DomainTransportPlan` through the same denied-column fail-closed
  boundary.
- Updated the Java snapshot manifest and alignment docs for the P0-16 evidence.

## Verification

Passed:

- `JAVA_HOME=/Users/fengjianguang/.jdk/temurin-17/Contents/Home mvn -pl foggy-dataset-model -am -P'!multi-db' -Dspring.profiles.active=sqlite -Dtest='JavaGovernanceSnapshotTest' -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false test`
  - `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`
- `.venv/bin/python -m ruff check tests/integration/test_java_governance_snapshot_parity.py`
  - `All checks passed!`
- `.venv/bin/python -m pytest tests/integration/test_java_governance_snapshot_parity.py -q`
  - `2 passed in 0.64s`
- `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_governance_snapshot_parity.py -q`
  - `6 passed in 0.66s`
- `.venv/bin/python -m pytest tests/compose/runtime/test_handler_pause.py::TestFailClosed::test_resume_after_resume tests/compose/runtime/test_suspend_limits.py::TestResourceCleanup::test_cleanup_on_resume -q`
  - `2 passed in 0.03s`
- `.venv/bin/python -m pytest tests/compose/runtime/test_handler_pause.py::TestPureRuntimePause::test_reject_raises_in_handler -q`
  - `1 passed in 0.03s`

Full baseline:

- `.venv/bin/python -m pytest -q`
  - `2 failed, 4039 passed, 232 skipped, 45 warnings in 17.58s`
- `.venv/bin/python -m pytest -q`
  - `1 failed, 4040 passed, 232 skipped, 43 warnings in 17.82s`
- Failures were compose runtime pause/resume tests that passed when rerun
  directly, so P0-16 records the current full baseline as unstable rather than
  green.

## Notes

- This item does not change Python production authorization behavior.
- The Java worktree contains existing unrelated aggregate-join changes; this
  item only stages the governance snapshot producer when committing.
- The Python worktree contains existing unrelated dictionary discovery changes;
  this item only stages the P0-16 fixture, manifest, replay test, and alignment
  docs.
