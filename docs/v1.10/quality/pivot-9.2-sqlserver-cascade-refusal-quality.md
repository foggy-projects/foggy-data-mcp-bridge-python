# Pivot 9.2 SQL Server Cascade Refusal Quality Gate

## 文档作用

- doc_type: implementation-quality-gate
- status: passed
- intended_for: quality-reviewer / signoff-owner
- purpose: 记录 Python Pivot v1.10 P2 SQL Server cascade refusal 的实现质量检查结论。

## Scope Checked

Runtime changes:

- `src/foggy/dataset_model/semantic/pivot/cascade_staged_sql.py`
- `src/foggy/dataset_model/semantic/service.py`

Tests changed:

- `tests/integration/test_pivot_v9_cascade_sqlserver_matrix.py`

Docs changed:

- `docs/v1.10/acceptance/pivot-9.2-sqlserver-cascade-refusal-acceptance.md`
- `docs/v1.10/coverage/pivot-9.2-sqlserver-cascade-refusal-coverage-audit.md`
- `docs/v1.10/quality/pivot-9.2-sqlserver-cascade-refusal-quality.md`

## Quality Findings

| Check | Result |
|---|---|
| Scope limited to SQL Server refusal evidence | pass |
| No public Pivot DSL change | pass |
| No schema change | pass |
| No unverified SQL Server staged SQL emitted | pass |
| No memory fallback introduced | pass |
| Refusal error path handles dialect property/method/None safely | pass |
| `SQLServerExecutor` dialect inference added for lifecycle consistency | pass |
| Tests prove executor is not called for refused cascade | pass |

## Risk Review

- SQL Server non-cascade query behavior may now infer `SqlServerDialect` from `SQLServerExecutor`; this is consistent with existing MySQL/PostgreSQL/SQLite inference.
- SQL Server cascade support remains unavailable by design.
- Any future SQL Server support must add a renderer and real SQL Server oracle parity before changing this refusal decision.

Quality conclusion: passed for P2 accepted-refusal.
