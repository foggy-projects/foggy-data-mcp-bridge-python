# P0-15 Pivot Domain Large-Domain Snapshot Replay Progress

Date: 2026-06-06

## Completed

- Added Java snapshot cases to `JavaPivotDomainSnapshotTest.java`:
  - `domain-sqlite-large-501-transport`
  - `domain-sqlite-python-bind-limit-gap`
- Regenerated `tests/fixtures/java_pivot_domain_snapshot_parity.json` from the
  Java exporter. The fixture now contains nine cases.
- Extended Python documented-gap replay so a gap can assert renderer-level
  fail-closed behavior, not only dialect dispatch refusal.
- Made Pivot translation replay tolerate missing
  `baselineRatioMetricNames` by treating it as an empty expected list.
- Updated alignment docs for the P0-15 snapshot evidence.

## Verification

Passed:

- `JAVA_HOME=/Users/fengjianguang/.jdk/temurin-17/Contents/Home mvn -pl foggy-dataset-model -am -P'!multi-db' -Dspring.profiles.active=sqlite -Dtest='JavaPivotDomainSnapshotTest' -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false test`
  - `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`
- `.venv/bin/python -m pytest tests/integration/test_java_pivot_domain_snapshot_parity.py -q`
  - `2 passed in 0.39s`
- `.venv/bin/python -m ruff check tests/integration/test_java_pivot_domain_snapshot_parity.py`
  - `All checks passed!`
- `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_pivot_domain_snapshot_parity.py -q`
  - `6 passed in 0.41s`
- `.venv/bin/python -m pytest -q`
  - `4041 passed, 232 skipped, 43 warnings in 17.66s`

## Notes

- This item intentionally keeps Python SQLite fail-closed at `1000 > 999`
  parameters.
- The Java worktree contains existing unrelated aggregate-join changes; this
  item only stages the Pivot domain snapshot producer when committing.
- The Python worktree contains existing unrelated dictionary discovery changes;
  this item only stages the P0-15 fixture, replay test, and alignment docs.
