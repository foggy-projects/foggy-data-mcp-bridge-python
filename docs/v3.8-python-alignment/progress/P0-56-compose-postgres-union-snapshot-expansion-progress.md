# P0-56 Compose PostgreSQL Union Snapshot Expansion Progress

## 2026-06-10

Status: complete.

Changes:

- Added Java compose snapshot case `union-all-sales-orders-postgres`.
- Recorded Java's current direct top-level union output shape instead of a CTE
  wrapper expectation.
- Regenerated `tests/fixtures/java_compose_snapshot_parity.json`.
- Updated the compose coverage inventory test to require `postgres/union` to be
  covered.
- Updated the Java snapshot parity manifest to advertise PostgreSQL top-level
  union success shape evidence.

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

- Treat this as compiler-shape evidence. Add live result parity later only when
  the compose live DB lane is reopened.
