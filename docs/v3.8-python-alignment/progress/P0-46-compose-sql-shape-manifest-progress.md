# P0-46 Compose SQL Shape Manifest Progress

## 2026-06-10

Added fixture-level compose SQL shape metadata.

Changes:

- Java `JavaComposeSnapshotTest` now records compact `expected.sqlShape`
  metadata for successful compose snapshot cases.
- Java marks frozen root-wrapper cases with `strictSqlShape`, including base
  MySQL8, MySQL 5.7, PostgreSQL, SQL Server, SQL Server join fallback,
  SQL Server union-derived fallback, and SQL Server derived-chain fallback.
- Python compose replay compares stable SQL shape keys for every successful
  case: union, join type, embedded `FROM (WITH`, where, and orderBy presence.
- Python compose replay compares full root CTE/subquery shape only for strict
  cases.
- The known PostgreSQL derived-over-join root-wrapper difference remains
  visible in the fixture but is not promoted to a strict failure.

Evidence:

- Java focused exporter:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  passed with `3` profile executions.
- Python focused replay and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  passed with `6 passed in 0.49s`.

Status:

- Compose snapshot replay now has structural SQL-shape coverage beyond marker
  presence.
- Broader SQL golden coverage and PostgreSQL derived-over-join root-wrapper
  convergence remain separate follow-ups.
