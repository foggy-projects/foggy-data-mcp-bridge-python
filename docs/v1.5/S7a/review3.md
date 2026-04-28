# S7a Evaluation Report: QueryPlan → Stable View/Relation

## 1. Conclusions

### 1.1 认可 `QueryPlan → Stable View/Relation` 作为 Stage 7 前置基础设施

**结论：认可，但分层实施。**

当前事实：
- Java/Python 的 `OutputSchema` + `SchemaDerivation` / `derive_schema` 已经能回答"一个 plan 输出哪些列名"。
- `CteUnit` 已经携带 `alias` / `sql` / `params` / `selectColumns`，是一个编译期 SQL 片段载体。
- `ComposePlanner` 的 `compileToComposedSql` / `compile_to_composed_sql` 已经在递归编译中产出 `CteUnit`，并把 plan → alias 映射记录在 `planAliasMap`。

推断：
- 从结构上看，`CteUnit + OutputSchema` 合在一起已经非常接近 `CompiledRelation` 的概念——缺的是**语义元数据**和**显式关联**（当前二者分属不同对象，且 `CteUnit` 不携带 `OutputSchema`）。
- 如果未来要让外层 `DerivedQueryPlan` 安全引用 timeWindow 结果列，编译器需要在产出 `CteUnit` 的同时知道该 unit 的稳定输出 schema。

建议：
- Stage 7a 的核心交付应是**让 `CteUnit`（或其升级体）与 `OutputSchema` 显式关联**，而不是从零新建一个完全独立的 `CompiledRelation` 类。

### 1.2 认可二次聚合/窗口应走 Derived Relation

**结论：强烈认可。**

当前事实：
- 8.4.0 契约 §2 明确禁止 `timeWindow + calculatedFields.agg/windowFrame`。
- `TimeWindowValidator.validateCalculatedFieldInteraction` 已实现 4 个细化错误码守住这条线。
- timeWindow 展开后的 SQL 已经是多层 CTE（comparative 走 JOIN + outer projection；rolling/cumulative 走 window function），再往里塞二次聚合会让 SQL 形态不可控。

推断：
- 如果打开 `calculatedFields.agg` 通道，validator 必须区分"对 timeWindow 输出列做 AVG(ratio)"和"对原始度量做新聚合"——这两者的 SQL 层级完全不同，且跨方言 CTE 嵌套/子查询包装的差异会被放大。
- `DerivedQueryPlan over CompiledRelation` 模型把这两层天然隔离，每层各自独立校验和编译。

---

## 2. 现状盘点

### 2.1 Java 现有能力

| 组件 | 当前能力 | 覆盖程度 |
|---|---|---|
| `OutputSchema` | 有序 `ColumnSpec` 列表，支持重名（G10 ambiguity），`names()` / `nameSet()` / `get()` / `getAll()` / `isAmbiguous()` | **列名 + 来源模型** ✅；**语义元数据** ❌ |
| `ColumnSpec` | `name` / `expression` / `sourceModel` / `dataType`(reserved) / `hasExplicitAlias` / `planProvenance`(G10) / `isAmbiguous`(G10) | **基本属性** ✅；`dataType` 仍 null；**无 `semanticKind` / `valueMeaning` / `referencePolicy`** ❌ |
| `SchemaDerivation` | 递归派生 Base/Derived/Union/Join 的 `OutputSchema`；bare-identifier scan 校验列引用 | **结构校验** ✅；**不理解 timeWindow 派生列语义** ❌ |
| `CteUnit` | `alias` / `sql` / `params` / `selectColumns` | **SQL 片段载体** ✅；**不携带 `OutputSchema` / `datasourceId` / `capabilities`** ❌ |
| `ComposePlanner` | 递归 plan→CteUnit/ComposedSql，dialect CTE fallback，`planAliasMap`(G10)，cross-datasource guard(F-7) | **编译管线** ✅；**不在 CteUnit 上附 schema / capabilities** ❌ |
| `TimeWindowExpander` | `expandRolling` / `expandCumulative` / `expandComparative` / `getOutputColumns` | **列名计算** ✅；**列语义（kind/meaning）未入 schema** ❌ |
| `TimeWindowValidator` | 10 基础校验 + 4 calc-field 交互校验 | **fail-closed 边界** ✅ |

### 2.2 Python 现有能力

