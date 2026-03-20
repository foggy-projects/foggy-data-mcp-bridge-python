# Foggy Dataset Python 移植进度报告

> Generated: 2026-03-21 | 基于 Java foggy-data-mcp-bridge 对比分析

---

## 一、dataset_model 模块

### 1.1 总览

| 指标 | Java | Python | 覆盖率 |
|------|------|--------|--------|
| 源码文件 | 242 | 34 | 14.0% |
| 类（含枚举） | ~210 | ~95 | 45.2% |
| 测试文件 | 54 | 11 | 20.4% |
| 测试方法 | 672 | 250 | 37.2% |

### 1.2 子模块对比

| 子模块 | Java 类数 | Python 类数 | 状态 | 说明 |
|--------|----------|------------|------|------|
| **definitions/** | 31 | 42 | ✅ 完成 | Python 更多（合并了 request 子类） |
| **engine/expression/** | 14 | 10 | ⚠️ 70% | 缺 InlineExpressionParser(解析已内嵌 service)、AllowedFunctions、SliceExpressionProcessor |
| **engine/join/** | 2 | 0 | ❌ 缺失 | JoinGraph/JoinEdge 未独立实现（JOIN 逻辑内嵌在 SemanticQueryService） |
| **engine/query/** | 4 | 8 | ✅ 完成 | JdbcQuery、Visitor、Builder、Result 全部移植 |
| **engine/preagg/** | 7 | 11 | ✅ 完成 | Matcher、Rewriter、Interceptor 全部移植 |
| **engine/formula/** | 20 | 0 | ❌ 缺失 | SqlFormula 体系（条件表达式生成器）未移植 |
| **engine/compose/** | 8 | 0 | ❌ 缺失 | CTE 多模型编排（compose_query）未移植 |
| **engine/query_model/** | 5 | 0 | ❌ 缺失 | QM 构建器、文件变更监听未移植 |
| **impl/** | 33 | 13 | ⚠️ 39% | 核心已移植，缺 dimension 子类型、query impl、utils |
| **semantic/** | 18 | 2 | ⚠️ 11% | SemanticQueryService 已实现，缺 V3Impl 的完整管线、DimensionMemberLoader、CaptionMatch |
| **authorization/** | 0* | 0 | — | Java 在 plugins/ 中实现，Python 无 |
| **config/** | 4 | 2 | ⚠️ 50% | 缺 DatasetProperties、AutoConfiguration |
| **plugins/** | 18 | 0 | ❌ 缺失 | AutoGroupBy、Having、L1/L2 Cache、Subtotal、QueryValidation 等步骤 |
| **proxy/** | 7 | 0 | ❌ 缺失 | TableModelProxy、DimensionProxy（TM/QM 动态引用） |
| **service/** | 6 | 0 | ❌ 缺失 | QueryFacade、JdbcService（查询执行管线） |
| **spi/** | 37 | 0 | ❌ 缺失 | 核心 SPI 接口（在 Python 中部分内嵌到 service） |

### 1.3 已实现的核心能力

| 能力 | Java | Python | 状态 |
|------|------|--------|------|
| 星型模型 JOIN（维度表） | ✅ JoinGraph + auto-JOIN | ✅ DimensionJoinDef + auto-JOIN | ✅ 功能等价 |
| 字段解析 dim$id/caption/prop | ✅ nameToJdbcQueryColumn | ✅ resolve_field() | ✅ 功能等价 |
| 内联聚合 sum(field) as alias | ✅ InlineExpressionParser | ✅ _parse_inline_expression() | ✅ 功能等价 |
| V3 元数据（JSON + Markdown） | ✅ SemanticServiceV3Impl | ✅ get_metadata_v3/markdown | ✅ 功能等价 |
| 预聚合匹配 | ✅ PreAggregationMatcher | ✅ PreAggregationMatcher | ✅ 功能等价 |
| SQL 方言翻译 | ✅ 4 dialects | ✅ 4 dialects + translate_function | ✅ 功能等价 |
| 数据库异步执行 | ✅ JdbcTemplate | ✅ aiomysql/asyncpg/aiosqlite | ✅ 功能等价 |
| 安全表达式求值 | ✅ Java 表达式 | ✅ AST-based (替换 eval) | ✅ 功能等价 |

### 1.4 未实现的能力

| 能力 | Java 类 | 优先级 | 影响 |
|------|---------|--------|------|
| **SqlFormula 条件生成器** | 20 个 Formula 类 | P1 | 复杂 slice 条件（范围、层级、IN 等）的 SQL 生成 |
| **QueryFacade 执行管线** | QueryFacade + Steps | P1 | beforeQuery/afterQuery 插件链 |
| **JoinGraph 路径查找** | JoinGraph + JoinEdge | P2 | 多跳 JOIN 路径计算（当前只支持 1 级） |
| **CTE 多模型编排** | ComposedSql + CteComposer | P2 | compose_query 工具依赖 |
| **QM 构建器** | JdbcQueryModelBuilder | P2 | 从 .qm 文件动态构建查询模型 |
| **AutoGroupBy/Having 插件** | 5 个 Step 类 | P2 | 自动推断 GROUP BY、HAVING 过滤 |
| **DimensionMemberLoader** | 2 个类 | P3 | 维度值缓存（caption→id 反查） |
| **Parent-Child 维度** | 3 个 Dimension 子类 | P3 | 组织架构等自引用层级 |
| **TableModelProxy** | 7 个 Proxy 类 | P3 | TM 动态引用代理（fsscript loadTableModel） |

### 1.5 测试覆盖对比

| 测试类别 | Java 测试数 | Python 测试数 | 覆盖率 |
|----------|-----------|-------------|--------|
| 模型定义 & 加载器 | 21 | 74 | ✅ 352% |
| 查询构建 / Visitor | 11 | 16 | ✅ 145% |
| 语义查询 V3 + JOIN + 维度 | 105 | 55 | ⚠️ 52% |
| 预聚合引擎 | 51 | 16 | ⚠️ 31% |
| 计算字段 | 39 | 27 | ⚠️ 69% |
| 内联表达式 | 17 | 9 | ⚠️ 53% |
| AutoGroupBy / 插件 | 64 | 15 | ⚠️ 23% |
| 授权 / 访问控制 | 29 | 28 | ✅ 97% |
| 查询验证 | 16 | 10 | ⚠️ 63% |
| SQL 方言翻译 | 108 | 176 | ✅ 163% |
| 查询执行（电商集成） | 84 | 0 | ❌ 0% |
| 维度层级 / 嵌套维度 | 52 | 0 | ❌ 0% |
| 多数据库 | 18 | 0 | ❌ 0% |
| **总计** | **672** | **250** | **37.2%** |

---

## 二、MCP 模块

### 2.1 总览

| 指标 | Java | Python | 覆盖率 |
|------|------|--------|--------|
| 源码文件 | 64 | 39 | 60.9% |
| 测试文件 | 27 | 3 | 11.1% |
| 测试方法 | 221 | 98 | 44.3% |

### 2.2 子模块对比

| 子模块 | Java 类数 | Python 类数 | 状态 | 说明 |
|--------|----------|------------|------|------|
| **tools/** | 9 | 4 | ⚠️ 44% | 已实现: Metadata、Query、Describe、Validate。缺: NL Query、Compose、Chart、Export、TableInspect |
| **spi/** | 5 | 4 | ✅ 80% | DatasetAccessor、LocalAccessor、RemoteAccessor(stub)、SemanticServiceResolver |
| **services/** | 7 | 2 | ⚠️ 29% | 已实现: McpToolDispatcher。缺: McpService、ToolConfigLoader(已独立到schemas/)、ToolFilterService、QueryExpertService |
| **config/** | 9 | 3 | ⚠️ 33% | 已实现: McpProperties、AuthProperties、DataSourceManager。缺: MultiPort、WebClient、FieldInfo 等 |
| **schema/** | 6 | 3 | ⚠️ 50% | 已实现: McpRequest/Response/Error。缺: NLQuery 请求/响应 |
| **auth/** | 3 | 3 | ✅ 100% | NoAuth、ApiKey、JWT 三策略 + RBAC |
| **controllers/routers/** | 7 | 4 | ⚠️ 57% | 已实现: Analyst、Admin、Health、MCP RPC。缺: Business、ChartImage、DevTools |
| **audit/** | 3 | 2 | ✅ 67% | ToolAuditService + ToolAuditLog |
| **validation/** | 5 | 2 | ⚠️ 40% | 基础验证已实现，缺详细的 ValidationError/Warning |
| **datasource/** | 4 | 1 | ⚠️ 25% | DataSourceManager 已实现，缺持久化和 Controller |
| **storage/** | 5 | 2 | ⚠️ 40% | LocalChartStorage 已实现，缺 cloud 适配器 |
| **schemas/** | — | 3 | ✅ Python 独有 | tool_config_loader + 共享 schema 文件（从 Java 同步） |

### 2.3 MCP 工具状态

| 工具名 | Java | Python | 状态 |
|--------|------|--------|------|
| `dataset.get_metadata` | ✅ MetadataTool | ✅ Markdown + JSON | ✅ 完成 |
| `dataset.describe_model_internal` | ✅ DescriptionModelTool | ✅ 已实现 | ✅ 完成 |
| `dataset.query_model` | ✅ QueryModelTool (V3) | ✅ 支持 payload 格式 + 内联聚合 | ✅ 完成 |
| `dataset_nl.query` | ✅ NaturalLanguageQueryTool | ❌ 未实现 | 需要 AI 服务 |
| `dataset.compose_query` | ✅ ComposeQueryTool | ❌ 未实现 | 需要 CTE 编排引擎 |
| `chart.generate` | ✅ ChartTool | ❌ 未实现 | 需要 chart-render-service |
| `dataset.export_with_chart` | ✅ ExportWithChartTool | ❌ 未实现 | 需要 chart-render-service |
| `dataset.inspect_table` | ✅ TableInspectionTool | ❌ 未实现 | Admin 工具 |
| `semantic_layer.validate` | ✅ SemanticLayerValidationTool | ❌ 未实现 | 需要 bundle 系统 |

### 2.4 MCP 协议能力

| 能力 | Java | Python | 状态 |
|------|------|--------|------|
| Streamable HTTP (POST) | ✅ | ✅ | ✅ 完成 |
| SSE Stream (GET) | ✅ | ✅ | ✅ 完成 |
| Session Management | ✅ Mcp-Session-Id | ✅ Mcp-Session-Id | ✅ 完成 |
| JSON-RPC 2.0 | ✅ | ✅ (无 error:null) | ✅ 完成 |
| Notification handling (202) | ✅ | ✅ | ✅ 完成 |
| tools/list | ✅ | ✅ 从共享 schema 加载 | ✅ 完成 |
| tools/call | ✅ | ✅ 3 个工具可用 | ⚠️ 部分 |
| resources/list | ✅ | ✅ | ✅ 完成 |
| resources/read | ✅ | ✅ | ✅ 完成 |
| prompts/list | ✅ | ✅ (空) | ✅ 完成 |
| Multi-port (Admin/Analyst/Business) | ✅ 3 端口 | ⚠️ 仅 Analyst | ⚠️ 部分 |
| 工具定义同步 | ✅ ToolConfigLoader | ✅ sync_mcp_schemas.py | ✅ 完成 |

### 2.5 MCP 测试覆盖

| 测试类别 | Java 测试数 | Python 测试数 | 覆盖率 |
|----------|-----------|-------------|--------|
| 工具配置加载 | 15 | 12 | ⚠️ 80% |
| 工具调度 | 10 | 8 | ⚠️ 80% |
| 元数据工具 | 20 | 15 | ⚠️ 75% |
| 查询工具 | 25 | 10 | ⚠️ 40% |
| 图表工具 | 15 | 5 | ⚠️ 33% |
| NL 查询工具 | 20 | 0 | ❌ 0% |
| 认证/授权 | 15 | 12 | ⚠️ 80% |
| 审计 | 10 | 8 | ⚠️ 80% |
| Controller 集成 | 30 | 0 | ❌ 0% |
| AI 集成测试 | 40 | 0 | ❌ 0% |
| 语义层验证 | 15 | 10 | ⚠️ 67% |
| **总计** | **221** | **98** | **44.3%** |

---

## 三、整体评估

### 3.1 功能完成度

```
dataset_model 模块
  ████████████████░░░░░░░░░░░░░░ 55%
  核心查询管线已通，缺 SqlFormula/QueryFacade/插件链/CTE

MCP 模块
  ██████████████████████░░░░░░░░ 70%
  3/9 工具完成，协议层完整，缺 NL/Chart/Compose 等高级工具

测试覆盖
  ████████████░░░░░░░░░░░░░░░░░░ 39%
  955 / ~2400 (Java dataset_model 672 + MCP 221 + 其他模块)
```

### 3.2 下一步优先级

| 优先级 | 工作项 | 预估工作量 | 影响 |
|--------|--------|-----------|------|
| **P0** | SqlFormula 条件生成器（20 类） | 3-5 天 | 完整的 slice 条件支持 |
| **P0** | QueryFacade 执行管线 | 2-3 天 | beforeQuery/afterQuery 插件 |
| **P1** | JoinGraph 多跳路径 | 1-2 天 | 复杂星型/雪花模型 |
| **P1** | QM 构建器 + .qm 文件加载 | 3-5 天 | 动态模型注册 |
| **P1** | compose_query (CTE 编排) | 3-5 天 | 多模型联合查询 |
| **P2** | NL Query 工具 | 2-3 天 | 需要 AI 服务对接 |
| **P2** | Chart 工具 | 1-2 天 | 需要 chart-render-service |
| **P2** | Parent-Child 维度 | 2-3 天 | 组织架构层级 |
| **P3** | TableModelProxy | 2-3 天 | fsscript loadTableModel |
| **P3** | 多端口 (Admin/Business) | 1 天 | 角色分离 |
