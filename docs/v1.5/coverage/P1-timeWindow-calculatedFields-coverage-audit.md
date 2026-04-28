---
audit_scope: feature
audit_mode: pre-acceptance-check
version: v1.5 follow-up
target: P1-timeWindow-calculatedFields
status: reviewed
conclusion: ready-for-acceptance
reviewed_by: execution-agent
reviewed_at: 2026-04-28
follow_up_required: no
---

# Test Coverage Audit

## Background

本审计对象是 Python 引擎 `timeWindow + calculatedFields` follow-up。该能力补齐 Java 8.5.0 的后置 scalar calculatedFields 子集，要求 timeWindow 先生成派生结果列，再在最终 wrapper 层执行 row-level scalar projection；非法组合必须返回 Java 同名错误码。

审计目标：确认 Java fixture、错误码、SQL wrapper、参数顺序、ORDER BY / LIMIT 最终层、SQLite 执行、MySQL8/Postgres 实库矩阵，以及质量闸门修复的 alias/order-by 场景都有可复核证据。

## Audit Basis

| 类型 | 路径 / 证据 |
|---|---|
| progress | `docs/v1.5/P1-timeWindow-calculatedFields-design-progress.md` |
| quality gate | `docs/v1.5/quality/P1-timeWindow-calculatedFields-implementation-quality.md` |
| Java fixture snapshot | `tests/fixtures/java_time_window_parity_catalog.json` |
| golden tests | `tests/test_dataset_model/test_time_window_java_parity_catalog.py` |
| SQLite execution | `tests/test_dataset_model/test_time_window_sqlite_execution.py` |
| real DB matrix | `tests/integration/test_time_window_real_db_matrix.py` |
| adjacent regression | `tests/test_dataset_model/test_time_window.py`, `tests/test_mcp/test_java_alignment.py`, calculatedFields regression suites |
| full regression | `python -m pytest -q` -> 3299 passed / 1 skipped / 1 xfailed |

## Coverage Matrix

| Item | Risk | Unit Test | Integration Test | E2E Test | Playwright Test | Manual Evidence | Evidence Path | Coverage |
|---|---|---|---|---|---|---|---|---|
| TWC1 Java 8.5 post scalar happy fixtures are accepted | critical | yes | - | - | - | - | `test_time_window_java_parity_catalog.py`, `java_time_window_parity_catalog.json` | covered |
| TWC2 `targetMetrics` cannot reference calculatedFields | critical | yes | - | - | - | - | negative Java fixture, asserts `TIMEWINDOW_TARGET_CALCULATED_FIELD_UNSUPPORTED` | covered |
| TWC3 post calc missing derived column is rejected | critical | yes | - | - | - | - | negative Java fixture, asserts `TIMEWINDOW_POST_CALCULATED_FIELD_NOT_FOUND` | covered |
| TWC4 post calc `agg` is rejected | critical | yes | - | - | - | - | negative Java fixture, asserts `TIMEWINDOW_POST_CALCULATED_FIELD_AGG_UNSUPPORTED` | covered |
| TWC5 post calc window clauses are rejected | critical | yes | - | - | - | - | negative Java fixture, asserts `TIMEWINDOW_POST_CALCULATED_FIELD_WINDOW_UNSUPPORTED` | covered |
| TWC6 SQL wrapper projects `tw_result.*` plus calc expressions | critical | yes | yes | - | - | - | golden SQL assertions, SQLite execution tests | covered |
| TWC7 calc expression can reference comparative aliases like `salesAmount__ratio` | critical | yes | yes | - | - | - | `growthPercent = salesAmount__ratio * 100` SQLite + real DB matrix | covered |
| TWC8 calc expression can reference rolling aliases like `salesAmount__rolling_7d` | critical | yes | yes | - | - | - | `rollingGap = salesAmount - salesAmount__rolling_7d` SQLite + real DB matrix | covered |
| TWC9 wrapper preserves bind parameter order | critical | - | yes | - | - | - | SQLite execution asserts `response.params == [100]` for outer calc literal and existing range params for rolling | covered |
| TWC10 ORDER BY / LIMIT are applied at the final wrapper layer | major | yes | yes | - | - | - | SQL assertions and execution tests with final order_by | covered |
| TWC11 Java camelCase calculatedFields keys are normalized | major | yes | - | - | - | - | Java fixture catalog uses Java payload shape; service normalizes `returnType`, `dependsOn`, `partitionBy`, `windowOrderBy`, `windowFrame` | covered |
| TWC12 post calculatedField `alias` remains orderable by calc `name` | major | - | yes | - | - | - | `test_time_window_post_calculated_field_alias_is_orderable` | covered |
| TWC13 MySQL8/Postgres runtime path executes post calc SQL | critical | - | yes | - | - | - | `test_real_db_post_calculated_fields_execute` over MySQL8 + Postgres | covered |
| TWC14 Existing timeWindow and calculatedFields behavior does not regress | critical | yes | yes | - | - | - | 173-case focused regression and full pytest suite | covered |
| TWC15 UI / experience impact | minor | - | - | - | N/A | N/A | progress marks Experience Progress N/A | covered |

## Evidence Summary

- `python -m pytest tests/test_dataset_model/test_time_window_java_parity_catalog.py tests/test_dataset_model/test_time_window_sqlite_execution.py -q`
  - result: 22 passed
  - run date: 2026-04-28
- `python -m pytest tests/test_dataset_model/test_time_window.py tests/test_dataset_model/test_time_window_sqlite_execution.py tests/test_dataset_model/test_time_window_java_parity_catalog.py tests/test_mcp/test_java_alignment.py tests/test_dataset_model/test_calc_field_dependency_e2e.py tests/test_dataset_model/test_semantic_service_formula_compiler.py tests/test_dataset_model/test_window_functions.py tests/test_dataset_model/test_sql_quoting_and_errors.py tests/test_dataset_model/test_conditional_aggregate_if_alignment.py -q`
  - result: 173 passed
  - run date: 2026-04-28
- `python -m pytest tests/integration/test_time_window_real_db_matrix.py -q`
  - result: 17 passed
  - run date: 2026-04-28
- `python -m pytest -q`
  - result: 3299 passed / 1 skipped / 1 xfailed
  - skipped: `tests/integration/test_formula_parity.py` needs Java `_parity_snapshot.json`, unrelated to this feature.
  - xfailed: cross-datasource union live detection is an existing deferred contract.

## Gaps

- No blocking evidence gaps.
- Non-blocking residual risk: SQL Server is not in the current Python real DB matrix. Current covered runtime dialects are SQLite, MySQL8, and Postgres, which match the existing timeWindow integration scope.
- Non-blocking residual risk: expression-level aggregate function detection beyond the Java fixture contract is not separately tested because the current Java 8.5.0 contract rejects `agg` metadata and window clauses, not raw function-name heuristics inside scalar expressions.

## Recommended Next Skills

- `foggy-acceptance-signoff`: 主推。覆盖证据已足够进入正式功能签收。
- `integration-test`: N/A for this gate; current required integration coverage is already present.
- `foggy-bug-regression-workflow`: N/A，本轮质量闸门发现的 alias/order-by 缺口已补自动化回归。
- `playwright-cli`: N/A，无 UI。

## Conclusion

- conclusion: `ready-for-acceptance`
- can_enter_acceptance: yes
- follow_up_required: no

判定依据：Java fixture、错误码、SQL shape、参数顺序、SQLite 执行、MySQL8/Postgres 实库矩阵、alias/order-by 回归和全量 pytest 均已覆盖；剩余风险均不影响 Java 8.5.0 子集的正式签收判断。
