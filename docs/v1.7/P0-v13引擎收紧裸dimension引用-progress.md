---
type: progress
version: v1.7
req_id: P0-v13-bare-dimension-tightening
status: ready-for-review
priority: P0
blocking_for: []
java_sync_required: yes  # 同步在 Java 8.4.0.beta
python_side_status: ready-for-review  # M2 + M4 + M6 + M7 ready-for-review · 2026-04-28
java_side_status: not-started
odoo_pro_side_status: not-started
acceptance_record: docs/v1.7/acceptance/P0-v13-bare-dimension-tightening-acceptance.md  # M11 落盘
accepted_at: null
---

# P0 v1.3 引擎收紧裸 dimension 引用 — Progress

> 状态口径：`not-started` / `in-design` / `in-progress` / `blocked` / `ready-for-review` / `accepted` / `rejected`

## 里程碑

| # | 阶段 | 状态 | 日期 | 备注 |
|---|------|------|------|------|
| M0 | 需求立项 | `completed` | 2026-04-28 | 本需求文档落盘 + backlog B-03 抬升 |
| M1 | 跨端行为审计 + 行为对照表 | `python-completed` | 2026-04-28 | Python 已实测（见需求文档"当前行为审计"）；Java 列待 M3.1 补完 |
| M2 | Python 端 `_build_query` + `resolve_field` 收紧 | `completed` | 2026-04-28 | M2.1 `parse_column_with_alias` 落盘 ✓ / M2.2 `_build_query` 列循环改造（calc-field passthrough · 严格 resolve · fail-loud + hint）✓ / M2.3 `resolve_field_strict` 实装 ✓ |
| M3 | Java 端 `findJdbcQueryColumnByName` + `SemanticQueryServiceV3Impl` 列循环收紧 | `not-started` | — | M3.1 实测 / M3.2 列循环改造 / M3.3 调用点同步 |
| M4 | 新增 Python 单测（T1-T10） | `completed` | 2026-04-28 | `tests/test_dataset_model/test_strict_column_resolution.py` · **10/10 passed** · 覆盖拒绝路径（T1/T2/T6）+ 接受路径（T3-T5/T7-T9）+ user alias 修复（T4 ★）+ F5 flatten（T10）|
| M5 | 新增 Java 单测（T1-T10 镜像） | `not-started` | — | `SemanticQueryServiceV3StrictColumnResolutionTest.java` |
| M6 | 历史 fixture / 测试 grep 全仓 + 批量迁移 | `python-completed` | 2026-04-28 | Python 端：~46 个测试文件 / 390+ substitutions（混合迁移：dim→`$caption` + 撤回 synthetic 路径 + 兼容修复）；同步补 `field_validator._check_field` 白名单 suffix-strip + visible-set 双向归一化 |
| M7 | Python 全仓回归（期望 3202+N passed） | `completed` | 2026-04-28 | **`pytest -q` 3223 passed / 1 skipped / 1 xfailed**（baseline 3202 → 3223 净增 21；T1-T10 + calc-field passthrough 恢复 + 治理路径迁移）|
| M8 | Java sqlite lane 全量回归（期望 1809+N passed） | `not-started` | — | `mvn test -pl foggy-dataset-model -Dspring.profiles.active=sqlite` |
| M9 | Odoo Pro vendored sync + fast lane 全量回归 | `not-started` | — | `python sync_foggy_vendored.py --check`；fast lane 期望 570+ passed |
| M10 | 跨端 parity 双端核对（A3） | `not-started` | — | 同 input 双端等价错误 / SQL；F4/F5 路由不破坏 |
| M11 | 签收记录 `docs/v1.7/acceptance/` | `not-started` | — | 标准 acceptance 文档 + evidence 列表 |
| M12 | 通知 root `CLAUDE.md` + backlog `B-03` 关闭 | `not-started` | — | 升级到"已解决的问题"区块；backlog README 状态改 `resolved` |

## 前置条件检查

| 项 | 状态 | 备注 |
|----|------|------|
| G5 F5 双端实施完成 | ✅ | PR-J1/J2/P1/P2 已落盘 |
| backlog B-03 立项 | ✅ | 已抬升至 v1.7 / 8.4.0.beta |
| 用户决策 Path A 严格化 | ✅ | 2026-04-28 用户确认 |
| 用户决策双端目标版本 | ✅ | Python v1.7 + Java 8.4.0.beta |

