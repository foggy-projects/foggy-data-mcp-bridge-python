# P0 Java/Python Parity Follow-Up Confirmation

## 文档作用

- doc_type: workitem
- status: proposed
- intended_for: product-owner / root-controller / python-engine-agent / java-engine-agent / reviewer
- purpose: 将 v1.15 parity baseline 中剩余的测试和功能缺口分配到合适迭代，供逐项确认。

## Version

- version: v1.16
- priority: P0 planning / confirmation
- source type: acceptance follow-up
- owning repo: `foggy-data-mcp-bridge-python`
- Java reference repo: `foggy-data-mcp-bridge-wt-dev-compose`

## Background

v1.15 已确认 Python engine 与 Java engine 在当前已签收 public/runtime 范围内对齐。剩余项不是当前缺陷，而是后续是否扩展支持范围的确认问题。

本文件的目标是避免后续执行时混淆三类事情：

- 只需要补测试证据的项。
- 需要先做语义设计的项。
- 当前应继续拒绝或延期的项。

## Follow-Up Matrix

| ID | Problem | Suggested Iteration | Current Boundary | Confirmation Needed |
|---|---|---|---|---|
| JP-FU-01 | CALCULATE SQL Server oracle | v1.16 P1 | Python CALCULATE 已签 SQLite/MySQL8/PostgreSQL；SQL Server 未作为显式 claim | 是否要把 SQL Server CALCULATE 升级为公开 parity claim？ |
| JP-FU-02 | Stable relation join / union as source | v1.16 P2 | 当前只签 outer aggregate/window | 是否有真实业务需要把 join/union relation 作为后续 relation source？ |
| JP-FU-03 | Pivot SQL Server cascade oracle | v1.17 P1 | Java/Python 均拒绝或延期 | 是否要实现 SQL Server staged cascade renderer，还是继续拒绝？ |
| JP-FU-04 | Pivot MySQL 5.7 live evidence | v1.17 P2 | Java/Python 均不继承 MySQL8 证据 | 是否仍支持 MySQL 5.7，还是明确从 cascade/domain transport 支持范围移除？ |
| JP-FU-05 | tree+cascade semantic spec | v1.18 P1 | Java/Python 均拒绝或延期 | 是否要投入语义设计，定义可证明的 tree ranking / subtotal / visible domain 规则？ |
| JP-FU-06 | outer Pivot cache | v1.19 P1 | feasibility only, no runtime cache | 是否有生产 telemetry 证明缓存收益足以覆盖权限安全和失效复杂度？ |

## Item Details

### JP-FU-01 CALCULATE SQL Server Oracle

Suggested iteration: v1.16 P1.

Current state:

- Python v1.11 signs restricted `CALCULATE(SUM(metric), REMOVE(dim))`.
- Existing oracle matrix covers SQLite, MySQL8, and PostgreSQL.
- SQL Server timeWindow and stable relation outer evidence exists, but CALCULATE SQL Server is not a signed claim.

Decision options:

- `accept-evidence-work`: add SQL Server real DB oracle tests for restricted CALCULATE.
- `defer`: keep current claim unchanged.
- `reject`: state that SQL Server CALCULATE is not in public parity scope.

Required tests if accepted:

- SQL Server grouped aggregate window oracle for global share.
- SQL Server grouped aggregate window oracle for partitioned share.
- SQL Server refusal for unsupported nested / non-grouped REMOVE cases.
- Full regression after adding tests.

Non-goals:

- No expansion beyond restricted CALCULATE.
- No nested CALCULATE or arbitrary MDX coordinate behavior.

### JP-FU-02 Stable Relation Join / Union As Source

Suggested iteration: v1.16 P2.

Current state:

- Python v1.12-v1.14 signs stable relation outer aggregate/window runtime.
- The signed scope does not include stable relation join/union as a downstream source.

Decision options:

- `require-design`: write a dedicated stable relation source design before implementation.
- `defer`: keep outer aggregate/window as the only signed runtime path.
- `reject`: explicitly state join/union relation source is out of scope.

Required tests if accepted:

- SQLite/MySQL8/PostgreSQL/SQL Server oracle for join source.
- SQLite/MySQL8/PostgreSQL/SQL Server oracle for union source.
- Governance propagation tests for systemSlice, deniedColumns, fieldAccess, and masking.
- SQL sanitizer and parameter order tests across nested relation layers.

Non-goals:

- No raw SQL escape hatch.
- No bypass of compose/queryModel authority envelope.

### JP-FU-03 Pivot SQL Server Cascade Oracle

Suggested iteration: v1.17 P1.

Current state:

- Java 9.1 / 9.2 lists SQL Server cascade as refused/deferred.
- Python v1.10 signs SQL Server cascade refusal.

Decision options:

- `align-with-java-implementation`: only start after Java accepts SQL Server oracle.
- `python-prototype`: Python prototypes renderer but does not claim parity until Java/product accepts.
- `continue-refusal`: keep stable `PIVOT_CASCADE_SQL_REQUIRED` refusal.

Required tests if accepted:

- SQL Server two-level rows cascade oracle.
- Parent ranking ignores child limit.
- Parent having before child rank.
- Child having does not affect parent.
- Deterministic NULL tie-breaking.
- Additive subtotal/grandTotal over surviving domain.
- Unsupported tree/cross-axis/three-level/non-additive cases continue to fail closed.

