# B-01 — Python gateway response 格式对齐 Java pagination

## 基本信息

- 优先级：中
- 状态：待排期
- 来源：`foggy-odoo-bridge-pro` P0-08 Phase 4
- 影响：Python gateway 通过 Odoo MCP 透传时，E2E 测试需要额外兼容代码

## 问题

Java gateway 的查询 response 包含标准 `pagination` 对象：

```json
{
  "items": [...],
  "pagination": {
    "start": 0,
    "limit": 5,
    "returned": 3,
    "totalCount": null,
    "hasMore": false
  }
}
```

Python gateway 的 response 没有 `pagination`，只有 `total`：

```json
{
  "items": [...],
  "total": 3
}
```

## 影响

- `foggy-odoo-bridge-pro` E2E 测试需要 `_assert_has_rows()` 兼容函数（已实施）
- 消费方需要知道当前是 Java 还是 Python 引擎来解析 response
- 列名在 Python embedded 模式下返回 display title（如 `"Employee Name"`），Java 返回原始字段名（如 `"name"`）

## 建议方案

Python 引擎在 `SemanticQueryService.query_model()` 的返回值中增加 `pagination` 对象，结构与 Java 一致。

## 约束

- 不影响现有 Python MCP 的公开 API
- 不需要一次性改完，可分阶段（先加 pagination，再对齐 column naming）
