# Stage 4: SQL Server timeWindow Real DB Matrix — Progress

## Status: **complete** ✅

**Date**: 2026-04-28
**Scope**: Extend Python timeWindow real DB matrix to SQL Server 2022

---

## Summary

Stage 4 adds SQL Server 2022 as the third database engine in the Python
timeWindow real DB integration matrix, joining MySQL 8.0 and PostgreSQL 15.

The implementation required:
1. A new `SQLServerExecutor` class using `pyodbc` (synchronous driver
   wrapped in async interface)
2. SQL dialect translation at the executor layer: `LIMIT N` → `TOP N`
   injection and CTE-in-subquery hoisting (SQL Server forbids `WITH` inside
   `FROM (...)` subqueries)
3. Three SQL Server-specific smoke tests plus participation in all existing
   parametrized matrix tests

## Environment

| Item | Value |
|------|-------|
| Container | `foggy-demo-sqlserver` from Java demo `docker-compose.yml` |
| Image | `mcr.microsoft.com/mssql/server:2022-latest` |
| Host/Port | `localhost:11433` |
| Database | `foggy_test` |
| Credentials | `sa` / `Foggy_Test_123!` |
| ODBC Driver | `{SQL Server}` (built-in Windows driver) |
| Data | Shared schema with MySQL/PostgreSQL demo; fact_sales 2022–2025 |

## Covered Scenarios

| Scenario | Test IDs | Status |
|----------|----------|--------|
| Rolling 7d window | `test_real_db_rolling_range...[sqlserver]` | ✅ |
| Cumulative YTD | `test_real_db_cumulative...[sqlserver-ytd]` | ✅ |
| Cumulative MTD | `test_real_db_cumulative...[sqlserver-mtd]` | ✅ |
| Comparative YoY | `test_real_db_comparative...[sqlserver-yoy]` | ✅ |
| Comparative MoM | `test_real_db_comparative...[sqlserver-mom]` | ✅ |
| Comparative WoW | `test_real_db_comparative...[sqlserver-wow]` | ✅ |
| Post-calc growthPercent | `test_real_db_post_calculated...[sqlserver-growthPercent]` | ✅ |
| Post-calc rollingGap | `test_real_db_post_calculated...[sqlserver-rollingGap]` | ✅ |
| YoY with non-null prior | `test_sqlserver_yoy_returns_non_null_prior` | ✅ |
| YTD cumulative monotonicity | `test_sqlserver_cumulative_ytd_smoke` | ✅ |
| Post-calc growth % accuracy | `test_sqlserver_post_calc_growth_percent` | ✅ |

**Total: 11 SQL Server tests (8 matrix + 3 dedicated)**

## Skip Conditions

Tests skip safely in the following scenarios:
- `pyodbc` not installed → `_HAS_SQLSERVER_EXECUTOR = False`
- SQL Server container not running → `_probe_or_skip()` catches connection failure
- ODBC driver not found → pyodbc raises `InterfaceError` during connect

Default regression without SQL Server is unaffected.

## Connection Configuration

Defaults match docker-compose, overridable via environment variables:

| Variable | Default |
|----------|---------|
| `FOGGY_SQLSERVER_HOST` | `localhost` |
| `FOGGY_SQLSERVER_PORT` | `11433` |
| `FOGGY_SQLSERVER_DATABASE` | `foggy_test` |
| `FOGGY_SQLSERVER_USER` | `sa` |
| `FOGGY_SQLSERVER_PASSWORD` | `Foggy_Test_123!` |

## SQL Dialect Translation

Two executor-level transformations were required:

### 1. LIMIT → TOP / OFFSET-FETCH
The Python engine emits `LIMIT N` or `LIMIT N OFFSET M`. SQL Server requires:
- `LIMIT N` → inject `TOP N` into the outermost SELECT (handles CTEs)
- `LIMIT N OFFSET M` → `OFFSET M ROWS FETCH NEXT N ROWS ONLY` (requires ORDER BY)

### 2. CTE Hoisting from Subqueries
The post-calc wrapper pattern produces:
```sql
SELECT tw_result.*, (expr) AS "alias"
FROM (
  WITH __time_window_base AS (...) SELECT ...
) tw_result
```
SQL Server rejects this. The executor hoists the CTE to the top level.

## Known Limitations

- **Java `SchemaAwareFieldValidationStep`**: Post-calc field aliases
  (e.g. `growthPercent`) cannot be included in Java request columns.
  This is NOT a Stage 4 fix — documented as a future Java contract
  extension item.
- **ODBC Driver**: The `{SQL Server}` built-in driver works but newer
  `{ODBC Driver 17/18 for SQL Server}` may be preferred in CI/production
  for TLS/auth support.
- **Async**: `SQLServerExecutor` wraps synchronous `pyodbc` calls.
  For production use, consider `aioodbc` or thread-pool delegation.

## Files Changed

| File | Change |
|------|--------|
| `src/foggy/dataset/db/executor.py` | Added `SQLServerExecutor`, CTE hoisting, LIMIT→TOP conversion |
| `tests/integration/test_time_window_real_db_matrix.py` | Added `sqlserver` to matrix + 3 dedicated tests |
| `docs/v1.5/S4-sqlserver-timewindow-real-db-matrix-progress.md` | This file (NEW) |
| `docs/v1.5/P2-post-v1.5-followup-execution-plan.md` | Stage 4 status → complete |
