# Evaluation Report: QueryPlan -> Stable View/Relation Architecture

## 1. 结论 (Conclusion)

- **强烈认可 `QueryPlan -> Stable View/Relation` 作为 Stage 7 的前置基础设施**。目前的 `QueryPlan` 编译过程丢弃了 Schema，只产出物理 SQL 片段。在开放二次聚合和窗口等复杂能力前，必须拥有带有完备 `OutputSchema`、能够描述列语义并携带方言能力标识的 `CompiledRelation`，从而提供安全的上下游组装边界。
- **完全同意二次聚合/窗口应该建模为 `DerivedQueryPlan over Stable Relation`，而不是扩展当前 post-calc 通道**。把外层聚合/窗口强制塞在同一个带有 `timeWindow` 的 DSL 请求中，会导致“明细生成”与“外层汇总”概念混淆，使得校验逻辑（validator）、错误码和 SQL 生成急剧复杂化。分层查询完美符合关系代数与底层 SQL 引擎的实际执行层级。

## 2. 现状盘点 (Current State)

### Java 现有能力
- **`OutputSchema` / `ColumnSpec`**：目前聚焦于名称防冲突（`isAmbiguous`）、来源追踪（`planProvenance`、`sourceModel`）和别名管理。但缺少关于业务含义或派生来源的语义化描述（类型 `dataType` 预留了但目前为空）。
- **`CteUnit` & `ComposedSql`**：主要承载 SQL 文本拼接（物理层）、别名分配（`alias`）和参数（`params`）传递。
- **`ComposePlanner`**：具备递归编译能力，但将推导的逻辑模型（`OutputSchema`）与物理 SQL 片段脱节，编译完直接返回 `CteUnit` 或组装好的 `ComposedSql`。

### Python 现有能力
- **Schema 推导**：`derive.py` / `output_schema.py` 严格镜像了 Java，具备 `derive_schema` 推导能力，拦截了无效列引用。
- **Plan 编译**：`compose_planner.py` 镜像实现了 `CteUnit` / `ComposedSql` 下推。同时 `_check_cross_datasource` 已能拦截跨数据源查询，但 `datasource` 信息是在每次编译时从底层绑定的，没有向上抽象为中间查询属性。
- **实库执行**：Stage 4 的 SQL Server 环境证明了方言相关的 CTE Hoisting 对于 timeWindow 是强需求，目前分散在 executor/compiler 层，缺乏对象模型支撑。

## 3. 缺口列表 (Gap List)

1. **Schema 语义缺口**：
    - 现有的 `ColumnSpec` 仅能表达列名和文本来源，无法表达它是基础字段、动态指标还是 `timeWindow` 派生列（如 `semanticKind`）。
    - 缺乏向 LLM 描述其真实业务含义的 `valueMeaning`（如 "当前值相对 prior 周期值的比率"），导致 LLM 无法准确利用这些字段。
    - 缺少能否在外部 `groupBy` 或 `window` 引用的 `referencePolicy`。
2. **Relation 抽象缺口**：
    - 缺少一个贯穿逻辑与物理层的封装对象（如 `CompiledRelation`）。单纯的 `CteUnit` 太偏向物理 SQL，无法承载上层需要的 Schema 以及方言执行能力标识。
3. **方言包装缺口**：
    - 对 SQL Server 等嵌套 CTE 敏感的数据库，需要将 `requiresCteHoisting` 作为关系的能力标识暴露给外层，防止生成的 SQL 在目标方言下执行失败。
4. **权限与 Datasource 缺口**：
    - 目前依靠 plan 树递归抓取 model 绑定来获取 datasource。对于可以被复用的 Stable Relation，应该在构造时固定其 `datasourceId` 并缓存其权限上下文。
5. **timeWindow 派生列含义缺口**：
    - 当前 Java 的 `TimeWindowExpander.computeOutputColumns()` 只管拼接后缀，缺乏正式的 schema 声明，不足以指导外层 derived plan 判断该列是否允许进一步聚合。

## 4. 推荐方案 (Recommended Approach)

**推荐 Option B：新增 `CompiledRelation` / `PlanView`。**

*原因分析*：
- **不选 Option A（复用 `CteUnit` 扩展字段）**：`CteUnit` 纯粹是应对底层 SQL 片段组装的物理模型。如果把 Schema 和 Datasource 挂载在 `CteUnit` 上，会导致物理组装过程与逻辑校验职责极度混淆。
- **不选 Option C（仅文档化现有 OutputSchema）**：纯文档契约无法支撑后续对 `timeWindow` 输出做强类型安全约束，更无法向 LLM 自动下发准确的 Schema 描述。
- **Option B 的核心优势**：引入独立的 `CompiledRelation`（包含 `alias`, `sql`, `params`, `OutputSchema`, `datasourceId`, `capabilities`）能清晰划分界限。它作为 `Compiler` 层对外暴露的标准化 API 边界，既可以直接转换为 LLM prompt 结构化描述，也可以作为 `DerivedQueryPlan` 安全引用的数据源。

## 5. 建议执行顺序 (Suggested Execution Order)

1. **Stage 7a contract doc**：完善并正式发布 `S7a-plan-stable-view-relation-contract-preflight.md`，敲定 `CompiledRelation` 结构和 `ColumnSpec` 语义扩展字段的最小必要集。
2. **Java proof-of-concept / tests**：在 Java 侧率先扩展 `ColumnSpec` 的 metadata；实现 `CompiledRelation` 抽象封装，并在 `TimeWindowExpander`（或相应的 derivation 逻辑）中注入派生列的具体 `semanticKind` 和 `valueMeaning`。
3. **Python mirror**：在 Python 侧镜像相应的 metadata 和数据类结构，对齐 Java fixture 并确保无语法漂移。
4. **Golden diff / Real DB evidence**：利用现有的 snapshot golden diff harness 确保 Schema 扩展不破坏原有查询执行。特别验证 SQL Server 对包含 `requiresCteHoisting` 能力的 `CompiledRelation` 的嵌套处理。
5. **最后讨论二次聚合/窗口开放**：以上稳定且实库证明通过后，再评估是否在 `DerivedQueryPlan over Relation` 的架构上正式放开对外层 `groupBy / aggregate / window` 的支持。

## 6. 风险与非目标 (Risks & Non-Goals)

- **明确非目标 - 混入普通列 Alias**：绝不把普通列投影（如 `columns=["amount AS amount1"]`）的处理混入本议题。它应单独作为 columns alias 的契约处理。
- **明确非目标 - 扩展 calculatedFields agg/window**：绝不顺手放开 calculatedFields 的 agg/window 能力。将严格保持现有的 `TIMEWINDOW_POST_CALCULATED_FIELD_AGG_UNSUPPORTED` 等 fail-closed 错误码。
- **明确非目标 - 修改 AST 默认值**：绝不翻转 Python 的 `use_ast_expression_compiler`，继续保持默认 `False`，避免扩大本次评估带来的运行时风险。
