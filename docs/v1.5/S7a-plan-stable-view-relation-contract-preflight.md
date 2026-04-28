# S7a stable view/relation contract

## 文档作用

- doc_type: formal-contract-draft + implementation-boundary
- intended_for: root-controller / Java contract owner / Python execution-agent / reviewer
- purpose: 定义 `QueryPlan -> Stable View/Relation` 的正式双引擎契约草案，作为 Stage 7 二次聚合 / 二次窗口之前的基础设施

## 基本信息

- version: post-v1.5 follow-up
- priority: P1 when Stage 7 is promoted
- status: contract-draft-for-review
- owner: `foggy-data-mcp-bridge-python` docs
- java_reference_repo: `foggy-data-mcp-bridge-wt-dev-compose`
- related_plan: `docs/v1.5/P2-post-v1.5-followup-execution-plan.md`
- related_stage7: `docs/v1.5/S7-future-java-contract-expansion-preflight.md`
- experience: N/A，纯后端 DSL / SQL engine 契约边界记录，无 UI 交互面

## Contract Scope

本契约只定义稳定 relation 的对象模型、schema metadata、CTE 渲染规则和完成门。它不开放新的用户查询能力。

In scope:

- 任意 `QueryPlan` 可以被编译为稳定 relation。
- relation 必须携带 SQL、params、alias、datasource identity、dialect/capabilities、`OutputSchema`。
- timeWindow 派生列必须进入 `OutputSchema` 并携带语义 metadata。
- CTE / subquery / SQL Server hoisting 的写法必须结构化定义，不能靠字符串猜测。
- Java 先发布 contract + fixture，Python 再镜像。

Out of scope:

- 不开放 timeWindow 后置二次聚合。
- 不开放 timeWindow 后置二次窗口。
- 不开放 `calculatedFields` 作为 `timeWindow.targetMetrics`。
- 不实现 named CTE / recursive CTE。
- 不把 relation 物化为数据库真实 `CREATE VIEW`。
- 不处理普通 `columns=["amount AS amount1"]` alias 契约。

## 背景

`timeWindow` 后置二次聚合 / 二次窗口如果硬塞进同一个已经包含 `timeWindow` 的 DSL，会把执行层级、字段来源、窗口分区、聚合口径都叠在一个请求对象里。这个形态对 LLM 和人类都不友好，也会让 validator 和错误码变复杂。

更稳的抽象是把任意 `QueryPlan` 编译成一个稳定的 relation：

```text
QueryPlan
  -> OutputSchema
  -> CompiledRelation(alias, sql, params, outputSchema, datasourceId, capabilities)
  -> outer QueryPlan can use it as source
```

这个 relation 可以理解成临时 SQL view：不是数据库里的 `CREATE VIEW`，而是编译期可引用、可校验、可包装的 SQL 关系。

## 核心结论

`Plan -> Stable View/Relation` 本来就应该存在，不应只为二次聚合 / 二次窗口服务。原因：

- 引擎必须知道一个 plan 的稳定输出列名。
- 引擎必须知道每个输出列的含义、来源、是否派生、是否可再次引用。
- derived / join / union / permission validation / golden diff 都依赖稳定 schema。
- LLM schema 描述不能只暴露字段名，还需要解释派生列语义，例如 `salesAmount__ratio` 是当前值相对 prior 的比率。
- 二次聚合 / 二次窗口只是该基础设施的下游消费者。

Contract requirements:

- `CteUnit` 保持内部 SQL assembly primitive，不作为正式 stable relation contract。
- 正式 relation contract 由 `CompiledRelation` / `PlanView` 或等价抽象承载。
- `QueryPlan` 不新增无上下文 `toView()` / `toRelation()` 方法。
- relation 编译必须由 compiler/service 执行，因为需要 dialect、datasource、权限、参数绑定和 wrapping 策略。
- 当前 Stage 7 仍 fail-closed；本契约落地后再决定是否开放 outer aggregate / outer window。

## Review 结论收敛

`docs/v1.5/S7a/review1.md`、`review2.md`、`review3.md` 的意见总体一致：认可 `QueryPlan -> Stable View/Relation` 是 Stage 7 的前置基础设施，也认可二次聚合 / 二次窗口应建模为 outer plan over relation，而不是扩展当前 `timeWindow + calculatedFields` 后置 scalar 通道。

采纳口径：

