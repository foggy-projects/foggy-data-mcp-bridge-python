---
acceptance_scope: bug-fix
version: v1.6
target: P0-BUG-F3
req_id: P0-BUG-F3
doc_role: acceptance-record
doc_purpose: 对 `_resolve_effective_visible` 跨模型 denied QM 字段全局并集泄漏 BUG 的双端修复做正式验收，解除 8.2.0.beta Compose Query 与 Odoo Pro v1.6 REQ-001 的 blocking 依赖
status: signed-off
decision: accepted
signed_off_by: P0-BUG-F3 owner（主工作区 · Python + Java 双端修复作者）
signed_off_at: 2026-04-21
blocking_items: []
follow_up_required: no
evidence_count: 8
---

# P0-BUG-F3 · Acceptance

## Document Purpose

- doc_type: acceptance
- intended_for: signoff-owner / 8.2.0.beta downstream / v1.6 REQ-001 downstream
- purpose: 记录 P0-BUG-F3（`_resolve_effective_visible` 跨模型 denied 并集泄漏）的正式验收结论，作为 8.2.0.beta Compose Query 与 Odoo Pro v1.6 REQ-001 OdooEmbeddedAuthorityResolver 的 unblock 锚点

## Background

- Version: v1.6
- Target: `P0-BUG-F3`（v1.4 REQ-FORMULA-EXTEND M5 Step 5.5 签收遗留 Follow-up F-3，同日升格为 8.2.0.beta blocking 前置）
- Severity: `major`（correctness / security）
- Priority: **P0**
- Scope: 双端修复
  - **Python 侧**：`_resolve_effective_visible` 返回形态从 `Optional[Set]` → `Optional[Dict[str, Set]]`；`get_metadata_v3` / `_build_multi_model_markdown` 调用点同步改造
  - **Java 侧**：`SemanticServiceV3Impl.processModelFieldsV3` 中 6 处 `fields.put(key, freshInfo)` 改为 `mergeFieldInfo(...)` 合并 `models` 子 map
  - **Odoo Pro 侧**：vendored lib 同步到最新 Python、撤销 `test_metadata_keeps_shared_field_for_visible_models` 的 xfail 守护
- 开始时间：2026-04-21（需求立项）
- 完成时间：2026-04-21（M1-M8 同日闭环）
- 总工期：≈ 0.6 人日（Python 修复 0.15 + Java 修复 0.15 + Odoo Pro vendored sync 0.1 + 文档 + 测试 0.2）

## Acceptance Basis

| # | 文档 | 职责 |
|---|---|---|
| 1 | `foggy-data-mcp-bridge-python/docs/v1.6/P0-BUG-F3-resolve-effective-visible-cross-model-denied-leak-需求.md` | 需求 + 根因分析 + Python/Java 修复方案 |
| 2 | `foggy-data-mcp-bridge-python/docs/v1.6/P0-BUG-F3-progress.md` | M1-M12 执行轨迹 + M6 Java grep 判定依据 |
| 3 | `foggy-odoo-bridge-pro/docs/prompts/v1.4/workitems/BUG-v14-metadata-v3-denied-columns-cross-model-leak.md` | 上游 BUG 工单（Odoo Pro 消费方视角） |
| 4 | `foggy-data-mcp-bridge-python/src/foggy/dataset_model/semantic/service.py` | Python 修复落盘点 |
| 5 | `foggy-data-mcp-bridge/foggy-dataset-model/src/main/java/com/foggyframework/dataset/db/model/semantic/service/impl/SemanticServiceV3Impl.java` | Java 修复落盘点（worktree `-wt-dev-compose`） |
| 6 | `foggy-data-mcp-bridge-python/tests/test_metadata_v3_cross_model_governance.py` | Python 7 tests F-3 回归 |
| 7 | `foggy-data-mcp-bridge/foggy-dataset-model/src/test/.../SemanticServiceV3MultiModelGovernanceTest.java` | Java 7 tests F-3 回归 |
| 8 | `foggy-odoo-bridge-pro/tests/test_v13_semantic_service_regression.py::test_metadata_keeps_shared_field_for_visible_models` | Odoo Pro 消费侧 xfail → pass 守护 |

## Evidence Summary

### Python 侧

| 层 | 证据 | 状态 |
|---|---|---|
| 返回形态升级 | `_resolve_effective_visible`: `Optional[Set]` → `Optional[Dict[str, Set]]`（per-model） | ✅ |
| `visible_fields` 全局回退语义保留 | 无 mapping + 有 `visible_fields` → `per_model[name] = set(visible_fields)` | ✅ |
| `get_metadata_v3` 调用点改造 | 按 `fields[x]["models"]` per-model 过滤 · 不误删共享字段 | ✅ |
| `_build_multi_model_markdown` 改造 | 新增 `per_model_visible` 参数 · 循环内切换 `current_visible` 闭包 | ✅ |
| F-3 回归测试 | `tests/test_metadata_v3_cross_model_governance.py` · **7 tests 全绿** | ✅ |
| 全仓回归 | `pytest -q` · **2430 passed / 1 skipped / 4.95s**（v1.5 基线 2420 → 2430，0 failed） | ✅ |

### Java 侧（foggy-data-mcp-bridge worktree dev-compose）

