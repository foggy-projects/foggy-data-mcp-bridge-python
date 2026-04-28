# P1 timeWindow calculatedFields design progress

## 文档作用

- doc_type: workitem / progress
- intended_for: execution-agent / reviewer / signoff-owner
- purpose: 记录 Python `timeWindow + calculatedFields` 后续增强的跨引擎契约、分阶段设计和验收口径

## 基本信息

- version: v1.5 follow-up
- priority: P3
- status: design-recorded / blocked-by-cross-engine-contract
- source_type: post-acceptance follow-up
- owning_repo: `foggy-data-mcp-bridge-python`
- java_source_repo: `foggy-data-mcp-bridge-wt-dev-compose`
- java_contract_source:
  - `docs/8.3.0.beta/P1-SemanticDSL-时间窗口能力设计.md`
  - `docs/8.3.0.beta/compose-query-manuals-gap-tracker.md`
- python_upstream_acceptance: `docs/v1.5/acceptance/P1-timeWindow-Python-parity-acceptance.md`
- related_gap: G3 / Java G6 - `timeWindow + calculatedFields` still fail-closed

## 背景

Python v1.5 已完成计算字段编译器三阶段签收，`timeWindow` parity lane 也已完成 S4 签收和 P1/P2 follow-up。当前唯一明确未开放的组合能力是 `timeWindow + calculatedFields`：

- Python runtime 当前在 `_build_time_window_query()` 中显式抛出 `TIMEWINDOW_CALCULATED_FIELDS_NOT_IMPLEMENTED`。
- Java `dev-compose` 侧文档允许 `calculatedFields` 与 `timeWindow` 共存，但红线是 `targetMetrics` 不得引用 `calculatedFields` 中定义的字段，避免循环依赖。
- Java gap tracker 中 G6 仍为 `open`，目标版本为 8.4.0.beta，尚未明确"计算字段先于还是后于 timeWindow 展开"。

## 目标结果

- 在 Java G6 正式关闭前，Python 不提前承诺完整组合能力。
- 明确首个可落地子集：只支持 `timeWindow` 结果列之上的后置计算字段。
- 保留当前 fail-closed 行为，直到测试矩阵和跨引擎契约足够完整。

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
- [x] 读取 Java gap tracker G6 状态：`open` / target `8.4.0.beta`
- [x] 确认 Python 当前 fail-closed guard
- [x] 记录 Python 分阶段设计与错误码建议
- [ ] 等待 Java G6 契约或产品确认后进入实现

## 测试计划

实现前应先补以下测试：

- negative: `targetMetrics` 引用 request `calculatedFields.name` 时返回 `TIMEWINDOW_TARGET_CALCULATED_FIELD_UNSUPPORTED`
- negative: 后置 calculatedFields 引用不存在的 timeWindow 输出列时返回 `TIMEWINDOW_POST_CALCULATED_FIELD_FIELD_NOT_FOUND`
- negative: 后置 calculatedFields 带 `agg` / window 配置时显式拒绝
- positive: comparative 结果上计算 `growthPercent = salesAmount__ratio * 100`
- positive: rolling 结果上计算 `rollingGap = salesAmount - salesAmount__rolling_7d`
- integration: SQLite / MySQL8 / Postgres 至少各一条后置 scalar calc 实跑
- parity: Java G6 fixture 可用后再补 Java/Python golden catalog 扩展

## Experience Progress

- status: N/A
- reason: 纯后端 DSL / SQL contract 设计，无 UI 交互。

## Execution Check-in

### Completed

- 当前 P3 只完成设计记录，不修改 runtime 行为。
- Python `timeWindow + calculatedFields` 仍保持 fail-closed。
- 设计明确以 Java `dev-compose` worktree 为契约来源，不再引用 Java main worktree。

### Self-check

- [x] owning repo / version path correct
- [x] Java source worktree correct
- [x] development progress recorded
- [x] testing progress recorded as plan, not falsely marked passed
- [x] experience progress explicitly marked N/A
- [x] cross-engine blocker recorded

## 后续衔接

推荐下一步先做 Java G6 契约收口或产品侧场景确认。若要 Python 先行实现，只建议以 feature-flag 或 fail-closed 子集方式开放"后置 scalar calculatedFields"，并在文档中标注为 Python provisional behavior。
