# P2 post-v1.5 follow-up execution plan

## 文档作用

- doc_type: requirement + implementation-plan
- intended_for: root-controller / execution-agent / reviewer
- purpose: 将 v1.4/v1.5 closeout 后的非阻断项拆成可独立开工、独立验收的后续执行计划

## 基本信息

- version: post-v1.5 follow-up
- priority: P2 overall; individual stages may be promoted by downstream demand
- status: complete-through-stage-6b; stage-7-complete-through-s7e; s7f-ready-after-signoff
- owning_repo: `foggy-data-mcp-bridge-python`
- java_reference_repo: `foggy-data-mcp-bridge-wt-dev-compose`
- related_closeout: `docs/v1.5/v1.4+v1.5-overall-progress-closeout.md`
- experience: N/A，当前计划均为后端 DSL / SQL engine / regression infrastructure，无 UI 交互面

## 背景

v1.4/v1.5 主线、Python timeWindow parity、`timeWindow + calculatedFields` 后置 scalar 子集、formula parity snapshot compare 均已完成并签收。当前剩余项不是当前 signed-off subset 的阻断项，主要分为三类：

- AST parser / 类型推导增强：Stage 6 / 6b 已完成；默认翻转仍待单独生产化签收。
- 基础设施：跨引擎 SQL golden diff、snapshot CI 固化、SQL Server real DB matrix。
- 未来契约扩展：跨数据源 compile-time 检测、timeWindow 二次聚合/窗口、named / recursive CTE。

本计划的目标是给这些项排出可执行顺序，并明确哪些现在可以做，哪些必须等待 Java 或上游契约先变更。

## 目标

1. 先关闭当前唯一 `xfailed` 的可规划路径：F-7 cross-datasource compile-time detection。
2. 把已经跑通的 Java formula snapshot 本地能力固化为 CI / artifact 约定。
3. 建立更长期的 Java/Python normalized SQL golden diff harness，降低后续双引擎漂移风险。
4. 在有 SQL Server 环境后补 timeWindow real DB matrix。
5. 将 calculatedFields 输出别名投影的 Java/Python 差异收敛为独立契约项。
6. Stage 6 / 6b 已完成 Phase 4 AST optional 的 parser / 类型推导增强；未来 Java 契约扩展保持显式等待，不在当前阶段抢跑。

## 非目标

- 不在没有契约变更的前提下开放 `timeWindow` 二次聚合、二次窗口或 `targetMetrics` 引用 calculatedFields。
- 不在没有明确业务需求的前提下实现 explicit named CTE / recursive CTE。
- 不在没有 SQL Server 可用环境的前提下伪造 SQL Server real DB 通过证据。
- 不把 Python AST compiler 默认切换到 AST-only；默认翻转与 char tokenizer 下线需专门立项处理。
- 不改 Java 代码；Java 侧工作需要在 `foggy-data-mcp-bridge-wt-dev-compose` 或对应 Java worktree 单独开工。

## Module Responsibility

| Area | Owner | Current Readiness | Responsibility |
|---|---|---:|---|
| Root planning / tracking | `foggy-data-mcp-bridge-python` docs | ready | 维护本计划、阶段进度、验收链接和 closeout 回写 |
| F-7 datasource identity contract | Python + Java + Odoo Pro if consumed | Python + Java complete | Python / Java 均选择 `ModelInfoProvider.get_datasource_id` / `getDatasourceId`，保持 `ModelBinding` 冻结 |
| Python compose compiler | `src/foggy/dataset_model/engine/compose/compilation` | complete | 已实现真实 cross-datasource compile-time rejection |
| Java compose compiler | `foggy-data-mcp-bridge-wt-dev-compose` | complete | 已镜像 Python 的 datasource identity 判断与错误码行为；提交 `f918343` |
| Formula parity snapshot CI | Java test + Python integration test | complete-with-ci-assumption | snapshot 生成/消费和 drift detection 已固化；外部 CI workflow 仍未接线 |
| Normalized SQL golden diff harness | Python tests + Java snapshot source | ready after snapshot CI | 把 timeWindow/formula 等 Java SQL 输出升级为系统化 diff |
| SQL Server real DB matrix | integration tests / CI env | complete | 已复用 Java demo SQL Server 2022 环境补齐执行矩阵 |
| calculatedFields alias projection contract | Java validator + Python semantic validation | complete | Stage 5 已对齐 calc output alias in columns |
| Phase 4 AST optional | Python fsscript + AST visitor | complete-through-stage-6b | SQL-specific AST / 保守字符串 `+` / AST-on SQLite smoke 已完成；默认翻转另起 gate |
| Future timeWindow / CTE contracts | Java-first contract | wait | Java 契约明确后 Python 再对齐 |

