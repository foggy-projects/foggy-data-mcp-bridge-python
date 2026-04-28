# S7 future Java contract expansion preflight

## 文档作用

- doc_type: preflight + contract-boundary-record
- intended_for: root-controller / Java contract owner / Python execution-agent / reviewer
- purpose: 记录 Stage 7 不立即开工的原因、候选契约扩展的业务动机、风险边界和 Python 侧进入实现前必须等待的 Java 证据

## 基本信息

- version: post-v1.5 follow-up
- priority: P2 when promoted by downstream demand
- status: wait-for-java-contract
- owner: `foggy-data-mcp-bridge-python` docs
- java_reference_repo: `foggy-data-mcp-bridge-wt-dev-compose`
- related_plan: `docs/v1.5/P2-post-v1.5-followup-execution-plan.md`
- experience: N/A，纯后端 DSL / SQL engine 契约边界记录，无 UI 交互面

## 当前结论

Stage 7 不是 Python 可独立抢跑的实现项。当前 Java 8.4.0 / 8.5.0 契约明确只开放 `timeWindow` 输出列上的后置 scalar calculatedFields 子集，并对以下能力保持 fail-closed 或 non-goal：

- `timeWindow` 后置二次聚合。
- `timeWindow` 后置二次窗口。
- `calculatedFields` 作为 `timeWindow.targetMetrics` 输入。
- explicit named CTE / recursive CTE。

Python 侧应继续镜像该边界：Java 契约未明确前，不改变运行时行为，不扩大 LLM schema 描述，不新增用户可见能力。

同时，Stage 7 的前置抽象应从"如何在 timeWindow DSL 里拼二次能力"调整为"如何把任意 QueryPlan 转成稳定 view/relation"。详见 `docs/v1.5/S7a-plan-stable-view-relation-contract-preflight.md`，该文件已升级为 formal contract draft。

## 这些能力要解决的问题

### 1. `timeWindow` 后置二次聚合

目标问题：用户已经得到 timeWindow 展开的明细结果后，希望再按更高层级汇总这些派生结果。

典型诉求：

- 先按 `store + month` 计算 `salesAmount__ratio`，再按 `region` 计算平均增长率。
- 先按 `product + day` 计算 `rolling_7d`，再按 `category` 求最大 / 平均 rolling 表现。
- 先得到每个客户群的同比差值，再在外层按渠道汇总差值。

当前不开放原因：

- 比率、差值、滚动值的二次聚合语义不天然一致：`AVG(ratio)`、`SUM(diff)`、重新计算整体 ratio 是三种不同口径。
- 很容易让用户误以为结果是 timeWindow 原始度量的自然汇总，实际可能是派生值的再聚合。
- SQL 结构需要明确外层 groupBy / having / orderBy 的执行层级，否则跨方言 CTE 与子查询包装容易漂移。

### 2. `timeWindow` 后置二次窗口

目标问题：用户想在 timeWindow 结果集之上再跑窗口函数，而不是只拿原始 timeWindow 派生列。

典型诉求：

- 对 `salesAmount__ratio` 做排名：按月找同比增长率排名前 N 的商品。
- 对 `salesAmount__diff` 再做移动平均：平滑同比差值。
- 对 `rollingGap` 再做累计或连续区间分析。

当前不开放原因：

- Java S16 历史决策已经把 rolling / cumulative 从 calculatedFields window path 切到 Compose plan，避免 inline window 被聚合校验误判。
- 二次窗口会重新引入窗口函数嵌套、partition/order/frame 层级歧义。
- SQL Server / MySQL / Postgres 对 CTE、窗口函数、ORDER BY 位置的限制不同，需要先有 Java 统一 SQL 形态和实库证据。

### 3. `calculatedFields` 作为 `timeWindow.targetMetrics` 输入

目标问题：用户希望对动态计算出来的指标直接做同比、环比、滚动或累计。

典型诉求：

