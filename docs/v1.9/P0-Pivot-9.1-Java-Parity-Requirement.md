# P0 Pivot 9.1 Java Parity Requirement

## 文档作用

- doc_type: requirement
- intended_for: root-controller / python-engine-agent / reviewer
- purpose: 定义 Python 引擎对齐 Java Pivot 9.1.0 的目标、约束、非目标、验收标准和 fail-closed 边界。

## 背景

Java Pivot Engine 9.1.0 RC2 已签收，签收原则是 correctness-first and LLM-safe：当语义或执行能力不能证明时，必须 fail closed，并给出可改写的错误提示，不能返回 best-effort 结果。

Python v1.8 已完成 Pivot S1-S3：

- `pivot` Pydantic DTO 与 MCP schema 合同。
- `outputFormat=flat/grid`。
- native metrics。
- rows/columns 降维。
- axis `having/orderBy/limit`。
- grid `rowHeaders/columnHeaders/cells`。
- crossjoin matrix fill。
- `slice/systemSlice/deniedColumns` 通过真实 SQL oracle parity 覆盖。

但 Python 当前的 Pivot 执行仍是“queryModel 基础聚合后，在内存执行 axis 操作和 shaping”。这可以支撑单层 TopN / having / grid shaping，但不能自动等价于 Java 9.1.0 的 staged SQL cascade 和 large-domain transport。

## 与版本目标的关系

本需求支撑 Python v1.9 的 Java Pivot 9.1 parity 规划。它不替代 v1.8 S4/S5 的 `properties/subtotal/non-additive/derived metrics/tree` 规划，但需要重新排序：任何 cascade 或 large-domain transport 能力都必须先满足 queryModel lifecycle 与真实 SQL oracle 证据。

## 目标

1. 对齐 Java 9.1.0 的公开语义边界，不改变 Python 公开 Pivot DSL。
2. 先补齐 Python 对 unsupported cascade shape 的 fail-closed 行为。
3. 明确 Stage 5A 和 C2 在 Python 侧的前置条件：必须保留 queryModel lifecycle、权限、systemSlice、deniedColumns、preAgg、参数顺序、SQL sanitizer/logging。
4. 建立 SQLite/MySQL8/Postgres 的真实 SQL oracle 测试矩阵。
5. 将 tree + cascade、cross-axis cascade、three-level cascade、having-only cascade、non-additive cascade totals、SQL Server cascade、MySQL 5.7 cascade 移入 refused/deferred 边界，除非后续有单独 oracle 覆盖。

## 约束

- 不改公开 Pivot DSL、JSON schema request shape 或 result shape，除非另有产品需求批准。
- 不声明 MDX compatibility。
- 不允许 CTE/compose 工具绕过 queryModel 生命周期访问模型数据。
- `timeWindow + pivot` 必须继续拒绝。
- cascade 请求不能走当前内存 fallback。
- 无真实 SQL oracle 覆盖的 cascade / transport 能力不得签收。
- 若 Python 没有等价 managed relation lifecycle，Stage 5A 和 C2 实现必须标记为 blocked，而不是降级到直接拼 SQL。

## 非目标

- 不开放 `CELL_AT` / `AXIS_MEMBER`。
- 不开放公开 `ROLLUP_TO` function string。
- 不实现 arbitrary MDX set algebra。
- 不在本阶段实现 tree + cascade。
- 不在本阶段实现 SQL Server cascade。
- 不在本阶段承诺 MySQL 5.7 live cascade support。
- 不把 current memory TopN 视为 Java 9.1 C2 等价实现。

## Python 9.1 Capability Gap Matrix

| Java 9.1 capability | Python current status | Python v1.9 decision |
|---|---|---|
| LLM routing matrix | aligned in v1.9 docs | P0 complete; no tool schema change |
| `query_model` lifecycle preservation | verified for scoped transport/cascade paths | P2 feasibility complete; scoped implementation preserves queryModel base-query lifecycle |
| Stage 5A large-domain transport | implemented for SQLite/MySQL8/PostgreSQL | P3 signed off with real SQL oracle parity |
| DomainTransport public DSL | Java 无公开 DSL | Python 不新增公开 DSL |
| rows two-level cascade C2 | implemented for scoped rows exactly two-level TopN | P4 signed off with risks; cascade totals deferred |
| cascade no memory fallback | implemented | Unsupported shapes fail closed before memory processing |
| deterministic NULL tie-breaking | implemented for scoped cascade | P4 covered by semantic and real DB oracle tests |
| additive subtotal / grandTotal over surviving domain | missing for cascade | deferred to Python 9.2; not part of scoped P4 CTE generation signoff |
| unsupported cascade error codes | implemented | Stable `PIVOT_CASCADE_*` prefixes are covered by tests |
| SQL Server cascade | Java deferred/refused | Python deferred/refused |
| MySQL 5.7 cascade | Java refused/deferred evidence | Python refused/deferred |

## 验收标准

P0/P1 验收：

- 文档清楚说明 Python 9.1 parity 的支持、拒绝、延后边界。
- cascade detector 能识别并拒绝 C2 v1 之外的 shape。
- cascade 请求不会进入 `MemoryCubeProcessor` 当前内存路径。
- 拒绝测试覆盖 exact error code 或稳定错误前缀。
- 现有 S1-S3 flat/grid oracle parity 不回归。

P2 之后的实现验收：

- 任何 Stage 5A/C2 运行时能力必须有 SQLite/MySQL8/Postgres 真实 SQL oracle parity。
- 权限、`systemSlice`、`deniedColumns`、params order、preAgg/sanitizer/logging 不能绕过。
- quality gate、coverage audit、acceptance signoff 必须独立落文档。
- Cascade subtotal / grandTotal parity is excluded from the scoped Python P4 signoff and must remain deferred until Python has explicit subtotal-row oracle coverage.
