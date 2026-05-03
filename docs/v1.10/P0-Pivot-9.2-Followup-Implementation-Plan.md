# P0 Pivot 9.2 Follow-Up Implementation Plan

## 文档作用

- doc_type: implementation-plan
- status: reviewed-for-p1-execution-prompt
- intended_for: python-engine-agent / reviewer / signoff-owner
- purpose: 将 Python Pivot 9.2 follow-up 拆成可评审、可独立签收的阶段。

## Ownership

| Owner | Responsibility |
|---|---|
| Root controller | 维护 v1.10 目标、评审阶段计划、决定是否进入实现 |
| Python engine agent | 实施被批准阶段、补测试、回写 progress |
| Java reference repo | 提供 9.2 follow-up 语义边界和 Java oracle 参考 |
| Quality reviewer | 执行 implementation quality gate |
| Coverage auditor | 执行 test coverage audit |
| Signoff owner | 执行 acceptance signoff |

## Phase P0 - Documentation and Boundary Alignment

状态：当前文档包。

工作：

- 创建 `docs/v1.10` planning package。
- 对齐 Python v1.9 accepted-with-risks 与 Java 9.2 follow-up。
- 明确 P1 可优先评审，P4/P5 继续 gated。

完成定义：

- requirement / implementation plan / code inventory / progress template 齐全。
- 每个 follow-up 都标注 supported / proposed / deferred / refused / blocked。

## Phase P1 - Cascade Subtotal / GrandTotal Semantic Review and Implementation

优先级：P1。

目标：

- 在 v1.9 已支持的 rows exactly two-level cascade surviving domain 上，定义 additive subtotal / grandTotal 的结果语义。
- 仅在语义评审和 oracle 通过后实现。

候选范围：

- 仅支持 `outputFormat=grid` 或 `flat` 中已经存在的非 tree result shape。
- 仅支持 additive native metrics。
- 仅支持 rows 轴 C2 cascade surviving domain。
- subtotal/grandTotal 必须基于 surviving domain，不包含被 TopN/having 剔除的成员。

必须拒绝：

- tree + cascade subtotal。
- columns cascade subtotal。
- non-additive metrics。
- derived metrics (`parentShare` / `baselineRatio`)。
- three-level cascade。

测试要求：

- SQLite/MySQL8/PostgreSQL 三库真实 SQL oracle parity。
- parent subtotal over surviving children。
- grandTotal over surviving parent+child domain。
- filtered-out parent/child 不进入 totals。
- empty surviving domain 的空结果/总计行为明确。
- options false 时不生成 subtotal rows。

## Phase P2 - SQL Server Cascade Oracle / Refusal Evidence

优先级：P2，可与 P1 并行做探针。

目标：

- 判断 SQL Server 是否能安全支持 v1.9 C2 staged SQL。
- 若支持，补 SQL Server oracle parity；若不支持，补稳定 refusal tests 和 prompt/schema 说明。

必须确认：

- SQL Server NULL-safe tuple matching shape。
- ROW_NUMBER deterministic ordering。
- params order。
- identifier quoting。
- real DB profile 是否可用。

完成定义：

- SQL Server integration test profile 0 skipped 通过，或 refusal tests 明确覆盖。
- 不影响 SQLite/MySQL8/Postgres 现有 parity。

## Phase P3 - MySQL 5.7 Live / Refusal Evidence

优先级：P3。

目标：

- 判断 MySQL 5.7 是否仍是 Python Pivot cascade 支持范围。
- 如果不支持窗口函数/CTE shape，则保持 fail-closed，并补 live/refusal evidence。

完成定义：

- 明确 MySQL 5.7 与 MySQL8 profile 区分。
- 超出能力时返回稳定错误，不伪装成 MySQL8。
- Stage 5A DomainTransport large-domain 行为有 threshold/refusal 证据。

## Phase P4 - Tree + Cascade Semantic Review

优先级：deferred / semantic review only。

目标：

- 只评审，不直接实现。
- 讨论 parent/child ranking、descendants、visible nodes、subtotal/tree totals 是否能定义成 LLM-safe 语义。

继续拒绝：

- 评审结论未签收前，`tree+cascade` runtime 必须保持 fail-closed。

## Phase P5 - Outer Pivot Cache Feasibility

优先级：deferred。

目标：

- 等 P6 telemetry 有数据后再评估。
- 定义 cache key、permission/systemSlice 参与方式、invalidation、result-shape 兼容性。

非目标：

- 不在没有性能证据前实现。

## Phase P6 - Production Telemetry / Log Query Examples

优先级：P2。

目标：

- 补充运维视角的日志 marker / 查询示例 / refusal 分类说明。
- 支撑后续 cache 和生产问题定位。

要求：

- 不泄露物理列、敏感参数或用户输入明文。
- 能区分 DomainTransport refusal、cascade refusal、unsupported dialect、oracle profile skipped。

## Required Test Matrix

| Case | P1 | P2 | P3 | Expected |
|---|---:|---:|---:|---|
| cascade row subtotal over surviving child domain | yes | optional | optional | SQL oracle parity |
| cascade grandTotal over surviving domain | yes | optional | optional | SQL oracle parity |
| filtered-out parent excluded from totals | yes | optional | optional | SQL oracle parity |
| filtered-out child excluded from parent subtotal | yes | optional | optional | SQL oracle parity |
| non-additive cascade totals | yes | optional | optional | reject |
| tree + cascade + totals | yes | optional | optional | reject |
| SQL Server C2 cascade | no | yes | no | parity or stable refusal |
| MySQL 5.7 C2 cascade | no | no | yes | stable refusal unless evidence proves support |
| existing SQLite/MySQL8/Postgres cascade | yes | yes | yes | no regression |

## Quality Gates

每个实现阶段完成后必须：

- 运行 targeted tests。
- 运行 `pytest -q`。
- 记录外部 DB profile 结果；不可用时写 blocked，不写 passed。
- 执行 implementation self-check。
- 高风险阶段执行 formal quality gate。
- 执行 coverage audit。
- 创建 feature acceptance record。
