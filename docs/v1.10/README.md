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
| P3 MySQL 5.7 live evidence / refusal evidence | accepted-refusal | 显式 `mysql5.7` cascade / large-domain transport 稳定 fail-closed；不声明 oracle parity。 |
| P4 tree + cascade semantic review | accepted-deferred | 已完成语义评审；runtime 继续 `PIVOT_CASCADE_TREE_REJECTED`。 |
| P5 outer Pivot cache feasibility | accepted-deferred | 已完成 feasibility；不新增 runtime cache，等待 telemetry 和权限安全 cache key 规格。 |
| P6 production telemetry examples | accepted-docs | 已补生产日志 marker、查询示例、拒绝分类和隐私规则。 |

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
| `acceptance/pivot-9.2-mysql57-refusal-acceptance.md` | P3 MySQL 5.7 拒绝签收记录 |
| `coverage/pivot-9.2-mysql57-refusal-coverage-audit.md` | P3 拒绝路径覆盖审计 |
| `quality/pivot-9.2-mysql57-refusal-quality.md` | P3 实现质量门 |
| `operations/pivot-9.2-telemetry-log-query-examples.md` | P6 生产日志查询与排障示例 |
| `acceptance/pivot-9.2-telemetry-docs-acceptance.md` | P6 文档签收记录 |
| `coverage/pivot-9.2-telemetry-docs-coverage-audit.md` | P6 文档覆盖审计 |
| `quality/pivot-9.2-telemetry-docs-quality.md` | P6 文档质量门 |
| `acceptance/pivot-9.2-tree-cascade-semantic-review.md` | P4 tree+cascade 语义评审结论 |
| `coverage/pivot-9.2-tree-cascade-semantic-coverage-audit.md` | P4 语义评审覆盖审计 |
| `quality/pivot-9.2-tree-cascade-semantic-quality.md` | P4 语义评审质量门 |
| `acceptance/pivot-9.2-outer-cache-feasibility.md` | P5 outer Pivot cache 可行性结论 |
| `coverage/pivot-9.2-outer-cache-feasibility-coverage-audit.md` | P5 可行性覆盖审计 |
| `quality/pivot-9.2-outer-cache-feasibility-quality.md` | P5 可行性质量门 |

## 外部基线

- Python v1.9 release readiness: `docs/v1.9/acceptance/python-pivot-9.1-release-readiness.md`
- Python v1.9 Stage 5B acceptance: `docs/v1.9/acceptance/pivot-stage5b-c2-cascade-acceptance.md`
- Java 9.2 follow-up roadmap: `D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-wt-dev-compose/docs/9.2.0/README.md`