| 组件 | 当前能力 | 覆盖程度 |
|---|---|---|
| `OutputSchema` | frozen dataclass，`ColumnSpec` tuple，G10 ambiguity mirror | 与 Java 同等 ✅/❌ |
| `ColumnSpec` | 字段集合与 Java 镜像；`plan_provenance` / `is_ambiguous` G10 PR1 | 与 Java 同等 ✅/❌ |
| `derive_schema` | 递归派生，bare-identifier scan，`_RESERVED_TOKENS` | 与 Java 同等 ✅/❌ |
| `CteUnit` | `alias` / `sql` / `params` / `select_columns` | 与 Java 同等 ✅/❌ |
| `compile_to_composed_sql` | 递归编译，dialect CTE fallback，`plan_alias_map`(G10)，cross-datasource(F-7) | 与 Java 同等 ✅/❌ |
| timeWindow 编译 | 在 `SemanticQueryService` 层面处理，不走 Compose plan 路径 | **独立管线**；Python compose 不直接产出 timeWindow 派生列 |

---

## 3. 缺口列表

### 3.1 Schema 语义缺口

> [!IMPORTANT]
> **当前 `ColumnSpec` 不表达列的业务含义。** 它只知道 `name="salesAmount__prior"` 和 `expression="salesAmount__prior"`，但不知道这是一个"上一对比周期的聚合值"。

缺失字段：

| 字段 | 用途 | 影响 |
|---|---|---|
| `semanticKind` | `base_field` / `aggregate_measure` / `time_window_derived` / `scalar_calc` / `window_calc` | LLM schema 描述、外层引用策略、二次聚合口径判定 |
| `valueMeaning` | 人/LLM 可读语义说明 | LLM 自动生成 DSL 时理解 `__ratio` 是比率而非金额 |
| `referencePolicy` | `readable` / `aggregatable` / `windowable` / `orderable` | 外层 plan 校验是否可对该列做 groupBy / agg / window / orderBy |
| `lineage` | 来源字段名或上游 relation 字段 | 跨 plan 追溯、golden diff 归因 |

**事实**：Java `ColumnSpec.dataType` 已预留但未使用（M5/M6）。`semanticKind` 和 `referencePolicy` 是比 `dataType` 更紧迫的缺口。

### 3.2 Relation 抽象缺口

> [!NOTE]
> `CteUnit` 缺少的不是 SQL 承载能力，而是**元数据关联**。

| 当前 CteUnit | 缺失 |
|---|---|
| `alias` ✅ | — |
| `sql` ✅ | — |
| `params` ✅ | — |
| `selectColumns` ✅ | — |
| — | `outputSchema: OutputSchema` |
| — | `datasourceId: Optional[str]` |
| — | `dialect: str` |
| — | `capabilities: RelationCapabilities` |

`RelationCapabilities` 候选字段：
- `supportsOuterAggregate: bool` — 外层是否可对该 relation 再做 GROUP BY
- `supportsOuterWindow: bool` — 外层是否可对该 relation 再做窗口函数
- `requiresCteHoisting: bool` — SQL Server / MySQL5.7 需要把嵌套 CTE 提升到顶层

### 3.3 timeWindow 派生列含义缺口

当前 `TimeWindowExpander.getOutputColumns()` 返回 `Set<String>` — 只有列名集合，没有每列的含义标注。

| 派生列 | 当前记录 | 应表达的含义 |
|---|---|---|
| `metric__prior` | 仅文档 | 上一对比周期的 `metric` 聚合值 |
| `metric__diff` | 仅文档 | 当前值 − prior |
| `metric__ratio` | 仅文档 | (当前 − prior) / prior；null when prior=0 |
| `metric__rolling_7d` | 仅文档 | 7 天滚动聚合 |
| `metric__ytd` | 仅文档 | 年初至今累计 |
| `metric__mtd` | 仅文档 | 月初至今累计 |

**事实**：`TimeWindowExpander` 里的 `ComparativeColumn` record 已经携带 `currentAlias` / `priorAlias` / `diffAlias` / `ratioAlias`，但这只是命名约定，没有流入 `OutputSchema`。

### 3.4 方言包装缺口

| 方言 | CTE 嵌套 | 已知风险 |
|---|---|---|
| MySQL 5.7 | ❌ 不支持 CTE | `useCte=false`，inline subquery；已处理 |
| MySQL 8 | ✅ | 无已知风险 |
| PostgreSQL | ✅ | 无已知风险 |
| SQLite | ✅ | `FULL OUTER JOIN` pre-3.39 不支持；已有 guard |
| SQL Server | ❌ `useCte=false` | **CTE 不能嵌套在 derived table 中**；`ComposePlanner` 已把 mssql/sqlserver 设为 `useCte=false`，但如果 Stable Relation 产出的 SQL 含 `WITH`，外层包装需要 CTE hoisting |

**事实**：Java/Python `ComposePlanner` 的 `DIALECT_CTE_SUPPORT` / `dialect_supports_cte` 已实现方言判定，但都是"全局开关"——没有 per-relation 的 `requiresCteHoisting` 粒度。当前因为 mssql 直接走 subquery 模式，这个缺口不紧迫，但如果未来要在 mssql 上做 CTE-based outer query over relation，需要 hoisting 逻辑。

