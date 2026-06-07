# P0-21 Compose Script Rows Result Shape Snapshot Replay Progress

Date: 2026-06-07

## Completed

- Extended Java compose-script snapshot cases with
  `execute-base-plan-rows-envelope`.
- Added Java-side contract assertions that execute-mode `plans` is a row list.
- Stabilized Java runtime global snapshot ordering to avoid fixture churn.
- Regenerated `tests/fixtures/java_compose_script_snapshot_parity.json`.
- Extended Python compose-script replay to assert `expected.hasRows` payloads.
- Updated the Java snapshot manifest and alignment docs for the P0-21 evidence.

## Verification

Passed:

- `mvn test -pl foggy-dataset-model -Dtest=JavaComposeScriptSnapshotTest`
  - Maven ran default, MySQL, and Postgres surefire executions for the snapshot
    test.
  - all executions passed with `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`
- `.venv/bin/python -m pytest tests/integration/test_java_compose_script_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - `8 passed in 0.45s`
- `.venv/bin/ruff check tests/integration/test_java_compose_script_snapshot_parity.py`
  - `All checks passed!`
- `.venv/bin/python -m pytest -q`
  - `4049 passed, 232 skipped, 43 warnings in 17.75s`

## Notes

- This item does not change Python production script runtime behavior.
- The Java commit only stages the compose script snapshot producer.
- The Python worktree contains existing unrelated dictionary discovery changes;
  this item only stages the P0-21 fixture, manifest, replay test, and alignment
  docs.
