# P0 — v1.2 列治理引擎侧（Python）— Progress

## 基本信息

- 目标版本：`v1.2`
- 需求等级：`P0`
- 状态：`Stage 0 + Stage 1 已完成`
- 责任项目：`foggy-data-mcp-bridge-python`
- 上游需求：`docs/v1.2/P0-column-governance-engine-需求.md`
- 开始日期：2026-04-07
- 完成日期：2026-04-07

## Development Progress

### Stage 0 — SPI/DTO 冻结

#### Step 0.1 新增 FieldAccessDef + SystemSlice DTO

- 状态：✅ 已完成
- 文件：`src/foggy/mcp_spi/semantic.py`
- `FieldAccessDef`：`visible: List[str]` + `masking: Dict[str, str]`
- `SystemSlice`：`slices: List[Any]`

#### Step 0.2 扩展 SemanticMetadataRequest

- 状态：✅ 已完成
- 新增字段：`visible_fields: Optional[List[str]] = Field(None, alias="visibleFields")`

#### Step 0.3 扩展 SemanticQueryRequest

- 状态：✅ 已完成
- 新增字段：`field_access: Optional[FieldAccessDef] = Field(None, alias="fieldAccess")`
- 新增字段：`system_slice: Optional[List[Any]] = Field(None, alias="systemSlice")`

#### Step 0.4 同步 vendored SPI

- 状态：✅ 已完成
- diff 结果：`Files are identical`
- 目标：`foggy-odoo-bridge-pro/foggy_mcp_pro/lib/foggy/mcp_spi/semantic.py`

### Stage 1 — Python 引擎实现

#### Step 1.1 LocalDatasetAccessor 透传

- 状态：✅ 已完成
- `build_query_request()` 从 payload 提取 `fieldAccess` → `FieldAccessDef` + `systemSlice`
- 向后兼容：不传时 `field_access=None`, `system_slice=None`

#### Step 1.2 field_validator.py（新建）

- 状态：✅ 已完成
- 文件：`src/foggy/dataset_model/semantic/field_validator.py`
- 表达式解析：支持 bare field / `dim$caption` / `sum(field) as alias` / `field as alias`
- alias 回溯：`_build_alias_map()` → orderBy alias 自动回溯到源字段
- visible 校验：columns / slice / orderBy / calculatedFields 全覆盖
- 结果裁剪：`filter_response_columns()` 移除非 visible 的 key

#### Step 1.3 masking.py（新建）

- 状态：✅ 已完成
- 文件：`src/foggy/dataset_model/semantic/masking.py`
- full_mask：`***`
- partial_mask：`张**`
- email_mask：`z***@example.com`
- phone_mask：`138****5678`
- 未知 mask type 降级为 full_mask（防泄漏）

#### Step 1.4 SemanticQueryService.query_model() 增强

- 状态：✅ 已完成
- 字段校验集成：query 执行前 validate_field_access()，blocked → 返回错误
- 结果裁剪：执行后 filter_response_columns() 移除非 visible key
- system_slice 合并：`request.system_slice` 追加到 `request.slice`，绕过 visible 校验
- masking：执行后 apply_masking() 对 visible 但需脱敏的字段执行掩码

#### Step 1.5 metadata 过滤

- 状态：✅ 已完成
- `get_metadata_v3(visible_fields=)`：在返回前按 `visible_set` 过滤 `fields` dict
- `get_metadata_v3_markdown(visible_fields=)`：`_build_single_model_markdown` + `_build_multi_model_markdown` 按 `visible_set` 过滤各 section
- `describe_model_internal` 不受 visible_fields 影响（系统内部通道）

#### Step 1.6 MCP RPC 路由层透传

- 状态：✅ 已完成
- `dataset.get_metadata` 工具从 `tool_args` 提取 `visibleFields` 传给 metadata 方法
- `dataset.query_model` 工具通过 `build_query_request()` 自动提取 `fieldAccess` + `systemSlice`

## Testing Progress

| # | 用例 | 结果 |
|---|------|------|
| 1 | 现有 fast tests 无回归 | ✅ 1599 passed |
| 2 | FieldAccessDef DTO 可导入 + JSON round-trip | ✅ |
| 3 | SystemSlice DTO 可导入 | ✅ |
| 4 | SemanticQueryRequest 向后兼容（不传 field_access → None） | ✅ |
| 5 | SemanticQueryRequest.field_access JSON alias = fieldAccess | ✅ |
| 6 | build_query_request 从 payload 提取 fieldAccess/systemSlice | ✅ |
| 7 | 不传 field_access 时 query_model 行为与 v1.1 一致 | ✅ |
| 8 | visible_fields 过滤 get_metadata_v3 JSON | ✅ |
| 9 | visible_fields 过滤 get_metadata_v3_markdown（single + multi） | ✅ |
| 10 | blocked 字段在 columns → 返回明确错误 | ✅ |
| 11 | blocked 字段在 slice → 返回明确错误 | ✅ |
| 12 | blocked 字段在 orderBy → 返回明确错误 | ✅ |
| 13 | orderBy alias 回溯到源字段校验 | ✅ |
| 14 | system_slice 中的字段不受 visible 约束 | ✅ (via service merge) |
| 15 | 表达式字段提取（bare / dim$suffix / agg(f) as alias） | ✅ (12 个用例) |
| 16 | masking 执行正确（full/partial/email/phone + 未知类型降级） | ✅ (4+1 种) |
| 17 | vendored SPI 一致性 diff | ✅ identical |
| — | 新增列治理测试合计 | ✅ **59 passed** |
| — | 全量测试合计 | ✅ **1658 passed** |

## 计划外变更

无

## 阻塞项

无

## 后续衔接

| 后续项 | 状态 |
|--------|------|
| Stage 2: Odoo Bridge 治理决策 | 可开始（依赖本 Stage 0+1 已就绪） |
| Stage 3: 脱敏配置 UI | 待 Stage 2 |
| Stage 4: 导出治理 | 待 Stage 3 |
| Java 引擎对齐 | v1.2 follow-up |