## Execution Order

### Stage 1 - F-7 datasource identity contract

- status: Python-complete / Java-complete
- priority: P1 within follow-up queue
- trigger: 需要消除当前唯一 `xfailed`，或 M7/M8 多 datasource 场景开始实际消费 compose query
- owner: root controller coordinates Python + Java contract owners

Requirement:

- 为 compose `UnionPlan` / `JoinPlan` 提供稳定 datasource identity 来源。
- 编译期发现左右分支属于不同 datasource 时，抛出 `compose-compile-error/cross-datasource-rejected`。
- Python / Java 错误码、phase、消息语义保持一致。

Contract decision:

- Option A: `ModelBinding.datasource_id`
  - 覆盖直接，能随 binding 传入 plan context。
  - 触动 M1/M5 冻结契约，可能要求 Python + Java + Odoo Pro 同步。
- Option B: `ModelInfoProvider.get_datasource_id(model_name)`
  - 只扩展 provider 契约，侵入性低。
  - 需要确认 Java / Python 两侧 provider 生命周期可访问 datasource identity。

Recommended decision:

- 已选择 Option B：`ModelInfoProvider.get_datasource_id(model_name, namespace) -> Optional[str]`。`ModelBinding` 保持冻结，不新增字段。

Acceptance:

- Python 当前 xfail 测试已转 regular pass：
  `tests/compose/compilation/test_union.py::TestUnionCrossDatasourceRejectedContract::test_cross_datasource_live_detection_via_real_plan`
- 已新增 join 分支同类测试。
- Python full regression: `3316 passed`。
- Python implementation quality gate: `docs/v1.5/quality/S1-S2-post-v1.5-followup-implementation-quality.md`, decision was `ready-with-risks` before Java mirror.
- Java mirror landed in `foggy-data-mcp-bridge-wt-dev-compose` commit `f918343 feat(compose): add datasource identity guard`.
- Java focused compose verification:
  `mvn test -pl foggy-dataset-model "-Dtest=ModelInfoProviderSmokeTest,ComposeSqlCompilerTest,UnionCompileTest,JoinCompileTest,ComposeCompileErrorCodesTest"` -> 3 surefire lanes, each 66 tests, 0 failures/errors/skips.
- Java compose lane:
  `mvn test -pl foggy-dataset-model "-Dtest=*CompileTest,*CompilationTest,*Compose*Test"` -> 184 tests, 0 failures/errors/skips.
- Java formula snapshot guard:
  `mvn test -pl foggy-dataset-model "-Dtest=FormulaParitySnapshotTest"` -> 3 surefire lanes, each 5 tests, 0 failures/errors/skips.

### Stage 2 - Formula parity snapshot CI solidification

- status: complete-with-ci-assumption
- priority: P2
- trigger: CI 可访问 Java + Python 两个 checkout，或允许把 Java snapshot artifact 注入 Python test job

Requirement:

- 固化 `FormulaParitySnapshotTest` 生成 `_parity_snapshot.json` 的产物位置。
- Python `tests/integration/test_formula_parity.py` 在 CI 中消费同一份 snapshot。
- 明确当 Java catalog 变化时，snapshot 应由 Java 测试再生成，而不是手写。

