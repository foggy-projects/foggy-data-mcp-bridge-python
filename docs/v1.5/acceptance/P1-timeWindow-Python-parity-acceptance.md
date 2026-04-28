---
acceptance_scope: feature
version: v1.5 follow-up
target: P1-timeWindow-Python-parity
doc_role: acceptance-record
doc_purpose: 说明本文件用于 Python timeWindow parity lane 的功能级正式验收与签收结论记录
status: signed-off
decision: accepted-with-risks
signed_off_by: execution-agent
signed_off_at: 2026-04-28
reviewed_by: foggy-test-coverage-audit
blocking_items: []
follow_up_required: yes
evidence_count: 10
---

# Feature Acceptance

## Background

- Version: v1.5 follow-up
- Target: Python 引擎对 Java `SemanticDSL timeWindow` 能力做 parity 补齐
- Owner: `foggy-data-mcp-bridge-python`
- Upstream Java baseline: `foggy-data-mcp-bridge/docs/8.3.0.beta/acceptance/P1-SemanticDSL-TimeWindow-Java-acceptance.md`
- Scope: DTO / MCP payload passthrough、validator、rolling / cumulative SQL path、comparative period SQL path、SQLite / MySQL8 / Postgres 执行证据。

该功能是 v1.5 主版本之后的独立 parity lane，不改变 `docs/v1.5/acceptance/version-signoff.md` 对计算字段编译器三阶段的既有签收结论。

## Acceptance Basis

| 类型 | 路径 |
|---|---|
| progress | `docs/v1.5/P1-timeWindow-Python-parity-progress.md` |
| quality gate | `docs/v1.5/quality/P1-timeWindow-Python-parity-implementation-quality.md` |
| coverage audit | `docs/v1.5/coverage/P1-timeWindow-Python-parity-coverage-audit.md` |
| Python code | `src/foggy/dataset_model/semantic/time_window.py`, `src/foggy/dataset_model/semantic/service.py` |
| Python tests | `tests/test_dataset_model/test_time_window.py`, `tests/test_dataset_model/test_time_window_sqlite_execution.py`, `tests/test_mcp/test_java_alignment.py` |
| Java/demo seed | `foggy-data-mcp-bridge/foggy-dataset-demo/docker/mysql/init/04-seed-2025-sales.sql` |

## Checklist

- [x] `SemanticQueryRequest` 接收并输出 Java camelCase `timeWindow`。
- [x] MCP accessor 从 Java payload 构造请求时保留 `timeWindow` 原始结构。
- [x] Python validator 镜像 Java timeWindow 基础契约，包含 grain / comparison / range / value / targetMetrics / rollingAggregator 校验。
- [x] 合法但未进入 SQL path 的组合 fail-closed，不静默忽略。
- [x] rolling / cumulative window expansion IR 完成。
- [x] rolling / ytd / mtd 两层 SQL path 完成。
- [x] `[)` / `[]` value / range lowering 完成，参数走 bind params。
- [x] yoy / mom / wow comparative self-join SQL path 完成，输出 `__prior` / `__diff` / `__ratio`。
- [x] MySQL executor dialect inference 修复，避免 MySQL8 使用 ANSI 双引号 alias。
- [x] compact date key bind params 修复，避免严格驱动下 integer 参数不匹配。
- [x] wow/week 质量复核修复完成，demo model 暴露 `salesDate$week`。
- [x] SQLite 自动化实库执行覆盖 rolling range 和 yoy。
- [x] MySQL8 2025 seed 已补，Python service yoy 查询返回非空 prior/diff/ratio。
- [x] Experience validation: N/A，纯后端 / API / SQL 引擎能力，无 UI。
- [x] S4 quality gate 和 coverage audit 已完成。

## Evidence

- Quality gate:
  - `docs/v1.5/quality/P1-timeWindow-Python-parity-implementation-quality.md`
  - decision: `ready-for-coverage-audit`
- Coverage audit:
  - `docs/v1.5/coverage/P1-timeWindow-Python-parity-coverage-audit.md`
  - conclusion: `ready-with-gaps`
- Test:
  - `python -m pytest tests/test_dataset_model/test_time_window.py tests/test_dataset_model/test_time_window_sqlite_execution.py tests/test_dataset_model/test_window_functions.py tests/test_mcp/test_java_alignment.py -q`
  - result: 86 passed
- Regression:
  - `python -m pytest tests/test_dataset_model/test_sql_quoting_and_errors.py tests/test_dataset_model/test_conditional_aggregate_if_alignment.py -q`
  - result: 37 passed
- MySQL8 evidence:
  - `localhost:13308/foggy_test`
  - `fact_sales` has 3179 `TW2025%` rows, `date_key` range `20250101..20250331`
  - 2025 yoy query returned 3 rows with non-null `salesAmount__prior`, `salesAmount__diff`, `salesAmount__ratio`
- SQLite evidence:
  - automated test covers rolling range result and yoy Jan 2024 prior/diff/ratio result.
- Postgres evidence:
  - progress records local `foggy-demo-postgres` rolling range and yoy self-join probe.
- Experience:
  - N/A.

## Failed Items

- none

## Risks / Open Items

- **G1 MySQL8 / Postgres probes are not CI automation**：当前是本地实库证据，非阻断。后续如要强化长期回归保护，应补 docker-backed integration profile。
- **G2 no Java ↔ Python golden output automation**：当前依赖 Java acceptance baseline + Python mirror tests + 文档映射，非阻断。
- **G3 `timeWindow + calculatedFields` fail-closed**：当前明确非目标，行为是显式拒绝而不是错误执行，非阻断。

## Final Decision

- decision: **accepted-with-risks**
- status: **signed-off**
- rationale:
  - 核心 timeWindow parity 能力已完成，包含 DTO / MCP / validator / SQL preview / SQLite execution / MySQL8 real DB yoy evidence。
  - 质量门槛无阻断发现。
  - 覆盖审计结论为 `ready-with-gaps`，缺口均为非阻断的长期自动化和组合能力问题。
  - 无 failed item，无验收阻断项。

## Signoff Marker

- acceptance_status: signed-off
- acceptance_decision: accepted-with-risks
- signed_off_by: execution-agent
- signed_off_at: 2026-04-28
- acceptance_record: docs/v1.5/acceptance/P1-timeWindow-Python-parity-acceptance.md
- blocking_items: none
- follow_up_required: yes

