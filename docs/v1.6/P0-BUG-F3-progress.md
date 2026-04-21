---
type: progress
version: v1.6
req_id: P0-BUG-F3
status: in-progress
priority: P0
blocking_for:
  - foggy-data-mcp-bridge 8.2.0.beta Compose Query
  - foggy-odoo-bridge-pro v1.6 REQ-001 OdooEmbeddedAuthorityResolver
java_sync_required: yes  # 2026-04-21 M6 grep 判定：Java 侧存在同类但不同形态的 bug
python_side_status: ready-for-review  # M2-M5 已完成 · 2430 passed / 1 skipped
---

# P0-BUG-F3 Progress

> 状态口径：`not-started` / `in-design` / `in-progress` / `blocked` / `ready-for-review` / `accepted` / `rejected`

## 里程碑

| # | 阶段 | 状态 | 日期 | 备注 |
|---|------|------|------|------|
| M0 | 需求立项 | `accepted` | 2026-04-21 | 本需求文档落盘 |
| M1 | 根因与修复方案评审 | `self-reviewed` | 2026-04-21 | 文档根因分析通过 |
| M2 | Python 侧 `_resolve_effective_visible` 改造 | `completed` | 2026-04-21 | 返回形态从 `Optional[Set]` 升级为 `Optional[Dict[str, Set]]`；保留 `visible_fields` 全局回退语义 |
| M3 | 调用点同步改造（`get_metadata_v3` + markdown builders） | `completed` | 2026-04-21 | `get_metadata_v3` 按 `fields[x]["models"]` per-model 过滤；`_build_multi_model_markdown` 新增 `per_model_visible` 参数并在模型循环内切换 `current_visible` 闭包 |
| M4 | 新增测试：F-3 回归 + 6 条正向用例 | `completed` | 2026-04-21 | `tests/test_metadata_v3_cross_model_governance.py` · 7 tests 落盘并全绿 |
| M5 | 全仓回归（期望 2420+N passed） | `completed` | 2026-04-21 | **2430 passed / 1 skipped / 4.95s**（v1.5 基线 2420 → 2430，0 failed） |
| M6 | Java 侧 grep 判定 | `completed` | 2026-04-21 | **`java_sync_required = yes`** —— Java 侧存在形态不同但症状一致的 bug：`SemanticServiceV3Impl.processModelFieldsV3` 用 `fields.put(key, freshInfo)` 且 `create*FieldInfo` 每次都新建 `models: {thisModel: ...}` 单元素 map，导致后处理模型直接**覆盖**前模型的字段条目。详见下方"M6 判定依据" |
| M7 | Java 侧同步修复 | `pending` | — | 见下方"Java 修复方案" · 预计 ~200 LOC refactor · 走独立 Java 仓 PR |
| M8 | Parity baseline 双端核对 | `pending` | — | Java 修完后跑 `FormulaParitySnapshotTest` 41 条目 + 新增多模型共享字段 parity 测试 |
| M9 | Odoo Pro 撤 xfail + vendored sync | `pending` | — | Python 侧已可撤 xfail，但需先 vendored sync；Java 侧修完再联调 |
| M10 | 签收记录 `docs/v1.6/acceptance/` | `pending` | — | |
| M11 | 通知 root CLAUDE.md F-3 状态升级为 `resolved` | `pending` | — | 待 Java M7 完成后 |
| M12 | 通知 8.2.0.beta 三份文档解除 blocking | `pending` | — | 待 M11 完成 |

## 下游依赖清单

本 BUG 修复是以下工作项的 blocking 前置：

| 下游 | 文档 | 解锁效果 |
|------|------|---------|
| `foggy-data-mcp-bridge` 8.2.0.beta | `docs/8.2.0.beta/P0-ComposeQuery-*-需求.md § 前置依赖` | 多模型脚本集成测试 + script 工具对外发布 |
| `foggy-odoo-bridge-pro` v1.6 REQ-001 | `docs/prompts/v1.6/P0-01-compose-query-embedded-authority-resolver-需求.md § 前置依赖` | `OdooEmbeddedAuthorityResolver` 多模型验收、M5 / M8 里程碑 |

## 风险记录

- R1：其他调用点漏网（实施日 grep 全仓确认）
- R2：API 返回形态意外破坏（新增 no_mapping_model 用例防护）
- R3：Java 侧漂移（M6 判定 + 必要时 M7 同步）
- R4：Odoo Pro vendored lib 漂移（M9 vendored sync 必做）

## 决策记录

