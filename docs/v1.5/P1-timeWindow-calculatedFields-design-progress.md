# P1 timeWindow calculatedFields design progress

## 文档作用

- doc_type: workitem / progress
- intended_for: execution-agent / reviewer / signoff-owner
- purpose: 记录 Python `timeWindow + calculatedFields` 后续增强的跨引擎契约、分阶段设计和验收口径

## 基本信息

- version: v1.5 follow-up
- priority: P3
- status: signed-off
- source_type: post-acceptance follow-up
- owning_repo: `foggy-data-mcp-bridge-python`
- java_source_repo: `foggy-data-mcp-bridge-wt-dev-compose`
- java_contract_source:
  - `docs/8.4.0.beta/P2-timeWindow-calculatedFields-interaction-contract.md`
  - `docs/8.3.0.beta/compose-query-manuals-gap-tracker.md`
- java_implementation_commit: `ba7831e feat(timeWindow): support post calculatedFields in timeWindow context`
- python_upstream_acceptance: `docs/v1.5/acceptance/P1-timeWindow-Python-parity-acceptance.md`
- related_gap: G3 / Java G6 - `timeWindow + calculatedFields` post scalar subset

## Acceptance Status

- acceptance_status: signed-off
- acceptance_decision: accepted
- signed_off_by: execution-agent
- signed_off_at: 2026-04-28
- acceptance_record: docs/v1.5/acceptance/P1-timeWindow-calculatedFields-acceptance.md
- blocking_items: none
- follow_up_required: no

## 背景

Python v1.5 已完成计算字段编译器三阶段签收，`timeWindow` parity lane 也已完成 S4 签收和 P1/P2 follow-up。当前唯一明确未开放的组合能力是 `timeWindow + calculatedFields`：

- Python runtime 原先在 `_build_time_window_query()` 中显式抛出 `TIMEWINDOW_CALCULATED_FIELDS_NOT_IMPLEMENTED`。
- Java `dev-compose` 侧 8.4.0.beta 契约已定义允许/禁止矩阵，8.5.0.beta 已实现后置 scalar calculatedFields。
- Python 本轮按 Java 8.5.0 fixture 对齐实现，保留禁止 `targetMetrics` 引用 calculatedFields、禁止二次聚合/窗口的 fail-closed 行为。

## 目标结果

- 对齐 Java 8.5.0 首个可落地子集：只支持 `timeWindow` 结果列之上的后置 scalar calculatedFields。
- 对非法组合返回 Java 同名错误码。
- 通过 Java 17 fixture、SQLite 执行、MySQL8/Postgres 实库矩阵验证。

## 设计原则

### 1. 不允许 calculatedFields 作为 targetMetrics 输入

`timeWindow.targetMetrics` 必须继续指向模型中的聚合 measure，不允许引用请求级 `calculatedFields.name`。

原因：

- Java 设计文档已把该路径定义为循环依赖风险。
- Python 现有 timeWindow base CTE 会先按目标 measure 聚合，再展开 rolling / cumulative / comparative；让 calculated field 参与 base metric 会改变聚合阶段语义。

建议错误码：

- `TIMEWINDOW_TARGET_CALCULATED_FIELD_UNSUPPORTED`

### 2. 第一阶段只开放后置计算字段

允许的安全子集：

- timeWindow 先完成 base aggregation 和派生列展开。
- calculatedFields 再作用于 timeWindow 外层结果。
- 表达式只能引用 timeWindow 最终输出列，例如：
  - `salesAmount`
  - `salesAmount__prior`
  - `salesAmount__diff`
  - `salesAmount__ratio`
  - `salesAmount__rolling_7d`
  - `salesAmount__ytd`
  - `salesAmount__mtd`
  - 已投影维度列

推荐 SQL shape：

```sql
WITH __time_window_result AS (
  <existing timeWindow SQL without outer post-calc projections>
)
SELECT
  __time_window_result.*,
  <compiled derived-output expression> AS <calculated_alias>
FROM __time_window_result
```

### 3. 暂不支持聚合 / 窗口型后置 calculatedFields

第一阶段的后置计算字段应限制为 row-level scalar expression。

暂不开放：

- `agg` 非空的 calculatedFields
- `partitionBy` / `windowOrderBy` / `windowFrame`
- 在后置表达式中再次调用窗口函数
- 在后置表达式中对 `__prior` / `__diff` / `__ratio` 再聚合

原因：

- 后置 stage 已经是 timeWindow 展开后的结果集，再聚合需要明确二次 grouping contract。
- Java G6 尚未定义该语义，Python 不应先行产生跨引擎不一致行为。

建议错误码：

- `TIMEWINDOW_POST_CALCULATED_FIELD_AGG_UNSUPPORTED`
- `TIMEWINDOW_POST_CALCULATED_FIELD_WINDOW_UNSUPPORTED`

### 4. 表达式解析必须切换到 derived-output schema

Python 现有 calculatedFields 编译器主要面向模型字段解析。后置 timeWindow 计算字段不能继续用物理模型字段 resolver，否则会误拒绝 `salesAmount__prior` 等 timeWindow 派生 alias。

实现时需要新增或复用一个轻量 resolver：

