**结论**

认可把 `QueryPlan -> Stable View/Relation` 作为 Stage 7 前置基础设施。当前 Java/Python 已经有 `OutputSchema`、`CteUnit`、`ComposedSql`、`DerivedQueryPlan` 包装能力，但这些更像“编译过程内部零件”，还不足以表达一个可被外层查询、LLM schema、validator 和双引擎 golden diff 稳定消费的 relation contract。

也认可二次聚合/二次窗口不应塞进现有 `timeWindow + calculatedFields.agg/windowFrame` 通道。当前 post-calc 通道是 scalar projection，继续保持 fail-closed 是对的。Stage 7 更合理的模型是：

```text
timeWindow QueryPlan
  -> CompiledRelation / PlanView
  -> outer DerivedQueryPlan
  -> outer aggregate / window
```

**现状盘点**

Java 当前已有事实：

- `OutputSchema` / `ColumnSpec` 已表达 ordered columns、name、expression、sourceModel、dataType、explicitAlias、G10 planProvenance、ambiguity。
- `SchemaDerivation` 已能为 base / derived / union / join 派生 schema，并做 name validation。
- `TimeWindowExpander.getOutputColumns()` 能稳定产出名字集合，例如 `metric__prior`、`metric__diff`、`metric__ratio`、`metric__rolling_7d`、`metric__ytd`、`metric__mtd`。
- `TimeWindowValidator` 当前用 name set 判断 post scalar calc 可引用范围，并明确拒绝 targetMetrics 引用 request-level calc、post calc agg/window。
- `CteUnit` 只有 `alias/sql/params/selectColumns`，`ComposedSql` 只有最终 `sql/params`。
- `ComposePlanner` 已有 derived wrapping、CTE/subquery fallback、F-7 datasource identity guard。Java 对 SQL Server 明确避免 nested CTE，走 inline subquery fallback。

Python 当前已有事实：

- `ColumnSpec` / `OutputSchema` 基本镜像 Java，已有 ordered schema、G10 provenance、ambiguity，但无语义 metadata。
- `derive_schema` 镜像 Java 的 base / derived / union / join schema derivation。
- `CteUnit` 也是 `alias/sql/params/select_columns`，`ComposedSql` 是 `sql/params`。
- `compile_plan_to_sql` 需要 context、semantic service、bindings、model info、datasource ids、dialect，说明 `plan.toView()` 这种无上下文方法不合适。
- Python planner 也有 CTE/subquery 包装与 F-7 cross-datasource 检查。SQL Server CTE 策略与 Java存在需要对齐的风险点：Java planner 直接禁用 SQL Server nested CTE；Python 文档记录有 SQL Server executor hoisting/fallback 逻辑，后续需要 golden evidence 固化。

**缺口列表**

1. Schema 语义缺口
   当前 `OutputSchema` 主要是“列名与来源”层级，不足以表达 `timeWindow` 派生列的业务含义。仅有 `salesAmount__ratio` 这个名字，无法稳定告诉 LLM、validator 或 outer planner：它是 ratio、来自哪个 metric、比较窗口是什么、是否适合再 sum/avg/order/window。

2. Relation 抽象缺口
   `CteUnit` 接近 SQL 片段，但缺少 `outputSchema`、datasource identity、dialect、capabilities、permission state。把它继续扩展成万能对象会污染内部 SQL assembly 边界。

3. timeWindow 派生列含义缺口
   当前 suffix 命名是必要但不充分。建议把派生列语义写进 schema，而不是只写进文档。至少需要 `semanticKind`、`valueMeaning`、`lineage`、`referencePolicy`。

4. 方言包装缺口
   SQL Server 对 `WITH` 位置敏感。Stable Relation 不能只保存 SQL 字符串，应携带 wrapping capability，例如 `requiresCteHoisting`、`canNestWithInDerived` 或 `relationWrapStrategy = inline_subquery | hoisted_cte | native_cte`。

5. 权限 / datasource 缺口
   Stable Relation 必须携带 datasource identity。F-7 guard 可以作为基础，但 relation 复用时不能依赖外层重新回溯 hidden plan。输出 schema 应是 permission filtering 后的 authorized schema，且 derived column 需要 lineage，避免通过 `ratio/diff` 暗中泄露 denied source columns。

**推荐方案**

推荐 Option B：新增 `CompiledRelation` / `PlanView`，不要复用扩展 `CteUnit` 作为正式契约。

建议边界：

- `OutputSchema`：描述 relation 输出列及语义。
- `CteUnit`：保留为内部 SQL assembly primitive。
- `ComposedSql`：最终可执行 SQL + params。
- `CompiledRelation` / `PlanView`：面向外层 query / LLM / validator 的稳定编译期 relation。

建议字段：

```text
alias
sql
params
outputSchema
datasourceId / datasourceIdentity
dialect
capabilities / relationWrapStrategy
sourcePlanId or planHash
permissionState or authorizedSchema marker
```

`ColumnSpec` 可扩展或挂 sidecar metadata：

```text
semanticKind: baseField | aggregateMeasure | timeWindowDerived | scalarCalc | windowCalc
valueMeaning
lineage
referencePolicy
```

Option A 复用 `CteUnit` 的优点是改动小，但抽象会变重，后续容易混淆“SQL 拼装单元”和“可复用 relation”。Option C 只文档化现有 `OutputSchema` 不够，无法支撑 LLM schema、二次查询 validator、权限 lineage 和 SQL Server wrapping 风险。

**建议执行顺序**

1. Stage 7a contract doc
   先定 `CompiledRelation` / `PlanView` 字段、schema semantic metadata、非目标和错误边界。

2. Java proof-of-concept / tests
   先在 Java 做最小 POC：`compileToRelation(plan, context)`，输出 authorized `OutputSchema` + relation capabilities。保留现有 post-calc fail-closed 测试。

3. Python mirror
   镜像 Java 契约，不翻 `use_ast_expression_compiler` 默认值。

4. Golden diff / real DB evidence
   覆盖 MySQL8、Postgres、SQLite、SQL Server，重点验证 relation wrapping、CTE hoisting/subquery fallback、params 顺序。

5. 最后再讨论二次聚合/窗口开放
   等 Stable Relation 契约稳定后，再把 outer aggregate/window 作为 `DerivedQueryPlan over relation` 开放。

**风险与非目标**

- 不要把 `columns=["amount AS amount1"]` 普通 alias 问题混入本议题。
- 不要顺手开放 `calculatedFields.agg/windowFrame/windowOrderBy`。
- 不要翻 Python `use_ast_expression_compiler` 默认值。
- 不要扩大 Stage 7 到 named / recursive CTE 实现。
- SQL Server wrapping 是最大方言风险，需要代码契约和 golden evidence，而不是只靠文档说明。

**验证**

已做只读检查。Python repo 当前有既有文档修改与新增 S7/S7a 文档，Java worktree clean。未修改代码或文档，因此未运行测试或 `diff --check`。
