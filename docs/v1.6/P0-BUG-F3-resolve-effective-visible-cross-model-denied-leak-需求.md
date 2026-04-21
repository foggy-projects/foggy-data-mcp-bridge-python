---
type: bug-fix-requirement
version: v1.6
req_id: P0-BUG-F3
status: draft
priority: P0
severity: major
discovered_at: 2026-04-20
discovered_during: REQ-FORMULA-EXTEND M5 Step 5.5 (vendored sync to foggy-odoo-bridge-pro)
upstream_bug_report: foggy-odoo-bridge-pro/docs/prompts/v1.4/workitems/BUG-v14-metadata-v3-denied-columns-cross-model-leak.md
v1_4_acceptance_followup_id: F-3
blocking_for:
  - foggy-data-mcp-bridge docs/8.2.0.beta (Compose Query)
  - foggy-odoo-bridge-pro docs/prompts/v1.6/P0-01-compose-query-embedded-authority-resolver
---

# P0-BUG-F3：`_resolve_effective_visible` 跨模型 denied QM 字段全局并集泄漏修复

## 基本信息

- 目标版本：`v1.6`
- 需求等级：`P0`
- 严重级别：`major`
- BUG 类型：`correctness / security`
- 来源：v1.4 REQ-FORMULA-EXTEND M5 Step 5.5 签收遗留 Follow-up F-3；同时是 8.2.0.beta Compose Query 的 blocking 前置依赖
- 下游 blocker 影响：
  - `foggy-data-mcp-bridge` 8.2.0.beta `script` 工具无法安全发布多模型场景
  - `foggy-odoo-bridge-pro` v1.6 `OdooEmbeddedAuthorityResolver` 集成验收无法进行

## 背景

v1.3 引入 `deniedColumns` 物理列黑名单机制后，`SemanticQueryService` 的 metadata 输出（`get_metadata_v3` / `get_metadata_v3_markdown`）会按列权限对字段清单做裁剪。当前实现 `_resolve_effective_visible` 在多模型同时暴露时产生了字段可见性的跨模型泄漏：**任何一个模型被 deny 的 QM 字段，如果其他模型存在同名 QM 字段，会被一并剥离。**

在单模型消费场景（如早期单 DSL 查询）下这不会被感知，但在以下场景里会直接观察到：

- `get_metadata_v3(model_names=[A, B])` 同时返回多个模型
- Compose Query（`script` 工具）多模型脚本的 schema 推导
- Odoo Pro 接入 `OdooEmbeddedAuthorityResolver` 后的字段可见性回传

## 现象复现

### 测试用例（来自 Odoo Pro 仓，fast lane）

```python
# tests/test_v13_semantic_service_regression.py::test_metadata_keeps_shared_field_for_visible_models
service = SemanticQueryService()
service.register_model(_make_model("SaleModel", "sale_order"))       # 有 name / amountTotal / company
service.register_model(_make_model("PartnerModel", "res_partner"))   # 有 name / amountTotal / company

metadata = service.get_metadata_v3(
    model_names=["SaleModel", "PartnerModel"],
    denied_columns=[DeniedColumn(table="sale_order", column="name")],
)

# 期望：
#   - "name" 仍在 metadata["fields"]
#   - metadata["fields"]["name"]["models"] == {"PartnerModel": {"description": "name"}}
# 实际：
#   - "name" 整体从 metadata["fields"] 消失
```

当前状态：Odoo Pro 仓用 `@pytest.mark.xfail(strict=False)` 守护，等本 BUG 修复后撤 xfail。

## 根因分析

### 阶段 1：per-model 翻译是正确的

`PhysicalColumnMapping.to_denied_qm_fields`（`src/foggy/dataset_model/semantic/physical_column_mapping.py:76-89`）：

```python
def to_denied_qm_fields(self, denied_columns: List[DeniedColumn]) -> Set[str]:
    denied: Set[str] = set()
    for dc in denied_columns:
        if not dc.table or not dc.column:
            continue
        key = f"{dc.table}.{dc.column}"         # table + column 组合 key
        qm_fields = self.physical_to_qm.get(key, [])
        denied.update(qm_fields)
    return denied
```

对输入 `DeniedColumn(table="sale_order", column="name")`：

- SaleModel 的 `physical_to_qm` 含 `"sale_order.name" -> ["name"]` → 返回 `{"name"}` ✓
- PartnerModel 的 `physical_to_qm` 不含 `"sale_order.name"` → 返回 `set()` ✓

### 阶段 2：BUG 在"跨模型合并"

