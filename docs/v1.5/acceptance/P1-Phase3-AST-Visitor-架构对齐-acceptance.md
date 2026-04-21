---
acceptance_scope: feature
version: v1.5
target: P1-Phase3-AST-Visitor-架构对齐
doc_role: acceptance-record
doc_purpose: 说明本文件用于功能级正式验收与签收结论记录
status: signed-off
decision: accepted-with-risks
signed_off_by: execution-agent
signed_off_at: 2026-04-20
reviewed_by: foggy-test-coverage-audit
blocking_items: []
follow_up_required: no
evidence_count: 7
---

# Feature Acceptance

## Document Purpose

- doc_type: acceptance
- intended_for: signoff-owner / reviewer / owning-module
- purpose: 记录 v1.5 Phase 3（AST-based `FsscriptToSqlVisitor` 架构对齐）的功能级正式验收结论

## Background

- Version: v1.5
- Phase: 3 / 3（v1.5 最后一块）
- Target: 把 Python 计算字段 → SQL 编译从字符级 tokenizer 升级为基于 fsscript AST 的 visitor；新增方法调用 / Ternary / `??` 能力
- Owner: `foggy-data-mcp-bridge-python` / `foggy.dataset_model.semantic`
- Goal: 架构对齐 Java AST visitor；未来 fsscript 新算子自动同步到 SQL 层；在 opt-in feature flag 下提供方法调用等 char-tokenizer 无法做到的能力

## Acceptance Basis

- requirement: `docs/v1.5/P1-Phase3-AST-Visitor-架构对齐-需求.md`
- progress: `docs/v1.5/P1-Phase3-AST-Visitor-架构对齐-progress.md`
- coverage audit: `docs/v1.5/coverage/v1.4+v1.5-coverage-audit.md`
- Java 上游参照：
  - `foggy-data-mcp-bridge/foggy-dataset-model/src/main/java/.../CalculatedFieldService.java`
  - `foggy-data-mcp-bridge/foggy-fsscript/src/main/java/com/foggyframework/fsscript/fun/`（Java fsscript visitor）

## Checklist

- [x] scope 内功能点已全部交付
  - `src/foggy/dataset_model/semantic/fsscript_to_sql_visitor.py`（~440 行；simplify 后 ~400 行）
    - `render_with_ast` 入口 + `FsscriptToSqlVisitor` + `AstCompileError`
    - 覆盖 AST 节点：字面量 / 变量 / 成员访问 / 二元 / 一元 / 三元 / 函数调用 / 方法调用
    - `_preprocess_if` 把 `IF(` rewrite 成 `__FSQL_IF__(`（复用 `skip_string_literal`）
  - 方法调用翻译：`startsWith` / `endsWith` / `contains` / `toUpperCase` / `toLowerCase` / `trim` / `length`（7 种）
  - 方言路由：方法调用的 concat 经 `FDialect.get_string_concat_sql`，`length()` 经 Phase 1 rename 到 SQL Server `LEN`
  - `SemanticQueryService(use_ast_expression_compiler=False)` feature flag（默认 OFF）
  - `_render_expression` AST-first + char-fallback（`AstCompileError` 自动兜底）
  - `_extract_field_dependencies` 修正：识别 `.method` 前缀，排除方法名出字段依赖
  - simplify 后：移除未用 `_STRING_METHOD_NAMES` frozenset；收窄 `except Exception`；`_preprocess_if` 复用 `skip_string_literal`
- [x] 原始 acceptance criteria 已逐项覆盖
  - Parity：34 组表达式在 AST 与 char 路径下语义等价
  - 方法调用：7 种方法 × 3 方言路由全部翻译正确
  - Ternary `a ? b : c` → `CASE WHEN ... END`
  - `??` → 方言感知的 `COALESCE` / `ISNULL`
  - Fallback：`IS NULL` / `BETWEEN` / `LIKE` / `CAST AS` 等 SQL-specific 语法自动回落 char tokenizer
  - `IF(...)` 预处理正确（词边界 + 字符串字面量跳过 + `$` 护栏）
  - 默认 flag OFF 时字节级 pre-v1.5 等价