- 2026-04-21：确定返回形态从 `Optional[set]` 升级为 `Optional[Dict[str, Set[str]]]`，不做兼容层
- 2026-04-21：确定 `visible_fields` 语义保持"跨模型共享白名单"，仅 deny 阶段 per-model
- 2026-04-21：确定"某模型无 mapping"时的语义：
  - 无 mapping + 有 `visible_fields`：`per_model[name] = set(visible_fields)`（保留 v1.3 全局白名单回退语义）
  - 无 mapping + 只有 `denied_columns`：不加入 dict，调用方按"不受治理"处理
- 2026-04-21：确定 Java 侧同步是否必须由 M6 grep 决定 · **M6 判定 yes**
- 2026-04-21：确定 Python 侧先行可发布，不等 Java；但 Odoo Pro 撤 xfail 需等 vendored sync，两仓 parity baseline 需等 Java M7 完成

## M6 判定依据

Java 仓文件：`D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-wt-dev-compose/foggy-dataset-model/src/main/java/com/foggyframework/dataset/db/model/semantic/service/impl/SemanticServiceV3Impl.java`

### 现象

- 第 739-872 行 `processModelFieldsV3`：按模型迭代处理 dimensions / properties / measures / calculated fields，每次调用 `fields.put(fieldName, fieldInfo)` 添加字段
- 第 878-927 行 `createDimensionIdFieldInfo` 等 5 个 `create*FieldInfo` 方法：每次都 `new LinkedHashMap<>()` 构造一个 `models` map，只 `put(modelName, modelInfo)` 当前模型
- 结果：两个模型 `ModelA` / `ModelB` 都有字段 `name$id` 时，处理完 ModelB 后 `fields["name$id"].models` 只剩 `{ModelB: ...}`

### 与 Python 的差异

| 维度 | Python（修前） | Java（当前） |
|---|---|---|
| `fields[x]["models"]` 多模型合并 | ✓ 正确（merge-into-existing） | ✗ 错误（put 覆盖整个 fieldInfo） |
| `_resolve_effective_visible` 返回形态 | ✗ 扁平 set（已修） | 不适用：Java 在 `processModelFieldsV3` 内按 per-model 做 `effectiveFieldAccess` 局部判断，没有独立的 resolve 函数 |
| 最终字段可见性 | 修前：共享字段被全局剥离 | 当前：共享字段只保留最后处理的模型 |

### Java 修复方案（M7 候选）

按严重度和修复面：

1. **必改**：`processModelFieldsV3` 第 779 / 784 / 805 / 833 / 853 / 871 行的 `fields.put(name, freshInfo)`。改为"若已存在，合并 `models` map 而非整体覆盖"：

```java
// 当前（buggy）
fields.put(idFieldName, idFieldInfo);

// 修复：合并 models 子 map，其余字段沿用首次写入的
@SuppressWarnings("unchecked")
Map<String, Object> existing = (Map<String, Object>) fields.get(idFieldName);
if (existing == null) {
    fields.put(idFieldName, idFieldInfo);
} else {
    @SuppressWarnings("unchecked")
    Map<String, Object> existingModels = (Map<String, Object>) existing.get("models");
    @SuppressWarnings("unchecked")
    Map<String, Object> newModels = (Map<String, Object>) idFieldInfo.get("models");
    existingModels.putAll(newModels);
}
```

建议抽出辅助方法 `mergeFieldInfo(fields, key, freshInfo)` 供 6 处调用复用。

2. **派生问题**：`buildJsonMetadata` 的第 103-129 行在每个模型循环内算 `effectiveFieldAccess`，并传给 `processModelFieldsV3`。如果 Model A 不 deny `name`、Model B deny `name`，两者都会把 `name` put 进 `fields`；合并修复后，Model B 因被 deny 不会 put，Model A 的 `name` 保留 —— 这是正确行为，无需额外改动

3. **Markdown 路径**（第 72-74 行 `buildMarkdownMetadata` 未接收 `deniedColumns`）：独立 bug，不属于 F-3 原始 scope，但建议同 PR 补上，否则 Odoo Pro 嵌入模式走 markdown 输出时列权限被完全忽略

### Java 新增测试建议

`SemanticServiceV3Test.java` 或新建 `MultiModelCrossDeniedTest.java`，至少覆盖：

- 两模型共享 `name$id`，无 deny → `fields.name$id.models` 包含两个 key
- 两模型共享，deny 其一 → `fields.name$id.models` 仅剩未被 deny 的那一个
- 两模型共享，deny 两者的各自物理列 → `fields.name$id` 整体消失
- Markdown 多模型 + deny → 未被 deny 的模型 `[field:...]` 行保留

测试 fixture 可参考 Python `tests/test_metadata_v3_cross_model_governance.py::_make_model`。
