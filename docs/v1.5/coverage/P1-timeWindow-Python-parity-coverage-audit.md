---
audit_scope: feature
audit_mode: pre-acceptance-check
version: v1.5 follow-up
target: P1-timeWindow-Python-parity
status: reviewed
conclusion: ready-with-gaps
reviewed_by: execution-agent
reviewed_at: 2026-04-28
follow_up_required: yes
---

# Test Coverage Audit

## Background

本审计对象是 Python 引擎对 Java `SemanticDSL timeWindow` 能力的独立 parity lane。该 lane 不改变 v1.5 计算字段编译器三阶段主签收结论，而是对 Java 已签收 `timeWindow` 能力做 Python 侧补齐。

审计目标：确认 DTO / MCP 契约、validator、window expansion、SQL lowering、comparative period、dialect execution 和 demo seed 验证是否有足够测试证据支撑，并判断是否可进入正式功能验收。

## Audit Basis

| 类型 | 路径 |
|---|---|
| progress | `docs/v1.5/P1-timeWindow-Python-parity-progress.md` |
| quality gate | `docs/v1.5/quality/P1-timeWindow-Python-parity-implementation-quality.md` |
| Java upstream acceptance | `foggy-data-mcp-bridge/docs/8.3.0.beta/acceptance/P1-SemanticDSL-TimeWindow-Java-acceptance.md` |
| Python tests | `tests/test_mcp/test_java_alignment.py` |
| Python tests | `tests/test_dataset_model/test_time_window.py` |
| Python tests | `tests/test_dataset_model/test_time_window_sqlite_execution.py` |
| Regression tests | `tests/test_dataset_model/test_window_functions.py` |
| Regression tests | `tests/test_dataset_model/test_sql_quoting_and_errors.py`, `tests/test_dataset_model/test_conditional_aggregate_if_alignment.py` |
| MySQL8 seed | `foggy-data-mcp-bridge/foggy-dataset-demo/docker/mysql/init/04-seed-2025-sales.sql` |

## Coverage Matrix

| Item | Risk | Unit Test | Integration Test | E2E Test | Playwright Test | Manual Evidence | Evidence Path | Coverage |
|---|---|---|---|---|---|---|---|---|
| TW1 Java camelCase `timeWindow` request alias | critical | yes | - | - | - | - | `test_java_alignment.py` | covered |
| TW2 MCP `build_query_request` preserves nested payload keys | critical | yes | - | - | - | - | `test_java_alignment.py` | covered |
| TW3 validator mirrors Java error codes and grain / comparison matrix | critical | yes | - | - | - | - | `test_time_window.py::TestTimeWindowValidator` | covered |
| TW4 relative / compact date parsing | major | yes | - | - | - | - | `test_time_window.py::TestRelativeDateParser` | covered |
| TW5 rolling window expansion IR | major | yes | - | - | - | - | `test_time_window.py::TestTimeWindowExpander` | covered |
| TW6 ytd / mtd cumulative expansion IR | major | yes | - | - | - | - | `test_time_window.py::TestTimeWindowExpander` | covered |
| TW7 rolling / ytd / mtd two-stage SQL preview | critical | yes | - | - | - | - | `test_time_window.py::TestTimeWindowServiceGuard` | covered |
| TW8 `[)` / `[]` range lowering into base CTE bind params | critical | yes | yes | - | - | - | `test_time_window.py`, `test_time_window_sqlite_execution.py` | covered |
| TW9 executor dialect inference for MySQL quoting | critical | yes | - | - | - | - | `test_time_window.py::test_time_window_infers_mysql_dialect_from_executor` | covered |
| TW10 compact date key bind params for strict DB drivers | critical | yes | yes | - | - | yes | `test_time_window_sqlite_execution.py`, MySQL8 / Postgres probes in progress | covered |
| TW11 yoy comparative self-join SQL preview | critical | yes | - | - | - | - | `test_time_window.py::test_yoy_sql_preview_uses_self_join_comparative_plan` | covered |
| TW12 mom comparative self-join SQL preview | major | yes | - | - | - | - | `test_time_window.py::test_mom_sql_preview_uses_month_index_self_join_condition` | covered |
| TW13 wow day / week comparative self-join | major | yes | - | - | - | - | `test_time_window.py::test_wow_day_sql_preview_uses_day_offset_self_join_condition`, `test_wow_week_sql_preview_uses_week_index_self_join_condition` | covered |
| TW14 SQLite real execution for rolling range | critical | - | yes | - | - | - | `test_time_window_sqlite_execution.py::test_rolling_range_executes_on_sqlite` | covered |
| TW15 SQLite real execution for yoy prior / diff / ratio | critical | - | yes | - | - | - | `test_time_window_sqlite_execution.py::test_yoy_comparative_executes_on_sqlite` | covered |
| TW16 MySQL8 real execution for yoy with non-null prior | critical | - | - | - | - | yes | Local `foggy-demo-mysql8` probe, 2025 rows return non-null `salesAmount__prior/diff/ratio` | covered |
| TW17 MySQL8 2025 deterministic seed | major | - | - | - | - | yes | `04-seed-2025-sales.sql`, commit `9f63739` | covered |
| TW18 Postgres real execution smoke | major | - | - | - | - | yes | progress record for local `foggy-demo-postgres` rolling + yoy probe | covered |
| TW19 `timeWindow + calculatedFields` fail-closed | major | yes | - | - | - | - | `test_time_window.py` guard coverage | covered |
| TW20 no UI / experience surface | minor | - | - | - | N/A | N/A | progress `Experience Progress: N/A` | covered |