### 3.5 权限 / datasource 缺口

| 项目 | 现状 | 缺口 |
|---|---|---|
| datasource identity | F-7 已完成；`ModelInfoProvider.get_datasource_id` 在 compile 时收集 | `CteUnit` 不携带 `datasourceId`，只在 `_CompileState.datasource_ids` 中按 model name 查 |
| permission filtering | G10 PR4 `ComposePlanAwarePermissionValidator` 已实现 plan-aware 白名单 | **只在编译前运行**；relation 复用场景下，如果 relation A 的某列被权限过滤，外层 plan 引用该列时无 guard |
| denied columns | `SchemaDerivation` javadoc 明确说 "M5 applies authority binding，当前不减列" | 如果 Stable Relation 要暴露给外层 plan，其 `OutputSchema` 应该是**权限过滤后**的 |

---

## 4. 推荐方案

### Option A：复用 CteUnit 扩展字段

在 `CteUnit` 上新增 `outputSchema` / `datasourceId` / `dialect` / `capabilities` 字段（均 optional，默认 null）。

**优点**：
- 零新类型；现有 `ComposePlanner` 产出 CteUnit 时顺手填充
- CteComposer / compose_planner 不需要大改
- 向后兼容：所有现有 CteUnit 使用方无需感知新字段

**缺点**：
- `CteUnit` 当前是 mutable（Java `@Getter` + 构造函数，Python `@dataclass`），加字段不破坏但语义上开始超载
- `CteUnit` 的名字暗示"CTE SQL 片段"，而不是"稳定关系"——概念漂移

### Option B：新增 CompiledRelation / PlanView

新类型 `CompiledRelation`，字段完全对应 S7a preflight 候选结构。`CteUnit` 保持原样作为"SQL 片段"，`CompiledRelation` 是"带 schema 的可引用关系"。

**优点**：
- 概念清晰：`CteUnit` = SQL 拼接单元；`CompiledRelation` = 语义可引用关系
- 未来 `DerivedQueryPlan over CompiledRelation` 的类型签名更自然
- 可渐进引入：先在 compiler 内部使用，不影响公开 API

**缺点**：
- 双引擎各新增一个类 + builder + 测试
- `CompiledRelation` 和 `CteUnit` 的 sql/params/alias 字段重叠，需要明确所有权

### Option C：仅文档化现有 OutputSchema，不新增抽象

只在文档和 LLM schema 描述中固化 timeWindow 派生列含义；代码层面不新增类型。

**优点**：零代码改动

**缺点**：
- LLM 只能从文档推断列含义，不能从 schema 对象直接获取
- 外层 plan 校验无法自动判断"这列可不可以做 groupBy"
- 二次聚合/窗口开放时必须回来补这些缺口

### 推荐：Option A（短期） → Option B（中期）

**理由**：
1. **短期**（Stage 7a contract doc + proof-of-concept）：在 `CteUnit` 上加 `outputSchema` 字段足矣。这让 timeWindow 编译路径在产出 `CteUnit` 时把派生列 schema 带上，外层 validator 可以校验引用合法性。改动量最小，可快速验证。
2. **中期**（二次聚合/窗口开放前）：一旦需要让 `DerivedQueryPlan` 把一个 `CteUnit` 当作"source relation"来引用，`CteUnit` 的语义超载就不可接受了。此时提取 `CompiledRelation` 作为 `CteUnit + OutputSchema + capabilities` 的组合体，并调整 `DerivedQueryPlan.source` 的类型签名。

> [!IMPORTANT]
> 不推荐直接跳到 Option B：当前还没有消费 `CompiledRelation` 的下游代码（二次聚合/窗口未开放），先落地 Option A 可以在最小改动下验证 schema 关联的正确性。

### 关于 `deriveSchema` vs `compileToRelation` 的位置

**事实**：`SchemaDerivation.derive(plan)` 是静态无上下文方法；`compileToComposedSql` 需要 bindings/dialect/semanticService。

**建议**：
- `deriveSchema(plan) → OutputSchema` 保持在 `SchemaDerivation` / `derive_schema` 里，不动。
- `compileToRelation(plan, context) → CompiledRelation` 应放在 `ComposePlanner` / `compile_to_composed_sql` 层。具体来说，`_compile_base` / `_compile_derived` 返回 `CteUnit` 时附上 `outputSchema`——`outputSchema` 通过 `SchemaDerivation.derive(plan)` 计算。
- **不建议**在 `QueryPlan` 上添加 `toView()` 或 `toRelation()` 无参方法。

---

## 5. 建议执行顺序

