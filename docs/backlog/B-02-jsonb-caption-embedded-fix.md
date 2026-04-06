# B-02 — Partner country JSONB caption embedded 引擎修复

## 基本信息

- 优先级：低
- 状态：✅ 已修复
- 来源：`foggy-odoo-bridge-pro` P0-08 Phase 3（demo 兼容性测试发现）

## 问题

通过 Odoo MCP embedded 模式查询 `OdooResPartnerQueryModel` 时，如果只请求 `country$caption` 列，返回 `items: []`（空结果）。

直连 Java gateway 查询相同数据时正常返回。

## 分析

Embedded 引擎（Python）的 SQL 构建中 `country$caption` 解析为 `rc.id`（country ID）而非 `rc.name ->> 'en_US'`（JSONB caption 提取）。当权限过滤条件叠加时（`partner_share` ir.rule），可能导致 0 rows。

## 影响

- demo 兼容性测试中 Partner Country JSONB 条目被注释跳过
- 不影响其他模型的 JSONB caption（department/job/journal/pickingType 等都正常）

## 建议

调查 `load_models_from_directory()` 中 `jsonbCaption()` 函数在 Python evaluator 中的解析行为。可能是 `dialectFormulaDef.postgresql.builder` 在 Python 引擎中未被正确执行。
