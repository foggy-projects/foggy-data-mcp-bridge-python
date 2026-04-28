# P2 post-v1.5 follow-up execution plan

## 文档作用

- doc_type: requirement + implementation-plan
- intended_for: root-controller / execution-agent / reviewer
- purpose: 将 v1.4/v1.5 closeout 后的非阻断项拆成可独立开工、独立验收的后续执行计划

## 基本信息

- version: post-v1.5 follow-up
- priority: P2 overall; individual stages may be promoted by downstream demand
- status: planned
- owning_repo: `foggy-data-mcp-bridge-python`
- java_reference_repo: `foggy-data-mcp-bridge-wt-dev-compose`
- related_closeout: `docs/v1.5/v1.4+v1.5-overall-progress-closeout.md`
- experience: N/A，当前计划均为后端 DSL / SQL engine / regression infrastructure，无 UI 交互面

## 背景

v1.4/v1.5 主线、Python timeWindow parity、`timeWindow + calculatedFields` 后置 scalar 子集、formula parity snapshot compare 均已完成并签收。当前剩余项不是当前 signed-off subset 的阻断项，主要分为三类：

- Phase 4 optional：AST 默认路径前的 parser / 类型推导增强。
- 基础设施：跨引擎 SQL golden diff、snapshot CI 固化、SQL Server real DB matrix。
- 未来契约扩展：跨数据源 compile-time 检测、timeWindow 二次聚合/窗口、named / recursive CTE。

本计划的目标是给这些项排出可执行顺序，并明确哪些现在可以做，哪些必须等待 Java 或上游契约先变更。

## 目标

1. 先关闭当前唯一 `xfailed` 的可规划路径：F-7 cross-datasource compile-time detection。
2. 把已经跑通的 Java formula snapshot 本地能力固化为 CI / artifact 约定。
3. 建立更长期的 Java/Python normalized SQL golden diff harness，降低后续双引擎漂移风险。
4. 在有 SQL Server 环境后补 timeWindow real DB matrix。
5. 将 calculatedFields 输出别名投影的 Java/Python 差异收敛为独立契约项。
6. 对 Phase 4 AST optional 和未来 Java 契约扩展保持显式等待，不在当前阶段抢跑。

## 非目标

- 不在没有契约变更的前提下开放 `timeWindow` 二次聚合、二次窗口或 `targetMetrics` 引用 calculatedFields。
- 不在没有明确业务需求的前提下实现 explicit named CTE / recursive CTE。
- 不在没有 SQL Server 可用环境的前提下伪造 SQL Server real DB 通过证据。
- 不把 Python AST compiler 默认切换到 AST-only；Phase 4 仅在专门立项后处理。
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
| calculatedFields alias projection contract | Java validator + Python semantic validation | planned | Stage 5 对齐 calc output alias in columns |
| Phase 4 AST optional | Python fsscript + AST visitor | optional | 仅在决定 AST default flip 前启动 |
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

- status: optional / wait
- priority: P3
- trigger: 决定将 `use_ast_expression_compiler` 默认切到 True，或出现必须 AST-only 才能安全支持的新语法

Requirement:

- Python fsscript parser 支持 `IS NULL` / `BETWEEN` / `LIKE` / `CAST AS` 等 SQL-specific 关键字进入 AST。
- `+` 运算符按操作数类型区分字符串拼接和数值加法。
- 评估 char tokenizer fallback 是否可以下线。

Acceptance:

- AST path 覆盖现有 SQL-specific expression catalog。
- MySQL / Postgres / SQLite / SQL Server 方言函数和字符串拼接单测通过。
- 默认 flag 变更需要单独质量闸门和覆盖审计。

### Stage 7 - Future Java contract expansion

- status: wait-for-java-contract
- priority: demand-driven

Items:

- `timeWindow` 后置二次聚合。
- `timeWindow` 后置二次窗口。
- `calculatedFields` 作为 `timeWindow.targetMetrics` 输入。
- explicit named CTE / recursive CTE。

Rule:

- Java 契约未明确前，Python 保持 fail-closed 或 non-goal。
- 一旦 Java 提供 contract + fixture，Python 新开独立 follow-up，对齐错误码、SQL 结构、实库矩阵和 LLM schema 描述。

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