- 以 `review2.md` 作为主基线：`CteUnit` 保持内部 SQL assembly primitive 职责，不作为正式 stable relation contract。
- 吸收 `review1.md` 的边界表达：`CompiledRelation` / `PlanView` 应同时承载 SQL、params、alias、schema、datasource identity、dialect/capabilities。
- 吸收 `review3.md` 的字段拆解：`ColumnSpec` 需要补充语义 metadata，但不采纳"短期先把 `CteUnit` 扩成正式 relation contract"的路线。

不采纳 `CteUnit.outputSchema` 作为正式短期契约的原因：

- `CteUnit` 当前在 Java / Python 两侧都是 SQL 片段拼装对象，语义上更接近 `WITH alias AS (sql)` 或 inline subquery 单元。
- Python `timeWindow` 目前主要在 semantic service 查询路径，不完全走 compose plan，因此只扩 `CteUnit` 不能覆盖 timeWindow 输出 schema 契约。
- 一旦 `CteUnit` 同时承载 schema、datasource、permission、capabilities，会混淆物理 SQL assembly 和可复用 relation 的边界。

## 对象模型

推荐不要把 `toView()` 直接放到 `QueryPlan` 上作为无参方法。SQL 编译依赖 dialect、权限、datasource、CTE 策略和参数绑定，应该由 compiler/service 负责。

建议形态：

```text
deriveSchema(plan) -> OutputSchema
compileToRelation(plan, context) -> CompiledRelation
```

边界要求：

- `OutputSchema`：描述 relation 输出列及列语义。
- `CteUnit`：保留为内部 SQL assembly primitive，不作为公开稳定 relation contract。
- `ComposedSql`：最终可执行 SQL + params。
- `CompiledRelation` / `PlanView`：面向外层 query / LLM / validator / parity fixture 的稳定编译期 relation。

正式候选结构：

```text
CompiledRelation:
  alias: string
  relationSql: RelationSql
  params: list                  # flattened params in render order
  outputSchema: OutputSchema
  datasourceId: optional string
  dialect: string
  capabilities: RelationCapabilities
  sourcePlanId: optional string
  permissionState: unknown | pre_authorized | authorized
```

`RelationSql` 必须是结构化 SQL，而不是任意 raw SQL 字符串：

```text
RelationSql:
  withItems: list<CteItem>
  bodySql: string               # SELECT ...，可以引用 withItems
  bodyParams: list
  preferredAlias: string

CteItem:
  name: string
  sql: string                   # SELECT ...，不得包含顶层 WITH，除非 marked nested
  params: list
  recursive: boolean = false
```

`RelationCapabilities`：

```text
RelationCapabilities:
  canInlineAsSubquery: boolean
  canHoistCte: boolean
  containsWithItems: boolean
  supportsOuterAggregate: boolean
  supportsOuterWindow: boolean
  requiresTopLevelWith: boolean
  relationWrapStrategy: inline_subquery | hoisted_cte | native_cte | fail_closed
```

`OutputSchema` 应至少表达：

- output name：外层可引用列名。
- expression/source：列来自哪个上游字段或表达式。
- semantic kind：base field / aggregate measure / timeWindow derived / scalar calc / window calc。
- value meaning：面向 LLM / reviewer 的语义说明。
- lineage：可选，原始模型字段或上游 relation 字段。
- reference policy：是否可在外层 groupBy / aggregate / window / orderBy 中引用。

建议 metadata 使用闭合集合或 string-backed constants，而不是完全自由字符串，避免 Java / Python 漂移：

```text
semanticKind:
  base_field
  aggregate_measure
  time_window_derived
  scalar_calc
  window_calc

referencePolicy:
  readable
  groupable
  aggregatable
  windowable
  orderable
```

`referencePolicy` 是能力集合，不是单值。示例：`salesAmount__ratio` 可 `readable/orderable`，是否可 `aggregatable` 必须由外层业务口径明确，不能默认等价于重新计算整体 ratio。

## CTE Rendering Contract

Stable Relation 的 SQL 写法必须遵守一个核心不变量：

```text
Never produce: FROM (WITH ... SELECT ...) AS rel
```

原因：

- SQL Server 不允许 CTE 出现在 derived table 内部。
- 多层 relation 如果靠 raw SQL 嵌套，params 顺序、CTE name collision、dialect fallback 都会失控。
- Java / Python 已存在不同 SQL 生成路径，必须用结构化 `RelationSql` 统一外层包装。

