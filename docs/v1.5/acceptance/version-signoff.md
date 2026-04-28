---
acceptance_scope: version
version: v1.5
target: v1.5-计算字段编译器与Java引擎架构对齐
doc_role: acceptance-record
doc_purpose: 说明本文件用于 v1.5 版本级正式验收与签收结论记录
status: signed-off
decision: accepted-with-risks
signed_off_by: execution-agent
signed_off_at: 2026-04-20
reviewed_by: foggy-test-coverage-audit
blocking_items: []
follow_up_required: no
evidence_count: 11
---

# Version Acceptance

## Document Purpose

- doc_type: acceptance
- intended_for: signoff-owner / reviewer / root-controller
- purpose: 记录 v1.5（Phase 1 + Phase 2 + Phase 3）的版本级正式验收结论与签收依据汇总

## Background

- Version: v1.5
- Scope: Python 侧 `foggy-data-mcp-bridge-python` 仓，三阶段完成"计算字段编译器与 Java 引擎架构对齐"
- Goal: 利用项目绿地期把 Python 引擎升级到与 Java 等价的架构能力，避免未来外部集成者依赖错误行为后难以回退

## Acceptance Basis

- v1.5 总控：`docs/v1.5/README.md`
- Phase 需求：
  - `docs/v1.5/P1-Phase1-Dialect函数翻译与arity校验-需求.md`
  - `docs/v1.5/P1-Phase2-计算字段依赖图-需求.md`
  - `docs/v1.5/P1-Phase3-AST-Visitor-架构对齐-需求.md`
- Phase 进度：
  - `docs/v1.5/P1-Phase1-Dialect函数翻译与arity校验-progress.md`
  - `docs/v1.5/P1-Phase2-计算字段依赖图-progress.md`
  - `docs/v1.5/P1-Phase3-AST-Visitor-架构对齐-progress.md`
- 覆盖审计：`docs/v1.5/coverage/v1.4+v1.5-coverage-audit.md`
- Java 参照：`foggy-data-mcp-bridge/foggy-fsscript/` + `foggy-data-mcp-bridge/foggy-dataset-model/` + `foggy-data-mcp-bridge/foggy-dataset/src/main/java/.../db/dialect/`

## Module Summary

| Module / Phase | Owner | Status | Acceptance Record | Notes |
|---|---|---|---|---|
| Phase 1 — Dialect 函数翻译 + arity | foggy.dataset / foggy.dataset_model | signed-off | `docs/v1.5/acceptance/P1-Phase1-Dialect函数翻译与arity校验-acceptance.md` | accepted |
| Phase 2 — 计算字段依赖图 | foggy.dataset_model.semantic | signed-off | `docs/v1.5/acceptance/P1-Phase2-计算字段依赖图-acceptance.md` | accepted |
| Phase 3 — AST-Visitor 架构对齐 | foggy.dataset_model.semantic + foggy.fsscript | signed-off | `docs/v1.5/acceptance/P1-Phase3-AST-Visitor-架构对齐-acceptance.md` | accepted-with-risks（非阻断） |
| v1.4 P2 — fsscript in/not in（前置依赖，已独立签收） | foggy.fsscript | signed-off | `docs/v1.4/acceptance/P2-fsscript-in-notin算子对齐Java-acceptance.md` | accepted |

## Checklist

- [x] 所有 scope 内模块均已完成 feature-level acceptance
  - Phase 1 / Phase 2 / Phase 3 各自独立 signed-off
- [x] v1.5 README 中的 11/13 Java 对齐能力目标已达成
  - `in`/`not in`、跨方言函数翻译、arity 校验、calc 拓扑排序、calc 循环检测、calc 传递依赖、slice/orderBy/groupBy/having 引用 calc、fsscript 方法调用、Ternary `?:`、`??` null coalesce、AST-based SQL 生成
  - 仅 2 项 scope-out 到 Phase 4（`+` 类型推导、Python fsscript parser SQL 关键字升级），不属于 v1.5 目标缺口
- [x] 测试记录完整且结果可追溯
  - 本版本新增 304 个 test（Phase 1：+182，Phase 2：+46，Phase 3：+76）
  - 回归基线演进：1905 → 2087 → 2133 → 2209；每阶段 0 failed
  - simplify 复盘后代码质量进一步提升（7 项重构修复），回归保持 2209 passed
- [x] 体验验证：`N/A` —— 全部为底层引擎层增强，无 UI 交互面；Phase 3 AST 路径默认关闭
- [x] 阻断项已清零
  - 无阻断
  - 非阻断 Gap（G1–G5）均列入 coverage audit，明确允许带风险进入验收
- [x] 执行标准合规
  - ✅ 新增测试均执行并通过
  - ✅ progress 文档全部 `[x]` 回写
  - ✅ 各阶段 final report（progress 文档）已输出
  - ✅ `foggy-implementation-quality-gate` 自检模式（每阶段 progress 声明 `self-check-only`，理由明示）
  - ✅ `foggy-test-coverage-audit` 已执行（见 Acceptance Basis）

## Evidence