`SemanticQueryService._resolve_effective_visible`（`src/foggy/dataset_model/semantic/service.py:371-403`）：

```python
all_denied_qm: set = set()
all_qm: set = set()
for name in model_names:
    mapping = self.get_physical_column_mapping(name)
    if mapping:
        all_denied_qm.update(mapping.to_denied_qm_fields(denied_columns))  # ← 扁平合并
        all_qm.update(mapping.get_all_qm_field_names())

if effective is not None:
    effective -= all_denied_qm
else:
    effective = all_qm - all_denied_qm                                      # ← 全局扣减
```

- SaleModel 贡献 `{"name"}` 到 `all_denied_qm`
- PartnerModel 贡献 `{}`
- 合并后 `all_denied_qm = {"name"}`，**model 归属信息被扁平化丢弃**
- 扣减时 `all_qm - all_denied_qm` 把属于 PartnerModel 的 `name` 也当成 SaleModel 的 `name` 一并剥离

### 结构性定性

这不是边界条件问题，是**数据结构选择错误**：
- per-model mapping 已经正确地把"模型归属"编码在 `physical_to_qm` 的 key 里
- 但返回类型 `Set[str]` 把这个归属压平成"QM 字段名"这一个维度
- 后续合并再次损失信息
- 任何依赖"某字段是哪个模型的"的下游，都会被这个扁平化破坏

## 修复目标

- `_resolve_effective_visible` 返回值从 `Optional[set]` 升级为 `Optional[Dict[str, Set[str]]]`，key=model name，value=该模型的 effective visible QM 字段集
- 所有调用点（`get_metadata_v3` / `get_metadata_v3_markdown` / `_build_single_model_markdown` / `_build_multi_model_markdown`）同步改造，按各自 model name 取对应 set
- `visible_fields` 白名单仍保持"跨模型共享白名单"语义（无论哪个模型，都先经过 `visible_fields` 过滤），只对 deny 阶段做 per-model 裁剪
- 保证 `None` 返回语义不变：所有调用点在 `None` 时不做裁剪

## 非目标

- 不重新设计 `DeniedColumn` 数据结构（保持 `{table, column}`）
- 不改 `PhysicalColumnMapping.to_denied_qm_fields` 的签名与语义（它本来就是 per-model 的）
- 不改 `visible_fields` / `denied_columns` 的入参契约
- 不调整 `get_metadata_v3` / markdown 的外部响应结构（只修正被错误剥离的字段能正确回来）

## 修复方案

### 1. `_resolve_effective_visible` 签名与实现

```python
def _resolve_effective_visible(
    self,
    model_names: List[str],
    visible_fields: Optional[List[str]],
    denied_columns: Optional[List['DeniedColumn']],
) -> Optional[Dict[str, Set[str]]]:
    """Compute per-model effective visible QM fields.

    Returns:
        - None when no governance applies (both visible_fields and denied_columns absent)
        - Dict[model_name, Set[qm_field]] otherwise; absent model keys mean "no mapping,
          caller should treat as if governance does not apply for that model"
    """
    if visible_fields is None and not denied_columns:
        return None

    visible_base: Optional[Set[str]] = set(visible_fields) if visible_fields is not None else None

    per_model: Dict[str, Set[str]] = {}
    for name in model_names:
        mapping = self.get_physical_column_mapping(name)
        if mapping is None:
            # No mapping → downstream will fall back to "no trimming" for this model
            continue

        model_all_qm: Set[str] = mapping.get_all_qm_field_names()
        model_denied: Set[str] = (
            mapping.to_denied_qm_fields(denied_columns) if denied_columns else set()
        )

        if visible_base is not None:
            model_effective = set(visible_base) - model_denied
        else:
            model_effective = model_all_qm - model_denied

        per_model[name] = model_effective

    return per_model
```

### 2. 调用点改造

#### `get_metadata_v3` (service.py:~2254)

```python
# before
effective_visible = self._resolve_effective_visible(target_models, visible_fields, denied_columns)
if effective_visible is not None:
    fields = {k: v for k, v in fields.items() if k in effective_visible}

# after
per_model_effective = self._resolve_effective_visible(target_models, visible_fields, denied_columns)
if per_model_effective is not None:
    # fields[field_name]["models"] 是 Dict[model_name, info]
    # 按模型分别裁剪；若某模型没有 mapping（不在 per_model_effective），视为该模型不受本次治理影响
    filtered_fields: Dict[str, Any] = {}
    for field_name, field_info in fields.items():
        models_of_field: Dict[str, Any] = field_info.get("models", {})
        kept_models: Dict[str, Any] = {}
        for model_name, model_info in models_of_field.items():
            effective = per_model_effective.get(model_name)
            if effective is None:
                # 该模型无 mapping → 不裁剪
                kept_models[model_name] = model_info
            elif field_name in effective:
                kept_models[model_name] = model_info
        if kept_models:
            # 字段至少在一个模型里可见
            new_info = dict(field_info)
            new_info["models"] = kept_models
            filtered_fields[field_name] = new_info
    fields = filtered_fields
```

