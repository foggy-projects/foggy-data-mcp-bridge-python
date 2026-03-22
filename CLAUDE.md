# Foggy Data MCP Bridge — Python

> **开源项目，请勿上传私有 key、账号密码、token 等敏感信息。**

从 [foggy-data-mcp-bridge](../foggy-data-mcp-bridge/) (Java) 迁移的 Python 版语义层查询服务。

## 快速启动

```bash
cd foggy-python

# 安装依赖
pip install -e ".[dev]"
pip install aiomysql   # MySQL 支持

# 运行测试
python -m pytest --tb=short -q

# 启动 MCP 服务（连接 Docker MySQL）
python -m foggy.demo.run_demo --port 8066

# 或指定数据库
python -m foggy.mcp.launcher.app --db-host localhost --db-port 13306 --db-user foggy --db-password foggy_test_123 --db-name foggy_test
```

## 项目结构

```
foggy-python/
├── src/foggy/
│   ├── core/              # 核心工具（异常、过滤器、工具类）
│   ├── bean_copy/         # Bean/Map 转换
│   ├── mcp_spi/           # MCP 工具接口
│   ├── dataset/           # 数据库层（方言、SQL 构建、ResultSet）
│   ├── dataset_model/     # 语义层引擎（定义、查询、元数据）
│   ├── fsscript/          # FSScript 脚本引擎
│   ├── mcp/               # MCP 服务器
│   │   ├── launcher/      # FastAPI 启动器
│   │   ├── routers/       # HTTP 路由（admin/analyst/mcp_rpc）
│   │   ├── schemas/       # 工具定义文件（从 Java 同步）
│   │   ├── spi/           # DatasetAccessor
│   │   ├── config/        # 配置（DataSource、Properties）
│   │   └── audit/         # 审计日志
│   └── demo/              # 演示模型和启动脚本
├── tests/                 # pytest 测试（625+）
└── scripts/
    └── sync_mcp_schemas.py  # 同步 Java 工具定义
```

## MCP 端点

| 路径 | 方法 | 说明 |
|------|------|------|
| `/mcp/analyst/rpc` | POST | MCP Streamable HTTP（JSON-RPC 2.0） |
| `/mcp/analyst/rpc` | GET | SSE 流 |
| `/api/v1/models` | GET | 列出所有模型 |
| `/api/v1/models/{name}` | GET | 模型元数据 |
| `/api/v1/query/{name}` | POST | 执行查询 |
| `/api/v1/query/{name}/validate` | POST | 验证查询（不执行） |
| `/health` | GET | 健康检查 |
| `/docs` | GET | Swagger UI |

## MCP 工具（对齐 Java）

| 工具名 | 说明 | 状态 |
|--------|------|------|
| `dataset.get_metadata` | 获取所有模型和字段的 V3 元数据包 | ✅ |
| `dataset.describe_model_internal` | 获取指定模型的详细元数据定义 | ✅ |
| `dataset.query_model` | 执行数据模型查询（V3：支持 payload 格式） | ✅ |
| `dataset_nl.query` | 自然语言查询 | ⏳ 需要 AI 服务 |
| `dataset.compose_query` | FSScript 多模型编排查询 | ⏳ |
| `chart.generate` | 图表生成 | ⏳ 需要 chart-render-service |
| `dataset.export_with_chart` | 查询+图表导出 | ⏳ |
| `dataset.inspect_table` | 数据库表结构检查 | ⏳ |

**工具定义从 `src/foggy/mcp/schemas/` 加载**（JSON schema + Markdown 描述），与 Java 共享同一套文件。

## 同步 MCP 工具定义

Java 侧修改工具描述/schema 后，运行：

```bash
python scripts/sync_mcp_schemas.py          # 执行同步
python scripts/sync_mcp_schemas.py --diff   # 仅查看差异
python scripts/sync_mcp_schemas.py --dry-run  # 预览不执行
```

## 数据库连接

默认连接 Java Docker MySQL：
- **Host**: localhost:13306
- **User**: foggy / foggy_test_123
- **Database**: foggy_test
- **Tables**: fact_sales, fact_order, dim_date, dim_product, dim_customer, dim_store, dim_channel, dim_promotion

## 依赖关系

```
foggy.mcp (MCP Server)
  ├── foggy.dataset_model (语义查询引擎)
  │   ├── foggy.dataset (SQL 生成、数据库执行)
  │   │   └── foggy.core (工具类)
  │   └── foggy.fsscript (表达式引擎)
  └── foggy.mcp_spi (工具接口)
```

## 开发规范

- **类型标注**: 所有公开 API 必须有类型标注
- **Pydantic**: 数据模型用 Pydantic v2 BaseModel
- **异步**: 数据库操作用 async（aiomysql/asyncpg/aiosqlite）
- **测试**: 新功能必须有 pytest 测试
- **安全**: 禁止 eval()，SQL 参数用占位符，不拼接用户输入
