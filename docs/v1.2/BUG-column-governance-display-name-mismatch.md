# BUG — 列治理 filter_response_columns / apply_masking display name 不匹配

## 基本信息

- 发现日期：2026-04-07
- 发现方：`foggy-odoo-bridge-pro` v1.2 E2E 验证
- 严重级别：**高**（有治理配置的模型查询结果全部列被清空）
- 影响范围：`filter_response_columns()` + `apply_masking()`
- 状态：**已修复** (2026-04-07)

## 问题描述

`filter_response_columns()` 和 `apply_masking()` 均使用 **QM field name**（如 `email`、`name`）匹配 items dict 的 key，但引擎查询返回的 items dict key 实际是 **SQL 列别名（display name）**（如 `"Email"`、`"Order Reference"`）。

导致结果：

1. `filter_response_columns` 中 `k in visible_set` 永远为 `False`（`"Email" not in {"email", "name", ...}"`），所有列被移除 → items 变成 `[{}, {}, ...]`
2. `apply_masking` 中 `field_name in row` 永远为 `False`（`"email" not in {"Email": "..."}"`），掩码永不执行

## 复现步骤

### 环境

- Odoo 17 embedded 模式（foggy-odoo-ui:8072）
- `foggy.column.policy` 配置：
  ```
  OdooResPartnerQueryModel / email / mask / email_mask
  ```

### 请求

```bash
curl -s -X POST http://localhost:8072/foggy-mcp/rpc \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fmcp_ui_admin_seed" \
  -d '{
    "jsonrpc": "2.0", "id": "test",
    "method": "tools/call",
    "params": {
      "name": "dataset.query_model",
      "arguments": {
        "model": "OdooResPartnerQueryModel",
        "payload": {
          "columns": ["name", "email"],
          "slice": [{"field": "email", "op": "!=", "value": ""}],
          "limit": 5
        }
      }
    }
  }'
```

### 实际结果

```json
{
  "items": [{}, {}, {}],
  "schema": {"columns": [{"name": "Name"}, {"name": "Email"}]},
  "pagination": {"returned": 3, "totalCount": 3}
}
```

items 全部为空字典 `{}`。SQL 正确执行并返回了 3 行数据（pagination 确认），但 `filter_response_columns` 把所有列移除了。

### 期望结果

```json
{
  "items": [
    {"Name": "Administrator", "Email": "a***@example.com"},
    {"Name": "OdooBot", "Email": "o***@example.com"},
    {"Name": "Foggy UI Walkthrough Partner", "Email": "f***@example.test"}
  ]
}
```

## 根因分析

### 数据流

```
1. 引擎构建 SQL:
   SELECT t.name AS "Name", t.email AS "Email" FROM res_partner ...

2. 数据库返回 rows:
   [{"Name": "Admin", "Email": "admin@example.com"}, ...]

3. from_legacy(data=rows, columns_info=[
     {"name": "Name", "fieldName": "name"},
     {"name": "Email", "fieldName": "email"},
   ])
   → response.items = [{"Name": "Admin", "Email": "admin@example.com"}]

4. filter_response_columns(items, field_access):
   visible_set = {"name", "email", ...}  ← QM field names
   keep rule: k in visible_set
   "Name" in {"name", "email"} → False ❌ (case + format mismatch)
   "Email" in {"name", "email"} → False ❌
   → items = [{}]  ← 全部列被移除

5. apply_masking(items, field_access):
   masking = {"email": email_mask_fn}
   "email" in {} → False ← 已经没有列了
   → 掩码无法执行
```

### 问题代码位置

**`field_validator.py` L297-307**：

```python
visible_set = set(field_access.visible)  # {"name", "email", ...} — QM field names
return [
    {k: v for k, v in row.items() if k in visible_set}  # k = "Name", "Email" — display names
    for row in items
]
```

**`masking.py` L110-113**：

```python
for field_name, mask_fn in resolved.items():  # field_name = "email" — QM field name
    if field_name in row:  # row keys = {"Name": ..., "Email": ...} — display names
        row[field_name] = mask_fn(row[field_name])
```