#### `get_metadata_v3_markdown` (service.py:~2302)

同上，把"扁平 visible_set 按字段名判断"改为"按 model 分组后，每个 model 自己判断"。单模型 markdown 路径也要按 `per_model_effective.get(target_name)` 取对应 set。

#### 其他调用点

通过 `grep _resolve_effective_visible` 定位全部调用点，确保无遗漏：

```
src/foggy/dataset_model/semantic/service.py:2254
src/foggy/dataset_model/semantic/service.py:2302
```

（本需求实现时必须重新 grep 确认，不能依赖此快照）

### 3. 并发与性能

- per-model 裁剪不引入额外 DB 查询，只是对内存中已有 mapping 的多做一层遍历
- 复杂度从 `O(|fields| * |models|)` 变为 `O(|fields| * |models_per_field|)`，实际相等
- 不做缓存；mapping 本身已按模型加载一次

## 测试计划

### 1. 新增/复活的失败用例（必须转绿）

对齐 Odoo Pro 侧 xfail 用例，本仓新建 `tests/test_metadata_v3_cross_model_governance.py`：

```python
def test_denied_on_one_model_does_not_strip_shared_field_from_another():
    """F-3 regression: DeniedColumn(table='sale_order', column='name') must NOT
    strip PartnerModel.name (which maps to res_partner.name).
    """
    service = SemanticQueryService()
    service.register_model(_make_model("SaleModel", "sale_order"))
    service.register_model(_make_model("PartnerModel", "res_partner"))

    metadata = service.get_metadata_v3(
        model_names=["SaleModel", "PartnerModel"],
        denied_columns=[DeniedColumn(table="sale_order", column="name")],
    )

    name_entry = metadata["fields"].get("name")
    assert name_entry is not None, "name must stay in fields"
    assert set(name_entry["models"].keys()) == {"PartnerModel"}, (
        "only PartnerModel should retain name; SaleModel is denied"
    )
```

### 2. 新增正向用例

| 用例 | 输入 | 期望 |
|---|---|---|
| `shared_field_both_allowed` | `denied_columns=[]`，两模型共享 `name` | 两模型都保留 `name` |
| `denied_on_both_models` | 两条 deny 分别命中两模型的各自物理表 | 两模型的共享 QM 字段都被剥离 |
| `shared_field_partial_deny` | 只 deny 一个模型的物理列 | 只有该模型的 QM 字段被剥离，其他模型保留 |
| `visible_fields_whitelist` | `visible_fields=['name']` + 任一模型 deny `name` | 被 deny 的模型不出现 `name`；其他模型保留 |
| `no_mapping_model` | 某模型未注册 `PhysicalColumnMapping` | 该模型不受治理，字段完整保留 |
| `empty_model_names` | `model_names=[]` | 返回空 metadata；不抛异常 |

### 3. 回归测试

- 跑 `pytest -q`，基线从 v1.5 签收的 **2420 passed / 1 skipped** 推进到 `2420+N`（N ≥ 新增用例数），无 failed
- 跑 `tests/integration/_sql_normalizer.py` + `test_formula_parity.py`（M5 Step 5.1 parity），不回归
- 跑 `tests/test_formula_security.py`（M5 Step 5.3 security），不回归

### 4. 上游 Odoo Pro 联调

- 本修复合并后，通知 Odoo Pro 仓：
  - 把 `tests/test_v13_semantic_service_regression.py::test_metadata_keeps_shared_field_for_visible_models` 的 `@pytest.mark.xfail(strict=False)` 撤除
  - 跑 Odoo Pro fast lane，确认 `510 passed + 1 xfailed` → `511 passed + 0 xfailed`
  - 对齐提交记录（对应 root CLAUDE.md 的"对齐提交"栏位）

## Java 侧同步修复要求

v1.4 REQ-FORMULA-EXTEND M5 是 Python / Java 双端对齐做的，Java 侧 `SemanticServiceV3Impl` 存在等价实现。Java 侧有两种可能：

1. 已是 per-model 正确实现（Python 侧扁平是回归）→ 本修复仅需 Python 侧
2. 同样是扁平合并（未覆盖到 cross-model deny 场景）→ Java 侧必须同步修复

