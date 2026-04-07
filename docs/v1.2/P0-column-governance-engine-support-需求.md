# P0 — v1.2 列治理引擎侧（Python）— 需求

## 基本信息

- 目标版本：`v1.2`
- 需求等级：`P0`
- 状态：`执行中`
- 责任项目：`foggy-data-mcp-bridge-python`
- 上游规划：`docs/v1.2/P0-column-governance-execution-plan.md`（workspace root）
- 创建日期：2026-04-07

## 需求范围

本需求覆盖总控执行规划中的 **Stage 0（SPI/DTO 冻结）** 和 **Stage 1（Python 引擎实现）**。

### Stage 0 — SPI/DTO 冻结

1. 在 `src/foggy/mcp_spi/semantic.py` 新增 `FieldAccessDef` + `SystemSlice` DTO
2. 扩展 `SemanticMetadataRequest` 增加 `visible_fields: Optional[List[str]]`
3. 扩展 `SemanticQueryRequest` 增加 `field_access: Optional[FieldAccessDef]` + `system_slice: Optional[List[Any]]`
4. 同步 vendored 到 `foggy-odoo-bridge-pro/foggy_mcp_pro/lib/foggy/mcp_spi/semantic.py`

### Stage 1 — Python 引擎实现

1. `LocalDatasetAccessor.query_model()` 透传 `field_access` + `system_slice`
2. `SemanticQueryService.query_model()` 增加字段校验 + 结果裁剪
3. `get_metadata_v3()` / `get_metadata_v3_markdown()` 增加 `visible_fields` 过滤
4. 新建 `field_validator.py`：表达式字段提取 + alias 回溯 + visible 校验
5. 新建 `masking.py`：脱敏执行（full_mask / partial_mask / email_mask / phone_mask）
6. MCP RPC 路由层透传

## SPI DTO 定义

### FieldAccessDef

```python
class FieldAccessDef(BaseModel):
    visible: List[str] = []       # 可见字段列表
    masking: Dict[str, str] = {}  # 字段 → 掩码类型
```

### SystemSlice

```python
class SystemSlice(BaseModel):
    slices: List[Any] = []
```

### SemanticMetadataRequest 扩展

```python
visible_fields: Optional[List[str]] = None  # 为 None 时返回全量
```

### SemanticQueryRequest 扩展

```python
field_access: Optional[FieldAccessDef] = Field(None, alias="fieldAccess")
system_slice: Optional[List[Any]] = Field(None, alias="systemSlice")
```

## 字段校验规则

### 表达式解析

```
"name"                      → 提取 "name"
"partner$caption"           → 提取 "partner$caption"
"sum(amountTotal) as total" → 提取 "amountTotal"
"count(name) as cnt"        → 提取 "name"
```

### 校验流程

1. 解析表达式，提取裸字段引用
2. 对提取出的裸字段做 visible_fields 校验
3. alias 不校验，只校验被引用的源字段
4. orderBy 引用 alias 时回溯到 columns 表达式提取源字段

### 校验范围

| 请求部分 | 受 visible_fields 约束 |
|----------|----------------------|
| columns | ✅ |
| slice（用户） | ✅ |
| orderBy | ✅（alias 回溯到源字段） |
| system_slice | ❌ 不受约束 |
| calculatedFields | ✅（引用的源字段） |

## 脱敏类型

| 类型 | 说明 | 示例 |
|------|------|------|
| full_mask | 完全掩码 | `***` |
| partial_mask | 部分掩码 | `张**` |
| email_mask | 邮箱掩码 | `z***@example.com` |
| phone_mask | 电话掩码 | `138****5678` |

## 向后兼容约束

- `field_access` 和 `system_slice` 均为 Optional
- 不传时行为与 v1.1 完全一致
- `describe_model_internal` 不受 `visible_fields` 影响
- 现有测试全部通过（无回归）

## 验收标准

1. 不传 field_access 时行为与 v1.1 完全一致
2. 传 `visible_fields` 时 metadata 只返回可见字段
3. 传 `field_access.visible` 时 query 校验 columns/slice/orderBy 中引用的裸字段
4. `sum(amountTotal) as total` 中的 `amountTotal` 被校验，`total` alias 不被校验
5. orderBy 引用 alias 时回溯到源字段校验
6. blocked 字段出现在 columns 中时返回明确错误
7. blocked 字段出现在用户 slice 中时返回明确错误
8. system_slice 中的字段不受 visible 约束
9. masking 执行正确（full_mask / partial_mask / email_mask / phone_mask）
10. 两份 `semantic.py`（Python SPI + Odoo vendored）完全一致
