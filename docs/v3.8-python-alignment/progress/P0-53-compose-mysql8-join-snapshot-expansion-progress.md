# P0-53 Compose MySQL8 Join Snapshot Expansion Progress

## 2026-06-10

Status: complete.

Changes:

- Added Java compose snapshot case `join-mysql8-cte`.
- Regenerated `tests/fixtures/java_compose_snapshot_parity.json`.
- Updated the compose coverage inventory test to require `mysql8/join` to be
  covered.
- Preserved the remaining missing cells as future planning input.

Evidence:

- Java exporter passed:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`.
- Coverage inventory reported `caseCount 21`, `successCaseCount 17`,
  `strictSuccessCaseCount 17`, and `successStrictCoverage 17/17`.
- Focused Python replay and manifest passed:
  `.venv/bin/python -m pytest tests/integration/test_compose_snapshot_coverage_script.py tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  with `7 passed in 0.88s`.
- Ruff passed:
  `.venv/bin/ruff check scripts/summarize-compose-snapshot-coverage.py tests/integration/test_compose_snapshot_coverage_script.py tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py`.
- `git diff --check` passed in both Java and Python worktrees.

Follow-up:

- Next targeted compose expansion candidates are PostgreSQL union/join or a
  deliberate SQLite entrypoint, depending on whether we want more
  CTE-capable neutral evidence or a new dialect lane.
