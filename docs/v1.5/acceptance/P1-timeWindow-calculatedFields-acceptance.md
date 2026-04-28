---
acceptance_scope: feature
version: v1.5 follow-up
target: P1-timeWindow-calculatedFields
doc_role: acceptance-record
doc_purpose: 说明本文件用于 Python timeWindow + calculatedFields follow-up 的功能级正式验收与签收结论记录
status: signed-off
decision: accepted
signed_off_by: execution-agent
signed_off_at: 2026-04-28
reviewed_by: N/A
blocking_items: []
follow_up_required: no
evidence_count: 8
---

# Feature Acceptance

## Document Purpose

- doc_type: acceptance
- intended_for: signoff-owner / reviewer / owning-module
- purpose: 记录 Python 引擎 `timeWindow + calculatedFields` 功能级正式验收结论与证据摘要

## Background

- Version: v1.5 follow-up
- Target: P1-timeWindow-calculatedFields
- Owner: `foggy-data-mcp-bridge-python`
- Java source repo: `foggy-data-mcp-bridge-wt-dev-compose`
- Goal: 对齐 Java 8.5.0 已实现的 `timeWindow` 后置 scalar calculatedFields 子集，保证合法组合可执行，非法组合按 Java 同名错误码 fail-closed。

本次验收不改变 v1.5 计算字段编译器三阶段主签收结论；它是 `timeWindow` parity lane 签收后的功能增强签收。

## Acceptance Basis

- `docs/v1.5/P1-timeWindow-calculatedFields-design-progress.md`
- `docs/v1.5/quality/P1-timeWindow-calculatedFields-implementation-quality.md`
- `docs/v1.5/coverage/P1-timeWindow-calculatedFields-coverage-audit.md`
- `docs/v1.5/P1-timeWindow-java-python-golden-diff-progress.md`
- `docs/v1.5/P1-timeWindow-real-db-integration-matrix-progress.md`
- Java contract: `docs/8.4.0.beta/P2-timeWindow-calculatedFields-interaction-contract.md`
- Java implementation: `ba7831e feat(timeWindow): support post calculatedFields in timeWindow context`
- Python implementation baseline: `123e093 feat(timeWindow): support post calculated fields`

## Checklist

- [x] scope 内功能点已全部交付：后置 scalar calculatedFields 可作用于 timeWindow 输出列。
- [x] 原始 acceptance criteria 已逐项覆盖：targetMetrics calc 引用、post missing field、post agg、post window 均按 Java 错误码拒绝。
- [x] SQL 语义达成：timeWindow 先生成结果，外层 `tw_result` projection 再追加 post calc，最终层应用 ORDER BY / LIMIT。
- [x] 质量闸门已完成：结论 `ready-for-coverage-audit`，并修复 alias/order-by 兼容缺口。
- [x] 覆盖审计已完成：结论 `ready-for-acceptance`。
- [x] 关键测试已通过：Java fixture、SQLite、MySQL8/Postgres 矩阵、相邻 calculatedFields 回归、全量 pytest 均通过。
- [x] 体验验证已完成，或明确标记 `N/A`：纯后端 DSL / SQL 能力，无 UI。
- [x] 文档、配置、依赖项已闭环：progress / quality / coverage / acceptance 均已落盘。

## Evidence

- Requirement / progress:
  - `docs/v1.5/P1-timeWindow-calculatedFields-design-progress.md`
- Quality:
  - `docs/v1.5/quality/P1-timeWindow-calculatedFields-implementation-quality.md`
- Coverage:
  - `docs/v1.5/coverage/P1-timeWindow-calculatedFields-coverage-audit.md`
- Golden fixture:
  - `tests/fixtures/java_time_window_parity_catalog.json`
  - `tests/test_dataset_model/test_time_window_java_parity_catalog.py`
- Runtime execution:
  - `tests/test_dataset_model/test_time_window_sqlite_execution.py`
  - `tests/integration/test_time_window_real_db_matrix.py`
- Adjacent regression:
  - `tests/test_dataset_model/test_time_window.py`
  - `tests/test_mcp/test_java_alignment.py`
  - `tests/test_dataset_model/test_calc_field_dependency_e2e.py`
  - `tests/test_dataset_model/test_semantic_service_formula_compiler.py`
  - `tests/test_dataset_model/test_window_functions.py`
  - `tests/test_dataset_model/test_sql_quoting_and_errors.py`
  - `tests/test_dataset_model/test_conditional_aggregate_if_alignment.py`
- Test runs:
  - `python -m pytest tests/test_dataset_model/test_time_window_java_parity_catalog.py tests/test_dataset_model/test_time_window_sqlite_execution.py -q` -> 22 passed
  - `python -m pytest tests/integration/test_time_window_real_db_matrix.py -q` -> 17 passed
  - combined timeWindow + calculatedFields regression -> 173 passed
  - `python -m pytest -q` -> 3301 passed / 1 xfailed

## Failed Items

- none

## Risks / Open Items

- SQL Server 不在当前 Python real DB matrix 中；当前矩阵范围是 SQLite、MySQL8、Postgres，与既有 timeWindow 集成范围一致，不阻断本次签收。
- 如 Java 后续开放二次聚合、二次窗口或 calculatedFields 作为 targetMetrics 输入，Python 需另开 follow-up；当前签收范围只覆盖 Java 8.5.0 后置 scalar 子集。

## Final Decision

结论：`accepted`。

理由：功能边界、错误码、SQL 语义、跨方言执行证据、质量门槛和覆盖审计均已闭环；无阻断项，残余风险均不影响当前 Java 8.5.0 子集的交付判断。

## Signoff Marker

- acceptance_status: signed-off
- acceptance_decision: accepted
- signed_off_by: execution-agent
- signed_off_at: 2026-04-28
- acceptance_record: docs/v1.5/acceptance/P1-timeWindow-calculatedFields-acceptance.md
- blocking_items: none
- follow_up_required: no