### Case A: relation 无 CTE

当 `RelationSql.withItems` 为空时，可以直接 inline subquery：

```sql
SELECT outer_cols
FROM (
  SELECT base_cols
  FROM fact_sales
  WHERE sales_date >= ?
) AS rel_0
```

也可以在 CTE-capable dialect 中包装成 native CTE：

```sql
WITH rel_0 AS (
  SELECT base_cols
  FROM fact_sales
  WHERE sales_date >= ?
)
SELECT outer_cols
FROM rel_0
```

默认推荐：

- 单层 relation：允许 inline subquery。
- relation 将被多处复用：推荐 native CTE。
- MySQL 5.7：只能 inline subquery，不能 native CTE。

### Case B: relation 内部已有 CTE

当 `RelationSql.withItems` 非空时，不允许直接把 `bodySql` 加 `WITH` 后塞进 `FROM (...)`。必须 hoist：

```sql
WITH
  __rel0_tw_base AS (
    SELECT salesDate, storeName, SUM(salesAmount) AS salesAmount
    FROM fact_sales
    GROUP BY salesDate, storeName
  ),
  rel_0 AS (
    SELECT
      cur.storeName,
      cur.salesAmount,
      prior.salesAmount AS salesAmount__prior,
      cur.salesAmount - prior.salesAmount AS salesAmount__diff,
      CASE
        WHEN prior.salesAmount IS NULL OR prior.salesAmount = 0 THEN NULL
        ELSE (cur.salesAmount - prior.salesAmount) / prior.salesAmount
      END AS salesAmount__ratio
    FROM __rel0_tw_base cur
    LEFT JOIN __rel0_tw_base prior ON ...
  )
SELECT outer_cols
FROM rel_0
```

规则：

- `withItems` 先渲染。
- relation 自身再作为一个 CTE item：`rel_0 AS (<bodySql>)`。
- outer query 只从 `rel_0` 读取。
- CTE 名称必须由 compiler 分配并带 relation prefix，例如 `__rel0_tw_base`，避免多个 relation 合并时冲突。

### Case C: SQL Server

SQL Server 必须优先使用 hoisted top-level `WITH`，且由于 T-SQL 的严格要求，建议使用前置分号防御（`;WITH`），并注意 CTE 内部禁止出现无 `TOP`/`OFFSET` 的 `ORDER BY`：

```sql
;WITH
  __rel0_tw_base AS (...),
  rel_0 AS (...)
SELECT outer_cols
FROM rel_0
```

当前实现基线：

- Java compose 现状对 `mssql` / `sqlserver` 使用全局 `useCte=false`，即优先 inline subquery fallback，目的是避免 nested CTE。
- Python compose / semantic timeWindow / executor 路径存在 CTE hoisting 入口，但并不等价于已经发布了 relation-level wrapping contract。
- S7a 不要求现有 compose 全局策略立即翻转；它要求新增 Stable Relation 时必须显式选择 `relationWrapStrategy`。

SQL Server relation-level 策略：

- 如果 relation 没有 inner CTE，允许 `inline_subquery`。
- 如果 relation 有 inner CTE，优先 `hoisted_cte`。
- 如果当前 Java 实现阶段暂不支持 SQL Server hoisting，可以对该 relation 返回 `fail_closed` / `RELATION_CTE_HOIST_UNSUPPORTED`，但不能生成 `FROM (WITH ... )`。
- 只有当 compiler 能把 inner CTE 结构性改写为不含 `WITH` 的 inline subquery 时，才允许对 SQL Server 使用 `inline_subquery` 兜底。

禁止：

```sql
SELECT outer_cols
FROM (
  WITH __time_window_base AS (...)
  SELECT ...
) AS rel_0
```

如果某个 relation 无法被 hoist，也无法改写为 inline subquery，必须 fail-closed，不能生成可能在 SQL Server 运行失败的 SQL。

### Case D: MySQL 5.7

MySQL 5.7 不支持 CTE。规则：

- `withItems` 为空：允许 inline subquery。
- `withItems` 非空：只有当 compiler 能把每个 CTE 结构性改写为 inline subquery 时才允许继续。
- 不能结构性改写时，返回 dialect unsupported / relation wrap unsupported 错误。

### Case E: MySQL 8 / PostgreSQL / SQLite