### 关键信息：`columns_info` 已包含映射关系

`service.py` 的 `_build_columns()` 在构建 `columns_info` 时已经记录了 `fieldName`（QM 名）和 `name`（display 名）的映射：

```python
columns_info.append({
    "name": label,          # "Email" — display name (= SQL alias = items key)
    "fieldName": dim_name,  # "email" — QM field name (= field_access key)
    ...
})
```

这个映射在 `SemanticQueryResponse.schema_info.columns` 中可用。

## 建议修复方案

### 方案 A：在 filter/masking 前构建反查映射（推荐）

在 `service.py` 的 `query_model()` 中，执行 filter/masking 前从 `build_result.columns` 构建 `display_name → qm_field_name` 映射：

```python
# 在 filter_response_columns / apply_masking 之前
if field_access is not None:
    # 构建 display_name → qm_field_name 映射
    display_to_qm = {}
    for col in build_result.columns:
        display_name = col.get("name", "")
        qm_name = col.get("fieldName", "")
        if display_name and qm_name:
            display_to_qm[display_name] = qm_name

    if field_access.visible:
        response.items = filter_response_columns(
            response.items, field_access, display_to_qm=display_to_qm
        )
    if field_access.masking:
        apply_masking(
            response.items, field_access, display_to_qm=display_to_qm
        )
```

`filter_response_columns` 改为：

```python
def filter_response_columns(items, field_access, display_to_qm=None):
    visible_set = set(field_access.visible)
    return [
        {k: v for k, v in row.items()
         if (display_to_qm or {}).get(k, k) in visible_set}
        for row in items
    ]
```

`apply_masking` 改为用 display name 查找 masking rule：

```python
def apply_masking(items, field_access, display_to_qm=None):
    # 构建 display_name → mask_fn 映射
    resolved = {}
    for field_name, mask_type in field_access.masking.items():
        resolved[field_name] = _MASK_FUNCS.get(mask_type, _mask_full)

    qm_to_display = {v: k for k, v in (display_to_qm or {}).items()}

    for row in items:
        for qm_name, mask_fn in resolved.items():
            display_name = qm_to_display.get(qm_name, qm_name)
            if display_name in row:
                row[display_name] = mask_fn(row[display_name])
```

### 方案 B：引擎返回 items 时使用 QM field name 作为 key

修改 `from_legacy()` 或 executor 返回逻辑，让 items 的 key 使用 QM field name 而非 display name。但此方案影响面大（所有消费者都依赖当前 display name key），**不推荐**。

## 影响评估

| 功能 | 影响 |
|------|------|
| blocked 字段查询拦截（pre-query validation） | ✅ **不受影响**（在 SQL 执行前校验，使用 QM field name） |
| blocked 字段 metadata 过滤 | ✅ **不受影响**（metadata 过滤在 `get_metadata_v3_markdown` 层面，使用 QM field name 匹配字段定义） |
| 查询结果列过滤（post-query） | ❌ **失效**（本 BUG） |
| 查询结果脱敏（post-query） | ❌ **失效**（本 BUG） |

## 相关文件

| 文件 | 位置 |
|------|------|
| `field_validator.py` | `src/foggy/dataset_model/semantic/field_validator.py` L283-307 |
| `masking.py` | `src/foggy/dataset_model/semantic/masking.py` L88-115 |
| `service.py` （调用点） | `src/foggy/dataset_model/semantic/service.py` L288-294 |
| `service.py` （columns_info 构建） | `src/foggy/dataset_model/semantic/service.py` L329-388 |

## 测试建议

修复后需要补充/更新以下测试用例（`tests/test_column_governance.py`）：

1. `filter_response_columns` 在 items key 为 display name 时正确按 visible 过滤
2. `apply_masking` 在 items key 为 display name 时正确执行掩码
3. 集成测试：查询带 fieldAccess 参数时，返回结果包含 visible 列且 masked 列被掩码
