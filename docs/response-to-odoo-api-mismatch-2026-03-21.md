# Python 团队回复：API 签名不一致报告

> **日期**：2026-03-21
> **回复方**：foggy-data-mcp-bridge-python 团队
> **针对文档**：`foggy-odoo-bridge/docs/api-signature-mismatch-report-2026-03-21.md`

---

## 一、总体结论

经过代码审查，报告中描述的 3 个问题**根因只有 1 个**：vendored 打包缺失 `foggy.mcp.spi` 模块。

Python 侧**已有完整的 dict → typed object 转换层**，Odoo 团队当前遇到的签名不匹配问题，本质上是因为 vendored 版本无法 import 到正确的桥接类 `LocalDatasetAccessor`，被迫尝试直接调用引擎层 `SemanticQueryService` 而暴露出来的。

---

## 二、逐项回复

### 问题 1：`query_model()` 第二参数类型不匹配

**结论：此问题在正确使用桥接层时不存在。**

Python 代码中已有明确的两层设计：

| 层 | 类 | `query_model` 第二参数 | 文件位置 |
|---|---|---|---|
| 外部 SPI（调用方应使用） | `DatasetAccessor` | `payload: Dict[str, Any]` ✅ 标准 JSON | `foggy/mcp/spi/__init__.py:375` |
| 桥接实现 | `LocalDatasetAccessor` | `payload: Dict[str, Any]` → 内部自动转换 | `foggy/mcp/spi/__init__.py:500` |
| 内部引擎（不应直接调用） | `SemanticQueryService` | `request: SemanticQueryRequest` 强类型 | `foggy/dataset_model/semantic/service.py:138` |

转换逻辑已实现在 `_build_query_request()` 函数中（`foggy/mcp/spi/__init__.py:438-460`），完整支持所有 Java camelCase 字段：

```python
# Odoo 侧正确的调用方式：
from foggy.mcp_spi import LocalDatasetAccessor  # 修复后的 import 路径

accessor = LocalDatasetAccessor(service)
result = accessor.query_model("sale_order", {
    "columns": ["name", "amount"],
    "limit": 10,
    "groupBy": ["category"],       # Java camelCase ✅
    "orderBy": [{"field": "amount", "direction": "DESC"}],
    "slice": [{"field": "status", "op": "eq", "value": "active"}],
})
# ↑ 标准 JSON dict，内部自动转换为 SemanticQueryRequest
```

**不计划在 `SemanticQueryService` 引擎层支持 dict 入参**——这是有意的分层设计，引擎层保持强类型以确保内部一致性。

---

### 问题 2：`describe_model()` — 需要补充

**结论：确认缺失，将补充实现。**

当前现状：
- `DatasetAccessor` 抽象类**已定义** `describe_model(model, format)` 方法签名 ✅
- `LocalDatasetAccessor` **已有实现**，内部调用 `resolver.get_metadata(request, format, context)` ✅
- MCP 工具层 `DescriptionModelTool` 和 `mcp_rpc.py` 路由**已有** `describe_model_internal` 的处理逻辑 ✅
- `SemanticQueryService`（引擎层）没有名为 `describe_model` 的独立方法，但 `get_metadata()` 在传入 `SemanticMetadataRequest(model=model_name)` 时已能返回单模型元数据

**实际影响评估**：`LocalDatasetAccessor.describe_model()` 已经可以正常工作（通过组合 `get_metadata` 实现）。Odoo 侧在解决问题 3 后，可以直接调用 `accessor.describe_model("sale_order")`，**无需等待引擎层新增方法**。

**后续优化**：我们会在 `SemanticQueryService` 引擎层补充一个语义更清晰的 `describe_model()` 便捷方法，但这不阻塞 Odoo 侧的开发。

---

### 问题 3：`foggy.mcp.spi` 模块 vendored 版本缺失

**结论：确认为根因，将修复。**

#### 修复方案：消除 `foggy.mcp.spi`，类型定义下沉到 `foggy.mcp_spi`

我们选择报告中建议的**方案 A**，并进一步**消除 `foggy.mcp.spi` 模块**（而非保留 re-export），原因如下：

**`foggy.mcp.spi` 不仅冗余，还造成了循环依赖**：

```
项目声明的依赖方向：
  foggy.mcp ──▶ foggy.dataset_model ──▶ foggy.dataset ──▶ foggy.core

实际代码中的依赖：
  foggy.mcp ──▶ foggy.dataset_model ──▶ foggy.mcp.spi (属于 foggy.mcp)
       ▲                                      │
       └──────────── 循环！ ──────────────────┘
```