这些方言允许 top-level CTE。默认使用 hoisted CTE 渲染，因为它与 SQL Server 的安全写法一致，也更利于 Java/Python parity snapshot。

SQLite 额外注意：

- 如果 relation body 使用 `FULL OUTER JOIN` 等 SQLite 版本相关能力，仍由现有 dialect capability / real DB matrix 兜底。

### Params Order

参数顺序必须稳定：

```text
flattenedParams = withItem[0].params
               + withItem[1].params
               + ...
               + relationSql.bodyParams
               + outerQuery.params
```

任何 Java / Python snapshot 都必须校验 params 顺序，而不只校验 SQL 结构。

### CTE Name Collision

CTE 名称由 compiler 统一分配，不允许用户输入直接成为 CTE name。

推荐命名：

```text
rel_0
__rel0_tw_base
__rel0_tw_prior
__rel1_base
```

规则：

- relation alias 使用 `rel_N`。
- relation 内部 CTE 使用 `__relN_*` prefix。
- outer compiler 合并多个 relation 时，如果发现 CTE name collision，必须重命名并同步重写引用，或 fail-closed。

## 对 timeWindow 的意义

当前 `timeWindow` 输出列命名已经有约定：

- `metric__prior`
- `metric__diff`
- `metric__ratio`
- `metric__rolling_{N}{unit}`
- `metric__ytd`
- `metric__mtd`

但未来要让外层 QueryPlan 稳定消费这些列，仅有命名约定还不够。需要把含义写进 schema：

- `salesAmount__prior`：上一对比周期的 `salesAmount` 聚合值。
- `salesAmount__diff`：当前周期值减 prior 周期值。
- `salesAmount__ratio`：当前周期值相对 prior 周期值的比率。
- `salesAmount__rolling_7d`：按 timeWindow field 排序的 7 天滚动聚合结果。

这样 LLM 和外层 validator 才能区分：

- 这是可直接展示的派生值。
- 这是可做 scalar post-calc 的列。
- 这是可在显式 outer aggregate 中再聚合的列。
- 这是只能在显式 outer window 中引用的列。

## 方言与权限边界

Stable Relation 不能只保存 SQL 字符串。至少需要把 relation wrapping 策略作为 capabilities 固化，避免外层 plan 包装后在特定方言下失效。

特别风险：

- Java compose 当前对 `mssql` / `sqlserver` 使用 subquery fallback，避免 nested CTE。
- Python compose 与 semantic timeWindow 路径存在不同的 CTE / hoisting 处理入口。
- SQL Server 的 `WITH` 位置敏感，future relation over relation 如果包含 inner `WITH`，必须明确使用 hoisted CTE、inline subquery 或 fail-closed。

权限 / datasource 规则：

- `CompiledRelation` 必须携带 datasource identity，不能要求外层 plan 重新回溯 hidden source plan。
- `outputSchema` 应代表外层可见 schema。权限裁剪未纳入当前阶段时，必须显式标注 `permissionState` 或 equivalent marker，避免被误用成授权后 schema。
- 派生列需要 lineage，避免通过 `diff` / `ratio` 等字段间接暴露被拒绝的源列。

## Contract Fixtures

Java 侧正式发布本契约时，至少需要输出以下 fixture，Python mirror 必须消费：

```text
_stable_relation_schema_snapshot.json
```

建议结构：

```json
{
  "source": "StableRelationSnapshotTest",
  "contractVersion": "S7a-1",
  "dialect": "mysql8",
  "cases": [
    {
      "id": "timewindow-yoy-relation",
      "relation": {
        "alias": "rel_0",
        "wrapStrategy": "hoisted_cte",
        "datasourceId": "demo",
        "permissionState": "unknown",
        "capabilities": {
          "containsWithItems": true,
          "canHoistCte": true,
          "canInlineAsSubquery": false,
          "supportsOuterAggregate": false,
          "supportsOuterWindow": false
        },
        "outputSchema": [
          {
            "name": "salesAmount__ratio",
            "semanticKind": "time_window_derived",
            "referencePolicy": ["readable", "orderable"],
            "valueMeaning": "current period salesAmount relative to prior period",
            "lineage": ["salesAmount"]
          }
        ]
      },
      "sqlMarkers": [
        "WITH",
        "rel_0 AS",
        "FROM rel_0"
      ],
      "forbiddenSqlMarkers": [
        "FROM (WITH"
      ]
    }
  ]
}
```