Acceptance:

- Java snapshot generation re-verified:
  `mvn test -pl foggy-dataset-model -Dtest=FormulaParitySnapshotTest`
- Python snapshot compare re-verified:
  `python -m pytest tests/integration/test_formula_parity.py -q`
- CI 文档已记录 artifact / checkout 路径约定。
- 本地 committed snapshot 与 Java catalog 的 drift 可被 Python 测试检测出来。
- Consolidated quality gate: `docs/v1.5/quality/S1-S2-post-v1.5-followup-implementation-quality.md`.

### Stage 3 - Java/Python normalized SQL golden diff harness

- status: complete (structural + key-marker parity; token-by-token diff needs normalizer extension for multi-CTE)
- priority: P2
- trigger: Stage 2 的 snapshot 生成 / 消费链路稳定后

Requirement:

- 把当前分散的 formula parity snapshot、timeWindow fixture catalog、未来 SQL golden 输出统一成可扩展 harness。
- 支持按 feature lane 组织 snapshot：formula / timeWindow / compose。
- 输出 mismatch 时给出 entry id、dialect、canonical SQL、params 差异。

Acceptance:

- Formula lane: `test_parity_matches_java_snapshot` migrated to `_golden_sql_diff.assert_golden_cases`.
- TimeWindow lane: 2 post-scalar calculatedFields happy cases structural parity + key-marker diff passing.
- Java snapshot producer: `TimeWindowParitySnapshotTest.java` writes `_time_window_parity_snapshot.json` via real `SemanticQueryServiceV3.generateSql`; Java commit `a2ae69d`.
- `test_full_golden_diff_when_snapshot_available` no longer skipped — validates Java snapshot schema, semantic markers, and cross-checks Python SQL.
- Known limitation: full token-by-token normalized SQL diff deferred — Java/Python produce architecturally different multi-CTE SQL.
- Focused regression: `70 passed, 0 skipped`.
- Progress doc: `docs/v1.5/S3-normalized-sql-golden-diff-progress.md`.

### Stage 4 - SQL Server timeWindow real DB matrix

- status: **complete** ✅
- priority: P3
- completed: 2026-04-28
- evidence: `S4-sqlserver-timewindow-real-db-matrix-progress.md`

Implementation:

- Added `SQLServerExecutor` to `executor.py` using `pyodbc` with LIMIT→TOP and CTE hoisting.
- Extended `test_time_window_real_db_matrix.py`: sqlserver added to parametrized matrix + 3 dedicated tests.
- 11 SQL Server tests total (8 matrix + 3 dedicated), all passing.
- Uses Java demo docker-compose SQL Server 2022 environment (port 11433).
- Skips safely when pyodbc / ODBC driver / container unavailable.
- Java `SchemaAwareFieldValidationStep` post-calc alias limitation documented, NOT fixed (deferred).

### Stage 5 - calculatedFields output alias projection contract alignment

- status: **complete** ✅
- priority: P2
- completed: 2026-04-28
- evidence: `S5-calculatedFields-alias-projection-contract-progress.md`

Implementation:

- Java `TimeWindowInterceptor`: strips calc field output names from `originalColumns` in the `BaseModelPlan` — post-calc aliases are projected in the outer `DerivedQueryPlan` wrapper only.
- Java `SemanticQueryServiceV3Impl`: passes `calculatedFields` to `extData` for both `generateSql()` and `queryModel(..., "execute", ...)`, so `TimeWindowInterceptor` can build the outer post-calc projection wrapper.
- Java `SchemaAwareFieldValidationStep`: already adds request-level `calculatedFields.name` to `schemaFields` (no change needed for non-timeWindow path).
- New Java test `SchemaAwareCalcFieldAliasTest`: 7 tests covering non-TW calc alias in columns/orderBy, TW growthPercent/rollingGap in preview and execute mode, unknown column rejection, and calc alias without definition rejection.
- Updated `TimeWindowParitySnapshotTest`: `growthPercent`/`rollingGap` now included in request columns.
- Python fixture updated: `requestColumns` field added to post-calc cases.
- Java `TimeWindowValidatorTest`: 19 tests still passing (negative cases preserved).
- Python golden diff, parity catalog, and real DB matrix all passing.
- `columns=["amount as amount1"]` is NOT opened by this change — stays on existing InlineExpressionParser path.
- `targetMetrics` referencing calculatedFields, post-calc agg/window/unknown-ref continue to fail-closed.