### Step 1：Stage 7a Contract Doc（文档 + 测试契约）

- [ ] 在 Java 侧定义 `ColumnSpec` 新增 `semanticKind` 字段的枚举值集合
- [ ] 定义 `TimeWindowExpander.getOutputSchema()` 方法签名（返回 `OutputSchema` 而非 `Set<String>`）
- [ ] 定义每种 timeWindow comparison mode 的派生列 `semanticKind` + `referencePolicy`
- [ ] 不改运行时代码；只落盘契约文档 + fixture schema

### Step 2：Java Proof-of-Concept

- [ ] `ColumnSpec` 新增 `semanticKind: String`（nullable，向后兼容）
- [ ] `TimeWindowExpander.getOutputSchema()` 实现，产出带 `semanticKind` 的 `ColumnSpec`
- [ ] `CteUnit` 新增 `outputSchema: OutputSchema`（nullable）
- [ ] `ComposePlanner._compileBase` 在产出 `CteUnit` 时附上 `SchemaDerivation.derive(plan)`
- [ ] 新增 unit test：验证 timeWindow plan 的 `CteUnit.outputSchema` 包含正确的派生列 + semanticKind

### Step 3：Python Mirror

- [ ] `ColumnSpec` 新增 `semantic_kind: Optional[str]`
- [ ] `CteUnit` 新增 `output_schema: Optional[OutputSchema]`
- [ ] `compose_planner._compile_base` 附上 `derive_schema(plan)`
- [ ] 镜像 Java 测试

### Step 4：Golden Diff / Real DB Evidence

- [ ] 在 `TimeWindowParitySnapshotTest` 中增加 `outputSchema` 字段的 snapshot
- [ ] Python 消费 Java snapshot 时校验 `semanticKind` 一致性
- [ ] 不触发 real DB 执行——schema 是编译期产物

### Step 5：讨论二次聚合/窗口开放

- [ ] 只在 Step 1-4 全部通过后才开始
- [ ] 基于 `CteUnit.outputSchema` 的 `referencePolicy` 判断外层可引用策略
- [ ] 此时决定是否需要 Option B（`CompiledRelation` 独立类型）

---

## 6. 风险与非目标

### 明确非目标

| 非目标 | 原因 |
|---|---|
| `columns=["amount AS amount1"]` 普通列 alias | 独立契约项，与 Stable Relation 无关 |
| 开放 `calculatedFields.agg / windowFrame` | 需要先完成 Step 1-4 |
| 翻转 Python `use_ast_expression_compiler` 默认值 | Stage 6 独立 gate |
| 实现 named CTE / recursive CTE | 需要单独的作用域 + 名称冲突契约 |
| 把 relation 物化为数据库真实 `CREATE VIEW` | 明确是编译期对象 |
| 改变已签收 subset 的运行时行为 | Stage 7 在 Java 契约发布前保持 fail-closed |

### 风险

| 风险 | 缓解 |
|---|---|
| `semanticKind` 枚举值集合不稳定 | 先用 String 而非 enum；stabilize 后再收紧 |
| `CteUnit.outputSchema` 增加内存压力 | `OutputSchema` 是 lightweight frozen 对象，典型 plan 只有十几列 |
| SQL Server CTE hoisting 在 per-relation 粒度不够 | 短期不影响——mssql 已走 subquery 模式；中期在 `capabilities` 中加 `requiresCteHoisting` |
| 权限过滤后的 schema 与编译前 schema 不一致 | Step 2 阶段 `CteUnit.outputSchema` 使用编译前 schema（和当前行为一致）；权限集成留到 G10 PR5+ |

---

## 7. 最小可行契约（仅为"稳定知道 plan 输出列名及含义"）

如果**不实现二次聚合/窗口**，只为了稳定表达 plan 输出列含义：

### 必须落代码

1. `ColumnSpec` 新增 `semanticKind: String`（Java + Python）— ~10 行/语言
2. `TimeWindowExpander.getOutputSchema()` / Python 对应逻辑返回带 `semanticKind` 的 `OutputSchema` — ~50 行/语言
3. 对应 unit test — ~30 行/语言

### 可只做文档契约

1. `referencePolicy`（是否可在外层 groupBy/agg/window/orderBy 中引用）— 当前无消费方，文档记录即可
2. `valueMeaning`（人/LLM 可读语义）— 当前 LLM schema 描述未消费 `OutputSchema`，文档记录即可
3. `lineage` — 当前无消费方
4. `CteUnit.outputSchema` — 如果不做二次聚合，无消费方；但建议 Java PoC 先做，验证可行性

### 不需要做

1. `CompiledRelation` 独立类型 — 留到二次聚合开放
2. `capabilities` — 留到二次聚合开放
3. 任何 runtime 行为变化
