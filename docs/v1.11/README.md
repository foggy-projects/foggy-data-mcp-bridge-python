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
| P1 CALCULATE / formula parity | proposed | 需要清理当前活跃脏分支并补三库 oracle/refusal。 |
| P2 timeWindow evidence refresh | proposed | 旧证据存在，需要升级到当前版本总签收口径。 |
| P3 compose / stable relation runtime boundary | proposed | 需要确认 Python 是 runtime parity 还是 contract mirror。 |
| P4 governance cross-path matrix | proposed | 需要覆盖普通 query_model、timeWindow、pivot、compose。 |
| P5 version signoff | pending | 等 P1-P4 完成后签收。 |

## 文档清单

| File | Purpose |
|---|---|
| `P0-Java-Python-Engine-Parity-Audit.md` | 全引擎对齐审计、差距矩阵和优先级建议 |
| `P0-Java-Python-Engine-Parity-Execution-Plan.md` | 后续执行阶段、测试矩阵和质量门 |

## 外部基线

- Python Pivot v1.10 signoff: `docs/v1.10/acceptance/version-signoff.md`
- Python historical migration report: `docs/migration-progress.md`
- Java Pivot 9.1 signoff: `D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-wt-dev-compose/docs/9.1.0/acceptance/version-signoff.md`
- Java Pivot 9.2 follow-up roadmap: `D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-wt-dev-compose/docs/9.2.0/README.md`

## 当前结论

Pivot 维度已达到可签收对齐；全引擎维度还不能直接声明完全对齐。真正需要下一步投入的是 CALCULATE / timeWindow / compose stable relation / governance 的当前版本证据刷新，而不是继续扩展 Pivot runtime。