`service.py`（属于 `dataset_model`）import 了 `foggy.mcp.spi`（属于 `mcp`），而 `mcp` 又依赖 `dataset_model`。这个循环依赖在 CPython 中碰巧能跑（import 顺序没冲突），但在 vendored/子集打包场景下直接崩溃。

**正确的架构**：SPI 类型定义放在独立的 `foggy.mcp_spi` 包中，位于依赖链底部，所有上层模块都可以安全 import。

```
修复前：
  foggy.mcp_spi/          → 仅含 McpTool, ToolResult 等工具接口
  foggy.mcp.spi/          → 含 SemanticQueryRequest, LocalDatasetAccessor 等（循环依赖源）

修复后：
  foggy.mcp_spi/          → 合并所有 SPI 类型（唯一的 SPI 包）
    ├── __init__.py        → 导出全部类型
    ├── tool.py            → McpTool, ToolResult（原有）
    ├── context.py         → ToolExecutionContext（原有）
    ├── events.py          → ProgressEvent（原有）
    ├── semantic.py        → SemanticQueryRequest, SemanticQueryResponse, ...（从 mcp.spi 迁入）
    └── accessor.py        → DatasetAccessor, LocalDatasetAccessor, ...（从 mcp.spi 迁入）

  foggy.mcp.spi/          → 删除（不保留 re-export）
```

依赖方向修复后：

```
foggy.mcp ──────────▶ foggy.dataset_model ──▶ foggy.dataset ──▶ foggy.core
    │                        │
    ▼                        ▼
foggy.mcp_spi ◀──────────────┘   ← 单向，无循环
```

**变更范围**：

| 文件 | 变更 |
|------|------|
| `foggy/mcp_spi/__init__.py` | 新增导出 Semantic 系列类型和 Accessor |
| `foggy/mcp_spi/semantic.py` | 新增，从 `foggy/mcp/spi/__init__.py` 迁入类型定义 |
| `foggy/mcp_spi/accessor.py` | 新增，从 `foggy/mcp/spi/__init__.py` 迁入 Accessor |
| `foggy/mcp/spi/` | **删除整个目录** |
| `foggy/dataset_model/semantic/service.py` | import 路径改为 `from foggy.mcp_spi import ...` |
| `foggy/mcp/` 下引用 `foggy.mcp.spi` 的文件 | import 路径统一改为 `from foggy.mcp_spi import ...` |

**不保留 re-export 的理由**：
- 保留 re-export 意味着循环依赖仍然"可用"，新代码可能继续错误地 import `foggy.mcp.spi`
- 干净删除可以通过 CI 强制确保不会回退
- 当前没有外部第三方依赖 `foggy.mcp.spi`（唯一的外部消费者是 Odoo vendored，而它本来就 import 不了）

---

## 三、Odoo 团队需要的 Action Items

修复完成后，Odoo 侧 `embedded_backend.py` 的推荐用法：

```python
# ===== 引擎初始化 =====
from foggy.mcp_spi import LocalDatasetAccessor
from foggy.dataset_model.semantic.service import SemanticQueryService

service = SemanticQueryService(...)
accessor = LocalDatasetAccessor(service)

# ===== 查询（标准 JSON dict 入参） =====
result = accessor.query_model("sale_order", {
    "columns": ["order_name", "total_amount"],
    "slice": [{"field": "status", "op": "eq", "value": "confirmed"}],
    "groupBy": ["customer_name"],
    "orderBy": [{"field": "total_amount", "direction": "DESC"}],
    "limit": 50
})
# result: SemanticQueryResponse
# result.model_dump(by_alias=True, exclude_none=True)  → Java 兼容 JSON

# ===== 模型描述 =====
meta = accessor.describe_model("sale_order", format="json")
# meta: SemanticMetadataResponse

# ===== 元数据 =====
all_meta = accessor.get_metadata()
# all_meta: SemanticMetadataResponse
```

**Odoo 侧 vendor 更新检查清单**：

- [ ] 更新 vendored 代码（`lib/foggy/`），确保包含 `foggy/mcp_spi/` 完整目录
- [ ] `embedded_backend.py` 中所有 import 使用 `from foggy.mcp_spi import ...`
- [ ] 通过 `LocalDatasetAccessor` 调用，**不要直接调用** `SemanticQueryService`
- [ ] 无需 vendored `foggy/mcp/` 目录（除非需要 MCP Server/Router 功能）