- `grossMargin = salesAmount - costAmount`，然后对 `grossMargin` 做 YoY。
- `unitPrice = salesAmount / quantity`，然后对 `unitPrice` 做 rolling。
- `conversionRate = orders / visits`，然后对 `conversionRate` 做 MoM。

当前不开放原因：

- `targetMetrics` 当前要求是模型声明的聚合 measure；request-level calculatedFields 没有稳定的聚合口径声明。
- 动态 calc 可能依赖 timeWindow 输出，形成循环依赖。
- 对比率类 calc 做 timeWindow 时，正确口径通常不是先算行级 ratio 再聚合，而是先聚合分子/分母再计算 ratio。
- Java 契约已明确 `targetMetrics` 引用 calculatedFields 禁止，并给出 `TIMEWINDOW_TARGET_CALCULATED_FIELD_UNSUPPORTED`。

### 4. explicit named CTE / recursive CTE

目标问题：用户想显式命名中间查询、复用复杂子查询，或表达递归层级遍历。

典型诉求：

- 显式 `as: "monthly_sales"`，后续多个查询复用同名 CTE。
- 递归展开组织、品类、地区层级。

当前不开放原因：

- Java 现有契约优先提供自动 CTE dedup，未承诺显式命名 CTE。
- 递归 CTE 与 QM 层级算子存在职责重叠；需要先决定层级查询是否继续由 QM `childrenOf` / `descendantsOf` 负责。
- named CTE 会引入名称冲突、作用域、权限裁剪和错误定位的新契约。

## Stage 7 开工门槛

任一候选项进入实现前，Java 侧必须先提供：

- `QueryPlan -> Stable View/Relation` 契约：包含 SQL、params、alias、datasource identity、dialect/capabilities 和稳定 `OutputSchema`。
- timeWindow 派生列 schema semantics：列名、含义、来源、是否可被外层 groupBy / aggregate / window / orderBy 引用。
- 明确契约文档：允许矩阵、禁止矩阵、执行顺序、SQL 层级。
- 错误码：非法引用、语义歧义、方言不支持时的稳定错误码。
- Positive fixtures：至少覆盖 preview SQL 和 execute-mode happy path。
- Negative fixtures：至少覆盖循环依赖、未知列、非法 agg/window、方言限制。
- SQL shape baseline：说明外层 projection / groupBy / window / orderBy / limit 的相对位置。
- Real DB evidence：SQLite + MySQL8 + Postgres，SQL Server 若涉及窗口/CTE 必须覆盖或显式 skip。
- LLM schema 描述更新：只在能力真实可用后再公开给 LLM。

## Python 侧保持行为

- 继续支持已签收的 `timeWindow` 后置 scalar calculatedFields。
- 继续拒绝后置 `agg`。
- 继续拒绝后置 `partitionBy` / `windowFrame` / `windowOrderBy`。
- 继续拒绝 `targetMetrics` 引用 request-level calculatedFields。
- 不新增 named CTE / recursive CTE 语法。
- 不把 `columns=["amount AS amount1"]` 这种普通列 alias 混入 Stage 7；它应单独作为 columns alias 契约扩展评估。

## Progress Tracking

### Development Progress

- [x] Stage 7 当前状态确认：`wait-for-java-contract`。
- [x] 候选能力业务动机记录完成。
- [x] 当前 fail-closed 边界记录完成。
- [x] `Plan -> Stable View/Relation` 前置抽象已升级为 S7a formal contract draft。
- [ ] Java 契约发布后，按具体候选项新开独立 follow-up。

### Testing Progress

- status: N/A
- reason: 本阶段仅记录契约边界，不改运行时代码，不新增用户可执行能力。

### Experience Progress

- status: N/A
- reason: 无 UI / manual workflow 变化。

## 自检结论

- non-goals 未扩大：是。
- 当前 Python/Java 已签收 subset 未改变：是。
- 是否需要正式 quality gate：否，本文件仅为 preflight 记录。
- 是否可进入实现：否，等待 Java contract + fixture。
