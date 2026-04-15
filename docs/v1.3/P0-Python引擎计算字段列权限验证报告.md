# P0 - Python 引擎计算字段列权限验证报告

## 文档作用

- doc_type: `verification-report`
- intended_for: `engine-owner | execution-agent | reviewer`
- purpose: 将 workspace root 的 Python 引擎验证结论下放到 `foggy-data-mcp-bridge-python`，作为本仓库后续能力整改的直接输入

## 基本信息

- 目标版本：`v1.3`
- 优先级：`P0`
- 状态：`resolved`
- 责任项目：`foggy-data-mcp-bridge-python`
- 上游目标文档：`docs/v1.3/P0-引擎计算字段列权限能力整改目标-需求.md`（workspace root）
- 上游验证报告：`docs/v1.3/python-engine-calculated-field-permission-verification.md`（workspace root）

## 结论

- 结论：**支持**（v1.3 整改后）
- 适用范围：
  - 支持 metadata `visibleFields` / `visible_fields` 字段裁剪
  - 支持普通字段、内联聚合字段 `sum(field) as alias`、以及 `calculated_fields` 的源字段权限校验
  - 支持对结果列做 visible/filter + masking
  - ✅ 支持对 DSL 内联表达式 `a + b as c` 做按源字段依赖拆解的权限判断
  - ✅ 支持对 `sum(a + b) as total` 做按源字段依赖拆解的权限判断
  - ✅ `orderBy` 对 alias 回溯到表达式依赖字段的权限判断已有完整证据
  - `orderBy` / `filter` 中直接写表达式的场景作为 P1 后续
- 残余风险点：
  - `orderBy` / `filter` 中直接写表达式（非 alias 回溯）的依赖提取尚未覆盖（P1）
  - `_EXPR_KEYWORDS` 关键词表可能遗漏罕见 SQL 函数名，但遗漏方向是 fail-closed（安全）

## 问题定义

本报告验证 `foggy-data-mcp-bridge-python` 引擎侧是否真的支持以下能力：

1. metadata / describe_model / get_metadata 场景下的字段裁剪
2. query_model / DSL 执行时的列权限校验
3. 计算字段依赖源列权限的正确处理
4. 重点场景：
   - QM 预定义计算字段
   - DSL 内联表达式 `a + b as c`
   - 聚合表达式 `sum(a + b) as total`
   - 只在 `orderBy` / `filter` 中引用计算表达式

## 代码链路

### 1. metadata / visibleFields

- [semantic.py](D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/src/foggy/mcp_spi/semantic.py)
  - `SemanticMetadataRequest.visible_fields = Field(..., alias="visibleFields")`
- [service.py](D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/src/foggy/dataset_model/semantic/service.py)
  - `get_metadata_v3(..., visible_fields=...)`
  - `get_metadata_v3_markdown(..., visible_fields=...)`
  - 返回前按 `visible_fields` 过滤 `fields`

### 2. query_model / fieldAccess

- [semantic.py](D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/src/foggy/mcp_spi/semantic.py)
  - `FieldAccessDef`
  - `SemanticQueryRequest.field_access = Field(..., alias="fieldAccess")`
- [service.py](D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/src/foggy/dataset_model/semantic/service.py)
  - `query_model()` 中先调用 `validate_field_access(...)`
  - 查询后调用 `filter_response_columns(...)` 和 `apply_masking(...)`

### 3. 计算字段 / 内联表达式（v1.3 升级）

- [field_validator.py](D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/src/foggy/dataset_model/semantic/field_validator.py)
  - `_extract_field_dependencies(expr)` — **v1.3 新增**，共享依赖提取原语
    - 剥离字符串字面量 → token 提取 → 过滤 `_EXPR_KEYWORDS`
    - 单一来源，被 `_parse_column_expr()` 和 `_extract_fields_from_calculated()` 共同调用
  - `_parse_column_expr()` — **v1.3 升级**
    - `_ColumnExpr` 增加 `source_fields: Set[str]` 字段
    - 对 `a + b as c`：提取 `source_fields = {a, b}`（不再把 `a + b` 当成伪字段名）
    - 对 `sum(a + b) as total`：提取 `source_fields = {a, b}`
  - `validate_field_access()` — **v1.3 升级**
    - columns 校验按 `source_fields` 集合逐个判定
    - orderBy alias 回溯到 `alias_deps` 依赖字段集合
    - 无可提取字段的表达式 fail-closed
  - `_extract_fields_from_calculated()` — **v1.3 重构**
    - 内部 token 提取逻辑委托给 `_extract_field_dependencies()`

## 已有测试证据

### 测试文件

- [test_column_governance.py](D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/tests/test_column_governance.py)
- [test_inline_expression.py](D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/tests/test_dataset_model/test_inline_expression.py)
- [test_window_functions.py](D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/tests/test_dataset_model/test_window_functions.py)

### v1.3 新增 / 改写测试

在 [test_column_governance.py](D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-python/tests/test_column_governance.py) 中：

**依赖提取单元测试（`TestExtractFieldDependencies` + `TestExtractFieldDependenciesPublic`，14 个）**

1. `test_bare_field` — `"name"` → `{"name"}`
2. `test_dimension_accessor` — `"partner$caption"` → `{"partner$caption"}`
3. `test_arithmetic` — `"a + b"` → `{"a", "b"}`
4. `test_multiply` — `"unitPrice * quantity"` → `{"unitPrice", "quantity"}`
5. `test_case_when` — 提取 `status`, `amount`；不含 `case`, `when`
6. `test_agg_wrapper` — `"sum(a + b)"` → `{"a", "b"}`
7. `test_string_literal_stripped` — `'active'` 不被提取
8. `test_no_fields` — `"1 + 2"` → `set()`
9. `test_empty` — `""` → `set()`
10. `test_nested_function` — `"round(a / b, 2)"` → `{"a", "b"}`
11. `test_bare_field` (public API)
12. `test_arithmetic_with_alias` (public API) — `"a + b as c"` → `{"a", "b"}`
13. `test_agg_over_expression_with_alias` (public API) — `"sum(a + b) as total"` → `{"a", "b"}`
14. `test_simple_agg` (public API) — `"sum(amount) as total"` → `{"amount"}`

