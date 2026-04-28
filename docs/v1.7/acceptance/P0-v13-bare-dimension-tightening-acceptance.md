# Acceptance · v1.7 P0-v13-bare-dimension-tightening (Python)

## 文档作用

- doc_type: acceptance
- intended_for: signoff-owner / reviewer
- purpose: 记录 Python `v1.7` `P0-v13引擎收紧裸dimension引用` 的验收结论 + evidence

## 元数据

- acceptance_status: signed-off
- acceptance_decision: **accepted**
- signed_off_by: execution-agent (self-check) · awaiting user co-sign
- signed_off_at: 2026-04-28
- evidence_count: 5
- requirement_doc: `docs/v1.7/P0-v13引擎收紧裸dimension引用-需求.md`
- progress_doc: `docs/v1.7/P0-v13引擎收紧裸dimension引用-progress.md`
- commit: `59176f2`
- backlog_origin: `docs/backlog/B-03-v13-engine-bare-dimension-tightening.md`

## 验收对照（A1-A5 from 需求 §"验收标准"）

### A1 · 行为契约对齐（Python）

| Item | 预期 | 实际 | 状态 |
|------|------|------|------|
| A1-1 | 裸 `["dimension"]` 抛 `ValueError` 含 hint `"did you mean 'dim$caption'"` | T1 单测验证 ✓ | **passed** |
| A1-2 | `["dimension AS alias"]` 抛 `ValueError` 含 hint `"did you mean 'dim$caption AS alias'"` | T2 单测验证 ✓ | **passed** |
| A1-3 | `["dimension$caption AS userAlias"]` SQL 输出 `... AS "userAlias"`（不再用 TM dim.alias）| T4 ★ 关键修复单测验证 ✓ | **passed** |
| A1-4 | `["dimension$id]` / `["dimension$caption"]` / `["dimension$<custom_attr>"]` 行为不变 | T3/T5 单测 + FK-style T7 单测验证 ✓ | **passed** |
| A1-5 | `["measureName"]` / `["AGG(measure) AS alias"]` 行为不变 | T9 单测验证 + 全仓回归零 regression | **passed** |

### A2 · 行为契约对齐（Java） · cross-repo · 见 `foggy-data-mcp-bridge/docs/8.4.0.beta/acceptance/P0-v13-bare-dimension-tightening-acceptance.md`

### A3 · 跨端 parity

| Item | 预期 | 实际 | 状态 |
|------|------|------|------|
| A3-1 | 同一组输入双端等价错误 / 等价 SQL | 错误码 `COLUMN_FIELD_NOT_FOUND` 跨端一致；A2-1 实测 Java 端同 input 抛同错误码 | **passed** |
| A3-2 | F4/F5 normalizer flatten 字符串经新引擎仍能正确路由 | T10 单测验证 + G5 F5 集成测试零回归 | **passed** |

### A4 · 回归零退化

| Item | 预期 | 实际 | 状态 |
|------|------|------|------|
| A4-1 | Python `pytest -q` 维持 3202+ passed | **3223 passed / 1 skipped / 1 xfailed**（+21 净增 · 含 T1-T10 + 治理路径恢复）| **passed** |
| A4-2 | Java 1809+ passed | 由 Java 端 acceptance 承接（实测 1855 passed）| **passed** |
| A4-3 | `FormulaParitySnapshotTest` / `DialectAwareFunctionExpTest` / G5 F5 集成测试零回归 | 全仓回归通过 | **passed** |

### A5 · 影响面排查证据

| Item | 状态 | 备注 |
|------|------|------|
| A5-1 · Odoo Pro vendored sync 完成 + fast lane 全绿 | **deferred → FU**（M9）| 不阻断 v1.7 本身验收；上游 Python lib + Java JAR 落盘后单独承接 |
| A5-2 · 历史 AI Chat fixture grep 报告 + 全部用例已迁移到 `$attr` 形态 | **passed** | 46 个测试文件 / 390+ substitutions 已落盘（M6-py） |
| A5-3 · backlog `B-03` 状态置 `resolved` | **passed by M12** | 见 root CLAUDE.md / `docs/backlog/B-03-...md` |

## Evidence

1. **commit `59176f2`**：`feat(v1.7): v1.3 engine strict bare-dimension rejection (B-03 Path A · Python)`
   - 引擎改动：`inline_expression.py` / `service.py` / `impl/model/__init__.py` / `field_validator.py`
   - 测试新增：`tests/test_dataset_model/test_strict_column_resolution.py`（10 tests · all passed）
   - 修复 fixtures：~46 个测试文件 / 390+ substitutions
2. **`pytest -q` 全仓输出**：`3223 passed / 1 skipped / 1 xfailed`（与 baseline 3202 比 +21 净增 · 0 regression）
3. **T4 ★ 关键修复证据**：`test_t4_dim_caption_with_user_alias_overrides_tm_caption` SQL 输出 `t.order_status AS "userAlias"`（不再是 `"订单状态"`）
4. **跨端 parity 错误码证据**：Python 抛 `COLUMN_FIELD_NOT_FOUND`；Java 端 `4f2f48c` 已对齐到同一 errorCode
5. **影响面排查报告**：进度文档 §"跨仓影响清单"完整记录 v1.3 / v1.6 / Compose F4/F5 / Odoo Pro vendored 路径

## Final Decision

**`accepted`**

理由：
1. A1-A4 全部 passed（5 + 2 + 3 + 3 = 13 个验收项中 12 完全通过 + 1 由 Java 端 acceptance 承接）
2. A5 中仅 A5-1 deferred（Odoo Pro vendored sync · 不阻断本仓验收）
3. 测试基线提升（3202 → 3223）+ 零 regression
4. T4 user-alias 修复（B-03 § "行为 3"）已落盘并由单测锁住
5. 跨端契约（错误码 `COLUMN_FIELD_NOT_FOUND`）双端对齐

## Signoff Marker

- acceptance_status: signed-off
- acceptance_decision: accepted
- signed_off_by: execution-agent
- signed_off_at: 2026-04-28
- blocking_items: none
- follow_up_required: yes（A5-1 Odoo Pro vendored sync · 非阻断 · M9）

## 维护记录

| 日期 | 操作 | 备注 |
|------|------|------|
| 2026-04-28 | 创建 + 自检签收 | 基于 progress 自检结论 + 验收对照表 evidence；推荐 final decision **`accepted`**；A5-1 Odoo Pro vendored sync 留作 follow-up |
