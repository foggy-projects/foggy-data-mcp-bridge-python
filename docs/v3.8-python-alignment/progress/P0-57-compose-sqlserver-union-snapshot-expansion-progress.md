# P0-57 Compose SQL Server Union Snapshot Expansion Progress

## 2026-06-10

Status: complete.

Changes:

- Added Java compose snapshot case `union-all-sales-orders-sqlserver`.
- Kept strict SQL-shape checks for direct union output and forbidden
  SQL Server CTE embedding markers.
- Regenerated `tests/fixtures/java_compose_snapshot_parity.json`.
- Updated the compose coverage inventory test to require `sqlserver/union` to
  be covered.
- Updated the Java snapshot parity manifest to advertise SQL Server top-level
  union fallback shape evidence.

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

- SQL Server compose fallback remains covered at compiler shape level. Live SQL
  Server execution remains out of scope for this snapshot expansion.