**判定方法**：在本需求实施阶段，先由执行方 grep `foggy-data-mcp-bridge/foggy-dataset-model/src/main/java/.../SemanticServiceV3Impl.java` 中 `resolveEffectiveVisible` 或等价方法，确认其返回形态是否按模型分组。

**两种情形下的交付路径**：

- Java 已正确：仅 Python 侧修复；本需求 `java_sync_required = no`
- Java 需同步：本需求 `java_sync_required = yes`，需在 `foggy-data-mcp-bridge` 仓起对应修复工单（版本目录 `docs/8.1.11.beta` 或 `docs/8.2.0.beta` 按当前可提交版本决定）；两仓修复在同一周期内落地，避免 parity 回归

无论哪种情形，本仓发布前必须跑一次 `FormulaParitySnapshotTest` 基线（Java 41 parity 条目），确认与 Python 侧结果一致。

## 修复文件清单

| 文件 | 角色 | 变更 |
|---|---|---|
| `src/foggy/dataset_model/semantic/service.py` | `_resolve_effective_visible` + 2 个调用点 | update |
| `src/foggy/dataset_model/semantic/physical_column_mapping.py` | `to_denied_qm_fields` | **do-not-touch** |
| `tests/test_metadata_v3_cross_model_governance.py` | 新增 F-3 回归测试 + 正向用例集 | create |
| `tests/test_metadata_v3.py`（如已存在） | 现有 metadata 测试 | `read-only-verify`（确保既有断言不回归） |
| `docs/v1.6/P0-BUG-F3-...-progress.md` | 进度骨架 | create |
| `docs/v1.6/acceptance/P0-BUG-F3-...-acceptance.md` | 签收记录 | create（修复完成后） |

## 验收标准

### 功能验收

- `test_denied_on_one_model_does_not_strip_shared_field_from_another` 通过
- 上表 6 条新增正向用例全部通过
- 现有 2420 passed 基线不回归（允许增加，不允许减少或 failed）
- `FormulaParitySnapshotTest` 41 parity 条目不回归

### 下游验收

- Odoo Pro 仓 `tests/test_v13_semantic_service_regression.py::test_metadata_keeps_shared_field_for_visible_models` xfail 撤除后通过
- Odoo Pro fast lane 从 `510 passed + 1 xfailed` 推进到 `511 passed + 0 xfailed`
- root CLAUDE.md v1.4 签收条目下的 F-3 状态升格为 `resolved` 或 `fixed-in-v1.6`

### 文档验收

- 本需求文档 status 更新为 `completed`
- `docs/v1.6/acceptance/` 下产出签收记录，含：测试结果、对齐提交 SHA、下游撤 xfail 的 Odoo Pro 对齐提交 SHA
- 通知 8.2.0.beta 主仓该前置依赖已清零（`foggy-data-mcp-bridge/docs/8.2.0.beta/*` 三份文档的"前置依赖"章节状态从 `blocking` 改为 `resolved`）

## 风险与缓解

### R1：其他调用点未被发现

- 风险：`_resolve_effective_visible` 可能在非 metadata 路径被间接调用，变更签名时遗漏
- 缓解：实施时 grep 全仓 + 跑完整 2420+ 测试基线

### R2：API 返回形态意外变化

- 风险：`fields[name]["models"]` 的裁剪逻辑改写后，可能把原本应保留的模型也误过滤
- 缓解：
  - 新增 `no_mapping_model` 用例（该模型视为不受治理，完整保留）
  - 保留 `kept_models` 非空判断（字段在任一模型可见就保留字段项本身）

### R3：Java 侧漂移

- 风险：Python 修了，Java 没修，parity test 开始失败；或反之
- 缓解：见"Java 侧同步修复要求"；两仓同周期落地

### R4：Odoo Pro vendored lib 漂移

- 风险：Odoo Pro 的 `foggy_mcp_pro/lib/foggy/` 是 vendored 的 Python lib，修复后需要重新 vendored sync
- 缓解：本需求完成后，Odoo Pro 仓需执行一次 vendored sync 并更新 `v1.4-vendored-sync-acceptance.md`

## 交付节奏

1. 根因与修复方案评审（本文档签收）
2. 实现 + 测试补齐 + 本仓回归通过
3. Java 侧 grep 判定 + 必要时同步修复
4. Parity baseline 双端核对
5. 下游 Odoo Pro 撤 xfail 并 vendored sync
6. 签收记录入 `docs/v1.6/acceptance/`
7. 通知 root CLAUDE.md 更新 F-3 状态