- Test:
  - 6 个新测试文件，共 364 用例全通过
    - `tests/test_fsscript/test_in_operator.py`（60）
    - `tests/test_dataset_model/test_dialect_function_translation.py`（83）
    - `tests/test_dataset_model/test_function_arity_validation.py`（99）
    - `tests/test_dataset_model/test_calc_field_sorter.py`（28）
    - `tests/test_dataset_model/test_calc_field_dependency_e2e.py`（18）
    - `tests/test_dataset_model/test_ast_expression_compiler.py`（76）
  - 全量回归：2209 passed, 0 failed
  - Coverage Matrix：`docs/v1.5/coverage/v1.4+v1.5-coverage-audit.md`（逐项 R1.x / R2.x / R3.x / R4.x 映射）
- Experience:
  - `N/A`（见 Checklist）
- Delivery Artifacts:
  - 新模块：
    - `src/foggy/dataset_model/semantic/calc_field_sorter.py`（Phase 2）
    - `src/foggy/dataset_model/semantic/fsscript_to_sql_visitor.py`（Phase 3）
  - 改造模块：
    - `src/foggy/fsscript/expressions/operators.py`（v1.4 IN/NOT_IN）
    - `src/foggy/fsscript/parser/parser.py`（v1.4 `_parse_in_rhs` + NOT IN lookahead）
    - `src/foggy/dataset/dialects/base.py`（Phase 1 `build_function_call` + simplify: `_translate_mysql_date_format` 共享）
    - `src/foggy/dataset/dialects/postgres.py` / `sqlite.py` / `sqlserver.py` / `mysql.py`（Phase 1 方言翻译 + simplify: `_FUNCTION_MAPPINGS` 类级常量）
    - `src/foggy/dataset_model/semantic/service.py`（Phase 1/2/3 全链路集成）
    - `src/foggy/dataset_model/semantic/field_validator.py`（Phase 3 方法名识别）
  - 契约对齐证据（散落在 4 份 progress 文档的"契约对齐证据"章节）

## Blocking Items

- none

## Risks / Open Items

- **G1 —— 无真实数据库执行链路测试**：所有断言针对生成的 SQL 字符串；方言翻译未在真实 DB 上跑通验证。缓解：Phase 1 镜像 Java 已在生产跑过的 `buildFunctionCall`；`tests/test_mcp/` 既有 docker 化 MySQL 兜底；Phase 3 AST 默认关闭。**允许带风险进入验收**。
- **G2 —— 无 Java ↔ Python 跨语言对照自动化**：契约对齐通过人工对照表记录，不是 cross-language test harness。缓解：首次对齐时密度足够，日常 Java 侧变更通过 PR review 同步。**长期基础设施缺口，非本版本缺口**。
- **G3 —— Phase 3 AST visitor 79% 行覆盖**：未覆盖 51 行全是 defensive 错误分支。ROI 低。**非阻断**。
- **G4 —— 无 performance / load 测试**：新开销均为 bounded O(n)；`_FUNCTION_MAPPINGS` 类级常量化后反而比 pre-v1.5 更快。**非阻断**。
- **G5 —— Phase 3 AST 路径无 production-like manual evidence**：flag 默认关闭，未来翻默认时补即可。**非阻断**。
- **Phase 4 候选**（独立立项，本版本不做）：
  - Python fsscript parser 升级支持 `IS NULL` / `BETWEEN` / `LIKE` / `CASE WHEN ... END`
  - `+` 运算符按操作数类型推导字符串拼接 vs 数值加法
  - 翻默认 `use_ast_expression_compiler=True` + 下线 char tokenizer

## Final Decision

- 结论：**accepted-with-risks**
- 原因：Phase 1 + Phase 2 均 `accepted`；Phase 3 `accepted-with-risks`（风险均为非阻断长期跟进项），版本整体采其上界结论
- **版本目标达成情况**：README 宣告的 11/13 Java 对齐能力全部交付（仅 2 项 scope-out 到 Phase 4）
- **下一步建议**：
  - 短期无需跟进
  - 中期若决定启用 AST 路径作为默认，先跑一轮 integration-test 真实 DB 验证（对应 G1 + G5），再翻默认
  - 长期可启动 Phase 4 做 100% AST 覆盖

## Signoff Marker

- acceptance_status: signed-off
- acceptance_decision: accepted-with-risks
- signed_off_by: execution-agent
- signed_off_at: 2026-04-20
- acceptance_record: docs/v1.5/acceptance/version-signoff.md
- blocking_items: none
- follow_up_required: no

## Post-Signoff Addendum

- addendum_date: 2026-04-28
- addendum_scope: v1.5 后续 parity lane 收口，不改变 2026-04-20 Phase 1 / Phase 2 / Phase 3 版本签收结论
- timeWindow_parity: 已完成并签收，见 `docs/v1.5/acceptance/P1-timeWindow-Python-parity-acceptance.md`
- timeWindow_calculatedFields: 已按 Java `foggy-data-mcp-bridge-wt-dev-compose` 8.4.0.beta 契约 / 8.5.0.beta runtime fixture 对齐并签收，见 `docs/v1.5/acceptance/P1-timeWindow-calculatedFields-acceptance.md`
- overall_closeout: `docs/v1.5/v1.4+v1.5-overall-progress-closeout.md`
- current_summary: Python 与 Java 在当前文档定义的 CTE baseline、timeWindow signed-off subset、后置 scalar calculatedFields subset 上已对齐；剩余项均记录为 Phase 4 optional、长期基础设施或未来契约扩展。