**服务级依赖感知测试（`TestServiceLevelCalculatedFieldGovernance`，改写 2 个 + 新增 7 个）**

1. `test_calculated_fields_rejects_blocked_source_field` — 保留（已有）
2. `test_inline_arithmetic_expression_rejects_blocked_dependency` — **改写**：断言 `"discountAmount" in error`，不含整段表达式
3. `test_inline_aggregate_expression_rejects_blocked_dependency` — **改写**：断言 `"discountAmount" in error`
4. `test_inline_arithmetic_all_visible_passes` — **新增**：两字段均可见 → 查询通过
5. `test_inline_aggregate_all_visible_passes` — **新增**：两字段均可见 → 查询通过
6. `test_orderby_alias_backtrack_to_expression_blocked` — **新增**：orderBy alias 回溯到表达式依赖
7. `test_orderby_alias_backtrack_to_expression_passes` — **新增**：alias 回溯 + 全部可见 → 通过
8. `test_accessor_payload_expression_rejection` — **新增**：JSON payload → accessor → service 全链路
9. `test_unparseable_expression_fails_closed` — **新增**：`"1 + 2"` 无字段 → fail-closed

### 实际运行命令

```powershell
pytest tests/test_column_governance.py -q -vv
```

```powershell
pytest tests/test_column_governance.py tests/test_dataset_model/test_inline_expression.py tests/test_dataset_model/test_window_functions.py -q
```

```powershell
pytest --tb=short -q
```

### 测试结果摘要

- column governance 单文件：`90 passed in 0.30s`
- 三文件相关测试：`122 passed in 0.23s`
- 全量测试：`1693 passed in 2.50s`

## 分类型结论

### 1. QM 预定义计算字段

- 结论：**支持**
- 证据：
  - `_extract_fields_from_calculated()` 委托 `_extract_field_dependencies()` 做 token 提取
  - `test_calculated_fields_rejects_blocked_source_field` 证明 blocked source field 被正确拒绝

### 2. 查询时 DSL 内联表达式 `a + b as c`

- 结论：**✅ 支持**（v1.3 整改后）
- 说明：
  - `_parse_column_expr()` 对 `a + b as c` 提取 `source_fields = {a, b}`
  - 错误信息报告具体被禁字段（如 `"discountAmount"`），不再把 `a + b` 当作伪字段名
- 证据：
  - `test_inline_arithmetic_expression_rejects_blocked_dependency` — 断言 `"discountAmount" in error`
  - `test_inline_arithmetic_all_visible_passes` — 两字段均可见时查询通过

### 3. 聚合表达式 `sum(a + b) as total`

- 结论：**✅ 支持**（v1.3 整改后）
- 说明：
  - `sum(a + b)` 不匹配简单聚合正则，走 alias 路径 → `_extract_field_dependencies("sum(a + b)")` = `{a, b}`
  - 错误信息报告具体被禁字段
- 证据：
  - `test_inline_aggregate_expression_rejects_blocked_dependency`
  - `test_inline_aggregate_all_visible_passes`

### 4. orderBy / filter 中引用计算表达式

- alias 回溯场景：**✅ 支持**
  - `validate_field_access()` 构建 `alias_deps` 映射，orderBy alias 回溯到表达式的依赖字段集合
  - `test_orderby_alias_backtrack_to_expression_blocked` / `_passes` 已证明
- 直接表达式场景：**P1 后续**
  - 当前 orderBy / filter 中直接写表达式（非 alias）的依赖提取未覆盖
  - 这不是当前真实业务场景的需求

## 验收口径对齐

对照上游 `P0-引擎计算字段列权限能力整改目标-需求.md` 的验收标准：

1. ✅ 真实代码链路存在（`_extract_field_dependencies` → `_parse_column_expr` → `validate_field_access`）
2. ✅ 单元测试覆盖：预定义计算字段、`a + b as c`、`sum(a + b) as total`、orderBy alias 回溯
3. ✅ 至少一条集成链路测试（`test_accessor_payload_expression_rejection`：JSON payload → accessor → service → rejection）
4. ✅ 失败断言证明依赖字段级判定（`"discountAmount" in error`），不是整段表达式当伪字段名
5. ✅ 无法解析依赖的表达式 fail-closed（`test_unparseable_expression_fails_closed`）

## 是否可以支撑 `odoo-bridge-pro` 按 `field.groups` 落地列权限

- 结论：**可以支撑已验证范围内的表达式**

可依赖范围：

1. 普通 QM 字段
2. `calculated_fields` 表达式
3. 内联聚合：`sum(field) as alias`
4. ✅ 内联算术：`a + b as c`
5. ✅ 复杂聚合：`sum(a + b) as total`
6. ✅ orderBy alias 回溯到表达式依赖

P1 后续补充范围：

1. orderBy / filter 中直接写表达式（非 alias 回溯）
2. slice 中表达式类 field 值的依赖提取

## 关联文档

- [P0-引擎计算字段列权限能力整改目标-需求.md](D:/foggy-projects/foggy-data-mcp/docs/v1.3/P0-引擎计算字段列权限能力整改目标-需求.md)
- [python-engine-calculated-field-permission-verification.md](D:/foggy-projects/foggy-data-mcp/docs/v1.3/python-engine-calculated-field-permission-verification.md)
