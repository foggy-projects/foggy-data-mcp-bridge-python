# S7b Stage 7 runtime contract plan

## 文档作用

- doc_type: requirement + implementation-plan
- intended_for: root-controller / Java contract owner / Python mirror owner / reviewer
- purpose: 在 S7a stable relation 双端模型对齐后，定义 Stage 7 runtime 能力开工前的契约冻结与分阶段开放计划

## 基本信息

- version: post-v1.5 follow-up
- priority: P1 when Stage 7 is promoted
- status: complete-through-s7e; s7f-ready
- owner: `foggy-data-mcp-bridge-python` docs
- java_reference_repo: `foggy-data-mcp-bridge-wt-dev-compose`
- related_contract: `docs/v1.5/S7a-plan-stable-view-relation-contract-preflight.md`
- related_python_mirror: `docs/v1.5/P2-S7a-stable-relation-python-mirror-progress.md`
- related_java_progress: `foggy-data-mcp-bridge-wt-dev-compose/docs/8.5.0.beta/P2-S7a-stable-relation-contract-progress.md`

## 背景

S7a 已把 `QueryPlan -> Stable Relation` 的模型层契约在 Java / Python 双端对齐。当前已经具备以下基础：

- Java 提供 `CompiledRelation` / `RelationSql` / `RelationCapabilities` / `ColumnSpec` metadata。
- Python 已 mirror Java S7a 模型，并消费 Java `_stable_relation_schema_snapshot.json`。
- `supportsOuterAggregate` / `supportsOuterWindow` 在双端都保持 `false`。
- SQL Server hoisted CTE / MySQL 5.7 fail-closed / 禁止 `FROM (WITH` 已形成可测试契约。

Stage 7 的目标不是继续扩 `timeWindow + calculatedFields` 后置表达式，而是让任意稳定 `CompiledRelation` 可以作为外层查询的 source。二次聚合与二次窗口必须建模为 outer plan over relation，而不是塞回同一层 timeWindow DSL。

## 目标

1. 冻结 S7a 对象模型与 snapshot schema，形成 Stage 7 runtime 的开工契约。
2. 明确 Java 先行的 runtime 入口：`compileToRelation(plan, context) -> CompiledRelation`。
3. 分阶段开放 relation-as-source、outer aggregate、outer window。
4. 确保每一阶段都保持 schema 稳定、权限边界清晰、datasource identity 不漂移。
5. 让 Python 继续作为 mirror / parity consumer，不在 Java contract 未冻结前抢跑 runtime 能力。

## 非目标

- 不在 S7b 阶段开放二次聚合或二次窗口。
- 不增加无上下文的 `QueryPlan.toView()` / `QueryPlan.toRelation()` 方法。
- 不把 stable relation 物化为数据库 `CREATE VIEW`。
- 不实现 named CTE / recursive CTE。
- 不开放普通 `columns=["amount AS amount1"]` alias 新契约。
- 不允许绕过 `referencePolicy` 对派生列做二次聚合或窗口。

## Contract Freeze Checklist

S7b 必须先完成以下确认，才能进入 Java S7c runtime POC：

- [x] `CompiledRelation` 字段名、默认值、nullable 语义冻结。
- [x] `RelationSql` 的 `withItems + bodySql + bodyParams + preferredAlias` 结构冻结。
- [x] `RelationCapabilities` 字段与 `relationWrapStrategy` 枚举值冻结。
- [x] `ColumnSpec` metadata 字段冻结，并继续排除在 equality/hash 之外。
- [x] `SemanticKind` / `ReferencePolicy` 字符串常量冻结。
- [x] `referencePolicy` 的默认解释冻结：集合语义，不是单值。
- [x] `salesAmount__ratio` 等 ratio 派生列默认不可 `aggregatable`。
- [x] SQL Server hoisted CTE 渲染规则冻结：不得生成 `FROM (WITH`。
- [x] MySQL 5.7 + inner CTE fail-closed 规则冻结。
- [x] Java stable relation snapshot schema 冻结，Python mirror 测试继续消费。

## Module Responsibility

| Area | Owner | Responsibility |
|---|---|---|
| Root contract | Python docs | 维护 S7b contract freeze、阶段顺序、跨端验收口径 |
| Java runtime | `foggy-data-mcp-bridge-wt-dev-compose/foggy-dataset-model` | 先实现真实 `compileToRelation`，再分阶段开放外层查询能力 |
| Python mirror | `foggy-data-mcp-bridge-python` | 继续消费 Java snapshot，镜像 contract，不抢跑 Java runtime |
| Parity tests | Java producer + Python consumer | 固化 snapshot schema、capabilities、SQL marker、metadata |
| Review/signoff | root-controller | 每阶段完成后执行实现自检、测试覆盖审计和签收 |

## Execution Order

### S7b - Contract freeze

- status: completed
- owner: root-controller + Java/Python contract owners

Output:

- S7a 文档状态升级为 `contract-frozen-for-stage7-runtime`。
- Java / Python progress 文档记录冻结结论。
- snapshot schema 版本保持 `S7a-1` 或显式升级为 `S7b-1`，不得无声变更。

Acceptance:

- Java `StableRelationSnapshotTest` 通过。
- Python stable relation snapshot tests 通过。
- 双端 `supportsOuterAggregate=false` / `supportsOuterWindow=false` 仍为默认。

