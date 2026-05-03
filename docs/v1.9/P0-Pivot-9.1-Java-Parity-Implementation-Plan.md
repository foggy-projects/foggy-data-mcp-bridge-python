# P0 Pivot 9.1 Java Parity Implementation Plan

## 文档作用

- doc_type: implementation-plan
- intended_for: python-engine-agent / reviewer / signoff-owner
- purpose: 将 Java Pivot 9.1.0 parity 拆成 Python 侧可执行分期，明确哪些阶段可开工、哪些阶段必须等待前置证据。

## Ownership

| Owner | Responsibility |
|---|---|
| Root controller | 维护版本目标、评审计划、决定是否进入实现 |
| Python engine agent | 实施 Python v1.9 P1+ 代码和测试，回写 progress |
| Java reference repo | 提供 9.1.0 签收基线和 oracle 语义 |
| Quality reviewer | 执行 implementation quality gate |
| Coverage auditor | 执行 test coverage audit |
| Signoff owner | 执行 acceptance signoff，避免自评即签收 |

## Phase P0 - Documentation and Semantic Boundary Alignment

状态：当前文档包。

工作：

- 创建 Python v1.9 parity 文档。
- 对齐 Java 9.1.0 的 LLM routing / Stage 5A / Stage 5B C2 边界。
- 明确 Stage 5A/C2 不改变公开 DSL。
- 明确 P1 可开工，P2/P3/P4 gated。

完成定义：

- `docs/v1.9` 下文档齐全。
- 规划中区分 supported、fail-closed、deferred、blocked。

## Phase P1 - Validation / Fail-Closed Parity

状态：ready-to-start-after-review。

目标：

- 先阻断 Python 当前内存路径误执行 cascade。
- 对齐 Java 9.1.0 的 rewriteable refusal categories。

建议范围：

- 新增 cascade detector。
- 请求进入 cascade semantics 时执行 validation。
- 所有 cascade semantics 在 P1 先 fail-closed，不放行 staged SQL 执行。
- 现有 non-cascade S3 能力必须继续执行并通过回归测试，包括 flat/grid、单层 TopN、having、crossjoin。
- 明确拒绝：
  - missing `orderBy` on limited cascade level。
  - columns axis cascade。
  - rows cascade plus column limit/having。
  - three-level cascade。
  - having-only cascade。
  - tree + cascade。
  - non-additive cascade ranking/having/totals。
  - parentShare/baselineRatio + cascade。
  - unsupported dialect / missing SQL capability。
- cascade request 不得进入 `MemoryCubeProcessor`。

测试要求：

- unit validation tests 覆盖全部拒绝 shape。
- S3 单层 TopN/having/grid tests 不回归。
- MCP schema/prompt 不新增公开 DSL。

## Phase P2 - Managed Relation Lifecycle Feasibility

状态：gated。

目标：

- 判断 Python 是否能在 Pivot 内部生成 wrappable managed relation，并保留 queryModel 生命周期。

必须回答：

- 是否存在等价 Java `queryFacade.prepareManagedRelation/executeManagedRelation` 的入口。
- 是否能得到 stable output aliases、params、datasource、dialect、permission state。
- 是否能把 relation 包装为 CTE/subquery，且不生成 `FROM (WITH ...)`。
- 是否能保留 `fieldAccess/systemSlice/deniedColumns` 和 preAgg rewrite。
- 是否能在 SQL logging 和 sanitizer 中保持物理列不泄露。

若任一答案是否定：

- Stage 5A 和 C2 继续 blocked。
- 不允许直接拼最终 SQL 绕过 queryModel。

交付物与解锁门槛：

- 必须产出 `docs/v1.9/P1-Pivot-9.1-Managed-Relation-Feasibility.md` 或等价 feasibility record。
- record 必须列明 managed relation lifecycle 是否等价、证据来源、代码/测试探针、未覆盖风险和 signoff 结论。
- 未形成 reviewed feasibility record 前，P3 Stage 5A 和 P4 C2 均不得解锁。

## Phase P3 - Stage 5A Large-Domain Transport Parity

状态：blocked-by-P2。

目标：

- 当 non-additive subtotal/grandTotal surviving domain `> 500` 时，在安全方言 transport 存在时不因尺寸直接失败。

必须保留：

- 公开 DSL 不变。
- renderer unsupported/unsafe 时 fail-closed。
- NULL-safe tuple matching。
- params order 与 SQL render order 一致。
- SQLite/MySQL8/Postgres 真实 SQL oracle parity。

初始策略：

- P2 通过前，Python 继续 fail-closed。
- 可以先设计内部 `DomainTransport` 抽象，但默认实现只做 threshold refusal。

## Phase P4 - C2 Rows Two-Level Cascade SQL Parity

状态：blocked-by-P2。

目标：

- 实现 Java 9.1 C2 v1 子集：rows exactly two-level cascade TopN，additive metrics，explicit `orderBy`，staged SQL only。

执行规则：

- parent level: aggregate -> having -> rank -> limit。
- child level: constrained by surviving parent domain -> aggregate -> having -> rank -> limit。
- child having/limit 不影响 parent survival。
- deterministic ordering: metric NULL bucket + dimension NULL buckets + prefix/current key ASC。
- additive subtotal/grandTotal over surviving domain。
- no memory fallback。

拒绝：

- columns cascade。
- cross-axis cascade。
- three-level cascade。
- having-only cascade。
- tree + cascade。
- non-additive cascade ranking/having/totals。
- unsupported dialect。
- SQL planner failure。

## Phase P5 - Quality / Coverage / Acceptance

每个实现阶段完成后必须：

- 运行 targeted tests。
- 运行 `pytest -q`。
- 记录未运行的外部 DB profile 及原因。
- 执行 implementation self-check。
- 高风险阶段执行 formal quality gate。
- 执行 coverage audit。
- 创建 acceptance record。

## Required Oracle / Refusal Test Matrix

| Case | Expected | Profiles |
|---|---|---|
| Parent TopN + child TopN | child ranks only within surviving parents | SQLite/MySQL8/Postgres real SQL parity |
| Parent ranking ignores child limit | parent aggregate uses full current-level domain | SQLite/MySQL8/Postgres real SQL parity |
| Parent having before child rank | parent domain filtered before child stage | SQLite/MySQL8/Postgres real SQL parity |
| Child having does not affect parent | child filter only removes child members | SQLite/MySQL8/Postgres real SQL parity |
| Missing `orderBy` | reject | unit |
| Deterministic NULL tie-breaking | stable cross-dialect ordering | SQLite/MySQL8/Postgres real SQL parity |
| Additive subtotal/grandTotal surviving domain | totals over surviving domain only | SQLite/MySQL8/Postgres real SQL parity |
| Unsupported dialect | reject, no memory fallback | unit / simulated MySQL5.7 |
| Non-additive cascade | reject | unit |
| Tree + cascade | reject | unit |

## Python 9.2.0 Follow-Up Alignment

Move these out of Python v1.9 unless separately accepted:

- tree + cascade / advanced tree subtotal semantics。
- SQL Server cascade oracle / CI。
- MySQL 5.7 live evidence。
- outer Pivot cache。
- production telemetry dashboards/log-query examples。