Fixture 要求：

- 至少覆盖 `timeWindow` yoy / rolling / cumulative 三类 relation。
- 至少覆盖 MySQL8、Postgres、SQLite、SQL Server 的 wrapping marker。
- SQL Server fixture 必须断言不存在 `FROM (WITH`。
- params 顺序必须进入 snapshot。
- `outputSchema` 必须包含 timeWindow 派生列 metadata。

## Error Boundaries

新增 relation contract 后，以下行为仍必须 fail-closed：

- `timeWindow + calculatedFields.agg`
- `timeWindow + calculatedFields.windowFrame`
- `timeWindow.targetMetrics` 引用 request-level calculatedFields
- 普通 `columns=["amount AS amount1"]` alias 自动开放
- named / recursive CTE
- relation wrapping strategy 不支持目标 dialect
- relation datasource 与 outer plan datasource 不一致

候选错误码：

```text
RELATION_WRAP_UNSUPPORTED
RELATION_CTE_HOIST_UNSUPPORTED
RELATION_DATASOURCE_MISMATCH
RELATION_OUTPUT_SCHEMA_UNAVAILABLE
RELATION_COLUMN_REFERENCE_UNSUPPORTED
```

## 与 Stage 7 的关系

Stage 7 的二次能力不应设计成：

```text
timeWindow + calculatedFields.agg/windowFrame
```

更合理的设计是：

```text
timeWindow plan
  -> CompiledRelation / stable view
  -> DerivedQueryPlan over relation
  -> outer aggregate / outer window
```

因此 Stage 7 的实际前置任务应是：

1. Java 侧确认 `OutputSchema` 是否已足够表达 timeWindow 派生列语义。
2. Java 侧确认 `CompiledRelation` / `PlanView` 抽象与 `CteUnit` 的职责边界。
3. Java 侧给出 relation 包装 SQL 的方言规则，特别是 SQL Server CTE hoisting。
4. Python 侧镜像对象模型与 schema semantics。
5. 之后才讨论二次聚合 / 二次窗口是否开放。

## 非目标

- 不在本 preflight 中开放二次聚合。
- 不在本 preflight 中开放二次窗口。
- 不改变 `timeWindow + calculatedFields` 当前后置 scalar 子集。
- 不要求把 relation 物化成数据库真实 view。
- 不把普通 `columns=["amount AS amount1"]` alias 问题混入本契约。
- 不把 `CteUnit` 扩展成正式对外 stable relation contract。

## Progress Tracking

### Development Progress

- [x] 抽象边界确认：`Plan -> Stable View/Relation` 是基础设施前置项。
- [x] `toView()` 不建议作为无上下文 plan 方法，建议由 compiler/service 产出 `CompiledRelation`。
- [x] 明确二次聚合 / 二次窗口应消费 relation，而不是扩展当前 post-calc scalar 通道。
- [x] 三份 S7a review 已收敛：`review2` 主采纳，`review1` 边界补强，`review3` 字段拆解部分采纳。
- [x] 明确 `CteUnit` 不作为正式 stable relation contract。
- [x] 正式契约草案补齐 `CompiledRelation` / `RelationSql` / `RelationCapabilities`。
- [x] 正式契约草案补齐 CTE hoisting / SQL Server / MySQL 5.7 写法规则。
- [ ] Java contract owner 确认现有 `OutputSchema` 是否足够承载 semantic metadata。
- [ ] Java contract owner 确认 `CompiledRelation` / `PlanView` 与 `CteUnit` 的实现边界。
- [ ] Java contract owner 确认 SQL Server relation wrapping / CTE hoisting 策略。
- [ ] Java contract owner 生成 stable relation schema snapshot。
- [ ] Python mirror 消费 Java snapshot。

### Testing Progress

- status: N/A
- reason: 本阶段仅记录契约边界，不改运行时代码，不新增用户可执行能力。

### Experience Progress

- status: N/A
- reason: 无 UI / manual workflow 变化。

## 自检结论

- 是否改变当前运行时行为：否。
- 是否扩大 Stage 7 实现范围：否，反而把前置条件收紧。
- 是否需要正式 quality gate：否，本文件仅为 preflight 记录。
- 是否可进入二次聚合 / 二次窗口实现：否，先等待 stable relation 契约。
