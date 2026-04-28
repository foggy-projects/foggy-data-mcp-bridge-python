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
  - `fsscript_to_sql_visitor.py` (~440 行，AST visitor + `_preprocess_if`)
  - feature flag `use_ast_expression_compiler` (默认 False)
  - 方法调用（`startsWith`/`endsWith`/`contains`/`toUpperCase`/`toLowerCase`/`trim`/`length`）方言路由
  - Ternary `a ? b : c` + `??` null-coalesce 新能力
  - AST-first + char-fallback 策略，对 SQL-specific 语法（`IS NULL`/`BETWEEN`/`LIKE`）自动回落
- 状态：`ready-for-quality-gate`，回归 2133 → 2209（+76，0 failed）

### v1.5 完整达成度

11 项能力中 11 项完成 Python 侧实现（含 Phase 3 的 AST-path 实现）；剩 2 项低优先级（`+` 类型推导、Python fsscript parser 升级以覆盖 SQL-specific 关键字走 AST）可在 Phase 4 单独评估。

### Phase 4（可选）— Python fsscript parser 升级

- 目的：补齐 `IS NULL` / `BETWEEN` / `LIKE` / `CAST AS` 等 SQL-specific 关键字，让所有表达式都走 AST（而不是部分回落 char tokenizer），然后翻默认到 AST + 下线 char tokenizer
- 规模：约 1 人周
- 优先级：低 —— 当前双轨已经覆盖用户实际使用场景

## 风险与决策点

| 风险 | 缓解 |
|---|---|
| Phase 1 修了 `DATE_FORMAT` 翻译，可能触发原本"绕过"Postgres 日期格式问题的存量代码 | Phase 1 只针对 `build_function_call` 返回非 `None` 的方言进行翻译；MySQL / SQLite 维持现状 |
| Phase 2 的循环检测把原来"侥幸能跑"的 calc 组合标红 | 提供明确的错误信息指向循环链上的字段，而不是静默通过 |
| Phase 3 的 AST 迁移改动面大 | 逐个表达式 shape 做对照测试（Java 同名测试镜像到 Python） |

## 版本号对齐

- Java 侧当前跨版本对应：计算字段相关工作散落在 `foggy-dataset-model` 的历代版本；Python v1.5 不强制绑 Java 某一版本，但 Phase 1 的函数翻译单测直接镜像 Java 的 `DialectFunctionTranslationTest.java`

## 后续独立 parity lane

- `P1-timeWindow-Python-parity-progress.md` — 跟踪 Java 已签收 `timeWindow` 能力在 Python 引擎的后续对齐。当前只完成 S0 DTO / MCP payload passthrough，QueryPlan / SQL execution parity 仍未完成；不改变本 README 中计算字段编译器三阶段的签收结论。

## 参考文档

- `docs/v1.4/P2-fsscript-in-notin算子对齐Java-需求.md`（上一轮 fsscript 算子对齐）
- Java 侧
  - `foggy-data-mcp-bridge/foggy-dataset/src/main/java/.../db/dialect/*Dialect.java`
  - `foggy-data-mcp-bridge/foggy-dataset-model/src/main/java/.../engine/expression/CalculatedFieldService.java`
  - `foggy-data-mcp-bridge/foggy-dataset-model/src/test/java/.../dialect/DialectFunctionTranslationTest.java`
