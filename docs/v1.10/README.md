# v1.10 - Python Pivot 9.2 Follow-Up Planning

## 文档作用

- doc_type: workitem-group
- status: reviewed-for-p1-execution-prompt
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 跟踪 Python Pivot 9.2 对 v1.9 accepted-with-risks 遗留项的规划、实施、测试覆盖与验收边界。

## 背景

Python Pivot v1.9 已完成 Stage 5A DomainTransport 与 Stage 5B C2 rows 轴两级 cascade staged SQL，并以 `accepted-with-risks` 签收。v1.10 聚焦 v1.9 明确延期的 9.2 follow-up，不改变公开 Pivot DSL。

核心原则继续沿用 Java 9.1/9.2 路线：语义和执行能力无法证明时必须 fail-closed，不能用内存 fallback 或普通 `groupBy` 近似替代。

## 进度总览

| 功能 | 状态 | 备注 |
|---|---|---|
| P0 文档与边界对齐 | reviewed | 文档包已通过评审，可进入 P1 execution prompt。 |
| P1 cascade subtotal/grandTotal 语义与 oracle | accepted | additive rowSubtotals / grandTotal over surviving rows cascade domain 已签收。 |
| P2 SQL Server cascade oracle / refusal evidence | accepted-refusal | SQL Server C2 cascade 稳定 fail-closed；不声明 oracle parity。 |
| P3 MySQL 5.7 live evidence / refusal evidence | proposed | 不默认启用 cascade；先确认环境与能力。 |
| P4 tree + cascade semantic review | deferred | 高风险语义项，先评审，不直接实现。 |
| P5 outer Pivot cache feasibility | deferred | 等 telemetry/性能证据证明需要。 |
| P6 production telemetry examples | proposed | 低风险文档/运维项，可与 P1/P2 并行。 |

## 文档清单

| 文件 | 用途 |
|---|---|
| `P0-Pivot-9.2-Followup-Requirement.md` | 需求、约束、非目标、验收标准 |
| `P0-Pivot-9.2-Followup-Implementation-Plan.md` | 分期实施计划、测试矩阵、质量门 |
| `P0-Pivot-9.2-Followup-Code-Inventory.md` | Python/Java 参考代码与预期改动范围 |
| `P0-Pivot-9.2-Followup-progress.md` | 后续执行 agent 的进度回写模板 |
| `acceptance/pivot-9.2-cascade-totals-acceptance.md` | P1 cascade totals 签收记录 |
| `coverage/pivot-9.2-cascade-totals-coverage-audit.md` | P1 测试覆盖审计 |
| `quality/pivot-9.2-cascade-totals-quality.md` | P1 实现质量门 |
| `acceptance/pivot-9.2-sqlserver-cascade-refusal-acceptance.md` | P2 SQL Server cascade 拒绝签收记录 |
| `coverage/pivot-9.2-sqlserver-cascade-refusal-coverage-audit.md` | P2 拒绝路径覆盖审计 |
| `quality/pivot-9.2-sqlserver-cascade-refusal-quality.md` | P2 实现质量门 |

## 外部基线

- Python v1.9 release readiness: `docs/v1.9/acceptance/python-pivot-9.1-release-readiness.md`
- Python v1.9 Stage 5B acceptance: `docs/v1.9/acceptance/pivot-stage5b-c2-cascade-acceptance.md`
- Java 9.2 follow-up roadmap: `D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-wt-dev-compose/docs/9.2.0/README.md`