## 测试覆盖要求（最小集）

### 单测（Python）

- T1-T10 见需求文档"测试计划 · 新增 Python 单测"

### 单测（Java）

- T1-T10 镜像（demo 模型字段替换为 `product$id` / `product$caption` / `salesAmount`）

### 集成测试回归

- Python：G5 F5 集成测试（`tests/compose/compilation/test_f5_integration.py`）零回归
- Java：`F5ColumnObjectIntegrationTest`、`EcommerceTestSupport` 系列零回归
- Odoo Pro embedded：fast lane 零回归

### Experience 验证

- experience: **N/A**（本改造为引擎层错误处理收紧，无 UI 交互；纯后端 / 纯 API）

## 跨仓影响清单

| 仓 | 路径 | 处理方式 |
|----|------|---------|
| `foggy-data-mcp-bridge-python` | `src/foggy/dataset_model/semantic/service.py` + `src/foggy/dataset_model/impl/model/__init__.py` + `tests/**` | M2 + M4 + M6 + M7 |
| `foggy-data-mcp-bridge` (Java worktree `dev-compose`) | `foggy-dataset-model/src/main/java/com/foggyframework/dataset/db/model/semantic/service/impl/SemanticQueryServiceV3Impl.java` + 调用点 + `src/test/java/**` | M3 + M5 + M6 + M8 |
| `foggy-odoo-bridge-pro` | `foggy_mcp_pro/lib/foggy/...`（vendored Python lib） | M9 vendored sync + fast lane |

## 风险记录

- R1 · 内部历史测试 / fixture 大量依赖裸 dim → M6 grep 全仓 + 批量重写
- R2 · vendored Odoo Pro embedded 漂移 → M9 vendored sync 必做
- R3 · 跨端错误消息文本不一致 → A3-1 用错误码而非文本作 parity 校验维度
- R4 · `dimension$id` 在自属性 dim（如 `orderStatus`）上的语义模糊 → M2.3 明确：自属性 dim 的 `$id` 与 `$caption` 都映射到 `dim.column`，保留 `$id` 标记便于 metadata 区分

## 决策记录

- 2026-04-28：确定 Path A 严格化（用户决策）
- 2026-04-28：确定双端目标版本 Python v1.7 + Java 8.4.0.beta（用户决策）
- 2026-04-28：确定轻量交付（requirement + progress 二件套，不走完整 5 件套执行包）
- 2026-04-28：跨双端等价错误码契约对齐 hold to A3-1（用错误码而非文本作 parity）

## Self-Check 区块（Python 侧完成 · 2026-04-28）

- [x] 需求或 bug 范围按预期实现：v1.3 `_build_query` 列循环 + `resolve_field_strict` + inline parser 三处对齐 Path A 严格化
- [x] 非目标未被意外扩大：F4/F5 normalizer 未变；inline aggregate 路径未变；metadata 暴露形态未变
- [x] 改动代码路径已记录：
  - `src/foggy/dataset_model/semantic/inline_expression.py`（新增 `parse_column_with_alias`）
  - `src/foggy/dataset_model/semantic/service.py`（列循环改造 · calc-field passthrough · fail-loud + hint）
  - `src/foggy/dataset_model/impl/model/__init__.py`（新增 `resolve_field_strict`）
  - `src/foggy/dataset_model/semantic/field_validator.py`（whitelist 双向 suffix-strip · 与 Java FieldAccessPermissionStep 对齐）
- [x] 自检结论：`self-check-only`（一项治理收紧 + 测试基线零退化 · 不需要正式 quality gate）
- [x] 测试状态：**pass** · 全仓 3223 passed / 1 skipped / 1 xfailed（基线 3202 → +21 净增）
- [x] 文档 / 后续项已记录：本 progress + 需求文档；Java 端 M3-M8 待启动

## 关联文档

- 需求：`docs/v1.7/P0-v13引擎收紧裸dimension引用-需求.md`
- backlog 起源：`docs/backlog/B-03-v13-engine-bare-dimension-tightening.md`
- Java 端镜像需求：`foggy-data-mcp-bridge/docs/8.4.0.beta/P0-v13引擎收紧裸dimension引用-需求.md`
- Java 端 progress：`foggy-data-mcp-bridge/docs/8.4.0.beta/P0-v13引擎收紧裸dimension引用-progress.md`
- 上游触发：G5 PR-P2 调试期复盘（commit `cf2ba9b` → `352a8bb`）