### Stage 6 - Phase 4 AST optional

- status: **complete**
- priority: P3
- delivered: `docs/v1.5/S6-phase4-ast-expression-compiler-progress.md`

Requirement:

- Python fsscript parser 支持 `IS NULL` / `BETWEEN` / `LIKE` / `CAST AS` 等 SQL-specific 关键字进入 AST。
- `+` 运算符按操作数类型区分字符串拼接和数值加法。
- 评估 char tokenizer fallback 是否可以下线。

Delivered:

- IS [NOT] NULL / [NOT] BETWEEN / [NOT] LIKE / CAST(x AS type) 原生 AST 编译。
- `+` 保守字符串字面量推断（StringExpression → dialect concat）。
- char tokenizer fallback 仅剩 `EXTRACT(YEAR FROM d)` 和显式 `CASE WHEN ... END`。
- Stage 6b 已补 AST-on SQLite execution smoke，并修复 `CAST(... AS TYPE)` 字段依赖抽取与 `CalculatedFieldDef` Stage 6 AST-only 早期校验 carve-out。
- 102 AST 测试通过，3363 全量回归 0 失败。

Acceptance:

- AST path 覆盖现有 SQL-specific expression catalog。
- MySQL / Postgres / SQLite / SQL Server 方言函数和字符串拼接单测通过。
- SQLite executor 真实执行覆盖 `IS NULL` / `BETWEEN` / `LIKE` / `CAST` / 字符串 `+`。
- 默认 flag 变更需要单独质量闸门和覆盖审计（未翻转，保持 False）。

### Stage 7 - Future Java contract expansion

- status: S7a Java POC + Python mirror complete; S7b frozen; S7c Java compileToRelation complete; S7d Java relation-as-source read-only complete; S7e Java outer aggregate complete + Python mirror complete; S7f Java outer window complete + Python mirror complete
- priority: demand-driven
- preflight: `docs/v1.5/S7-future-java-contract-expansion-preflight.md`
- relation_contract: `docs/v1.5/S7a-plan-stable-view-relation-contract-preflight.md`
- runtime_contract_plan: `docs/v1.5/S7b-stage7-runtime-contract-plan.md`
- outer_window_preflight: `docs/v1.5/S7f-outer-window-contract-preflight.md`
- python_mirror_progress: `docs/v1.5/P2-S7a-stable-relation-python-mirror-progress.md`

Items:

- `timeWindow` 后置二次聚合。
- `timeWindow` 后置二次窗口。
- `calculatedFields` 作为 `timeWindow.targetMetrics` 输入。
- explicit named CTE / recursive CTE。

Why these might exist:

- 后置二次聚合用于在 timeWindow 结果集上做更高层汇总，例如先按 `store + month` 得到同比增长率，再按 `region` 汇总增长表现。
- 后置二次窗口用于在 timeWindow 派生列上继续做排名、移动平均、累计或平滑分析，例如对 `salesAmount__ratio` 做 rank 或 rolling average。
- `calculatedFields` 作为 `targetMetrics` 用于对动态指标直接做同比/滚动，例如 `grossMargin = salesAmount - costAmount` 后再做 YoY。
- explicit named CTE / recursive CTE 用于显式复用复杂中间结果或表达递归层级遍历。

Why they remain closed:

