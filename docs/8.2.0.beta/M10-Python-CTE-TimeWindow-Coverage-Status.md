# M10 Python CTE / TimeWindow Coverage — Status & Gap Report

> **Doc role**: M11-S8 deliverable (Python parity mirror)
> **Trigger**: `foggy-data-mcp-bridge/docs/8.2.0.beta/M10-Python-CTE-TimeWindow-Coverage-Alignment-Prompt.md`
> **Status**: `audit-complete · awaiting scope decision`
> **Date**: 2026-04-26

## TL;DR

Python 侧的 compose / CTE / script runtime / MCP 测试**总数 608+**，但分类后只有 PREVIEW（551）和 MIXED（57）两类，**REAL（真实 DB parity）= 0**。timeWindow 更严重：**整套 DSL + AST 展开 + 相对日期 lowering 在 Python 仓不存在**，只有 `MeasureType.TIME_INTELLIGENT` 枚举占位 + 一个未被调用的 `time_function` 字段。

Java 矩阵的六个维度里：
- compose 三件（derived/filter / join aggregate / union all）+ script resource + MCP `compose_script` —— 基础设施就绪，可以补 parity
- timeWindow 四件（YoY / MTD / YTD / rolling）—— **不是测试问题，是功能缺失**

## 现状盘点

### 1. Compose / CTE / Script Runtime 测试

| 维度 | 文件 | tests | 类别 | 真实 DB | 备注 |
|---|---|---:|---|---|---|
| compilation | `tests/compose/compilation/test_*.py` (13 文件) | 166 | PREVIEW | ❌ | 全部检查 SQL 字符串 / AST 形状 |
| plan tree | `tests/compose/plan/test_*.py` (6 文件) | 80 | PREVIEW | ❌ | AST 不变量、链式 builder |
| runtime | `tests/compose/runtime/test_*.py` (7 文件) | 132 | MIXED | ⚠️ | 用 `StubSemanticService` 返回 `[{"sentinel": "row"}]` |
| sandbox | `tests/compose/sandbox/test_*.py` (5 文件) | 51 | PREVIEW | ❌ | 安全护栏 |
| schema | `tests/compose/schema/test_*.py` (4 文件) | 67 | PREVIEW | ❌ | 输出 schema 派生 |
| authority | `tests/compose/authority/test_*.py` (9 文件) | 112 | PREVIEW | ❌ | 权限契约 |
| engine | `tests/engine/compose/test_join_select_api.py` | 6 | PREVIEW | ❌ | 链式 API 形状 |

**对应 Java 的 4 个 parity 测试类，Python 侧 0 等价：**

| Java 类 | 用途 | Python 等价 |
|---|---|---|
| `ComposeRealSqlParityTest` | derived/filter / join aggregate / union all 真实 SQL parity | ❌ 缺失 |
| `ScriptResourceRealSqlParityTest` | JS 脚本资源真实执行 + 手写 SQL 比对 | ❌ 缺失 |
| `ComposedDataSetResultIntegrationTest` | legacy `withJoin` 容器 + 缓存 + parity | ⚠️ N/A（Python 无此 legacy 路径） |
| `ComposeScriptToolIntegrationTest` | MCP `dataset.compose_script` embedded 真实 join 脚本 parity | ❌ 缺失（仅有 stub-based 单元测试） |

### 2. TimeWindow 整体覆盖

**结论：Python 仓没有 timeWindow 实现**

| Java 组件 | Python 状态 | 影响 |
|---|---|---|
| `TimeWindowDef`（值对象） | **不存在** | 无法构造 timeWindow 请求 |
| `TimeWindowValidator`（方言兼容矩阵） | **不存在** | 无校验 |
| `RelativeDateParser`（today/yesterday/last_week/MTD/YTD lowering） | **不存在** | 无相对日期 |
| `TimeWindowExpander`（`_window` slice AST 展开） | **不存在** | 无 AST 展开 |
| YoY 自连接 | **不存在** | 无 prior-year 比对 |
| MTD / YTD 累计窗口 | **不存在** | 无累计 |
| Rolling 7d/30d 滑动窗口 | **不存在** | 无滑动 |
| 方言 capability 检测（MySQL 5.7 vs 8） | **不存在** | 无能力开关 |
| 标准窗口函数（lag/lead/rowNumber/rank/over） | ✅ 部分（`tests/test_dataset_model/test_window_functions.py` 23 PREVIEW tests） | 仅 ANSI 形状 |

唯一遗迹：

```python
# src/foggy/dataset_model/definitions/measure.py
TIME_INTELLIGENT = "time_intelligent"  # Time-based (YoY, MoM, etc.)  ← 枚举占位
time_function: Optional[str] = Field(default=None, ...)               ← 字段占位，无消费者
```

### 3. 真实 DB 测试基础设施

| 资产 | 状态 | 位置 |
|---|---|---|
| SQLite executor + 内存 fixture | ✅ 已有 | `src/foggy/dataset/db/executor.py` · `tests/test_dataset_model/test_conditional_aggregate_if_alignment.py` |
| MySQL / PG executor | ✅ 已有（硬编码 docker port） | 同上 |
| Ecommerce demo schema（fact_sales / dim_date / 等） | ✅ 已有 | `src/foggy/demo/models/ecommerce_models.py` |
| 共享 SQL parity normalizer | ✅ 已有 | `tests/integration/_sql_normalizer.py` |
| **`assertRowsEqual` + canonical row 归一化** | ❌ 缺失 | Java 用 `BigDecimal` 6位 + `stripTrailingZeros` + 排序 |
| **`EcommerceTestSupport` 等价 fixture（绑定 SQLite + 模型注册 + executor）** | ❌ 缺失 | Java 提供一站式 |
| **MCP 工具集成测试 harness（HTTP / JSON-RPC + 真实 DB）** | ❌ 缺失 | `tests/test_mcp/test_compose_script_tool.py` 仅 stub |
| **方言 capability 检测**（`supportsWindowFunctions()`） | ❌ 缺失 | 无 pytest skipif / probe fixture |

