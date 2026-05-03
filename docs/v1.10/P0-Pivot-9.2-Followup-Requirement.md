# P0 Pivot 9.2 Follow-Up Requirement

## 文档作用

- doc_type: requirement
- status: reviewed-for-p1-execution-prompt
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 定义 Python Pivot 9.2 follow-up 的目标、边界、非目标和验收标准。

## 背景

Python Pivot v1.9 已签收：

- flat/grid Pivot runtime。
- Stage 5A DomainTransport: SQLite / MySQL8 / PostgreSQL。
- Stage 5B C2 rows exactly two-level cascade TopN staged SQL。
- fail-closed guardrails: tree+cascade、columns cascade、derived metric cascade、unsupported dialect。

v1.9 明确延期：

- cascade subtotal / grandTotal。
- tree + cascade。
- SQL Server cascade oracle。
- MySQL 5.7 live/refusal evidence。
- outer Pivot cache。
- production telemetry / log-query examples。

## 与版本目标的关系

本需求支撑 Python v1.10，也就是 Python Pivot 9.2 follow-up。它不是重新实现 Pivot，也不扩展公开 DSL；它只处理 v1.9 签收风险中可独立验证、可独立验收的部分。

## 目标

1. 为 cascade subtotal / grandTotal 建立明确语义和真实 SQL oracle，若通过评审再实现。
2. 为 SQL Server cascade 建立方言 oracle 或明确 refusal evidence。
3. 为 MySQL 5.7 建立 live evidence 或明确继续 fail-closed 的依据。
4. 为 production telemetry/log-query 补齐可操作的运维证据说明。
5. 对 tree + cascade、outer Pivot cache 先做 feasibility/semantic review，不直接进入实现。

## 约束

- 不改变公开 Pivot JSON DSL。
- 不绕过 queryModel 生命周期、权限治理、systemSlice、deniedColumns、SQL sanitizer。
- cascade 仍禁止无证据的内存 fallback。
- unsupported 方言或语义不明时必须 fail-closed。
- 不宣称 MDX 兼容，只声明受控 Pivot DSL 子集能力。
- 实现前必须先有 oracle/refusal 测试设计；测试不能只验证代码形状。

## 非目标

- 不实现通用 MDX `CELL_AT` / `AXIS_MEMBER` / cross-axis coordinates。
- 不实现 three-level cascade。
- 不实现 columns-axis cascade。
- 不实现 non-additive cascade totals，除非单独需求和 oracle 先签收。
- 不把 compose/CTE 工具作为 queryModel 生命周期的替代入口。
- 不在没有性能/遥测证据前实现 outer Pivot cache。

## 验收标准

| Area | Acceptance |
|---|---|
| cascade subtotal/grandTotal | 有语义评审记录、三库 oracle parity、fail-closed 边界测试、质量门和签收记录 |
| SQL Server cascade | 有 SQL Server oracle parity 或明确 refusal tests；不得静默 fallback |
| MySQL 5.7 | 有 live evidence 或明确 refusal tests；不得冒充 MySQL8 |
| tree + cascade | 有语义评审结论；未通过前 runtime 继续拒绝 |
| telemetry | 有日志 marker / 查询示例 / 运维说明，且不泄露物理列或敏感参数 |
| public contract | schema/prompt 与实际能力一致，未开放未实现特性 |

## 成功定义

v1.10 不要求所有候选项都实现。成功定义是：

- P1/P2/P3/P6 中至少一个被实现并签收，或明确被拒绝/延期且证据充分。
- 所有未实现项都有稳定 fail-closed 行为和文档化边界。
- `pytest -q` 通过；涉及外部 DB 的阶段必须记录 profile、命令和 skipped/blocked 原因。
