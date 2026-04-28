# v1.5 — 计算字段编译器与 Java 引擎架构对齐

## 文档作用

- doc_type: workitem-group
- intended_for: execution-agent / reviewer
- purpose: 记录把 Python 侧计算字段 → SQL 翻译器从"字符级 tokenizer"升级为与 Java 对齐的架构的跨阶段工作包

## Acceptance Status

- acceptance_status: signed-off
- acceptance_decision: accepted-with-risks
- signed_off_by: execution-agent
- signed_off_at: 2026-04-20
- acceptance_record: docs/v1.5/acceptance/version-signoff.md
- blocking_items: none
- follow_up_required: no
- coverage_audit: docs/v1.5/coverage/v1.4+v1.5-coverage-audit.md

## 背景

v1.4 已经让 fsscript 语法层支持 `v in (...)` / `v not in (...)`，且借 SQL 原生 `IN` 语法天然在 QM/DSL 计算字段里可用。但更深的调研暴露了**结构性短板**：

| 差距 | Python（`_render_expression` 字符级 tokenizer） | Java（fsscript AST + `SqlExpFactory`） |
|---|---|---|
| 跨方言函数翻译（`DATE_FORMAT` / `YEAR` / `IFNULL`） | ❌ | ✅ `FDialect.buildFunctionCall` |
| 函数参数 arity 校验 | ❌（仅 `IF`） | ✅ |
| 计算字段依赖图 / 循环检测 | ❌ | ✅ 拓扑排序 |
| 方法调用（`s.startsWith(x)` → `LIKE`） | ❌（白名单拒） | ✅ |
| 复杂类型推导（`+` 字符串拼接 → MySQL `CONCAT` / Postgres `\|\|`） | ❌ | ✅ |

整体不是方言差异，而是**能力差距**：字符级翻译无法看到操作数类型、无法做上下文相关分派。

## 目标

> **利用项目当前绿地期，把 Python 侧升级为与 Java 引擎 1:1 架构对齐**，避免以后外部集成者依赖错误行为后难以回退。

## 交付模式

`single-root delivery` — 全部在 `foggy-data-mcp-bridge-python` 仓，分阶段 PR 级交付。

## 三阶段工作包

### Phase 1 — Dialect-aware 函数翻译 + arity 校验 ✅ 已完成

- `P1-Phase1-Dialect函数翻译与arity校验-需求.md`
- `P1-Phase1-Dialect函数翻译与arity校验-progress.md`
- 实际规模：1 人日
- 产出：`FDialect.build_function_call` + 4 个方言实现 + `_FUNCTION_ARITY` 65 项 + 182 用例
- 状态：`ready-for-quality-gate`，回归 1905 → 2087（0 failed）

### Phase 2 — 计算字段依赖图（拓扑排序 + 循环检测）✅ 已完成

- `P1-Phase2-计算字段依赖图-需求.md`
- `P1-Phase2-计算字段依赖图-progress.md`
- 实际规模：略低于预估（~1.5 人日）
- 产出：`calc_field_sorter.py`（Kahn 算法）+ `compiled_calcs` 全链路透传 + 46 用例
- 收益：支持 `c = a + b`、`d = c * 2` 的传递依赖；slice/groupBy/orderBy/having 可引用 calc；循环明确报错
- 状态：`ready-for-quality-gate`，回归 2087 → 2133（0 failed）

### Phase 3 — `_render_expression` → `FsscriptToSqlVisitor`（AST-based 架构对齐）✅ 已完成

- `P1-Phase3-AST-Visitor-架构对齐-需求.md`
- `P1-Phase3-AST-Visitor-架构对齐-progress.md`
- 实际规模：~1 人日（比预估 1.5 人周快很多，因用 feature flag 双轨策略规避了 Python fsscript parser 未达 Java 级别的部分）
- 产出：
  - `fsscript_to_sql_visitor.py`（AST visitor + `_preprocess_if`）
  - feature flag `use_ast_expression_compiler` (默认 False)
  - 方法调用（`startsWith`/`endsWith`/`contains`/`toUpperCase`/`toLowerCase`/`trim`/`length`）方言路由
  - Ternary `a ? b : c` + `??` null-coalesce 新能力
  - Stage 6 已补齐 `IS NULL` / `BETWEEN` / `LIKE` / `CAST` 原生 AST 编译与保守字符串 `+` 拼接推导；char fallback 仅保留给 `EXTRACT(YEAR FROM ...)`、显式 `CASE WHEN ... END` 等未迁移构造
- 状态：`ready-for-quality-gate`，回归 2133 → 2209（+76，0 failed）

### v1.5 完整达成度

11 项能力中 11 项完成 Python 侧实现（含 Phase 3 的 AST-path 实现）；post-v1.5 Stage 6 已补齐原 Phase 4 optional 中的 SQL-specific AST 覆盖与保守字符串 `+` 推导。`use_ast_expression_compiler` 默认仍为 `False`，默认翻转与 char tokenizer 下线仍独立评估。

### Stage 6（已完成）— Python fsscript parser 升级

- 已完成：`IS NULL` / `BETWEEN` / `LIKE` / `CAST AS` 等 SQL-specific 关键字走 AST；字符串字面量参与 `+` 时走方言拼接。
- 未翻默认：`use_ast_expression_compiler=True` 与 char tokenizer 下线仍需单独生产化签收。
- 证据：`S6-phase4-ast-expression-compiler-progress.md`。

## 风险与决策点