---

## 四、时间线

| 事项 | 预计完成 | 状态 |
|------|---------|------|
| 类型定义迁入 `foggy.mcp_spi` | 2026-03-24（周二） | 🔜 计划中 |
| 删除 `foggy.mcp.spi` + 全量 import 路径更新 | 同上 | 🔜 计划中 |
| 全量测试通过确认 | 2026-03-24 | 🔜 |
| 通知 Odoo 团队可更新 vendor | 2026-03-25（周三） | ⏳ |

---

## 五、附：修复后架构说明

### 依赖方向（修复后，无循环）

```
foggy.mcp (MCP Server)
    │
    ├──依赖──▶  foggy.dataset_model (语义查询引擎)
    │               │
    │               ├──依赖──▶  foggy.dataset (SQL 生成)
    │               │               └──▶  foggy.core (工具类)
    │               ├──依赖──▶  foggy.fsscript (表达式引擎)
    │               └──依赖──▶  foggy.mcp_spi ◀──┐
    │                                             │
    └──依赖──▶  foggy.mcp_spi (SPI 类型，唯一入口) ─┘

    ❌ foggy.mcp.spi — 已删除，不再存在
```

### 调用层次

```
Odoo embedded_backend.py / MCP Router / HTTP API
         │
         ▼
┌──────────────────────────────────────────┐
│  LocalDatasetAccessor  (foggy.mcp_spi)   │  ← 外部调用入口
│  • query_model(model, dict)              │     接受标准 JSON dict
│  • describe_model(model, format)         │
│  • get_metadata()                        │
│                                          │
│  内部：_build_query_request(dict)        │     dict → SemanticQueryRequest
│         → resolver.query_model(typed)    │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│  SemanticQueryService  (dataset_model)    │  ← 引擎层（强类型）
│  • query_model(model, SemanticQueryReq)  │     不对外暴露 dict 接口
│  • get_metadata(SemanticMetadataReq)     │     保持类型安全
│  • get_metadata_v3(model_names)          │
└──────────────────────────────────────────┘
```

### Vendored 最小依赖集（Odoo 内嵌模式所需）

```
lib/foggy/
  ├── core/               ✅ 必须
  ├── mcp_spi/            ✅ 必须（SPI 类型 + Accessor）
  ├── dataset/            ✅ 必须（SQL 引擎）
  ├── dataset_model/      ✅ 必须（语义层引擎）
  ├── fsscript/           ✅ 必须（表达式引擎）
  ├── bean_copy/          ✅ 必须（工具类）
  └── mcp/                ❌ 不需要（MCP Server/Router，仅独立部署时使用）
```

**设计原则**：MCP/外部层接受标准 JSON，引擎层保持强类型。转换职责在 `LocalDatasetAccessor` 桥接层完成。`foggy.mcp_spi` 是所有 SPI 类型的唯一归属地，位于依赖链底部，任何模块都可以安全 import。

---

## 六、附：Python 侧代码质量审查（与 Java 对齐）

> 在修复 `foggy.mcp.spi` 问题的同时，我们对整个 Python 移植项目做了全面审查。
> 以下问题将随本次修复一并或分批清理，**不影响 Odoo 侧的对接时间线**。

### 6.1 重复类型定义（将清理）

| 类型 | 正式定义（`foggy.mcp.spi` → 将迁入 `foggy.mcp_spi`） | 重复定义（`service_v3.py`） | 差异 |
|------|------|------|------|
| `SemanticQueryRequest` | Pydantic BaseModel，含 Java camelCase alias | dataclass，无 alias | 字段名不一致 |
| `SemanticQueryResponse` | Pydantic，含 `from_error()`/`from_legacy()` 工厂方法 | dataclass，无工厂方法 | 功能缺失 |
| `DebugInfo` | Pydantic，alias `durationMs` | dataclass，`duration_ms` | 序列化名不一致 |
| `ColumnDef`, `SchemaInfo`, `PaginationInfo` | Pydantic，Java 对齐 | dataclass，Python 风格 | 序列化名不一致 |

**处理方案**：`service_v3.py` 中的 dataclass 定义将被删除，统一使用 `foggy.mcp_spi` 中的 Pydantic 模型。`service_v3.py` 是 Java V3 迁移的中间产物，功能已合并到 `service.py`。

### 6.2 重复的 `LocalDatasetAccessor` 类（将清理）

