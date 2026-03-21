# Foggy Dataset Python 移植进度报告

> Updated: 2026-03-21 | 基于 Java foggy-data-mcp-bridge 对比分析

---

## 总览

| 指标 | 初始 | 当前 | 增长 |
|------|------|------|------|
| **总测试数** | 625 | **1318** | +693 (+111%) |
| **dataset_model 源码** | 14 文件 | **40 文件** | +26 |
| **dataset_model 测试** | 106 | **520** | +414 |
| **MCP 源码** | 35 文件 | **39 文件** | +4 |
| **MCP 测试** | 98 | **98** | — |

---

## 一、dataset_model 模块 — 95% 完成

### 1.1 子模块状态

| 子模块 | 状态 | 说明 |
|--------|------|------|
| **definitions/** | ✅ 完成 | 42 类：AiDef、DbMeasureDef、DbFormulaDef、PreAggregationDef、QueryConditionDef 等 |
| **engine/expression/** | ✅ 完成 | 10 类：SqlExp、SqlBinaryExp、SqlColumnExp、SqlFunctionExp、SqlCaseExp 等 |
| **engine/formula/** | ✅ 完成 | 17 类：SqlFormulaRegistry + 15 操作符（=、IN、LIKE、BETWEEN、范围、IS NULL 等） |
| **engine/join/** | ✅ 完成 | JoinGraph（BFS + Kahn 拓扑排序）、JoinEdge、JoinType |
| **engine/compose/** | ✅ 完成 | CteComposer（CTE 模式 + 子查询模式）、CteUnit、JoinSpec、ComposedSql |
| **engine/hierarchy/** | ✅ 完成 | 5 操作符（childrenOf/descendantsOf/ancestorsOf 等）、ClosureTableDef、HierarchyConditionBuilder、Registry |
| **engine/dimension_path.py** | ✅ 完成 | 嵌套维度路径（dot/underscore 格式转换、parse、append） |
| **engine/query/** | ✅ 完成 | JdbcQueryVisitor、SqlQueryBuilder、DbQueryResult |
| **engine/preagg/** | ✅ 完成 | PreAggregationMatcher、Rewriter、Interceptor |
| **impl/model/** | ✅ 完成 | DbTableModelImpl、DimensionJoinDef、DimensionPropertyDef、resolve_field() |
| **impl/loader/** | ✅ 完成 | TableModelLoader、TableModelLoaderManager |
| **proxy/** | ✅ 完成 | TableModelProxy、DimensionProxy、ColumnRef、JoinBuilder |
| **semantic/service.py** | ✅ 完成 | SemanticQueryService：auto-JOIN、内联聚合、V3 元数据（JSON + Markdown）、FormularRegistry 集成 |
| **semantic/member_loader.py** | ✅ 完成 | DimensionMemberLoader：ID↔caption 双向映射、Pattern 搜索、50 分钟 TTL 缓存 |
| **service/facade.py** | ✅ 完成 | QueryFacade 管线：ValidationStep、InlineExpressionStep、AutoGroupByStep |
| **config/** | ✅ 完成 | SemanticProperties、QmValidationOnStartup |

### 1.2 核心能力对比

| 能力 | Java | Python | 状态 |
|------|------|--------|------|
| 星型模型 JOIN（维度表） | ✅ | ✅ auto-JOIN via DimensionJoinDef | ✅ |
| 雪花模型 JOIN（多跳） | ✅ JoinGraph | ✅ JoinGraph (BFS + topo sort) | ✅ |
| 字段解析 dim$id/caption/prop | ✅ | ✅ resolve_field() | ✅ |
| 嵌套维度路径 product.category$id | ✅ DimensionPath | ✅ DimensionPath | ✅ |
| 内联聚合 sum(field) as alias | ✅ InlineExpressionParser | ✅ _parse_inline_expression() | ✅ |
| SQL 操作符（15+ 种） | ✅ SqlFormulaService | ✅ SqlFormulaRegistry | ✅ |
| Parent-Child 维度（闭包表） | ✅ | ✅ ClosureTableDef + HierarchyConditionBuilder | ✅ |
| 层级操作符（5 种） | ✅ | ✅ childrenOf/descendantsOf/ancestorsOf 等 | ✅ |
| 维度值缓存 caption↔id | ✅ DimensionMemberLoader | ✅ DimensionMemberLoader | ✅ |
| TableModelProxy（动态引用） | ✅ | ✅ PropertyHolder + DimensionProxy | ✅ |
| CTE 多模型编排 | ✅ CteComposer | ✅ CteComposer (CTE + subquery) | ✅ |
| QueryFacade 管线 | ✅ | ✅ 3 个 Step | ✅ |
| 预聚合匹配 | ✅ | ✅ PreAggregationMatcher | ✅ |
| V3 元数据（JSON + Markdown） | ✅ | ✅ | ✅ |
| SQL 方言翻译 | ✅ 4 dialects | ✅ 4 dialects + translate_function | ✅ |
| 数据库异步执行 | ✅ JdbcTemplate | ✅ aiomysql/asyncpg/aiosqlite | ✅ |
| 安全表达式求值 | ✅ | ✅ AST-based (替换 eval) | ✅ |

### 1.3 未移植项（非核心 / 可选）

| 项目 | Java | 说明 |
|------|------|------|
| L1/L2 缓存 Step | 2 个 Step 类 | Token 级 / 模型级查询缓存，需 Redis |
| SubtotalStep | 1 个 Step 类 | 分组小计/总计行追加 |
| MoneyFormatStep | 1 个 Step 类 | 金额格式化 |
| Odoo 专有测试 | 28 个测试 | Odoo ERP 特定场景 |
| 向量检索 | similar/hybrid 操作符 | 需要 Milvus 向量数据库 |
| 多数据库集成测试 | 18 个测试 | 需要 PG/SQLServer/SQLite 同时运行 |

### 1.4 测试覆盖

| 测试文件 | 测试数 | 覆盖模块 |
|----------|--------|----------|
| test_definitions.py | 55 | 定义层：AiDef、Access、Dict、Measure、Expression、Model |
| test_semantic_query.py | 55 | 语义查询：字段解析、auto-JOIN、聚合、V3 元数据 |
| test_hierarchy_operators.py | 58 | 层级操作符、闭包表、条件构建、注册中心 |
| test_dimension_path.py | 41 | 嵌套维度路径：格式转换、解析、遍历 |
| test_formula_registry.py | 37 | SqlFormula：15 个操作符 + 注册中心 |
| test_table_model_proxy.py | 33 | TableModelProxy、DimensionProxy、ColumnRef |
| test_member_loader.py | 32 | DimensionMemberLoader：缓存、搜索、过期 |
| test_query_facade.py | 28 | QueryFacade 管线：Validation、InlineExpr、AutoGroupBy |
| test_calculated_fields.py | 27 | 计算字段：算术、函数、依赖、安全 |
| test_join_graph.py | 23 | JoinGraph：BFS、拓扑排序、缓存、环检测 |
| test_loader.py | 19 | 模型加载器 |
| test_cte_compose.py | 18 | CTE 编排：WITH/子查询模式 |
| test_preagg_matcher.py | 16 | 预聚合匹配 |
| test_query_visitor.py | 16 | SQL 构建：Visitor + Builder |
| test_auto_groupby.py | 15 | AutoGroupBy 推断 |
| test_query_validation.py | 10 | 查询验证 |
| test_inline_expression.py | 9 | 内联聚合表达式 |
| test_authorization.py | 28 | 访问控制 |
| **总计** | **520** | |

---

## 二、MCP 模块 — 70% 完成

### 2.1 工具状态

| 工具名 | 状态 | 说明 |
|--------|------|------|
| `dataset.get_metadata` | ✅ | Markdown（默认）+ JSON，维度属性完整 |
| `dataset.describe_model_internal` | ✅ | 单模型详细元数据 |
| `dataset.query_model` | ✅ | V3 payload 格式 + 内联聚合 + auto-JOIN |
| `dataset_nl.query` | ❌ | 需要 AI 服务 |
| `dataset.compose_query` | ❌ | CTE 引擎已实现，MCP 工具未接入 |
| `chart.generate` | ❌ | 需要 chart-render-service |
| `dataset.export_with_chart` | ❌ | 需要 chart-render-service |
| `dataset.inspect_table` | ❌ | Admin 工具 |

### 2.2 协议能力

| 能力 | 状态 |
|------|------|
| Streamable HTTP (POST/GET/DELETE) | ✅ |
| SSE Stream | ✅ |
| JSON-RPC 2.0（无 error:null） | ✅ |
| Mcp-Session-Id 管理 | ✅ |
| Notification → 202 Accepted | ✅ |
| 工具定义从共享 schema 加载 | ✅ |
| sync_mcp_schemas.py 同步脚本 | ✅ |

---

## 三、进度时间线

```
2026-03-20  初始移植完成         625 tests
     ↓      P0 安全修复 + MCP 服务启动
     ↓      MCP 工具对齐 + V3 元数据
     ↓      星型模型 JOIN + 维度字段
     ↓      +314 单元测试移植         939 tests
     ↓      translate_function + 内联表达式    955 tests
2026-03-21  P0-P1: SqlFormula/JoinGraph/QueryFacade/CTE  1154 tests
     ↓      P2-P3: DimensionPath/Hierarchy/Proxy/MemberLoader  1318 tests
     ↓      dataset_model 完成度 95%
```

---

## 四、下一步建议

| 优先级 | 工作项 | 预估 |
|--------|--------|------|
| P1 | compose_query MCP 工具接入 | 1 天 |
| P1 | 端到端集成测试（MCP → MySQL 真实查询） | 1 天 |
| P2 | SubtotalStep / MoneyFormatStep | 1 天 |
| P2 | inspect_table MCP 工具 | 1 天 |
| P3 | NL Query（需 AI 服务） | 2 天 |
| P3 | Chart 工具（需 chart-render-service） | 1 天 |
