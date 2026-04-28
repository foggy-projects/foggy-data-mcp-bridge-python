# B-03 — v1.3 引擎收紧裸 dimension 引用 + 修复 `dimension AS alias` 静默丢列

## 基本信息

- 优先级：P0（已抬升）
- 状态：📋 **已抬升 → Python `v1.7` + Java `8.4.0.beta`**（2026-04-28）
- 改造路径：**Path A · 严格化**（用户决策）
- 来源：G5 PR-P2 调试期（`cf2ba9b` → `352a8bb` 复盘）
- 影响：测试基线 / LLM 生成 SQL 行为可预测性 / 与 QM 公开契约一致性

## 抬升后的正式文档

- Python `v1.7`：[`docs/v1.7/P0-v13引擎收紧裸dimension引用-需求.md`](../v1.7/P0-v13引擎收紧裸dimension引用-需求.md) + [`progress.md`](../v1.7/P0-v13引擎收紧裸dimension引用-progress.md)
- Java `8.4.0.beta`：`foggy-data-mcp-bridge/docs/8.4.0.beta/P0-v13引擎收紧裸dimension引用-{需求,progress}.md`（worktree `dev-compose`）

本 backlog 文件保留为历史复盘记录；后续讨论 / 实施 / 验收一律走正式文档。

## 问题摘要

v1.3 `SemanticQueryService.build_query_with_governance`（Python）/ `SemanticServiceV3Impl`（Java）当前对 `columns: List[str]` 中的 dimension 引用存在两条不符合 QM 公开契约的行为：

### 行为 1 · 裸 dimension 引用被 fallback 解析

```python
columns=["orderStatus"]   # 实际行为：fallback 到 t.order_status AS "<dim caption>"
```

按 Foggy QM 公开契约，dimension **不是可投影的列**，必须通过属性引用：
- `orderStatus$id` — 业务键 / FK
- `orderStatus$caption` — 显示名
- `orderStatus$<custom_attr>` — 在 TM 声明的其他属性

LLM 看到的 `dataset.get_metadata` / `dataset.describe_model_internal` 元数据**从不暴露**裸 dimension 作为可投影字段——所以裸引用是**遗留宽容路径**，不在公开契约范围内。

### 行为 2 · `dimension AS alias` 静默丢列

```python
columns=["orderStatus AS status"]
# 实际行为：既不匹配 inline-aggregate（缺括号）
#         又不能 model.resolve_field("orderStatus AS status")
#         → 静默被循环跳过，最终 SQL:
#           WITH cte_0 AS (FROM fact_sales AS t LIMIT 1000)
#           SELECT * FROM cte_0
```

这是 G5 PR-P2 调试期发现的 v1.3 长期 bug：用户写错 `field AS alias` 形态时引擎应当 fail-loud，但当前路径既不匹配 `parse_inline_aggregate` 又不匹配 `resolve_field`，被循环 silently 跳过——最终生成的 SQL 没有 SELECT 子句（外层 `SELECT * FROM cte_0` 看似正常，但 cte_0 内部没有列，等于 `SELECT *` 一个空集）。

### 行为 3（次要）· `dimension$attr AS alias` 也被静默忽略

```python
columns=["orderStatus$caption AS status"]
# 实际行为：识别 $caption 走 resolve_field，但 AS 后缀被忽略，
#         alias 仍用 TM 里声明的 dimension.alias（"订单状态"）
```

`AS alias` 对 dimension 引用整体无效——只对 inline-aggregate 路径生效。

## 根因（Python · `service.py:765-779`）

```python
for col_name in request.columns:
    inline = self._parse_inline_expression(col_name, model, ensure_join)  # 路径 1
    if inline:
        builder.select(inline["select_expr"]); continue
    resolved = model.resolve_field(col_name)                              # 路径 2
    if resolved:
        # 用 dimension.alias / TM-defined caption 作 SQL alias
        ...
    # ❌ 既不命中路径 1 又不命中路径 2 → 循环跳过，无任何报错
```

Java `SemanticServiceV3Impl` 同源（具体类待补，应有等价循环）。

## 影响范围

1. **测试稳定性**：当前 G5 F5 集成测试在 PR-P2 (`cf2ba9b`) 用了裸 `orderStatus`，已在 followup commit (`352a8bb`) 改为 `orderStatus$caption` 摆脱依赖宽容路径。但其他 v1.3 集成测试可能仍有依赖。

2. **LLM 错误反馈**：LLM 写错 `"orderStatus AS status"` 时不报错，返回空 SELECT 结果，难以诊断；理想情况是 fail-loud 提示 `Did you mean "orderStatus$caption AS status"?`。

3. **跨语言契约一致性**：Java 行为可能略有差异（具体待审计），双端契约对齐需要明确的统一规则。

## 建议改造（待立项时细化）

### 路径 A · 严格化（推荐）

1. `resolve_field` 拒绝裸 dimension 引用（保留 measure / dimension attribute / calc field）
2. `parse_inline_expression` 后的 fallback 路径加 fail-loud：
   ```python
   raise ValueError(
       f"COLUMN_FIELD_NOT_FOUND: column '{col_name}' could not be resolved. "
       f"Did you mean '{col_name}$caption' or '{col_name}$id'?"
   )
   ```
3. dimension `AS alias` 形态也走 fail-loud 拒绝（强制走 `dimension$attr AS alias`，仍要确认引擎支持后者）

### 路径 B · 兼容化（次推荐）

保留裸 dimension 兼容（标 deprecated）；只修 `dimension AS alias` 静默丢列（fail-loud 拒绝）。

### 共同前置

- 跨双端 audit `_build_query` / `processQueryColumns`（Java 等价方法）现有行为
- 在 spec 里明确"dimension 投影必须走 `$attr` 形态"作为公开契约
- 影响面评估：vendored Odoo Pro embedded、所有现有 fast-lane 测试、AI Chat session 中的历史 query

## 关联

- G5 PR-P2 followup commit：`foggy-data-mcp-bridge-python` `352a8bb`
- 公开契约语义：`docs-site/zh/dataset-model/tm-qm/query-dsl.md` §dimension 引用形式
- v1.3 引擎参考：`foggy-data-mcp-bridge-python/src/foggy/dataset_model/semantic/service.py:765-779`
- 集成测试规范：`CLAUDE.md` § 集成测试规范（真实 SQL 比对）