- 输入：timeWindow 输出列集合
- 行为：只允许引用输出列集合内的字段 / alias
- SQL 编译：引用外层 CTE alias，而不是物理表列

建议错误码：

- `TIMEWINDOW_POST_CALCULATED_FIELD_FIELD_NOT_FOUND`

### 5. LIMIT / ORDER BY 语义保持在最终层

如果原 timeWindow 查询存在 `orderBy` / `limit`：

- base timeWindow expansion 先生成完整语义结果；
- 后置 calculatedFields 在 outer wrapper 中追加；
- 最终 `ORDER BY` / `LIMIT` 放在 wrapper 最外层，避免先截断再计算或别名不可见。

## 非目标

- 不实现"对计算字段做 yoy / mom / wow / rolling"。
- 不实现"post-calc 后再 group by / having"。
- 不改变 Java G6 尚未签收的 API 契约。
- 不把 `timeWindow` rolling / cumulative 回退到 calculatedFields 窗口函数路线；Java S16 已经明确该路线会触发聚合校验误判。

## 开发进度

- [x] 确认 Java source worktree：`foggy-data-mcp-bridge-wt-dev-compose`
- [x] 读取 Java timeWindow 设计中的 calculatedFields 共存规则
- [x] 读取 Java 8.4.0.beta G6 契约和 8.5.0.beta 实现 fixture
- [x] 确认 Python 当前 fail-closed guard
- [x] 记录 Python 分阶段设计与错误码建议
- [x] 移除 Python 全局 fail-closed guard，改为 Java 同名细分错误码
- [x] 实现后置 scalar calculatedFields 外层 projection
- [x] ORDER BY / LIMIT 保持在最终层
- [x] 同步 Java timeWindow parity catalog 至 17 cases
- [x] 质量闸门修复 post calculatedField `alias` 场景下按计算字段 `name` 排序的兼容缺口
- [x] 完成测试覆盖审计
- [x] 完成功能签收
- [x] 同步 LLM-facing query_model v3 schema / descriptions

## 测试计划

- [x] Java parity catalog: 17 cases passed, including 2 post-calc happy + 4 post-calc negative
- [x] SQLite execution: `growthPercent = salesAmount__ratio * 100`
- [x] SQLite execution: `rollingGap = salesAmount - salesAmount__rolling_7d`
- [x] SQLite execution: post calculatedField declares `alias`, `orderBy.field` uses calc `name`, final SQL orders by output alias
- [x] MySQL8/Postgres real DB matrix: post-calc YoY + rolling cases passed
- [x] Existing timeWindow / MCP regression passed
- [x] Existing calculatedFields regression passed
- [x] Full Python test suite: 3299 passed / 1 skipped / 1 xfailed
  - skipped: `tests/integration/test_formula_parity.py` requires Java `_parity_snapshot.json`, unrelated to this work
  - xfailed: cross-datasource union live detection is an existing deferred contract

## Experience Progress

- status: N/A
- reason: 纯后端 DSL / SQL contract 设计，无 UI 交互。

## Execution Check-in

### Completed

- Python runtime 已支持 Java 8.5.0 契约中的后置 scalar calculatedFields 子集。
- `targetMetrics` 引用 calc field 时返回 `TIMEWINDOW_TARGET_CALCULATED_FIELD_UNSUPPORTED`。
- 后置 calc field 引用缺失列、使用 `agg`、使用 window clause 时分别返回 Java 同名错误码。
- timeWindow 输出 SQL 在有后置 calc 时外包 `tw_result` projection，最终层再追加 ORDER BY / LIMIT。
- Java fixture source 明确来自 `foggy-data-mcp-bridge-wt-dev-compose`，不是 Java main worktree。
- 质量闸门已完成：`docs/v1.5/quality/P1-timeWindow-calculatedFields-implementation-quality.md`。
- 覆盖审计已完成：`docs/v1.5/coverage/P1-timeWindow-calculatedFields-coverage-audit.md`。
- 功能签收已完成：`docs/v1.5/acceptance/P1-timeWindow-calculatedFields-acceptance.md`。
- post calculatedField `alias` 场景下，`orderBy.field` 可继续使用 calc `name`，最终 SQL 会映射到输出 alias。
- LLM-facing docs 已同步：
  - `src/foggy/mcp/schemas/query_model_v3_schema.json`
  - `src/foggy/mcp/schemas/descriptions/query_model_v3.md`
  - `src/foggy/mcp/schemas/descriptions/query_model_v3_no_vector.md`
  - `src/foggy/mcp/schemas/descriptions/query_model_v3_basic.md`

### Self-check

- [x] owning repo / version path correct
- [x] Java source worktree correct
- [x] development progress recorded
- [x] testing progress recorded with passing evidence
- [x] experience progress explicitly marked N/A
- [x] Java 8.5.0 contract and fixture alignment recorded
- [x] implementation quality gate completed
- [x] coverage audit completed
- [x] acceptance signoff completed
- [x] LLM-facing schema / descriptions synced

## 后续衔接

当前 follow-up 已签收。后续如 Java 开放二次聚合、二次窗口或 calculatedFields 作为 targetMetrics 输入，Python 需另开 follow-up；当前实现只签收 Java 8.5.0 的后置 scalar 子集。