Non-goals:

- No memory fallback for cascade.
- No general MDX Generate support.

### JP-FU-04 Pivot MySQL 5.7 Live Evidence

Suggested iteration: v1.17 P2.

Current state:

- Java documents MySQL 5.7 as guarded/fail-closed or live-evidence gap.
- Python v1.10 signs explicit MySQL5.7 refusal tests.

Decision options:

- `live-refusal-evidence`: add real MySQL5.7 fixture proving stable refusal.
- `support-limited-transport`: design non-window fallback only where semantics allow.
- `drop-support`: document MySQL5.7 as unsupported for cascade/domain transport.

Required tests if accepted:

- Live MySQL5.7 refusal before SQL execution for cascade.
- Live MySQL5.7 large-domain transport refusal or limited transport oracle.
- MySQL8 tests proving no profile regression.

Non-goals:

- Do not emulate MySQL8 window semantics on MySQL5.7 without a signed algorithm.
- Do not relabel MySQL5.7 as MySQL8 based on executor class.

### JP-FU-05 tree+cascade Semantic Spec

Suggested iteration: v1.18 P1.

Current state:

- Java and Python both reject tree+cascade.
- Python v1.10 has semantic review and runtime refusal, but no implementation.

Decision options:

- `semantic-design`: define tree ranking, visible nodes, descendant aggregation, subtotal behavior, and oracle matrix.
- `defer`: keep fail-closed.
- `reject`: state tree+cascade is outside Pivot DSL design.

Required tests if accepted:

- Parent/child visible-domain oracle.
- Ranking with hidden descendants.
- Tree subtotal over visible vs full descendant domain decision tests.
- Cross-dialect SQL oracle or explicit unsupported dialect refusals.
- Backward compatibility tests for non-cascade tree behavior.

Non-goals:

- No implementation before semantic signoff.
- No best-effort tree flattening as substitute.

### JP-FU-06 outer Pivot Cache

Suggested iteration: v1.19 P1.

Current state:

- Java 9.2 tracks outer Pivot cache as deferred.
- Python v1.10 feasibility concludes no runtime cache until telemetry and permission-safe key are signed.

Decision options:

- `telemetry-first`: collect query cost/repetition evidence before implementation.
- `design-cache-key`: define permission-aware cache key and invalidation model.
- `defer`: keep no outer cache.

Required tests if accepted:

- Cache key includes model, pivot request, user-visible permissions, systemSlice, deniedColumns, dialect, and relevant model version.
- Cache does not leak data across authority envelopes.
- Invalidation tests for model/schema changes.
- Hit/miss telemetry tests.
- Performance baseline before/after.

Non-goals:

- No cache keyed only by raw request JSON.
- No cache that ignores permissions or system slices.

## Ownership

| Area | Primary Owner | Secondary Owner |
|---|---|---|
| CALCULATE SQL Server oracle | Python engine | Java alignment reviewer |
| Stable relation join/union source | Python engine / compose owner | governance reviewer |
| Pivot SQL Server cascade | Java Pivot first, then Python mirror | dialect owner |
| Pivot MySQL5.7 evidence | dialect owner | Python/Java engine owners |
| tree+cascade semantic spec | product / semantic owner | Java/Python Pivot owners |
| outer Pivot cache | performance/cache owner | governance reviewer |

## Acceptance Criteria

- Each item has an explicit decision: `accepted-for-implementation`, `evidence-only`, `deferred`, or `rejected`.
- Any item accepted for implementation has a dedicated requirement, implementation plan, progress tracker, quality gate, coverage audit, and acceptance record.
- Any item deferred or rejected keeps stable fail-closed behavior and public docs do not claim support.
- No item changes public DSL without separate product approval.

## Progress Tracking

Development progress:

| Step | Status | Notes |
|---|---|---|
| Create follow-up intake docs | done | v1.16 docs created. |
| Confirm JP-FU-01 | pending | Await product/engineering decision. |
| Confirm JP-FU-02 | pending | Await product/engineering decision. |
| Confirm JP-FU-03 | pending | Depends on Java/Product SQL Server cascade decision. |
| Confirm JP-FU-04 | pending | Depends on MySQL5.7 support policy. |
| Confirm JP-FU-05 | pending | Needs semantic review. |
| Confirm JP-FU-06 | pending | Needs telemetry/performance signal. |

Testing progress:

| Scope | Status | Notes |
|---|---|---|
| Current v1.15 regression | passed | `pytest -q` -> `3977 passed`. |
| New runtime tests | N/A | This is planning-only; no runtime code added. |
| Future per-item oracle tests | pending | Listed under each item. |

Experience progress:

- N/A. These are backend/query-engine planning items with no UI workflow.

## Constraints / Non-Goals

- Do not implement these items from this intake document alone.
- Do not change MCP schema or public prompt claims until an item is accepted and tested.
- Do not convert refusal/deferred items into silent fallback behavior.
- Do not claim Java/Python parity for a dialect without executable oracle or explicit refusal evidence.

## Required Review Workflow

For each item that moves beyond confirmation:

1. Generate a dedicated requirement / plan package.
2. Review with `plan-evaluator`.
3. Execute implementation if approved.
4. Run `foggy-implementation-quality-gate`.
5. Run `foggy-test-coverage-audit`.
6. Run `foggy-acceptance-signoff`.
