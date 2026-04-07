# P0 — v1.2 列治理引擎侧（Python）— Implementation Plan

## 基本信息

- 目标版本：`v1.2`
- 需求等级：`P0`
- 责任项目：`foggy-data-mcp-bridge-python`
- 上游需求：`P0-column-governance-engine-support-需求.md`
- Code Inventory：`P0-column-governance-engine-support-code-inventory.md`

## 实施步骤（8 Steps）

### Step 1. 新增 FieldAccessDef + SystemSlice DTO

- 文件：`src/foggy/mcp_spi/semantic.py`
- 操作：在 `SemanticMetadataRequest` 之前新增 `FieldAccessDef(BaseModel)` + `SystemSlice(BaseModel)`
- `FieldAccessDef.visible: List[str]` — 可见字段白名单
- `FieldAccessDef.masking: Dict[str, str]` — 字段 → 脱敏类型映射
- `SystemSlice.slices: List[Any]` — 系统注入的行级过滤
- 均使用 `Field(default_factory=list/dict)` 确保默认值安全

### Step 2. 扩展 SemanticMetadataRequest + SemanticQueryRequest

- 文件：`src/foggy/mcp_spi/semantic.py`
- `SemanticMetadataRequest` 增加 `visible_fields: Optional[List[str]] = Field(None, alias="visibleFields")`
- `SemanticQueryRequest` 增加：
  - `field_access: Optional[FieldAccessDef] = Field(None, alias="fieldAccess")`
  - `system_slice: Optional[List[Any]] = Field(None, alias="systemSlice")`
- 向后兼容：所有新字段默认 None

### Step 3. 新建 field_validator.py

- 文件：`src/foggy/dataset_model/semantic/field_validator.py`（新建）
- 核心函数：
  - `extract_field_from_expr(expr)` — 解析 `sum(field) as alias` 等表达式，提取裸字段
  - `_build_alias_map(columns)` — 从 columns 列表构建 alias → source 映射
  - `_extract_fields_from_slice(slice_items)` — 递归提取 slice 中引用的字段
  - `validate_field_access(columns, slice_items, order_by, calculated_fields, field_access)` → `FieldValidationResult`
  - `filter_response_columns(items, field_access)` — 从结果行中移除非 visible 字段
- 表达式解析覆盖：bare field / `dim$suffix` / `agg(field) as alias` / `field as alias`
- orderBy alias 回溯：通过 `_build_alias_map` 将 alias 映射回源字段再校验

### Step 4. 新建 masking.py

- 文件：`src/foggy/dataset_model/semantic/masking.py`（新建）
- 核心函数：`apply_masking(items, field_access)` — 就地修改行数据
- 4 种 mask 函数：`_mask_full` / `_mask_partial` / `_mask_email` / `_mask_phone`
- 未知 mask type 降级为 `full_mask`（防泄漏原则）

### Step 5. 集成 SemanticQueryService.query_model()

- 文件：`src/foggy/dataset_model/semantic/service.py`
- 新增导入 `FieldAccessDef` / `validate_field_access` / `filter_response_columns` / `apply_masking`
- 在 `query_model()` 中：
  1. **query 前**：从 `request.field_access` 提取 visible 列表，调用 `validate_field_access()` 校验 columns/slice/orderBy
  2. **system_slice 合并**：`request.system_slice` 追加到 `request.slice`，使用 `model_copy(update=...)` 避免修改原始对象
  3. **query 后**：`filter_response_columns()` 裁剪非 visible key
  4. **masking**：`apply_masking()` 对需脱敏字段执行掩码

### Step 6. 集成 metadata 过滤

- 文件：`src/foggy/dataset_model/semantic/service.py`
- `get_metadata_v3(visible_fields=)` — 在返回前按 `visible_set` 过滤 `fields` dict
- `get_metadata_v3_markdown(visible_fields=)` — 传入 `visible_set` 到 `_build_single_model_markdown` + `_build_multi_model_markdown`
- 两个 private builder 增加 `visible_set: Optional[set]` 参数，内部使用 `_visible(field_name)` helper 过滤各 section
- `describe_model_internal` 不受 visible_fields 影响（不传参数）

### Step 7. 更新 Accessor + MCP RPC 路由

- `src/foggy/mcp_spi/accessor.py` — `build_query_request()` 从 payload 提取 `fieldAccess` 构建 `FieldAccessDef`、提取 `systemSlice`
- `src/foggy/mcp/routers/mcp_rpc.py` — `dataset.get_metadata` 工具从 `tool_args` 提取 `visibleFields` 传给 metadata 方法

### Step 8. 同步 vendored SPI

- 将更新后的 `src/foggy/mcp_spi/semantic.py` 复制到 `foggy-odoo-bridge-pro/foggy_mcp_pro/lib/foggy/mcp_spi/semantic.py`
- `diff` 确认两份文件完全一致

## 向后兼容保障

- 所有新参数 `Optional`，默认 `None`
- `None` 时代码路径完全跳过治理逻辑，行为与 v1.1 一致
- 现有测试套件必须全量通过无回归

## 依赖关系

```
Step 1-2 (SPI DTO) → Step 3-4 (新模块) → Step 5-6 (集成) → Step 7 (路由) → Step 8 (sync)
```

Step 3 和 Step 4 可并行。Step 5 和 Step 6 可并行。
