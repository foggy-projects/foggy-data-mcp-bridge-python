# P0-18 Authority Visible Model Governance Snapshot Replay Progress

Date: 2026-06-07

## Completed

- Extended `JavaGovernanceSnapshotTest.java` with an
  `authority-resolution` case type.
- Added Java-exported neutral cases:
  - `authority-visible-model-allow-compiles`
  - `authority-visible-model-deny-missing-binding-fails-closed`
- Regenerated `tests/fixtures/java_governance_snapshot_parity.json`. The
  governance fixture now contains 18 cases.
- Extended Python governance replay with a static resolver so the replay uses
  the compile entry point's one-shot authority-resolution path.
- Updated the Java snapshot manifest and alignment docs for the P0-18 evidence.

## Verification

Passed:

- `JAVA_HOME=/Users/fengjianguang/.jdk/temurin-17/Contents/Home mvn -pl foggy-dataset-model -am -P'!multi-db' -Dspring.profiles.active=sqlite -Dtest='JavaGovernanceSnapshotTest' -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false test`
  - First run hit a Maven incremental testCompile/classpath transient on
    existing compose classes such as `CteUnit`, `JoinSpec`, and `CteComposer`.
  - Immediate rerun passed:
    `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`.
- `.venv/bin/python -m ruff check tests/integration/test_java_governance_snapshot_parity.py`
  - `All checks passed!`
- `.venv/bin/python -m pytest tests/integration/test_java_governance_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - `6 passed in 0.53s`
- `.venv/bin/python -m pytest -q`
  - `4049 passed, 232 skipped, 43 warnings in 17.65s`

## Notes

- This item does not change Python production authorization behavior.
- The Java worktree contains existing unrelated aggregate-join changes; this
  item only stages the governance snapshot producer when committing.
- The Python worktree contains existing unrelated dictionary discovery changes;
  this item only stages the P0-18 fixture, manifest, replay test, and alignment
  docs.