- 二次聚合的口径容易歧义：聚合 ratio、聚合 diff、重新计算整体 ratio 不是同一件事。
- 二次窗口会重新引入 S16 已规避的 window nesting / partition / order / frame 层级问题。
- request-level calculatedFields 缺少稳定聚合口径，作为 `targetMetrics` 可能形成循环依赖或错误业务语义。
- named / recursive CTE 会引入作用域、名称冲突、权限裁剪和方言兼容的新契约。

Precondition:

- 在开放任何二次聚合 / 二次窗口前，先定义 `QueryPlan -> Stable View/Relation` 契约。
- `Stable View/Relation` 必须携带 SQL、params、alias、datasource identity、dialect/capabilities 和稳定 `OutputSchema`。
- `OutputSchema` 不只描述列名，还应描述列语义、来源、是否派生、是否可在外层 groupBy / aggregate / window / orderBy 中引用。
- `timeWindow` 派生列如 `metric__prior` / `metric__diff` / `metric__ratio` / `metric__rolling_*` / `metric__ytd` / `metric__mtd` 必须在 schema 中有稳定含义。
- `CteUnit` 继续保持内部 SQL assembly primitive 职责，不作为正式 stable relation contract；relation contract 由 `CompiledRelation` / `PlanView` 或等价抽象承载。
- SQL Server relation wrapping / CTE hoisting 是 Stage 7 开放前的显式契约项，不能只靠文档说明。
- CTE 写法必须遵守 S7a 规则：不得生成 `FROM (WITH ... SELECT ...) AS rel`；带 inner CTE 的 relation 必须 hoist 成 top-level `WITH ... rel_N AS (...) SELECT ... FROM rel_N`，不支持 hoist 的方言 fail-closed。
- 二次聚合 / 二次窗口应建模为 `DerivedQueryPlan over Stable Relation`，而不是放开当前 `timeWindow + calculatedFields` 的 `agg/windowFrame` 通道。

Rule:

- S7b 先冻结 stable relation contract，不直接开放 runtime 能力。
- S7c 由 Java 先接入真实 `compileToRelation(plan, context) -> CompiledRelation` 入口。
- S7d 只开放 relation-as-source read-only 外层查询；raw filter 必须声明依赖列并通过 `referencePolicy` 验证，SQL Server hoisted CTE 使用防御性 `;WITH`。
- S7e has been completed on both Java and Python: Java opened outer aggregate for wrappable relations; Python mirrors MEASURE_DEFAULT with aggregatable, updates for_dialect(), and consumes the S7e snapshot.
- S7f has been completed on both Java and Python: Java opened outer window for wrappable window-capable dialects in `b248404`, kept MySQL 5.7 fail-closed for outer window, and published `_stable_relation_outer_window_snapshot.json` (`S7f-1`). Python mirrors `windowable`, capability matrix, error codes, and snapshot consumer tests only; it does not implement runtime outer window. Python verification: focused `120 passed`; full regression `3468 passed`.
- Python 继续作为 Java snapshot consumer / mirror，不在 Java runtime contract 未冻结前抢跑能力。

## Code Inventory

