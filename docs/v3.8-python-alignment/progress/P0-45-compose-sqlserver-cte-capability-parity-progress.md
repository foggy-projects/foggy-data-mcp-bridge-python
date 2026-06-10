# P0-45 Compose SQL Server CTE Capability Parity Progress

## 2026-06-10

Aligned Python compose planner SQL Server CTE capability with Java.

Changes:

- Python compose `dialect_supports_cte` now treats `mssql` and `sqlserver`
  as compose-level subquery fallback dialects.
- Python no longer delegates SQL Server compose fallback capability to
  `SqlServerDialect.supports_cte`; this keeps compose lowering aligned with
  Java while preserving the lower-level dialect model.
- Updated Python dialect fallback tests for CTE truth table, single-base
  `mssql`, and join `mssql` shapes.
- Java `JavaComposeSnapshotTest` now exports cross-dialect base and join shape
  markers for MySQL 5.7 subquery fallback, PostgreSQL CTE shape, SQL Server
  base subquery fallback, and SQL Server join subquery fallback.

Evidence:

- Java focused exporter:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  passed with `3` profile executions.
- Python focused fallback and replay coverage:
  `.venv/bin/python -m pytest tests/compose/compilation/test_dialect_fallback.py tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  passed with `36 passed in 0.17s`.
- Python compose compilation suite:
  `.venv/bin/python -m pytest tests/compose/compilation -q`
  passed with `275 passed in 0.68s`.
- Python full suite:
  `.venv/bin/python -m pytest -q`
  passed with `4082 passed, 232 skipped, 53 warnings in 17.95s`.

Status:

- Python compose-level SQL Server CTE capability now matches Java.
- Broader SQL golden shape expansion remains separate.
