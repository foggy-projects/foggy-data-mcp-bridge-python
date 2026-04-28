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
5. 对 Phase 4 AST optional 和未来 Java 契约扩展保持显式等待，不在当前阶段抢跑。

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
| F-7 datasource identity contract | Python + Java + Odoo Pro if consumed | contract-needed | 决定 datasource identity 放在 `ModelBinding` 还是 `ModelInfoProvider` |
| Python compose compiler | `src/foggy/dataset_model/engine/compose/compilation` | blocked by contract | 在契约确定后实现真实 cross-datasource compile-time rejection |
| Java compose compiler | `foggy-data-mcp-bridge-wt-dev-compose` | blocked by contract | 镜像 Python 的 datasource identity 判断与错误码行为 |
| Formula parity snapshot CI | Java test + Python integration test | ready | 固化 snapshot 生成与消费约定，避免本地文件漂移 |
| Normalized SQL golden diff harness | Python tests + Java snapshot source | ready after snapshot CI | 把 timeWindow/formula 等 Java SQL 输出升级为系统化 diff |
| SQL Server real DB matrix | integration tests / CI env | env-needed | 有 SQL Server 环境后补执行矩阵 |
| Phase 4 AST optional | Python fsscript + AST visitor | optional | 仅在决定 AST default flip 前启动 |
| Future timeWindow / CTE contracts | Java-first contract | wait | Java 契约明确后 Python 再对齐 |

## Execution Order

### Stage 1 - F-7 datasource identity contract

- status: not-started
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

- 优先评估 Option B。只有 provider 无法稳定拿到 datasource identity 时，再升级到 Option A。

Acceptance:

- Python 当前 xfail 测试转 regular pass：
  `tests/compose/compilation/test_union.py::TestUnionCrossDatasourceRejectedContract::test_cross_datasource_live_detection_via_real_plan`
- 新增 / 更新 join 分支同类测试。
- Java `@Disabled` / placeholder 测试转 regular pass。
- full regression 无新增 skipped / xfailed。

### Stage 2 - Formula parity snapshot CI solidification

- status: ready-to-execute
- priority: P2
- trigger: CI 可访问 Java + Python 两个 checkout，或允许把 Java snapshot artifact 注入 Python test job

Requirement:

- 固化 `FormulaParitySnapshotTest` 生成 `_parity_snapshot.json` 的产物位置。
- Python `tests/integration/test_formula_parity.py` 在 CI 中消费同一份 snapshot。
- 明确当 Java catalog 变化时，snapshot 应由 Java 测试再生成，而不是手写。

Acceptance:

- Java CI job 运行：
  `mvn test -pl foggy-dataset-model -Dtest=FormulaParitySnapshotTest`
- Python CI job 运行：
  `python -m pytest tests/integration/test_formula_parity.py -q`
- CI 文档记录 artifact / checkout 路径约定。
- 本地 committed snapshot 与 Java 生成 snapshot 的 drift 能被检测出来。

### Stage 3 - Java/Python normalized SQL golden diff harness

- status: planned
- priority: P2
- trigger: Stage 2 的 snapshot 生成 / 消费链路稳定后

Requirement:

- 把当前分散的 formula parity snapshot、timeWindow fixture catalog、未来 SQL golden 输出统一成可扩展 harness。
- 支持按 feature lane 组织 snapshot：formula / timeWindow / compose。
- 输出 mismatch 时给出 entry id、dialect、canonical SQL、params 差异。

Acceptance:

- 至少覆盖 formula parity 和 timeWindow post-scalar calculatedFields 子集。
- Java snapshot 来源可追踪到 Java test / fixture。
- Python normalizer 中等价形态规则有单测保护。
- full regression 通过。

### Stage 4 - SQL Server timeWindow real DB matrix

- status: env-needed
- priority: P3
- trigger: 有可重复的 SQL Server 本地或 CI 环境

Requirement:

- 将 `tests/integration/test_time_window_real_db_matrix.py` 扩展到 SQL Server。
- 覆盖 rolling / cumulative / comparative / post scalar calculatedFields 至少一条 smoke path。
- 不用 string-only assertion 伪装 real DB evidence。

Acceptance:

- SQL Server profile 下 real DB integration 通过。
- 文档记录连接方式、跳过条件和数据 seed 约定。
- 不影响无 SQL Server 环境下的默认 full regression。

### Stage 5 - Phase 4 AST optional

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

### Stage 6 - Future Java contract expansion

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
    notes: Stage 4 有 SQL Server 环境后扩展

  - repo: foggy-data-mcp-bridge-python
    path: src/foggy/fsscript, src/foggy/dataset_model/semantic
    role: AST parser / expression compiler
    expected_change: update
    notes: Stage 5 optional only

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
| Stage 5 | AST compiler catalog + dialect function tests + calculatedFields regression + full Python regression |
| Stage 6 | New Java fixture / contract tests first, then Python mirror tests |

## Quality / Audit / Acceptance Flow

Each stage must finish with:

1. Implementation self-check written to its progress doc.
2. Focused tests and full regression evidence.
3. `foggy-implementation-quality-gate` if the stage changes shared compiler behavior or cross-repo contract.
4. `foggy-test-coverage-audit` before formal signoff.
5. `foggy-acceptance-signoff` for Stage 1, Stage 3, Stage 5, and any Stage 6 Java-contract expansion.

## Recommended Start Order

1. Stage 1: F-7 datasource identity contract planning and implementation.
2. Stage 2: Formula parity snapshot CI solidification.
3. Stage 3: Java/Python normalized SQL golden diff harness.
4. Stage 4: SQL Server timeWindow real DB matrix when environment exists.
5. Stage 5: Phase 4 AST optional only if AST default flip becomes a concrete goal.
6. Stage 6: Future Java contract expansions only after Java publishes contract + fixtures.

## Current Decision

- Start with Stage 1 planning package if the next sprint goal is to remove the last `xfailed`.
- Start with Stage 2 if the next sprint goal is CI hardening with minimal product semantics risk.
- Do not start Stage 5/6 opportunistically; both require explicit trigger conditions.
