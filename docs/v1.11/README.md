# v1.11 - Java/Python Engine Parity Audit

## 文档作用

- doc_type: workitem-group
- status: draft-audit
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 跟踪 Python 引擎与 Java 引擎在 query_model、CALCULATE、timeWindow、pivot、compose、governance、dialect 维度的对齐差距和下一步执行顺序。

## 背景

Python Pivot v1.10 已按 Java Pivot 9.2 follow-up 边界完成签收，结论为 `accepted-with-risks`。Pivot 主线已经达到“支持项有 oracle、未支持项 fail-closed/deferred”的对齐状态。

v1.11 的目标不是继续扩 Pivot，而是把注意力扩大到整个 Python engine：确认哪些 Java 能力已经 runtime 对齐，哪些只是 contract mirror，哪些需要补证据或补实现。

## 进度总览

| Area | Status | Notes |
|---|---|---|
| P0 parity audit | draft-audit | 已建立首版差距矩阵和执行建议。 |
| P1 CALCULATE / formula parity | accepted-with-profile-note | 受限 CALCULATE 已补 SQLite/MySQL8/PostgreSQL oracle；默认 mysql profile 继续 fail-closed。 |
| P2 timeWindow evidence refresh | accepted | 当前 main 已重跑 timeWindow + SQLite/MySQL8/PostgreSQL/SQL Server 证据矩阵。 |
| P3 compose / stable relation runtime boundary | accepted-with-runtime-boundary | compose runtime 与 MCP path 已验收；stable relation S7e/S7f 为 contract mirror，不宣称 Python runtime parity。 |
| P4 governance cross-path matrix | accepted | 已覆盖 base query_model、timeWindow、pivot、compose 与 MCP router governance 透传。 |
| P5 version signoff | pending | P1-P4 已完成，下一步生成版本级签收。 |

## 文档清单

| File | Purpose |
|---|---|
| `P0-Java-Python-Engine-Parity-Audit.md` | 全引擎对齐审计、差距矩阵和优先级建议 |
| `P0-Java-Python-Engine-Parity-Execution-Plan.md` | 后续执行阶段、测试矩阵和质量门 |
| `acceptance/calculate-formula-parity-acceptance.md` | P1 CALCULATE / formula parity 签收 |
| `coverage/calculate-formula-parity-coverage-audit.md` | P1 测试覆盖审计 |
| `quality/calculate-formula-parity-quality.md` | P1 实现质量记录 |
| `acceptance/timewindow-current-parity-acceptance.md` | P2 timeWindow 当前证据签收 |
| `coverage/timewindow-current-parity-coverage-audit.md` | P2 测试覆盖审计 |
| `quality/timewindow-current-parity-quality.md` | P2 质量记录 |
| `acceptance/compose-stable-relation-boundary-acceptance.md` | P3 compose/stable relation 边界签收 |
| `coverage/compose-stable-relation-boundary-coverage-audit.md` | P3 测试覆盖审计 |
| `quality/compose-stable-relation-boundary-quality.md` | P3 质量记录 |
| `acceptance/governance-cross-path-acceptance.md` | P4 governance 横向矩阵签收 |
| `coverage/governance-cross-path-coverage-audit.md` | P4 测试覆盖审计 |
| `quality/governance-cross-path-quality.md` | P4 质量记录 |

## 外部基线

- Python Pivot v1.10 signoff: `docs/v1.10/acceptance/version-signoff.md`
- Python historical migration report: `docs/migration-progress.md`
- Java Pivot 9.1 signoff: `D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-wt-dev-compose/docs/9.1.0/acceptance/version-signoff.md`
- Java Pivot 9.2 follow-up roadmap: `D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-wt-dev-compose/docs/9.2.0/README.md`

## 当前结论

Pivot 维度已达到可签收对齐；P1 CALCULATE / formula、P2 timeWindow、P3 compose/stable relation boundary、P4 governance cross-path matrix 已完成当前版本证据签收。下一步是 v1.11 version signoff，而不是继续扩展 Pivot runtime。
