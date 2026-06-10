# P0-55 Compose PostgreSQL Join Snapshot Expansion Progress

## 2026-06-10

Status: complete.

Changes:

- Added Java compose snapshot case `join-postgres-cte`.
- Regenerated `tests/fixtures/java_compose_snapshot_parity.json`.
- Updated the compose coverage inventory test to require `postgres/join` to be
  covered.
- Updated the Java snapshot parity manifest to advertise PostgreSQL join CTE
  success shape evidence.

Evidence:

- Java exporter passed:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`.
- Coverage inventory reported `caseCount 24`, `successCaseCount 20`,
  `strictSuccessCaseCount 20`, and `successStrictCoverage 20/20`.
- Focused Python replay and manifest passed:
  `.venv/bin/python -m pytest tests/integration/test_compose_snapshot_coverage_script.py tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`.
- Ruff passed for the touched Python script/test replay files.
- `git diff --check` passed in both Java and Python worktrees.

Follow-up:

- Keep PostgreSQL join as stable SQL-shape evidence; broader live DB proof is
  outside this compiler snapshot lane.
