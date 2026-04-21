---
acceptance_scope: feature
version: v1.4
target: P2-fsscript-in-notin算子对齐Java
doc_role: acceptance-record
doc_purpose: 说明本文件用于功能级正式验收与签收结论记录
status: signed-off
decision: accepted
signed_off_by: execution-agent
signed_off_at: 2026-04-20
reviewed_by: foggy-test-coverage-audit
blocking_items: []
follow_up_required: no
evidence_count: 5
---

# Feature Acceptance

## Document Purpose

- doc_type: acceptance
- intended_for: signoff-owner / reviewer / owning-module
- purpose: 记录 Python 侧 fsscript `v in (...)` / `v not in (...)` 算子对齐 Java 8.1.11.beta 的功能级正式验收结论

## Background

- Version: v1.4
- Target: fsscript 表达式层新增 SQL 风格 `in` / `not in` 成员测试算子
- Owner: `foggy-data-mcp-bridge-python` / `foggy.fsscript` 子模块
- Goal: 让 Python fsscript 在语法（parser）和语义（evaluator）两层都支持 Java 已交付的 `v in (1, 2, 3)` / `v not in (1, 2, 3)`，保证同一份 QM/TM 表达式在 Java / Python 两端可执行出同一结果

## Acceptance Basis

- requirement: `docs/v1.4/P2-fsscript-in-notin算子对齐Java-需求.md`
- progress: `docs/v1.4/P2-fsscript-in-notin算子对齐Java-progress.md`
- coverage audit: `docs/v1.5/coverage/v1.4+v1.5-coverage-audit.md`
- Java 上游参照：`foggy-data-mcp-bridge/foggy-fsscript/src/main/java/com/foggyframework/fsscript/fun/IN.java` + `NOT_IN.java`
- Java 上游需求：`foggy-data-mcp-bridge/docs/8.1.11.beta/P2-fsscript支持in和not-in算子-需求.md`

## Checklist

- [x] scope 内功能点已全部交付
  - Parser：`TokenType.IN` 挂入 `op_map`、`NOT IN` 双 token lookahead、`_parse_in_rhs` 处理 `(a, b, c)` / `[a, b, c]` / 表达式
  - AST：`BinaryOperator.IN` / `NOT_IN` 枚举
  - Evaluator：`_check_in` / `_loose_equal` / `_to_haystack` helper，实现 null / 数值归一 / bool 护栏语义
- [x] 原始 acceptance criteria 已逐项覆盖
  - 主语法 `v in (1,2,3)` / `v not in (1,2,3)` ✅
  - 数组字面量 `[1,2,3]` ✅
  - 变量 / dict / set / tuple RHS ✅
  - null / 空集合语义 ✅
  - 数值归一（int/float/Decimal）✅
  - Python 特有 bool 护栏 ✅
  - 字符串 haystack 子串语义 ✅
  - 尾随逗号 ✅
  - for-in / instanceof / == / && / 前缀 not 零回归 ✅
- [x] 关键测试已通过
  - `tests/test_fsscript/test_in_operator.py`：60 passed
  - fsscript 子集全量回归：509 passed（449 基线 + 60 新增）
  - 全量回归（v1.4 当时阶段）：1821 → 1905 passed, 0 failed
- [x] 体验验证：`N/A` —— 纯语法引擎增强，无 UI 交互面；QM/TM 作者在 .qm/.tm 文件中书写表达式即可受益
- [x] 文档、配置、依赖项已闭环
  - requirement 和 progress 文档完整
  - 进度标记全部 `[x]`
  - 契约对照表回写 progress 文档

## Evidence

- Requirement:
  - `docs/v1.4/P2-fsscript-in-notin算子对齐Java-需求.md`
- Test:
  - `tests/test_fsscript/test_in_operator.py`（60 用例，覆盖 9 个测试类）
  - `docs/v1.5/coverage/v1.4+v1.5-coverage-audit.md` Coverage Matrix 的 R1.1–R1.12 行
- Experience:
  - `N/A`（见 Checklist）
- Artifact:
  - Python 源码改动：`src/foggy/fsscript/expressions/operators.py`（+130 行）、`src/foggy/fsscript/parser/parser.py`（+76 行）
  - 契约对齐对照表：progress 文档"契约对齐证据"章节（Java `IN.java` / `NOT_IN.java` ↔ Python `_check_in` 行级映射）

## Failed Items

- none

## Risks / Open Items

- **DSL 下推**（fsscript `in` → DSL `list` 算子的 query planner 下推）不在本需求范围；progress 已显式声明延后。非阻断，不影响本次验收。
- **Java 侧自身单元测试未齐**：Java 需求文档的 Progress Tracking 仍显示 `[ ]`（Java 代码已实现，测试未补齐）。Python 侧独立完成，不阻塞；跟进由 Java owner 负责。

## Final Decision

- 结论：**accepted**
- 所有 scope-in 功能点、acceptance criteria 已完整交付
- 60 个单元测试 + fsscript 全量 509 通过 + 整仓 1905 通过均为 0 failed
- 契约对齐 Java 的 `IN.java` / `NOT_IN.java` 语义（含 null / Number / Map.keySet / singleton），Python 侧另外加 bool 护栏（Python 特有陷阱）
- 无阻断项；无需跟进

## Signoff Marker

- acceptance_status: signed-off
- acceptance_decision: accepted
- signed_off_by: execution-agent
- signed_off_at: 2026-04-20
- acceptance_record: docs/v1.4/acceptance/P2-fsscript-in-notin算子对齐Java-acceptance.md
- blocking_items: none
- follow_up_required: no