```yaml
code_inventory:
  - repo: foggy-data-mcp-bridge-python
    path: docs/v1.5/P2-post-v1.5-followup-execution-plan.md
    role: root execution plan
    expected_change: create
    notes: 本文件，总控后续阶段与验收标准

  - repo: foggy-data-mcp-bridge-python
    path: docs/v1.5/v1.4+v1.5-overall-progress-closeout.md
    role: closeout summary
    expected_change: update
    notes: 推荐下一步需从已完成的 snapshot automation 调整为本计划顺序

  - repo: foggy-data-mcp-bridge-python
    path: docs/v1.5/README.md
    role: version index
    expected_change: update
    notes: 增加 post-v1.5 follow-up 计划入口

  - repo: foggy-data-mcp-bridge-python
    path: tests/compose/compilation/test_union.py
    role: F-7 xfail guard
    expected_change: update
    notes: Stage 1 才允许把 xfail 转 regular pass

  - repo: foggy-data-mcp-bridge-python
    path: src/foggy/dataset_model/engine/compose/compilation
    role: compose compiler
    expected_change: update
    notes: Stage 1 契约确定后实现 datasource identity 检测

  - repo: foggy-data-mcp-bridge-python
    path: tests/integration/test_formula_parity.py
    role: Python snapshot consumer
    expected_change: update
    notes: Stage 2/3 可补 drift detection 或更通用 harness

  - repo: foggy-data-mcp-bridge-python
    path: tests/integration/_sql_normalizer.py
    role: canonical SQL normalizer
    expected_change: update
    notes: Stage 3 新增 golden diff 规则时必须补 normalizer 单测

  - repo: foggy-data-mcp-bridge-python
    path: tests/integration/test_time_window_real_db_matrix.py
    role: real DB matrix
    expected_change: update
    notes: Stage 4 已扩展 SQL Server 环境

  - repo: foggy-data-mcp-bridge-python
    path: tests/fixtures/java_time_window_parity_catalog.json, tests/test_dataset_model/test_time_window_java_parity_catalog.py
    role: calc alias projection parity fixtures
    expected_change: update
    notes: Stage 5 对齐 Java/Python calc output alias in columns

  - repo: foggy-data-mcp-bridge-python
    path: src/foggy/fsscript, src/foggy/dataset_model/semantic
    role: AST parser / expression compiler
    expected_change: update
    notes: Stage 6 optional only

  - repo: foggy-data-mcp-bridge-wt-dev-compose
    path: foggy-dataset-model/src/test/java/.../parity/FormulaParitySnapshotTest.java
    role: Java formula snapshot producer
    expected_change: update
    notes: Stage 2/3 可调整 artifact path 或 schema；非 Python 本计划直接修改范围

  - repo: foggy-data-mcp-bridge-wt-dev-compose
    path: foggy-dataset-model/src/main/java/.../compose
    role: Java compose compiler
    expected_change: update
    notes: Stage 1 Java 镜像实现；需在 Java worktree 单独执行
```

## Testing Requirements

| Stage | Required Tests |
|---|---|
| Stage 1 | focused compose compile tests + full Python regression + Java compose focused tests |
| Stage 2 | Java `FormulaParitySnapshotTest` + Python `test_formula_parity.py` + CI artifact check |
| Stage 3 | feature lane golden diff tests + normalizer unit examples + full Python regression |
| Stage 4 | SQL Server real DB matrix profile + default regression skip behavior |
| Stage 5 | Java validator contract tests + Python mirror fixtures + real DB calc alias projection regression |
| Stage 6 | AST compiler catalog + dialect function tests + calculatedFields regression + full Python regression |
| Stage 7 | New Java fixture / contract tests first, then Python mirror tests |

## Quality / Audit / Acceptance Flow

Each stage must finish with:

1. Implementation self-check written to its progress doc.
2. Focused tests and full regression evidence.
3. `foggy-implementation-quality-gate` if the stage changes shared compiler behavior or cross-repo contract.
4. `foggy-test-coverage-audit` before formal signoff.
5. `foggy-acceptance-signoff` for Stage 1, Stage 3, Stage 5, and any Stage 7 Java-contract expansion.

## Recommended Start Order

1. Stage 3: Java/Python normalized SQL golden diff harness.
2. Stage 4: SQL Server timeWindow real DB matrix when environment exists.
3. Stage 5: calculatedFields output alias projection contract alignment.
4. Stage 6: Phase 4 AST optional only if AST default flip becomes a concrete goal.
5. Stage 7: Future Java contract expansions only after Java publishes contract + fixtures.

## Current Decision

- Python Stage 1 and Stage 2 are implemented and verified.
- Java Stage 1 mirror is implemented and verified in `foggy-data-mcp-bridge-wt-dev-compose` commit `f918343`.
- Full two-engine F-7 implementation closure is complete; formal signoff can proceed after coverage audit if needed.
- Stage 4 is complete.
- Do not start Stage 5/6/7 opportunistically; each requires explicit trigger conditions.