| 风险 | 缓解 |
|---|---|
| Phase 1 修了 `DATE_FORMAT` 翻译，可能触发原本"绕过"Postgres 日期格式问题的存量代码 | Phase 1 只针对 `build_function_call` 返回非 `None` 的方言进行翻译；MySQL / SQLite 维持现状 |
| Phase 2 的循环检测把原来"侥幸能跑"的 calc 组合标红 | 提供明确的错误信息指向循环链上的字段，而不是静默通过 |
| Phase 3 的 AST 迁移改动面大 | 逐个表达式 shape 做对照测试（Java 同名测试镜像到 Python） |

## 版本号对齐

- Java 侧当前跨版本对应：计算字段相关工作散落在 `foggy-dataset-model` 的历代版本；Python v1.5 不强制绑 Java 某一版本，但 Phase 1 的函数翻译单测直接镜像 Java 的 `DialectFunctionTranslationTest.java`

## 后续独立 parity lane

- 总体收口：`v1.4+v1.5-overall-progress-closeout.md` — 汇总 v1.4/v1.5 主线、Python timeWindow parity、`timeWindow + calculatedFields` follow-up、CTE/compose baseline 的当前双端对齐状态与剩余遗留项。
- `P1-timeWindow-Python-parity-progress.md` — 跟踪 Java 已签收 `timeWindow` 能力在 Python 引擎的后续对齐。当前已完成 S4 并功能级签收：`accepted-with-risks`；覆盖 DTO / MCP payload passthrough + validator + rolling/cumulative expansion IR + rolling/ytd/mtd 两层 SQL path + value/range lowering + yoy/mom/wow comparative self-join SQL path + SQLite/MySQL8/Postgres 实库矩阵；MySQL8 已补 2025 sales fact seed 并验证 yoy prior/diff/ratio 非空；验收记录见 `docs/v1.5/acceptance/P1-timeWindow-Python-parity-acceptance.md`。该 follow-up 不改变本 README 中计算字段编译器三阶段的签收结论。
- `P1-timeWindow-calculatedFields-design-progress.md` — 记录 P3 `timeWindow + calculatedFields` 后续增强。当前已按 Java `foggy-data-mcp-bridge-wt-dev-compose` 8.4.0.beta 契约 / 8.5.0.beta 实现对齐并完成签收：Python 支持 timeWindow 输出列之上的后置 scalar calculatedFields，并保留 targetMetrics 引用 calc field、后置 agg/window/缺失列的 Java 同名错误码 fail-closed。签收记录见 `docs/v1.5/acceptance/P1-timeWindow-calculatedFields-acceptance.md`。
- `P2-post-v1.5-followup-execution-plan.md` — 记录 v1.4/v1.5 closeout 后的非阻断项执行顺序：F-7 datasource identity contract、formula parity snapshot CI 固化、normalized SQL golden diff harness、SQL Server real DB matrix、Phase 4 AST optional，以及未来 Java 契约扩展的启动条件。
- `S1-F7-datasource-identity-contract-progress.md` — 记录 post-v1.5 Stage 1 执行结果：Python 已通过 `ModelInfoProvider.get_datasource_id` 实现 cross-datasource union/join compile-time rejection，full regression 3316 passed；Java 镜像已在 `foggy-data-mcp-bridge-wt-dev-compose` 提交 `f918343` 完成并验证。
- `S2-formula-parity-snapshot-ci-progress.md` — 记录 post-v1.5 Stage 2 执行结果：formula parity snapshot schema/catalog/integrity drift detection 已启用，Java snapshot generation 与 Python strict compare 已复验。
- `S7-future-java-contract-expansion-preflight.md` — 记录 Stage 7 未来 Java 契约扩展边界：`timeWindow` 后置二次聚合/窗口、`calculatedFields` 作为 `targetMetrics`、named / recursive CTE 均等待 Java contract + fixtures，Python 当前保持 fail-closed / non-goal。
- `S7a-plan-stable-view-relation-contract-preflight.md` — Stage 7 stable relation formal contract draft：定义 `CompiledRelation` / `RelationSql` / `OutputSchema` semantics、CTE hoisting / SQL Server 写法规则，二次聚合/窗口后续应消费该 relation，而不是扩展当前 post-calc scalar 通道。
- `P2-S7a-stable-relation-python-mirror-progress.md` — 记录 S7a Python mirror：已对齐 Java stable relation POC，消费 Java snapshot，并保持 outer aggregate/window 未开放。
- `S7b-stage7-runtime-contract-plan.md` — Stage 7 runtime contract freeze 计划：S7b 冻结契约，S7c Java 接入 `compileToRelation`，S7d/S7e/S7f 再分阶段开放 relation-as-source、outer aggregate、outer window。
- `quality/S1-S2-post-v1.5-followup-implementation-quality.md` — 记录 Stage 1/2 合并实现质量门结论与后续闭环：Python 侧质量门已完成，Java datasource identity mirror 后续已补齐。

## 参考文档

- `docs/v1.4/P2-fsscript-in-notin算子对齐Java-需求.md`（上一轮 fsscript 算子对齐）
- Java 侧
  - `foggy-data-mcp-bridge/foggy-dataset/src/main/java/.../db/dialect/*Dialect.java`
  - `foggy-data-mcp-bridge/foggy-dataset-model/src/main/java/.../engine/expression/CalculatedFieldService.java`
  - `foggy-data-mcp-bridge/foggy-dataset-model/src/test/java/.../dialect/DialectFunctionTranslationTest.java`
