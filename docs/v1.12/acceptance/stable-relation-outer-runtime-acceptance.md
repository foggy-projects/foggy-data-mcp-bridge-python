---
acceptance_scope: feature
version: v1.12
target: stable-relation-outer-query-runtime
doc_role: acceptance-record
doc_purpose: 记录 Python stable relation S7e/S7f outer aggregate/window runtime parity 的功能签收边界
status: signed-off
decision: accepted-with-risks
signed_off_by: root-controller
signed_off_at: 2026-05-03
blocking_items: []
follow_up_required: yes
---

# Stable Relation Outer Runtime Acceptance

## Document Purpose

- doc_type: acceptance
- intended_for: reviewer / root-controller / python-engine-agent
- purpose: 记录 v1.12 P1 对 Java S7e/S7f stable relation outer aggregate/window 的 Python runtime 对齐结果。

## Requirement

v1.11 已确认 Python 只消费 Java S7e/S7f snapshot，未声明 runtime parity。v1.12 P1 补齐内部 runtime 编译器：

- 输入：已授权的 `CompiledRelation`。
- 输出：可执行 SQL、参数、`OutputSchema`。
- 范围：S7e outer aggregate、S7f outer window。
- 约束：不改变 public DSL，不开放 raw SQL escape hatch。

## Implemented Behavior

| Behavior | Status | Evidence |
|---|---|---|
| outer aggregate over inline relation | implemented | SQLite oracle runtime test |
| outer aggregate over relation with inner CTE | implemented | CTE hoist + params order runtime test |
| ratio / timeWindow-derived field aggregate rejection | implemented | `RELATION_COLUMN_NOT_AGGREGATABLE` |
| MySQL 5.7 CTE relation aggregate rejection | implemented | `RELATION_OUTER_AGGREGATE_NOT_SUPPORTED` |
| outer rank using ratio as order key | implemented | SQLite oracle runtime test |
| moving average over windowable measure | implemented | SQLite oracle runtime test |
| ratio as window input rejection | implemented | `RELATION_COLUMN_NOT_WINDOWABLE` |
| MySQL 5.7 window rejection | implemented | `RELATION_OUTER_WINDOW_NOT_SUPPORTED` |
| SQL Server hoisted CTE marker | implemented | `;WITH`, no `FROM (WITH` |

## Verification

Current targeted evidence:

```powershell
pytest tests/compose/relation/test_relation_outer_query_runtime.py -q
# 9 passed
```

Full gate evidence:

```powershell
pytest tests/compose/relation -q -rs
# 106 passed in 0.15s

pytest -q
# 3961 passed in 12.14s
```

## Decision

Feature-level implementation is accepted with risks. The accepted risk is that live MySQL8/PostgreSQL/SQL Server execution is not claimed here; this feature proves runtime through SQLite oracle plus dialect marker/refusal behavior, matching the Java S7e/S7f contract evidence style.
