# P0 — v1.2 列治理引擎侧（Python）— Code Inventory

## 基本信息

- 目标版本：`v1.2`
- 需求等级：`P0`
- 责任项目：`foggy-data-mcp-bridge-python`
- 上游需求：`P0-column-governance-engine-support-需求.md`

## Stage 0 — SPI/DTO 冻结

| # | 文件路径 | 角色 | 变更类型 | 备注 |
|---|---------|------|---------|------|
| 0.1 | `src/foggy/mcp_spi/semantic.py` | SPI DTO 定义 | `update` | 新增 `FieldAccessDef` / `SystemSlice`；扩展 `SemanticMetadataRequest.visible_fields` / `SemanticQueryRequest.field_access` + `.system_slice` |
| 0.2 | `foggy-odoo-bridge-pro/.../lib/foggy/mcp_spi/semantic.py` | vendored 拷贝 | `sync` | 直接从 Python 仓复制，不手写 |

## Stage 1 — Python 引擎实现

| # | 文件路径 | 角色 | 变更类型 | 备注 |
|---|---------|------|---------|------|
| 1.1 | `src/foggy/mcp_spi/accessor.py` | Accessor 透传 | `update` | `build_query_request()` 提取 `fieldAccess` → `FieldAccessDef`、`systemSlice` |
| 1.2 | `src/foggy/dataset_model/semantic/field_validator.py` | 字段校验模块 | `create` | 表达式解析 + alias 回溯 + visible 校验 + 结果列裁剪 |
| 1.3 | `src/foggy/dataset_model/semantic/masking.py` | 脱敏执行模块 | `create` | `apply_masking()` — full/partial/email/phone mask |
| 1.4 | `src/foggy/dataset_model/semantic/service.py` | 查询引擎主类 | `update` | `query_model()` 集成校验 + 裁剪 + system_slice 合并 + 脱敏；`get_metadata_v3()` / `get_metadata_v3_markdown()` 增加 `visible_fields` 过滤 |
| 1.5 | `src/foggy/mcp/routers/mcp_rpc.py` | MCP RPC 路由 | `update` | `dataset.get_metadata` 透传 `visibleFields` |

## 测试文件

| # | 文件路径 | 角色 | 变更类型 | 备注 |
|---|---------|------|---------|------|
| T.1 | `tests/test_column_governance.py` | 列治理单元测试 | `create` | 59 个用例：DTO / 表达式解析 / 校验 / 裁剪 / 脱敏 / 向后兼容 |

## 不变更文件（read-only-analysis）

| 文件路径 | 确认结论 |
|---------|---------|
| `src/foggy/mcp/routers/semantic_v3.py` | 已有调用点，visible_fields 默认 None，无需改动 |
| `src/foggy/dataset_model/definitions/access.py` | 已有 `DbAccessDef` 列掩码字段定义，v1.2 不复用（由 Bridge 侧计算 FieldAccessDef 传入） |
