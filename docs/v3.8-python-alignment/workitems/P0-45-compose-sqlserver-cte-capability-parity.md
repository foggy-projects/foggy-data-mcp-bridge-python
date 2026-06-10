# P0-45 Compose SQL Server CTE Capability Parity

## Requirement

Align Python compose planner SQL Server fallback behavior with Java.

Java `ComposePlanner` treats `mssql` / `sqlserver` as compose-level
subquery fallback dialects because SQL Server CTEs cannot be safely nested
under derived-table composition. Python must use the same rule in compose
lowering while leaving the lower-level SQL Server dialect capability model
unchanged.

## Scope

- Make Python compose `dialect_supports_cte("mssql"|"sqlserver")` return
  `False`, matching Java `ComposePlanner.dialectSupportsCte`.
- Keep `mysql8`, PostgreSQL, and SQLite CTE-capable in compose lowering.
- Keep bare `mysql` / `mysql57` as subquery fallback dialects.
- Update Python dialect fallback tests for single-base and join shapes.
- Add Java snapshot cases for MySQL 5.7, PostgreSQL, and SQL Server base
  fallback/CTE shape plus SQL Server join fallback.
- Replay Java compose snapshots after the capability change.

## Non-Goals

- Do not change `SqlServerDialect.supports_cte` outside compose planner.
- Do not add live SQL Server execution.
- Do not change stable relation outer-query SQL Server hoisting behavior.

## Acceptance

- Python compose fallback truth table matches Java compose planner.
- Python single-base `mssql` uses subquery fallback.
- Python join `mssql` uses subquery fallback.
- Java `JavaComposeSnapshotTest` exports cross-dialect base/join fallback
  markers for replay.
- Java compose snapshot replay remains green.