### S7c - Java compileToRelation runtime entry

- status: completed
- owner: Java

Requirement:

- 引入真实 compiler/service 入口，将现有 `QueryPlan` 编译为 `CompiledRelation`。
- 不把编译逻辑塞进无上下文 `QueryPlan.toRelation()`。
- 编译上下文必须携带 dialect、datasource identity、权限状态、参数绑定、CTE wrapping 策略。

Acceptance:

- base plan / derived plan / timeWindow plan 可产出 stable relation。
- relation SQL 参数顺序稳定。
- SQL Server 有 inner CTE 时使用 top-level hoisted CTE。
- MySQL 5.7 + inner CTE fail-closed。
- Stage 7 二次聚合/窗口仍未开放。

### S7d - Relation-as-source read-only outer query

- status: completed
- owner: Java first, Python mirror after contract evidence

Requirement:

- 允许外层 query 以 `CompiledRelation` 作为 source。
- 第一版只开放 readable select、orderable orderBy、必要的 filter/limit。
- 输出新的 `OutputSchema`，并保留 relation lineage。

Non-goals:

- 不开放 outer aggregate。
- 不开放 outer window。
- 不开放 relation join / union。

Acceptance:

- 外层引用未知列 fail-closed。
- 外层引用不可 readable/orderable 列 fail-closed。
- raw filter 必须声明依赖列，否则无法按 `referencePolicy` 验证并 fail-closed。
- SQL Server hoisted CTE 使用防御性 `;WITH`，且仍不得出现 `FROM (WITH`。
- datasource identity 继承稳定。
- output schema 对外稳定。

### S7e - Outer aggregate

- status: Java completed; Python mirror ready
- owner: Java first, Python mirror after snapshot

Requirement:

- 允许外层对 stable relation 做聚合。
- 只能聚合 `referencePolicy` 包含 `aggregatable` 的列。
- ratio / percent 派生列默认不可聚合，除非未来契约明确业务口径。

Acceptance:

- 合法 aggregatable 字段二次聚合通过。
- ratio sum/avg 默认拒绝。
- 非 aggregatable 字段拒绝。
- Java snapshot 增加正反例，Python 消费通过。

Java evidence:

- Java opened `supportsOuterAggregate=true` for wrappable relations while
  keeping `supportsOuterWindow=false`.
- S7a frozen snapshot remains `_stable_relation_schema_snapshot.json`
  (`S7a-1`).
- S7e aggregate evidence is emitted separately as
  `_stable_relation_outer_aggregate_snapshot.json` (`S7e-1`).
- S7e snapshot covers positive `SUM + GROUP BY`, ratio aggregate rejection,
  MySQL 5.7 CTE fail-closed, and SQL Server hoisted CTE.

### S7f - Outer window

- status: ready after Python S7e mirror
- owner: Java first, Python mirror after snapshot

Requirement:

- 允许外层对 stable relation 做窗口计算。
- 只有 `windowable` 列可以作为窗口表达式输入。
- partition/order 引用也必须通过 `referencePolicy`。

Acceptance:

- 合法 outer window 通过。
- 不可 windowable 派生列拒绝。
- 内层 timeWindow 与外层 window 的 schema lineage 可解释。

## Code Inventory

| Repo | Path | Role | Expected Change | Notes |
|---|---|---|---|---|
| Python | `docs/v1.5/S7a-plan-stable-view-relation-contract-preflight.md` | root contract | update | S7b 完成后升级状态 |
| Python | `docs/v1.5/P2-S7a-stable-relation-python-mirror-progress.md` | Python evidence | update | 记录 mirror 后续验证 |
| Python | `src/foggy/dataset_model/engine/compose/relation/` | Python mirror model | read-only-analysis | S7b 只确认，不抢跑 runtime |
| Python | `tests/compose/relation/` | Python parity tests | update | 消费 Java snapshot schema 变化 |
| Java | `foggy-dataset-model/src/main/java/.../compose/relation/` | Java relation contract | update | S7c 后承接 runtime entry |
| Java | `foggy-dataset-model/src/main/java/.../compose/compilation/` | Java compiler | update | 推荐新增 compiler/service 入口 |
| Java | `foggy-dataset-model/src/main/java/.../compose/plan/` | QueryPlan family | update cautiously | 不新增无上下文 toRelation |
| Java | `foggy-dataset-model/src/test/java/.../parity/` | Java snapshot producer | update | 每阶段产出 fixture/evidence |

## Verification

Java baseline:

```powershell
cd D:\foggy-projects\foggy-data-mcp\foggy-data-mcp-bridge-wt-dev-compose
mvn test -pl foggy-dataset-model "-Dtest=StableRelationSnapshotTest,RelationModelTest,ColumnSpecMetadataTest,TimeWindowOutputSchemaTest"
```

Python mirror:

```powershell
cd D:\foggy-projects\foggy-data-mcp\foggy-data-mcp-bridge-python
pytest tests/compose/relation tests/compose/schema/test_column_spec_metadata.py -q
```

Before signoff:

```powershell
git diff --check
```

## Completion Gate

每个 Stage 7 子阶段完成后必须提供：

- changed files
- test commands and results
- snapshot / parity evidence
- `supportsOuterAggregate` / `supportsOuterWindow` 状态说明
- error code / fail-closed 行为说明
- quality self-check conclusion
- 是否可进入下一阶段的明确结论