## Evidence Summary

- `python -m pytest tests/test_dataset_model/test_time_window.py tests/test_dataset_model/test_time_window_sqlite_execution.py tests/test_dataset_model/test_window_functions.py tests/test_mcp/test_java_alignment.py -q`
  - result: 86 passed
  - run date: 2026-04-28
- `python -m pytest tests/test_dataset_model/test_sql_quoting_and_errors.py tests/test_dataset_model/test_conditional_aggregate_if_alignment.py -q`
  - result: 37 passed
  - run date: 2026-04-28
- MySQL8 real DB yoy probe:
  - target: `localhost:13308/foggy_test`
  - result: `error=None`, 2025 months returned: 3
  - Jan 2025: `salesAmount=25629634.80`, `salesAmount__prior=17529506.00`, `salesAmount__diff=8100128.80`, `salesAmount__ratio=0.4620854`
  - Feb 2025: `salesAmount=24810051.20`, `salesAmount__prior=16790321.00`, `salesAmount__diff=8019730.20`, `salesAmount__ratio=0.4776401`
  - Mar 2025: `salesAmount=25333770.00`, `salesAmount__prior=17318898.00`, `salesAmount__diff=8014872.00`, `salesAmount__ratio=0.4627819`
- MySQL8 seed evidence:
  - `fact_sales` has 3179 `TW2025%` rows
  - `date_key` range: `20250101..20250331`
- Experience:
  - N/A, pure backend / API / SQL engine capability.

## Gaps

### G1: MySQL8 / Postgres real DB probes are local manual evidence

- severity: minor
- status: non-blocking
- impact: CI cannot yet catch all future dialect runtime regressions for MySQL8 / Postgres `timeWindow` paths.
- mitigation: SQLite real execution is automated; SQL preview and dialect inference are unit-tested; MySQL8 2025 yoy non-null result was verified manually against demo DB.
- recommendation: later add optional docker-backed integration tests when the repo has a stable DB test profile.

### G2: No Java ↔ Python golden output automation

- severity: minor
- status: non-blocking
- impact: Java future changes to `timeWindow` semantics will not automatically fail Python tests.
- mitigation: Python tests mirror the known Java contract and progress links to Java acceptance baseline.
- recommendation: create cross-language contract harness only if both engines keep evolving this DSL surface.

### G3: `timeWindow + calculatedFields` remains fail-closed

- severity: minor
- status: non-blocking
- impact: combined feature users receive an explicit unsupported result instead of execution.
- mitigation: this is documented as current non-goal; fail-closed behavior prevents silent wrong SQL.
- recommendation: promote to a later feature only after Java contract for the combined path is explicit.

## Recommended Next Skills

- `foggy-acceptance-signoff`: 主推。核心 coverage 已覆盖，只有非阻断测试自动化缺口，可进入功能签收。
- `integration-test`: 后续若要把 MySQL8 / Postgres manual probes 固化进 CI，再补 docker-backed integration profile。
- `foggy-bug-regression-workflow`: N/A，本轮未发现验收阻断 BUG。
- `playwright-cli`: N/A，无 UI。

## Conclusion

- conclusion: `ready-with-gaps`
- can_enter_acceptance: yes
- follow_up_required: yes

判定依据：

- critical coverage items TW1 / TW2 / TW3 / TW7 / TW8 / TW9 / TW10 / TW11 / TW14 / TW15 / TW16 均已覆盖。
- 核心自动化测试 86 + 37 均通过。
- SQLite real execution 已自动化；MySQL8 yoy 非空 prior/diff/ratio 已用 2025 seed 在本地实库复核。
- 剩余 G1 / G2 / G3 均为非阻断长期回归保护或组合能力扩展问题，不影响本次功能级验收。

