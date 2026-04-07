# P0 — v1.2 列治理引擎侧（Python）— Execution Prompt

## 基本信息

- 目标版本：`v1.2`
- 需求等级：`P0`
- 责任项目：`foggy-data-mcp-bridge-python`
- 实施计划：`P0-column-governance-engine-support-implementation-plan.md`

## 开工提示词

```
请在 foggy-data-mcp-bridge-python 中实施 v1.2 列治理引擎支持。

实施计划在 docs/v1.2/P0-column-governance-engine-support-implementation-plan.md，
共 8 步，按顺序执行：

1. src/foggy/mcp_spi/semantic.py — 新增 FieldAccessDef / SystemSlice DTO
2. 同上 — 扩展 SemanticMetadataRequest + SemanticQueryRequest
3. src/foggy/dataset_model/semantic/field_validator.py — 新建，表达式解析 + 校验
4. src/foggy/dataset_model/semantic/masking.py — 新建，4 种脱敏
5. src/foggy/dataset_model/semantic/service.py — query_model() 集成
6. 同上 — get_metadata_v3/markdown 集成 visible_fields
7. accessor.py + mcp_rpc.py — 透传
8. vendored SPI 同步到 foggy-odoo-bridge-pro

完成后执行验收命令确认无回归。
```

## 验收命令

### 1. 全量 fast tests（无回归）

```bash
cd foggy-data-mcp-bridge-python
python -m pytest tests/ --tb=short -q --ignore=tests/odoo_agnostic --ignore=tests/integration -x
```

预期：1658+ passed，0 failed

### 2. 列治理专项测试

```bash
python -m pytest tests/test_column_governance.py -v --tb=short
```

预期：59 passed

### 3. DTO 导入验证

```bash
python -c "
from foggy.mcp_spi.semantic import FieldAccessDef, SystemSlice, SemanticQueryRequest, SemanticMetadataRequest
fa = FieldAccessDef(visible=['name'], masking={'email': 'email_mask'})
req = SemanticQueryRequest(columns=['name'], field_access=fa, system_slice=[{'field': 'x'}])
mr = SemanticMetadataRequest(visible_fields=['name'])
assert req.field_access.visible == ['name']
assert req.system_slice == [{'field': 'x'}]
assert mr.visible_fields == ['name']
print('DTO import OK')
"
```

### 4. 向后兼容验证

```bash
python -c "
from foggy.mcp_spi.semantic import SemanticQueryRequest, SemanticMetadataRequest
req = SemanticQueryRequest(columns=['name'])
assert req.field_access is None
assert req.system_slice is None
mr = SemanticMetadataRequest(model='test')
assert mr.visible_fields is None
print('Backward compat OK')
"
```

### 5. vendored SPI 一致性

```bash
diff foggy-data-mcp-bridge-python/src/foggy/mcp_spi/semantic.py foggy-odoo-bridge-pro/foggy_mcp_pro/lib/foggy/mcp_spi/semantic.py
```

预期：无差异

### 6. 脱敏功能验证

```bash
python -c "
from foggy.dataset_model.semantic.masking import apply_masking
from foggy.mcp_spi.semantic import FieldAccessDef
fa = FieldAccessDef(masking={'email': 'email_mask', 'phone': 'phone_mask', 'name': 'partial_mask', 'secret': 'full_mask'})
rows = [{'email': 'zhang@test.com', 'phone': '13812345678', 'name': '张三丰', 'secret': 'password123', 'id': 1}]
apply_masking(rows, fa)
assert rows[0]['email'] == 'z***@test.com'
assert rows[0]['phone'] == '138****5678'
assert rows[0]['name'] == '张**'
assert rows[0]['secret'] == '***'
assert rows[0]['id'] == 1
print('Masking OK')
"
```

### 7. 字段校验功能验证

```bash
python -c "
from foggy.dataset_model.semantic.field_validator import validate_field_access
from foggy.mcp_spi.semantic import FieldAccessDef
fa = FieldAccessDef(visible=['name', 'amount'])
# pass
r1 = validate_field_access(columns=['name', 'sum(amount) as total'], slice_items=[], order_by=[{'field': 'total'}], field_access=fa)
assert r1.valid, 'should pass'
# fail
r2 = validate_field_access(columns=['name', 'secretField'], slice_items=[], order_by=[], field_access=fa)
assert not r2.valid, 'should fail'
assert 'secretField' in r2.blocked_fields
print('Field validation OK')
"
```