## Java parity 契约（Python 必须复现）

```
SETUP:
  - 继承 EcommerceTestSupport 等价 fixture（in-memory SQLite + 模型 + 种子数据）
  - 取得 dialect_key + 是否支持窗口函数
  - 注册 fact_sales / fact_return / dim_product / dim_date 等

EXECUTE:
  - 通过 SemanticQueryService / compose runtime 拿 actual rows
  - 写等价手写 SQL（方言相关 quoting：MySQL backtick / MSSQL bracket / PG-SQLite quote）
  - 用 executor 直接跑手写 SQL 拿 expected rows

COMPARE:
  - assertRowsEqual(expected, actual, require_non_empty)
    · canonical_rows: 每行字段按 key 排序 → LinkedHashMap
    · canonical_value: 数字 → BigDecimal 6位 HALF_UP stripTrailingZeros
    · 行排序按 toString() 稳定化
    · expected.size == actual.size 且全等

CAPABILITY:
  - supports_window_functions() → 当 dialect == mysql 5.7 → False，使用 info-log no-op
  - 不接受无解释的 skip 噪音
```

## 维度落地难度

| 维度 | 落地难度 | 阻塞？ | 估计工作量 |
|---|---|---|---|
| `assertRowsEqual` + canonical_rows 归一化器 | 低 | 否 | 0.5 day（独立模块 + 12 个单元测试） |
| Ecommerce 真实 DB fixture（compose 专用） | 低 | 否 | 0.5 day（复用 demo schema + executor） |
| compose CTE parity（derived/filter / join aggregate / union all） | 中 | 否 | 1 day（3 个 parity test，每个含等价手写 SQL） |
| script resource auto-execute parity | 中 | 否 | 0.5 day（复用 JS fixture + 上面的 fixture） |
| MCP `compose_script` 工具真实集成测试 | 中 | 否 | 0.5 day（接入现有 MCP harness） |
| 方言 capability 检测 fixture | 低 | 否 | 0.25 day |
| **timeWindow `TimeWindowDef` / Validator / RelativeDateParser / Expander 移植** | **高** | **是** | **3-5 days**（功能移植，非测试） |
| timeWindow YoY/MTD/YTD/rolling parity 测试 | 中 | **是（依赖上一项）** | 1.5 day（移植完成后） |

## 推荐分批

### Batch 1: compose / CTE / MCP（不阻塞，可立即开干）

可以在 1-2 天内完成 M10 prompt 第 2 步前 5 个维度：

1. 写 `tests/compose/parity/_assertions.py` —— `canonical_rows` + `assert_rows_equal` + 数字归一化
2. 写 `tests/compose/parity/conftest.py` —— ecommerce SQLite fixture + `parity_executor` + `parity_service`
3. 实现 `test_compose_real_sql_parity.py` —— 3 tests（derived/filter / join aggregate / union all）
4. 实现 `test_script_resource_real_sql_parity.py` —— 3 tests（用现有的 union/join/derived JS fixture）
5. 实现 `test_compose_script_tool_real_db.py` —— 1-2 tests（MCP 工具 + 真实 DB）
6. 加方言 capability fixture（compose 不需要窗口，但 timeWindow 用得上）

**回写 deliverable**：M11-S8 状态 `pending → completed (compose 部分)`

### Batch 2: timeWindow（阻塞 — 需先开 P0 移植 REQ）

不能直接补 parity 测试，因为功能不存在。需先：

1. 写 P0 REQ：`docs/8.2.0.beta/P0-TimeWindow-Python-Port-需求.md`
   - 移植 4 个 Java 类：`TimeWindowDef` / `TimeWindowValidator` / `RelativeDateParser` / `TimeWindowExpander`
   - 接入 Python `SemanticQueryRequest` 的 `_window` slice 操作符
   - 4 方言 SQL lowering（MySQL/PG/SQLite/MSSQL）
2. 实施移植（3-5 day）
3. 然后再补 YoY/MTD/YTD/rolling 真实 SQL parity（1.5 day）

**当前 M10 prompt 把"补测试"和"补功能"两件事打包在一起，timeWindow 部分实际上是一个独立的功能 REQ，应该升级到 P0 级别另立项。**

## 给用户的决策点

1. **Batch 1 是否立即开干？** —— 可独立交付，约 1-2 天，是 M10 prompt 里 6 维度中的 5 个 + 测试基础设施
2. **timeWindow 移植 REQ 是否本轮立项？** —— 如果立项，本会话先写 REQ 文档，下个会话开移植；如果不立项，M10 标 `partial-complete`，timeWindow 部分挂到 M11-S8 / M11-S5 的 follow-up 列表
3. **`CteComposer.compose` 的 `select_columns` API 漂移** —— 你说 Java 侧另会话处理。Python 侧无需改动；本 doc 已记录差异

## 当前文件交付

- 本文档：`foggy-data-mcp-bridge-python/docs/8.2.0.beta/M10-Python-CTE-TimeWindow-Coverage-Status.md`
- 引用 Java 侧规范：`foggy-data-mcp-bridge/docs/8.2.0.beta/M10-Python-CTE-TimeWindow-Coverage-Alignment-Prompt.md`
- 引用 Java 侧 M11 收口：`foggy-data-mcp-bridge/docs/8.2.0.beta/M11-CTE-TimeWindow-Coverage-Closure-Plan.md`

待用户决策后回写本文档 §推荐分批 章节为 `in-progress` 或 `accepted-with-deferred`。