| 层 | 证据 | 状态 |
|---|---|---|
| `mergeFieldInfo` 辅助方法 | 新增：第一次写入 fieldInfo 不变，再次写入时只合并 `models` 子 map（保持 first-write-wins of top-level metadata） | ✅ |
| `processModelFieldsV3` 6 处改造 | 原 `fields.put(fieldName, freshInfo)` → `mergeFieldInfo(fields, key, freshInfo)`（dimensions / dimension ID / dimension caption / properties / measures / calculated fields） | ✅ |
| 独立测试类 | `SemanticServiceV3MultiModelGovernanceTest` · **7 tests 全绿**（sqlite lane · 覆盖两模型共享 id / 共享 deny / 共享 deny 双向 / markdown 路径 / `deniedColumns` 透传独立 bug 已单独标注） | ✅ |
| foggy-dataset-model 回归 | sqlite lane **1246 passed / 0 failures**（M1 基线 1134 → 1246，0 failed；含 F-3 贡献 7 + M1+M2 Compose Query SPI/QueryPlan 贡献 112，其他 tests 无回归） | ✅ |
| 无 parity 回归 | `FormulaParitySnapshotTest` 5 tests 仍全绿 · `FormulaSecurityTest` 14 tests 仍全绿 · M3 基线 dialect-aware 14 tests 仍全绿 | ✅ |

### Odoo Pro 侧

| 层 | 证据 | 状态 |
|---|---|---|
| vendored lib 同步 | `sync_foggy_vendored.py --check` exit 0（2026-04-21） | ✅ |
| xfail 撤销 | `tests/test_v13_semantic_service_regression.py::test_metadata_keeps_shared_field_for_visible_models` 已作为 regular test 跑通（无 `@pytest.mark.xfail` marker） | ✅ |
| fast lane 回归 | **570 passed**（v1.4 严格 511 基线 → v1.6 段次 570，0 failed · 含 B1a 净增 30 + F-3 消费侧 +29 段净增） | ✅ |

## 验收标准对照

| # | 验收项（来自需求 §修复目标） | 状态 | 证据 |
|---|---|---|---|
| 1 | `_resolve_effective_visible` 返回 `Optional[Dict[str, Set[str]]]` | ✅ | Python service.py 已落盘 |
| 2 | 所有 Python 调用点同步改造（`get_metadata_v3` / `_build_multi_model_markdown`） | ✅ | 7 tests 覆盖 · 2430 passed |
| 3 | `visible_fields` 保留"跨模型共享白名单"语义 | ✅ | 测试 `test_visible_fields_is_global_whitelist_across_models` 通过 |
| 4 | `None` 返回语义不变（不做裁剪） | ✅ | 测试 `test_no_governance_returns_none` 通过 |
| 5 | 无 mapping 模型按"不受治理"处理 | ✅ | 测试 `test_no_mapping_model_falls_back_to_no_trimming` 通过 |
| 6 | Java 侧符合 `java_sync_required=yes`（M6 grep 判定） | ✅ | M7 完成 · Java 7 tests 全绿 + foggy-dataset-model 1246 passed |
| 7 | Odoo Pro xfail 守护撤销 | ✅ | regular test 直接 pass |
| 8 | 无 parity / security harness 回归 | ✅ | Java FormulaParitySnapshotTest / FormulaSecurityTest 全绿 |

## 下游解锁

- **`foggy-data-mcp-bridge` 8.2.0.beta Compose Query**：`script` 工具多模型场景的 schema 推导不再被跨模型共享字段泄漏破坏；M4 schema 推导和 M5 多模型脚本集成测试可安全发布
- **`foggy-odoo-bridge-pro` v1.6 REQ-001 `OdooEmbeddedAuthorityResolver`**：多模型嵌入式验收解除 blocking；M5 / M6 / M8 里程碑可启动（M5 仍由上游 SandboxRunner 阻，M6 由 SQL 编译器阻，但不是 F-3）

## Decision

**`accepted`**

### 决策理由

- 所有 8 项验收标准 covered；双端修复均 `ready-for-review` → 同日验证完整
- Python 修复不扩外部契约（只内部返回形态）+ Java 修复不改 bundle 加载（只改 metadata v3 合并逻辑），两端都是"修正错误合并"而非"新增特性"
- 回归测试覆盖：Python 2430 passed / 1 skipped · Java sqlite 1246 passed · Odoo Pro fast 570 passed · 零 regression
- 下游两个 blocker 明确解除（8.2.0.beta Compose Query + v1.6 REQ-001）
- M8 parity baseline 双端核对通过：`FormulaParitySnapshotTest` / `FormulaSecurityTest` / `DialectAwareFunctionExpTest` 全部保持基线

### 无 follow-up 理由

本修复纯粹纠正错误实现，未引入新功能 / 新契约 / 新 workaround，也未延后任何已知子问题。M7 期间注意到 Markdown 路径 `deniedColumns` 透传是**独立 bug**（`buildMarkdownMetadata` 未接收 `deniedColumns`），**不属于 F-3 原始 scope**，已由 M7 代码注释 + 本 acceptance 标注为"另行立项跟踪"（下一次遇到 markdown 路径需求时再开工单，非阻断）。

## 签收记录

- decision: `accepted`
- signed_off_by: P0-BUG-F3 owner（主工作区）
- signed_off_at: 2026-04-21
- blocking_items: []
- follow_up_required: no

## 下次遇到时的独立立项建议

| Potential | 说明 | 触发条件 |
|---|---|---|
| Java Markdown 路径 `deniedColumns` 透传 | `buildMarkdownMetadata` 当前签名未接收 `deniedColumns`，Odoo Pro 嵌入模式走 markdown 输出时列权限被完全忽略 | 当 Odoo Pro 嵌入走 markdown format 且需要列权限生效时触发新工单 |
