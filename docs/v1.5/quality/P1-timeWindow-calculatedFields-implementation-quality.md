---
quality_scope: feature
quality_mode: pre-coverage-audit
version: v1.5 follow-up
target: P1-timeWindow-calculatedFields
status: reviewed
decision: ready-for-coverage-audit
reviewed_by: execution-agent
reviewed_at: 2026-04-28
follow_up_required: no
---

# Implementation Quality Gate

## Background

本质量门槛针对 Python 引擎 `timeWindow + calculatedFields` follow-up。Java 侧来源为 `foggy-data-mcp-bridge-wt-dev-compose` 的 8.4.0.beta 契约与 8.5.0.beta 运行时实现；Python 侧本轮目标是开放 timeWindow 结果集之上的后置 scalar calculatedFields，并继续 fail-closed 拒绝 targetMetrics 引用 calc field、后置 agg/window/缺失列。

## Check Basis

| 类型 | 路径 / 证据 |
|---|---|
| progress | `docs/v1.5/P1-timeWindow-calculatedFields-design-progress.md` |
| Java contract | `docs/8.4.0.beta/P2-timeWindow-calculatedFields-interaction-contract.md` |
| Java implementation | `ba7831e feat(timeWindow): support post calculatedFields in timeWindow context` |
| Python implementation | `123e093 feat(timeWindow): support post calculated fields` |
| quality fix | post calculatedField `alias` order-by mapping fixed in this review |
| full regression | `python -m pytest -q` -> 3301 passed / 1 xfailed |

## Changed Surface

| Area | Paths |
|---|---|
| timeWindow validator constants | `src/foggy/dataset_model/semantic/time_window.py` |
| pre-validation routing | `src/foggy/dataset_model/semantic/field_validator.py` |
| SQL lowering / wrapper projection | `src/foggy/dataset_model/semantic/service.py` |
| Java fixture catalog | `tests/fixtures/java_time_window_parity_catalog.json` |
| golden fixture tests | `tests/test_dataset_model/test_time_window_java_parity_catalog.py` |
| SQLite execution tests | `tests/test_dataset_model/test_time_window_sqlite_execution.py` |
| MySQL8 / Postgres integration tests | `tests/integration/test_time_window_real_db_matrix.py` |
| progress docs | `docs/v1.5/P1-timeWindow-*.md`, `docs/v1.5/README.md` |

## Quality Checklist

| Check | Result | Notes |
|---|---|---|
| scope conformance | pass | 实现只开放 Java 8.5.0 已定义的后置 scalar 子集，未扩展到二次聚合/窗口或 calc-as-targetMetric。 |
| code hygiene | pass | 未发现 debug 输出、临时分支、未落档 TODO；已有 sample print 位于历史 docstring/probe 文件，不属于本次改动。 |
| duplication and consolidation | pass | wrapper projection、post-calc 校验、post-calc select 构建已拆成独立 helper，未把逻辑继续堆入主 timeWindow builder。 |
| complexity and abstraction | pass-with-note | `SemanticQueryService` 的 timeWindow lowering 仍较集中；本次新增 helper 已把关键步骤分层，后续若继续扩展二次聚合/窗口再抽出独立 lowering service 更合适。 |
| error handling and edge cases | pass | target metric calc 引用、post calc 缺失列、agg、window 均返回 Java 同名错误码。 |
| readability and maintainability | pass | `tw_result` wrapper、derived-output resolver、order/limit 最终层策略可直接从 helper 名称读出意图。 |
| critical logic documentation | pass | progress 已记录 Java 契约、允许/禁止矩阵、参数顺序和测试证据；本质量记录补齐 alias order-by 修复证据。 |
| contract and compatibility | pass | 支持 Java camelCase calculatedFields keys；保留 Python snake_case 内部模型兼容。 |
| documentation and writeback | pass | progress / golden diff / real DB matrix / README 已记录 follow-up 状态；本记录作为进入 coverage audit 的前置证据。 |
| test alignment | pass | Java 17 fixture、SQLite 执行、MySQL8/Postgres 实库矩阵、既有 calculatedFields 回归、全量 pytest 均覆盖改动面。 |
| release readiness | pass | 无阻断质量问题，可进入 coverage audit。 |

## Findings

- No blocking findings.
- Quality review found and fixed one compatibility gap: when a post calculatedField declares `alias`, `orderBy.field` can now use the calculated field `name` and the final SQL orders by the emitted alias, matching the regular calculatedFields path.
- No required refactor before coverage audit.

## Risks / Follow-ups

- Expression-level aggregate function calls embedded directly in `expression` are not separately rejected beyond the Java 8.5.0 fixture contract, which rejects the `agg` property and window clauses. This is a parity choice, not a coverage blocker.
- SQL Server is now part of the Python real DB matrix via Stage 4; current evidence covers SQLite, MySQL8, Postgres, and SQL Server.
- Java/Python projection contract still differs for calculatedFields output aliases in `columns`: Python allows it, Java `SchemaAwareFieldValidationStep` currently rejects post-calc aliases such as `growthPercent` / `rollingGap`. This is deferred to Stage 5.

## Recommended Next Skills

- `foggy-test-coverage-audit`: next step, map requirement / error codes / execution paths to test evidence.
- `foggy-acceptance-signoff`: run after coverage audit passes.

## Decision

- decision: `ready-for-coverage-audit`
- can_enter_coverage_audit: yes
- follow_up_required: no