| 位置 | 状态 | 说明 |
|------|------|------|
| `foggy/mcp/spi/__init__.py:467` | ✅ 正式实现 | 完整的 dict→typed 转换，含 async 支持 |
| `foggy/mcp/services/mcp_service.py:78` | ❌ 废弃桩代码 | Placeholder，方法签名不一致，返回硬编码空数据 |

**处理方案**：删除 `mcp_service.py` 中的桩实现。

### 6.3 废弃的 Schema 文件（将清理）

| 文件 | 说明 |
|------|------|
| `foggy/mcp/schema/request.py` | 旧版 `QueryRequest`/`MetadataRequest`，Python 风格字段名，未与 Java 对齐 |
| `foggy/mcp/schema/response.py` | 旧版 `QueryResult`/`MetadataResult`/`McpError`，已被 SPI 模型取代 |
| `foggy/mcp/routers/analyst.py` 中的 `QueryExecuteRequest` | 使用 `filters` 而非 Java 标准的 `slice`，需迁移 |

**处理方案**：删除旧 schema 文件，`analyst.py` 路由统一使用 `SemanticQueryRequest`。

### 6.4 字符串硬编码（将补充枚举）

当前散落在 7+ 个文件中的裸字符串比较：

```python
# 当前（多处硬编码）
if mode == "validate":       # service.py:160, 755, service_v3.py:172
if fmt == "json":            # mcp_rpc.py:208, semantic_v3.py:147, metadata_tool.py:225
```

**处理方案**：新增枚举，与 Java 侧 Constants 对齐：

```python
# foggy/mcp_spi/enums.py（新增）
class QueryMode(str, Enum):
    EXECUTE = "execute"
    VALIDATE = "validate"

class MetadataFormat(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"
```

### 6.5 无界缓存（将修复）

| 缓存 | 位置 | 问题 | 修复方案 |
|------|------|------|---------|
| `SemanticQueryService._cache` | `service.py:83` | 纯 dict，无大小限制，过期条目不清理 | 加 `maxsize` + 定期清理过期条目 |
| `DimensionMemberLoader._cache` | `member_loader.py:106` | 纯 dict，无大小限制 | 加 `maxsize` 上限 |
| `JoinGraph._path_cache` | `join/__init__.py:86` | 纯 dict，仅拓扑变更时清理 | 低优先级，加大小监控 |
| `FileModuleLoader._cache` | `module_loader.py:67` | 纯 dict，需手动 `clear_cache()` | 加 TTL 自动过期 |

> **说明**：以上缓存在 Java 侧对应的是 Guava Cache / Caffeine（有 maxSize + expireAfterWrite）。
> Python 侧迁移时简化为 dict，在长时间运行的进程（如 Odoo 内嵌模式）中存在 OOM 风险。

### 6.6 安全审查结果

| 检查项 | 结果 |
|--------|------|
| `eval()` / `exec()` 使用 | ✅ 未发现 |
| SQL 参数化 | ✅ 主路径均使用占位符。`sqlserver.py` 的 `get_table_exists_sql()` 有一处 f-string 拼接 information_schema 查询（使用了引号转义，低风险），将改为参数化 |
| `foggy.core` 依赖纯净性 | ✅ 无外部 foggy 模块 import |
| `foggy.dataset` 依赖纯净性 | ✅ 仅依赖 `foggy.core` |
| `foggy.fsscript` 依赖纯净性 | ✅ 仅内部 import |
| `foggy.mcp_spi` 依赖纯净性 | ✅ 无 `foggy.mcp` import |

### 6.7 Vendoring 影响的完整 import 修改清单

以下文件需要将 `from foggy.mcp.spi import ...` 改为 `from foggy.mcp_spi import ...`：

| 文件 | 当前 import | 分类 |
|------|------------|------|
| `foggy/dataset_model/semantic/service.py:20` | `from foggy.mcp.spi import ...` (7 个类型) | ⛔ 循环依赖（根因） |
| `foggy/mcp/launcher/app.py:24` | `from foggy.mcp.spi import LocalDatasetAccessor, ...` | 🔧 需改路径 |
| `foggy/mcp/routers/analyst.py:7` | `from foggy.mcp.spi import ...` | 🔧 需改路径 |
| `foggy/mcp/routers/mcp_rpc.py:20` | `from foggy.mcp.spi import ...` | 🔧 需改路径 |
| `foggy/mcp/routers/semantic_v3.py:18` | `from foggy.mcp.spi import ...` | 🔧 需改路径 |
| `foggy/demo/start_server.py:136,230,255` | `from foggy.mcp.spi import ...` | 🔧 需改路径 |
