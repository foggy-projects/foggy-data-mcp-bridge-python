# v1.9 - Pivot 9.1 Java Parity Planning

## 文档作用

- doc_type: workitem-group
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 跟踪 Java Pivot Engine 9.1.0 已签收优化向 Python 引擎镜像迁移的规划、实施、测试覆盖与验收边界。

## 背景

Java Pivot Engine 9.1.0 RC2 已签收，核心新增边界包括：

- Stage 5A large-domain transport：内部 `DomainTransportPlan` / `DomainRelationRenderer`，不改变公开 Pivot DSL。
- Stage 5B C2 cascade Generate：仅支持 rows 轴 exactly two-level cascade TopN，必须走 staged SQL，禁止当前内存 fallback。
- LLM query tool capability matrix：明确 `query_model`、`timeWindow`、`pivot`、CTE/compose 的路由边界。

Python 当前已完成 v1.8 S1-S3：Pivot 合同层、flat/grid runtime、axis having/orderBy/limit、crossjoin，并通过 SQLite/MySQL8/Postgres 真实 SQL oracle parity。Python 仍缺少 Java 9.1 的 Stage 5A/C2 运行时能力。

## 进度总览

| 功能 | 状态 | 备注 |
|---|---|---|
| P0 文档与边界对齐 | done | 本目录定义 Python 9.1 parity 的目标、非目标、测试矩阵和执行门。 |
| P1 validation / fail-closed parity | done | Cascade 检测与拒绝边界已实现，禁止当前内存路径误执行 unsupported cascade。 |
| P2 managed relation lifecycle feasibility | done | Feasibility 结论为 conditional-pass。 |
| P3 Stage 5A large-domain transport parity | done | SQLite/MySQL8/PostgreSQL real SQL oracle parity 已签收。 |
| P4 C2 rows two-level cascade SQL parity | signed-off-with-risks | Scoped rows two-level cascade staged SQL 已签收；cascade totals defer 到 9.2。 |
| P5 quality / coverage / acceptance | signed-off | P4 quality gate, coverage audit, and feature acceptance are complete. |

## 文档清单

| 文件 | 用途 |
|---|---|
| `P0-Pivot-9.1-Java-Parity-Requirement.md` | 需求、约束、非目标、签收标准 |
| `P0-Pivot-9.1-Java-Parity-Implementation-Plan.md` | 分期实施计划、测试矩阵、9.2.0 延后项 |
| `P0-Pivot-9.1-Java-Parity-Code-Inventory.md` | Python/Java 参考代码与预期改动范围 |
| `P0-Pivot-9.1-Java-Parity-progress.md` | 后续执行 agent 的进度回写模板 |
| `quality/pivot-stage5b-c2-cascade-implementation-quality.md` | P4 implementation quality gate |
| `coverage/pivot-stage5b-c2-cascade-coverage-audit.md` | P4 test coverage audit |
| `acceptance/pivot-stage5b-c2-cascade-acceptance.md` | P4 feature acceptance signoff |

## 外部基线

- Java accepted closeout commit: `10e863e9 docs(pivot): sign off 9.1.0 rc2 and track 9.2.0 followups`
- Java C2 tag: `v9.1.0-rc.2`
- Python current baseline: `docs/v1.8/P0-Pivot-V9-Python-Parity-Gap-Report.md`