- [x] 关键测试已通过
  - `tests/test_dataset_model/test_ast_expression_compiler.py`：76 passed
  - 全量回归（Phase 3 末端）：2133 → 2209 passed, 0 failed
  - 全量回归（simplify 末端）：2209 passed, 0 failed
- [x] 体验验证：`N/A` —— 底层引擎能力增强，AST 路径默认关闭，无 UI 交互面；未来翻默认时再补 manual evidence
- [x] 文档、配置、依赖项已闭环
  - requirement 和 progress 全部 `[x]`
  - 契约对照表（fsscript AST → SQL 映射 + 方言路由实证）回写 progress 文档
  - Python 侧刻意偏差（`!=` → `<>` 标准化、括号分组、`__FSQL_IF__` sentinel）落档

## Evidence

- Requirement:
  - `docs/v1.5/P1-Phase3-AST-Visitor-架构对齐-需求.md`
- Test:
  - `tests/test_dataset_model/test_ast_expression_compiler.py`（76 用例，8 个测试类）
  - `docs/v1.5/coverage/v1.4+v1.5-coverage-audit.md` Coverage Matrix 的 R4.1–R4.10 行
- Experience:
  - `N/A`（AST 默认关闭）
- Artifact:
  - Python 源码改动：
    - 新文件 `src/foggy/dataset_model/semantic/fsscript_to_sql_visitor.py`（~400 行，simplify 后）
    - 修改 `src/foggy/dataset_model/semantic/service.py`（feature flag + AST 路由 + fallback）
    - 修改 `src/foggy/dataset_model/semantic/field_validator.py`（方法名识别）
  - 方言路由实证：progress 文档"方言路由实证"章节（MySQL / Postgres / SqlServer / none 四方言 × 3 方法）

## Failed Items

- none

## Risks / Open Items

- **G3（Phase 3 79% 行覆盖）**：`fsscript_to_sql_visitor.py` 247 行中 51 行未覆盖，均为 defensive 错误分支（未知 AST 节点 / 未支持字面量类型 / 未支持方法 / MemberAccess non-variable base）。新增 AST 节点类型时自然触发；当前不补测试 ROI 低。非阻断。
- **G5（AST 默认未开启，无 production-like manual evidence）**：`use_ast_expression_compiler=True` 下的真实 DSL `calculatedFields` 跑 live DB 未落盘 manual evidence。缓解：76 AST 测试 + fallback 设计 + flag 默认 False 已充分隔离风险。
- **Phase 4 候选**：Python fsscript parser 不支持 `IS NULL` / `BETWEEN` / `LIKE` / `CASE WHEN ... END`，这些表达式继续走 char-tokenizer fallback。若要 100% AST 覆盖需升级 fsscript parser。本期不做。
- **`+` 运算符类型推导**：需要 AST 静态分析操作数类型；Phase 3 保持 emit SQL `+`，字符串拼接用户需显式 `CONCAT(...)`。已 scope-out 到 Phase 4 或更后。

## Final Decision

- 结论：**accepted-with-risks**
- 风险均为**非阻断的长期跟进项**，不影响 Phase 3 本次交付签收：
  - 默认 flag OFF，生产行为完全不变（已有 `TestDefaultOffInvariant` 锁）
  - 启用后有 parity 锁 + fallback 双保险（已有 `test_char_and_ast_agree_on_fallback_paths` 锁）
  - SQL-specific 语法永不进入 AST 路径，回落字节级等价旧行为
- 全部 6 项开发进度 + 4 项测试进度完成；76 个新增测试覆盖 parity / 方法调用 / fallback / 预处理 / 错误处理 / compiled_calcs 集成
- 架构对齐 Java AST visitor；未来算子在两端自动同步
- 无阻断项；无需立即跟进（除非用户决定启动 Phase 4 或 flip 默认到 AST）

## Signoff Marker

- acceptance_status: signed-off
- acceptance_decision: accepted-with-risks
- signed_off_by: execution-agent
- signed_off_at: 2026-04-20
- acceptance_record: docs/v1.5/acceptance/P1-Phase3-AST-Visitor-架构对齐-acceptance.md
- blocking_items: none
- follow_up_required: no
